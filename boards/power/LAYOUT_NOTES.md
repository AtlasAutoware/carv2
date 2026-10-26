# ATLAS-PWR-1 rev B: layout notes (agents E and E2)

Status (E2, 2026-10-26): **not ready to order.** The board is built on the post-review design (`design.py` after
f270903) and routed except for 18 signal connections and 10 ground pins (DRC section). Copper, mask, markings and the
high-current numbers below are final for the power section; the open connections are all in the logic half (the
Pico, the J14 header, the hub and the dev-kit feed), and finishing them needs the placement change described under
"Routing".

## What changed in the layout and why

Placement (`layout.py`, no part removed, no net changed):

- U202 turned 180 degrees, so the BMS-side pins of both optocouplers (U201 1/2, U202 3/4) face west in one
  column and the board-side pins face east. Before, U202's BMS pins sat between U201's board-side pins and the
  DEV+/DEV- wire pads with under 2 mm on either side, so the 2 mm isolation rule could not be met.
- R201, R204, C201 (the BMS-side chips) pinned on the bottom under the optocouplers; two NO_AUTO bands keep
  every other bottom chip 2 mm off the BMS domain. TP1002 (GND test point) moved beside TP402 (+5V); TP302,
  C1001 and R1002 pinned where they fit after the reshuffle.
- SW801, F402 and TP702 moved 0.35-0.4 mm: SW801 and F402 overlapped the hub's socket courtyard by 0.17 and
  0.21 mm (the placer's HOLLOW rule let it through, KiCad's courtyard check does not).
- TP301 moved 0.6 mm down to make room for the FET bar warning.
- E2 moves for routing (board-local mm, all on the bottom unless noted; `layout.py` marks each with "(E2)"):

