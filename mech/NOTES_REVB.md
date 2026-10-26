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
outboard edge, with the MIDI fuse holder on the lid beside the dev kit's plugs and the mated XT90 pair (the board's
pigtail in the pack's XT90-S) lying on the lid. The lidar's USB-Ethernet dongle is zip-tied behind the camera arch's
left leg and the camera's 12 V regulator behind its right leg. The charge modules (PD trigger and CC/CV buck) live
in the right pod. The power board's connectors are at agent D's final positions (`boards/power/HANDOFF_E.md`).

## Interference results

| run | printed and bought parts (`kit.py`) | new parts, plugs (`extras.py`) | cables (36 runs) | cable against cable | lidar plane |
| --- | --- | --- | --- | --- | --- |
| `POWER_L` 130 (the default, agent D's layout) | 0 | 0 | 0 | 0 | all inside the rear blind sector |
| `POWER_L` 130, `SHEET_PARTS=all` (laser-cut tray, BMS holder, canopy box, splices) | 0 | 0 | 0 | 0 | all inside |
| `POWER_L` 150 (run before D's connector positions; not rerun, D's layout is 130 mm) | 4 overlaps, all the lidar's M12 plug envelope against the board's front: the PCB, its height-map blocks and the front-left 25 mm standoff | 0 | the lidar Ethernet cable runs through the board's front-left corner | 0 | all inside |

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
- Right pod windows (`clearances` in the extras report): the charge and laptop USB-C plugs pass their windows with
  1.75 mm a side and 1.5 mm above and below; the J601 plug head has 0.8 mm a side and 0.85 mm above and below in
  its inner-wall window; the CC/CV module has 1.0 mm all round in its window and stands 0.8 mm into the inner wall's
  thickness (it is 14 mm deep, the pod inside 13.2 mm); the PD trigger board reaches 4.6 mm past the inner wall into
  the gap over the board edge.

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
11. **FSESC USB goes to the board's hub (Phase 2 decision 4; D's J602, hub port 3)**, not to a dev-kit USB-A as one line of my task text said.
    PHASE2 governs; the FSESC talks to the Jetson over UART1 through the ribbon. The lengths differ by a few cm.
12. **Laptop USB-C straight into the hub.** D put the hub module's USB-C at the board's pod edge (car x 56.5, centre
    about z 22.8), so the laptop's own cable plugs in through both pod walls (window x 48.5 to 64.5, z 17.8 to
    27.8). The panel-mount socket and its pigtail are gone.
13. **Button window at D's SW401** (right-angle, plunger tip at the board edge, car x 80.75, z about 12). Its plunger
    is 26 mm in from the pod's outer face, so it is pressed with a rod (a 3 mm hex key) through both walls; the
    window (x 76.2 to 90, z 8 to 17) reaches on to the status LEDs D701 / D702 at x 87.75 so they show through it.
    The remote-button header J1002 on the front edge still takes a panel button if the team prefers one.
14. **ESC battery leads on D's wire pads** (board X 5, Y 42 and 54): straight from the FSESC's front end down onto
    the pads, 19 and 24 mm routed. No XT60 and no U-loop; the battery-lead exits on the FSESC are still estimates.
15. **Fan lead.** D moved the fan header to the rear edge (J1003): the lead is now 88 mm (it was 230 mm to the front
    edge).
16. **Connector positions from D** (`extras.POWER_CONN`, from HANDOFF_E's table): the pad-group centres and the facing
    edge are D's; the height of each plug above the board (header plus mating plug, for example 11 mm for the fan
    header, 18 mm for the box header with its IDC plug, 17 mm for the servo plug) is an estimate. The front-edge
    entries keep their distance from the front edge if `POWER_L` changes; D's layout is 130 mm.
17. **The JBD's leads** are assumed to leave its rear end (x -80). The B+ path is pack + up the lid's front slot, the
    MIDI fuse on the lid, then the pack's XT90-S; the B- path is pack - up the rear slot to the BMS, P- to the XT90-S.
    D replaced the board-mount XT90 with BAT+ / BAT- pads and a 10 AWG pigtail to an XT90 male. The mated pair
    (22 x 12 x 46 mm, an estimate) lies on the lid along x at car x -60 to -14, y 30 to 52: the board pigtails
    (58 and 56 mm) come over the pack edge into its +x end, the fuse lead (106 mm) and the BMS P- (68 mm) into its -x
    end. Polarity in the model: + on the pair's north side.
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
21. **J601 with a right-angle USB-A plug.** J601 (Wurth 614004134726) stands on its edge at the pod edge (car x 70.8),
    its face 0.5 mm inside the board edge. A straight plug and its strain relief need about 40 mm (D's estimate); the
    pod's outer face is 26 mm out, so a straight plug would stand 14 mm out of the side of the car. The model takes a
    right-angle plug whose cable leaves its narrow side, which on an edge-standing receptacle is upward (on a normal
    receptacle that is a "left" or "right" angle plug, not "up" or "down"): head 9 x 12 x 18 mm beyond the face (an
    estimate). The head's last 3.5 mm pass through a window in the inner wall (x 65.5 to 77, z 6 to 26, which merges
    with the button window), and the cable rises in the 8 mm gap and runs over the carrier's front strip to the dev
    kit's USB-C: 165 mm, so a 0.3 m cable. The plug goes in before the right pod is fitted. J601's height is not in
    the KiCad footprint; `J601_H` 14.5 mm is the shell's width plus a standoff (MEASURE_FIRST 29).
