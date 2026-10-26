# ATLAS-PWR-1 rev B: handoff to layout and routing (agent E) and to the mech model

Board-local coordinates in mm, top view: X forward from the rear edge (0..130), Y toward the car's left from the
pod edge (0..84). Car coordinates: (x, y) = (X - 32, Y - 68). Heights are above the board's top surface; the
board top sits at car z 8.6 (7 mm standoffs on the 1.6 mm deck datum used by `mech/kit.py`).

E2b (2026-10-26): the board is now **4 layers**, still 1.6 mm thick, so nothing changes for the mech model: F.Cu and
B.Cu 2 oz as before (parts, power pours, hand routes), In1.Cu a 1 oz solid GND plane (cut out under the BMS domain,
X 76-85, Y 58-84 and X 76-92.5, Y 76.6-84), In2.Cu 1 oz signals. The placement is the one in this file with eight of the J12
series resistors (R801, R802, R806, R807, R809, R811, R812, R813) moved under and beside the Pico (LAYOUT_NOTES.md);
J802 did not move (table below). Why four layers, the stackup and the routing: LAYOUT_NOTES.md.

## What is in this folder

| File | What it is |
| --- | --- |
| `design.py`, `chips_power.py` | netlist and parts; `build_sch.py power` writes `atlas_power_parts.json` and the 10 schematic sheets |
| `layout.py` | outline (130 x 84, 2 mm corner radius, no notch), holes, net classes, BMS clearance rule, explicit placement of 118 parts, power copper, markings (agent E) |
| `out/atlas_power_placement.json` | placement of all 215 parts (118 explicit, the rest placed by `placer.py`), 0 conflicts |
| `DESIGN_FIXED.md` | every change made for the pre-order review (2026-10-24), with the refs that moved |
| `out/atlas_power_copper.json` | power pours, GND stitching vias, hole keep-outs, router keep-outs |
| `out/fp_lib.json` | footprint geometry for the placer, made from the `.kicad_mod` files by `tools/fp_lib_from_mod.py`; your first `build_pcb.py` run replaces it with KiCad's own dump |
| `out/placement.png`, `out/placement_pours.png` | the placement, top and bottom; the second shows the power pours |
| `netcheck.py` | electrical checks (0 errors, 14 warnings) |

Tool changes I made (generic, the drive board does not use them): `tools/placer.py` reads three optional layout
settings. `HOLLOW` lists modules on tall sockets: other parts may sit inside their outline and only their pads are
obstacles. `SMD_UNDER_THT` with `PAD_CLEAR`: on the far side a through-hole part blocks only its pads plus
PAD_CLEAR, so bottom chips go under through-hole bodies. `SIDE` (set from the parts JSON) puts each auto-placed
part on its own side. `tools/fp_lib_from_mod.py` is new. `tools/make_footprints.py power` writes this board's
footprints in KiCad 7 format.

Known tool problem: `tools/build_pcb.py` calls KiCad 9 API (`FOOTPRINT.SetField` at line 117, and
`pcbnew.FLIP_DIRECTION_LEFT_RIGHT` for bottom parts). Under KiCad 7.0.11's pcbnew it stops at `SetField`. KiCad 7
has `SetProperty` and `Flip(pos, True)`; I did not change build_pcb.py.

## Regions

