"""The brain board's PCAL6408A I/O expander (U34, 0x20 on the SYS I2C bus).

At power-up every pin is an input and the output register reads 0xFF. The board's pull-downs keep
MCU_RST_REQ, MCU_BOOT0 and LIDAR_EN low while the pins are inputs. Turning P0 into an output
before its output bit is cleared would therefore reset the STM32 (and, through POWER_EN, cut the
Jetson's own supply), so this class always writes the output register first and the direction
register second.
"""
from . import board
from .i2c import BusLock

REG_INPUT = 0x00
REG_OUTPUT = 0x01
REG_POLARITY = 0x02
REG_CONFIG = 0x03       # 1 = input
REG_PULL_ENABLE = 0x43
REG_PULL_SELECT = 0x44


class Expander:
    def __init__(self, bus, addr=board.EXPANDER_ADDR):
        self.bus = bus
        self.addr = addr

    def _rd(self, reg):
        return self.bus.write_read(self.addr, [reg], 1)[0]

    def _wr(self, reg, val):
        self.bus.write(self.addr, [reg, val & 0xFF])

    def setup(self):
        """Make P0-P2 outputs without a glitch, keeping the lidar where it is."""
        with BusLock('expander'):
            config = self._rd(REG_CONFIG)
            out = self._rd(REG_OUTPUT)
            lidar_on = not (config >> board.EXP_LIDAR_EN) & 1 and (out >> board.EXP_LIDAR_EN) & 1
            out &= ~board.EXP_OUTPUTS
            if lidar_on:
                out |= 1 << board.EXP_LIDAR_EN
            self._wr(REG_OUTPUT, out)
            self._wr(REG_CONFIG, (config | 0xFF) & ~board.EXP_OUTPUTS)

    def inputs(self):
        return self._rd(REG_INPUT)

    def line(self, n):
        return (self.inputs() >> n) & 1

    def set_line(self, n, value):
        if not (board.EXP_OUTPUTS >> n) & 1:
            raise ValueError(f'expander P{n} is not an output on this board')
        with BusLock('expander'):
            config = self._rd(REG_CONFIG)
            if (config >> n) & 1:
                raise RuntimeError('expander not set up (run setup() first)')
            out = self._rd(REG_OUTPUT)
            out = (out | (1 << n)) if value else (out & ~(1 << n))
            self._wr(REG_OUTPUT, out)

    # Named helpers
    def estop_ok(self):
        return bool(self.line(board.EXP_ESTOP_OK))

    def charging(self):
        return not self.line(board.EXP_CHG_STAT_N)

    def lidar(self, on=None):
        if on is None:
            config = self._rd(REG_CONFIG)
            if (config >> board.EXP_LIDAR_EN) & 1:
                return False    # still an input: the drive board's pull-down keeps the lidar off
            return bool((self._rd(REG_OUTPUT) >> board.EXP_LIDAR_EN) & 1)
        self.set_line(board.EXP_LIDAR_EN, on)
        return on

    def pse_interrupt(self):
        return not self.line(board.EXP_PSE_INT_N)