| Part | From | To | Why |
| --- | --- | --- | --- |
| C502 (100 nF, Q501 gate-source) | 68.25, 38.25 | 33.6, 22.5 | beside Q501's gate; the auto placer had put it 28 mm away |
| R306 (100k, MIC5014 IN pull-down) | 62.0, 69.75 | 62.0, 72.9 | north of the heatsink-NTC track that leaves under the MIC5014 |
| R701 (100k, VM_SENSE divider top) | 120.75, 58.5 | 70.0, 56.0, turned 270 | on the VM link: VM (a 0.3 mm class) cannot pass between the J802 and Pico pins, VM_SENSE can |
| R401 (33k, BAT to BTN_HI) | 115.0, 2.5 | 76.5, 49.8 | beside F501's BAT pin; it took a thin BAT track across the board |
| R411 (10k, VDEV_F to OV_G) | 75.5, 55.0 | 85.7, 54.4, turned 270 | it sat in the 2.5 mm gap west of F401 that MIC_IN and NTC_NODE need |
| TP403 (SERVO_V test point, top) | 120.6, 70.0 | 44.0, 14.1 | on the servo supply run (it was 50 mm from it) |
| J408 (DEV- wire pad, top) | 92.0, 68.2 | 93.28, 68.2 | room for the 2 mm VDEV track to DEV+ west of it; courtyard 0.03 mm clear of the Pico's |

  When `placer.py` ran again after these, it shifted a few auto-placed parts: C401 (45.25, 17.5 to 44.75, 19.25),
  C407 (81.75 to 82.75), R203 (88.0 to 88.5), R505 (31.0 to 30.75), R506 (41.0 to 40.25), R507 (41.25, 14.75 to
  39.5, 15.5), R811 (42.5, 11.75 to 60.0, 19.0), R813 (56.75, 17.0 to 41.75, 11.25), TP802 (37.0, 14.25 to 34.75,
  14.5). `KEEP_AUTO` is now True, so the next run keeps them. A move of D501 was tried and taken back (its courtyard
  overlapped MOD501's).

Copper:

- The VM pour reaches down to Y 36.5 between X 13.9 and 54 (nothing is placed there on the top). The corner where
  the motor current turns west into the ESC+ strip was 8 mm wide; it is now 11 mm. On the dry-run fills this took
  the BAT-to-ESC+ path from 1.078 to 1.022 mOhm and the peak current density at that corner from 25 to 20 A per
  mm of copper (`pour_resistance.py`, 0.2 mm grid, 90 A). The final numbers are under "High-current path".
- Review m20: solder mask open over the main current paths of the BAT and VM pours (`layout.copper()`, `C.mask`),
  1 mm inside the pour, 1.5 mm from every pad of another net, off the part bodies and the strips kept for the
  markings. On the final board: 9 openings on F.Mask, 665 mm2, exposing 327.8 mm2 of BAT and 337.4 mm2 of VM copper
  and no copper of any other net; nothing on B.Mask.

## Net classes and rules

| Class | Width | Clearance | Via | Nets |
| --- | --- | --- | --- | --- |
| Default (signals) | 0.3 | 0.25 | 0.8 / 0.4 | everything not below |
| Supply | 2.0 | 0.3 | 1.2 / 0.6 | VSYS_SW, VDEV_F, VDEV, LID_SW, LIDAR_V, CHG_IN, CHG_OUT, CHG_RB, CAM_VIN, BAT (its routed feeds), CHG_GND |
| Servo | 2.5 | 0.3 | 1.2 / 0.6 | SERVO_V |
| Pulse | 1.0 | 0.3 | 1.0 / 0.5 | PRE_D, PRE_F, V5_IN, VM |
| Rail5 | 1.0 | 0.25 | 1.0 / 0.5 | +5V |
| Power | 0.6 | 0.25 | 0.8 / 0.4 | +3V3, PICO_VSYS, CON_3V3, SW_GATE, SW_G1-3, HUB_VBUS (0.6 so it can reach U602's middle pin) |
| USB | 0.4 | 0.25 | 0.8 / 0.4 | P1-P4 D+/D-, routed as coupled pairs (0.4 mm, 0.3 mm gap) before the autorouter |
| BMS | 0.3 | 0.3 | 0.8 / 0.4 | BMS_VDD, BMS_TXD, BMS_RXD, BMS_GND, BMS_OPT1_A; 2 mm to every other net (DRU rule, and a class_class rule for Freerouting) |

Board floors (PCBWay capabilities page, Oct 2026, 2 oz normal process): 0.2 mm clearance (8 mil), 0.25 mm track,
0.8 mm via, 0.15 mm annular ring, 0.3 mm drill, 0.4 mm hole to hole, 0.3 mm copper to edge. KiCad's TO-92 land
pattern has 0.22 mm between pads and a 0.15 mm ring; a DRU rule allows 0.2 mm between the pads of each TO-92 part.
The class widths are targets: where a track could not get through at its class width the routers went down to the
board floor (list under "For the reviewer").

## Routing (E2, 2026-10-25 and 26)

Where it started: the first pass (Freerouting 1.9, 19 minutes, then 13 rounds of mazeroute) left 44 unconnected
items, about 25 of them on the 2.0 and 2.5 mm supply nets. Two causes:

- A tool bug. mazeroute's distance fields stopped at 1.0 mm, so a cell could never be free for a track wider than
  2 x (1.0 - clearance), 1.4 mm here: every wide net failed with "no open cell on start", on an empty board too.
  Fixed in `tools/mazeroute.py` (the fields now reach the widest rule plus the BMS isolation, and the router keeps
  the 2 mm BMS isolation itself).
- Order. The supply nets went to the routers after the signals had taken the corridors.

So the board was rebuilt from `layout.py` (`placer.py`, `build_pcb.py`) after the part moves above and routed
again, power first:

1. Two router guides in `layout.copper()` ('D:' areas, gone once routing is done): the bottom GND under the power
   section stays whole (X 0-58, Y 36-84), and no top track under J601's metal shell.
2. USB pairs: `mazeroute.py --only-pairs` (0.4 mm, 0.3 mm gap), locked; P1 needs one crossover via. The pair
   router left a 0.6 mm stub on P3_DM at J602; `out/usb_routes.json` has it trimmed.
3. Power copper by hand, locked: `out/hand_routes.txt` (turned into routes by the new `tools/hand_routes.py`, then
   `add_routes.py --lock`) holds every piece with a comment saying why it goes where it does. Widths: SERVO_V 2.5 mm
   along the J801 header, 1.9 mm at the rear pads, 1.6 mm through the neck between H1003's keep-out and the hub
   socket, 2.0 mm under the hub and J601; BAT feed to the latch 2.0 mm; VSYS_SW 2.0 mm from the latch to R408,
   TP401, J410 and F401, then a 1.0 mm front branch to the lidar switch and the camera polyfuse; CHG_RB 1.2 mm;
   VDEV_F and VDEV 2.0 mm, the C405 branch 1.0 mm, the D404 branch 1.5 mm; gate drive 0.6 mm; the VM sense links
   0.3-0.4 mm. Then the charger, lidar, camera and dev-kit branches with `mazeroute.py --only NET --width NET=W`
   (and the new `--skip` for the thin side branches), and the BMS domain, each locked.
4. Signals: Freerouting 1.9 from a clean board (50 minutes, 45 passes) left 21 nets open, all of the same kind:
   the MIC5014 side (MIC_IN, NTC_NODE, VM_SENSE, PRE_B, BTN_HI) and the J12 header side (the J801 series resistors)
   could not reach the Pico. Two power runs closed the dev-kit feed on both layers (the VSYS_SW front branch as a
   router diagonal from F401 on the top, the C405 branch round F401 on the bottom), so both were redone by hand: the
   front branch now leaves J410 straight east along Y 31.2, and C405 joins the VDEV trunk on the top, south of
   Q404 and up between D404/Q402 and J802. R411 moved out of the gap west of F401 (table above).
5. The seven nets that cross from the MIC5014 side (MIC_IN, NTC_NODE, VM_SENSE, PRE_B, BTN_HI, OV_G, OV_REF) were
   routed with mazeroute together with the rails on the otherwise empty logic half (one round, no clashes); the
   seven were kept and locked, the rails dropped. They pass the BMS domain to the south, along its 2 mm keep-away.
6. Freerouting for everything else (30 minutes, 45 passes) left 35 nets open; `mazeroute.py --only NET`, net by
   net, closed 17 of them (most in one round with no clash: Freerouting had left free paths unused). Longer runs
   (Freerouting from the clean board, stopped at pass 82 of 150 with no fewer items to route; mazeroute negotiation
   over all open nets; and a new `--win` option that lets one long net push the short ones aside) did not get
   further: the pushed nets could not be routed again. A local reroute round R412 and R419 (OV_B and OV_C, whose
   pads the locked crossing nets box in) traded two open nets for three and was not kept.

What is left (18 nets, see DRC) is a capacity problem in one place, not a tool problem. Twelve of them are long runs
from the J12 header's series resistors and the rear connectors (FAN_PWM, SERVO_IN_J, VESC_KILL, I2C0_SCL/SDA,
JETSON_3V3_SENSE, LATCH_OFF, LIDAR_REQ, ESTOP_OK_TO_JETSON, +5V to U302) to the Pico, and all of them have to get
into a strip about 20 mm wide that is already walled by the J14 header J802 (a 1x12 column 4.6 mm west of the
Pico's left pin column), the hub module's pin ring and the dev-kit feed. A 0.3 mm track fits once between two
pins of J802 or of the Pico, so every net that reaches the Pico from the west spends one of J802's 11 gaps per
layer and then one of the Pico's. The others (J14_CON_RXD, J14_PWR_KEY_N, JETSON_RESET, SERVO_BUF, OV_B, OV_C,
PRE_G, HUB_VBUS) are short pins that the long ones boxed in. Ways to finish it, in the order I would try them:

- Move J802 off the Pico's left side, if the J14 harness in `mech/` allows another spot. That opens the 4.6 mm
  channel and J802's 11 gaps at once; then rerun step 6.
- Or put the J801 series resistors (R801-R813) next to the Pico instead of next to J801: the long runs then become
  the J12_* nets, which start at the header pins and can be routed as one bus over the top side south of the power
  section (X 15-75, Y 13-33), which is still largely free.
- Either way, reroute the logic half from the state after step 5 (`out/hand_routes.txt` plus the locked crossing
  nets), not from this board.

Tool changes (`tools/README.md`, step 5): the mazeroute reach fix, `DSN_CLASS_CLEARANCE` kept by mazeroute,
`--skip REF,...`, `--win NET,...`; `tools/hand_routes.py` is new.

## High-current path

`pour_resistance.py` on the final fills (`dump_board.py --fills BAT,VM,GND`), 0.1 mm grid, 70 um copper, 90 A.
Copper only (no FET leads, solder or wire). "Peak" is the highest current per mm of copper width on the grid, at a
pad edge or a corner; "p99" is the 99th percentile.

| Path | Resistance | Drop at 90 A | Peak current density | Narrowest copper |
| --- | --- | --- | --- | --- |
| BAT pour: J101 (pack +) to the three FET drains | 0.196 mOhm | 17.7 mV | 23.5 A/mm at Q301's drain pin (18.6, 60.6), p99 6.5 | 36.8 mm (cut across the pour at Y 75.5) |
| VM pour: the three FET sources to J901 (ESC+) | 0.391 mOhm | 35.2 mV | 27.3 A/mm at Q301's source pin (21.0, 58.4), p99 9.5 | 11.6 mm (the ESC+ strip, cut at X 9.0) |
| GND: J902 (ESC-) to J102 (pack -), both layers | 0.037 mOhm | 3.3 mV | 10.7 A/mm at (3.4, 59.0), p99 3.0 top, 1.7 bottom | 12.9 mm top (cut at Y 60.6), 13.1 mm bottom (Y 57.0) |
| Whole path J101 to J901, each FET at its 1.3 mOhm maximum | 1.035 mOhm | 93.2 mV | 22.1 A/mm by J101 (23.2, 75.8), 24.5 A/mm at the ESC+ corner (13.8, 47.6) | |

In the whole-path run the three FETs share the current as 33.8 A (Q301, nearest the pack and ESC pads), 29.9 A
(Q302) and 26.3 A (Q303). On the 0.2 mm grid of the dry run the same path was 1.022 mOhm; the finer grid resolves
the corners better.

## DRC

`tools/drc.py` (KiCad 7.0.11, `boards/power/drc.rpt`), final board:

- 31 unconnected items: 18 signal connections, one per net: +5V (R409 to U302), ESTOP_OK_TO_JETSON, FAN_PWM,
  HUB_VBUS (U602 pin 2), I2C0_SCL, I2C0_SDA, J14_CON_RXD, J14_PWR_KEY_N, JETSON_3V3_SENSE, JETSON_RESET, LATCH_OFF,
  LIDAR_REQ, OV_B, OV_C, PRE_G, SERVO_BUF, SERVO_IN_J, VESC_KILL; and 13 ground items: through-hole GND pins whose
  pieces of fill are cut off by the routing (J408 DEV-, J802 pins 7 and 11, U302 pins 7 and 12, U402 pin 2, U801
  pin 2, U802 pins 2 and 3, MOD402 pin 2).
- 0 clearance, short, crossing, hole, edge and courtyard errors.
- Warnings (silkscreen only): 31 silk_overlap, all footprint texts against footprint graphics: the heatsink's
  "HEATSINK = BAT+ INSULATE" over its own outline (9), the Pico's and the hub's printed labels ("USB", "USB HUB 5997",
  "P1"-"P3", "UP") over their outlines (11), the "K" cathode marks of D401, D402, D404-D406, D501, D1001, D1002 over
  their body outlines, "CAM REG" against J1001's reference; and 12 silk_over_copper (the J401, J901, J904, TP101 and
  TP301 references, two of the hub's labels, D101's "K", the heatsink text, two circles and one line touching
  copper). The fab clips silkscreen off pads and openings.
