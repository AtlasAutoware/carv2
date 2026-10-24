"""JBD / Xiaoxiang smart BMS protocol over UART (9600 8N1): the part the supervisor uses.

Sources (read Oct 24, 2026):
  - JBD "General Protocol V4" (Jiabaida.communication.protocol.pdf), in the docs/ folder of
    github.com/syssi/esphome-jbd-bms at commit 48a0d97. Frame layout, registers 03/04/05/E1,
    field units, the protection bits, and the example frames used in tests/test_jbd.py.
  - esphome-jbd-bms components/jbd_bms/jbd_bms.cpp (same commit): checksum code, the 100 mA
    unit flag in bit 7 of the FET byte (not in the V4 document), the MOSFET bit meanings.

Frame format (from the protocol document; NOT YET VERIFIED ON THE TEAM'S BMS):
  request   DD  A5|5A  reg     len  data  chk_hi chk_lo  77     A5 = read, 5A = write
  response  DD  reg    status  len  data  chk_hi chk_lo  77     status 00 = ok, 80 = error
  chk = 0x10000 - sum(bytes 2 .. 3+len), i.e. reg+len+data in a request, status+len+data in a
  response. Values are big-endian.

Registers used: 03 basic information, 04 cell voltages, E1 MOSFET control (write 00 XX:
bit 0 set = charge FET off, bit 1 set = discharge FET off, 00 = release both).
"""

START = 0xDD
END = 0x77
READ = 0xA5
WRITE = 0x5A
REG_BASIC = 0x03
REG_CELLS = 0x04
REG_VERSION = 0x05
REG_MOS = 0xE1

MAX_DATA = 100          # longest data field accepted (a 32-cell 04 frame is 64 bytes)

# Protection status bits (V4 document, "Remark 1"), short names for the status frame
PROTECTION = ('cell_ov', 'cell_uv', 'pack_ov', 'pack_uv', 'chg_ot', 'chg_ut', 'dsg_ot', 'dsg_ut',
              'chg_oc', 'dsg_oc', 'short', 'afe_error', 'mos_lock', 'chg_timeout')


def checksum(data):
    """0x10000 minus the byte sum, 16 bits ("sum, invert, plus 1" in the V4 document)."""
    s = 0
    for b in data:
        s += b
    return (0x10000 - s) & 0xFFFF


def _frame(second, third, data):
    body = bytes([third, len(data)]) + bytes(data)
    c = checksum(body)
    return bytes([START, second]) + body + bytes([c >> 8, c & 0xFF, END])


def build_request(reg, data=b'', write=False):
    """A request frame, e.g. build_request(0x03) == DD A5 03 00 FF FD 77."""
    return _frame(WRITE if write else READ, reg, data)


def build_response(reg, data, status=0):
    """A response frame as the BMS sends it (used by the simulator and the tests)."""
    return _frame(reg, status, data)


def mos_value(charge_on, discharge_on):
    return (0 if charge_on else 1) | (0 if discharge_on else 2)


def mos_request(charge_on, discharge_on):
    return build_request(REG_MOS, bytes([0, mos_value(charge_on, discharge_on)]), write=True)


def _u16(d, i):
    return (d[i] << 8) | d[i + 1]


def _s16(d, i):
    v = _u16(d, i)
    return v - 0x10000 if v & 0x8000 else v


def parse_basic(d):
    """Register 03 data -> dict. Current is the BMS's own sign: positive while charging."""
    if len(d) < 23:
        raise ValueError('basic info: %d data bytes, need 23' % len(d))
    scale = 0.1 if d[20] & 0x80 else 0.01       # 10 mA / 10 mAh units, or 100 mA with the flag
    temps = []
    for k in range(d[22]):
        j = 23 + 2 * k
        if j + 1 < len(d):
            temps.append(round((_u16(d, j) - 2731) / 10.0, 1))     # 0.1 K, 2731 = 0 C
    date = _u16(d, 10)
    return {
        'v': round(_u16(d, 0) * 0.01, 2),
        'i_chg': round(_s16(d, 2) * scale, 2),
        'rem_ah': round(_u16(d, 4) * scale, 2),
        'full_ah': round(_u16(d, 6) * scale, 2),
        'cycles': _u16(d, 8),
        'date': '%04d-%02d-%02d' % (2000 + (date >> 9), (date >> 5) & 0x0F, date & 0x1F),
        'balance': _u16(d, 12) | (_u16(d, 14) << 16),
        'prot': _u16(d, 16),
        'sw': '%d.%d' % (d[18] >> 4, d[18] & 0x0F),
        'soc': d[19],
        'fet_chg': (d[20] & 1) != 0,
        'fet_dsg': (d[20] & 2) != 0,
        'ncell': d[21],
        'temps': temps,
    }


