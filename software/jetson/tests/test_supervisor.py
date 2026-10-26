import os
import threading
import time

import pytest

from atlas_hw import supervisor as sup


def test_line_buffer_and_parse():
    lb = sup.LineBuffer()
    assert lb.feed(b'{"t":"st') == []
    assert lb.feed(b'atus"}\r\n>>> \r') == ['{"t":"status"}', '>>>']
    assert sup.parse('{"t": "ack"}') == {'t': 'ack'}
    assert sup.parse('>>> ') is None and sup.parse('[1]') is None and sup.parse('{bad') is None
    assert sup.in_repl(['MicroPython v1.24.1 on 2024-11-29; Raspberry Pi Pico with RP2040'])


def test_request_reply_and_unsolicited(pico):
    pico.start()
    pico.extra = ['{"t": "evt", "evt": "boot"}', 'some REPL noise']
    link = sup.Link()
    try:
        reply = link.request({'cmd': 'lidar', 'on': False})
        assert reply == {'t': 'ack', 'cmd': 'lidar', 'on': False, 'id': reply['id']}
        st = link.request({'cmd': 'status'})
        assert st['t'] == 'status' and st['bms']['v'] == pytest.approx(15.62)
    finally:
        link.close()
    assert pico.state['lidar'] is False


def test_port_is_raw_no_echo(pico):
    import termios
    attrs = termios.tcgetattr(pico.slave)
    attrs[3] |= termios.ECHO | termios.ICANON                  # a fresh tty: cooked, echoing
    termios.tcsetattr(pico.slave, termios.TCSANOW, attrs)
    link = sup.Link()
    try:
        pico.write({'t': 'status', 'state': 'RUN'})
        time.sleep(0.05)
        assert link.read_available() == [{'t': 'status', 'state': 'RUN'}]
        pico.pump(0.1)
        assert pico.received == []              # nothing echoed back to the Pico
    finally:
        link.close()


def test_timeout_mentions_the_repl(pico):
    pico.silent = True
    pico.extra = ['>>> ']
    pico.start()
    link = sup.Link()
    try:
        with pytest.raises(sup.SupervisorError, match='REPL'):
            link.request({'cmd': 'status'}, timeout=0.3)
    finally:
        link.close()


# ---------------------------------------------------------------- the daemon
class Running:
    """A Daemon stepping in a thread, talking to a FakePico."""

    def __init__(self, pico, lines=None, on_status=None):
        self.pico = pico
        self.logs = []
        self.daemon = sup.Daemon(open_link=lambda: sup.Link(pico.slave_path), lines=lines,
                                 boot='abcd1234', on_status=on_status, log=self.logs.append)
        self.stop = threading.Event()
        self.daemon.start_server()
        self.t = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        try:
            while not self.stop.is_set():
                self.daemon.step(0.02)
        finally:
            self.daemon.stop()

    def __enter__(self):
        self.pico.start()
        self.t.start()
        deadline = time.time() + 2
        while self.daemon.link is None and time.time() < deadline:
            time.sleep(0.01)
        return self

    def __exit__(self, *a):
        self.stop.set()
        self.t.join(2)
        self.pico.stop()


def wait_for(cond, timeout=2.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_daemon_heartbeat_status_file_and_requests(pico, run_dir):
    statuses = []
    with Running(pico, on_status=statuses.append):
        assert wait_for(lambda: 'hb' in pico.cmds())
        hb = next(m for m in pico.received if m['cmd'] == 'hb')
        assert hb['boot'] == 'abcd1234'
        pico.write(dict(pico.state))                            # the Pico's 1 Hz frame
        assert wait_for(lambda: sup.read_live() is not None)
        assert sup.read_live()['state'] == 'RUN' and statuses
        client = sup.DaemonClient()
        reply = client.request({'cmd': 'lidar', 'on': False, 'id': 'mine'})
        assert reply['t'] == 'ack' and reply['id'] == 'mine'
        fwd = [m for m in pico.received if m['cmd'] == 'lidar'][0]
        assert fwd['id'] != 'mine'                               # the daemon's own id on the wire
        assert client.request({'cmd': 'nope'})['t'] == 'err'
        info = client.request({'cmd': 'daemon'})
        assert info['link'] == pico.slave_path and info['paused'] is False
        assert client.request({'cmd': 'hb'})['t'] == 'err'       # heartbeats are the daemon's job
        assert isinstance(sup.connect(), sup.DaemonClient)
    pico.pump(0.2)
    assert pico.cmds()[-1] == 'bye'                              # said goodbye when stopped
    assert not os.path.exists(sup.SOCKET_PATH)


def test_daemon_logs_events(pico, run_dir):
    with Running(pico) as r:
        pico.write({'t': 'evt', 'evt': 'state', 'was': 'RUN', 'to': 'LOCKOUT', 'why': 'estop', 'ms': 5})
        assert wait_for(lambda: any('RUN -> LOCKOUT (estop)' in x for x in r.logs))


def test_daemon_lidar_request_also_moves_LIDAR_REQ(pico, run_dir, world):
    from atlas_hw import gpio
    lines = gpio.Lines(outputs={'JETSON_UP': 1, 'LIDAR_REQ': 1})
    try:
        with Running(pico, lines=lines) as r:
            pico.write(dict(pico.state, lidar=True))
            assert wait_for(lambda: r.daemon.lidar_state is True)
            world.history.clear()
            sup.DaemonClient().request({'cmd': 'lidar', 'on': False})
            assert [v for off, v in world.history if off == 105] == [0]
            assert world.chips['/dev/gpiochip0'][106]['value'] == 1      # JETSON_UP held
    finally:
        lines.release()


def test_daemon_syncs_LIDAR_REQ_to_reported_state(pico, run_dir, world):
    from atlas_hw import gpio
    lines = gpio.Lines(outputs={'JETSON_UP': 1, 'LIDAR_REQ': 0})
    try:
        with Running(pico, lines=lines):
            pico.write(dict(pico.state, lidar=True))
            assert wait_for(lambda: world.chips['/dev/gpiochip0'][105]['value'] == 1)
    finally:
        lines.release()


def test_daemon_lets_go_in_the_repl_and_resumes(pico, run_dir):
    with Running(pico) as r:
        pico.write('MicroPython v1.24.1 on 2024-11-29; Raspberry Pi Pico with RP2040')
        pico.write('>>> ')
        assert wait_for(lambda: r.daemon.paused)
        assert r.daemon.link is None
        reply = sup.DaemonClient().request({'cmd': 'status'})
        assert reply['t'] == 'err' and 'REPL' in reply['msg']
        sup.DaemonClient().request({'cmd': 'resume'})
        assert wait_for(lambda: r.daemon.link is not None)


def test_daemon_survives_a_missing_port(run_dir):
    logs = []
    d = sup.Daemon(open_link=lambda: sup.Link('/dev/does-not-exist'), log=logs.append)
    d.step(0.0)
    d.step(0.0)
    assert d.link is None and len(logs) == 1 and 'cannot open' in logs[0]


def test_send_halt(pico):
    pico.start()
    ack = sup.send_halt('reboot', pico.slave_path)
    assert ack['cmd'] == 'halt'
    assert pico.received[-1] == {'cmd': 'halt', 'verb': 'reboot'}
