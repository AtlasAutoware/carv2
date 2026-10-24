"""TI INA228 on the drive board: pack current through the BMS shunt, pack voltage on B+.

Register map and scaling as in the INA228 datasheet (SBOSA20) and Linux drivers/hwmon/ina238.c:
VSHUNT, VBUS and CURRENT are 20-bit fields in 24-bit registers (low 4 bits reserved), POWER is
24-bit, ENERGY and CHARGE are 40-bit. SHUNT_CAL = 13107.2e6 * CURRENT_LSB * R_SHUNT.

The chip runs from the drive board's 3.3 V, so its accumulators start from zero every time the
car is switched on.
"""
from . import board

REG_CONFIG = 0x00
REG_ADC_CONFIG = 0x01
REG_SHUNT_CAL = 0x02
REG_VSHUNT = 0x04
REG_VBUS = 0x05
REG_DIETEMP = 0x06
REG_CURRENT = 0x07
REG_POWER = 0x08
REG_ENERGY = 0x09
REG_CHARGE = 0x0A
REG_DIAG_ALRT = 0x0B
REG_MANUFACTURER_ID = 0x3E
REG_DEVICE_ID = 0x3F

CONFIG_RSTACC = 1 << 14
# Continuous shunt, bus and temperature; 1052 us conversions; 16-sample average (about 50 ms)
ADC_CONFIG = (0xF << 12) | (5 << 9) | (5 << 6) | (5 << 3) | 2

VBUS_LSB = 195.3125e-6          # V
VSHUNT_LSB = 312.5e-9           # V (ADCRANGE = 0, +-163.84 mV)
DIETEMP_LSB = 7.8125e-3         # degC


def _s(value, bits):
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


class INA228:
    def __init__(self, bus, addr=board.INA228_ADDR, r_shunt=board.BMS_SHUNT_OHM, max_current=327.68):
        self.bus = bus
        self.addr = addr
        self.r_shunt = r_shunt
        # Full shunt range at ADCRANGE 0 is 163.84 mV / 0.5 mOhm = 327.68 A
        self.current_lsb = max_current / (1 << 19)
        self.shunt_cal = int(round(13107.2e6 * self.current_lsb * r_shunt))
        if not 0 < self.shunt_cal < 0x8000:
            raise ValueError('SHUNT_CAL out of range for this shunt and current')

    def _read(self, reg, nbytes):
        return int.from_bytes(self.bus.write_read(self.addr, [reg], nbytes), 'big')

    def _write16(self, reg, value):
        self.bus.write(self.addr, [reg, (value >> 8) & 0xFF, value & 0xFF])

    def identify(self):
        mfr = self._read(REG_MANUFACTURER_ID, 2)
        dev = self._read(REG_DEVICE_ID, 2)
        return mfr == 0x5449 and (dev >> 4) == 0x228, mfr, dev

    def configure(self, reset_accumulators=False):
        ok, mfr, dev = self.identify()
        if not ok:
            raise IOError(f'no INA228 at 0x{self.addr:02x} (manufacturer 0x{mfr:04x}, device 0x{dev:04x})')
        self._write16(REG_CONFIG, CONFIG_RSTACC if reset_accumulators else 0)
        self._write16(REG_ADC_CONFIG, ADC_CONFIG)
        self._write16(REG_SHUNT_CAL, self.shunt_cal)

    def bus_voltage(self):
        return (self._read(REG_VBUS, 3) >> 4) * VBUS_LSB

    def shunt_voltage(self):
        return _s(self._read(REG_VSHUNT, 3) >> 4, 20) * VSHUNT_LSB

    def current(self):
        """Amps; positive while the pack discharges (IN+ is on the pack side of the shunt)."""
        return _s(self._read(REG_CURRENT, 3) >> 4, 20) * self.current_lsb

    def power(self):
        return self._read(REG_POWER, 3) * 3.2 * self.current_lsb

    def energy(self):
        """Joules since the accumulators were last reset (always positive)."""
        return self._read(REG_ENERGY, 5) * 16 * 3.2 * self.current_lsb

    def charge(self):
        """Coulombs since the accumulators were last reset; discharge counts up."""
        return _s(self._read(REG_CHARGE, 5), 40) * self.current_lsb

    def die_temperature(self):
        return _s(self._read(REG_DIETEMP, 2), 16) * DIETEMP_LSB

    def read_all(self):
        return {
            'voltage': self.bus_voltage(),
            'current': self.current(),
            'power': self.power(),
            'charge_c': self.charge(),
            'energy_j': self.energy(),
            'die_temp': self.die_temperature(),
        }
