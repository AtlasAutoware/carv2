# Car v2 software

What runs on the car, what it does and where it lives. How to get it onto the hardware:
docs/FLASHING.md. Rev B (the dev-kit carrier and the ATLAS-PWR-1 power board) comes first; the
rev A sections after it describe the drive board and brain board, kept as history.

## Rev B

Nothing in this section has run on the car yet. The supervisor firmware and the Jetson tools
pass their tests on simulated hardware (`python3 -m pytest firmware/supervisor/tests` and
`python3 -m pytest software/jetson/tests`; the second suite also runs the real firmware against
the Jetson tools over a pseudo-terminal).

### What changed from rev A

| Rev A | Rev B |
| --- | --- |
| STM32F405 on the drive board ran VESC and the power sequencing | The owned Flipsky Mini FSESC 6.7 Pro runs Flipsky's VESC firmware, configured in VESC Tool (below). The power sequencing moved to a Raspberry Pi Pico on the power board running MicroPython: `firmware/supervisor/` |
| Jetson on the ATLAS-BRN-1 brain board | Jetson on its NVIDIA dev-kit carrier; a 40-pin ribbon (J12) and a 1x12 harness (J14) go to the power board |
| OS_HALTED pin for "the Jetson has halted" | A HALT line from a systemd-shutdown hook, J12's 3.3 V through a divider, and a 1 Hz heartbeat |
| PCAL6408A expander for lidar, E-stop and charger lines | The supervisor switches the lidar; E-stop and charger reach J12 pins 33/32 as GPIO inputs and the status frame |
| INA228 on the BMS shunt | The JBD BMS measures the pack; the Pico reads it on UART0 and forwards it |
| TPS25751 PD controller, ID EEPROM, USB0 role switch | Gone: a USB-C PD trigger module and a CC/CV buck charge the pack; the dev kit's USB-C works as shipped |
| VESC on the STM32's USART3 through the stack | The FSESC's UART on J12 pins 8/10, `/dev/ttyTHS1` -> `/dev/atlas_vesc` |
| PoE camera from the brain board | The camera is powered through its M8 GPIO connector; its RJ45 carries data only |
| LAN7800 for the lidar | A USB 3 gigabit adapter on a dev-kit USB-A port, named `lidar0` |

The rev A drivers are kept in `software/jetson/atlas_hw/reva/` (expander, INA228, TPS25751, ID
EEPROM, USB role) with their tests; the `atlas` command no longer uses them, and its `pd`,
`usb-role`, `stm32` and `id` commands are gone.

### Supervisor firmware (Pico)