| Region | X | Y | Contents |
| --- | --- | --- | --- |
| Power section | 0-74 | 36-84 | pack pads, bulk caps, FET row and bar, VM pour, precharge, MIC5014, ESC and BEC pads, charge fuse |
| Rear edge, low | 0-18 | 0-36 | fan header, FSESC COMM, SERVO_IN, BEC_OUT, servo-supply pads, fan 2N7000 |
| Middle rear | 14-74 | 13-36 | PD-trigger and CC/CV wire pads, charge reverse block, Pololu latch pads, R-78E 5 V |
| J12 strip | 11-71 | 2-12 | 2x20 box header for the ribbon (ribbon leaves upward and out over the Y = 0 edge) |
| Hub | 79-98 | 0-30 | CH334F hub on sockets, USB-C at the Y = 0 edge; MCP2221A (socket) and MCP1700 under it; J603 (spare port) west of it |
| Dev-kit feed and BMS | 75-95 | 30-84 | BMS JST-XH and its two PC817s, DEV pads, dev-kit fuse, OV cut-off, J14 header |
| Pico | 96-117 | 30-84 | Pico on sockets, USB end at the pack edge; 74HCT08 (socket) and two PC817s under it |
| Below the Pico | 97-122 | 0-30 | dev-kit USB-A J601 at the Y = 0 edge, FSESC USB header J602, power button, status LEDs at the edge, recovery button, lidar polyfuse and TVS |
| Front edge | 117-130 | 9-76 | servo header and 1000 uF, lidar switch and terminal, camera feed pads, E-stop, remote button |

## High-current nets and the hand copper (copper() in layout.py)

- BAT (pack +, up to 90 A pulses): top pour `P:BAT_F` north of the FET pin row (Y >= 59.5, X 13.5-66), plus the
  strip under Q304 and a tongue to the charge fuse F501 (X 64.5-74.5, Y 48-64). The bottom under it is GND, so
  the bulk-cap loop is short.
- VM (motor bus to the FSESC): top pour `P:VM_F` south of the pin row (X 13.9-56.6, Y 39.6-59.5) and the rear
  part (X 0-13.9, Y 36-47.6) that holds the ESC+ pad. At least 12 mm wide everywhere, 2 oz.
- GND return: top corner `P:GND_PWR_F` (X 0-13.4, Y 48.6-84) with ESC- and BAT- 12 mm apart, and the whole bottom
  of the power section `P:GND_PWR_B` (X 0-66, Y 36-84), stitched in the corner.
- Each pour reaches its own pins over their outer edge: the TO-220 pads are 1.9 x 2.0 mm at 2.54 mm, so nothing
  fits between them. BAT has priority 13, VM and GND 12.
- Deviation from PHASE2's "BAT/VM >= 8 mm on both layers": VM is on the top only and the bottom under it is GND.
  The pour is 12-20 mm wide (more copper than 2 x 8 mm), and the GND plane right under it keeps the switching
  loop small. If you want VM on the bottom too, keep a GND path from ESC- to BAT- on both layers.
- Gate drive: MIC5014 GATE (U301 pin 5, X 72.3 Y 66.2) to the 10 Ohm gate resistors R301-R303 on the bottom right
  north of each G pin (X 15/28/41, Y 63.6). Run SW_GATE on the bottom along Y about 66.5; the short SW_Gn stubs
  go south to the G pins. MIC5014 SOURCE (pin 3, X 64.7 Y 68.7) needs a 0.6 mm bottom track to a via in the VM
  pour (for example at X 55, Y 57). R304 (2.2M gate-source) is SMD near the MIC5014.
- Precharge: Q304 D (X 60.5 Y 59.5) -> F301 (X 61, Y 55.6 / 50.5) -> R313 pad 1 (X 54.5 Y 45.5); R313 pad 2 sits
  in the VM pour. 1 mm tracks (1.7 A peak).
- Charge ground (review B1): CHG_GND is its own net. It joins MOD501 pad 2 (PD trigger GND), MOD502 pad 2 (CC/CV
  IN-), D501, C501, Q502/Q503 emitters, R504, R506 and TP502. Its only link to GND is inside the CC/CV module (IN- to
  OUT-, the current shunt): MOD502 pad 4 (OUT-) is on GND. Route CHG_GND as a Supply track (2.0 mm, 2.5 A); the GND
  fills must not swallow it (they will not: it is a different net), and nothing may join it to GND on the board.
