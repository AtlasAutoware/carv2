import struct

import pytest

from atlas_hw import tps25751 as T
from atlas_hw.i2c import I2CError
from fakes import FakeBus, FakeTPS25751

LOW = bytes((i * 7 + 3) & 0xFF for i in range(11392))      # SLVAFV8's example bundle size
LOW2 = bytes((i * 13 + 5) & 0xFF for i in range(9000))


def full_image(low=LOW, size=0x6000):
    img = bytearray(b'\xff' * size)
    img[0:4] = struct.pack('<I', 0x800)
    img[0x400:0x404] = struct.pack('<I', 0)
    img[0x3FC:0x400] = struct.pack('<I', 0xACE00001)
    img[0x800:0x800 + len(low)] = low
    return bytes(img)


def setup(eeprom=None, good=(LOW, LOW2)):
    bus = FakeBus()
    chip = bus.attach(0x20, FakeTPS25751(bus, good, eeprom))
    return bus, chip, T.TPS25751(bus)


def test_register_framing():
    bus, chip, tps = setup()
    assert tps.mode() == 'PTCH'
    assert bus.log[-1] == ('wr', 0x20, b'\x03', 5)          # register, then count + 4 bytes
    tps.write(T.REG_DATA1, b'\x01\x02')
    assert bus.log[-1] == ('w', 0x20, b'\x09\x02\x01\x02')  # register, count, data


def test_unknown_command_raises():
    bus, chip, tps = setup()
    with pytest.raises(T.TPSError, match='not accepted'):
        tps.command('FLad', b'\0\0\0\0', 1)                 # EEPROM commands need APP mode


def test_patch_load_blank_eeprom():
    bus, chip, tps = setup()
    assert tps.load_patch(LOW) == 'APP '
    assert chip.mode == 'APP '
    # PBMs input: size (LE32), temporary address, timeout
    pbms = [e for e in bus.log if e[0] == 'w' and e[2][:1] == b'\x09' and len(e[2]) == 8]
    assert pbms[0][2][2:] == struct.pack('<IBB', len(LOW), 0x30, 0x32)
    # the bundle went to the temporary address in 64-byte pieces
    chunks = [e[2] for e in bus.log if e[0] == 'w' and e[1] == 0x30]
    assert b''.join(chunks) == LOW and max(len(c) for c in chunks) == 64
    assert chip.eeprom == bytearray(b'\xff' * 0x10000)       # RAM only


def test_patch_load_bad_bundle_aborts():
    bus, chip, tps = setup()
    with pytest.raises(T.TPSError, match='patch complete status'):
        tps.load_patch(LOW[:-1] + b'\0')
    assert chip.mode == 'PTCH' and 0x30 not in bus.devices


def test_patch_load_pbms_error():
    bus, chip, tps = setup()
    chip.pbms_rc = 5
    with pytest.raises(T.TPSError, match='invalid temporary address'):
        tps.load_patch(LOW)


def test_patch_load_needs_ptch():
    bus, chip, tps = setup(eeprom=None)
    tps.load_patch(LOW)
    with pytest.raises(T.TPSError, match='PTCH'):
        tps.load_patch(LOW)


def test_patch_address_rules():
    bus, chip, tps = setup()
    for bad in (0, 0x20, 0x23):
        with pytest.raises(ValueError):
            tps.load_patch(LOW, temp_addr=bad)


def test_first_programming_and_boot():
    bus, chip, tps = setup()
    img = full_image()
    tps.load_patch(LOW)
    tps.eeprom_write_full(img)
    assert bytes(chip.eeprom[:len(img)]) == img
    assert tps.restart() == 'APP '                           # boots from the EEPROM now
    assert chip._boot_mode() == 'APP '


def test_full_write_cut_leaves_pointers_clear():
    bus, chip, tps = setup()
    img = full_image()
    tps.load_patch(LOW)
    chip.fail_after_flwd = 100
    with pytest.raises(I2CError):
        tps.eeprom_write_full(img)
    assert chip.eeprom[0:4] == b'\0\0\0\0' and chip.eeprom[0x400:0x404] == b'\0\0\0\0'
    assert chip._boot_mode() == 'PTCH'                       # the Jetson can load a patch again


def test_bad_full_image_rejected_before_writing():
    bus, chip, tps = setup()
    tps.load_patch(LOW)
    img = bytearray(full_image())
    img[0:4] = struct.pack('<I', 0x1234)
    with pytest.raises(T.TPSError, match='Full Flash'):
        tps.eeprom_write_full(bytes(img))
    assert chip.eeprom == bytearray(b'\xff' * 0x10000)


def test_lowregion_match():
    assert T.lowregion_matches(full_image(), LOW)
    assert not T.lowregion_matches(full_image(), LOW2)


def test_ab_update():
    img = bytearray(b'\xff' * 0x10000)
    img[:0x6000] = full_image()
    bus, chip, tps = setup(eeprom=img)
    assert chip.mode == 'APP '
    assert tps.eeprom_update(LOW2) == 1
    assert tps.region_pointer(0) == 0 and tps.region_pointer(1) == 0x4400
    assert bytes(chip.eeprom[0x4400:0x4400 + len(LOW2)]) == LOW2
    assert tps.restart() == 'APP '
    assert tps.eeprom_update(LOW) == 0                      # and back again
    assert tps.region_pointer(0) == 0x800 and tps.region_pointer(1) == 0


def test_update_refuses_without_active_region():
    bus, chip, tps = setup()
    tps.load_patch(LOW)
    with pytest.raises(T.TPSError, match='Full Flash'):
        tps.eeprom_update(LOW2)


def test_update_refuses_oversized_bundle_for_region0():
    img = bytearray(b'\xff' * 0x10000)
    img[0x400:0x404] = struct.pack('<I', 0x4400)
    img[0:4] = b'\0\0\0\0'
    img[0x4400:0x4400 + len(LOW)] = LOW
    bus, chip, tps = setup(eeprom=img)
    assert chip.mode == 'APP '
    with pytest.raises(T.TPSError, match='holds'):
        tps.eeprom_update(bytes(0x3C01))


def test_status_decoding():
    img = bytearray(b'\xff' * 0x10000)
    img[:0x6000] = full_image()
    bus, chip, tps = setup(eeprom=img)
    st = tps.status()
    assert st['mode'] == 'APP ' and st['eeprom_present'] and st['plug_present']
    assert st['vbus'] == 'PD contract' and st['sink'] and st['typec_current'] == 'PD'
