"""Pack voltage, current and an estimated state of charge, from the supervisor's status frames.

Rev B has no INA228. The JBD BMS measures the pack (voltage in 10 mV steps, current in 10 mA
steps, cell voltages, temperatures); the power board's Pico reads it about once a second and
puts it in its 1 Hz status frame (firmware/supervisor/jbd.py). If the BMS does not answer, the
Pico's own divider on the pack bus still gives the voltage, without current.

One process owns the estimate: `atlas battery-daemon` (atlas-battery.service), which is also the
supervisor link daemon (supervisor.Daemon: heartbeat, JETSON_UP, socket). It writes the live
state to /run/atlas/battery.json on every status frame, which the CLI and the ROS 2 node read,
and saves the estimate to /var/lib/atlas/battery.json so the next start-up can continue from it.

How the estimate works (unchanged from rev A, only the source changed)
  - At start-up, from the pack voltage. The Jetson already draws current by then, so the voltage
    is corrected by I x R_PACK before the lookup in OCV_TABLE.
  - After that, coulomb counting: the daemon integrates the BMS current between status frames
    (rev A's INA228 did this in hardware). The BMS's own state of charge (RSOC) is reported next
    to it as bms_soc; it keeps counting while the car is off, so once the BMS's capacity
    settings are right it may become the better number.
  - The saved estimate is kept at start-up if it is within SAVED_TRUST of the voltage estimate.
    Otherwise the voltage wins: the pack was charged or used while the car was off.

OCV_TABLE and R_PACK are placeholders, not Molicel P28A data: a generic rest-voltage curve for
NMC 18650 cells and a rough guess at the pack resistance. Replace both with measurements
(ATLAS_PACK_R and /etc/atlas/ocv.json) before trusting the percentage below about 20 %.
"""
import json
import os
import time

from . import board

LIVE_PATH = '/run/atlas/battery.json'
STATE_PATH = '/var/lib/atlas/battery.json'
SAVE_PERIOD = 60.0
SAVED_TRUST = 0.15
MAX_GAP_S = 5.0             # longer gaps between frames are not integrated (link down)

# per-cell rest voltage -> state of charge; generic NMC shape, see the module docstring
OCV_TABLE = [
    (3.30, 0.00), (3.50, 0.03), (3.60, 0.07), (3.66, 0.10), (3.70, 0.15), (3.73, 0.20),
    (3.77, 0.30), (3.80, 0.40), (3.84, 0.50), (3.88, 0.60), (3.94, 0.70), (4.00, 0.80),
    (4.07, 0.90), (4.14, 0.97), (4.20, 1.00),
]
R_PACK = float(os.environ.get('ATLAS_PACK_R', '0.05'))    # ohm, guess: cells + BMS FETs + wiring


def load_ocv_table(path='/etc/atlas/ocv.json'):
    """A measured table as [[cell_volts, soc_0_to_1], ...] replaces the generic one."""
    try:
        with open(path) as f:
            table = sorted((float(v), float(s)) for v, s in json.load(f))
        if len(table) >= 2:
            return table
    except (OSError, ValueError, TypeError):
        pass
    return OCV_TABLE


def soc_from_cell_voltage(v, table=OCV_TABLE):
    if v <= table[0][0]:
        return table[0][1]
    for (v0, s0), (v1, s1) in zip(table, table[1:]):
        if v <= v1:
            return s0 + (s1 - s0) * (v - v0) / (v1 - v0)
    return table[-1][1]


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f)
    os.replace(tmp, path)


def read_live(path=None, max_age=10.0):
    """The daemon's latest state, or None if it is not running (or the file is stale)."""
    try:
        with open(path or LIVE_PATH) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if time.time() - data.get('time', 0) > max_age:
        return None
    return data


