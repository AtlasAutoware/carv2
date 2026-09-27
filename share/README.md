# Pictures for posting

All of these come out of the design files; none are photos.

| file | what it shows |
| --- | --- |
| `car_front_left.png`, `car_rear_right.png`, `car_side.png`, `car_top.png` | The whole car: the printed kit with the stack canopy, both boards, the pack, every cable and plug, on a stand-in Slash 4x4. Rendered with Blender Cycles by `render_car.py` from the scene `car_scene.py` builds out of `mech/kit.py`, `mech/extras.py` and the two boards' KiCad 3D models. |
| `car_exploded.png` | The same, with the drive board lifted 55 mm, the brain board 115 mm and the canopy 185 mm to show the stack. The cables are hidden in this one, and the antennas are folded back. |
| `drive_iso.png`, `drive_top.png`, `drive_bottom.png` | The drive board as routed, rendered by KiCad. The four bulk capacitors, the 2 x 20 stack socket and the power stage (FETs on the underside) are the big parts. |
| `brain_iso.png`, `brain_top.png` | The brain board (Jetson carrier) as routed, rendered by KiCad. The Jetson module and the NVMe card plug in and are not shown. Many of the parts from Antmicro's design, the module socket among them, have no 3D model here and show as bare pads. |
| `drive_thermal_70A.png` | Simulated temperature of the drive board at 70 A peak phase current with the fan, 35 C air: about 58 C on the hottest FET (`sim/drive_thermal.py`). |
| `dclink_waveforms.png` | Simulated ripple current in the ESC's bus capacitors (`sim/dclink.py`). |
| `precharge.png` | Simulated switch-on of the motor bus through the precharge resistors (`sim/precharge.py`). |
| `poe_boost.png` | Simulated 52 V boost that powers the camera over Ethernet (`sim/poe_boost.py`). |

Stand-ins: in the car pictures the chassis is drawn from `kit.py`'s keep-out numbers (all estimates), with
suspension, wheels and tread drawn to look plausible, not measured. The lidar, the camera and lens, the Jetson
module with the dev kit's heatsink and fan, the NVMe and Wi-Fi cards, the RJ45 jacks and plugs, the stacking
header, the 40 mm fan and the antennas are simple shapes sized from their datasheets or from kit.py's envelopes, not models of
the real parts. In the drive board pictures a few parts have no 3D model in KiCad and show as bare pads.

To make them again:

1. `boards/tools/run_kicad.sh glb-drive glb-brain render-drive render-brain` writes the board models and renders
   to `boards/*/out/render/`; copy the board PNGs you want here.
2. `python3 share/car_scene.py` writes the scene (`share/scene/`, not in git).
3. Render with `python3 share/render_car.py -- car_front_left car_rear_right car_side car_top car_exploded`, using
   Blender 4.2's `bpy` module (Python 3.11). About 12 minutes a view at 2700 x 1800 and 80 samples on two CPU
   cores; `--quick` gives a 900 x 600 preview in under a minute.
4. `sim/run_all.sh` writes the plots to `sim/out/`.

`make_renders.py` is the older VTK version, with no chassis, canopy or cables. It writes the same car file names.
