"""Rev B: what the Jetson is wired to, on the NVIDIA dev-kit carrier and the ATLAS-PWR-1 power board.

Sources: the rev B decisions of Oct 24, 2026; NVIDIA's Jetson Orin Nano developer kit carrier
board specification, Table 3-3 (J12, 40-pin header) and Table 3-4 (J14, button header);
MicroPython's rp2 port for the Pico's USB IDs (ports/rp2/mpconfigport.h: VID 0x2E8A Raspberry
Pi, PID 0x0005 "RP2 MicroPython").

  J12 pins 8/10   UART1 (serial@3100000, /dev/ttyTHS1 on JetPack 6) -> FSESC UART: /dev/atlas_vesc
  Pico micro-USB  -> a dev-kit USB-A port: USB CDC /dev/ttyACM*, udev name /dev/atlas_supervisor
  J12 pins 3/5    I2C bus 7 (c250000.i2c) -> the Pico's spare I2C pins; no chips on it
  J12 pin 31      JETSON_UP   (out): high while the Atlas software runs
  J12 pin 29      LIDAR_REQ   (out): lidar power request, edges (the Pico owns the switch)
  J12 pin 33      ESTOP_OK    (in):  high = E-stop loop closed (driven by the Pico through 10 k)
  J12 pin 32      CHG_STAT_N  (in):  low = charger connected
  J14 pins 12/11  power key (KEY_POWER), pressed by the Pico through an optocoupler

The rev A constants (expander, INA228, TPS25751, ID EEPROM) are in atlas_hw.reva.board.
"""
import glob
import os

# ---------------------------------------------------------------- serial links
SUPERVISOR_LINK = '/dev/atlas_supervisor'
SUPERVISOR_USB_VID = '2e8a'         # Raspberry Pi
SUPERVISOR_USB_PID = '0005'         # MicroPython on an RP2040/RP2350
SUPERVISOR_BAUD = 115200            # ignored by USB CDC; set so a terminal looks normal

VESC_LINK = '/dev/atlas_vesc'
VESC_UART_CONTROLLER = '3100000.serial'     # UART1, J12 pins 8 (TX) / 10 (RX)
VESC_BAUD = 115200

# ---------------------------------------------------------------- I2C (spare)
POWER_I2C_CONTROLLER = 'c250000.i2c'        # J12 pins 3/5, normally /dev/i2c-7
POWER_I2C_DEFAULT = 7

# ---------------------------------------------------------------- J12 GPIO lines
# (chip, line offset, line name). The line names are what the tegra234 GPIO driver reports
# (`gpioinfo`); gpio.py looks a line up by name first and falls back to the offset. The offsets
# are the commonly published ones for the Orin Nano dev kit on JetPack 6: CHECK WITH `gpioinfo`
# on the car. ATLAS_GPIO_<NAME>=gpiochip0:106 (or =PQ.06) in /etc/atlas/atlas.conf overrides.
GPIO_JETSON_UP = ('gpiochip0', 106, 'PQ.06')    # J12 pin 31, GPIO11
GPIO_LIDAR_REQ = ('gpiochip0', 105, 'PQ.05')    # J12 pin 29, GPIO01
GPIO_ESTOP_OK = ('gpiochip0', 43, 'PH.00')      # J12 pin 33, GPIO13
GPIO_CHG_STAT_N = ('gpiochip0', 41, 'PG.06')    # J12 pin 32, GPIO07

GPIO_OUTPUTS = ('JETSON_UP', 'LIDAR_REQ')
GPIO_INPUTS = ('ESTOP_OK', 'CHG_STAT_N')

# ---------------------------------------------------------------- battery pack (4S3P Molicel P28A)
PACK_CELLS_SERIES = 4
PACK_CAPACITY_AH = 8.4


def _tty_by_controller(pattern, controller):
    for path in sorted(glob.glob(pattern)):
        if controller in os.path.realpath(os.path.join(path, 'device')):
            return '/dev/' + os.path.basename(path)
    return None


def _tty_by_usb_id(vid, pid):
    for path in sorted(glob.glob('/sys/class/tty/ttyACM*')):
        dev = os.path.realpath(os.path.join(path, 'device'))
        for up in (dev, os.path.dirname(dev)):
            try:
                with open(os.path.join(up, 'idVendor')) as f:
                    v = f.read().strip()
                with open(os.path.join(up, 'idProduct')) as f:
                    p = f.read().strip()
            except OSError:
                continue
            if v == vid and p == pid:
                return '/dev/' + os.path.basename(path)
    return None


def supervisor_tty():
    """The Pico's USB CDC port: $ATLAS_SUPERVISOR_TTY, the udev name, or found by USB ID."""
    if os.environ.get('ATLAS_SUPERVISOR_TTY'):
        return os.environ['ATLAS_SUPERVISOR_TTY']
    if os.path.exists(SUPERVISOR_LINK):
        return SUPERVISOR_LINK
    return _tty_by_usb_id(SUPERVISOR_USB_VID, SUPERVISOR_USB_PID) or SUPERVISOR_LINK


def vesc_tty():
    """The UART to the FSESC: $ATLAS_VESC_TTY, the udev name, or the ttyTHS* on serial@3100000."""
    if os.environ.get('ATLAS_VESC_TTY'):
        return os.environ['ATLAS_VESC_TTY']
    if os.path.exists(VESC_LINK):
        return VESC_LINK
    return _tty_by_controller('/sys/class/tty/ttyTHS*', VESC_UART_CONTROLLER) or '/dev/ttyTHS1'


def power_i2c_bus():
    """Linux bus number of J12's I2C (pins 3/5), found by controller address."""
    if os.environ.get('ATLAS_I2C_POWER'):
        return int(os.environ['ATLAS_I2C_POWER'])
    for path in glob.glob('/sys/bus/i2c/devices/i2c-*'):
        if f'/{POWER_I2C_CONTROLLER}/' in os.path.realpath(path) + '/':
            try:
                return int(os.path.basename(path).split('-')[1])
            except ValueError:
                pass
    return POWER_I2C_DEFAULT
