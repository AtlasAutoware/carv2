"""LED patterns students read off the board."""
import main
import sequencer as Q
from sim import Rig


def flashes(rig, which, period_ms):
    """Count rising edges of one LED over one period, sampled every 10 ms."""
    n, last = 0, False
    for t in range(0, period_ms, 10):
        led = main.led_pattern(rig.seq, t)[which]
        if led and not last:
            n += 1
        last = led
    return n


def test_fault_blink_codes():
    rig = Rig()
    rig.hw.load_ohm = 0.5
    rig.run(8000)
    assert rig.state() == Q.FAULT and rig.seq.why == 'short'
    assert flashes(rig, 1, 2 * 600 + 1500) == main.FAULT_BLINKS['short'] == 2
    assert not any(main.led_pattern(rig.seq, t)[0] for t in range(0, 3000, 10))


def test_run_and_lockout_patterns():
    rig = Rig()
    rig.run(1000)
    assert main.led_pattern(rig.seq, 500) == (True, False)          # RUN, no link: green steady
    rig.hw.set_input('ESTOP_OK', 0)
    rig.run(50)
    assert main.led_pattern(rig.seq, 100) == (False, True)          # LOCKOUT, loop open
    rig.hw.set_input('ESTOP_OK', 1)
    rig.run(50)
    assert main.led_pattern(rig.seq, 100) == (True, True)           # loop closed: press to re-arm


def test_off_is_dark():
    rig = Rig()
    rig.run(1000)
    rig.hw.set_input('BUTTON_N', 0)
    rig.run(5200)
    assert rig.state() == Q.OFF
    assert not any(any(main.led_pattern(rig.seq, t)) for t in range(0, 3000, 10))
