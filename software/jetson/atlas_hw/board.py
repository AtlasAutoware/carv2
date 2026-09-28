"""Where the drive board and brain board parts sit, as the Jetson sees them.

Sources: boards/stack/stack.py (stack pin map), boards/brain/out/atlas_brain.net (module pins), the
Linux device trees for the Orin Nano (tegra234.dtsi aliases: i2c1 = gen2 at 0xc240000, i2c7 = gen8
at 0xc250000) and the Orin Nano 40-pin header tables (module I2C0 on pins 185/187 is /dev/i2c-1,
module I2C1 on pins 189/191 is /dev/i2c-7, module UART1 on pins 203/205 is serial@3100000).

Bus numbers are looked up by controller address at run time, so a different numbering in a
later JetPack does not break anything. ATLAS_I2C_STACK, ATLAS_I2C_SYS and ATLAS_VESC_TTY override.
"""
import glob
import os

# Module I2C1 (pins 189/191) -> stack pins 19/20 -> drive board
STACK_I2C_CONTROLLER = 'c250000.i2c'
STACK_I2C_DEFAULT = 7
INA228_ADDR = 0x40          # drive board, BMS shunt 0.5 mOhm, pack voltage on B+
ID_EEPROM_ADDR = 0x50       # drive board 24AA02, WP tied low (it answers on all of 0x50-0x57)
TPS25751_ADDR = 0x20        # drive board PD controller target port (ADCIN1 = LDO_3V3, ADCIN2 = GND: index #1)
TPS23861_ADDR = 0x28        # brain board PoE PSE (A3 open); every TPS23861 also answers 0x30 (broadcast)

# Module I2C0 (pins 185/187) -> brain board "SYS I2C": the expander (and the module's own INA3221 at 0x40)
SYS_I2C_CONTROLLER = 'c240000.i2c'
SYS_I2C_DEFAULT = 1
EXPANDER_ADDR = 0x20        # PCAL6408A U34, ADDR strapped to GND

# Module UART1 (pins 203/205) -> NTS0102 -> stack pins 15/16 -> STM32 USART3 (VESC, 115200)
VESC_UART_CONTROLLER = '3100000.serial'

# Expander lines (fork_config.py RENAME_GLOBAL, peripherals sheet)
EXP_MCU_RST_REQ = 0     # out: 1 = hold the STM32 in reset (Q1003 pulls NRST low)
EXP_MCU_BOOT0 = 1       # out: 1 = STM32 starts its ROM bootloader at the next reset
EXP_LIDAR_EN = 2        # out: 1 = lidar eFuse (TPS26600) on
EXP_ESTOP_OK = 3        # in:  1 = E-stop loop closed
EXP_CHG_STAT_N = 4      # in:  0 = charging (BQ25798 STAT through 10k)
EXP_SPARE1 = 5          # stack pin 31, test pad on the drive board
EXP_SPARE2 = 6          # stack pin 32
EXP_PSE_INT_N = 7       # in:  0 = PoE controller interrupt
EXP_OUTPUTS = (1 << EXP_MCU_RST_REQ) | (1 << EXP_MCU_BOOT0) | (1 << EXP_LIDAR_EN)

# Battery pack: 4S3P Molicel P28A
PACK_CELLS_SERIES = 4
PACK_CAPACITY_AH = 8.4
BMS_SHUNT_OHM = 0.0005


def _find_i2c_bus(controller, env, default):
    if os.environ.get(env):
        return int(os.environ[env])
    for path in glob.glob('/sys/bus/i2c/devices/i2c-*'):
        real = os.path.realpath(path)
        if f'/{controller}/' in real + '/':
            try:
                return int(os.path.basename(path).split('-')[1])
            except ValueError:
                pass
    return default


def stack_i2c_bus():
    """Linux bus number of the stack I2C (INA228, ID EEPROM, TPS25751, TPS23861)."""
    return _find_i2c_bus(STACK_I2C_CONTROLLER, 'ATLAS_I2C_STACK', STACK_I2C_DEFAULT)


def sys_i2c_bus():
    """Linux bus number of the brain board SYS I2C (PCAL6408A expander)."""
    return _find_i2c_bus(SYS_I2C_CONTROLLER, 'ATLAS_I2C_SYS', SYS_I2C_DEFAULT)


def vesc_tty():
    """The tty that reaches the STM32 (VESC firmware), e.g. /dev/ttyTHS0."""
    if os.environ.get('ATLAS_VESC_TTY'):
        return os.environ['ATLAS_VESC_TTY']
    if os.path.exists('/dev/atlas_vesc'):
        return '/dev/atlas_vesc'
    for path in sorted(glob.glob('/sys/class/tty/ttyTHS*')):
        if VESC_UART_CONTROLLER in os.path.realpath(os.path.join(path, 'device')):
            return '/dev/' + os.path.basename(path)
    return '/dev/ttyTHS0'
