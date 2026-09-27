# Pictures for posting

All of these come out of the design files; none are photos.

| file | what it shows |
| --- | --- |
| `car_front_left.png`, `car_rear_right.png`, `car_top.png` | The printed kit with both boards in place: deck, side pods, bumper, wing, camera arch and lidar plinth. Rendered with VTK by `make_renders.py` from `mech/kit.py` and the two boards' KiCad 3D models. The Traxxas chassis is left out. |
| `car_exploded.png` | The same, with the drive board lifted 45 mm and the brain board 90 mm to show the stack. |
| `drive_iso.png`, `drive_top.png`, `drive_bottom.png` | The drive board as routed, rendered by KiCad. The four bulk capacitors, the 2 x 20 stack socket and the power stage (FETs on the underside) are the big parts. |
| `brain_iso.png`, `brain_top.png` | The brain board (Jetson carrier) as routed, rendered by KiCad. The Jetson module and the NVMe card plug in and are not shown. Many of the parts from Antmicro's design, the module socket among them, have no 3D model here and show as bare pads. |
| `drive_thermal_70A.png` | Simulated temperature of the drive board at 70 A peak phase current with the fan, 35 C air: about 58 C on the hottest FET (`sim/drive_thermal.py`). |
| `dclink_waveforms.png` | Simulated ripple current in the ESC's bus capacitors (`sim/dclink.py`). |
| `precharge.png` | Simulated switch-on of the motor bus through the precharge resistors (`sim/precharge.py`). |
| `poe_boost.png` | Simulated 52 V boost that powers the camera over Ethernet (`sim/poe_boost.py`). |

Stand-ins: in the car pictures the lidar, the camera, the Jetson module with its heatsink, the NVMe
card, the RJ45 jacks and the stacking header are simple shapes, not models of the real parts. In the
drive board pictures a few parts have no 3D model in KiCad and show as bare pads.

To make them again: `boards/tools/run_kicad.sh "" glb-drive glb-brain render-drive render-brain`,
then `python3 share/make_renders.py` (VTK), and `sim/run_all.sh` for the plots.