- FSESC signal grounds (review M6): J903 pin 2 (COMM_GND) -> R905 3.3 Ohm -> GND, J904 pin 3 (SRVIN_GND) -> R906
  3.3 Ohm -> GND, J602 pin 4 (VUSB_GND) -> R604 2.2 Ohm -> GND. Put each resistor right at its connector pin; the
  connector-side net is a short track from the pin to the resistor, never connected to a GND pour.
- Net classes in layout.py: Supply 2.0 mm (VSYS_SW, dev-kit feed, lidar, camera, charge path, CHG_GND), Servo 2.5 mm
  (SERVO_V runs from the rear BEC pads at X 9-15 to the front servo header at X 127: about 115 mm, use 2.5 mm or
  wider and both layers if you can), Pulse 1.0 mm (PRE_D, PRE_F, V5_IN), Power 0.6 mm, USB 0.4/0.25 mm, BMS 0.3 mm
  with 1.0 mm clearance and a 2 mm DRU rule against every other net. Signals 0.3 mm.
- USB pairs (keep short, coupled, over GND): P1 hub X 96.1 Y 9.7 (D+) / 12.24 (D-) -> J601 X 102.8, Y 16.83 (pin 3,
  D+) / 14.83 (pin 2, D-), VBUS pin 1 at Y 12.83, GND pin 4 at Y 18.83, shell pads at X 100.08/105.52, Y 12.1/19.1
  (GND); the pair arrives in the opposite order, so swap it with one via pair or approach J601's pins from both
  sides. P3 hub X 96.1 Y 19.86 (D+) / 22.4 (D-) -> J602 X 109.3, Y 14.77 (pin 3) / 17.31 (pin 2) (full speed only).
  P2 hub X 80.9 Y 9.7/12.2 -> U601 pins 12/13 (under the hub); P4 hub X 80.9 Y 19.9/22.4 -> J603 X 77.4. Your
  `out/usb_routes.json` from the earlier placement no longer fits P1 and P3.

## Keep-outs and mechanical rules

- Mounting holes at (4,4), (4,80), (75,4), (75,80), (126,4), (126,80): 3.2 mm NPTH, no copper and no parts within
  3.5 mm (`K:hole*`, kept after routing; the printed standoffs can conduct).
- BMS domain (BMS_VDD, BMS_TXD, BMS_RXD, BMS_GND, BMS_OPT1_A at J201, U201, U202 and three bottom chips): 2 mm from
  everything else, no pour across the gap between the two sides of U201/U202.
- Under the Pico (X 99-115, Y 31-82) and the hub (X 82-95, Y 1-28): parts there are 9 mm tall or less (module
  underside at 11.0 mm). The modules' courtyards are only their socket strips, so KiCad does not flag them.
- The heatsink bar (X 10.5-50.5, Y 62.9-65.9) is live at BAT+ and rests on the BAT pour: keep only BAT copper
  under it. Its front face is 0.15 mm off the FET tab backs on paper; the M3 bolts close that.
- Height map (mech kit `power_zones()`): 23 mm everywhere under the dev-kit tray (X 20-120) and in the 9 mm bands
  Y 0-9 and Y 75-84 of both end strips; 35 mm elsewhere. The tallest parts are the 680 uF caps (about 21 mm) and
  the FETs on the bar (about 20 mm). Check the mini blade fuse holders with fuses fitted (not measured).
- Bottom side: no parts taller than 2 mm (1206/1210 chips only); the board sits on 7 mm standoffs.
- J601 (USB-A, Wurth 614004134726, KiCad `USB_A_Wuerth_614004134726_Horizontal`) stands on its edge: body 7.1 mm
  wide (X 99.25-106.35) and 19.3 mm deep (Y 0.5-19.8), opening facing -Y with its face 0.5 mm inside the board edge.
  I could not open Wurth's drawing (the download was blocked), so its height and its exact face position are taken
  from the KiCad footprint and not verified: check both on the part before the panel cut-out is fixed.

## What to keep by hand

- Keep the explicit placement in layout.py as it is (pads that face the edges, the power section, the parts under
  the modules). `KEEP_AUTO` is off; the bottom chips come out the same on every run.