`firmware/supervisor/README.md` covers it: what each file does, how to flash it with Thonny or
mpremote, the USB protocol, the state machine and its timings, the LEDs, and what is still
unverified. In short: at power-on it precharges the motor bus and closes the main switch if the
E-stop loop is closed; it latches the E-stop until a button press (a press with the loop still
open is ignored); a short press presses the Jetson's power key and waits for its halt; a 5 s
press cuts the motor bus, the lidar and the Jetson at once and switches the latch off when the
button is released; it reports the BMS, the buses, the heatsink and the Jetson link once a
second. For a hung Jetson, move the Pico's
USB cable to the debug hub's spare port and send it `reboot hard` (SYS_RESET* pulse) or
`jetson_power_cycle` (the dev kit's DC feed off for 10 s) from the laptop.

### Jetson

JetPack 6 for the Orin Nano Super developer kit, plus `software/jetson/`, installed by
`sudo software/jetson/system/install.sh`:

| Piece | What it does |
| --- | --- |
| `atlas` command (`atlas_hw`, in /opt/atlas) | `atlas status`, `battery`, `lidar on/off`, `supervisor ...` (status, shutdown, fan, bms-fets, hb-timeout, log, send, repl, resume), `vesc --probe`. `atlas --help` lists everything |
| atlas-battery.service (`atlas battery-daemon`) | Owns the supervisor's USB port: sends the 1 Hz heartbeat, holds JETSON_UP (J12 pin 31) and LIDAR_REQ (pin 29), writes the latest status to /run/atlas/supervisor.json and the battery estimate to /run/atlas/battery.json, logs the supervisor's events to the journal, answers the CLI and ROS on /run/atlas/supervisor.sock, and shuts the Jetson down cleanly under 3.30 V per cell (I x R corrected, 30 s, not while charging). When it stops it sends "bye" |
| atlas-hw-init.service | At boot, once atlas-battery.service has the link: lidar power per `ATLAS_LIDAR_AT_BOOT`, then a one-line summary in the journal |
| /usr/lib/systemd/system-shutdown/atlas-halt | At the very end of every shutdown: sends `{"cmd":"halt","verb":"poweroff"}` (or reboot, halt, kexec) to the supervisor and drives JETSON_UP low |
| /etc/systemd/logind.conf.d/90-atlas-power-key.conf | The supervisor's power-key press (J14 pins 12/11) arrives as KEY_POWER: shut down |
| /etc/udev/rules.d/99-atlas.rules | `/dev/atlas_vesc` (serial@3100000), `/dev/atlas_supervisor` (USB 2e8a:0005, ModemManager kept off it), `/dev/atlas_i2c_power` (bus 7, spare), `lidar0`, gpiochip group access |
| NetworkManager: atlas-lidar | The USB adapter (drivers r8152, ax88179_178a or lan78xx): 192.168.0.100/24 |
| NetworkManager: atlas-camera | The dev kit's own port (r8168/r8169): link-local, MTU 9000 |
| /etc/atlas/atlas.conf | Supervisor port, lidar at boot, low-battery threshold, pack resistance, optional GPIO line overrides |
| nvpmodel | Set to the 25 W mode by install.sh: the DC jack is fed from the pack, and MAXN_SUPER can draw more than the jack's 3.5 A at 12 V |

**How a shutdown goes.** Button (or `atlas supervisor shutdown`, or a low pack) -> the Pico kills
the VESC, opens the main switch and presses the power key for 180 ms -> logind powers off ->
atlas-battery.service stops and sends "bye" -> at the end, atlas-halt sends HALT -> the Pico
switches the lidar off and, 3 s later, the Pololu latch. If HALT never comes, J12's 3.3 V going
away for 2 s does the same; failing both, the supervisor stops waiting 120 s after "bye" (60 s
after the press if there was no "bye"). `sudo poweroff` and `sudo reboot` on the Jetson work as
usual: HALT switches the car off, REBOOT keeps it on.

**A lost heartbeat** (atlas-battery.service crashed, or the Pico's USB cable came loose) is not
a reason to cut a running Jetson. 60 s after the last heartbeat (120 s after a "bye"), if J12's
3.3 V or JETSON_UP says the Jetson is still powered, the supervisor opens the main switch and
presses the power key, again every 10 s for up to 60 s, and then waits for HALT or for the 3.3 V
to go, however long that takes. Only when neither line shows the Jetson as powered does it switch
the car off at once.

**Low pack while charging.** The supervisor's low-pack shutdown (11.6 V for 10 s) stays active
with the USB-C charger in, unless the pack voltage is rising: the car at 25 W with the lidar and
camera can draw more than the 42 W charger gives.

**The J12 lines.** `atlas_hw/gpio.py` uses libgpiod (python3-libgpiod 1.x on JetPack 6, or the
2.x bindings) and looks the lines up by name, then by offset: JETSON_UP PQ.06 (gpiochip0 line
106), LIDAR_REQ PQ.05 (105), ESTOP_OK PH.00 (43), CHG_STAT_N PG.06 (41). These are the commonly
published numbers for the Orin Nano dev kit; check them once with `gpioinfo` on the car and set
`ATLAS_GPIO_<NAME>` in /etc/atlas/atlas.conf if they differ. NVIDIA reported a gpioset output
problem in JetPack 6.0 and 6.1, fixed in 6.2 (R36.4.3); if the outputs do not move, the USB link
still carries everything they do.

**Working on the Pico from the Jetson.** `atlas supervisor repl --yes` stops the firmware (motor bus
off) and makes atlas-battery.service let go of the port; then use Thonny, mpremote or `screen`;
press Ctrl-D there to restart the firmware, and run `atlas supervisor resume`. Do not just stop
atlas-battery.service while the firmware runs: 120 s after its "bye" the supervisor presses the
power key and the Jetson shuts down (unless you send `hb_timeout 0`).

**Battery estimate.** Same method as rev A (start from the corrected pack voltage, then count
coulombs), but the current comes from the JBD BMS through the Pico's status frame (10 mA steps,
about once a second) and the daemon integrates it. `atlas battery` also shows the cell voltages,
temperatures and the BMS's own state of charge. The calibration notes under "Battery estimate:
what to measure" below still apply. If the BMS does not answer, the voltage comes from the
Pico's divider and the estimate stops counting.

### The FSESC (VESC Tool settings)

The FSESC keeps Flipsky's VESC firmware; nothing is built. Connect VESC Tool through the power
board's debug USB-C (the hub has a port for the FSESC's USB) and set, then write the app and motor
configurations:

- **UART app on the COMM port at 115200** (App Settings > General > App to Use: UART;
  App Settings > UART > Baudrate 115200). `vesc_driver` on the Jetson uses `/dev/atlas_vesc` at
  115200.
- **Kill switch on ADC2, active low** (App Settings > General > Kill Switch Mode, the ADC2 low
  option, `KILL_SW_MODE_ADC2_LOW` in the bldc source). The supervisor holds ADC2 at 3.3 V
  through 1 k to run and pulls it to 0 V to kill; VESC kills below 1.65 V, checked every 10 ms
  (bldc `timeout.c`). Before turning it on, check in VESC Tool's realtime data that ADC2 reads
  about 3.3 V with the car in RUN: if the FSESC divides its ADC inputs, 3.3 V could read under
  1.65 V and the motor would never run. The kill switch needs VESC firmware 5.03 or later.