class PackSource:
    """Turns status frames into readings shaped like rev A's INA228.read_all(): voltage, current
    (positive while discharging), power, and charge_c, the coulombs counted since start-up."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.charge_c = 0.0
        self._last = None           # (time, current)

    def reading(self, status):
        bms = status.get('bms') or {}
        if bms.get('ok') and bms.get('v') is not None:
            v, i, source = float(bms['v']), float(bms.get('i', 0.0)), 'bms'
        elif status.get('bat') is not None:
            v, i, source = float(status['bat']), None, 'pico_adc'
        else:
            return None
        t = self.clock()
        if i is not None and self._last is not None:
            t0, i0 = self._last
            if 0 < t - t0 <= MAX_GAP_S:
                self.charge_c += (i + i0) / 2.0 * (t - t0)
        self._last = (t, i) if i is not None else None
        r = {'voltage': v, 'current': i if i is not None else 0.0, 'current_known': i is not None,
             'power': v * (i or 0.0), 'charge_c': self.charge_c, 'source': source,
             'charging': bool(status.get('chg'))}
        for k_out, k_in in (('cells', 'cells'), ('temps', 'temps'), ('bms_soc', 'soc'),
                            ('rem_ah', 'rem_ah'), ('full_ah', 'full_ah'), ('bms_prot', 'prot')):
            if source == 'bms' and k_in in bms:
                r[k_out] = bms[k_in]
        return r


class Estimator:
    def __init__(self, capacity_ah=board.PACK_CAPACITY_AH, cells=board.PACK_CELLS_SERIES,
                 r_pack=R_PACK, state_path=None, table=None):
        self.capacity_c = capacity_ah * 3600.0
        self.cells = cells
        self.r_pack = r_pack
        self.state_path = state_path or STATE_PATH
        self.table = table or OCV_TABLE
        self.soc0 = None
        self.q0 = None
        self.source = None

    @property
    def started(self):
        return self.soc0 is not None

    def start(self, r):
        v_rest = (r['voltage'] + r['current'] * self.r_pack) / self.cells
        soc_v = soc_from_cell_voltage(v_rest, self.table)
        saved = None
        try:
            with open(self.state_path) as f:
                saved = float(json.load(f)['soc'])
        except (OSError, ValueError, KeyError, TypeError):
            pass
        if saved is not None and abs(saved - soc_v) <= SAVED_TRUST:
            self.soc0, self.source = saved, 'saved'
        else:
            self.soc0, self.source = soc_v, 'voltage'
        self.q0 = r['charge_c']
        return self.soc0

    def read(self, r):
        r = dict(r)
        soc = self.soc0 - (r['charge_c'] - self.q0) / self.capacity_c
        r['soc'] = min(1.0, max(0.0, soc))
        r['cell_v'] = r['voltage'] / self.cells
        r['cell_v_rest'] = (r['voltage'] + r['current'] * self.r_pack) / self.cells
        r['soc_source'] = self.source
        r['time'] = time.time()
        return r

    def save(self, soc):
        _write_json(self.state_path, {'soc': soc, 'time': time.time()})


class BatteryMonitor:
    """The daemon's status callback: estimate, live file, saved state, low-voltage shutdown.

    shutdown_cell_v: if the I x R corrected cell voltage stays below this for hold_s (and the pack
    is not charging), power the Jetson off cleanly. The supervisor then sees HALT and turns the
    car off. The BMS cuts the pack at its own cell undervoltage setting (3.00 V per cell planned).
    """

    def __init__(self, shutdown_cell_v=None, hold_s=30.0, log=print, poweroff=None,
                 clock=time.monotonic, live_path=None, estimator=None, source=None):
        self.est = estimator or Estimator(table=load_ocv_table())
        self.src = source or PackSource(clock)
        self.shutdown_cell_v = shutdown_cell_v
        self.hold_s = hold_s
        self.log = log
        self.poweroff = poweroff or (lambda: os.system('systemctl poweroff'))
        self.clock = clock
        self.live_path = live_path or LIVE_PATH
        self.last = None
        self._t_save = None
        self._low_since = None
        self.powering_off = False

    def on_status(self, status):
        r = self.src.reading(status)
        if r is None:
            return None
        if not self.est.started:
            self.est.start(r)
            self.log(f'battery: start {self.est.soc0 * 100:.0f} % (from {self.est.source}, {r["source"]})')
            self._t_save = self.clock()
        r = self.est.read(r)
        self.last = r
        try:
            _write_json(self.live_path, r)
        except OSError as e:
            self.log(f'battery: cannot write {self.live_path}: {e}')
        now = self.clock()
        if now - self._t_save > SAVE_PERIOD:
            self._save(r['soc'])
            self._t_save = now
        self._low_voltage(r, now)
        return r

    def _save(self, soc):
        try:
            self.est.save(soc)
        except OSError as e:
            self.log(f'battery: cannot save the estimate: {e}')

    def _low_voltage(self, r, now):
        if not self.shutdown_cell_v or self.powering_off:
            return
        if r['cell_v_rest'] < self.shutdown_cell_v and not r['charging']:
            self._low_since = self._low_since or now
            if now - self._low_since > self.hold_s:
                self.log(f'battery: {r["cell_v_rest"]:.2f} V per cell for {self.hold_s:.0f} s, powering off')
                self._save(r['soc'])
                self.powering_off = True
                self.poweroff()
        else:
            self._low_since = None

    def stop(self):
        if self.last is not None:
            self._save(self.last['soc'])


def run_daemon(shutdown_cell_v=None, hold_s=30.0, log=print, tty=None):
    """atlas-battery.service: the supervisor link (heartbeat, JETSON_UP, socket) plus the estimate."""
    import signal
    from . import gpio, supervisor

    mon = BatteryMonitor(shutdown_cell_v=shutdown_cell_v, hold_s=hold_s, log=log)
    last = supervisor.read_live(max_age=30.0)
    lidar = last.get('lidar') if last else os.environ.get('ATLAS_LIDAR_AT_BOOT', '1').strip() in ('1', 'yes', 'true', 'on')
    try:
        lines = gpio.Lines(outputs={'JETSON_UP': 1, 'LIDAR_REQ': 1 if lidar else 0}, consumer='atlas-battery')
        log('gpio: JETSON_UP high, LIDAR_REQ ' + ('high' if lidar else 'low'))
    except gpio.GpioUnavailable as e:
        lines = None
        log(f'gpio: {e}; JETSON_UP not driven (the heartbeat still tells the supervisor the Jetson is up)')
    daemon = supervisor.Daemon(open_link=lambda: supervisor.Link(tty), lines=lines,
                               on_status=mon.on_status, log=log)
    stop = []
    signal.signal(signal.SIGTERM, lambda *a: stop.append(1))
    signal.signal(signal.SIGINT, lambda *a: stop.append(1))
    try:
        daemon.run(lambda: bool(stop))
    finally:
        mon.stop()
        if lines is not None:
            lines.release()
