# Rev B printed kit: notes (24 October 2026)

What changed in `kit.py`, `extras.py` and `../boards/board_outlines.py` for rev B, the calls made along the way, what
still has to be measured, and what to print. The design inputs are the Phase 2 brief (ATLAS-PWR-1 board facts and
the decisions of 24 October) and the Phase 1 mechanical plan (dev-kit carrier, section 8). Coordinates are car mm:
+x forward, +y left, deck top at z 0.

## The rev B layout in one paragraph

The power board (car x -32 to -32 + `POWER_L`, y -68 to 16) sits on six 7 mm deck standoffs. A printed tray stands on
the same six holes with M3 x 25 standoffs and carries the NVIDIA dev-kit carrier (car x -12 to 88, y -63 to 16) on
four bosses, I/O edge toward the pack. The plugs on that edge (DC, RJ45, two USB-A, USB-C) sit over the pack lid. A
canopy covers the dev kit and the plugs, on two pillars printed on the tray, two M3 standoff stacks over the
board's front standoffs and one leg in zone B. A 3 mm acrylic shield hangs under the tray over the FET heatsink bar,
which is live at pack voltage. The FSESC sits
in a cradle in the ESC bay beside the motor (x -113 to -35), the right pod's fan blows across it, and the motor leads
drop through a new deck opening at its motor end. The JBD BMS stands on its long edge in a holder on the pack lid's
outboard edge, with the MIDI fuse holder on the lid beside the dev kit's plugs. The lidar's USB-Ethernet dongle is
zip-tied behind the camera arch's left leg.

## Interference results

| run | printed and bought parts (`kit.py`) | new parts, plugs (`extras.py`) | cables (31 runs) | cable against cable | lidar plane |
| --- | --- | --- | --- | --- | --- |
| `POWER_L` 130 (the default, agent D's layout) | 0 | 0 | 0 | 0 | all inside the rear blind sector |
| `POWER_L` 130, `SHEET_PARTS=all` (laser-cut tray, BMS holder, canopy box, splices) | 0 | 0 | 0 | 0 | all inside |
| `POWER_L` 150 | 4 overlaps, all the lidar's M12 plug envelope against the board's front: the PCB, its height-map blocks and the front-left 25 mm standoff | 0 | the lidar Ethernet cable runs through the board's front-left corner | 0 | all inside |

The lidar's two M12 plugs end at x 114.6 (an estimate: 45 mm straight plugs behind the swivel unit, MEASURE_FIRST item
12). A 150 mm board reaches x 118, so its front 3.4 mm is inside them. Agent D took the recommendation and laid the
board out at 130 mm, which is now the default. At 130 mm the plug ends are 16.6 mm ahead of the board, the lidar
power cable goes straight into a front-edge terminal, the servo lead goes straight down the deck slot just ahead of
the board, and the board needs no servo notch. Everything that is parametric follows `POWER_L`: the tray, the
inserts, the canopy posts, the outline and keep-outs in `boards/outlines.json`.

Other numbers from `out/kit_report.json` and `out/extras_report.json`:

- Stack: board top z 8.6; tray 33.6 to 36.6; carrier 43.6 to 45.17; fan top 77.17; canopy posts 48 mm above the
  tray (top z 84.6); canopy underside 85.6 (8.4 mm over the fan), top 88.0. The carrier's 6 mm underside allowance
  clears the tray by 1.0 mm; the tray clears the board's 23 mm parts by 2.0 mm.
- FET shield: z 30.6 to 33.6, 2.0 mm over the bar's live metal (20 mm above the board, an estimate).
- Canopy: 24.9 mm over the dev kit's plugs, 22.9 mm over the ribbon's IDC socket, 4.0 mm inboard of the BMS.
- ESC: case (placeholder) x -109.5 to -38.5, y -55.5 to -12.5, z 3 to 25.7: 20.5 mm of air to the pod wall where the
  fan blows in, 9.3 mm under the 35 mm bay limit.
- The right pod's rear bolt at (-88, -72.5) sits inboard of the new fan window, on the flange. Its head (top z 4.65)
  covers the window's lowest 2.65 mm over 6 mm of width; harmless, so the bolt stays.
