# ATLAS-PWR-1 rev B: layout notes (agents E and E2)

Status (E2b, 2026-10-26): **routed, 4 layers.** The board is built on the post-review design (`design.py` after
f270903) and fully routed: `tools/drc.py` finds 0 unconnected items and 0 clearance, short, crossing, hole, edge or
courtyard errors (DRC section). It went from 2 to 4 layers on 2026-10-26: on two layers the logic half could not be
routed (21 connections still open after two full attempts on the placement below, 18 at 8803cd2) and its ground had
no path to the pack ("Why four layers"). Still to do before ordering: the KiCad 10 checks on the laptop (ERC, DRC with
schematic parity, last section) and a look at the files in out/fab. PCBWay prices are under "PCBWay quote".

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
- E2b (2026-10-26), the placement change asked for after 8803cd2:
  - J802 (the 1x12 J14 harness header) stays at 93.0, 48.4. A search of the whole board on a 0.5 mm grid, both
    orientations, for a spot where its 3.6 x 31.6 mm courtyard clears every top-side courtyard and the locked power
    copper found only the spot it has. In the rear half (X below 65, where the 75 mm harness reaches) every
    spot overlaps the J801 ribbon header, and with J801 left out every spot still overlaps at least six pinned top
    parts (the best: U401, Q503, MOD401, TP501, TP802, TP403 at 48.5, 16.0). Elsewhere the nearest spots overlap the
    Pico or J408. Moving it would mean moving pinned parts, which was not asked for.
  - The J12 ribbon's series resistors whose far side is a Pico pin moved from the J801 header to the Pico (bottom,
    `layout.py` "(E2b)"): R801 (330, I2C0_SDA) 100.25, 67.75; R802 (330, I2C0_SCL) 100.25, 62.5; R809 (10k,
    JETSON_UP) 100.25, 50.0; R806 (10k, JETSON_3V3_SENSE) 106.75, 40.5 with its 100k pull-down R807 at 109.5, 34.5;
    R812 (1k, ESTOP_OK_TO_JETSON) 112.75, 48.25; R811 (10k, LIDAR_REQ) 112.75, 53.5; all turned 90. R813 (1k,
    CHG_STAT_N_TO_JETSON) went to 127.75, 45.0, turned 90 (its first spot, 119.25, 47.5, sat on a locked VSYS_SW
    track). R803/R804 (to the FSESC COMM header) and the pull-downs R805, R808, R810 stay at J801.

Copper:

- The VM pour reaches down to Y 36.5 between X 13.9 and 54 (nothing is placed there on the top). The corner where
  the motor current turns west into the ESC+ strip was 8 mm wide; it is now 11 mm. On the dry-run fills this took
  the BAT-to-ESC+ path from 1.078 to 1.022 mOhm and the peak current density at that corner from 25 to 20 A per
  mm of copper (`pour_resistance.py`, 0.2 mm grid, 90 A). The final numbers are under "High-current path".
- Review m20: solder mask open over the main current paths of the BAT and VM pours (`layout.copper()`, `C.mask`),
  1 mm inside the pour, 1.5 mm from every pad of another net, off the part bodies and the strips kept for the
  markings. On the final board: 9 openings on F.Mask, 665 mm2, exposing 327.7 mm2 of BAT and 337.4 mm2 of VM copper
  and no copper of any other net; nothing on B.Mask.

## Stackup (E2b)

| Layer | Copper | What is on it |
| --- | --- | --- |
| F.Cu | 2 oz (70 um) | all through-hole parts and modules; the BAT, VM and GND power pours; the hand routes and power runs, locked as at 8803cd2; signals; a GND fill after routing |
| In1.Cu | 1 oz (35 um) | one solid GND plane (`P:GND_In1`) over the whole board except the BMS domain and its 2 mm band (X 76-85, Y 58-84 and X 76-92.5, Y 76.6-84: the `BMS_DOMAIN` boxes, also a keep-out on In1 and In2, `K:bms_in1`), so BMS_GND stays an island of its own; every through-hole GND pin joins it, J408 (DEV-) without thermal spokes (`FULL_CONNECT`) |
| In2.Cu | 1 oz (35 um) | signals, and most of the +3V3, +5V and PICO_VSYS runs (85, 163 and 61 mm of them) |
| B.Cu | 2 oz (70 um) | the bottom chips; the GND pour under the power section; signals; a GND fill after routing |

