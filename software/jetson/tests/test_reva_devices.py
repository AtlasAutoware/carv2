"""Rev A drivers (atlas_hw.reva), kept for the rev A boards in boards/drive and boards/brain."""
import pytest

from atlas_hw.i2c import BusLock
from atlas_hw.reva import board
from atlas_hw.reva.expander import Expander
from atlas_hw.reva.ideeprom import IDEEPROM
from atlas_hw.reva.ina228 import INA228
from fakes import FakeBus, FakeEEPROM24AA02, FakeINA228, FakePCAL6408A


# ---------------------------------------------------------------- INA228
def ina():
    bus = FakeBus()
    chip = bus.attach(0x40, FakeINA228())
    return chip, INA228(bus)


def test_ina228_calibration_value():
    chip, dev = ina()
    assert dev.shunt_cal == 4096                 # 13107.2e6 x (327.68 / 2^19) x 0.5 mOhm
    dev.configure(reset_accumulators=True)
    regs = dict(chip.writes)
    assert regs[0x02] == 4096 and regs[0x01] == (0xF << 12) | (5 << 9) | (5 << 6) | (5 << 3) | 2
    assert chip.writes[0] == (0x00, 1 << 14)


def test_ina228_scaling():
    chip, dev = ina()
    chip.set20(0x05, round(15.0 / 195.3125e-6))             # 15.00 V
    chip.set20(0x07, -4000)                                  # charging: negative
    chip.set40(0x0A, -3600 * 1600)                           # -3600 C at 0.625 mA per LSB
    chip.regs[0x06] = round(31.25 / 7.8125e-3)
    assert dev.bus_voltage() == pytest.approx(15.0, abs=1e-3)
    assert dev.current() == pytest.approx(-2.5)
    assert dev.charge() == pytest.approx(-3600.0)
    assert dev.die_temperature() == pytest.approx(31.25)


def test_ina228_identify_rejects_other_chip():
    chip, dev = ina()
    chip.regs[0x3F] = 0x2381
    with pytest.raises(IOError):
        dev.configure()


# ---------------------------------------------------------------- expander
def test_expander_setup_writes_output_before_direction():
    bus = FakeBus()
    chip = bus.attach(0x20, FakePCAL6408A())
    exp = Expander(bus)
    exp.setup()
    assert [r for r, v in chip.writes] == [0x01, 0x03]
    out, cfg = chip.writes[0][1], chip.writes[1][1]
    assert out & board.EXP_OUTPUTS == 0                      # P0-P2 low before they become outputs
    assert cfg == 0xFF & ~board.EXP_OUTPUTS
    assert exp.estop_ok() and exp.charging() and not exp.lidar()


def test_expander_keeps_lidar_on_across_setup():
    bus = FakeBus()
    chip = bus.attach(0x20, FakePCAL6408A())
    exp = Expander(bus)
    exp.setup()
    exp.lidar(True)
    exp.setup()
    assert exp.lidar()
    assert not (chip.regs[0x01] >> board.EXP_MCU_RST_REQ) & 1


def test_expander_refuses_inputs_and_unset_up():
    bus = FakeBus()
    bus.attach(0x20, FakePCAL6408A())
    exp = Expander(bus)
    with pytest.raises(RuntimeError):
        exp.set_line(board.EXP_LIDAR_EN, 1)
    with pytest.raises(ValueError):
        exp.set_line(board.EXP_ESTOP_OK, 1)


# ---------------------------------------------------------------- ID EEPROM
def test_id_eeprom_round_trip_and_pages():
    bus = FakeBus()
    chip = bus.attach(0x50, FakeEEPROM24AA02())
    eep = IDEEPROM(bus)
    assert eep.record() is None
    rec = {'board': 'ATLAS-DRV-1', 'rev': 'A', 'serial': '001', 'built': '2026-10-20'}
    eep.write_record(rec)
    assert eep.record() == rec
    assert all(a // 8 == (a + n - 1) // 8 for a, n in chip.page_writes)


def test_id_eeprom_detects_damage():
    bus = FakeBus()
    chip = bus.attach(0x50, FakeEEPROM24AA02())
    eep = IDEEPROM(bus)
    eep.write_record({'serial': '002'})
    chip.mem[8] ^= 0x01
    with pytest.raises(ValueError, match='CRC'):
        eep.record()


# ---------------------------------------------------------------- lock
def test_buslock_reentrant():
    with BusLock('test'):
        with BusLock('test'):
            pass
    with BusLock('test'):
        pass
