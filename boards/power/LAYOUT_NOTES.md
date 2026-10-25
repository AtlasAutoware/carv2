# ATLAS-PWR-1 rev B: layout notes (agent E)

Status: skeleton. The board in this folder is a dry run on the 23b0746 placement; the review's copper changes
(docs/review_revb_2026-10-24.md: CHG_GND, USB-A receptacles, ground resistors, Q402 gate capacitor) go into
`design.py` first, then the board is rebuilt and routed. Sections marked "pending" are filled from that run.

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

Copper:

- The VM pour reaches down to Y 36.5 between X 13.9 and 54 (nothing is placed there on the top). The corner where
  the motor current turns west into the ESC+ strip was 8 mm wide; it is now 11 mm. On the dry-run fills this took
  the BAT-to-ESC+ path from 1.078 to 1.022 mOhm and the peak current density at that corner from 25 to 20 A per
  mm of copper (`pour_resistance.py`, 0.2 mm grid, 90 A).
- Review m20: solder mask open over the BAT and VM pours (pending, patch ready).

## Net classes and rules

| Class | Width | Clearance | Via | Nets |
| --- | --- | --- | --- | --- |
| Default (signals) | 0.3 | 0.25 | 0.8 / 0.4 | everything not below |
| Supply | 2.0 | 0.3 | 1.2 / 0.6 | VSYS_SW, VDEV_F, VDEV, LID_SW, LIDAR_V, CHG_IN, CHG_OUT, CHG_RB, CAM_VIN, BAT (its routed feeds) |
| Servo | 2.5 | 0.3 | 1.2 / 0.6 | SERVO_V |
| Pulse | 1.0 | 0.3 | 1.0 / 0.5 | PRE_D, PRE_F, V5_IN, VM |
| Rail5 | 1.0 | 0.25 | 1.0 / 0.5 | +5V, HUB_VBUS |
| Power | 0.6 | 0.25 | 0.8 / 0.4 | +3V3, PICO_VSYS, CON_3V3, SW_GATE, SW_G1-3 |
| USB | 0.4 | 0.25 | 0.8 / 0.4 | P1-P4 D+/D-, routed as coupled pairs (0.4 mm, 0.3 mm gap) before the autorouter |
| BMS | 0.3 | 0.3 | 0.8 / 0.4 | BMS_VDD, BMS_TXD, BMS_RXD, BMS_GND, BMS_OPT1_A; 2 mm to every other net (DRU rule, and a class_class rule for Freerouting) |

Board floors (PCBWay capabilities page, Oct 2026, 2 oz normal process): 0.2 mm clearance (8 mil), 0.25 mm track,
0.8 mm via, 0.15 mm annular ring, 0.3 mm drill, 0.4 mm hole to hole, 0.3 mm copper to edge. KiCad's TO-92 land
pattern has 0.22 mm between pads and a 0.15 mm ring; a DRU rule allows 0.2 mm between the pads of each TO-92 part.

## Routing (pending)

## High-current path (pending final numbers)

## DRC (pending)

## Markings

Three fiducials (top), board name, revision and date (top and bottom), "FET bar is at pack voltage" next to the
FET row across from the bar (the heatsink footprint also carries "HEATSINK = BAT+ INSULATE"), + and - beside the
pack, ESC, BEC and dev-kit wire pads, and a pin-1 dot beside every polarised top-side part that has room.

## For the reviewer (pending)

## Regenerating on the laptop (KiCad 10, run_kicad.sh) (pending)