- The charge USB-C plug passes the pod window with 1.75 mm a side and 4 mm above and below.

## Judgment calls

1. **BMS on its edge on the pack lid.** The JBD is 160 x 105 x 10 mm. Lying flat on the 138 x 51 mm lid it would
   reach y 122, past the left pod and the deck edge (y 88.75). Inside a taller pack box it cannot go either: the box
   is 121 x 41 mm inside, and it cannot grow down at all because it already sits 2.8 mm above the bay floor
   (`pack_box_bms_check` in the kit report). So it stands on its long edge in a holder on the lid's outboard edge
   (x -80 to 80, y 61 to 71, z 9 to 114), clear of the left pod by 0.6 mm at the uprights and inside the lidar's
   blind sector (151 degrees). It keeps the battery assembly in one place and the 10 AWG leads short (88 and 96 mm).
   The cost is a 105 mm tall plate on the left side of the car. I also looked at a flat shelf over the ESC bay at the
   rear (x -199 to -39, z about 37); it is lower but needs longer 10 AWG leads, covers the FSESC and the rear body
   clips, and needs four tall legs. `BMS_MOUNT=flat` keeps a flat tray on the lid for a smaller BMS that
   fits the lid; with the 160 x 105 board the checks show it hitting the left pod.
2. **Phase opening moved.** Section 8 of the Phase 1 plan put it at x -94 to -82, but that is over the rear-right
   splice plate (x -95 to -65) and around the joint bolt at (-90, -60). It is now at x -112 to -101, y -70 to -46
   (`PHASE_OPENING`), between the rear post slot and the cross rib, right under the FSESC's motor end. The leads
   drop in three staggered columns so none crosses another.
3. **ESC cradle on two new inserts and two shared joint bolts**, not four inserts. The outboard tabs sit on the rear
   joint's bolts at (-90, -60) and (-70, -60) (M3 x 16 through cradle, deck and splice plate), because there is no
   clean spot for an insert on that side between the opening, the joint and the splice plate.
4. **Servo slot extended** outboard from y -52 to y -67, so it lines up with the board's servo notch (car x 98.5 to
   103.5 on the board's Y = 0 edge). Without that the notch led nowhere. At 130 mm or less the notch is not needed.
5. **Tray bosses 7 mm tall** (the 6 mm underside allowance plus 1 mm). The tray adds 3 mm and the bosses 7 mm over
   the Phase 1 plan's carrier height, so the canopy top is at 87.6 instead of about 77.6. It stays in the blind
   sector. If the measured underside is the drawing's 4.3 mm, set `DEVKIT_BOTTOM_H=4.3 DEVKIT_BOSS_H=5.3`.
6. **Height map tightened in three places**, for the tray's rails and arms: the strip Y 0 to 5 under the tray, and the
   9 mm bands along both long edges (Y 0 to 9 and Y 75 to 84) in the rear and front strips, are 23 mm, not 35 mm.
   The 35 mm zones are X 0 to 20 and X over 120 at Y 9 to 75. **Agent D must use this map** (`boards/outlines.json`,
   `power.height_zones_local`).
7. **Countersunk tray screws.** Two of the six tray standoffs are under the carrier (the X 75 pair is at y 12, under
   the I/O edge). M3 x 8 countersunk heads sit flush, so the 1 mm under the carrier is enough.
8. **The canopy's supports.** Two pillars printed on the tray's rear arms (x -18, 10 mm clear of the rear standoff
   screws), and one printed leg in zone B (92, 44) whose foot takes the front joint's two left bolts (no new
   inserts). At the front, a 130 mm board's front standoffs (x 94) sit 2 mm from where front pillars would go (x 96),
   so a printed pillar would cover their screw heads. There the front posts are M3 hex standoff stacks (40 + 8 mm,
   male-female) screwed straight into the front tray standoffs, clamping the tray in place of the countersunk screws
   (`canopy_posts()`, kind 'coaxial'). On a board 9 mm or more away from that (120 mm, 150 mm) the front posts are
   printed pillars again. Every post ends 48 mm above the tray, so bought and printed posts mix. Zone C is behind the
   canopy, so it has no leg.
