"""The Jetson tools against the real supervisor firmware, end to end.

firmware/supervisor/ runs under CPython on its simulated power board (sim.Rig), in real time,
with its USB port bridged to a pseudo-terminal. The Jetson side opens the pty as if it were
/dev/atlas_supervisor. This checks that both sides speak the same protocol; it does not check
MicroPython or the hardware.
"""
import os
import sys
import threading
import time
import tty

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
FIRMWARE = os.path.join(REPO, 'firmware', 'supervisor')
if not os.path.isdir(FIRMWARE):
    pytest.skip('firmware/supervisor not found', allow_module_level=True)
sys.path.insert(0, FIRMWARE)

import sequencer as Q  # noqa: E402
import sim  # noqa: E402

from atlas_hw import battery, cli  # noqa: E402
from atlas_hw import supervisor as sup  # noqa: E402


class PtyPico:
    def __init__(self):
        self.master, self.slave = os.openpty()
        tty.setraw(self.slave)
        os.set_blocking(self.master, False)
        self.path = os.ttyname(self.slave)
        self.rig = sim.Rig()
        self.rig.hw.set_input('JETSON_3V3_SENSE', 1)
        self.rig.hw.set_input('JETSON_UP', 1)
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        rig = self.rig
        last = time.monotonic()
        while not self._stop.is_set():
            now = time.monotonic()
            dt = int(min(50.0, (now - last) * 1000))
            if dt >= 1:
                last += dt / 1000.0
                rig.clock.advance(dt)
                rig.hw.step(dt)
            try:
                rig.usb.rx += os.read(self.master, 4096)
            except (BlockingIOError, OSError):
                pass
            rig.app.step()
            if rig.usb.tx:
                data, rig.usb.tx = bytes(rig.usb.tx), bytearray()
                try:
                    os.write(self.master, data)
                except OSError:
                    pass
            time.sleep(0.003)

    def start(self):
        self._t.start()
        return self

    def wait_state(self, state, timeout=3.0):
        end = time.time() + timeout
        while time.time() < end:
            if self.rig.state() == state:
                return True
            time.sleep(0.01)
        return False

    def close(self):
        self._stop.set()
        self._t.join(2)
        os.close(self.master)
        os.close(self.slave)


@pytest.fixture
def pico(monkeypatch, run_dir):
    p = PtyPico().start()
    monkeypatch.setenv('ATLAS_SUPERVISOR_TTY', p.path)
    assert p.wait_state(Q.RUN)
    yield p
    p.close()


def wait_for(cond, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_link_talks_to_the_firmware(pico):
    link = sup.Link()
    try:
        assert wait_for(lambda: pico.rig.seq.bms is not None and pico.rig.seq.bms.online())
        st = link.request({'cmd': 'status'})
        assert st['state'] == 'RUN' and st['bms']['ok'] and st['bms']['cells'] == [3.9, 3.91, 3.9, 3.92]
        assert link.request({'cmd': 'lidar', 'on': False})['t'] == 'ack'
        assert wait_for(lambda: pico.rig.hw.out['LIDAR_EN'] == 0)
        assert link.request({'cmd': 'bms_fets', 'discharge': False})['t'] == 'err'   # needs force
    finally:
        link.close()


def test_cli_status_against_the_firmware(pico, capsys):
    cli.main(['status'])
    out = capsys.readouterr().out
    assert 'supervisor   RUN' in out and 'motor bus    16.00 V, main switch on' in out


def test_daemon_heartbeat_battery_and_shutdown(pico):
    logs = []
    mon = battery.BatteryMonitor(log=logs.append)
    d = sup.Daemon(open_link=lambda: sup.Link(pico.path), on_status=mon.on_status, boot='feedbeef',
                   log=logs.append)
    stop = threading.Event()
    t = threading.Thread(target=d.run, args=(stop.is_set,), daemon=True)
    t.start()
    try:
        seq = pico.rig.seq
        assert wait_for(lambda: seq.hb_seen and seq.boot_id == 'feedbeef')
        assert wait_for(lambda: battery.read_live() is not None)
        live = battery.read_live()
        assert live['source'] == 'bms' and live['voltage'] == pytest.approx(15.63)
        assert sup.DaemonClient().request({'cmd': 'lidar', 'on': False})['on'] is False
        # the car's button: the firmware presses the Jetson's power key
        pico.rig.hw.set_input('BUTTON_N', 0)
        time.sleep(0.2)
        pico.rig.hw.set_input('BUTTON_N', 1)
        assert pico.wait_state(Q.SHUTDOWN_REQUESTED)
        assert wait_for(lambda: pico.rig.hw.pulses_of('JETSON_PWR_KEY'))
        assert any('SHUTDOWN_REQUESTED (button)' in x for x in logs)      # event in the journal
    finally:
        stop.set()                                  # systemd stops the daemon: it says bye
        t.join(3)
    assert wait_for(lambda: seq.t_bye is not None)
    assert sup.send_halt('poweroff', pico.path)['state'] == 'HALTING'      # the shutdown hook
    assert pico.wait_state(Q.HALTING, 1.0)
    assert pico.wait_state(Q.OFF, 4.0)
    assert pico.rig.hw.pulses_of('LATCH_OFF')
