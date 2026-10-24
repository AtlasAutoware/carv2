# Measure before printing or ordering

The chassis numbers in `mech/kit.py` come from car 1's plate and a keep-out model built from
Traxxas's specs and exploded views. Most are estimates. Each one below is a single parameter
in `kit.py` (`P = dict(...)`), and every script re-runs its checks when a number changes:
`python3 mech/kit.py` rebuilds all parts, repeats the interference test and rewrites the STLs.

Print `fit_coupon_front.stl` and `fit_coupon_rear.stl` first (about 20 g each). They are the
deck's tower saddles and body-post slots cut out of the full deck, so if they drop onto the
towers with the posts through the slots, the deck will too.

| # | measure | parameter | now | why it matters |
| --- | --- | --- | --- | --- |
| 1 | distance between the front and rear shock-tower top edges | `FRONT_TOWER_X`, `REAR_TOWER_X` | 168.3 / -141.7 (310 apart) | saddle positions; the rear one was moved 11.4 mm from car 1 using the wheelbase only |
| 2 | height of the tower top edges below where the deck will sit; old-plate underside to the chassis side-wall top | `TOWER_TOP_BELOW_OLD_PLATE`, `UNDER_CLEARANCE` | 16 / 45 | deck height; everything under the deck is checked against it |
| 3 | body-post positions on each tower (x and y at deck height) | `FRONT_POST`, `REAR_POST` | (180.4, +-38.6) / (-127.7, +-41.1) | the 24 mm post slots have +-8.5 mm of slack |
| 4 | tower thickness at the top | `TOWER_T` | 4 | saddle slot width (tower + 0.6) |
| 5 | battery bay: length, width, inner edge y, floor depth below the side-wall top | `BATT_BAY`, `TUB_DEPTH` | x -75..65, y 15..62, 24 deep | the pack box body is 124 x 44 x 72.4 mm (flange on top) and must fit, with 2.8 mm under it |
| 6 | stock battery hold-down posts: where they are and whether they come out | - | not modelled | they may have to be removed for the pack box |
| 7 | steering servo top (inverted case) and bellcrank sweep under the front of the deck | `SERVO`, `LINKAGE` | top at rim +25 / +12 | front rib and servo cable slot |
| 8 | transmission and motor tops under the rear of the deck | `GEARBOX`, `MOTOR_*` | rim +22 / +23 | rear ribs and the phase-wire slot |
| 9 | front tyre at full lock and full bump against the deck's front corners | `TYRE_*`, `BUMP`, `LOCK_DEG` | clears in the model | the nose taper starts at x 120 for this reason |
| 10 | Triton bottom face: spacing of the four corner M3 holes | `CAM_HOLE_PITCH` | 20 x 20, ESTIMATE | the cradle has +-1.5 mm slots; confirm on the camera (LUCID's manual says 4 corner M3 on the bottom but gives no spacing) |
| 11 | Puller Pro sensor plug: pitch and pin order | drive board J_HALL | JST-ZH 6-pin assumed | decides the board connector |
| 12 | M12 lidar plug bodies behind the TiM561 | `tim561()` estimates | 45 mm long, so the cables leave them at x 114.6 | they run under the camera arch. Rev B: they also cap the power board's length. At `POWER_L` 150 the board's front 3.4 mm and its front-left standoff sit inside the plug envelope; 130 leaves 16.6 mm for the cables to turn (`kit_report.json`, `lidar_plug_ends_ahead_of_power_board_mm`) |
| 13 | wheel drop with the chassis lifted (suspension droop), front and rear | `STAND_H` in `mech/extras.py` | 40 mm assumed | the bench stand's height: 125 mm leaves about 13 mm under the tyres at 40 mm of droop |
| 14 | (rev A only) the camera cable's RJ45 plug and boot, width and height | `CAM_PLUG_NOTCH` (removed in rev B) | 20 mm slot for a 14 x 10 mm boot | rev B has no camera-plug slot: the camera cable leaves the dev kit's RJ45 over the pack lid |
| 15 | antenna connectors on the M.2 Wi-Fi card from the dev kit | pigtails in `bom/make_bom.py` | MHF4 (AW-CB375NF datasheet); MHF4 pigtails ordered | check the card when the kit arrives |
| 16 | (rev A only) brain board corner H4 (brain-local 10, 5) under the camera RJ45 J6 | - | no screw from the top | rev B has no brain board |

## Rev B additions (dev-kit carrier, FSESC, BMS)

Rev B puts the NVIDIA dev-kit carrier on a printed tray over the new power board, the FSESC in a cradle beside the
motor and the JBD BMS on the pack lid (`mech/NOTES_REVB.md`). Items 17 to 24 come from the Phase 1 mechanical
report (C, section 9); 25 and 26 are estimates the rev B model added. Each parameter is in `mech/kit.py` unless
another file is named. Change it, rerun `python3 mech/kit.py` and `python3 mech/extras.py`, and the tray, the cradle,
the canopy and the cable lengths follow.

| # | measure | parameter | now | why it matters |
| --- | --- | --- | --- | --- |
| 17 | Dev-kit carrier: the 4 mounting-hole positions from the board edges, the hole diameter (M2.5 or M3), the keep-out ring around each | `DEVKIT_HOLES` (dev-kit-local X from the rear edge, Y from the edge opposite the I/O connectors), `DEVKIT_PILOT_D` | PLACEHOLDER, unverified: an 86 x 58 mm rectangle centred on the 100 x 79 board, (7, 10.5) to (93, 68.5); 2.2 mm pilots for M2.5 thread-forming screws | the tray's four bosses. NVIDIA's carrier spec gives only the 100 x 79 mm outline; the hole positions are in the login-only design files. Measure before printing the tray. The power board PCB no longer depends on this: the tray stands on the board's own six holes |
| 18 | Dev kit: carrier top to fan top; module and heatsink footprint and position on the carrier; which sides the heatsink fins exhaust to | `JETSON_SINK_H`, `JETSON_XY` | 32 mm; dev-kit-local X 10 to 88, Y 8 to 56 (estimates) | canopy height (8 mm over the fan), the grille position (`extras.FAN_C`); keep the fin exits clear of the canopy lip |
| 19 | Dev kit bottom with the NVMe and the Wi-Fi card fitted: the lowest point below the carrier | `DEVKIT_BOTTOM_H`, `DEVKIT_BOSS_H` | 6.0 mm; bosses 7.0 mm (bottom + 1) | the boss height on the tray. If the bottom is 4.3 mm as the carrier drawing says, the bosses can drop to 5.5 mm and everything above comes down 1.5 mm |
| 20 | Positions of J12 (40-pin), J14 (button header), J13 (fan) and of the I/O connectors along the edges | `DEVKIT_J12`, `DEVKIT_J14`, `DEVKIT_IO` | estimates: J12 at dev-kit X 6 to 57 and J14 at X 62 to 92.5 on the edge opposite the I/O; DC, DisplayPort, 2 USB-A stacks, RJ45, USB-C along the I/O edge | the ribbon and harness runs, where the power board's box header and 1 x 12 header go, where the right-pod windows can go, the plug envelopes over the pack lid |
| 21 | Cased FSESC: L x W x H, where each lead and port leaves the case (motor leads, battery leads, USB, COMM, hall), mounting holes; which model each owned unit is | `ESC_CASE`, `ESC_C`; port positions in `extras.cable_defs()` | PLACEHOLDER: Mini FSESC 6.7 Pro bare 67 x 39 x 18.7 mm plus 2 mm a side = 71 x 43 x 22.7 mm, centred at (-74, -34) | the cradle, its zip-tie straps, the phase-lead drop through the deck and the U-loop of the battery leads into the XT60 |
| 22 | Bench: J12 pin 17 voltage after `sudo poweroff` with DC still on; PC_LED (J14 pins 2-1) open voltage and current; `evtest` on a J14 pin 12-11 short; seconds from key press to halt | supervisor firmware timeouts (`firmware/supervisor/`) | not measured | the halt-detection choice and the supervisor timeouts |
| 23 | Triton: boots from 12 V on M8 pin 1 (+) and pin 5 (GND) with a plain (non-PoE) link; its current; the right-angle M8 plug's size | camera power; `triton()` M8 plug envelope | 2.5 W (Edmund); plug 16 mm out, cable up (estimate) | camera power from the power board; the M8 lead's route over the arch |
| 24 | `zcat /proc/config.gz \| grep -E 'RTL8152\|LAN78XX\|AX88179'` on the car's JetPack, and the adapter's driver in `ethtool -i`; the adapter's body size and cable length | `USB_ETH` | 50 x 22 x 15 mm body, 180 mm cable (estimates) | which adapter to buy, the NetworkManager match; the dongle stands against the camera arch's left leg |
| 25 | JBD BMS: outline (160 x 105 x 10 mm in two listings), where B-, P-, the balance connector, the NTC and the UART port leave the board, any heat plate | `BMS`, `BMS_MOUNT`; lead ends in `extras.cable_defs()` | 160 x 105 x 10 mm, standing on edge on the pack lid; all leads assumed at its rear end | the BMS holder and the 10 AWG lead lengths. A board that fits the 138 x 51 mm lid could lie flat instead (`BMS_MOUNT=flat`) |
| 26 | MIDI 125 A fuse holder size and stud positions; XT90-S plug length with its leads | `MIDI_FUSE_XY`, `MIDI_FUSE_H`; `xt90s_pack` in `boards()` | 60 x 30 x 26 mm holder on the lid (estimate); XT90-S 30 mm out from the board edge | the B+ lead lengths and the space under the dev kit's plugs |
