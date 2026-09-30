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
