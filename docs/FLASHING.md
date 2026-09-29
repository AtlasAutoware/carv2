# Programming the car v2 boards

Every chip is programmed on the assembled boards, never before it is soldered. This page is
the order to do it in and the commands. None of it has been tried on real boards yet: the
boards are not built. Where a step is untested or depends on a guess, it says so.

## What gets programmed

| Part | What | First time | Later |
| --- | --- | --- | --- |
| STM32F405 (drive U601) | VESC 6.06 with the ATLAS_DRV1 target + VESC bootloader | SWD on J601 with an ST-Link (step 1) | VESC Tool over USB (step 7) |
| Jetson Orin Nano module + NVMe | JetPack for the Orin Nano Super | On the NVIDIA dev kit carrier (step 3) | `apt` updates; reflash the same way |
| TPS25751D (drive U701) | PD sink and charger settings in its EEPROM (U702) | From the Jetson through the controller (step 6) | `atlas pd update` |
| 24AA02 (drive U1002) | Board ID record | `atlas id --write` (step 8) | same |

Nothing to program: BQ25798 (the PD controller sets it up), USB2514B (strapped), CP2102N
(factory default), TPS23861 (auto mode), BQ7791508 (fixed thresholds), INA228 (set up at run
time), LAN7800.

## Tools

- An ST-Link with a 10-pin 1.27 mm Cortex debug cable for J601. An STLINK-V3SET is on the
  Syslab purchase sheet (row 96); its box includes a flat cable from its 14-pin STDC14
  connector to that 10-pin header.
- A PC with one of: OpenOCD, stlink-tools (`st-flash`), or STM32CubeProgrammer. The team
  laptop (CachyOS) has none of them; `sudo pacman -S openocd stlink` installs the first two.
- VESC Tool 6.06 (on the laptop at ~/vesc_tool/build/lin/vesc_tool_6.06).
- An Ubuntu PC or VM for NVIDIA's flashing tools (SDK Manager or the L4T flash scripts).
- The NVIDIA Orin Nano Super developer kit (on the order) for the first Jetson flash.
- Optional: an Adafruit FT232H (purchase sheet row 95) to set up USB-C charging before the
  brain board is on the car (step 6, bench variant).

Firmware files: `firmware/vesc/prebuilt/` (built from this repo, see `BUILD_INFO.txt` there),
or build them with `firmware/vesc/build.sh`.

## 1. STM32 first flash (drive board, SWD)

Do it before the brain board goes on: J601 is at drive (105.5, 33.5), under the brain board
once stacked, and whether a debug cable fits through the 20 mm gap has not been checked.

1. Pack connected (or a current-limited bench supply on the pack terminals, 14-16 V, 0.5 A).
   Press the power button: the latch turns on the 5 V and 3.3 V rails, and a blank STM32
   cannot turn them off again (KILL has a pull-down).
2. ST-Link on J601 (pin 1 marked on the silkscreen). J601 carries 3.3 V as the reference only.
3. Write the combined image (firmware at 0x08000000, VESC bootloader at 0x080E0000):

   ```
   openocd -f interface/stlink.cfg -f target/stm32f4x.cfg \
     -c "program firmware/vesc/prebuilt/atlas_drv1_full.hex verify reset exit"
   ```
   or `st-flash --reset --format ihex write firmware/vesc/prebuilt/atlas_drv1_full.hex`,
   or `STM32_Programmer_CLI -c port=SWD -w firmware/vesc/prebuilt/atlas_drv1_full.hex -v -rst`.

   Use the .hex, not the .bin: the bootloader is only in the .hex, and VESC Tool needs it for
   every later update.
4. USB-C cable to the laptop, FLASH switch (SW801) on normal. The STM32 is on hub port 2.
   Open VESC Tool, connect: it should report firmware 6.06, hardware ATLAS_DRV1. In its
   terminal, `atlas_status` prints the main switch, E-stop, gate driver and brain board state.
5. Motor and current set-up: docs/COMPLETE_CAR.md.

## 2. Stack the boards

