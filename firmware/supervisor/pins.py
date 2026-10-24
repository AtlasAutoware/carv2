"""Raspberry Pi Pico GPIO map of the ATLAS-PWR-1 power board (rev B).

This is the only place in the firmware that knows GP numbers. It copies the table in
boards/power/PINMAP.md, which is the single source of truth for the hardware: if the board
changes, change PINMAP.md first, then this file. tests/test_pins.py compares this file with
PINMAP.md and with the Pico's net list in boards/power/design.py whenever they exist.

Two pins differ from the first map of Oct 24 (PINMAP.md, "Changes from the PHASE2 map"): GP15 is
CHG_PRESENT_N (an open-collector transistor, low = charger present) instead of an active-high
divider, and GP22 is DEVKIT_PWR, an output that can switch the dev kit's DC feed off to
power-cycle a hung Jetson, instead of the spare VM_OK input. A 10 k pull-up holds GP22 at about
2.7 V, so the dev kit stays on while the Pico is in reset.

Directions are from the Pico's side. "Safe" levels are what the pins take at start-up and after
any fault: main switch and precharge off, VESC killed, lidar off, no key presses.
"""

# ---------------------------------------------------------------- GP numbers
BMS_TX = 0                  # UART0 TX to the JBD BMS through a PC817 (BMS side powered from its port)
BMS_RX = 1                  # UART0 RX from the JBD BMS through a PC817
PRECHARGE_EN = 2            # 2N3904 -> IRF9Z34N precharge P-FET (10 ohm 5 W into the motor bus)
MAIN_EN = 3                 # 74HC08 input; AND with ESTOP_OK -> MIC5014 IN (main switch)
I2C0_SDA = 4                # J12 pin 3 (Jetson I2C bus 7), spare link, no pull-ups on the board
I2C0_SCL = 5                # J12 pin 5
LIDAR_EN = 6                # 2N3904 -> lidar P-FET; 100 k base pull-down (off when the Pico is dead)
JETSON_PWR_KEY = 7          # PC817 across J14 pins 12/11 (SLEEP/WAKE*); 150-200 ms pulse
JETSON_RESET = 8            # PC817 across J14 pins 8/7 (SYS_RESET*); 100 ms pulse
LATCH_OFF = 9               # Pololu #2813 OFF input (a high pulse turns the car off)
ESTOP_OK = 10               # loop sense: 3.3 V -> loop -> node -> 10 k to GND; closed = high
JETSON_UP = 11              # J12 pin 31 (Jetson output) through 100 k pull-down
JETSON_3V3_SENSE = 12       # J12 pin 17 (VDD_3V3_SYS) through 10 k series, 100 k to GND
BUTTON_N = 13               # power button, active low (pull-up)
VESC_KILL = 14              # FSESC ADC2 through 1 k; 3.3 V = run, 0 V = kill; 100 k pull-down
CHG_PRESENT_N = 15          # Q503 open collector, 10 k pull-up: low = USB-C charger delivering 20 V
FAN_PWM = 16                # fan PWM through a 2N7000, 25 kHz
LED_STATUS = 17             # on-board LED (green)
LED_FAULT = 18              # on-board LED (red)
ESTOP_OK_TO_JETSON = 19     # J12 pin 33 (Jetson input) through 10 k
CHG_STAT_N_TO_JETSON = 20   # J12 pin 32 (Jetson input) through 10 k; low = charging
LIDAR_REQ = 21              # J12 pin 29 (Jetson output) through 100 k pull-down
DEVKIT_PWR = 22             # 4.7 k into a 2N3904 that holds the dev-kit feed P-FET on; high = powered (10 k pull-up)
VM_SENSE = 26               # ADC0: motor bus, 100 k / 18 k divider
BAT_SENSE = 27              # ADC1: pack bus (taken from VSYS_SW), 100 k / 18 k divider
FET_NTC = 28                # ADC2: 10 k NTC (Vishay NTCLE100E3103JB0) on the main-switch heatsink, 10 k to 3.3 V

# ---------------------------------------------------------------- how the firmware uses them
# (name, GP, safe level). hal.Hardware sets the level before it makes the pin an output.
OUTPUTS = (
    ('PRECHARGE_EN', PRECHARGE_EN, 0),
    ('MAIN_EN', MAIN_EN, 0),
    ('LIDAR_EN', LIDAR_EN, 0),
    ('JETSON_PWR_KEY', JETSON_PWR_KEY, 0),
    ('JETSON_RESET', JETSON_RESET, 0),
    ('LATCH_OFF', LATCH_OFF, 0),
    ('VESC_KILL', VESC_KILL, 0),            # 0 = kill: the motor stays off until RUN
    ('LED_STATUS', LED_STATUS, 0),
    ('LED_FAULT', LED_FAULT, 0),
    ('ESTOP_OK_TO_JETSON', ESTOP_OK_TO_JETSON, 0),
    ('CHG_STAT_N_TO_JETSON', CHG_STAT_N_TO_JETSON, 0),
    ('DEVKIT_PWR', DEVKIT_PWR, 1),          # 1 = dev kit powered: never cut the Jetson by accident
)

# (name, GP, pull): pull is None (the board has its own resistor), 'up' or 'down'
INPUTS = (
    ('ESTOP_OK', ESTOP_OK, None),           # 10 k pull-down on the board
    ('JETSON_UP', JETSON_UP, None),         # 100 k pull-down on the board
    ('JETSON_3V3_SENSE', JETSON_3V3_SENSE, None),
    ('BUTTON_N', BUTTON_N, 'up'),
    ('CHG_PRESENT_N', CHG_PRESENT_N, None), # 10 k pull-up on the board
    ('LIDAR_REQ', LIDAR_REQ, None),         # 100 k pull-down on the board
)

# The Jetson's I2C bus 7 is wired to these pins as a spare. They stay high-impedance inputs so
# the Pico never loads or drives that bus.
HIGH_Z = (I2C0_SDA, I2C0_SCL)

ADCS = (
    ('VM_SENSE', VM_SENSE),
    ('BAT_SENSE', BAT_SENSE),
    ('FET_NTC', FET_NTC),
)

# ---------------------------------------------------------------- analog front end
# From boards/power/design.py (Oct 24 draft); check again when the board is final.
ADC_VREF = 3.3              # Pico ADC reference (the Pico's 3.3 V through its RC filter)
VM_DIVIDER = 118.0 / 18.0   # bus volts per ADC volt: 100 k over 18 k (16.8 V -> 2.56 V at the pin)
BAT_DIVIDER = 118.0 / 18.0  # same divider on VSYS_SW
NTC_PULLUP_OHM = 10000.0    # 10 k from 3.3 V to the NTC node, NTC to ground
NTC_R25_OHM = 10000.0
NTC_BETA = 3977.0           # NTCLE100E3103JB0: B25/85 = 3977 K (Vishay datasheet value as listed in design.py)

# ---------------------------------------------------------------- BMS UART and fan
BMS_UART_ID = 0
BMS_BAUD = 9600             # JBD default (JBD General Protocol V4, "Physical interface")
# design.py wires both PC817s non-inverting (Pico TX low -> LED on -> BMS RX low, and back).
# If a board inverts, set these: the RP2040 UART can invert in hardware, no board change needed.
BMS_INVERT_TX = False
BMS_INVERT_RX = False

FAN_PWM_HZ = 25000
# design.py: the 2N7000 pulls the fan's PWM wire low while the Pico pin is high, so a high pin
# means a slower fan, and a dead or reset Pico leaves the fan at full speed.
FAN_PWM_INVERT = True
