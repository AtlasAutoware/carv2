"""The drive board's TPS25751D USB-C PD controller (U701), through its I2C target port.

The controller keeps its patch and settings in the M24512 EEPROM on its own I2C bus (I2Cc, where
it is the only controller; TI does not support a second one there). The Jetson reaches the
controller on the stack I2C and has it do everything:

  load_patch()      PTCH mode (blank or bad EEPROM): load a Low Region binary into the controller's
                    RAM with patch burst mode. It then runs it (APP mode). The EEPROM is untouched.
  eeprom_write_full()  APP mode: write TI's Full Flash binary into the EEPROM (once per board).
  eeprom_update()   APP mode: write a Low Region binary into the unused EEPROM region, verify it,
                    then switch the region pointers over (TI's A/B update).
  restart()         GAID: cold restart; the controller boots from the EEPROM.

Sources
  TI SLVSH93A (TPS25751 data sheet) 8.3.11 and 8.4.1: ADCIN1 = LDO_3V3 and ADCIN2 = GND decode to
    SafeMode with I2C address index #1 (0x20, answered during boot too). At boot the controller
    reads its EEPROM at 0x50 on I2Cc; without a valid one it waits for a host.
  TI SLVAFV8 (loading a patch from an embedded controller): PBMs input layout, the bundle may go in
    several writes because the pointer "is not reset by the I2C start or stop", 500 us between
    bursts, 20 ms after PBMc.
  TI SLVAFL1 (updating the EEPROM through the PD controller): FLad, FLwd (64 bytes, 75 us apart),
    FLrd (16 bytes out), FLvy, region pointers at 0x000 and 0x400, bundles at 0x800 and 0x4400,
    Full Flash binary for the first programming, Low Region binaries for updates.
  Linux drivers/usb/typec/tipd/core.c (TPS25750 support): byte-count framing, 4CC execution and
    "!CMD", BOOT_STATUS bits 2 and 3, PBMs/PBMc/PBMe data and timeouts, DBfg after a patch load.
"""
import struct
import time

from . import board
from .i2c import BusLock, I2CError

REG_VID = 0x00
REG_MODE = 0x03
REG_CMD1 = 0x08
REG_DATA1 = 0x09
REG_VERSION = 0x0F
REG_STATUS = 0x1A
REG_BOOT_STATUS = 0x2D
REG_POWER_STATUS = 0x3F

BOOT_DEAD_BATTERY = 1 << 2
BOOT_EEPROM_PRESENT = 1 << 3

MAX_LEN = 64                    # DATA1 holds 64 bytes
TASK_TIMEOUT = 1
TASK_REJECTED = 3
PBMS_ERRORS = {4: 'invalid bundle size', 5: 'invalid temporary address', 6: 'invalid timeout'}
BUNDLE_TIMEOUT = 0x32           # PBMs timeout in 100 ms steps (5 s, as in Linux)
PATCH_ADDR = 0x30               # temporary target address for the burst (not 0, not 0x20-0x23)

REGION_PTR = (0x0000, 0x0400)       # 32-bit little-endian pointer per region; 0 = region unused
REGION_BUNDLE = (0x0800, 0x4400)    # where each region's bundle starts
EEPROM_SIZE = 0x10000               # M24512
FLWD_LEN = 64
FLRD_LEN = 16

MODE_NAMES = {'APP ': 'running its configuration', 'PTCH': 'waiting for a patch (EEPROM blank or invalid)',
              'BOOT': 'booting (dead-battery condition)', 'BIST': 'self test', 'DISC': 'disconnected'}


class TPSError(IOError):
    pass


