"""Stand-ins for the chips, so the tools can be tested without the boards.

They follow the parts' documented register behaviour closely enough to catch framing, ordering
and state-machine mistakes. FakeTPS25751's idea of a "valid" configuration is simply "one of the
bundles the test registered": it does not model TI's real validity checks.
"""
import struct

from atlas_hw.i2c import I2CError


class FakeBus:
    def __init__(self):
        self.devices = {}
        self.log = []

    def attach(self, addr, dev):
        self.devices[addr] = dev
        return dev

    def _dev(self, addr):
        dev = self.devices.get(addr)
        if dev is None or getattr(dev, 'nack', 0):
            if dev is not None:
                dev.nack -= 1
            raise I2CError(f'0x{addr:02x} NACK')
        return dev

    def write(self, addr, data):
        self.log.append(('w', addr, bytes(data)))
        self._dev(addr).write(bytes(data))

    def read(self, addr, n):
        self.log.append(('r', addr, n))
        return self._dev(addr).read(n)

    def write_read(self, addr, data, n):
        self.log.append(('wr', addr, bytes(data), n))
        return self._dev(addr).write_read(bytes(data), n)


class FakeINA228:
    def __init__(self):
        self.regs = {0x00: 0, 0x01: 0xFB68, 0x02: 0x1000, 0x04: 0, 0x05: 0, 0x06: 0, 0x07: 0,
                     0x08: 0, 0x09: 0, 0x0A: 0, 0x3E: 0x5449, 0x3F: 0x2281}
        self.size = {0x00: 2, 0x01: 2, 0x02: 2, 0x04: 3, 0x05: 3, 0x06: 2, 0x07: 3, 0x08: 3,
                     0x09: 5, 0x0A: 5, 0x3E: 2, 0x3F: 2}
        self.writes = []

    def write(self, data):
        reg = data[0]
        self.writes.append((reg, int.from_bytes(data[1:], 'big')))
        self.regs[reg] = int.from_bytes(data[1:], 'big')
        if reg == 0 and self.regs[0] & (1 << 14):
            self.regs[0x09] = self.regs[0x0A] = 0
            self.regs[0] &= ~(1 << 14)

    def write_read(self, data, n):
        reg = data[0]
        assert n == self.size[reg], f'read of 0x{reg:02x} with {n} bytes'
        return self.regs[reg].to_bytes(n, 'big')

    # helpers for tests
    def set20(self, reg, value):
        self.regs[reg] = (value & 0xFFFFF) << 4

    def set40(self, reg, value):
        self.regs[reg] = value & ((1 << 40) - 1)


class FakeEEPROM24AA02:
    def __init__(self):
        self.mem = bytearray(b'\xff' * 256)
        self.ptr = 0
        self.page_writes = []

    def write(self, data):
        self.ptr = data[0]
        payload = data[1:]
        if payload:
            assert len(payload) <= 8
            page = self.ptr & ~7
            self.page_writes.append((self.ptr, len(payload)))
            for i, b in enumerate(payload):
                self.mem[page + ((self.ptr - page + i) % 8)] = b     # wraps inside the page like the chip

    def write_read(self, data, n):
        self.ptr = data[0]
        out = bytes(self.mem[(self.ptr + i) % 256] for i in range(n))
        self.ptr = (self.ptr + n) % 256
        return out


class FakePCAL6408A:
    def __init__(self):
        self.regs = {0x00: 0x00, 0x01: 0xFF, 0x02: 0x00, 0x03: 0xFF, 0x43: 0x00, 0x44: 0xFF}
        self.inputs = 0b0000_1000          # P3 high: E-stop closed; P4 low: charging; P7 low
        self.writes = []

    def write(self, data):
        self.writes.append((data[0], data[1]))
        self.regs[data[0]] = data[1]

    def write_read(self, data, n):
        reg = data[0]
        if reg == 0x00:
            out_mask = ~self.regs[0x03] & 0xFF
            return bytes([(self.inputs & ~out_mask) | (self.regs[0x01] & out_mask)])
        return bytes([self.regs[reg]])