Brain board on the drive board (mech/README.md). With the car on, the STM32 raises POWER_EN
and the brain board powers up; about 5 s later the STM32 presses the Jetson's power button
if the Jetson has not started by itself.

**SW1 on the brain board** (slide switch, near the rear edge) must be in button mode, with
its pins 2 and 3 connected (check with a meter; which slider position that is has not been
checked). In the other position Antmicro's auto-on circuit restarts the Jetson a few seconds
after every shutdown, and the drive board would never see it stay halted.

## 3. Jetson module and NVMe

Flash on the NVIDIA dev kit first. It is NVIDIA's supported path, and the brain board
carries the same module ports the software uses:

1. Module and NVMe on the dev kit carrier. Flash JetPack with SDK Manager or the L4T scripts,
   following NVIDIA's instructions for the Orin Nano Super developer kit. The laptop has an
   unchecked image, ~/Downloads/jetpack72/jetsoninstaller-r39.2.1-arm64.iso; check that the
   release supports the Orin Nano before using it.
2. First boot on the dev kit: user `atlas`, network, `sudo apt update && sudo apt upgrade`.
3. Move the module and NVMe to the brain board.

Flashing in the car also looks possible but is untested: FLASH switch to flash (USB-C goes
straight to the Jetson's USB0), hold S1 (FORCE_RECOVERY) and switch the car on or press S4
(power). On the brain board, S1 is on the right-hand edge (car right side) 74 mm from the rear
edge, S4 34 mm from the rear, S2 and S3 are user buttons. The STM32 must already run step 1's
firmware, because it powers the brain board. Risk: the brain board has no VBUS detection on
USB0, which NVIDIA's initrd flash may need.

## 4. Atlas tools on the Jetson

```
git clone https://github.com/AtlasAutoware/carv2.git && cd carv2
sudo software/jetson/system/install.sh
sudo reboot
atlas status
```

`atlas status` should list the drive board, the pack voltage, the PD controller's mode,
E-stop, charger, lidar power and the USB0 role. What the install does: docs/SOFTWARE.md.

## 5. Check the stack buses

```
i2cdetect -y -r 7      # stack I2C: 0x20 PD controller, 0x28 PoE controller (and 0x30, its broadcast
                       # address), 0x40 INA228, 0x50-0x57 ID EEPROM (the 24AA02 answers on all eight)
i2cdetect -y -r 1      # brain board: 0x20 expander (and the module's own 0x40)
```
The bus numbers are the usual ones for these controllers (c250000.i2c and c240000.i2c);
`/dev/atlas_i2c_stack` and `/dev/atlas_i2c_sys` point at the right ones either way.

## 6. USB-C PD controller EEPROM

Until this is done the car does not charge from USB-C (the controller waits in PTCH mode).

1. Make the two files with TI's tool: docs/TPS25751_CONFIG.md. Commit them to
   `firmware/tps25751/`.
2. On the Jetson:
   ```
   sudo cp firmware/tps25751/tps25751_lowregion.bin /etc/atlas/
   sudo atlas pd flash firmware/tps25751/tps25751_full.bin --lowregion /etc/atlas/tps25751_lowregion.bin
   atlas pd status
   ```
   `atlas pd flash` loads the configuration into the controller's RAM first (it cannot write
   its EEPROM before it runs one), writes the Full Flash image through the controller (TI's
   FLad/FLwd commands; the controller is the only I2C controller on its EEPROM bus), reads it
   back, checks it with FLvy, writes the region pointer last and restarts the controller from
   the EEPROM. It should end with "the controller booted from the EEPROM".
3. Plug in the 65 W charger. `atlas pd status`: `VBUS PD contract`. `atlas status`: charging.

A power cut in the middle leaves the region pointers cleared, so the controller comes back in
PTCH mode; run the same command again. Meanwhile `/etc/atlas/tps25751_lowregion.bin` keeps
charging working while the car is on (atlas-hw-init loads it at boot).

Later changes: `sudo atlas pd update new_lowregion.bin` (TI's two-region update: the new
bundle goes into the unused region and the pointers switch only after it verifies).

