# TPS25751D configuration (USB-C PD sink + BQ25798 charger)

The drive board's PD controller (U701, TPS25751DREFR) does nothing useful until it has a
configuration: its ADCIN pins select SafeMode (ADCIN1 = LDO_3V3, ADCIN2 = GND), so the sink path
stays off and USB PD stays disabled until one loads (TI SLVSH93A, section 8.4.1). The
configuration also tells it how to program the BQ25798 charger (U703, 0x6B on the controller's
own I2C bus). It lives in the M24512 EEPROM (U702, 0x50 on that bus).

This page lists what to enter in TI's **TPS25751 Application Customization Tool** (a web tool
on dev.ti.com, TI account needed) and which files to export. The tool's exact screens are not
described here because nobody on the team has used it yet; the values below come from the
board design (`boards/drive/design.py`, block G_CHARGE) and the pack.

## Files to export

- **Full Flash binary**: the whole EEPROM image, region headers included. Written once per
  board: `atlas pd flash` (docs/FLASHING.md, step 6). TI's EEPROM application note (SLVAFL1):
  "The external EEPROM shall be programmed with a Full Flash binary the very first time".
- **Low Region binary**: the configuration bundle alone. Used to run the configuration from RAM
  while the EEPROM is blank (`atlas pd load`, and at every boot through `atlas pd ensure`) and
  for later updates (`atlas pd update`).

Export both from the same session, name them `tps25751_full.bin` and
`tps25751_lowregion.bin`, and commit them to `firmware/tps25751/` with a note of the tool
version. `atlas pd flash` checks that the Low Region binary sits inside the Full Flash image
where TI's layout puts it, which catches files from different sessions.

## Settings

| Setting | Value | Why |
| --- | --- | --- |
| Port role | Sink only | The board never sources (design.py, the PP5V capacitor: "sink-only board: never sourced"). |
| USB data | None through the PD controller | D+/D- go straight to the USB2514B hub; the controller only handles power. |
| Sink PDOs | 5 V 3 A, 9 V 3 A, 15 V 3 A, 20 V 3.25 A | 20 V is the highest the board takes: SMF24A TVS (24 V standoff) and 25 V capacitors on VBUS. No PPS, no EPR. 3.25 A matches the Anker 715 (A2663, 65 W) on the parts list. |
| Battery charger | BQ25798 (listed as supported on page 1 of SLVSH93A) | I2C address 0x6B on the controller's I2C bus. |
| Cells in series | 4 | 4S3P Molicel P28A. The PROG resistor (17.4k) already sets 4S at power-up. |
| Charge voltage | **16.4 V** (4.10 V per cell). Judgment call, see below | The BMS (BQ7791508) cuts at 4.20 V per cell. Charging to 16.8 V leaves no margin for cell imbalance, and the BMS would cut the charge at the end. |
| Charge current | **3.75 A** (1.25 A per cell). Judgment call | docs/ARCHITECTURE.md plans about 60 W into the pack with the car off (about 2.5 h from empty). BQ25798 allows up to 5 A. |
| Input current limit | 3.25 A | Same as the ILIM_HIZ resistors (39k / 100k). A lower value from the PD contract wins automatically. |
| Precharge / termination | Tool defaults | |
| Battery temperature (TS) | Ignore / fixed | TS sees a fixed 25 C divider; the pack NTC goes to the BMS. |
| GPIO0-GPIO7 | **Unused, never outputs** | All eight are tied to GND on the board. A GPIO configured as a driven-high output would short. GPIO11 is not connected. |
| I2C target interrupt | Not needed | PD_IRQ_N has a pull-up but goes nowhere. The Jetson polls. |
| Liquid detection, BC1.2, source features | Off | Not on this board. |

**Charge voltage.** 16.4 V gives up some capacity (for Li-ion cells, stopping at 4.10 V instead
of 4.20 V typically costs around 10 %; not measured on the P28A). 16.6 V (4.15 V per cell)
is the highest value that still leaves some margin under the BMS trip. Ragini or Eshan decide;
16.4 V is the safer starting point.

**Charge current.** 3.75 A is the design figure; the P28A's own charge limits are in Molicel's
data sheet and must be checked before raising it.

## After programming

`atlas pd status` should show mode `'APP '` and "EEPROM found". With the Anker charger plugged
in: `VBUS PD contract`, and `atlas battery` shows a negative current (the pack charging) when
the car's own load is below what the charger delivers.
