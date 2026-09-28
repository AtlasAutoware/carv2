"""I2C access for the Atlas tools.

Everything above this file talks to a bus through three calls: write, read and write_read (a write
then a read with a repeated start, one transaction). LinuxI2C does that through /dev/i2c-N
(smbus2); FtdiI2C through an FT232H on a laptop (pyftdi); tests use fakes with the same calls.
"""
import fcntl
import os
import threading


class I2CError(IOError):
    pass


class LinuxI2C:
    """A Linux i2c-dev bus, e.g. LinuxI2C(7) for /dev/i2c-7.

    i2c-dev takes at most 8192 bytes per message; nothing here sends more than 66.
    """

    def __init__(self, bus):
        from smbus2 import SMBus, i2c_msg
        self._msg = i2c_msg
        self.bus = bus
        try:
            self._smbus = SMBus(bus)
        except OSError as e:
            raise I2CError(f'cannot open /dev/i2c-{bus}: {e}') from e

    def write(self, addr, data):
        try:
            self._smbus.i2c_rdwr(self._msg.write(addr, list(data)))
        except OSError as e:
            raise I2CError(f'i2c-{self.bus} 0x{addr:02x} write: {e}') from e

    def read(self, addr, n):
        m = self._msg.read(addr, n)
        try:
            self._smbus.i2c_rdwr(m)
        except OSError as e:
            raise I2CError(f'i2c-{self.bus} 0x{addr:02x} read: {e}') from e
        return bytes(list(m))

    def write_read(self, addr, data, n):
        w = self._msg.write(addr, list(data))
        r = self._msg.read(addr, n)
        try:
            self._smbus.i2c_rdwr(w, r)
        except OSError as e:
            raise I2CError(f'i2c-{self.bus} 0x{addr:02x} write/read: {e}') from e
        return bytes(list(r))

    def close(self):
        self._smbus.close()


class FtdiI2C:
    """An FT232H (Adafruit #2264, I2C switch on) driven from a laptop with pyftdi.

    Wiring to the drive board's stack socket with the brain board off: D0 (SCL) to pin 19,
    D1/D2 (SDA) to pin 20, GND to pin 36. The drive board has 10k pull-ups on both lines.
    The TPS25751 stretches the clock, which the FT232H only follows if D7 is wired to D0 and
    clockstretching is on (pyftdi's rule), so that wire is needed for `atlas pd` commands.

    url: pyftdi device URL, 'ftdi://ftdi:232h/1' for the first FT232H.
    """

    def __init__(self, url='ftdi://ftdi:232h/1', frequency=100e3, clockstretching=True):
        from pyftdi.i2c import I2cController, I2cNackError
        self._nack = I2cNackError
        self._ctrl = I2cController()
        self._ctrl.configure(url, frequency=frequency, clockstretching=clockstretching)
        self.bus = url

    def _port(self, addr):
        return self._ctrl.get_port(addr)

    def write(self, addr, data):
        try:
            self._port(addr).write(bytes(data))
        except self._nack as e:
            raise I2CError(f'0x{addr:02x} NACK on write: {e}') from e

    def read(self, addr, n):
        try:
            return bytes(self._port(addr).read(n))
        except self._nack as e:
            raise I2CError(f'0x{addr:02x} NACK on read: {e}') from e

    def write_read(self, addr, data, n):
        try:
            return bytes(self._port(addr).exchange(bytes(data), n))
        except self._nack as e:
            raise I2CError(f'0x{addr:02x} NACK: {e}') from e

    def close(self):
        self._ctrl.terminate()


class BusLock:
    """An advisory lock so two Atlas processes never interleave transactions on one chip.

    The kernel serialises single transactions, but a read-modify-write of the expander, or a
    4CC command to the PD controller, is several. Re-entrant within one process, so a long
    sequence can hold the lock around helpers that take it too.
    """
    _held = {}                  # path -> [file, depth]
    _mutex = threading.RLock()

    def __init__(self, name):
        self.path = f'/run/lock/atlas-{name}.lock'

    def __enter__(self):
        BusLock._mutex.acquire()
        entry = BusLock._held.get(self.path)
        if entry:
            entry[1] += 1
            return self
        try:
            f = open(self.path, 'w')
        except OSError:
            f = open(os.path.join('/tmp', os.path.basename(self.path)), 'w')
        fcntl.flock(f, fcntl.LOCK_EX)
        BusLock._held[self.path] = [f, 1]
        return self

    def __exit__(self, *exc):
        entry = BusLock._held[self.path]
        entry[1] -= 1
        if entry[1] == 0:
            fcntl.flock(entry[0], fcntl.LOCK_UN)
            entry[0].close()
            del BusLock._held[self.path]
        BusLock._mutex.release()
        return False
