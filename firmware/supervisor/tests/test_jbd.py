"""JBD frame building and parsing against frames printed in JBD's own protocol document.

Recorded frames (all from "General Protocol V4", Jiabaida.communication.protocol.pdf, in
github.com/syssi/esphome-jbd-bms docs/ at commit 48a0d97, unless marked otherwise). Their
checksums were checked when they were copied here. They are documentation examples, not frames
captured from the team's BMS: the format is unverified on hardware.
"""
import pytest

import jbd
from sim import SimClock, SimJbd, SimUart


def hx(s):
    return bytes.fromhex(s.replace(' ', ''))


# Section 3: host sends / BMS feedback (15-cell pack)
DOC_REQ_BASIC = hx('DD A5 03 00 FF FD 77')
DOC_REQ_CELLS = hx('DD A5 04 00 FF FC 77')
DOC_REQ_VERSION = hx('DD A5 05 00 FF FB 77')
DOC_BASIC_15S = hx('DD 03 00 1B 17 00 00 00 02 D0 03 E8 00 00 20 78 00 00 00 00 00 00 10 48 03 0F '
                   '02 0B 76 0B 82 FB FF 77')
DOC_CELLS_15S = hx('DD 04 00 1E 0F 66 0F 63 0F 63 0F 64 0F 3E 0F 63 0F 37 0F 5B 0F 65 0F 3B 0F 63 '
                   '0F 63 0F 3C 0F 66 0F 3D F9 F9 77')
DOC_VERSION = hx('DD 05 00 0A 30 31 32 33 34 35 36 37 38 39 FD E9 77')
# Section 4: "the host sends DD 5A E1 02 00 02 FF 1B 77, it means software shutdown discharging MOS"
DOC_MOS_DSG_OFF = hx('DD 5A E1 02 00 02 FF 1B 77')
# Section 5: the field-by-field walk-throughs (17-cell pack), reassembled from the listed fields
DOC_BASIC_17S = hx('DD 03 00 1F 19 DF F8 24 0D A5 0F A0 00 02 24 91 00 00 00 00 00 00 12 57 03 11 '
                   '04 0B 98 0B A9 0B 96 0B 97 F8 9A 77')
DOC_CELLS_17S = hx('DD 04 00 22 0E C8 0E C8 0E CB 0E CF 0E CA 0E C7 0E CA 0E CD 0E C9 0E CA 0E CB '
                   '0E CB 0E C8 0E CC 0E C8 0E C9 0E C9 F1 87 77')
# A 4-cell answer from the comment in esphome-jbd-bms jbd_bms.cpp (same commit)
ESPHOME_BASIC_4S = hx('DD 03 00 1D 06 17 00 00 01 F3 01 F4 00 00 2C 7C 00 00 00 00 00 00 80 64 03 04 '
                      '03 0B 8D 0B 8C 0B 88 FA 85 77')


def one(frame):
    p = jbd.FrameParser()
    out = p.feed(frame)
    assert len(out) == 1 and p.bad == 0
    return out[0]


# ---------------------------------------------------------------- building
def test_read_requests_match_the_document():
    assert jbd.build_request(jbd.REG_BASIC) == DOC_REQ_BASIC
    assert jbd.build_request(jbd.REG_CELLS) == DOC_REQ_CELLS
    assert jbd.build_request(jbd.REG_VERSION) == DOC_REQ_VERSION


def test_mos_request_matches_the_document():
    assert jbd.mos_request(charge_on=True, discharge_on=False) == DOC_MOS_DSG_OFF
    assert jbd.mos_value(True, True) == 0
    assert jbd.mos_value(False, True) == 1
    assert jbd.mos_value(False, False) == 3


def test_document_checksums():
    for f in (DOC_BASIC_15S, DOC_CELLS_15S, DOC_VERSION, DOC_BASIC_17S, DOC_CELLS_17S, ESPHOME_BASIC_4S):
        n = f[3]
        assert jbd.checksum(f[2:4 + n]) == (f[4 + n] << 8 | f[5 + n])


# ---------------------------------------------------------------- parsing the document's frames
def test_basic_15s():
    reg, status, data = one(DOC_BASIC_15S)
    assert (reg, status) == (0x03, 0)
    b = jbd.parse_basic(data)
    assert b['v'] == pytest.approx(58.88)
    assert b['i_chg'] == 0
    assert b['rem_ah'] == pytest.approx(7.20)
    assert b['full_ah'] == pytest.approx(10.00)
    assert b['soc'] == 72 and b['ncell'] == 15 and b['sw'] == '1.0'
    assert b['fet_chg'] and b['fet_dsg']
    assert b['temps'] == [pytest.approx(20.3), pytest.approx(21.5)]


def test_basic_17s_discharging():
    b = jbd.parse_basic(one(DOC_BASIC_17S)[2])
    assert b['v'] == pytest.approx(66.23)
    assert b['i_chg'] == pytest.approx(-20.12)          # "the final current is -20.12A"
    assert b['rem_ah'] == pytest.approx(34.93)
    assert b['full_ah'] == pytest.approx(40.00)
    assert b['cycles'] == 2 and b['soc'] == 87 and b['ncell'] == 17
    # The document writes "2968 - 2731 = 247 ... = 24.7 C"; 2968 - 2731 is 237, so 23.7 C
    assert b['temps'][0] == pytest.approx(23.7)
    assert len(b['temps']) == 4