class FakeTPS25751:
    """PTCH / APP modes, 4CC tasks, patch burst mode and the EEPROM behind the controller."""

    def __init__(self, bus, good_bundles=(), eeprom=None):
        self.bus = bus
        self.good = [bytes(b) for b in good_bundles]
        self.eeprom = bytearray(eeprom) if eeprom is not None else bytearray(b'\xff' * 0x10000)
        self.cmd1 = b'\0\0\0\0'
        self.data1 = bytearray(64)
        self.flash_ptr = 0
        self.burst = None
        self.boot_status = 1 << 3             # EEPROM present (it answers even when blank)
        self.fail_after_flwd = None
        self.flwd_count = 0
        self.pbms_rc = 0
        self.nack = 0
        self.mode = self._boot_mode()

    # what the controller does at power-up or GAID
    def _boot_mode(self):
        for r, (p, start) in enumerate(((0x0, 0x800), (0x400, 0x4400))):
            if struct.unpack('<I', self.eeprom[p:p + 4])[0] == start and self._valid_at(start):
                return 'APP '
        return 'PTCH'

    def _valid_at(self, addr):
        return any(self.eeprom[addr:addr + len(g)] == g for g in self.good)

    def write(self, data):
        reg, count, payload = data[0], data[1], data[2:]
        assert count == len(payload), 'byte count does not match the data'
        if reg == 0x09:
            self.data1[:len(payload)] = payload
            self._last_len = count
        elif reg == 0x08:
            self._run(payload.decode('ascii'))
        else:
            raise AssertionError(f'unexpected write to 0x{reg:02x}')

    def write_read(self, data, n):
        reg = data[0]
        if reg == 0x03:
            body = self.mode.encode()
        elif reg == 0x08:
            body = self.cmd1
        elif reg == 0x09:
            body = bytes(self.data1)
        elif reg == 0x2D:
            body = self.boot_status.to_bytes(5, 'little')
        elif reg == 0x1A:
            body = (1 | (2 << 20) | (3 << 18)).to_bytes(4, 'little')
        elif reg == 0x3F:
            body = (1 | 2 | (3 << 2)).to_bytes(2, 'little')
        else:
            raise AssertionError(f'unexpected read of 0x{reg:02x}')
        return (bytes([len(body)]) + body + bytes(n))[:n]

    def _rc(self, rc=0, extra=b''):
        self.data1 = bytearray(64)
        self.data1[0] = rc
        self.data1[1:1 + len(extra)] = extra

    def _run(self, cmd):
        arg = bytes(self.data1)
        self.cmd1 = b'\0\0\0\0'
        if cmd == 'GAID':
            self.mode = self._boot_mode()
            self.nack = 3
            return
        if self.mode == 'PTCH':
            if cmd == 'PBMs':
                size, addr, timeout = struct.unpack('<IBB', arg[:6])
                if self.pbms_rc:
                    return self._rc(self.pbms_rc)
                self.burst = {'size': size, 'addr': addr, 'data': bytearray()}
                self.bus.attach(addr, _BurstTarget(self.burst))
                return self._rc(0)
            if cmd == 'PBMc' and self.burst:
                del self.bus.devices[self.burst['addr']]
                ok = len(self.burst['data']) == self.burst['size'] and bytes(self.burst['data']) in self.good
                self.burst = None
                if ok:
                    self.mode = 'APP '
                    return self._rc(0)
                return self._rc(0, b'\0\x01')          # DPCS (byte 2) non-zero
            if cmd == 'PBMe':
                if self.burst:
                    self.bus.devices.pop(self.burst['addr'], None)
                self.burst = None
                return self._rc(0)
            self.cmd1 = b'!CMD'
            return
        # APP mode
        if cmd == 'FLad':
            self.flash_ptr = struct.unpack('<I', arg[:4])[0]
            return self._rc(0)
        if cmd == 'FLwd':
            self.flwd_count += 1
            if self.fail_after_flwd is not None and self.flwd_count > self.fail_after_flwd:
                raise I2CError('simulated power cut')
            n = self._last_len
            self.eeprom[self.flash_ptr:self.flash_ptr + n] = arg[:n]
            self.flash_ptr += n
            return self._rc(0)
        if cmd == 'FLrd':
            a = struct.unpack('<I', arg[:4])[0]
            self.data1 = bytearray(64)
            self.data1[:16] = self.eeprom[a:a + 16]
            return
        if cmd == 'FLvy':
            a = struct.unpack('<I', arg[:4])[0]
            return self._rc(0 if self._valid_at(a) else 1)
        if cmd == 'DBfg':
            self.boot_status &= ~(1 << 2)
            return self._rc(0)
        self.cmd1 = b'!CMD'

    _last_len = 0


class _BurstTarget:
    def __init__(self, burst):
        self.burst = burst

    def write(self, data):
        self.burst['data'] += data

