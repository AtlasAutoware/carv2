import pytest

from atlas_hw import cli
from fakes import FakeBus, FakeEEPROM24AA02, FakeINA228, FakePCAL6408A, FakeTPS25751
from test_tps25751 import LOW, full_image


@pytest.fixture
def car(monkeypatch):
    stack = FakeBus()
    tps = stack.attach(0x20, FakeTPS25751(stack, [LOW]))
    ina = stack.attach(0x40, FakeINA228())
    stack.attach(0x50, FakeEEPROM24AA02())
    sysbus = FakeBus()
    exp = sysbus.attach(0x20, FakePCAL6408A())
    monkeypatch.setattr(cli, '_stack', lambda args: stack)
    monkeypatch.setattr(cli, '_sys', lambda args: sysbus)
    monkeypatch.setattr('atlas_hw.battery.read_live', lambda *a, **k: None)
    return {'tps': tps, 'ina': ina, 'exp': exp}


def test_pd_flash_from_blank(car, tmp_path, capsys):
    img, low = tmp_path / 'full.bin', tmp_path / 'low.bin'
    img.write_bytes(full_image())
    low.write_bytes(LOW)
    cli.main(['pd', 'flash', str(img), '--lowregion', str(low)])
    out = capsys.readouterr().out
    assert 'matches the Full Flash image: yes' in out and 'booted from the EEPROM' in out
    assert car['tps'].mode == 'APP '


def test_pd_flash_blank_needs_lowregion(car, tmp_path):
    img = tmp_path / 'full.bin'
    img.write_bytes(full_image())
    with pytest.raises(SystemExit, match='--lowregion'):
        cli.main(['pd', 'flash', str(img)])


def test_pd_ensure_loads_patch(car, tmp_path, monkeypatch, capsys):
    low = tmp_path / 'low.bin'
    low.write_bytes(LOW)
    monkeypatch.setenv('ATLAS_PD_LOWREGION', str(low))
    cli.main(['pd', 'ensure'])
    assert car['tps'].mode == 'APP '
    cli.main(['pd', 'ensure'])
    assert "mode 'APP '" in capsys.readouterr().out


def test_stm32_refused_without_power_en_fix(car, monkeypatch):
    monkeypatch.delenv('ATLAS_POWER_EN_FIXED', raising=False)
    with pytest.raises(SystemExit, match='R609'):
        cli.main(['stm32', 'bootloader'])
    assert car['exp'].writes == []


def test_stm32_bootloader_sequence(car):
    cli.main(['stm32', 'bootloader', '--power-en-fixed'])
    outs = [v for r, v in car['exp'].writes if r == 0x01]
    # BOOT0 (P1) goes high before the reset pulse on P0, and the reset is released at the end
    assert outs[-3] & 0b10 and not outs[-3] & 0b01
    assert outs[-2] & 0b11 == 0b11
    assert outs[-1] & 0b11 == 0b10


def test_status_and_lidar(car, capsys):
    cli.main(['hw-init', '--lidar', 'on'])
    cli.main(['status'])
    out = capsys.readouterr().out
    assert 'lidar power  on' in out and 'E-stop       closed' in out and 'PTCH' in out


def test_id_write_and_read(car, capsys):
    cli.main(['id', '--write', '--serial', '007', '--built', '2026-10-20'])
    assert '"serial": "007"' in capsys.readouterr().out
