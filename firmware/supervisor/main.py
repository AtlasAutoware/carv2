"""ATLAS-PWR-1 supervisor: MicroPython on the Raspberry Pi Pico. MicroPython runs this file at
power-up. It wires the parts together, feeds the watchdog and drives the two LEDs.

    sequencer.py  the state machine (power, E-stop, Jetson shutdown, faults)
    jbd.py        the BMS on UART0
    link.py       the JSON line protocol to the Jetson on USB
    hal.py        the pins (pins.py has the GPIO map)

Getting to the REPL (for Thonny, mpremote or a terminal):
  - hold the power button until both LEDs light (about 3 s after the Pico starts), or
  - send `repl` (or press Ctrl-C) on the USB port: the supervisor turns the motor bus off,
    stops the watchdog and leaves. The Jetson stays powered. Ctrl-D restarts the supervisor; it
    then waits for a button press before it switches the motor bus on again.
"""
import time

import hal
from jbd import JbdClient
from link import LineLink
from sequencer import (FAULT, HALTING, INIT, LOCKOUT, PRECHARGE, RUN, SHUTDOWN_REQUESTED, Sequencer,
                       Settings)

WATCHDOG_MS = 3000          # well above the worst USB write stall (MicroPython's CDC timeout)
REPL_HOLD_MS = 3000         # hold the button this long at start-up to stay in the REPL
LOCKOUT_FLAG = 'lockout.flag'   # written when leaving for the REPL: the next start waits for a press

# Fault LED blink counts (FAULT state): count the red flashes
FAULT_BLINKS = {'short': 2, 'slow': 3, 'bat_sense': 4, 'main_switch': 5}


def led_pattern(seq, t):
    """(status LED, fault LED) for the sequencer's state at time t (ms).

      INIT, PRECHARGE      green fast blink (5 Hz)
      RUN                  green on; a short dark blink every 2 s while the Jetson link is alive
      LOCKOUT              red blink 1 Hz; green on when the loop is closed (press to re-arm)
      FAULT                red flashes N times, pause (2 short, 3 slow precharge, 4 pack sense,
                           5 main switch)
      SHUTDOWN_REQUESTED,  green blink 2 Hz
      HALTING
      OFF                  both off
      low battery          red double flash every 3 s on top of the above (RUN, LOCKOUT)
    """
    s = seq.state
    green = red = False
    if s in (INIT, PRECHARGE):
        green = t % 200 < 100
    elif s == RUN:
        green = not (seq.link_alive() and t % 2000 < 100)
    elif s == LOCKOUT:
        red = t % 1000 < 500
        green = seq.estop_ok
    elif s == FAULT:
        n = FAULT_BLINKS.get(seq.why, 1)
        k = t % (n * 600 + 1500)
        red = k < n * 600 and k % 600 < 300
    elif s in (SHUTDOWN_REQUESTED, HALTING):
        green = t % 500 < 250
    if seq.low_warned and s in (RUN, LOCKOUT):
        k = t % 3000
        if k < 600:
            red = k < 150 or 300 <= k < 450
    return green, red


class App:
    """One main-loop pass is step(). main.py calls it every TICK_MS; sim.Rig does the same."""

    def __init__(self, hw, clock, usb, uart, settings=Settings, cold_start=True):
        self.hw = hw
        self.clock = clock
        self.S = settings
        self.bms = JbdClient(uart, clock)
        self.seq = Sequencer(hw, clock, settings, cold_start=cold_start, bms=self.bms)
        self.link = LineLink(usb)
        self.t_status = clock.now()
        self.seq.start()

    def step(self):
        """Returns True when the supervisor should stop and leave for the REPL."""
        seq = self.seq
        for msg in self.link.poll():
            reply = seq.command(msg)
            if reply is not None:
                self.link.send(reply)
        self.bms.tick()
        seq.tick()
        for e in seq.take_events():
            self.link.send(e)
        if self.clock.since(self.t_status) >= self.S.STATUS_PERIOD_MS:
            self.t_status = self.clock.now()
            self.link.send(seq.status())
        green, red = led_pattern(seq, self.clock.since(seq.t_start))
        self.hw.write('LED_STATUS', green)
        self.hw.write('LED_FAULT', red)
        return seq.repl_requested


def _file_exists(name):
    try:
        open(name).close()
        return True
    except OSError:
        return False


def _write_lockout_flag():
    try:
        with open(LOCKOUT_FLAG, 'w') as f:
            f.write('leave the motor bus off until the button is pressed\n')
    except OSError:
        pass


def _button_held_for_repl(hw, clock):
    t0 = clock.now()
    while hw.read('BUTTON_N') == 0:
        if clock.since(t0) >= REPL_HOLD_MS:
            return True
        time.sleep_ms(10)
    return False


def start():
    import os
    import sys
    import machine
    import micropython
    micropython.alloc_emergency_exception_buf(100)
    hw = hal.Hardware()
    clock = hal.Clock()
    if _button_held_for_repl(hw, clock):
        hw.write('LED_STATUS', 1)
        hw.write('LED_FAULT', 1)
        _write_lockout_flag()
        print('ATLAS supervisor: button held at start-up, staying in the REPL (motor bus off).')
        return
    cold = hal.cold_start() and not _file_exists(LOCKOUT_FLAG)
    if _file_exists(LOCKOUT_FLAG):
        os.remove(LOCKOUT_FLAG)
    app = App(hw, clock, hal.UsbSerial(), hal.BmsUart(), cold_start=cold)
    hal.keyboard_interrupt(False)
    wdt = hal.start_watchdog(WATCHDOG_MS)
    tick = Settings.TICK_MS
    next_t = time.ticks_ms()
    try:
        while True:
            if app.step():
                break
            wdt.feed()
            next_t = time.ticks_add(next_t, tick)
            wait = time.ticks_diff(next_t, time.ticks_ms())
            if wait > 0:
                time.sleep_ms(wait)
            else:
                next_t = time.ticks_ms()        # fell behind: do not try to catch up
    except KeyboardInterrupt:                   # only if kbd_intr was re-enabled: same as `repl`
        pass
    except Exception as e:                      # a bug: motor off, note it, start again
        app.seq.make_safe()
        try:
            with open('crash.txt', 'w') as f:
                sys.print_exception(e, f)
        except OSError:
            pass
        try:
            app.link.send({'t': 'evt', 'evt': 'crash', 'msg': repr(e)})
        except Exception:
            pass
        time.sleep_ms(200)
        machine.reset()                         # comes back in LOCKOUT ('restart')
    # leaving for the REPL on request
    app.seq.make_safe()
    hal.stop_watchdog()
    hal.keyboard_interrupt(True)
    _write_lockout_flag()
    hw.write('LED_STATUS', 1)
    hw.write('LED_FAULT', 1)
    print('ATLAS supervisor stopped: motor bus off, Jetson still powered. Ctrl-D restarts it.')


if __name__ == '__main__':
    start()