- Route BAT, VM and GND only through the pours; the `D:*` keep-outs stop the router from crossing them on the top.
- If a bottom chip blocks a route, move it with `SIDE`/explicit placement in layout.py rather than by hand in
  KiCad, so the next placer run keeps it.

## Real connector positions (for mech/extras.py POWER_CONN and kit.py POD_WINDOWS)

Positions are pad-group centres. "Above" = the cable enters from above the board; heights marked est. are not
measured.

| Item | Board X, Y | Car x, y | Edge, direction | Notes |
| --- | --- | --- | --- | --- |
| ESC+ / ESC- pads (replaces the XT60PW) | 5.0, 42.0 / 5.0, 54.0 | -27.0, -26.0 / -27.0, -14.0 | rear (X = 0), leads over the edge | 10-12 AWG soldered from above. ESC_OUT_Y = 48 (midway); both inside the ESC's Y span 12.5-55.5 |
| BEC+ / BEC- pads (Castle BEC input) | 22.0, 42.0 / 12.0, 50.2 | -10.0, -26.0 / -20.0, -17.8 | rear area | 16 AWG. BEC+ is on VM (default) |
| BEC+ALT pad J410 (review M3) | 63.6, 34.45 | 31.6, -33.55 | middle | 16 AWG; on VSYS_SW. The BEC's red lead goes here instead of BEC+ only if its start-up stops the precharge, so the lead must reach both pads |
| BEC_OUT header J403 (BEC output plug) | 9.2, 22.7 | -22.8, -45.3 | rear area, above | 1x3 2.54 mm, V+ in the middle; servo plug about 17 mm tall (est.) |
| Servo-supply pads SRV+ / SRV- | 14.6, 33.0 / 14.6, 26.8 | -17.4, -35.0 / -17.4, -41.2 | rear area | alternative to J403 |
| FSESC COMM J903 | 2.7, 27.6 (pins at Y 21.6-33.6) | -29.3, -40.4 | rear edge, above | JST-PH 7 vertical; pin 1 at Y 21.6; pin 2 (GND) through R905 |
| SERVO_IN J904 | 9.2, 32.0 (signal at Y 34.5) | -22.8, -36.0 | rear area, above | 1x3 2.54 mm; pin 3 (GND) through R906 |
| Fan J1003 (moved to the rear edge) | 3.6, 13.4 (pins at Y 9.6-17.2) | -28.4, -54.6 | rear edge, above | 4-pin fan header, pin 1 (GND) at Y 9.6 |
| Pack BAT+ / BAT- pads (replaces the XT90 board-mount) | 19.5, 79.6 / 6.25, 65.6 | -12.5, 11.6 / -25.75, -2.4 | pack edge, leads over the Y = 84 edge near X 5-22 | 10 AWG pigtail to an XT90 male that mates with the pack's XT90-S |
| BMS UART J201 | 85.3, 81.0 | 53.3, 13.0 | pack edge, above | JST-XH 4 vertical |
| Dev-kit DC lead DEV+ / DEV- | 92.0, 74.0 / 93.28, 68.2 | 60.0, 6.0 / 61.28, 0.2 | pack side | 18 AWG pads (DEV- moved 1.28 mm east in routing, LAYOUT_NOTES.md) |
| Pico micro-USB | 106.5, 83.4 | 74.5, 15.4 | pack edge, facing +Y | about 13.9 mm above the board (8.5 mm socket + 2.5 mm header spacer + PCB) |
| Hub USB-C (laptop port) | 88.5, -0.4 | 56.5, -68.4 | pod edge (Y = 0), facing -Y | centre about 14.2 mm above the board, car z about 22.8 (est.: module on 8.5 mm sockets) |
| Dev-kit USB-A J601 (review M7) | 102.8, face at Y 0.5 | 70.8, -67.5 | pod edge (Y = 0), opening facing -Y | one standard USB-A to USB-C cable to the dev kit's USB-C. The plug and its cable need about 40 mm beyond the edge (est.), or use a cable with a right-angle (up or down) USB-A plug. Height of the opening not verified (see above) |
| FSESC USB header J602 / spare port J603 | 109.3, 16.0 (pin 1 at Y 19.85) / 77.4, 17.6 | 77.3, -52.0 / 45.4, -50.4 | middle, above | 1x4 2.54 mm, Adafruit 4449 jack leads; J602 to the FSESC micro-USB cable, J603 spare |
| Status / fault LEDs D701 / D702 | 119.75, 8.1 / 119.75, 2.8 | 87.75, -59.9 / 87.75, -65.2 | pod edge, beside the power button | 3 mm, visible from above and through the button window if it is wide enough |
| Recovery button SW801 | 102.9, 25.8 | 70.9, -42.2 | middle, pressed from above | 6 mm tactile, 5 mm tall, just south of the Pico |
| Power button SW401 (right angle) | 112.75, 5.6; plunger tip at Y -0.25 | 80.75, -68.3 | pod edge, pressed from -Y | plunger about 3.5 mm above the board, car z about 12 (est.) |
| J12 box header J801 | 41.1, 7.3 (pins X 17.0-65.3, rows Y 6.0 / 8.5) | 9.1, -60.7 | middle, ribbon up | 2x20 shrouded; header plus IDC plug about 18 mm (est.) |
| J14 header J802 | 93.0, 48.4 (pin 1 at Y 62.4, pin 12 at Y 34.5) | 61.0, -19.6 | middle, above | 1x12 vertical, Dupont housing; unchanged by E2b (no other spot on the board takes its 3.6 x 31.6 mm courtyard without moving a pinned part, LAYOUT_NOTES.md) |
| Servo J406 | 127.6, 17.1 (signal at Y 19.6) | 95.6, -50.9 | front edge, above | 1x3 2.54 mm |
| Lidar power J409 | 125.0, 26.8 (+ at Y 25.0) | 93.0, -41.2 | front edge, wires enter from +X | Phoenix PT 1,5/2-3,5-H |
| Camera regulator input pads (MOD402) | 125.1, 44.6 (VIN at Y 46.5, GND at Y 42.7) | 93.1, -23.4 | front edge | 22 AWG pair to the Pololu S18V20F12 on the tray; its 12 V output goes straight to the Triton's M8 lead (pin 1 red +12 V, pin 5 black GND). No camera connector on the board; D406 (P6KE22A) guards the regulator input |
| E-stop J1001 | 126.5, 55.0 | 94.5, -13.0 | front edge, above | JST-PH 2 vertical |
| Remote button J1002 | 122.9, 64.0 | 90.9, -4.0 | front edge, enters from +X | JST-PH 2 side entry |
| Charge: PD-trigger pads, CC/CV pads | 19.3, 21.0; 26.9, 24.0 | -12.7, -47.0; -5.1, -44.0 | middle rear | both modules sit off the board in the pod at the charge window (mech's choice of x); six wires, one per module terminal: PD VOUT, PD GND (CHG_GND), CC/CV IN+, IN- (CHG_GND), OUT+, OUT- (GND). Never join IN- and OUT- outside the module (review B1) |
| Pololu latch pads | 48.3, 23.3 | 16.3, -44.7 | middle | latch module on the tray, 18 AWG VIN/VOUT/GND, thin ON/OFF |

POD_WINDOWS: `debug_usbc` at car x 56.5, z about 19-26 (plug overmold around the 22.8 centre); `button` at car
x 80.75, z about 9-16 (the status LEDs sit just front of it at car x 87.75); new `devkit_usba` centred at car x 70.8,
from the board top (car z 8.6) up; size it from the plug of the cable the team buys (the receptacle's height is not
verified), unless a right-angle plug keeps the cable inside the pod; `charge_usbc` is wherever the mech model puts
the PD trigger in the pod (no board constraint, but not at car x 66-76 any more).
