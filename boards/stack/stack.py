"""The drive-board-to-brain-board connector, defined once for both boards.

Both board generators import this file, so the pin map, the net names and the pin positions
cannot drift apart. tools/check_stack.py reads the netlists and footprints of both finished
boards and checks them against this table.

Coordinates are board-local, top view, in mm: X runs forward from each board's rear edge,
Y runs toward the car's left side from each board's right edge. The brain board sits 20 mm
further forward, so brain X = drive X - 20 and brain Y = drive Y.
"""

PITCH = 2.54
COLS = 20                      # 2 x 20, pin 1 at the rear end
CENTER_DRIVE = (85.5, 62.5)    # header centre on the drive board (from the placement plan)
BRAIN_DX = -20.0               # brain-local X = drive-local X + BRAIN_DX
STACK_GAP = 20.0               # drive-board top to brain-board bottom (mech/kit.py STACK_H): 20 mm M3 standoffs;
                               # the brain NVMe then clears the drive's 12.8 mm bulk caps by about 2 mm

# pin: (net, kind, direction, note). kind: pwr / gnd / sig. Direction is seen from the drive board.
PINS = {
    1: ('VSYS', 'pwr', 'out', 'charger SYS rail, 12-16.8 V; 6 pins x 3 A'),
    2: ('VSYS', 'pwr', 'out', ''),
    3: ('VSYS', 'pwr', 'out', ''),
    4: ('VSYS', 'pwr', 'out', ''),
    5: ('VSYS', 'pwr', 'out', ''),
    6: ('VSYS', 'pwr', 'out', ''),
    7: ('GND', 'gnd', '', ''),
    8: ('GND', 'gnd', '', ''),
    9: ('GND', 'gnd', '', ''),
    10: ('GND', 'gnd', '', ''),
    11: ('STK_USB0_DP', 'sig', 'bidi', 'Jetson USB0 D+ (hub port 1, or straight to USB-C when flashing)'),
    12: ('STK_USB0_DN', 'sig', 'bidi', 'Jetson USB0 D-'),
    13: ('GND', 'gnd', '', ''),
    14: ('GND', 'gnd', '', ''),
    15: ('STK_VESC_J2M', 'sig', 'in', 'Jetson UART1 TX -> STM32 USART3 RX (PB11), 3.3 V'),
    16: ('STK_VESC_M2J', 'sig', 'out', 'STM32 USART3 TX (PB10) -> Jetson UART1 RX, 3.3 V'),
    17: ('STK_CON_J2M', 'sig', 'in', 'Jetson debug UART TX -> CP2102N RXD, 3.3 V'),
    18: ('STK_CON_M2J', 'sig', 'out', 'CP2102N TXD -> Jetson debug UART RX, 3.3 V'),
    19: ('STK_I2C_SCL', 'sig', 'bidi', 'Jetson I2C1 (3.3 V, pulled up on the module): INA228 0x40, ID EEPROM 0x50, TPS25751 target'),
    20: ('STK_I2C_SDA', 'sig', 'bidi', ''),
    21: ('STK_PWR_BTN_N', 'sig', 'out', 'low while the power button asks the Jetson to shut down (module SLEEP/WAKE*)'),
    22: ('STK_OS_HALTED', 'sig', 'in', 'high when the Jetson module is off; pulled up on the drive board'),
    23: ('STK_POWER_EN', 'sig', 'out', 'high = brain board input eFuse on; pulled down on the brain board'),
    24: ('STK_MCU_NRST', 'sig', 'in', 'open drain from the brain board (FET on expander P0): resets the STM32'),
    25: ('STK_MCU_BOOT0', 'sig', 'in', 'expander P1 drives high to start the STM32 bootloader'),
    26: ('STK_ESTOP_OK', 'sig', 'out', 'high while the E-stop loop is closed (expander P3 input)'),
    27: ('STK_CHG_STAT', 'sig', 'out', 'BQ25798 STAT, open drain via 10k, low while charging (expander P4 input)'),
    28: ('STK_LIDAR_EN', 'sig', 'in', 'high = lidar eFuse on (expander P2); pulled down on the drive board'),
    29: ('GND', 'gnd', '', ''),
    30: ('GND', 'gnd', '', ''),
    31: ('STK_SPARE1', 'sig', 'bidi', 'brain board I/O expander pin (PCAL6408A P5, 3.3 V); test pad on the drive board'),
    32: ('STK_SPARE2', 'sig', 'bidi', 'expander P6'),
    33: ('STK_CAN_TX', 'sig', 'in', 'Jetson CAN TX (3.3 V); test pad on the drive board'),
    34: ('STK_CAN_RX', 'sig', 'out', 'Jetson CAN RX (3.3 V)'),
    35: ('3V3_DRV', 'pwr', 'out', 'drive board 3.3 V: reference rail for the brain board level shifters'),
    36: ('GND', 'gnd', '', ''),
    37: ('GND', 'gnd', '', ''),
    38: ('GND', 'gnd', '', ''),
    39: ('GND', 'gnd', '', ''),
    40: ('GND', 'gnd', '', ''),
}

# per-board net name for each stack net (the brain board keeps Antmicro's own names apart)
DRIVE_NET = {n: n for n in set(v[0] for v in PINS.values())}
DRIVE_NET['3V3_DRV'] = '+3V3'
DRIVE_NET['STK_ESTOP_OK'] = 'ESTOP_OK'
BRAIN_NET = {n: n for n in set(v[0] for v in PINS.values())}
BRAIN_NET['VSYS'] = 'STK_VSYS'
BRAIN_NET['3V3_DRV'] = 'STK_3V3_DRV'
BRAIN_NET['STK_USB0_DP'] = 'USB0_D_P'         # straight to the module pins (Antmicro net names)
BRAIN_NET['STK_USB0_DN'] = 'USB0_D_N'
BRAIN_NET['STK_CON_J2M'] = 'DEBUG_TXD'        # 3.3 V side of Antmicro's debug UART translator U4
BRAIN_NET['STK_CON_M2J'] = 'DEBUG_RXD'
BRAIN_NET['STK_I2C_SCL'] = 'I2C1_SCL'
BRAIN_NET['STK_I2C_SDA'] = 'I2C1_SDA'


def pin_xy_drive(n):
    """Drive-board-local (X, Y) of pin n. Odd pins on the car-left row."""
    c = (n - 1) // 2
    x = CENTER_DRIVE[0] + (c - (COLS - 1) / 2) * PITCH
    y = CENTER_DRIVE[1] + (PITCH / 2 if n % 2 else -PITCH / 2)
    return (round(x, 4), round(y, 4))


def pin_xy_brain(n):
    x, y = pin_xy_drive(n)
    return (round(x + BRAIN_DX, 4), y)


def drive_nets():
    return {n: DRIVE_NET[v[0]] for n, v in PINS.items()}


def brain_nets():
    return {n: BRAIN_NET[v[0]] for n, v in PINS.items()}


if __name__ == '__main__':
    for n in sorted(PINS):
        print(n, PINS[n][0], pin_xy_drive(n), pin_xy_brain(n))