- Copper: 1869 track segments and 247 vias (224 at 0.8/0.4, 12 at 1.0/0.5, 11 at 1.2/0.6), of which 52 are GND
  stitching vias (`finish_pcb.py`, 3 mm grid) and 36 join GND fill islands (`pad_vias.py --zone-islands`).

## Markings

Three fiducials (top), board name, revision and date (top and bottom), "FET bar is at pack voltage" next to the
FET row across from the bar (the heatsink footprint also carries "HEATSINK = BAT+ INSULATE"), + and - beside the
pack, ESC, BEC and dev-kit wire pads, and a pin-1 dot beside every polarised top-side part that has room (59 dots;
D702 and J1002 have none, no room). Where a wire pad had no free side for its sign, the pad's name with the sign
("BAT+", "SRV+", "SRV-") replaces the reference (J101, J404, J405). The bottom carries the board name, a serial
number box and "bottom: 1206/1210 chips, solder these first", reading correctly from below. The bottom chips'
references are on B.Fab, not on the silkscreen (build_pcb.py keeps only J, SW, TP, U and LED references on silk).

## For the reviewer

- Not orderable yet: 18 open signal connections and 10 GND pins (DRC). The files in out/fab and out/render were
  regenerated from this board so they match it, not so they can be ordered.
- J408 (DEV-, the dev kit's return, fused at 5 A on the feed side by F401) is one of the GND pins not reached by a
  fill; whoever finishes the routing should give it a wide GND connection, not just a via.
- Review m19 (10 AWG pads): J101, J102, J901 and J902 are 7.5 mm pads with 3.5 mm holes and a ring of six 0.6 mm
  plated holes, joined solid (no thermal spokes) to their 2 oz pours: J101 to BAT and J901 to VM on the top, J102
  and J902 to GND on both sides. That is right for 90 A and is exactly why they are slow to heat: the build guide's
  hot plate at about 100 C or 100-150 W iron (docs/BUILD_POWER_BOARD.md, tools and step 11) is needed; the README's
  assembly order now says so too.
- Review m20: done, numbers under "What changed".
- Tracks below their class width, where nothing wider fits (lengths on the final board): SERVO_V 2.0 mm (60.9),
  1.9 mm (26.6), 1.6 mm (8.8, the neck at H1003), 1.0 mm (2.7, the TP403 stub); VSYS_SW 1.0 mm front branch (75.2,
  lidar and camera; 3.95 A at a 10 C rise for 2 oz by the IPC-2221 outer-layer formula) and 0.5 mm to the sense and gate parts (18.1); CHG_RB 1.2 mm
  (50.2); VDEV 1.0 mm (31.5, the C405 branch); CAM_VIN, LID_SW, LIDAR_V 1.0 mm; CHG_IN and CHG_GND 0.5 mm only on the
  branches to the PD-trigger decoupling, Q502/Q503 and their resistors (the charge current path itself is 2 mm);
  +3V3 0.25 mm (26.3), PICO_VSYS 0.25 mm (18.1), HUB_VBUS 0.25 mm (15.9), CON_3V3 0.25 mm (15.2), and 0.25 mm pieces
  on LATCH_ON, SERVO_SIG, CON_RX, PRE_G, J14_RECOVERY_N, OV_K.
- The build guide (step 2) says the bottom silkscreen shows each chip's reference; on this board they are on B.Fab.
  Either print the B.Fab layer (gerbers/atlas_power-B_Fab.gbr) as the assembly drawing, or move the references to
  the silkscreen where they fit.
- The board text still carries the date 2026-10-24.

## Regenerating on the laptop (KiCad 10, run_kicad.sh)

The board was built, routed and checked here with KiCad 7.0.11; the K tools fall back to the KiCad 7 calls
(`tools/README.md`, "KiCad 7 and KiCad 10"). KiCad 7 cannot read the KiCad 9 schematic sheets, has no
`kicad-cli pcb drc` and no 3D renderer, so four steps are still to run on the team laptop (KiCad 10 flatpak), from
the repo root:

```
boards/tools/run_kicad.sh erc-power      # ERC on the schematic sheets: boards/power/erc.rpt
boards/tools/run_kicad.sh drc-power      # KiCad's own DRC with --schematic-parity: boards/power/drc.rpt
boards/tools/run_kicad.sh render-power   # 3D pictures: out/render/power_top, _bottom, _iso, _iso_bottom .png
boards/tools/run_kicad.sh glb-power      # 3D model for share/make_renders.py: out/render/atlas_power.glb
```

- `drc-power` adds the schematic parity check, which could not run here. The board was built from
  `atlas_power_parts.json`, which `build_sch.py` writes together with the schematic, so parity should come out
  clean; a footprint or net difference means the two have drifted apart and must be fixed before ordering. Expect
  the unconnected items and silkscreen warnings listed above; anything new in the copper categories needs a look.
- If KiCad 10 says the zones are out of date, open the board, press B (refill), save, and run `drc-power` again.
  The zones here were filled by KiCad 7.
- Do not run `pcb-power`: it builds the board again from the placement and throws the routing away.
- Do not use `fab-power` for the order: it deletes out/fab first and writes KiCad's own set (both CPL sides, a BOM
  from the schematic, a zip with every layer). The files in out/fab come from `tools/fab_outputs.py power` (plain
  Python around kicad-cli, KiCad 7 or later, no schematic needed); run that again after any change to the board.
