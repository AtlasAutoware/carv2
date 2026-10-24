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
| P1S_CarV2_RevB_Tray | devkit_tray, canopy_leg | about 27 g |
| P1S_CarV2_RevB_ESC_BMS | esc_cradle, bms_fence | about 26 g |
| P1S_CarV2_RevB_Canopy | stack_canopy | about 36 g |
| P1S_CarV2_RevB_Pod_R | side_pod_right (flipped, tree supports) | about 44 g + supports |
| P1S_CarV2_RevB_Deck | deck_mid (and deck_rear, deck_front unless converted) | about 109 g each |

## Laser-cut parts

The school's CO2 laser (acrylic, plywood, MDF up to about 6 mm, no metal) can cut flat versions of five rev B parts.
`kit.py` and `extras.py` write each one as a 2D profile to `out/laser/`: a DXF (mm, layer CUT for the cut lines,
layer ENGRAVE for text) and an SVG (red hairline = cut, black = engrave). The printed versions stay as they are; both
are kept in step from the same parameters.

**Material.** Use 3 mm laser-grade birch plywood for parts that take bolts or knocks, and 3 mm cast acrylic (PMMA)
where it must insulate or should be clear. Do not laser PVC or vinyl (chlorine gas), polycarbonate (it burns and
yellows instead of cutting), ABS, or anything carbon-filled. MDF cuts cleanly but crumbles at bolt holes and swells
when wet, so keep it for jigs. Every sheet part here is an insulator, which is the main reason to prefer them: CF
filament conducts.

**Sizes are kerf-neutral.** The files are drawn at nominal size; do not add a kerf offset in the laser software. The
beam's kerf (about 0.1 to 0.2 mm) makes holes and slots that much bigger and outlines and tabs that much smaller,
and the tab and slot sizes below already allow for it. M3 holes are drawn at 3.2 mm (about 3.35 mm after cutting).
The laser cannot countersink: where a countersunk screw goes (tray standoffs, shield screws, BMS lid screws),
countersink the 3.2 mm hole by hand with a 90 degree bit to 6.7 mm.

**Tab and slot rule.** Tabs are `TAB_L` (10 mm) long and one sheet thick, so they finish flush. Slots are drawn
`SHEET_T + 0.1` wide and `TAB_L + 0.2` long and are always closed (2.5 mm or more of sheet outside them). There are at
least two tabs per edge, at most 40 mm apart, the end ones 8 mm in from the corners. Corners are a three-finger box
joint (the long side keeps the top and bottom thirds). With the kerf this gives about 0.2 to 0.3 mm of play: a push
fit in acrylic (acrylic cement) and a glue fit in plywood (PVA). **Measure the actual sheet with calipers and set
`SHEET_T` before cutting** (MEASURE_FIRST item 27): "3 mm" stock runs 2.7 to 3.2 mm, and a slot drawn for the wrong
thickness either rattles or will not close.

| file (`out/laser/`) | material | size (mm) | qty | replaces | notes |
| --- | --- | --- | ---: | --- | --- |
| `laser_fet_shield` | 3 mm cast acrylic only | 34 x 23 | 1 | new (no printed version) | hangs under the dev-kit tray over the FET heatsink bar, which is live at BAT+; 2 x M3 x 10 nylon countersunk screws from the tray top, nylon nuts under it. Engraved "BAT+ BELOW" |
| `laser_devkit_tray` | 3 mm birch plywood (or cast acrylic) | 130 x 84 | 1 | `devkit_tray` | the same frame, flat. The carrier stands on four 7 mm `devkit_spacers` (printed, glued on) or on three stacked `laser_spacer_disc` per hole (9 mm, set `DEVKIT_BOSS_H=9`). All four canopy posts become M3 hex standoffs, 40 + 8 mm (on the printed tray only the front two are) |
| `laser_spacer_disc` | 3 mm acrylic or plywood | 8 x 8 | 12 | the tray's bosses (option) | 2.7 mm hole for M2.5 |
| `laser_bms_base`, `laser_bms_wall_in`, `laser_bms_wall_out` | 3 mm birch plywood or cast acrylic | 164 x 22, 164 x 15, 164 x 63 | 1 each | `bms_fence` | walls tab into the base; the outboard wall's two ears are the uprights (zip-tie notches). The holder moves the BMS 2.5 mm inboard so the base's slots stay closed |
| `laser_canopy_top`, `laser_canopy_skirt_left`, `_right`, `_rear`, `_front` | 3 mm birch plywood (tougher in a roll) or clear cast acrylic | 136 x 133; 131 x 13 (x2); 128 x 13 (x2) | 1 each | `stack_canopy` | hex grille, RP-SMA D-holes and five post holes in the top, "ATLAS" engraved; skirts 10 mm deep, tabbed into closed slots, box-jointed corners. 4 mm bigger a side than the printed canopy |
| `laser_splice` | 3 mm birch plywood (not acrylic: it cracks at bolt holes under vibration) | 30 x 72 | 4 | the four `splice_*` plates | one profile: the left and right plates are the same part turned over |

All of it nests on one 300 x 300 mm sheet of 3 mm plywood plus a 100 x 50 mm offcut of acrylic for the shield (and
a 300 x 200 mm acrylic sheet if the canopy is to be clear).

**Better cut than printed, and why:**

- **The FET shield** has to be acrylic: it is there because the printed tray is CF-filled and conducts, and the bar
  under it is at pack voltage. Acrylic does not char and softens at about 100 C; the supervisor cuts the main
  switch at a FET temperature of 90 C, and the shield hangs 2 mm clear of the bar.
- **The splice plates**: a minute of cutting instead of four prints, flat and stiff, identical every time.
- **The BMS holder**: the BMS's bottom edge (its B- side and balance pads) stands in it, so an insulating holder is
  safer than a CF one. Three flat parts, glued.
- **The canopy**: insulating, transparent to the Wi-Fi antennas that sit on it (CF may detune them), tougher in
  plywood, and quicker than printing it.
- **The dev-kit tray**: insulating where the printed tray is not. It sits 5 mm over the BAT+ bar and 1 mm under the
  carrier's underside parts (NVMe, screws), so a plywood or acrylic tray takes the CF shorting risk away entirely (keep the
  acrylic shield anyway: it also stops a cable or a dropped screw from bridging). The cost is bought standoffs
  for the canopy posts and four small spacers.

**Stays printed, and why:** the deck pieces (5 mm deck with 10 mm ribs and tower saddles), the bumper, the camera
arch and cradles (tilted tops), the lidar plinth (pocket and counterbores), both side pods (curved and hollow), the
wing parts, the pack box (a deep box), the cell holders (cell pockets), the pack lid (pressure ribs underneath),
the ESC cradle (small 3D locators and under-base strap grooves, and its size is a placeholder until the FSESC case
is measured), the canopy leg (an 85 mm column), the tray spacers (or use the discs) and the bench stand.

**Checking the sheet versions.** `SHEET_PARTS=all python3 kit.py` and `SHEET_PARTS=all python3 extras.py` (or a comma
list of `tray,bms,canopy,splices`) put the sheet parts into the model in place of the printed ones and run every
interference and cable check against them. The shield is always in the model (`FET_SHIELD=0` removes it).
