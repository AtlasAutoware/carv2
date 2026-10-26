"""A simulated power board for running the supervisor on a PC (CPython). Not copied to the Pico.

    from sim import Rig
    rig = Rig()              # pack at 16 V, E-stop closed, Jetson off
    rig.run(500)             # 500 ms of main-loop ticks
    rig.state()              # 'RUN'

SimHardware models what the firmware can see: the motor bus charging through the precharge
resistor into the ESC's capacitors (exact RC solution, so a 10 ms tick is fine), the 74HCT08 that
only lets MAIN_EN and PRECHARGE_EN through while the E-stop loop is closed, the NTC, the Jetson's sense lines and
timed pulses. SimJbd answers BMS requests with frames built by jbd.build_response. Rig wires the
real main.App to these parts and steps it, exactly as main.py does on the Pico.
"""
import json
import math

import jbd
import pins


class SimClock:
    def __init__(self, start=1000):
        self.t = start

    def now(self):
        return self.t

    def since(self, t):
        return self.t - t

    def advance(self, ms):
        self.t += ms


def ntc_volts(celsius):
    if celsius is None:
        return pins.ADC_VREF                # open: no NTC
    t = celsius + 273.15
    r = pins.NTC_R25_OHM * math.exp(pins.NTC_BETA * (1.0 / t - 1.0 / 298.15))
    return pins.ADC_VREF * r / (r + pins.NTC_PULLUP_OHM)


class SimHardware:
    IDLE_LOAD_OHM = 330.0       # default VM load: about 50 mA at 16 V

    def __init__(self, clock, bat_v=16.0, vm_cap_uf=2000.0, precharge_ohm=10.0, vm_load_a=None):
        """vm_load_a: what the ESC (booting) and the Castle BEC with the servo draw from VM, in A at
        the pack voltage, modelled as a resistor (the review measured the case for 150-200 mA).
        Without it, IDLE_LOAD_OHM. load_ohm adds a fault (a short or partial short) in parallel."""
        self.clock = clock
        self.bat_v = bat_v
        self.vm = 0.0
        self.vm_cap_uf = vm_cap_uf
        self.precharge_ohm = precharge_ohm
        self.vm_load_a = vm_load_a
        self.load_ohm = None            # extra load on VM (a short or partial short), ohms
        self.main_switch_works = True
        self.fet_c = 25.0
        self.out = {}
        for name, _gp, level in pins.OUTPUTS:
            self.out[name] = level
        self.inp = {'ESTOP_OK': 1, 'JETSON_UP': 0, 'JETSON_3V3_SENSE': 0, 'BUTTON_N': 1,
                    'CHG_PRESENT_N': 1, 'LIDAR_REQ': 0}
        self.fan_duty = None
        self.changes = []               # (t, name, value)
        self.pulses = []                # (t, name, ms)
        self._pulse_end = {}
        self._estop_handler = None

    # ---- the hal interface
    def write(self, name, value):
        v = 1 if value else 0
        if self.out.get(name) != v:
            self.out[name] = v
            self.changes.append((self.clock.now(), name, v))

    def read(self, name):
        if name in self.inp:
            return self.inp[name]
        return self.out[name]

    def volts(self, name, samples=8):
        if name == 'VM_SENSE':
            return min(pins.ADC_VREF, self.vm / pins.VM_DIVIDER)
        if name == 'BAT_SENSE':
            return min(pins.ADC_VREF, self.bat_v / pins.BAT_DIVIDER)
        if name == 'FET_NTC':
            return ntc_volts(self.fet_c)
        raise KeyError(name)

    def pulse(self, name, ms):
        self.write(name, 1)
        self._pulse_end[name] = self.clock.now() + ms
        self.pulses.append((self.clock.now(), name, ms))

    def fan(self, percent):
        self.fan_duty = percent

    def on_estop_open(self, handler):
        self._estop_handler = handler

    # ---- test controls
    def set_input(self, name, value):
        old = self.inp[name]
        self.inp[name] = value
        if name == 'ESTOP_OK' and old == 1 and value == 0 and self._estop_handler:
            self._estop_handler(None)       # the falling-edge interrupt

    def main_closed(self):
        return bool(self.out['MAIN_EN'] and self.inp['ESTOP_OK'] and self.main_switch_works)

    def step(self, dt_ms):
        now = self.clock.now()
        for name in list(self._pulse_end):
            if now >= self._pulse_end[name]:
                del self._pulse_end[name]
                self.write(name, 0)
        if self.main_closed():
            self.vm = self.bat_v
            return
        c = self.vm_cap_uf * 1e-6
        r_load = self.IDLE_LOAD_OHM
        if self.vm_load_a:
            r_load = max(self.bat_v, 1.0) / self.vm_load_a
        if self.load_ohm is not None:
            r_load = 1.0 / (1.0 / r_load + 1.0 / max(self.load_ohm, 1e-3))
        if self.out['PRECHARGE_EN'] and self.inp['ESTOP_OK']:     # the 74HCT08 gates it too
            v_inf = self.bat_v * r_load / (r_load + self.precharge_ohm)
            tau = (r_load * self.precharge_ohm / (r_load + self.precharge_ohm)) * c
        else:
            v_inf = 0.0
            tau = r_load * c
        self.vm = v_inf + (self.vm - v_inf) * math.exp(-dt_ms / 1000.0 / tau)

    def pulses_of(self, name):
        return [p for p in self.pulses if p[1] == name]