**Bench variant, brain board not on the car:** an FT232H on the drive board's stack socket
reaches the same chips. Wires: D0 (SCL) to socket pin 19, D1 and D2 (SDA, the board's I2C
switch on) to pin 20, GND to pin 36, and D7 to D0 (the PD controller stretches the clock and
pyftdi needs D7 to see it). The drive board has 10k pull-ups on these lines. From the repo on
the laptop:
```
pip install smbus2 pyftdi
cd software/jetson
python3 -m atlas_hw.cli --ftdi pd flash ../../firmware/tps25751/tps25751_full.bin --lowregion ../../firmware/tps25751/tps25751_lowregion.bin
```
J702 (the EEPROM header, not fitted) is not needed for any of this.

## 7. Later STM32 updates (VESC Tool)

VESC Tool, Firmware tab, Custom File: `firmware/vesc/prebuilt/atlas_drv1.bin`, Upload. The
STM32 restarts at the end.

With the POWER_EN fix (below, on every board built from the Sept 29 files) the brain board and
the Jetson stay up through that restart. **On a board without it**, the restart switches the brain
board off without warning. So first: in the VESC Tool terminal `atlas_autooff 0` (the car stays on when the
Jetson halts), then `sudo poweroff` on the Jetson and wait for it to halt, then upload. The
STM32 does not press the Jetson's power button again after a shutdown, so it stays off until
the upload. The new firmware powers the brain board up and, 5 s later, starts the Jetson.

## 8. Board ID

```
sudo atlas id --write --serial 001 --rev A
```

## The POWER_EN fix (applied Sept 29, 2026)

Before this change R609 (100k, drive board) pulled STK_POWER_EN down, so whenever the STM32 was
in reset, flashing, or blank, the brain board and the Jetson lost power. The drive board now has
two resistors for it:

- R609 goes to +3V3 instead of GND. The firmware already drives PA4 high at start-up and low
  before it turns the car off, so only the reset and flashing moments change.
- R625, a new 10k pull-down on GATE_EN_MCU (PB5, input A of the E-stop AND gate U502), next to
  U502. Before it, nothing held that line while the STM32 is in reset or in its ROM bootloader. The bootloader uses PB5 as
  CAN2 RX and may pull it up, and it also uses PA9/PA10 (PWM_BH/PWM_CH), PB13 (PWM_AL) and
  PC10/PC11 (ESTOP_OK, IMU SDA) for its USART1, USART3 and CAN2 interfaces (ST AN2606; the
  exact pin states there have not been checked). With the gate driver held off by the
  pull-down, those pins cannot switch the power stage while the motor bus is still charged.

With both:

- The Jetson stays up through STM32 resets and VESC Tool updates.
- The Jetson can flash the STM32 itself, even a blank one, with no ST-Link and no cable in
  the stack gap: `atlas stm32 bootloader` (expander P1 = BOOT0, P0 = reset) starts the STM32's
  ROM bootloader, which listens on USART3 (PB10/PB11, the Jetson UART) and on USB DFU (hub
  port 2); then `stm32flash -b 115200 -w atlas_drv1_full.hex -v /dev/atlas_vesc` and
  `atlas stm32 run`. Unplug the USB-C cable during a UART flash so the bootloader does not pick
  USB instead. Untested; stm32flash's handling of a .hex with a gap has not been checked.
  Without the GATE_EN pull-down, do not use this route (see above).
- The brain board powers up as soon as the car is on, before the STM32 runs.

`ATLAS_POWER_EN_FIXED=1` in /etc/atlas/atlas.conf (the installed default now) unlocks
`atlas stm32`. Set it to 0 on a board built from files older than Sept 29.

## Troubleshooting

- `atlas pd status` says PTCH: the EEPROM is blank or was not accepted. `sudo atlas pd load
  /etc/atlas/tps25751_lowregion.bin` runs the configuration until the next power cycle.
- VESC Tool does not see the ESC: FLASH switch on normal, USB-C cable with data lines.
- `atlas: cannot open /dev/i2c-7`: log out and in again after install (i2c group).
- The Jetson turns off shortly after boot: the drive board saw it halted for 3 s after it had
  been running. Check SW1 (step 2) and `atlas_status` in VESC Tool.
