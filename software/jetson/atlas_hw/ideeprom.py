"""The drive board's ID EEPROM: Microchip 24AA02 (256 bytes, 8-byte pages, WP tied low), 0x50 on
the stack I2C. Holds a small record so the software can tell which board it is talking to.

Record layout (our own):
  0x00  b'ATL1'            magic and format version
  0x04  n                  length of the JSON text
  0x05  JSON, n bytes      e.g. {"board": "ATLAS-DRV-1", "rev": "A", "serial": "001", "built": "2026-10-20"}
  0x05+n  CRC-32 of bytes 0x00..0x04+n, little-endian
The rest of the chip is left alone. A blank chip reads 0xFF.
"""
import json
import struct
import time
import zlib

from . import board

SIZE = 256
PAGE = 8
WRITE_MS = 5            # 24AA02 write cycle, maximum
MAGIC = b'ATL1'
MAX_JSON = SIZE - 9


class IDEEPROM:
    def __init__(self, bus, addr=board.ID_EEPROM_ADDR):
        self.bus = bus
        self.addr = addr

    def read(self, offset=0, n=SIZE):
        out = bytearray()
        while len(out) < n:            # 32-byte reads keep each transaction short
            k = min(32, n - len(out))
            out += self.bus.write_read(self.addr, [offset + len(out)], k)
        return bytes(out)

    def write(self, offset, data):
        """Page writes (never across an 8-byte boundary), then read back."""
        data = bytes(data)
        if offset < 0 or offset + len(data) > SIZE:
            raise ValueError('outside the 256-byte EEPROM')
        pos = 0
        while pos < len(data):
            a = offset + pos
            k = min(PAGE - a % PAGE, len(data) - pos)
            self.bus.write(self.addr, bytes([a]) + data[pos:pos + k])
            time.sleep(WRITE_MS / 1000 + 0.001)
            pos += k
        if self.read(offset, len(data)) != data:
            raise IOError('ID EEPROM read-back differs from what was written')

    def record(self):
        """The stored record as a dict, None for a blank chip. Raises ValueError if it is damaged."""
        head = self.read(0, 5)
        if head == b'\xff' * 5:
            return None
        if head[:4] != MAGIC:
            raise ValueError(f'ID EEPROM starts with {head[:4]!r}, not an Atlas record')
        n = head[4]
        if n > MAX_JSON:
            raise ValueError('ID EEPROM record length out of range')
        body = self.read(0, 5 + n + 4)
        crc = struct.unpack('<I', body[5 + n:])[0]
        if zlib.crc32(body[:5 + n]) != crc:
            raise ValueError('ID EEPROM record CRC mismatch')
        return json.loads(body[5:5 + n].decode('utf-8'))

    def write_record(self, rec):
        text = json.dumps(rec, separators=(',', ':'), sort_keys=True).encode('utf-8')
        if len(text) > MAX_JSON:
            raise ValueError(f'record is {len(text)} bytes of JSON; {MAX_JSON} fit')
        blob = MAGIC + bytes([len(text)]) + text
        self.write(0, blob + struct.pack('<I', zlib.crc32(blob)))