- **Servo output on** (App Settings > General > Enable Servo Output). The PPM pin then drives the
  steering servo and `vesc_driver`'s `commands/servo/position` works as on car 1. This is why the
  kill switch uses ADC2 and not the PPM pin.
- **Timeout** about 250 ms with about 10 A brake current (App Settings > General), so a crashed
  ROS stack stops the car.
- **Limits** as rev A: motor 70 A / -40 A, battery 90 A / -12 A, absolute 150 A, cut-off
  13.4-12.6 V, 4 cells, 8.4 Ah; maximum input voltage about 18 V. Check that the Mini 6.7 Pro runs
  at 12.0 V on a bench supply first (its rated floor is 14 V).
- **IMU: open question.** The FSESC has no IMU, and VESC's external-IMU input shares the COMM
  port's pins with the UART, so with the UART link there is no IMU on the ESC. Options: an
  LSM6DS3TR-C breakout (Adafruit 4503) on the Jetson's I2C bus 7 (J12 pins 3/5, reached through
  the ribbon at the power board; needs a small ROS node that does not exist yet), or the OAK-D's
  IMU as on car 1, or the FSESC on USB with the IMU on its COMM port (then UART1 is free and the
  kill switch wiring is unchanged). Car 1's stack keeps working meanwhile.

`atlas vesc --probe` asks the FSESC for its firmware version and hardware name over the UART
(stop `vesc_driver` first: one program per port).

**`vesc_driver` and flow control.** The ROS 2 `vesc_driver` (f1tenth/vesc, `vesc_driver/src/vesc_interface.cpp`,
`connect()`) opens the port with `FlowControl::HARDWARE`; on UART1 with only TX/RX/GND wired that
can stall transmit. Change that one line to `FlowControl::NONE` in the team's copy (or tie the
Jetson's UART1 CTS, J12 pin 36, low).

### ROS 2 (rev B)

`software/ros2/atlas_power`: `/battery` (from atlas-battery.service, now with cell voltages, the
highest BMS temperature and the BMS capacity), `/estop_ok` and `/charging` (J12 pins 33 and 32,
or the supervisor status if libgpiod is missing), service `/lidar_power` (through the daemon's
socket). `vesc_driver`: `port: /dev/atlas_vesc` at 115200, with the flow-control change above.

## Rev A (history): STM32 on the drive board, VESC 6.06 with the ATLAS_DRV1 target

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
  precharge resistors). If the bus collapses while on (a TPS48111 over-current trip), the
  STM32 drops MAIN_ON so the chip's own 15 s retry cannot close the FETs onto an empty bus,
  and precharges again 15 s later, three times at most.
- **E-stop and gate driver.** While the loop is open the motor ignores commands. The DRV8323RS
  runs from the switched bus and forgets its settings whenever ENABLE drops for about a
  millisecond, so the firmware writes the 40 V/V gain and the over-current settings back
  after every precharge and E-stop release, reads the gain back every 5 ms, and holds the
  motor for 0.5 s after a restore. VESC measures the current-sensor offsets once at boot; if
  the gate driver was not configured the whole time, the firmware measures them again (about
  1.4 s, commands locked out) once the E-stop is closed and the motor is still.
- **Jetson.** 5 s after the brain board gets power, if the Jetson has not started by itself,
  the STM32 presses its power button (up to twice, 20 s apart). It never presses after the
  Jetson has run, so a Jetson shut down on purpose stays down. Once the Jetson has run, a halt
  lasting 3 s makes the STM32 switch the car off (`atlas_autooff 0` turns that off until the
  next start).
- **Power button.** A press (30 ms, so a spike on the remote button lead does not count) asks
  the Jetson to shut down (1 s on the power-key line, again every 10 s in case it was still
  booting), waits up to 60 s for it to halt, then switches off the brain board, the main switch
  and the latch.
- **Defaults** for this car (VESC Tool can change them): motor 70 A / -40 A, battery 90 A /
  -12 A, absolute 150 A (the current sensing is linear to about 175 A), battery cut-off
  13.4-12.6 V (3.35-3.15 V per cell under load, above the BMS cut at 3.00 V; starting values
  to check on the bench), 4 cells, 8.4 Ah, power button mode "toggle button only". The UART
  app is VESC's default (UART at 115200).
- **Terminal commands** (VESC Tool): `atlas_status`, `atlas_precharge`, `atlas_main_off`,
  `atlas_brain on|off|press`, `atlas_autooff 0|1`, `atlas_poweroff`, `test_button`.

## Rev A (history): Jetson on the brain board

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
stack I2C = module I2C1 = i2c@c250000 (normally /dev/i2c-7): INA228 0x40, ID EEPROM 0x50
(answers 0x50-0x57), PD controller 0x20, PoE controller 0x28 (and its broadcast address 0x30). Brain board I2C = module I2C0 = i2c@c240000
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

## Rev A (history): ROS 2

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