class SimJbd:
    """A JBD BMS answering 03, 04 and E1 (frames from jbd.build_response)."""

    def __init__(self):
        self.cells_v = [3.90, 3.91, 3.90, 3.92]
        self.current_a = -1.25          # BMS sign: negative = discharging
        self.soc = 61
        self.rem_ah = 5.12
        self.full_ah = 8.40
        self.cycles = 3
        self.prot = 0
        self.fet = 3                    # bit 0 charge on, bit 1 discharge on
        self.temps_c = [22.6, 23.1]
        self.answer = True
        self.mos_writes = []

    def basic_data(self):
        v = int(round(sum(self.cells_v) * 100))
        i = int(round(self.current_a * 100)) & 0xFFFF
        d = bytearray()
        for x in (v, i, int(round(self.rem_ah * 100)), int(round(self.full_ah * 100)), self.cycles,
                  (26 << 9) | (9 << 5) | 15, 0, 0, self.prot):
            d += bytes([(x >> 8) & 0xFF, x & 0xFF])
        d += bytes([0x10, self.soc, self.fet, len(self.cells_v), len(self.temps_c)])
        for t in self.temps_c:
            k = int(round(t * 10)) + 2731
            d += bytes([k >> 8, k & 0xFF])
        return bytes(d)

    def cell_data(self):
        d = bytearray()
        for c in self.cells_v:
            mv = int(round(c * 1000))
            d += bytes([mv >> 8, mv & 0xFF])
        return bytes(d)

    def respond(self, frame):
        if not self.answer:
            return b''
        reg = frame[2]
        if frame[1] == jbd.READ and reg == jbd.REG_BASIC:
            return jbd.build_response(reg, self.basic_data())
        if frame[1] == jbd.READ and reg == jbd.REG_CELLS:
            return jbd.build_response(reg, self.cell_data())
        if frame[1] == jbd.WRITE and reg == jbd.REG_MOS:
            x = frame[5]
            self.mos_writes.append(x)
            self.fet = (0 if x & 1 else 1) | (0 if x & 2 else 2)
            return jbd.build_response(reg, b'')
        return jbd.build_response(reg, b'', status=0x80)


class SimUart:
    """The BMS port: requests go to a SimJbd, answers come back after delay_ms."""

    def __init__(self, clock, bms=None, delay_ms=40):
        self.clock = clock
        self.bms = bms or SimJbd()
        self.delay_ms = delay_ms
        self.sent = []
        self._queue = []                # (ready_at, bytes)

    def write(self, data):
        data = bytes(data)
        self.sent.append(data)
        reply = self.bms.respond(data)
        if reply:
            self._queue.append((self.clock.now() + self.delay_ms, reply))

    def read(self):
        now = self.clock.now()
        out = b''
        keep = []
        for ready, data in self._queue:
            if now >= ready:
                out += data
            else:
                keep.append((ready, data))
        self._queue = keep
        return out


class SimUsb:
    """The USB CDC port: tests put lines in rx and read the Pico's lines from tx."""

    def __init__(self):
        self.rx = bytearray()
        self.tx = bytearray()

    def read_available(self, limit=256):
        n = min(limit, len(self.rx))
        for i in range(n):
            if self.rx[i] == 3:
                n = i + 1
                break
        out = bytes(self.rx[:n])
        del self.rx[:n]
        return out

    def write(self, data):
        self.tx += data

    def send(self, obj_or_text):
        if isinstance(obj_or_text, dict):
            obj_or_text = json.dumps(obj_or_text)
        self.rx += obj_or_text.encode() + b'\n'

    def received(self):
        """Every JSON line the Pico has written since the last call."""
        lines = bytes(self.tx).split(b'\n')
        self.tx = bytearray(lines[-1])
        out = []
        for line in lines[:-1]:
            if line.strip():
                out.append(json.loads(line))
        return out


class Rig:
    """The whole supervisor (main.App) on simulated hardware."""

    def __init__(self, settings=None, cold_start=True, bat_v=16.0, **hw_kwargs):
        import main
        import sequencer
        self.S = settings or sequencer.Settings
        self.clock = SimClock()
        self.hw = SimHardware(self.clock, bat_v=bat_v, **hw_kwargs)
        self.bms = SimJbd()
        self.uart = SimUart(self.clock, self.bms)
        self.usb = SimUsb()
        self.app = main.App(self.hw, self.clock, self.usb, self.uart, settings=self.S,
                            cold_start=cold_start)
        self.seq = self.app.seq
        self.msgs = []

    def run(self, ms):
        """Advance ms milliseconds of main-loop ticks; collect what the Pico sent."""
        tick = self.S.TICK_MS
        for _ in range(int(ms // tick)):
            self.clock.advance(tick)
            self.hw.step(tick)
            self.app.step()
        self.msgs += self.usb.received()
        return self

    def state(self):
        return self.seq.state

    def events(self, name=None):
        evts = [m for m in self.msgs if m.get('t') == 'evt']
        if name:
            evts = [e for e in evts if e['evt'] == name]
        return evts

    def replies(self, t=None):
        return [m for m in self.msgs if t is None or m.get('t') == t]

    def jetson_boots(self, boot='b00t0001'):
        """The Jetson comes up: 3.3 V, then JETSON_UP and heartbeats."""
        self.hw.set_input('JETSON_3V3_SENSE', 1)
        self.hw.set_input('JETSON_UP', 1)
        self.heartbeat(boot)
        return self

    def heartbeat(self, boot='b00t0001'):
        self.usb.send({'cmd': 'hb', 'boot': boot})

    def run_with_heartbeat(self, ms, boot='b00t0001', every=1000):
        while ms > 0:
            self.heartbeat(boot)
            step = min(every, ms)
            self.run(step)
            ms -= step
        return self

    def press(self, ms=200):
        self.hw.set_input('BUTTON_N', 0)
        self.run(ms)
        self.hw.set_input('BUTTON_N', 1)
        self.run(100)
        return self