9. **Lidar dongle behind the arch's left leg**, not on the deck in zone B. Zone B has no room for a 50 mm dongle
   whose RJ45 plug and boot need another 32 mm (the arch feet, the BMS holder's front end, the pack lid). Upright
   behind the leg, jack down, the lidar cable is 41 mm and the dongle's own 180 mm lead reaches the dev kit with
   130 mm routed.
10. **Wi-Fi antennas on the canopy's rear edge.** The pigtails cannot leave the carrier over its rear or front edge,
    because the power board's 35 mm strips reach up to the carrier's underside there. They come out under the I/O
    edge behind the unused DisplayPort and run back: 104 and 161 mm. Order 20 cm pigtails; the 15 cm ones on the BOM
    do not reach.
11. **FSESC USB goes to the board's hub (Phase 2 decision 4)**, not to a dev-kit USB-A as one line of my task text said.
    PHASE2 governs; the FSESC talks to the Jetson over UART1 through the ribbon. The lengths differ by a few cm.
12. **Debug USB-C as a panel-mount socket in the right pod's window**, with a pigtail to the hub. A THT receptacle
    at the board edge also works through the same window (then no cable).
13. **Button window in the rear strip** (car x -20). A 6 mm tactile switch at the board edge is 26 mm in from the
    pod's outer face; fit a 12 mm panel-mount momentary in the window on the board's remote-button header, or a
    printed plunger.
14. **ESC battery leads loop round.** The FSESC's front end is only 6.5 mm from the board's rear edge, so the battery
    leads turn inboard at once and come back into the XT60 from behind (62 and 85 mm). Better for the layout: put the
    XT60PW at the inboard end of the rear edge (Y 66 or more, as modelled) or land the leads on wire pads.
15. **Fan lead.** PHASE2 puts the fan header on the board's front edge; the fan is now at the rear (x -94 to -54), so
    its lead is 230 to 250 mm. A fan header on the rear edge would make it about 60 mm. A question for agent D.
16. **Placeholder connector positions on the board** (`extras.POWER_CONN`): ESC XT60 at the rear edge Y 66, FSESC
    COMM at Y 14; XT90 at the pack edge X 8, BMS UART at X 22, DC pads at X 28, Pico USB at X 102; hub at (70, 40);
    box header for the ribbon centred at (40, 8.5) near the right edge, behind the X 75 standoff; 1 x 12 header at
    (92, 13.5); front edge: servo Y 14, fan Y 24, camera power Y 34, lidar power Y 58 (straight in line with the
    lidar's power plug at car y -10). Pod windows (`POD_WINDOWS`): charge USB-C at car x 68, debug USB-C at 88, button
    at -20, all z 10 to 25. When D reports the real positions, edit those two dicts and rerun.
17. **The JBD's leads** are assumed to leave its rear end (x -80). The B+ path is pack + up the lid's front slot, the
    MIDI fuse on the lid, then the XT90-S; the B- path is pack - up the rear slot to the BMS, P- to the XT90-S.
18. **Acrylic FET shield.** D's layout puts the 40 x 15 x 3 mm heatsink bar (live at BAT+, the three FET tabs are its
    drains) at board X 10.5 to 50.5, Y 63 to 66, under the tray's CF rear rails, 5 mm below them. A 3 mm cast acrylic
    plate (34 x 23 mm, board X 20 to 54, Y 49 to 72) hangs under the tray there on two nylon countersunk M3 screws,
    2 mm above the bar. Under its footprint the height map drops to 21 mm (`low_shield` in `boards/outlines.json`);
    D's tallest parts there are the 21 mm 680 uF caps and the FET tabs (about 20 mm). Its two nylon nuts need parts at
    18 mm or less under the two screw points. Acrylic softens at about 100 C; the supervisor cuts the main switch at
    a FET temperature of 90 C.
19. **Printed canopy corner radius 12 to 6 mm.** The 12 mm radius gave an inner lip fillet that overlapped the
    right-hand posts by 6.5 mm3 each. The checks had not reported it because the canopy-to-tray contact was on a
    "touching by design" list; face contacts never count, so that list entry is gone and the checks see it now.
20. **Laser-cut versions** of the tray, the BMS holder, the canopy (as a slot-and-tab box) and the splice plates, plus
    the shield, from the same parameters (PRINTING.md, "Laser-cut parts"). They are better than CF prints wherever a
    part must insulate. The laser BMS holder moves the BMS 2.5 mm inboard (its base needs closed slots and the left
    pod is 1.7 mm away), and the laser canopy is 4 mm bigger a side so its skirts, inset 2.5 mm for closed slots, stay
    1.5 mm off every post.

## Parameters that must be measured

| parameter (`kit.py` unless named) | now | measure (MEASURE_FIRST) |
| --- | --- | --- |
| `DEVKIT_HOLES`, `DEVKIT_PILOT_D` | placeholder 86 x 58 mm rectangle centred on the carrier: (7, 10.5), (93, 10.5), (7, 68.5), (93, 68.5); M2.5 | item 17, before printing the tray |
| `JETSON_SINK_H`, `JETSON_XY` | 32 mm; X 10 to 88, Y 8 to 56 | item 18 |
| `DEVKIT_BOTTOM_H`, `DEVKIT_BOSS_H` | 6.0, 7.0 | item 19 |
| `DEVKIT_J12`, `DEVKIT_J14`, `DEVKIT_IO` | estimates | item 20 |
| `ESC_CASE`, `ESC_C`, the FSESC port positions in `extras.cable_defs()` | 71 x 43 x 22.7 mm placeholder | item 21, before printing the cradle |
| the M8 plug in `triton()` | 16 mm out, cable up | item 23 |
| `USB_ETH` | 50 x 22 x 15 mm | item 24 |
| `BMS`, its lead positions | 160 x 105 x 10 mm, leads at the rear end | item 25, before printing the BMS holder |
| `MIDI_FUSE_XY`, `MIDI_FUSE_H` | 60 x 30 x 26 mm | item 26 |
| `tim561()` plug lengths | 45 mm | item 12: it decides how long the power board can be |
| `POWER_L` and `extras.POWER_CONN` | 130 mm (D's layout); connector placeholders | from agent D's layout |
| `SHEET_T` | 3.0 mm | item 27: measure every laser sheet before cutting the tab-and-slot parts |
| `FET_BAR` height | 20 mm of live metal above the board | item 28: the shield hangs 2 mm above it |

**Where the dev-kit hole default comes from.** NVIDIA's carrier board specification (Fig. 4-1, read through the
uelectronics.com mirror) gives the outline (100.00 x 79.00 mm, PCB 1.57 mm, 16.70 mm top and 4.30 mm bottom maximum)
but no hole positions. NVIDIA's forum points to the carrier design files and the dev-kit STEP model on the Jetson
Download Center, which need a developer login and could not be fetched here; no other page I could read gives them
either. The default is the 86 x 58 mm pattern I recall for the older Jetson Nano and Xavier NX dev-kit carriers,
centred on the board. It is unverified and may well be wrong: measure the owned carrier with calipers before the
tray is printed. The tray regenerates from the four numbers. The power board no longer depends on them.

## Parts to print for rev B

Solid PETG-CF masses from the model at the 130 mm board; as printed (4 walls, 35-40 % gyroid) expect about 65 %.

| part | why | solid g | printed g (about) |
| --- | --- | ---: | ---: |
| `devkit_tray` | new (or cut `laser_devkit_tray`) | 29 | 19 |
| `esc_cradle` | new (placeholder size until the FSESC case is measured) | 10 | 7 |
| `bms_fence` | new (or cut the three `laser_bms_*`) | 29 | 19 |
| `canopy_leg` | new | 13 | 8 |
| `stack_canopy` | new outline over the dev kit (or cut the `laser_canopy_*` box) | 54 | 35 |
| `side_pod_right` | fan window moved, plug slot gone, three new windows | 68 | 44 + supports |
| `deck_mid` | new insert positions; a rev A print cannot be converted | 167 | 109 |
| `deck_rear` | new phase opening, one insert; or convert a rev A print by hand | 180 | 117 |
| `deck_front` | two inserts, servo slot extended; or convert a rev A print | 171 | 111 |
| **total** | with `deck_rear` and `deck_front` converted | **370** | **about 240** |
| **total** | with all three deck pieces reprinted | **721** | **about 470** |

Unchanged from rev A: the splices (or cut them), the fit coupons (the rear coupon now includes part of the new phase
opening; an already printed one is still a valid fit test), the plinth, the bumper, the arch and cradles, the left
pod, the wing, the pack box, the lid and the cell holders, the washers and the bench stand.

## Parts to cut for rev B

All 3 mm, kerf-neutral DXF and SVG in `out/laser/` (sizes in mm, from `kit_report.json` and `extras_report.json`,
key `laser`). Everything but the shield is optional: it replaces a printed part.

| file | material | size | qty |
| --- | --- | --- | ---: |
| `laser_fet_shield` | cast acrylic only | 34 x 23 | 1 |
| `laser_devkit_tray` | birch plywood (or cast acrylic) | 130 x 84 | 1 |
| `laser_spacer_disc` | acrylic or plywood (option to the printed spacers) | 8 x 8 | 12 |
| `laser_bms_base`, `laser_bms_wall_in`, `laser_bms_wall_out` | birch plywood or cast acrylic | 164 x 22, 164 x 15, 164 x 63 | 1 each |
| `laser_canopy_top` | birch plywood or clear cast acrylic | 136 x 133 | 1 |
| `laser_canopy_skirt_left`, `_right` | same | 131 x 13 | 1 each |
| `laser_canopy_skirt_rear`, `_front` | same | 128 x 13 | 1 each |
| `laser_splice` | birch plywood (not acrylic, not MDF) | 30 x 72 | 4 |

## Bought parts the kit now needs

- 6 x M3 x 25 mm male-female standoffs (new), 4 x M3 x 8 countersunk, 2 x M3 x 40 and 2 x M3 x 8 male-female
  standoffs (the front canopy posts), 4 x M2.5 x 10 thread-forming screws for plastic, 2 x M3 x 10 countersunk (BMS
  holder), 4 x M3 x 16 (shared joint bolts), 5 x M3 x 8 button heads (canopy), 2 x M3 x 10 nylon countersunk
  screws and nylon nuts (shield), about 34 M3 inserts in all (rev A: about 30), zip ties.
- With the laser-cut tray: 4 x M3 x 40 female-female + 4 x M3 x 8 male-female standoffs for all four posts, and
  M3 x 6 button heads from under the sheet at the two rear ones.
- 20 cm MHF4 to RP-SMA pigtails instead of 15 cm.
- No aluminium heat spreader any more.

## Open questions

- The power board's connector positions: D's 130 mm layout moved the fan header to the rear edge and put the ESC
  and pack leads on wire pads, so `extras.POWER_CONN` (my placeholders) should be updated from
  `boards/power/layout.py` and the cables rerun. The fan lead then drops from 230 mm to about 60.
- Is the 21 mm limit under the acrylic shield fine with D's FET bar as built (MEASURE_FIRST 28)?
- With wire pads at the rear edge (D's layout), do the ESC's battery leads still need the U-loop (the case's front
  end is 6.5 mm from the board)?
- The carrier's holes, heights and header positions; the FSESC case and its ports; the BMS's terminals; the fuse
  holder; the dongle (MEASURE_FIRST 17 to 26).
- Which sides the dev kit's heatsink fins exhaust to. The canopy is open below its 4 mm lip on every side, so the
  air can leave anywhere, but the grille sits over the assumed fan position.
- Is a 105 mm BMS plate on the left side acceptable to the team, or is a smaller BMS (one that fits the lid flat)
  worth buying?

## Not changed here (other files that still describe rev A)

- `share/car_scene.py` imports `kit.DRIVE_HOLES`, `kit.BRAIN_HOLES`, `P['DRIVE_Z']`, `P['BRAIN']` and the rev A
  `extras` names (`JETSON_BOX` is kept, `CAM_JACK`, `Z_BRAIN_TOP` and the others are gone), so it no longer runs. It
  needs the same rev B rewrite before the whole-car renders are redone.
- `docs/COMPLETE_CAR.md` describes the rev A canopy and plug slot.
- `boards/stack/stack.py` and `boards/tools/check_stack.py` belong to the retired stack connector.
- The rev A placement drawings and DXFs in `boards/drive/` and `boards/brain/` are left as they were.
