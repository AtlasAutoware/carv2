# Jetson software for rev B: what changed, judgment calls, unverified items, open questions

Written Oct 24, 2026 with atlas_hw 0.2.0. The user-facing description is in docs/SOFTWARE.md
("Rev B"); the supervisor side is in firmware/supervisor/README.md and NOTES.md.

## What happened to each file

| File | Rev B |
| --- | --- |
| `atlas_hw/board.py` | Rewritten: supervisor port and USB IDs, VESC UART, J12 GPIO lines (name and offset), I2C bus 7 as a spare. The rev A constants moved to `atlas_hw/reva/board.py` |
| `atlas_hw/expander.py`, `ina228.py`, `tps25751.py`, `ideeprom.py`, `usbrole.py` | Retired: moved (`git mv`) to `atlas_hw/reva/`, imports fixed, tests kept as `tests/test_reva_*.py`. The `atlas` command does not use them |
| `atlas_hw/i2c.py` | Kept as is (the reva drivers use it; bus 7 is a spare on rev B) |
| `atlas_hw/supervisor.py` | New: raw-mode port, the line protocol, `Link`, `DaemonClient`, `connect()`, the `Daemon` (heartbeat, JETSON_UP, status file, journal events, socket), `send_halt()` |
| `atlas_hw/gpio.py` | New: libgpiod 1.x and 2.x, lines by name then offset, `read_inputs()`, `request_lidar()` |
| `atlas_hw/battery.py` | The estimator and the low-voltage shutdown are unchanged in method; the source is now the supervisor's status (`PackSource` integrates the BMS current). `BatteryMonitor` is the daemon's callback; `run_daemon()` starts the supervisor daemon with it |
| `atlas_hw/vesc.py` | New: `atlas vesc --probe` (COMM_FW_VERSION over the UART) |
| `atlas_hw/cli.py` | Rewritten: `status`, `battery`, `lidar`, `supervisor ...`, `vesc`, `hw-init`, `battery-daemon`, `halt-hook`. `pd`, `usb-role`, `stm32`, `id` and `--ftdi` are gone |
| `system/99-atlas.rules` | `/dev/atlas_vesc` on serial@3100000, `/dev/atlas_supervisor` by 2e8a:0005 (ModemManager ignored), `/dev/atlas_i2c_power`, gpiochip group, `lidar0` |
| `system/NetworkManager/atlas-lidar.nmconnection` | Matches `r8152;ax88179_178a;lan78xx;` |
| `system/NetworkManager/atlas-camera.nmconnection` | Comment only: no PoE, camera powered over its GPIO connector |
| `system/atlas.conf` | Adds `ATLAS_SUPERVISOR_TTY` and commented `ATLAS_GPIO_*`; drops `ATLAS_PD_LOWREGION` and `ATLAS_POWER_EN_FIXED` (install.sh removes them from an existing file) |
| `system/systemd/atlas-battery.service` | Now the supervisor link daemon too; `Restart=always`, 2 s |
| `system/systemd/atlas-hw-init.service` | Oneshot after atlas-battery.service: lidar per config, summary. `pd ensure` and `usb-role` dropped |
| `system/system-shutdown/atlas-halt` | New, installed in /usr/lib/systemd/system-shutdown/ |
| `system/logind/90-atlas-power-key.conf` | Comment only |
| `system/install.sh` | gpiod packages, the hook, a byte-compile (the hook runs read-only), getty check on ttyTHS1, 25 W nvpmodel, rev A key clean-up |
| `software/ros2/atlas_power/power_node.py` | J12 inputs through `gpio.Lines` (fallback: status file), lidar through the daemon socket, cell voltages and BMS temperature in `/battery` |
| `tests/` | 77 tests: rev B (`test_supervisor`, `test_gpio`, `test_battery`, `test_cli`, `test_vesc`, `test_integration_firmware`) and rev A (`test_reva_*`) |

## Judgment calls

1. **The battery daemon owns the supervisor port.** One process must read a tty, and the
   battery estimate needs the status frames, so `atlas battery-daemon` is the heartbeat loop and
   the link owner; everything else goes through `/run/atlas/supervisor.sock` (or opens the port
   directly when the daemon is not running). The service keeps its rev A name so the docs and the
   ROS node's warning still match.
2. **JETSON_UP is held by the same daemon**, not by atlas-hw-init: a oneshot unit cannot hold a
   libgpiod line after it exits. hw-init `Wants=` the daemon (which starts the heartbeat and
   raises JETSON_UP) and then applies the lidar setting through it. The supervisor does not treat
   JETSON_UP falling as a halt (the daemon stops early in a shutdown); the shutdown hook drops it
   at the very end anyway.