class TPS25751:
    def __init__(self, bus, addr=board.TPS25751_ADDR, log=None):
        self.bus = bus
        self.addr = addr
        self.log = log or (lambda msg: None)

    # ---- registers: [register][byte count][data], reads return the byte count first
    def read(self, reg, n):
        data = self.bus.write_read(self.addr, [reg], n + 1)
        if data[0] < n:
            raise TPSError(f'register 0x{reg:02x} returned {data[0]} bytes, expected {n}')
        return bytes(data[1:n + 1])

    def write(self, reg, data):
        data = bytes(data)
        if len(data) > MAX_LEN:
            raise ValueError('at most 64 data bytes per register write')
        self.bus.write(self.addr, bytes([reg, len(data)]) + data)

    def mode(self):
        return self.read(REG_MODE, 4).decode('ascii', 'replace')

    def boot_status(self):
        return int.from_bytes(self.read(REG_BOOT_STATUS, 5), 'little')

    def status(self):
        """STATUS (0x1A), POWER_STATUS (0x3F) and friends, decoded the way Linux's tipd driver does."""
        out = {'mode': self.mode(), 'boot_status': self.boot_status()}
        out['eeprom_present'] = bool(out['boot_status'] & BOOT_EEPROM_PRESENT)
        out['dead_battery'] = bool(out['boot_status'] & BOOT_DEAD_BATTERY)
        if out['mode'] == 'APP ':
            st = int.from_bytes(self.read(REG_STATUS, 4), 'little')
            ps = int.from_bytes(self.read(REG_POWER_STATUS, 2), 'little')
            out['status'] = st
            out['plug_present'] = bool(st & 1)
            out['vbus'] = ('vSafe0V', 'vSafe5V', 'PD contract', 'fault')[(st >> 20) & 3]
            out['power_source'] = ('unknown', 'VIN_3V3', 'dead battery (VBUS)', 'VBUS')[(st >> 18) & 3]
            out['power_status'] = ps
            out['connected'] = bool(ps & 1)
            out['sink'] = bool(ps & 2)
            out['typec_current'] = ('USB default', '1.5 A', '3.0 A', 'PD')[(ps >> 2) & 3]
        return out

    # ---- 4CC tasks
    def command(self, cmd, data_in=b'', out_len=0, timeout=1.0, result_delay=0.0):
        """Run a 4CC task: DATA1 <- input, CMD1 <- cmd, wait for CMD1 = 0, read DATA1."""
        with BusLock('tps25751'):
            busy = self.read(REG_CMD1, 4)
            if busy not in (b'\0\0\0\0', b'!CMD'):
                raise TPSError(f'controller still busy with {busy!r}')
            if data_in:
                self.write(REG_DATA1, data_in)
            self.write(REG_CMD1, cmd.encode('ascii'))
            deadline = time.monotonic() + timeout
            while True:
                cur = self.read(REG_CMD1, 4)
                if cur == b'!CMD':
                    raise TPSError(f'{cmd} is not accepted in mode {self.mode()!r}')
                if cur == b'\0\0\0\0':
                    break
                if time.monotonic() > deadline:
                    raise TPSError(f'{cmd} did not finish within {timeout} s')
                time.sleep(0.001)
            if result_delay:
                time.sleep(result_delay)
            return self.read(REG_DATA1, out_len) if out_len else b''

    def task(self, cmd, data_in=b'', out_len=1, **kw):
        """A task whose first output byte is a return code (0 = success)."""
        out = self.command(cmd, data_in, max(out_len, 1), **kw)
        if out[0] == TASK_TIMEOUT:
            raise TPSError(f'{cmd}: task timed out')
        if out[0] == TASK_REJECTED:
            raise TPSError(f'{cmd}: task rejected')
        if out[0]:
            raise TPSError(f'{cmd}: task return code {out[0]}')
        return out

    def wait_mode(self, wanted, timeout):
        deadline = time.monotonic() + timeout
        last = None
        while True:
            try:
                last = self.mode()
                if last in wanted:
                    return last
            except (I2CError, TPSError):
                last = None             # restarting: no answer for a moment
            if time.monotonic() > deadline:
                raise TPSError(f'controller mode {last!r}, expected {" or ".join(repr(w) for w in wanted)}')
            time.sleep(0.02)

    def restart(self, timeout=5.0):
        """GAID: cold restart from the EEPROM. Returns the mode it comes back in ('APP ' or 'PTCH').

        The sink path drops during the restart: on USB power alone (no battery) the car goes off.
        """
        with BusLock('tps25751'):
            self.write(REG_CMD1, b'GAID')
        time.sleep(0.5)
        return self.wait_mode(('APP ', 'PTCH'), timeout)

    # ---- patch burst mode (RAM only)
    def load_patch(self, bundle, temp_addr=PATCH_ADDR, chunk=64):
        """Load a Low Region binary into RAM (PTCH mode only). The controller then runs it."""
        bundle = bytes(bundle)
        if temp_addr == 0 or 0x20 <= temp_addr <= 0x23 or temp_addr > 0x77:
            raise ValueError(f'0x{temp_addr:02x} cannot be the patch address')
        with BusLock('tps25751'):
            mode = self.mode()
            if mode != 'PTCH':
                raise TPSError(f'controller is in mode {mode!r}; patches only load in PTCH mode')
            boot = self.boot_status()
            out = self.command('PBMs', struct.pack('<IBB', len(bundle), temp_addr, BUNDLE_TIMEOUT), 1,
                               timeout=4.0, result_delay=0.0005)
            if out[0]:
                raise TPSError('PBMs: ' + PBMS_ERRORS.get(out[0], f'task return code {out[0]}'))
            try:
                for off in range(0, len(bundle), chunk):
                    self.bus.write(temp_addr, bundle[off:off + chunk])
                    time.sleep(0.0005)
                # PBMc fails without some input (Linux comment), so it gets two zero bytes
                out = self.command('PBMc', b'\0\0', 40, timeout=2.0, result_delay=0.02)
                if out[0]:
                    raise TPSError(f'PBMc: task return code {out[0]}')
                if out[2]:
                    raise TPSError(f'PBMc: device patch complete status {out[2]}')
            except Exception:
                try:
                    self.command('PBMe', b'', 1)
                except Exception:
                    pass
                raise
            self.wait_mode(('APP ',), 1.0)
            if boot & BOOT_DEAD_BATTERY:
                self.task('DBfg')
        self.log(f'patch loaded ({len(bundle)} bytes), controller in APP mode')
        return 'APP '

    # ---- EEPROM through the controller (APP mode)
    def _require_app(self):
        mode = self.mode()
        if mode != 'APP ':
            raise TPSError(f'controller is in mode {mode!r}; the EEPROM commands need APP mode '
                           '(load a Low Region binary with load_patch first)')

    def flash_read(self, addr, n):
        out = bytearray()
        with BusLock('tps25751'):
            while len(out) < n:
                out += self.command('FLrd', struct.pack('<I', addr + len(out)), FLRD_LEN)
        return bytes(out[:n])

    def flash_write(self, addr, data, progress=None):
        """FLad once, then FLwd in 64-byte pieces (the address increments by itself)."""
        if addr % FLWD_LEN:
            raise ValueError('write start must be 64-byte aligned (M24512 pages are 128 bytes)')
        with BusLock('tps25751'):
            self.task('FLad', struct.pack('<I', addr))
            for off in range(0, len(data), FLWD_LEN):
                self.task('FLwd', data[off:off + FLWD_LEN])
                time.sleep(75e-6)
                if progress:
                    progress(min(off + FLWD_LEN, len(data)), len(data))

    def region_pointer(self, region):
        return struct.unpack('<I', self.flash_read(REGION_PTR[region], 4))[0]

    def write_region_pointer(self, region, value):
        with BusLock('tps25751'):
            self.task('FLad', struct.pack('<I', REGION_PTR[region]))
            self.task('FLwd', struct.pack('<I', value))
            time.sleep(75e-6)
            got = self.region_pointer(region)
        if got != value:
            raise TPSError(f'region {region} pointer reads 0x{got:x} after writing 0x{value:x}')

    def verify_region(self, region):
        self.task('FLvy', struct.pack('<I', REGION_BUNDLE[region]))

    def _compare(self, addr, data):
        got = self.flash_read(addr, len(data))
        if got != data:
            i = next(i for i in range(len(data)) if got[i] != data[i])
            raise TPSError(f'EEPROM verify failed at 0x{addr + i:04x}: 0x{got[i]:02x} != 0x{data[i]:02x}')

    def eeprom_write_full(self, image, verify=True, progress=None):
        """First programming of a board: TI's Full Flash binary, from address 0.

        Both region pointers are cleared first and written last, so a cut part-way leaves an EEPROM
        the controller ignores (it then waits in PTCH mode and the Jetson can load a patch again).
        """
        image = bytes(image)
        ptrs = check_full_image(image)
        with BusLock('tps25751'):
            self._require_app()
            for r in (0, 1):
                self.write_region_pointer(r, 0)
            body = bytearray(image)
            for r in (0, 1):
                body[REGION_PTR[r]:REGION_PTR[r] + 4] = b'\0\0\0\0'
            self.flash_write(0, bytes(body), progress)
            if verify:
                self._compare(0, bytes(body))
            for r in (0, 1):
                if ptrs[r]:
                    self.verify_region(r)
            for r in (0, 1):
                if ptrs[r]:
                    self.write_region_pointer(r, ptrs[r])
        self.log('Full Flash image written')

    def eeprom_update(self, lowregion, verify=True, progress=None):
        """TI's A/B update with a Low Region binary: new region first, pointers last."""
        lowregion = bytes(lowregion)
        with BusLock('tps25751'):
            self._require_app()
            ptr = [self.region_pointer(r) for r in (0, 1)]
            active = [r for r in (0, 1) if ptr[r] == REGION_BUNDLE[r]]
            if not active:
                raise TPSError(f'no active region (pointers 0x{ptr[0]:x}, 0x{ptr[1]:x}): program the '
                               'Full Flash binary once first (eeprom_write_full)')
            old = active[0]
            new = 1 - old
            limit = (REGION_BUNDLE[1] if new == 0 else EEPROM_SIZE) - REGION_BUNDLE[new]
            if len(lowregion) > limit:
                raise TPSError(f'Low Region binary is {len(lowregion)} bytes; region {new} holds {limit}')
            self.log(f'active region {old}, writing region {new}')
            self.write_region_pointer(new, 0)
            self.flash_write(REGION_BUNDLE[new], lowregion, progress)
            if verify:
                self._compare(REGION_BUNDLE[new], lowregion)
            self.verify_region(new)
            self.write_region_pointer(new, REGION_BUNDLE[new])
            self.write_region_pointer(old, 0)
        self.log(f'region {new} active')
        return new