22. **Charge modules in the right pod**, at a charge window that no longer has to line up with the board. The PD
    trigger (Adafruit 5807, 24.5 x 20.2 x 4.9 mm from adafruit.com) lies flat with its USB-C against the outer wall's
    charge window at car x 19 and passes through a slot in the inner wall, so its wire holes end up in the gap next to
    the board edge (50 mm of wire to its pads). The CC/CV module stands on its long edge behind the fan's forward
    just forward of the fan (car x -50 to 1), its PCB on the outer wall and its parts facing inboard. At 51 x 26.3 x 14 mm (one vendor's
    listing) it is 0.8 mm deeper than the pod inside, so its parts stand into a window in the inner wall (x -51 to 2,
    z 5 to 33.3), which also lets its heat out into the gap and its wires straight through to the board (36 and
    60 mm). Which edge of the trigger the USB-C is on, and the module actually bought, are MEASURE_FIRST 30.
23. **Camera regulator on the arch.** D's notes put the Pololu S18V20F12 (43 x 21 x 10 mm, pololu.com) "on the
    tray", but the tray is a frame of rails with no free surface outside the carrier. It stands upright against the
    rear face of the camera arch's right leg instead (x 126 to 136, y -36 to -15, z 40 to 83), the mirror image of the
    lidar dongle: 53 mm of 22 AWG pair from the MOD402 pads, 89 mm of M8 lead from the camera. If the team wants it on
    the tray, it needs a small bracket there.
24. **Leads that got longer** with D's positions: the dev-kit DC lead (40 to 103 mm: the DEV pads are now under the
    carrier's middle, not under the DC jack), the J14 harness (42 to 75 mm: J802 is in the board's middle), the BMS
    UART (144 to 200 mm: J201 is near the board's front), the FSESC USB (84 to 121 mm, to J602), the lidar power
    (15 to 42 mm: J409 is 5 mm in from the front edge, its wires enter from the front) and the fuse lead to the
    XT90-S (64 to 106 mm). Shorter: the fan lead, the ESC battery leads, the BMS P- and the camera's M8 lead.

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
| `MIDI_FUSE_XY`, `MIDI_FUSE_H`; `XT90_PAIR`, `XT90_PAIR_C` | 60 x 30 x 26 mm; pair 22 x 12 x 46 mm at (-37, 41) | item 26 |
| `tim561()` plug lengths | 45 mm | item 12: it decides how long the power board can be |
| `POWER_L` and `extras.POWER_CONN` | 130 mm; D's connector positions (HANDOFF_E), plug heights estimated | the plug heights on the built board |
| `J601_H`, `J601_PLUG` | 14.5 mm; right-angle head 9 x 12 x 18 mm | item 29, and the cable bought |
| `PD_TRIGGER`, `PD_RECEPT_DZ`, `CCCV`, `CCCV_X`, `CCCV_Z0` | 24.5 x 20.2 x 4.9 mm, 3.3 mm; 51 x 26.3 x 14 mm | item 30, before printing the right pod |
| `POD_WINDOWS` (`debug_usbc`, `button` z) | z 17.8 to 27.8; 8 to 17 | item 31 |
| `CAM_REG` | 43 x 21 x 10 mm (pololu.com) | where the team wants it |
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
| `side_pod_right` | fan window moved, plug slot gone, new windows at D's connector positions, room for the charge modules | 65 | 42 + supports |
| `deck_mid` | new insert positions; a rev A print cannot be converted | 167 | 109 |
| `deck_rear` | new phase opening, one insert; or convert a rev A print by hand | 180 | 117 |
| `deck_front` | two inserts, servo slot extended; or convert a rev A print | 171 | 111 |
| **total** | with `deck_rear` and `deck_front` converted | **367** | **about 240** |
| **total** | with all three deck pieces reprinted | **718** | **about 465** |

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
- A USB-A to USB-C cable, 0.3 m, with a right-angle USB-A plug whose cable leaves the plug's narrow side (for J601).
- Zip ties or a printed clip for the camera regulator on the arch; foam tape or a dab of hot glue for the PD trigger
  in its slot.
- No aluminium heat spreader any more.

## Open questions

- J601: its real height and face position, and which right-angle USB-A plug the team buys (MEASURE_FIRST 29). If no
  suitable plug turns up, a short USB-A extension with a right-angle male works too.
- The CC/CV module: if the one bought is 13 mm deep or less, its inner-wall window can go.
- Is the 21 mm limit under the acrylic shield fine with D's FET bar as built (MEASURE_FIRST 28)?
- Where the team wants the camera regulator (on the arch as modelled, or on a bracket on the tray as D's notes say).
- The carrier's holes, heights and header positions; the FSESC case and its ports; the BMS's terminals; the fuse
  holder and the XT90 pair; the dongle (MEASURE_FIRST 17 to 26).
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