Dielectrics as written into the board's stackup (`layout.STACKUP`, nominal; the fab sets its own): 0.2 mm prepreg,
0.97 mm core, 0.2 mm prepreg, 1.6 mm finished, HASL lead-free. The mounting-hole keep-outs (3.5 mm) are on all four
layers. The BMS isolation rule (2 mm from every other net, DRU) applies on every layer as before.

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
0.8 mm via, 0.15 mm annular ring, 0.3 mm drill, 0.4 mm hole to hole, 0.3 mm copper to edge. They are kept for all
four layers (the inner 1 oz layers would allow less; the quote below is for 8/8 mil). KiCad's TO-92 land
pattern has 0.22 mm between pads and a 0.15 mm ring; a DRU rule allows 0.2 mm between the pads of each TO-92 part.
The class widths are targets: where a track could not get through at its class width the routers went down to the
board floor (list under "For the reviewer").

## Routing, two layers (E2, 2026-10-25 and 26)

This section is the history: the board as built now is the four-layer one ("Routing, four layers").

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

That pass (8803cd2) left 18 nets: long runs from the J12 header's series resistors and the rear connectors to the
Pico, which all have to get into a strip about 20 mm wide walled by the J14 header J802 (a 1x12 column 4.6 mm west
of the Pico's left pin column), the hub module's pin ring and the dev-kit feed, and short pins they boxed in. A
0.3 mm track fits once between two pins of J802 or of the Pico. The two fixes proposed then were to move J802 and to
put R801-R813 next to the Pico; only the second was possible (placement above).

### Second routing pass (E2b, 2026-10-26)

The board was built again from the new placement (`build_pcb.py`) and the routing redone from the state after step 5:
the locked copper of 8803cd2 (323 tracks and 17 vias: the USB pairs, `out/hand_routes.txt` and the power runs,
without the GND stitching vias and without the seven crossing nets), then the 17 crossing and dev-kit nets (MIC_IN,
NTC_NODE, VM_SENSE, PRE_B, BTN_HI, OV_G, OV_REF, OV_B, OV_C, OV_K, DEV_B, DEVKIT_PWR, PRE_G, PRE_C, PRE_D, LED5_A,
LEDS_A) with mazeroute, one round with no clash (248 tracks, 27 vias), locked. Two full attempts from there:

1. Freerouting 1.9, 45 passes (47 minutes), left 43 open signal connections; `mazeroute.py --only NET` net by net
   (kept only when the open count went down with no copper error) took that to 22; a second net-by-net pass with the
   other long nets protected closed none. The R419-to-C407 link of VDEV_F, which the router could not make at the
   2 mm class width, went in by hand at 1.0 mm (`out/hand_routes.txt`): 21. This is the board here.
2. To give the J12 nets a way into the Pico from the south on the top, the VSYS_SW front branch was taken to the
   bottom for X 99.0-110.9 under the Pico's south edge (two 1.2/0.6 vias) and R603 moved beside U601 to clear that
   bottom run. The six J12 nets were routed first, as a bus kept on the top by router guides except where it crosses
   SERVO_V and inside the hub and the Pico (16 negotiation rounds for four of them, one more run for J12_3V3 and
   J12_SCL), and locked; then the 17 crossing nets around it (15 routed; OV_C and OV_G left with 2 clashes after
   12 rounds); then Freerouting (45 passes, 48 minutes) left 55 open connections and the net-by-net pass 37, on 29
   nets. The bus has to cross the hub area to reach the Pico's south edge, and there it closed off the console and
   hub nets (CON_TX and J14_CON_RXD found no path at all). Worse than attempt 1, so attempt 1 was kept and the R603
   move and the VSYS_SW change were taken back.

What is left on attempt 1 (21 connections on 19 nets; the numbers in brackets are how many pieces of other nets the
net's best path crossed in the net-by-net pass):

- The J12 bus, 64 to 101 mm from J801 to the resistors under the Pico: J12_SDA (11), J12_SCL (10), J12_JETSON_UP (13),
  J12_ESTOP_OK (14), J12_LIDAR_REQ (4). Under the Pico there is room, but the way in is only between the Pico's pins
  (one track per 2.54 mm gap and layer, the same gaps J802 uses) or across its south edge, where the VSYS_SW front
  branch runs on the top at Y 30.45 from X 96.6 to 115.4 and the bottom holds R603, R705, R807, R1001 and the locked
  BTN_HI and DEVKIT_PWR tracks.
- Long runs from the rear connectors to the Pico through the same strip: +5V (R409 to U302 pin 10; 5), BUTTON_N (12),
  CHG_PRESENT_N (5), LATCH_OFF (23), PICO_VSYS (20), SERVO_IN_J (19), SERVO_SIG (R410 to J406; 13) and three
  pieces of +3V3 (to R203 and R1001; the router found no path for them, even at 0.25 mm).
- Short connections boxed in around the Pico's south and east sides: J14_RECOVERY_N (J802 pin 10 to SW801, 13 mm; 8),
  J14_CON_RXD (J802 pin 3 to R602; 3), JETSON_3V3_SENSE (R807 to R806, 9 mm; 10), LIDAR_REQ (R811 to Pico pin 27,
  8 mm; 2), LID_G (R422 to Q405's gate track, 5 mm; 4), HUB_VBUS (C603 to the hub, 17 mm; partly routed).

### Why four layers

Both two-layer attempts end at the same wall: with J802 pinned 4.6 mm west of the Pico, two layers do not have room
for the J12 nets, the rear-connector nets and the J14/hub nets to all reach the Pico. And the ground fill round the
Pico (574 mm2 on the top, 734 mm2 on the bottom on attempt 1, with J408's DEV- pad in it) touched the pack ground
nowhere: no spot where it lay over the main ground on the other side with room for a via, and no path even for a
0.6 mm ground track through the finished routing. The dev kit's 5 A return had no ground path. Moving J802 would
have meant moving six pinned parts (U401, Q503, MOD401, TP501, TP802, TP403); a GND plane and a signal layer inside
fix both problems without touching the placement.

Tool changes (`tools/README.md`, step 5): the mazeroute reach fix, `DSN_CLASS_CLEARANCE` kept by mazeroute,
`--skip REF,...`, `--win NET,...`; `tools/hand_routes.py` is new.

## Routing, four layers (E2b, 2026-10-26)

1. Built from the placement above (`placer.py` for the copper JSON, then `build_pcb.py`; see "Regenerating" for the
   five parts `placer.py` moves when it runs again) with `COPPER_LAYERS = 4`, `LAYER_TYPES` (In1 a plane, In2 a
   signal layer) and `STACKUP`.
2. The locked copper of 8803cd2 again, unchanged and still locked (323 tracks, 17 vias: the USB pairs,
   `out/hand_routes.txt` and the power runs), with the MIC_IN/NTC hand pieces and the R419-C407 VDEV_F link, and the
   11 locked GND vias of the GND corner.
3. Freerouting 1.9 on everything else at once (In1 a plane, not routed; 45 passes and the optimiser, 18 minutes):
   4 open connections left (BAT to C302, ESTOP_IN, PRE_G twice), 0 copper errors.
4. `mazeroute.py --only ESTOP_IN,PRE_G,BAT`, one round, no clash, with the router guides and the BAT/VM solder mask
   openings given back to it as keep-outs (Freerouting's session import takes the guides off the board; a first try
   without them put a PRE_G via and a BAT track inside the mask openings).
5. Ground: every through-hole GND pin is on the plane. 22 vias from `pad_vias.py --zone-islands` join small pieces of
   the outer GND fills; four bottom pieces under the Pico (with the GND pads of R704, R1003, C603 and C704) had no
   room for a via and got GND tracks to the nearest ground from `mazeroute.py --gnd-pads` (it moved 11 pieces of
   other nets to make room; one BAT_SENSE via pair it left 0.27 mm apart was routed again). `finish_pcb.py` then put
   284 GND stitching vias between the outer fills and the plane (62 on a 3 mm grid, 222 more on a 1.5 mm grid), where
   a via lands in GND on F, In1 and B and clears In2's copper.

Tool changes for four layers (`tools/README.md`): `build_pcb.py` writes `layout.STACKUP` into the board (KiCad 7's
Python has no stackup API); `finish_pcb.py` stitches through an inner signal layer that has no GND fill, clearing
its copper; `pour_resistance.py --cu-um-inner` (1 oz inside); `fab_outputs.py` writes the inner layers' Gerbers and
renders.

## High-current path

`pour_resistance.py` on the final four-layer fills (`dump_board.py --fills BAT,VM,GND`), 0.1 mm grid, 70 um copper
outside and 35 um inside (`--cu-um 70 --cu-um-inner 35`), 90 A. Copper only (no FET leads, solder or wire). "Peak" is
the highest current per mm of copper width on the grid, at a pad edge or a corner; "p99" is the 99th percentile.

| Path | Resistance | Drop at 90 A | Peak current density | Narrowest copper |
| --- | --- | --- | --- | --- |
| BAT pour: J101 (pack +) to the three FET drains | 0.196 mOhm | 17.7 mV | 23.5 A/mm at Q301's drain pin (18.6, 60.6), p99 6.5 | 36.8 mm (cut across the pour at Y 75.5) |
| VM pour: the three FET sources to J901 (ESC+) | 0.391 mOhm | 35.2 mV | 27.3 A/mm at Q301's source pin (21.0, 58.4), p99 9.5 | 11.6 mm (the ESC+ strip, cut at X 9.0) |
| GND: J902 (ESC-) to J102 (pack -), all four layers | 0.025 mOhm (two layers: 0.037) | 2.3 mV (3.3) | 8.8 A/mm on F and B at (7.8, 59.0), 4.2 A/mm on the In1 plane at (7.0, 59.0) (two layers: 10.7 A/mm) | 12.9 mm top (cut at Y 60.6), 13.1 mm bottom (Y 57.0), plus the plane |
| Whole path J101 to J901, each FET at its 1.3 mOhm maximum | 1.035 mOhm | 93.2 mV | 22.1 A/mm by J101 (23.2, 75.8), 24.5 A/mm at the ESC+ corner (13.8, 47.6) | |

In the whole-path run the three FETs share the current as 33.8 A (Q301, nearest the pack and ESC pads), 29.9 A
(Q302) and 26.3 A (Q303). On the 0.2 mm grid of the dry run the same path was 1.022 mOhm; the finer grid resolves
the corners better. The BAT, VM and whole-path rows are the same as on two layers (the top pours did not change, so
the narrowest-copper cuts were not measured again); the GND return gained the plane.

The dev kit's return, J408 (DEV-) to J102 (pack -) at 5 A (F401's rating): 0.976 mOhm, 4.9 mV, peak 1.2 A/mm on the
In1 plane at (85.0, 58.2), the corner of the BMS cut-out, 0.8 A/mm on the top and 0.7 A/mm on the bottom. J408 is
joined to the plane and both outer fills without thermal spokes. On two layers this path did not exist.

## DRC

`tools/drc.py` (KiCad 7.0.11, `boards/power/drc.rpt`), final board:

- 0 unconnected items (two layers, attempt 1: 21 signal connections and 9 ground pieces).
- 0 clearance, short, crossing, hole, edge, courtyard and solder mask bridge errors.
- Warnings (silkscreen only): 33 silk_overlap, footprint texts against footprint graphics: the heatsink's "HEATSINK =
  BAT+ INSULATE" over its own outline (9), the Pico's and the hub's printed labels ("USB", "USB HUB 5997", "P1"-"P3")
  over their outlines (11), the hub's "UP" against U601's reference, the "K" cathode marks of D401, D402, D404-D406,
  D501, D1001, D1002 over their body outlines (8), J407's "DEV+" (its sign, see "Markings") over its outline (2), "CAM
  REG" against J1001's reference, one circle over another; and 12 silk_over_copper (the J401, J901, J904, TP101 and
  TP301 references, two of the hub's labels, D101's "K", the heatsink text, two circles and one line touching copper).
  The fab clips silkscreen off pads and openings.
- Copper per layer: F.Cu 474 track segments (1214 mm, 50 nets), In1.Cu none (the plane), In2.Cu 545 segments
  (2209 mm, 57 nets), B.Cu 925 segments (1799 mm, 116 nets); 1944 segments in all. 435 vias (412 at 0.8/0.4, 11 at
  1.0/0.5, 12 at 1.2/0.6), 317 of them GND: 284 stitching, 22 joining fill pieces, the 11 of the GND corner. Fills:
  In1 GND plane 8228 mm2, top GND 4076 + 409 mm2, bottom GND 3498 + 2600 mm2, BAT 1356 mm2, VM 1088 mm2.

## Markings

Three fiducials (top), board name, revision and date "ATLAS-PWR-1 rev B  2026-10-26" (top at 34.0, 38.0 and
bottom at 30.0, 38.0), "FET bar is at pack voltage" next to the FET row across from the bar (the heatsink footprint
also carries "HEATSINK = BAT+ INSULATE"), + and - beside the pack, ESC, BEC and dev-kit wire pads, and a pin-1 dot
beside every polarised top-side part that has room (59 dots; D702 and J1002 have none, no room). Where a wire pad had
no free side for its sign, the pad's name with the sign ("BAT+", "SRV+", "SRV-", "DEV+") replaces the reference
(J101, J404, J405, J407). The bottom carries the board name, a serial number box and "bottom: 1206/1210 chips,
solder these first", reading correctly from below.

Bottom chip references (E2b): 69 of the 107 bottom parts have their reference on B.Silkscreen (0.8 mm text, placed
after the markings, each where it clears pads, other text and outlines, by `finish_pcb.py`'s silk pass). The other
38 had no free spot and stay on B.Fab: C1001, C303, C402, C407, C603, C702, C704, R1001, R1003, R1004, R203, R314,
R316, R401, R402, R411, R412, R413, R417, R421, R422, R501, R503, R506, R602, R603, R705, R806, R807, R811, R812,
R813, R814, R815, R903, R904, R905, R906 (mostly the parts packed under the Pico and the hub). The fab layer is in
the gerbers (atlas_power-B_Fab.gbr) and can be printed as the assembly drawing for those.

## For the reviewer

- Before ordering: the KiCad 10 checks (last section), then a look at out/fab (14 files in the PCBWay zip: four
  copper layers, both masks, pastes and silkscreens, the outline, PTH and NPTH drill files, the Gerber job file with
  the stackup).
- The USB pairs: their locked parts are as at 8803cd2; the last few millimetres to the pins were made by the
  autorouter, as on two layers, and two of those ends now run on In2: 5.2 mm of P1_DM and 5.0 mm of P4_DM, their
  partners on F/B. No impedance control was asked for; the pairs (0.4 mm, 0.3 mm gap) now run over the In1 plane
  0.2 mm below F, so their impedance is lower than on the two-layer board.
- Power nets the autorouter put on In2 (1 oz), all short side branches: VSYS_SW 5.6 mm at 2.0 mm (Q405 to the
  camera polyfuse F403, 0.75 A hold), CHG_GND 3.5 mm at 2.0 mm (to the TP502 test point), PRE_D 4.1 mm at 1.0 mm
  (precharge), V5_IN 21.1 mm at 1.0 mm (R408 to U401 and D401), +5V 162.5 mm at 1.0 mm. The main supply runs are the
  locked ones on F and B.
- Review m19 (10 AWG pads): J101, J102, J901 and J902 are 7.5 mm pads with 3.5 mm holes and a ring of six 0.6 mm
  plated holes, joined solid (no thermal spokes) to their 2 oz pours: J101 to BAT and J901 to VM on the top, J102
  and J902 to GND on both sides. That is right for 90 A and is exactly why they are slow to heat: the build guide's
  hot plate at about 100 C or 100-150 W iron (docs/BUILD_POWER_BOARD.md, tools and step 11) is needed; the README's
  assembly order now says so too.
- Review m20: done, numbers under "What changed".
- Tracks below their class width (lengths in mm on the final board; every signal is at its class width now, the
  0.25 mm pieces of the two-layer board are gone): SERVO_V 2.0 mm (60.9), 1.9 mm (26.6), 1.6 mm (8.8, the neck at
  H1003), 1.0 mm (2.7, the TP403 stub); VSYS_SW 1.0 mm (75.3, the front branch to the lidar and camera; 3.95 A at a
  10 C rise for 2 oz by the IPC-2221 outer-layer formula) and 0.5 mm to the sense and gate parts (18.1); CHG_RB
  1.2-1.3 mm (51.3) and 0.5 mm (9.3); VDEV 1.0 mm (31.5, the C405 branch); VDEV_F 1.5 mm (11.0, the D404 branch),
  1.0 mm (2.2, the R419-C407 link) and 0.5 mm (9.9, short links to the cut-off parts); CAM_VIN 1.0 mm (23.7), LID_SW
  1.0 mm (13.9), LIDAR_V 1.0 mm (11.7); CHG_IN and CHG_GND 0.5 mm only on the branches to the PD-trigger decoupling,
  Q502/Q503 and their resistors (the charge current path itself is 2 mm); VM 0.4 and 0.3 mm (37.2 and 13.8, the sense
  links); BAT 0.4 mm (2.6, R401), 0.6 mm (1.7, C104's hand link) and 1.6-1.9 mm stubs (3.2) by C301/C302 and R309.
- The build guide (docs/BUILD_POWER_BOARD.md, step 2) says the bottom silkscreen shows each chip's reference: true
  for 69 of the 107 bottom parts now, not for the 38 listed under "Markings". The guide should say so, or point to
  the B.Fab layer for those.

## PCBWay quote (instant quote, pcbway.com, 2026-10-26)

4 layers, 130 x 84 mm, FR-4 S1000H TG150 (PCBWay's default for 4 layers), 1.6 mm, 8/8 mil track/space, 0.3 mm
minimum hole, green mask, white silkscreen, HASL lead-free, tented vias, no impedance control, 4-5 day build, DHL to
the US (USD 26.55, 2-4 business days; shown ship date 2026-10-31, delivery 2026-11-03). Customs duties and VAT not
included; the final price is subject to PCBWay's review of the files.

| Copper | 5 pcs | 10 pcs |
| --- | --- | --- |
| 2 oz outer, 1 oz inner (this stackup) | USD 155.79 + 26.55 = 182.34 | USD 173.32 + 26.55 = 199.87 |
| 1 oz everywhere (for comparison) | USD 82.63 + 26.55 = 109.18 | USD 95.30 + 26.55 = 121.85 |

The two-layer quote at 8803cd2 (2 oz) was USD 50.09 + 26.55 for 5 and 60.25 + 26.55 for 10.

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
- If `placer.py power` runs again (it also writes the copper JSON that `build_pcb.py` reads), it moves R412, R419,
  R1001, C704 and C407 even with `KEEP_AUTO`: keep the copper JSON it writes and put `out/atlas_power_placement.json`
  back from git. The stackup in the board file comes from `layout.STACKUP` (`build_pcb.py`); KiCad keeps it on save.
- Do not use `fab-power` for the order: it deletes out/fab first and writes KiCad's own set (both CPL sides, a BOM
  from the schematic, a zip with every layer). The files in out/fab come from `tools/fab_outputs.py power` (plain
  Python around kicad-cli, KiCad 7 or later, no schematic needed); run that again after any change to the board.
