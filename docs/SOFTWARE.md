# Car v2 software

What runs on the two boards, what it does and where it lives. How to get it onto the boards:
docs/FLASHING.md. Nothing here has run on real boards yet; the firmware compiles and the
Jetson tools pass their tests against simulated chips (`software/jetson/tests`).

## STM32 on the drive board: VESC 6.06 with the ATLAS_DRV1 target

`firmware/vesc/hw_atlas_drv1.c` and `.h`, a VESC hardware target based on the HD60 one
(same STM32F405 + DRV8323RS family). `firmware/vesc/build.sh` clones the VESC sources at the
6.06 release (the version of VESC Tool on the team laptop), adds the target and builds; the
results go to `firmware/vesc/out/`. `firmware/vesc/prebuilt/` holds a build of the committed
sources with its `BUILD_INFO.txt`. Building needs `arm-none-eabi-gcc` (on CachyOS:
`sudo pacman -S arm-none-eabi-gcc arm-none-eabi-newlib`); the script tries VESC's own
GCC 7 download first and falls back to the system compiler.

Differences from a stock VESC, all in the target files:

- **Pins.** Gate driver SPI, current sensing (40 V/V), hall and servo inputs, USART3 to the
  Jetson at 115200, the IMU on I2C, plus the Atlas I/O: KILL (PB12), MAIN_ON (PA6), PRECHG_ON
  (PA7), brain board POWER_EN (PA4), Jetson power key (PC14), OS_HALTED, E-stop, the TPS48111
  current monitor (PA5, 46 V/V over 0.2 mOhm).
- **Main switch and precharge.** At start-up the STM32 closes the precharge path, checks that
  the motor bus rises (below 4 V after 10 ms means a short: stop) and settles above 9 V
  within 400 ms, then turns on the main FETs. A failed precharge is not retried by itself;
  `atlas_precharge` in the VESC Tool terminal retries it (at most every 15 s, for the
  precharge resistors).
- **E-stop.** While the loop is open the motor ignores commands. The DRV8323RS forgets its
  settings whenever its ENABLE drops, so the firmware writes the 40 V/V gain and the
  over-current settings back when the E-stop closes, checks the gain every 250 ms, and redoes
  the current-offset calibration once the motor is still.
- **Jetson.** 5 s after start, if the Jetson has not started by itself, the STM32 presses its
  power button (up to twice, 20 s apart). Once the Jetson has run, a halt lasting 3 s makes the
  STM32 switch the car off (`atlas_autooff 0` turns that off until the next start).
- **Power button.** A press asks the Jetson to shut down (1 s on the power-key line), waits up
  to 60 s for it to halt, then switches off the brain board, the main switch and the latch.
- **Defaults** for this car (VESC Tool can change them): motor 70 A / -40 A, battery 90 A /
  -12 A, absolute 180 A, battery cut-off 12.0-11.2 V, 4 cells, 8.4 Ah, power button mode
  "toggle button only". The UART app is VESC's default (UART at 115200).
- **Terminal commands** (VESC Tool): `atlas_status`, `atlas_precharge`, `atlas_main_off`,
  `atlas_brain on|off|press`, `atlas_autooff 0|1`, `atlas_poweroff`, `test_button`.

## Jetson on the brain board

JetPack for the Orin Nano Super, flashed as for the NVIDIA developer kit, plus
`software/jetson/`, installed by `sudo software/jetson/system/install.sh`:

| Piece | What it does |
| --- | --- |
| `atlas` command (`atlas_hw` package, in /opt/atlas) | `atlas status`, `battery`, `lidar on/off`, `pd ...` (USB-C PD controller), `id` (board ID EEPROM), `usb-role`, `stm32 ...` (needs the POWER_EN fix). `atlas --help` lists everything. |
| atlas-hw-init.service | At boot: sets up the brain board expander (outputs low before they become outputs, so the STM32 is never reset by accident), lidar power as configured, loads the PD configuration into RAM if the PD EEPROM is blank, sets the Jetson's USB0 to device mode. |
| atlas-battery.service | Owns the INA228: pack voltage, current, charge counter and a state-of-charge estimate, written to /run/atlas/battery.json every 2 s. Shuts the Jetson down cleanly if the corrected cell voltage stays under 3.30 V for 30 s. |
| /etc/systemd/logind.conf.d/90-atlas-power-key.conf | The drive board's power button arrives as KEY_POWER: shut down. |
| NetworkManager: atlas-lidar | LAN7800 port (driver lan78xx): 192.168.0.100/24. The TiM561 ships at 192.168.0.1. |
| NetworkManager: atlas-camera | The module's own Ethernet on the camera jack (Realtek, r8168/r8169): link-local, MTU 9000 for GigE Vision. |
| /etc/udev/rules.d/99-atlas.rules | /dev/atlas_vesc (UART to the STM32), /dev/atlas_i2c_stack, /dev/atlas_i2c_sys, group permissions. |
| /etc/atlas/atlas.conf | Lidar at boot, PD Low Region file, low-battery threshold, pack resistance, POWER_EN fix flag. |

Where the parts sit on the Jetson (from the brain board netlist and NVIDIA's pin tables):
stack I2C = module I2C1 = i2c@c250000 (normally /dev/i2c-7): INA228 0x40, ID EEPROM 0x50,
PD controller 0x20, PoE controller 0x28. Brain board I2C = module I2C0 = i2c@c240000
(/dev/i2c-1): expander 0x20. VESC UART = module UART1 = serial@3100000. The tools find the
bus numbers by controller address, so a different numbering does not break them.

### Battery estimate: what to measure

The start-up estimate reads the pack voltage through a generic NMC rest-voltage table and
corrects it with an assumed pack resistance of 0.05 Ohm. Neither is Molicel P28A data. To
calibrate:
- Pack resistance: note `atlas battery` at rest and again under a steady load (lidar on,
  Jetson busy); (V_rest - V_load) / (I_load - I_rest). Put it in ATLAS_PACK_R.
- Rest-voltage table: after a full charge, log `atlas battery --json` during a slow discharge
  with pauses; write the pairs as [[cell_volts, fraction], ...] to /etc/atlas/ocv.json.
After that, coulomb counting keeps the percentage. The INA228 only counts while the car is on,
so a charge with the car off is picked up from the voltage at the next start-up.

## ROS 2

`software/ros2/atlas_power` (ament_python; copy or link it into the car's workspace):

- `/battery` (sensor_msgs/BatteryState, from atlas-battery.service), `/estop_ok` and
  `/charging` (std_msgs/Bool), service `/lidar_power` (std_srvs/SetBool).
- `ros2 launch atlas_power atlas_power.launch.py`

Changes to car 1's stack for car 2:
- `vesc_driver`: `port: /dev/atlas_vesc` (115200, as on car 1).
- Lidar: `sick_scan_xd`, TiM5xx launch file, `hostname: 192.168.0.1`.
- Camera: LUCID's Arena SDK and `arena_camera_ros2`; set the camera's packet size to use the
  9000-byte MTU.
- IMU: the drive board's LSM6DS3 through the VESC (if the `vesc_driver` version in use
  publishes it) instead of the OAK-D.
