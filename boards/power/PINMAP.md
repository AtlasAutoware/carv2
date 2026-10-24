# ATLAS-PWR-1 rev B: Pico GPIO map

This table is the single source of truth for the supervisor's pins. `boards/power/design.py` wires the Pico from
it and `firmware/supervisor/pins.py` copies it (its `tests/test_pins.py` compares all three). Change this file
first, then the other two.

The Raspberry Pi Pico (RP2040) sits in two 1x20 female sockets, USB end at the pack edge (Y = 84). Pins 1 to 20
run down the left column from the USB end, 21 to 40 back up the right column. "dir" is from the Pico's side.

## Changes from the PHASE2 map of Oct 24

- GP15 is `CHG_PRESENT_N`, active low: an open-collector NPN (Q503) with a 10k pull-up to 3.3 V, low while the
  charge input carries more than about 17.5 V. PHASE2 had an active-high divider from the charge input, which
  back-powers an unpowered Pico when the charger is plugged in with the car off.
- GP22 is `DEVKIT_PWR`, an output: high (or floating) keeps the dev kit's DC feed on, low turns it off, so the
  Pico can power-cycle a hung Jetson. A 10k pull-up holds it at about 2.7 V while the Pico is in reset. PHASE2
  had a spare `VM_OK` input here.

## GPIO

| GP | Pico pin | dir | net | circuit on the board |
| --- | --- | --- | --- | --- |
| GP0 | 1 | out | BMS_TX | UART0 TX; sinks the LED of PC817 U202 through 470 Ohm from 3.3 V; U202 drives the JBD RX (BMS side) |
| GP1 | 2 | in | BMS_RX | UART0 RX; PC817 U201 collector, 4.7k pull-up to 3.3 V; idle high |
| GP2 | 4 | out | PRECHARGE_EN | 74HCT08 gate 2 with ESTOP_OK, then a 2N3904 that turns on the IRF9Z34N precharge P-FET; 100k pull-down |
| GP3 | 5 | out | MAIN_EN | 74HCT08 gate 1 with ESTOP_OK, then 1k into MIC5014 IN (main switch); 100k pull-down |
| GP4 | 6 | io | I2C0_SDA | J12 pin 3 (Jetson I2C bus 7) through 330 Ohm, fitted DNP; no pull-ups on the board |
| GP5 | 7 | io | I2C0_SCL | J12 pin 5 through 330 Ohm, fitted DNP |
| GP6 | 9 | out | LIDAR_EN | 4.7k into a 2N3904 that pulls the lidar P-FET gate; 100k base pull-down (lidar off while the Pico is dead) |
| GP7 | 10 | out | JETSON_PWR_KEY | 470 Ohm into the LED of PC817 U801, whose transistor shorts J14 pin 12 to pin 11; pulse 150-200 ms |
| GP8 | 11 | out | JETSON_RESET | 470 Ohm into PC817 U802, J14 pin 8 to pin 7; pulse 100 ms |
| GP9 | 12 | out | LATCH_OFF | 1k into the Pololu #2813 OFF input; 100k pull-down; a high pulse turns the car off |
| GP10 | 14 | in | ESTOP_OK | 3.3 V -> 1k -> E-stop loop -> 100 Ohm -> node with 10k + 100 nF to GND; closed = 3.0 V, open = 0 V. Same node feeds the 74HCT08 |
| GP11 | 15 | in | JETSON_UP | J12 pin 31 through 10k series; 100k pull-down on the J12 side |
| GP12 | 16 | in | JETSON_3V3_SENSE | J12 pin 17 (dev-kit 3.3 V) through 10k series, 100k to GND (reads 3.0 V when the Jetson is up) |
| GP13 | 17 | in | BUTTON_N | 2N3904 open collector, 10k pull-up; low while the board button or the remote button is held |
| GP14 | 19 | out | VESC_KILL | 1k into the FSESC ADC2 (COMM pin 6); 3.3 V = run, 0 V = kill; 100k pull-down |
| GP15 | 20 | in | CHG_PRESENT_N | 2N3904 open collector, 10k pull-up; low = USB-C charger delivering 20 V |
| GP16 | 21 | out | FAN_PWM | 100 Ohm into a 2N7000 that pulls the fan PWM line low; 100k gate pull-down (fan at full speed with the Pico off). 25 kHz |
| GP17 | 22 | out | LED_STATUS | green LED D701 through 470 Ohm |
| GP18 | 24 | out | LED_FAULT | red LED D702 through 470 Ohm |
| GP19 | 25 | out | ESTOP_OK_TO_JETSON | J12 pin 33 through 10k |
| GP20 | 26 | out | CHG_STAT_N_TO_JETSON | J12 pin 32 through 10k; low = charging |
| GP21 | 27 | in | LIDAR_REQ | J12 pin 29 through 10k series; 100k pull-down on the J12 side |
| GP22 | 29 | out | DEVKIT_PWR | 4.7k into a 2N3904 that holds the dev-kit feed P-FET on (through the over-voltage cut-off); 10k pull-up; low = dev kit off |
| GP26 | 31 | adc | VM_SENSE | ADC0: motor bus through 100k / 18k (x 0.1525) + 100 nF; 16.8 V reads 2.56 V |
| GP27 | 32 | adc | BAT_SENSE | ADC1: VSYS_SW (equals the pack while the latch is on) through 100k / 18k + 100 nF |
| GP28 | 34 | adc | FET_NTC | ADC2: 10k NTC (Vishay NTCLE100E3103JB0, B 3977 K) on the heatsink bar to GND, 10k to 3.3 V, 100 nF; 25 C reads 1.65 V, 90 C about 0.3 V |

## Power and other pins

| Name | Pico pin | Connection |
| --- | --- | --- |
| VSYS | 39 | +5 V (RECOM R-78E) through a 1N5817, plus 10 uF; the Pico's own VBUS diode lets its USB cable power it on the bench |
| 3V3(OUT) | 36 | the board +3V3 rail (pull-ups, E-stop loop source, NTC divider, opto LEDs): about 300 mA available |
| RUN | 30 | test pad TP702 (short to GND to reset the Pico) |
| VBUS | 40 | not connected |
| 3V3_EN | 37 | not connected (pulled up on the Pico) |
| ADC_VREF | 35 | not connected |
| AGND | 33 | GND |
| GND | 3, 8, 13, 18, 23, 28, 38 | GND |

## Analog scaling for the firmware

- VM_SENSE and BAT_SENSE: V_bus = V_adc / 0.15254 (18k / 118k). 30 V on the bus would give 4.6 V; the 100k
  limits the clamp current into the pin to about 65 uA.
- FET_NTC: R_ntc = 10k x V / (3.3 - V); T = 1 / (1/298.15 + ln(R_ntc / 10k) / 3977) - 273.15.