def check_full_image(image):
    """Sanity checks on a Full Flash binary before anything is written. Returns the two pointers."""
    if not REGION_BUNDLE[0] < len(image) <= EEPROM_SIZE:
        raise TPSError(f'{len(image)} bytes is not a Full Flash binary for a 64 KB EEPROM')
    ptrs = [struct.unpack('<I', image[p:p + 4])[0] for p in REGION_PTR]
    for r in (0, 1):
        if ptrs[r] not in (0, REGION_BUNDLE[r]):
            raise TPSError(f'region {r} pointer in the image is 0x{ptrs[r]:x} (expected 0 or '
                           f'0x{REGION_BUNDLE[r]:x}): is this the Full Flash binary?')
    if not any(ptrs):
        raise TPSError('the image points at neither region')
    if ptrs[1] and len(image) <= REGION_BUNDLE[1]:
        raise TPSError('the image points at region 1 but ends before it')
    return ptrs


def lowregion_matches(image, lowregion):
    """True if the Low Region binary sits byte for byte in the region the Full Flash image uses.

    Expected from SLVAFL1's layout when both files come from one run of TI's tool; a mismatch
    usually means files from different runs.
    """
    ptrs = check_full_image(image)
    start = REGION_BUNDLE[0] if ptrs[0] else REGION_BUNDLE[1]
    return image[start:start + len(lowregion)] == bytes(lowregion)
