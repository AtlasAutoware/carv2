import os
import threading

import pytest

from atlas_hw import vesc


def test_crc16_xmodem():
    assert vesc.crc16(b'123456789') == 0x31C3        # the CRC-16/XMODEM check value


def test_packet_round_trip_and_noise():
    pkt = vesc.packet(bytes([vesc.COMM_FW_VERSION]))
    assert pkt == bytes([2, 1, 0]) + vesc.crc16(b'\x00').to_bytes(2, 'big') + b'\x03'
    payload, rest = vesc.unpack(b'\xff\x02\x99' + pkt + b'\x02')
    assert payload == b'\x00' and rest == b'\x02'


def fw_answer(major=6, minor=6, hw='60_MK6'):
    return vesc.packet(bytes([0, major, minor]) + hw.encode() + b'\0' + bytes(range(12)) + b'\0\0\0\0\0\0')


def test_parse_fw_version():
    payload, _ = vesc.unpack(fw_answer())
    fw = vesc.parse_fw_version(payload)
    assert (fw['major'], fw['minor'], fw['hw']) == (6, 6, '60_MK6')
    assert fw['uuid'] == bytes(range(12)).hex()
    with pytest.raises(ValueError):
        vesc.parse_fw_version(b'\x04\x01')


def test_probe_on_a_pty():
    master, slave = os.openpty()
    path = os.ttyname(slave)

    def esc():
        data = b''
        while vesc.packet(b'\x00') not in data:
            data += os.read(master, 64)
        os.write(master, b'\x00\x01' + fw_answer(5, 3, 'FSESC_TEST'))
    t = threading.Thread(target=esc, daemon=True)
    t.start()
    try:
        fw = vesc.probe(path, timeout=2.0)
    finally:
        os.close(master)
        os.close(slave)
    assert fw['hw'] == 'FSESC_TEST' and fw['minor'] == 3
