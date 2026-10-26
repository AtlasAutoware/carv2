"""The USB line protocol: framing, plain-text commands, Ctrl-C."""
from link import LineLink, parse_line
from sim import SimUsb


def test_json_and_plain_text():
    assert parse_line('{"cmd": "lidar", "on": false, "id": 3}') == {'cmd': 'lidar', 'on': False, 'id': 3}
    assert parse_line('lidar ON') == {'cmd': 'lidar', 'on': True}
    assert parse_line('fan 40') == {'cmd': 'fan', 'duty': 40}
    assert parse_line('fan auto') == {'cmd': 'fan', 'auto': True}
    assert parse_line('reboot') == {'cmd': 'reboot', 'hard': False}
    assert parse_line('reboot hard') == {'cmd': 'reboot', 'hard': True}
    assert parse_line('halt poweroff') == {'cmd': 'halt', 'verb': 'poweroff'}
    assert parse_line('bms_fets discharge_off force') == {'cmd': 'bms_fets', 'charge': True,
                                                          'discharge': False, 'force': True}
    assert parse_line('hb_timeout 0') == {'cmd': 'hb_timeout', 's': 0}
    assert parse_line('  status  ') == {'cmd': 'status'}


def test_ignored_and_bad_lines():
    assert parse_line('') is None
    assert parse_line('{"t": "status"}') is None          # an echo of our own output
    assert parse_line('{oops')['cmd'] == '?'
    assert parse_line('[1, 2]')['cmd'] == '?'
    assert parse_line('AT')['cmd'] == '?'                 # ModemManager probing, if not stopped by udev
    assert parse_line('fan fast')['cmd'] == '?'


def test_framing_cr_lf_and_split_reads():
    usb = SimUsb()
    link = LineLink(usb)
    usb.rx += b'stat'
    assert link.poll() == []
    usb.rx += b'us\r'                                      # screen sends CR for Enter
    assert link.poll() == [{'cmd': 'status'}]
    usb.rx += b'{"cmd": "hb"}\r\n\r\nlidar off\n'
    assert link.poll() == [{'cmd': 'hb'}, {'cmd': 'lidar', 'on': False}]


def test_overlong_line_is_dropped():
    usb = SimUsb()
    link = LineLink(usb)
    usb.rx += b'x' * 1000 + b'\nstatus\n'
    msgs = []
    for _ in range(10):
        msgs += link.poll()
    assert msgs == [{'cmd': 'status'}] and link.dropped == 1


def test_ctrl_c_requests_the_repl_and_leaves_the_rest():
    usb = SimUsb()
    link = LineLink(usb)
    usb.rx += b'hal\x03\r\x01'
    assert link.poll() == [{'cmd': 'repl', 'via': 'ctrl-c'}]
    assert bytes(usb.rx) == b'\r\x01'


def test_send_is_one_json_line():
    usb = SimUsb()
    LineLink(usb).send({'t': 'ack', 'cmd': 'x'})
    assert bytes(usb.tx).count(b'\n') == 1
    assert usb.received() == [{'t': 'ack', 'cmd': 'x'}]