def test_basic_4s_esphome_example():
    b = jbd.parse_basic(one(ESPHOME_BASIC_4S)[2])
    assert b['v'] == pytest.approx(15.59)
    assert b['ncell'] == 4 and b['soc'] == 100 and b['sw'] == '8.0'
    assert b['rem_ah'] == pytest.approx(4.99) and b['full_ah'] == pytest.approx(5.00)
    assert b['temps'] == [pytest.approx(22.6), pytest.approx(22.5), pytest.approx(22.1)]
    assert b['date'] == '2022-03-28'


def test_cells():
    cells = jbd.parse_cells(one(DOC_CELLS_15S)[2])
    assert len(cells) == 15 and cells[0] == pytest.approx(3.942)
    cells = jbd.parse_cells(one(DOC_CELLS_17S)[2])
    assert len(cells) == 17 and cells[0] == pytest.approx(3.784) and cells[3] == pytest.approx(3.791)


def test_version_frame():
    reg, status, data = one(DOC_VERSION)
    assert reg == 0x05 and data == b'0123456789'


def test_hundred_milliamp_flag():
    data = bytearray(one(ESPHOME_BASIC_4S)[2])
    data[2:4] = bytes([0xFF, 0xF6])                     # -10 counts
    data[20] |= 0x80                                    # esphome-jbd-bms: 100 mA / 100 mAh units
    b = jbd.parse_basic(bytes(data))
    assert b['i_chg'] == pytest.approx(-1.0)
    assert b['full_ah'] == pytest.approx(50.0)


def test_short_basic_frame_is_rejected():
    with pytest.raises(ValueError):
        jbd.parse_basic(bytes(22))


def test_protection_names():
    assert jbd.protection_names(0) == []
    assert jbd.protection_names((1 << 1) | (1 << 10)) == ['cell_uv', 'short']


# ---------------------------------------------------------------- the parser on a messy line
def test_parser_garbage_split_and_back_to_back():
    p = jbd.FrameParser()
    stream = b'\x00\x77\x12' + DOC_BASIC_15S + DOC_CELLS_15S
    out = []
    for i in range(0, len(stream), 5):                  # 5 bytes at a time, as a UART delivers them
        out += p.feed(stream[i:i + 5])
    assert [f[0] for f in out] == [0x03, 0x04]
    assert p.garbage == 3 and p.bad == 0


def test_parser_skips_a_bad_checksum_and_recovers():
    bad = bytearray(DOC_BASIC_15S)
    bad[10] ^= 0x01
    p = jbd.FrameParser()
    out = p.feed(bytes(bad) + DOC_CELLS_15S)
    assert [f[0] for f in out] == [0x04]
    assert p.bad >= 1


def test_parser_data_bytes_equal_to_start_and_end_markers():
    frame = jbd.build_response(0x04, bytes([0x0F, 0xDD, 0x0F, 0x77]))
    reg, status, data = one(frame)
    assert data == bytes([0x0F, 0xDD, 0x0F, 0x77])


def test_parser_error_status_and_echo():
    p = jbd.FrameParser()
    out = p.feed(jbd.build_response(0x03, b'', status=0x80) + DOC_REQ_BASIC)
    assert out == [(0x03, 0x80, b'')]
    assert p.echoes == 1


def test_parser_bad_length_resyncs():
    p = jbd.FrameParser()
    out = p.feed(bytes([0xDD, 0x03, 0x00, 0xF0]) + DOC_CELLS_15S)
    assert [f[0] for f in out] == [0x04]


def test_mos_answer():
    frame = jbd.build_response(jbd.REG_MOS, b'')
    assert frame == hx('DD E1 00 00 00 00 77')          # V4 document, section 4 (checksum of 00 00)
    assert one(frame) == (0xE1, 0, b'')


# ---------------------------------------------------------------- the polling client
def client(**kw):
    clock = SimClock()
    bms = SimJbd()
    uart = SimUart(clock, bms, **kw)
    return clock, bms, uart, jbd.JbdClient(uart, clock)


def run(clock, c, ms):
    for _ in range(ms // 10):
        clock.advance(10)
        c.tick()


def test_client_polls_basic_then_cells():
    clock, bms, uart, c = client()
    run(clock, c, 200)
    assert uart.sent[:2] == [DOC_REQ_BASIC, DOC_REQ_CELLS]
    assert c.online()
    s = c.summary()
    assert s['v'] == pytest.approx(15.63) and s['i'] == pytest.approx(1.25)   # Atlas sign: + = discharging
    assert s['cells'] == [3.9, 3.91, 3.9, 3.92] and s['soc'] == 61
    run(clock, c, 1000)
    assert uart.sent.count(DOC_REQ_BASIC) == 2                                # once per second


def test_client_timeouts_and_offline():
    clock, bms, uart, c = client()
    run(clock, c, 200)
    bms.answer = False
    run(clock, c, 6000)
    assert not c.online()
    assert c.timeouts >= 5
    assert c.summary()['ok'] is False


def test_client_fet_write_then_reads_back():
    clock, bms, uart, c = client()
    run(clock, c, 200)
    c.set_fets(charge_on=False, discharge_on=True)
    run(clock, c, 200)
    assert jbd.mos_request(False, True) in uart.sent
    assert bms.mos_writes == [1]
    assert c.write_result == 'ok'
    assert c.basic['fet_chg'] is False and c.basic['fet_dsg'] is True
    i = uart.sent.index(jbd.mos_request(False, True))
    assert uart.sent[i + 1] == DOC_REQ_BASIC                                  # read back at once
