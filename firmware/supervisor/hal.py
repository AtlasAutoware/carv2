"""Hardware abstraction: the only firmware module that touches `machine`.

sequencer.py, jbd.py and link.py never import `machine`. They are handed four small objects:

  clock   now() -> ms; since(t) -> ms elapsed since t (the Pico's ms counter wraps, so always
          compare times with since(), never with < or >)
  hw      write(name, 0|1), read(name) -> 0|1, volts(name) -> volts at the Pico pin,
          pulse(name, ms), fan(percent), on_estop_open(handler)
  uart    write(bytes), read() -> bytes (b'' when nothing is waiting): the BMS port, 9600 8N1
  usb     read_available() -> bytes, write(bytes): the USB CDC line to the Jetson

On the Pico these are Clock, Hardware, BmsUart and UsbSerial below. On a PC (pytest, or trying
the state machine without a board) they are the classes in sim.py, which is never copied to
the Pico, so it costs no RAM there. Names are the ones in pins.py.
"""
import time

import pins

try:
    import machine
    import micropython
    ON_PICO = True
except ImportError:         # CPython: use sim.py instead
    machine = None
    micropython = None
    ON_PICO = False


class Clock:
    def now(self):
        return time.ticks_ms()

    def since(self, t):
        return time.ticks_diff(time.ticks_ms(), t)

    def sleep_ms(self, ms):
        time.sleep_ms(ms)


class Hardware:
    """The power board as the sequencer sees it."""

    def __init__(self):
        Pin = machine.Pin
        pulls = {None: None, 'up': Pin.PULL_UP, 'down': Pin.PULL_DOWN}
        self._pins = {}
        for name, gp, level in pins.OUTPUTS:
            # value= is applied before the pin becomes an output (ports/rp2/machine_pin.c), so a
            # pin never glitches high at boot (rev A review F7)
            self._pins[name] = Pin(gp, Pin.OUT, value=level)
        for name, gp, pull in pins.INPUTS:
            self._pins[name] = Pin(gp, Pin.IN, pulls[pull])
        for gp in pins.HIGH_Z:
            Pin(gp, Pin.IN, None)
        self._adc = {}
        for name, gp in pins.ADCS:
            self._adc[name] = machine.ADC(Pin(gp))
        self._fan = machine.PWM(Pin(pins.FAN_PWM))
        self._fan.freq(pins.FAN_PWM_HZ)
        self.fan(100)
        self._timers = {}
        try:
            self._onboard = Pin('LED', Pin.OUT, value=0)     # the Pico's own LED mirrors LED_STATUS
        except (ValueError, TypeError):
            self._onboard = None

    def write(self, name, value):
        v = 1 if value else 0
        self._pins[name].value(v)
        if name == 'LED_STATUS' and self._onboard is not None:
            self._onboard.value(v)

    def read(self, name):
        return self._pins[name].value()

    def volts(self, name, samples=8):
        adc = self._adc[name]
        total = 0
        for _ in range(samples):
            total += adc.read_u16()
        return total * pins.ADC_VREF / (65535 * samples)

    def pulse(self, name, ms):
        """Pin high now, low again after ms, timed by a hardware timer so a slow main loop
        cannot stretch a power-key press (review MINOR-1: long presses can force a hard off)."""
        pin = self._pins[name]
        timer = self._timers.get(name)
        if timer is None:
            timer = machine.Timer()
            self._timers[name] = timer
        else:
            timer.deinit()

        def release(_t):
            pin.value(0)
        pin.value(1)
        try:
            timer.init(mode=machine.Timer.ONE_SHOT, period=ms, callback=release, hard=True)
        except TypeError:   # older MicroPython without hard timers
            timer.init(mode=machine.Timer.ONE_SHOT, period=ms, callback=release)

    def fan(self, percent):
        duty = max(0, min(100, int(percent)))
        if pins.FAN_PWM_INVERT:
            duty = 100 - duty
        self._fan.duty_u16(duty * 65535 // 100)

    def on_estop_open(self, handler):
        """handler(pin) runs as a hard interrupt on the falling edge of ESTOP_OK: it must only
        write pins and set flags (no floats, no new objects)."""
        self._pins['ESTOP_OK'].irq(trigger=machine.Pin.IRQ_FALLING, handler=handler, hard=True)


class BmsUart:
    def __init__(self):
        UART = machine.UART
        invert = 0
        if pins.BMS_INVERT_TX:
            invert |= UART.INV_TX
        if pins.BMS_INVERT_RX:
            invert |= UART.INV_RX
        self._u = UART(pins.BMS_UART_ID, baudrate=pins.BMS_BAUD, bits=8, parity=None, stop=1,
                       tx=machine.Pin(pins.BMS_TX), rx=machine.Pin(pins.BMS_RX),
                       timeout=0, rxbuf=256, invert=invert)

    def write(self, data):
        self._u.write(data)

    def read(self):
        n = self._u.any()
        if not n:
            return b''
        return self._u.read(n) or b''


class UsbSerial:
    """The Pico's built-in USB CDC port (the same one the MicroPython REPL normally uses).

    While main.py runs, the REPL is not active and micropython.kbd_intr(-1) stops a stray
    Ctrl-C from killing the supervisor, so this class owns the port. A Ctrl-C byte is handed
    to the link as a request for the REPL (link.py) and the bytes after it are left unread, so
    Thonny's or mpremote's raw-REPL handshake reaches the REPL intact.
    """

    def __init__(self):
        import sys
        import select
        self._in = getattr(sys.stdin, 'buffer', sys.stdin)
        self._out = getattr(sys.stdout, 'buffer', sys.stdout)
        self._raw = self._out is not sys.stdout
        self._poll = select.poll()
        self._poll.register(sys.stdin, select.POLLIN)

    def read_available(self, limit=256):
        out = bytearray()
        while len(out) < limit and self._poll.poll(0):
            b = self._in.read(1)
            if not b:
                break
            if isinstance(b, str):
                b = b.encode()
            out += b
            if b == b'\x03':
                break
        return bytes(out)

    def write(self, data):
        if self._raw:
            self._out.write(data)
        else:
            self._out.write(data.decode())


# ---------------------------------------------------------------- start-up helpers
def cold_start():
    """True after a power-on reset; False after a watchdog reset or machine.reset()."""
    return machine.reset_cause() == machine.PWRON_RESET


def start_watchdog(timeout_ms):
    return machine.WDT(timeout=timeout_ms)


def stop_watchdog():
    """MicroPython cannot stop the RP2040 watchdog once started, so clear its ENABLE bit
    (WATCHDOG CTRL bit 30) through the register's atomic-clear alias (+0x3000), as the Pico
    SDK's watchdog_disable() does. Addresses from the Pico SDK register headers
    (hardware/regs/addressmap.h, watchdog.h): RP2040 0x40058000, RP2350 (Pico 2) 0x400d8000.
    Not yet tried on a Pico."""
    import os
    base = 0x400D8000 if 'RP2350' in os.uname().machine else 0x40058000
    machine.mem32[base + 0x3000] = 1 << 30


def keyboard_interrupt(enabled):
    micropython.kbd_intr(3 if enabled else -1)