3. **"bye" when the daemon stops.** Without it, a slow shutdown (a unit holding systemd for 90 s)
   would hit the supervisor's 60 s heartbeat timeout before the file systems are synced. With
   it the supervisor waits 120 s instead of 60 s and stops pressing the power key. If the
   heartbeat does not come back, the supervisor (since the Oct 24 review, M4) presses the power key
   while the Jetson is still powered rather than cutting it, so a service stopped by hand ends in a
   clean shutdown 120 s later unless the service comes back or `hb_timeout 0` is sent. The CLI's `supervisor repl` / `resume` exist so
   nobody needs to stop the service.
4. **The daemon lets go of the port when the Pico is in its REPL** (it sees the REPL banner or
   prompt, or forwards a `repl` ack) and takes it back on `atlas supervisor resume`, so Thonny or
   mpremote can use the port from the Jetson.
5. **LIDAR_REQ mirrors the lidar state** reported by the supervisor, and a change is sent both as
   the USB `lidar` command and as an edge on LIDAR_REQ. The supervisor treats LIDAR_REQ by edges,
   so moving the level towards the reported state never changes anything; for 3 s after a request
   the daemon does not resync from status, so a frame sent before the command cannot undo it.
6. **The NetworkManager lidar profile matches drivers, not `lidar0`**: it then works even if the
   udev rename does not happen. `cdc_ncm` is left out of both (some AX88179B adapters bind to it,
   but USB gadget links can use it too).
7. **The shutdown hook calls Python** (`atlas halt-hook`, so the port and GPIO handling is the
   tested code) with a 5 s timeout and a shell `printf` fallback. install.sh byte-compiles
   /opt/atlas because the root file system is read-only by then.
8. **The CLI never asks the BMS to open its discharge FETs without `--yes`**, and the firmware
   refuses it without `"force": true`.
9. **The ROS node reads ESTOP_OK and CHG_STAT_N on J12** (lowest latency) and falls back to the
   status file (up to 1 s old) when libgpiod is missing or the lines are busy.
10. **25 W power mode** set by install.sh, found by name in /etc/nvpmodel.conf.

## Unverified

- **Pico USB IDs** 2e8a:0005: MicroPython's rp2 default (`ports/rp2/mpconfigport.h`). Any other
  MicroPython board on the Jetson would match the same udev rule.
- **gpiochip line numbers and names**: PQ.06/106, PQ.05/105, PH.00/43, PG.06/41 are the commonly
  published Orin Nano dev-kit values (only PH.00 = line 43 is confirmed on NVIDIA's forum). Run
  `gpioinfo`. The output fix for JetPack 6.0/6.1 is in 6.2 (R36.4.3) per NVIDIA.
- **`/dev/ttyTHS1` for serial@3100000** on the car's JetPack 6 (ttyTHS0 on JetPack 5). The udev
  rule matches the controller, so the name does not matter to the tools, but check
  `ls -l /dev/atlas_vesc`. Also that no serial console runs on it (install.sh checks gettys and
  `/proc/cmdline`).
- **J14 pin 12 as KEY_POWER** (verify with `evtest`) and **J12 pin 17 dropping after poweroff**
  (verify with a meter): both from the dev-kit study, both "likely".
- **The nvpmodel.conf format** (`< POWER_MODEL ID=n NAME=25W >`) the install script parses.
- **The USB adapter's driver** on the car's kernel: `zcat /proc/config.gz | grep -E 'RTL8152|LAN78XX|AX88179'`.
- **termios on ttyACM**: raw mode with VMIN 1 and O_NONBLOCK, tested only on a pseudo-terminal.
- Python 3.10 (JetPack 6) is assumed; the tests ran on 3.13.

## Open questions

1. **IMU.** The FSESC has none and its external-IMU pins are the UART used for the Jetson. An
   LSM6DS3TR-C breakout on J12's I2C bus 7 needs a mounting point at the power board end of the
   ribbon and a small ROS node (not written); or keep the OAK-D's IMU as on car 1.
2. Should `atlas status` show the supervisor's events since boot (it has `log` for the last 20)?
3. JETSON_UP and LIDAR_REQ are released when atlas-battery.service stops. Whether Tegra keeps the
   level after release is unknown; nothing depends on it (judgment call 2), but it is worth one
   look with a meter.
4. Flashing JetPack through the power board's USB 2.0 hub has not been tried; NVIDIA's tools are
   known to be picky about hubs.
