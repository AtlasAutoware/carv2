# ATLAS-PWR-1 rev B: design fixes from the pre-order review (2026-10-24)

Status: done. The fixes from `docs/review_revb_2026-10-24.md` assigned to the design are in `design.py`,
`chips_power.py`, `layout.py`, `netcheck.py`, `PINMAP.md`, `README.md`, `HANDOFF_E.md`, `NOTES.md` and
`bom/revb`. Layout: rebuild the PCB from `out/atlas_power_placement.json`.

Regenerated: `atlas_power_parts.json`, the 10 schematic sheets, `out/atlas_power_placement.json`,
`out/atlas_power_copper.json`, `out/placement.png`, `bom/revb/power_board_bom.csv` and `power_board_cost.md`.

| Check | Result |
| --- | --- |
| `build_sch.py power` | 215 parts (was 206), 133 nets, 10 sheets |
| `check_fp.py power` | 48 footprints, 0 problems |
| `placer.py power` | 215 placed, 118 explicit, 0 unplaced, 0 conflicts, board still 130 x 84 mm |
| `netcheck.py` | 0 errors, 14 warnings (10 as before, 4 new: 2.7 mA into the dev kit's 1k-fed pins while it is off, see NOTES 16) |
| firmware tests (`firmware/supervisor`, reads PINMAP.md) | 119 passed |
| cost | USD 149.37 per board (was 140.67), USD 11.30 of it not verified (unchanged) |

## Refs

No existing ref changed: the new parts sit at the end of their blocks.

New: C407, C502, D406, J410, R316, R604, R905, R906, TP502.

## Changes

| Review item | Change | Refs |
| --- | --- | --- |
| B1 | New net CHG_GND: MOD501 GND, MOD502 IN-, D501 anode, C501, Q502 and Q503 emitters, R504, R506, test pad TP502. MOD502 OUT- is on GND and is the only link (inside the module, its current shunt). Netcheck rule [14] checks it; the DC model has a 0.05 Ohm shunt in the module. CHG_GND is in net class Supply (2.0 mm) | MOD501, MOD502, D501, C501, Q502, Q503, R504, R506, TP502 |
| B1 | README: 5-minute bench check of the module in hand (20 V in, 4.7 Ohm load, measure IN- to OUT-). No high-side module could be verified, so none is named | - |
| M1 | 10k to 1k on the four board outputs toward the dev kit: FSESC TX to J12 pin 10, ESTOP_OK_TO_JETSON to pin 33, CHG_STAT_N_TO_JETSON to pin 32, console TX to J14 pin 3. Rule [6] asks for 1k on the three J12 outputs; rule [13] allows up to 3 mA (warning) into those pins with the dev kit off. R803, R809, R811, R603, R806 stay 10k | R804, R812, R813, R602 |
| M2 | IRF4905PBF (TO-220, G-D-S, -55 V, 20 mOhm at -10 V, USD 2.71 Mouser via findchips) in place of the IRF9Z34N; lower gate resistor 10k to 6.8k (VGS -7.1 V at 12 V, -10 V at 16.8 V, -17.9 V at 30 V). OV trip 18.7 V (was 18.6), release 17.85 V | Q402, Q501, R412, R502 |
| m5 | 100 nF gate-source on both P-FETs (about 0.4 ms soft start) | C407 (Q402), C502 (Q501) |
| M3 | Alternative BEC input pad on VSYS_SW, placed at (63.6, 34.45); BEC+ (J401, VM) stays the default. README test 2 step 7: the real-load precharge test, then the pad or R313 at 4.7 Ohm 5 W (Yageo SQP500JB-4R7, same body) | J410 (new), R313 note |
| M6 | FSESC signal grounds through 1206 resistors: COMM pin 2 (net COMM_GND) 3.3 Ohm, servo-lead ground (SRVIN_GND) 3.3 Ohm, FSESC USB ground (VUSB_GND) 2.2 Ohm. Rule [14] checks each has exactly one resistor to GND | R905, R906, R604; J903, J904, J602 |
| M7 | J601 (hub port 1, dev kit) is a Wurth 614004134726 through-hole USB-A on its edge, footprint `Connector_USB:USB_A_Wuerth_614004134726_Horizontal` (pads 1 VBUS, 2 D-, 3 D+, 4 GND, four shell pads 5 = GND), at the Y = 0 edge between the hub and the power button, opening facing -Y. J602 (FSESC) stays 1x4 (see disagreements); J603 unchanged. README documents the direct-cable fallback for flashing | J601 |
| m1 | 100k to 2.2M gate-source pull-down; README test 2 checks SW_GATE - VM >= 10 V at 12 V | R304 |
| m3 | 100 nF to 10 nF (KEMET C1206C103K5RACTU), 0.1 ms; no 74HCT132 | C1001 |
| m4 | P6KE20A to P6KE22A (Taiwan Semiconductor, USD 0.45 converted from a Newark price in CAD); D401 on the R-78E input stays P6KE20A | D404, D405 |
| m6 | NTC node separated from GP28 by 10k (new net NTC_NODE: TH301, R314, R316; FET_NTC: R316, C304 at the pin) | R316 (new), TH301, R314 |
| m9 | 10 Ohm to 4.7 Ohm (Vishay MBB02070C4708FCT00, 0.6 W); D401 takes about 2 A on a 30 V spike (netcheck) | R408 |
| m12 | README "Settings that must be made": BMS over-voltage 4.25 V, CC/CV 16.80 V / 2.5 A, VESC max input 18 V (m4), VESC battery cut-off 13.4 to 12.6 V (m9) | - |
| m18 | P6KE22A fitted at the camera regulator input | D406 (new) |
| m22 | `design.py` block A: the pack carries the XT90-S female (the anti-spark half; meter-check), the board pigtail an XT90 male. DIP sockets are BOM lines (TE 1-2199298-2 for U301, 1-2199298-3 for U302 and U601). HANDOFF_E.md connector table: fan, ESC pads, camera wiring and the new parts | - |

## Placement changes in layout.py (on top of agent E's file; every agent E edit kept)

| Part | Was | Now |
| --- | --- | --- |
| J601 USB-A | pin 1 (100.6, 13.4), 1x4 | pin 1 (102.8, 12.83) rot 90: body X 98.5-107.1, Y 0-20.7 |
| J602 FSESC header | pin 1 (104.5, 13.4) | pin 1 (109.3, 19.85), pins down to Y 12.23 |
| SW801 recovery | centre (102.65, 19.8) | (102.87, 25.8), just south of the Pico |
| D701, D702 LEDs | (109.9, 18.3), (109.9, 23.1) | (119.75, 8.06), (119.75, 2.82) rot 90, at the Y = 0 edge beside the power button |
| F402 lidar polyfuse | (102.0, 27.6) | (116.66, 24.05) |
| D405 lidar TVS | (115.0, 27.4) | (110.07, 25.71) rot 90 |
| TP702 PICO_RUN | (107.6, 28.4) | (113.77, 27.7) |
| TP401 VSYS_SW | (62.4, 32.6) | (62.05, 29.14), to make room for J410 |
| J410 BEC+ALT (new) | - | pin (63.6, 34.45) |
| D406 camera TVS (new) | - | (125.75, 71.96) rot 90 |
| R314, R316 (bottom) | R316 pinned at GP28 | R316 (series) stays at (112.85, 66.0); R314 (divider top) pinned at (112.85, 60.6) |
| R1003 (bottom, 10k ESTOP_OK pull-down) | auto | pinned at (102.75, 37.05) beside C1001 (the auto placer could not find it a spot any more) |

Also in layout.py: value lookups updated (C1001 '10n', Q402/Q501 'IRF4905PBF', D404/D405 'P6KE22A', R408 '4.7'),
CHG_GND added to net class Supply, 'BEC+ALT' added to WIRE_SIGNS, and the floorplan sketch.

## For the layout agent

- `out/atlas_power_geom.json`: I removed the J601 entry (backup in my scratchpad). `placer.build_library` keys the
  dumped geometry by the part's current footprint, so the old 1x4 geometry was being written into `fp_lib.json`
  under the USB-A footprint id. The next KiCad dump puts the right one back. Any later footprint change on an
  existing ref has the same trap.
- `out/usb_routes.json` no longer fits ports 1 and 3 (new pin positions in HANDOFF_E.md; port 1 arrives in the
  opposite D+/D- order).
- Put R604, R905 and R906 at their connector pins; COMM_GND, SRVIN_GND and VUSB_GND must not touch a GND pour.
- The FIDUCIAL_NEAR spot (121.0, 4.5) is now beside D701/D702; marks() searches outward, so it should find room.

## Not changed, and why

- **J602 stays a 1x4 header (review M7 asked for a USB-A there too).** The Y = 0 edge between the hub (X 97.7) and
  the right-angle power button (X 108) has room for one receptacle. A second one would need the button moved off
  the pod window, and a stacked double USB-A has one shell for both ports, which ties the FSESC's USB ground to GND
  and undoes M6. The FSESC link is full speed (12 Mb/s), which the header and lead carry fine.
- **M3 as two pads, not a 3-pin jumper or solder bridge**: see NOTES; same function, nothing in the current path.
- **m3 with 10 nF, not a 74HCT132**: one value change, no new IC (NOTES).
- **No high-side CC/CV module named (B1)**: none could be verified from a published schematic.
- **`boards/outlines.json`**: its "power" entry already reads 130 x 84 mm, holes at (4,4), (4,80), (75,4), (75,80),
  (126,4), (126,80), no servo notch, which matches layout.py; nothing to change.

## Outside my files, still stale

- `docs/BUILD_POWER_BOARD.md`: lines 84-87 (D404, D405 P6KE20A; Q402, Q501 IRF9Z34N; R408 10 Ohm; J601 a 1x4 header;
  new parts missing), 124, 134-135 and 226 (four IRF9Z34N; now two plus two IRF4905), 191 (R408), 212 (J601),
  474 and 497 (dev-kit cable through an Adafruit 4449 lead; now one USB-A to USB-C cable).
- `firmware/supervisor/pins.py` lines 38-39: GP19 and GP20 "through 10 k" (now 1k).
- `mech`: a window or clearance for the dev-kit USB-A plug at car x 70.8 on the pod side (HANDOFF_E.md); the
  charge_usbc window placeholder sits there now.
