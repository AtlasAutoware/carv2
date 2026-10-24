# Printing the kit (P1S, PETG-CF)

The STLs in `out/stl` are not all in a printable orientation. On Sept 30 the bumper failed: its flange sat 20 mm
above the bed with nothing under it. An overhang audit of every STL found the same kind of problem in six more
parts. The fix is in the slicing, not the CAD: a few parts are turned upside down and the rest get tree supports.
Scripts live on the laptop in `~/slice_work` (`slice_carv2_fixed.sh`, `stl_flip.py`, `upload_fixed.sh`).

| part | problem in `out/stl` orientation | how to print it |
| --- | --- | --- |
| bumper | 38 x 80 mm flange floating 20 mm up | as is, tree supports from the plate, 5 mm brim |
| camera_arch | top bar floating 96 mm up (70 x 72 mm) | upside down (bar on the bed), supports under the foot pads |
| pack_box | printed floor-up (42 x 121 mm bridge at 70 mm) | upside down (floor on the bed, open end up), supports under the screw tabs |
| side_pod_left / _right | sloped walls, 1,900-2,100 mm2 of overhang | upside down, tree supports from the plate |
| wing_blade | 41 x 184 mm blade 7 mm above the bed | as is, supports under the blade |
| wing_strut_left / _right | 33 x 84 mm bar 3 mm above the bed | as is, supports under the bar |
| lidar_plinth | 28 x 38 mm pocket ceiling 4 mm up | as is, no supports (short bridge) |
| stack_canopy | only the 0.6 mm engraving | as is, no supports |
| deck pieces, splices, washers, fit coupons, cell holders, pack lid, camera cradles | fine | as is |

Support settings: tree(auto), build plate only, bridges up to 10 mm unsupported, 0.25 mm top/bottom gap
(PETG-CF), 5 mm outer brim on the supported plates.

Plates on the printer (`/carv2/`), all PETG-CF, 0.4 mm hardened nozzle:

| file | parts | time | filament |
| --- | --- | --- | --- |
| P1S_CarV2_Bumper_v2 | bumper (5 walls, 40 %) | 4 h 16 m | 92 g |
| P1S_CarV2_Arch_Struts | camera arch (flipped), 2 wing struts | 4 h 3 m | 89 g |
| P1S_CarV2_Plinth_Cradle_Canopy | lidar plinth, camera cradle (0 deg), stack canopy | 2 h 0 m | 57 g |
| P1S_CarV2_Side_Pods | both side pods (flipped), 3 walls 20 % | 5 h 38 m | 157 g |
| P1S_CarV2_Wing_Lid | wing blade, pack lid, 3 walls 20 % | 3 h 34 m | 81 g |
| P1S_CarV2_Pack_Box_v2 | pack box (flipped), 3 walls 30 % | 2 h 45 m | 74 g |

Unchanged from before: the three deck pieces, splices + washers, fit coupons, cell holders. The old
Mounts_Canopy, Bumper, Pods_Wing_Lid and Pack_Box files get renamed `OLD_DONT_PRINT_...` on the card by `upload_fixed.sh`.

## Rev B parts (Oct 24)

Rev B adds four printed parts and changes five (`NOTES_REVB.md` has the reasons). Every new STL in `out/stl` is
already in its print orientation, and none needs supports. All are PETG-CF on the 0.4 mm hardened nozzle.

| part | orientation in `out/stl` | supports | settings, notes |
| --- | --- | --- | --- |
| devkit_tray | as is: frame on the bed, bosses and the four canopy pillars up | none | 4 walls, 40 % gyroid (it is a frame and must not sag between the six standoffs). The pillars are 10 mm wide and 48 mm tall: print the tray alone or with low parts, 5 mm brim. The six countersinks print on top, which is fine. Regenerate it after measuring the carrier's holes (MEASURE_FIRST item 17) |
| esc_cradle | as is: base on the bed | none | 4 walls, 35 % gyroid. The zip-tie grooves under the base are 1.4 mm deep, so the base bridges 5.2 mm over each one; no support needed. Placeholder size until the FSESC case is measured (item 21) |
| bms_fence | as is: base on the bed, channel and uprights up | none | 4 walls, 35 % gyroid. The uprights are 60 mm tall and 12 mm wide; brim them. The two countersinks are on top |
| canopy_leg | as is: foot on the bed | none | 5 walls (the column is mostly walls), 5 mm brim; 84 mm tall and 12 mm across, so slow the last 40 mm down or print it with the tray |
| stack_canopy | top face down, as in rev A | none | new outline (132 x 129 mm) over the dev kit and its plugs; only the 0.6 mm engraving |
| side_pod_right | as rev A: upside down, tree supports from the plate | tree | the fan window moved to x -94..-54, the camera-plug slot and the tie slots are gone, and three windows (charge USB-C, debug USB-C, button) go through both walls. The window tops are 16 mm bridges; the tree supports from the plate already reach them |
| deck_rear, deck_mid, deck_front | top face down, as in rev A | none | new holes and openings (below). Reprint deck_mid in any case |

**Rev A deck pieces already printed?** `deck_mid` has to be reprinted: the new power-board insert at (-28, -64)
lands on the corner of a rev A heat-spreader vent. The other two can be converted by hand instead (car coordinates,
from `kit.py`):

- `deck_rear`: cut the phase and hall opening at x -112 to -101, y -70 to -46 (drill the corners, saw, file); drill
  4.0 mm at (-104, -8) for the ESC cradle's insert.
- `deck_front`: drill 4.0 mm at the two front power-board standoffs, (POWER_L - 36, -64) and (POWER_L - 36, 12)
  (114 at a 150 mm board, 94 at 130); extend the servo-lead slot at x 98.5 to 103.5 outboard from y -52 to y -67.

The rev A holes left in those two pieces (old drive-board inserts) are harmless.

Plates for rev B (estimates from the solid volumes, about 65 % as printed; slice before trusting the times):

| plate | parts | filament |
| --- | --- | --- |
| P1S_CarV2_RevB_Tray | devkit_tray, canopy_leg | about 35 g |
| P1S_CarV2_RevB_ESC_BMS | esc_cradle, bms_fence | about 26 g |
| P1S_CarV2_RevB_Canopy | stack_canopy | about 36 g |
| P1S_CarV2_RevB_Pod_R | side_pod_right (flipped, tree supports) | about 44 g + supports |
| P1S_CarV2_RevB_Deck | deck_mid (and deck_rear, deck_front unless converted) | about 109 g each |
