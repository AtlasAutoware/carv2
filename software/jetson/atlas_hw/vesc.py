"""A one-shot check of the FSESC on UART1 (/dev/atlas_vesc): ask for its firmware version.

VESC packet framing (bldc comm/packet.c, release_6_06 at 94b305e): 0x02, length (1 byte),
payload, CRC-16/XMODEM of the payload (util/crc.c, polynomial 0x1021, start 0), 0x03.
COMM_FW_VERSION (0) answers: 0, major, minor, hardware name (NUL-terminated), 12-byte UUID, ...
(comm/commands.c). Only one program can use the port: stop vesc_driver (the ROS node) first.
"""
import os
import select
import time

from . import board

COMM_FW_VERSION = 0


def crc16(data):
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return crc


def packet(payload):
    c = crc16(payload)
    return bytes([2, len(payload)]) + bytes(payload) + bytes([c >> 8, c & 0xFF, 3])


def unpack(buf):
    """(payload, rest) for the first valid short packet in buf, or (None, what to keep). Every
    0x02 is tried as a start, so a stray 0x02 with a large length byte cannot hide a good packet
    behind it."""
    keep_from = None
    i = buf.find(b'\x02')
    while i >= 0:
        if len(buf) - i < 2:
            keep_from = i if keep_from is None else keep_from
            break
        n = buf[i + 1]
        end = i + 2 + n + 3
        if len(buf) >= end:
            payload = buf[i + 2:i + 2 + n]
            if buf[end - 1] == 3 and crc16(payload) == (buf[end - 3] << 8 | buf[end - 2]):
                return payload, buf[end:]
        elif keep_from is None:
            keep_from = i
        i = buf.find(b'\x02', i + 1)
    return None, (b'' if keep_from is None else buf[keep_from:])


def parse_fw_version(payload):
    if not payload or payload[0] != COMM_FW_VERSION or len(payload) < 4:
        raise ValueError('not a COMM_FW_VERSION answer')
    name_end = payload.index(0, 3) if 0 in payload[3:] else len(payload)
    return {'major': payload[1], 'minor': payload[2], 'hw': payload[3:name_end].decode('ascii', 'replace'),
            'uuid': payload[name_end + 1:name_end + 13].hex()}


def probe(path=None, timeout=1.0):
    """Send COMM_FW_VERSION on the VESC UART and return the parsed answer."""
    from .supervisor import raw_tty
    path = path or board.vesc_tty()
    fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        raw_tty(fd, board.VESC_BAUD)
        os.write(fd, packet(bytes([COMM_FW_VERSION])))
        buf = b''
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            r, _, _ = select.select([fd], [], [], max(0.0, end - time.monotonic()))
            if not r:
                break
            try:
                buf += os.read(fd, 1024)
            except BlockingIOError:
                continue
            payload, buf = unpack(buf)
            if payload is not None and payload[:1] == bytes([COMM_FW_VERSION]):
                return parse_fw_version(payload)
        raise TimeoutError(f'no answer from a VESC on {path} within {timeout:g} s')
    finally:
        os.close(fd)