def parse_cells(d):
    """Register 04 data -> cell voltages in volts (2 bytes per cell, mV)."""
    if len(d) % 2 or len(d) > 64:
        raise ValueError('cell info: %d data bytes' % len(d))
    return [_u16(d, 2 * k) / 1000.0 for k in range(len(d) // 2)]


def protection_names(bits):
    out = []
    for k in range(len(PROTECTION)):
        if bits & (1 << k):
            out.append(PROTECTION[k])
    return out


class FrameParser:
    """Turns a byte stream into (reg, status, data) tuples. Resynchronises on bad frames by
    dropping one byte and looking for the next 0xDD, so a data byte that happens to be 0xDD or
    0x77 cannot lock it up. Frames whose second byte is A5/5A are our own requests coming back
    (a looped-back or echoing opto stage) and are counted, not returned."""

    def __init__(self):
        self.buf = bytearray()
        self.bad = 0
        self.echoes = 0
        self.garbage = 0

    def feed(self, data):
        self.buf += data
        out = []
        while True:
            i = 0
            n = len(self.buf)
            while i < n and self.buf[i] != START:
                i += 1
            if i:
                self.garbage += i
                self.buf = self.buf[i:]
            if len(self.buf) < 4:
                break
            length = self.buf[3]
            if length > MAX_DATA:
                self.bad += 1
                self.buf = self.buf[1:]
                continue
            total = 7 + length
            if len(self.buf) < total:
                break
            f = bytes(self.buf[:total])
            got = (f[4 + length] << 8) | f[5 + length]
            if f[total - 1] != END or checksum(f[2:4 + length]) != got:
                self.bad += 1
                self.buf = self.buf[1:]
                continue
            self.buf = self.buf[total:]
            if f[1] in (READ, WRITE):
                self.echoes += 1
                continue
            out.append((f[1], f[2], f[4:4 + length]))
        if len(self.buf) > 2 * (7 + MAX_DATA):     # never grow without bound on a noisy line
            self.garbage += len(self.buf)
            self.buf = bytearray()
        return out


class JbdClient:
    """Polls the BMS without blocking: tick() every main-loop pass.

    Each poll cycle sends 03, and 04 when 03 has answered. A MOSFET write queued with
    set_fets() goes out before the next read, and 03 is read again right after it so the
    status shows the new FET state.
    """
    POLL_MS = 1000
    TIMEOUT_MS = 300        # 9600 baud: a 4-cell 03 answer (~38 bytes) takes about 40 ms
    STALE_MS = 5000         # older than this and the status says the BMS is offline

    def __init__(self, uart, clock, poll_ms=None):
        self.uart = uart
        self.clock = clock
        self.poll_ms = poll_ms or self.POLL_MS
        self.parser = FrameParser()
        self.basic = None
        self.cells = None
        self.t_basic = None
        self.t_cells = None
        self.timeouts = 0
        self.errors = 0           # status 0x80 answers and frames that did not parse
        self.write_result = None  # None, 'pending', 'sent', 'ok', 'error', 'timeout'
        self._wait = None
        self._t_sent = None
        self._t_cycle = None
        self._next = None
        self._write = None

    def set_fets(self, charge_on, discharge_on):
        self._write = mos_request(charge_on, discharge_on)
        self.write_result = 'pending'

    def online(self):
        return self.t_basic is not None and self.clock.since(self.t_basic) < self.STALE_MS

    def age_s(self):
        if self.t_basic is None:
            return None
        return round(self.clock.since(self.t_basic) / 1000.0, 1)

    def _send(self, frame, reg):
        self.uart.write(frame)
        self._wait = reg
        self._t_sent = self.clock.now()

    def tick(self):
        data = self.uart.read()
        if data:
            for reg, status, payload in self.parser.feed(data):
                self._on_frame(reg, status, payload)
        if self._wait is not None and self.clock.since(self._t_sent) > self.TIMEOUT_MS:
            self.timeouts += 1
            if self._wait == REG_MOS:
                self.write_result = 'timeout'
            self._wait = None
            self._next = None
        if self._wait is not None:
            return
        if self._write is not None:
            frame, self._write = self._write, None
            self.write_result = 'sent'
            self._send(frame, REG_MOS)
        elif self._next is not None:
            reg, self._next = self._next, None
            self._send(build_request(reg), reg)
        elif self._t_cycle is None or self.clock.since(self._t_cycle) >= self.poll_ms:
            self._t_cycle = self.clock.now()
            self._send(build_request(REG_BASIC), REG_BASIC)

    def _on_frame(self, reg, status, payload):
        if reg == self._wait:
            self._wait = None
        if status != 0:
            self.errors += 1
            if reg == REG_MOS:
                self.write_result = 'error'
            return
        try:
            if reg == REG_BASIC:
                self.basic = parse_basic(payload)
                self.t_basic = self.clock.now()
                self._next = REG_CELLS
            elif reg == REG_CELLS:
                self.cells = parse_cells(payload)
                self.t_cells = self.clock.now()
            elif reg == REG_MOS:
                self.write_result = 'ok'
                self._next = REG_BASIC          # read the FET state back at once
        except ValueError:
            self.errors += 1

    def summary(self):
        """The 'bms' part of the status frame. Current uses the Atlas sign (positive while
        discharging, as rev A's INA228), so 'i' is minus the BMS's own reading."""
        out = {'ok': self.online(), 'age': self.age_s(), 'timeouts': self.timeouts,
               'errors': self.errors + self.parser.bad}
        b = self.basic
        if b is not None:
            out['v'] = b['v']
            out['i'] = round(-b['i_chg'], 2)
            out['soc'] = b['soc']
            out['rem_ah'] = b['rem_ah']
            out['full_ah'] = b['full_ah']
            out['cycles'] = b['cycles']
            out['prot'] = b['prot']
            if b['prot']:
                out['prot_names'] = protection_names(b['prot'])
            out['fet_chg'] = b['fet_chg']
            out['fet_dsg'] = b['fet_dsg']
            out['balance'] = b['balance']
            out['temps'] = b['temps']
        if self.cells is not None:
            out['cells'] = [round(c, 3) for c in self.cells]
        if self.write_result is not None:
            out['fet_write'] = self.write_result
        return out
