# Car 2 rev B electronics: independent pre-order review (Oct 24, 2026)

Reviewed: branch `rev-b-tht` at 23b0746 (design, firmware, software); commit b101e53 added only docs. The layout in
progress was not reviewed. The reviewer had not seen the design being made. Scenario runs used the team's own
firmware simulator (`firmware/supervisor/sim.py`).

## Verdict

Fix first, then order. No redesign is needed.

The architecture is sound and most of rev A's lessons have landed. Nothing on the board references the BMS's B-
except through the two optocouplers, so the INA228-class fault is gone. The pack bus has real bulk capacitance. An
E-stop under 90 A is benign because the FSESC's own bus capacitors hold VM while the FETs turn off. Every IC pin
stays inside its absolute maximum at 16.8 V, at 20 V charger input and in the 30 V case.

Before boards are ordered: one blocker, seven majors (three need small copper changes: a through-hole USB-A for the
dev kit's hub port, series resistors in the grounds facing the FSESC, a gate capacitor on Q402), the rest are part or
value changes plus three firmware changes. Three bench tests before ordering: drive J12 pin 10 through 10 kOhm on the
real dev kit; precharge the real FSESC and Castle BEC through 10 Ohm; check the CC/CV module's current-sense topology.

| ID | Sev. | Finding | Fix (where) |
| --- | --- | --- | --- |
| B1 | BLOCKER | MOD502 IN- and OUT- (and MOD501 GND) are all on board GND. The usual XL4015 CC/CV module senses current with a shunt between IN- and OUT-, so constant-current limiting is lost. Charging then runs at whatever the 60 W PD source gives (about 4 A), with Q501 at about 2-3 W and no heatsink. | Specify a module with high-side sensing (confirm from its schematic), or split a CHG_GND net (MOD501 GND, MOD502 IN-, D501, C501 and the D502 detector) so that MOD502 OUT- is the only tie to GND |
| M1 | MAJOR | The 10 kOhm series resistors drive the dev kit's level-shifted inputs: R804 (FSESC TX to J12 pin 10), R812 (pin 33), R813 (pin 32) and R602 (console TX to J14 pin 3). A TXB-type translator holds its pin through about 4 kOhm, so a 10 kOhm driver only reaches 0.94 V and the input never toggles. The Jetson would get no VESC telemetry. | Change those four to 1 kOhm and update netcheck rule [6]. First, a 5-minute test on the dev kit |
| M2 | MAJOR | The IRF9Z34N in the dev-kit feed (Q402) and the charge reverse block (Q501) only gets VGS = -V/2: -6 V at 12 V, on a part rated at -10 V with Vth up to -4 V. At 3 A that is 1.4-2.3 W in a TO-220 with no heatsink, a rise of 85-140 C. | IRF4905PBF (same G-D-S, 20 mOhm, Mouser $2.70) and R412/R502 at 6.8 kOhm (VGS = -0.6 V). Copper: a 100-220 nF gate-source capacitor on Q402 |
| M3 | MAJOR | Precharge must reach 90 % of the pack through about 10.6 Ohm. The FSESC (booting) and the Castle BEC with the servo and 1000 uF already load VM. On the team's simulator, 150 mA fails at 12-14.4 V and 200 mA fails at 16.8 V: three tries, then FAULT, and the car never arms. | Firmware: done when VM >= BAT - 2.5 V and has stopped rising. Bench-test the real FSESC and BEC on 10 Ohm. If the BEC start-up collapses VM, move BEC+ to VSYS_SW (copper) or use 4.7 Ohm 5 W for R313 |
| M4 | MAJOR | 60 s without a heartbeat leads to HALTING and LATCH_OFF even while the Jetson's 3.3 V and JETSON_UP are high. A crashed daemon or a loose Pico micro-USB hard-cuts a running Jetson. Simulated: OFF 65 s after the last heartbeat with v33 still high. | Firmware: on heartbeat loss with v33 or JETSON_UP high, press the power key (`request_shutdown`) and do not halt. Halt only on HALT or when v33 drops |
| M5 | MAJOR | The 5 s long-press force-off pulses LATCH_OFF while the button is still held, which keeps the Pololu ON input at 2.0-2.8 V. The Pololu defines ON and OFF as pulses, not both at once. The latch likely comes back on, and the Pico then boots into its 3 s "REPL hold" with the car still on. | Firmware: at 5 s, drop MAIN, precharge, lidar and DEVKIT_PWR; pulse LATCH_OFF only after release. Bench-check the Pololu |
| M6 | MAJOR | Three FSESC signal grounds (COMM pin 2 to J903, the servo lead to J904, USB to J602) run in parallel with its ESC- lead. The 1 mOhm lead drops about 90 mV at 90 A, which pushes about 1-2 A through the JST-PH COMM ground and about 0.5 A through the USB ground. A failed ESC- joint sends the whole motor current through them. | Copper: 2.2-4.7 Ohm 1206 (or a 0.1-0.2 A PTC) in series with the GND pins of J903, J904 and J602. Run ESC+ and ESC- as one strain-relieved pair |
| M7 | MAJOR | The 480 Mb/s path to the dev kit runs through the hub sockets, J601 pins, a 30 cm Adafruit 4449 Dupont lead, a USB-A jack and a cable. That is likely marginal for USB networking and flashing. | Copper: a through-hole USB-A receptacle in place of J601 (and J602), so the dev kit uses one normal USB-A-to-C cable. Document the direct-cable fallback |

## Blocker detail: B1

Where: `design.py` block E: MOD502 `{'IN-': 'GND', 'OUT-': 'GND'}`, MOD501 `{'GND': 'GND'}`. The pack's charge
return is board GND (P-), the same net. The common XL4015 CC/CV module (two trimmers, an LM358) regulates current from
the drop across a low-side shunt (about 0.05 Ohm) between IN- and OUT-. With IN- and OUT- both on board GND, the
return current reaches IN- through the board, the shunt carries none, and CC never engages. The set-up step in the
build guide works on the bench and silently stops working once the module is wired into the car. Consequence: about
3.5-4.5 A into a 13-15 V pack, Q501 at 2-3 W with no heatsink (150-200 C), the module past its 3 A rating, the 5 A
blade at 80-90 % load, possibly a hiccuping PD charger, all during unattended charging. Fix: (a) a module whose
schematic shows high-side sensing (note the MPN), or (b) split the ground: the PD charger's output is isolated, so
MOD501 GND and MOD502 IN- go on a new CHG_GND net, MOD502 OUT- is the only connection to GND, and D501, C501 and the
D502/Q502/Q503 detector reference CHG_GND. Quick check on the module in hand: run it from 20 V into a 4.7 Ohm power
resistor and measure IN- to OUT-; about 0.1 V means a low-side shunt.

## Major detail

M1. On NVIDIA forums, Jetson staff say the 40-pin UART and GPIO pins go through a level shift with load requirements;
the Nano and AGX Xavier dev kits use TI TXB0108 auto-direction translators there. A TXB holds each port through about
4 kOhm, so through 10 kOhm the pin reaches 3.3 x 4/14 = 0.94 V from a held low and never crosses VCC/2. With 1 kOhm
it reaches 2.64 V, above VIH of about 2.15 V. The Jetson-to-board direction is fine. Test before ordering: a 3.3 V
USB-UART through 10 kOhm into J12 pin 10 at 115200 while `cat /dev/ttyTHS1` runs on the dev kit.

M2. IRF9Z34N: RDS(on) 0.10 Ohm maximum at -10 V, VGS(th) -2 to -4 V, RthJA 62 C/W. At -6 V, with a high-threshold
part, at 100-125 C, estimated 0.15-0.25 Ohm. Dev-kit current 3.0 A at 12 V (25 W mode), up to 3.75 A in MAXN:
1.35-2.25 W at 12 V, a rise of 84-140 C under the tray. IRF4905PBF: TO-220 G-D-S, -55 V, -74 A, 20 mOhm at -10 V,
plus or minus 20 V gate, same footprint; with R412/R502 at 6.8 kOhm, VGS = -7.1 V at 12 V, -10 V at 16.8 V and
-17.9 V at 30 V.

M3. Simulation on `sim.py` with the VM load raised (the sim assumes 50 mA): 12.0 V and 14.4 V packs pass at 50 and
100 mA, fail (slow, retry, FAULT) at 150 and 200 mA; 16.8 V passes up to 150 mA. The limit is a 1.2 V drop, 110 mA
at 12 V. Closing the switch onto a 2.5 V step into 2 mF is 6 mJ, spread over milliseconds by the slow MIC5014
turn-on. Bench test: 12 V supply, 10 Ohm, the real FSESC, the Castle BEC set to 7.5 V, the servo and 1000 uF, scope
on VM.

M4. Safety does not need the cut: the VESC's 250 ms UART timeout with 10 A brake already stops the car if the stack
dies. A hard power cut without a shutdown risks the NVMe and leaves a dead car mid-race.

M5. While the button is held, LATCH_ON sits at 2.0-2.8 V, above the Pololu's 1 V ON threshold. Pololu describes ON
and OFF as high pulses and warns that holding a control pin high may interfere with the others. The designer's own
NOTES item 7 forbids pulsing LATCH_OFF while the button is held.

M6. ESC- lead: 85-120 mm of 12 AWG plus two joints, about 1 mOhm, 90 mV at 90 A. Parallel paths: COMM ground about
40-80 mOhm (1.1-2.2 A at 90 A, against a JST-PH rating of 2 A), servo-lead ground 1-2 A, USB ground about
0.12-0.15 Ohm (0.6-0.75 A). A 2.2-4.7 Ohm 1206 in each drops the loop current to 20-40 mA and opens like a fuse if
ESC- fails. The FSESC USB is full speed only.

M7. NVIDIA's flashing instructions assume a direct cable; that it works through a hub is unverified. Keep "laptop
straight into the dev kit's USB-C" as the documented fallback for flashing.

## Minor findings

| ID | Finding | Fix |
| --- | --- | --- |
| m1 | R304 (100 kOhm, SW_GATE to VM) loads the MIC5014's charge pump (its output is plotted on a 1-1000 uA scale). At 10-15 V, R304 draws 100-150 uA, so VGS may settle near 10 V instead of 15 V. | 1-2.2 MOhm. In test 2, measure SW_GATE - VM >= 10 V at a 12 V pack |
| m2 | With IN low, the MIC5014 holds the gate low and its gate-source clamp zener conducts from SOURCE (VM): a few mA of drain on VM whenever VM is up with the switch off. Adds to M3. | Test 2: measure the current into U301 pin 3 with VM at 14 V and IN low |
| m3 | ESTOP_OK falls with a 1 ms time constant (R1003 10k, C1001 100 nF) into a 74HCT08 with no Schmitt input. A connector glitch can open the switch at the HCT's threshold without the Pico seeing an edge, and the slow MIC5014 turn-on recloses it under load. | 74HCT132 (Schmitt NAND, DIP-14), a Schmitt stage before the AND, or C1001 at 10 nF |
| m4 | D404 (dev-kit feed) and D405 (lidar) are P6KE20A, in the same 19.0-21.0 V band as the pack TVS D101 (1.5KE20A). In a sustained over-voltage the lowest-VBR device takes the current, possibly a 600 W part behind a 5 A fuse. | P6KE22A for D404 and D405. Mark the VESC 18 V maximum input voltage as a must-set |
| m5 | Q402 has no gate soft start: tens of amps for tens of us into C405 and the carrier's input capacitors. | 100-220 nF gate-source (copper) |
| m6 | TH301 is bent against the bar, which is at BAT+, with only Kapton between. A chafed coating puts the pack voltage onto GP28. | 10 kOhm between the NTC node and GP28, or a lug NTC under an insulating washer |
| m7 | `_battery()` skips both low-pack checks while CHG_PRESENT_N is low; the car on at 25 W plus lidar and camera draws about 40-45 W against 42 W of charge, so the pack can still reach the BMS cut. | Keep BAT_CUT active while charging, or suspend it only while the pack voltage is rising |
| m8 | In OFF, the firmware pulses LATCH_OFF every 500 ms forever and ignores the button. A Pico that survives on USB power switches the car off again within 0.5 s of every press. | In OFF, `machine.reset()` when BAT_SENSE comes back |
| m9 | Sag at low charge: pack plus harness about 30-45 mOhm, 2.7-4 V at 90 A. At 12 V open-circuit, VSYS_SW can reach 8-9.3 V, below the dev kit's 9 V and near the R-78E's 8 V minimum after R408. | Mark the VESC battery cut-off (13.4-12.6 V) as a must-set. R408 at 4.7 Ohm |
| m10 | The BMS optocouplers drive 4.7 kOhm loads at 9600 baud; rise time grows with load resistance and the LEDs saturate the transistors. Margin unknown at a 104 us bit time. | Scope the loop-back in bench test 1. Fallback: 1-2.2 kOhm loads, or an H11L1 Schmitt optocoupler |
| m11 | If the JBD port's VDD is 5 V while its TX idles at 3.3 V, U201's LED leaks about 0.5 mA and the Pico's RX may never idle high; R204 would pull the JBD's RX to 5 V. | Measure VDD and the TX idle level first. If they differ, drive the LED from TX to BMS_GND and invert in the RP2040 UART |
| m12 | BMS over-voltage set to 4.20 V equals the CV point (16.80 V), so the BMS ends charges whenever a cell runs high, and its open charge FET removes regen on a full pack. | BMS over-voltage at 4.25 V, CV at 16.80 V |
| m13 | The hub module carries 4 x 100 uF on downstream VBUS behind a 2 A PTC, so the laptop sees about 400 uF at plug-in. Laptops usually tolerate it. | Note only |
| m14 | Unverified whether the FSESC powers its MCU from USB VBUS, and whether that back-feeds VM. | With only the laptop connected, measure VM. If above 1 V, cut VBUS in the FSESC's USB lead |
| m15 | No reverse-polarity protection on BAT. A reversed pigtail puts D101 in forward conduction across the pack. | Guide: meter-check the pigtail and XT90 polarity before the first pack connection |
| m16 | A short press in LOCKOUT with the loop still open requests a shutdown. | Ignore the press, or log `rearm_refused` |
| m17 | Pololu notes the switch may turn on at power-up at high voltage. | Check on the bench; if seen, require a press after a cold boot |
| m18 | CAM_VIN has no TVS; the S18V20F12 is 32 V absolute maximum and Pololu warns about LC spikes. | Optional P6KE22A at the camera pads |
| m19 | The 10 AWG pads in 2 oz copper on big pours may not wet with a 70 W iron. | Preheat the board (hot plate at about 100 C) or use a 100-150 W iron for J101, J102, J901 and J902 |
| m20 | VM is a single 2 oz top pour, 12 mm wide at its narrowest: about 0.17 W per mm of length at 90 A, fine for 33 A average and 2 s pulses (estimate). | Leave solder mask open on the BAT and VM pours so they can be tinned or strapped. Thermal camera in test 3 |
| m21 | The ESC's input ripple reaches C101-C103 through the switch and leads. EEU-FR1V681 is rated about 2.18 A at 100 kHz each. TME lists it as 10 x 20 mm, `design.py` as 12.5 x 20; both fit the 5 mm pitch. | Log the capacitor temperature during test 3 |
| m22 | Documents disagree with the design: WIRING.md rev B still shows XT60PW/XT90 board-mounts, a camera 2-pin, a USB-C-to-C dev-kit cable and the fan header on the front edge; `boards/outlines.json` "power" is still 150 mm with holes at 146 mm; `pins.py` says the GP22 pull-up is 47 k (board: 10 k); `design.py` says the pack carries an XT90-S female, WIRING.md says male (the anti-spark only works with the matching half); the DIP sockets are not BOM lines. | Fix each |

## Checked and found fine

Absolute maximum ratings at 16.8 V, 20 V charger input and 30 V (netcheck re-run: 0 errors, 10 warnings; the rest
by hand): MIC5014 (V+ 60 V absolute, 30 V operating; IN and SOURCE from -20 V to V+; gate clamp 13-17 V above
SOURCE; non-inverting input), IRFB7430, IRF9Z34N, 2N3904/2N3906, PC817, TL431, R-78E (input 8-28 V), MCP1700, the
hub, Pico VSYS, the XL4015 module (about 34.7 V at most), S18V20F12 (32 V). Pin tables and footprints: MIC5014 DIP-8
(1 V+, 2 IN, 3 SOURCE, 4 GND, 5 GATE), PC817, TL431, MCP1700, the TO-220s, the R-78E, the Pico footprint (17.78 mm
rows), the Adafruit 5997 hub footprint against Adafruit's Eagle board (pin order VBUS, D+, D-, GND per port; only a
solder jumper on its underside), MF-R lead spacing, the 10 AWG pad. Ground domains: the JBD switches B- and the only
links from board GND to B- are U201 and U202; the charge current returns through the XT90 and the BMS common port;
the laptop, the Jetson, the camera and the lidar all reference P- only. No back-powering (HUB_VBUS reaches only the
hub ports and U602; D402 stops the Pico's USB from feeding +5V; CHG_PRESENT_N is open collector; pins 32 and 33 are
driven only while v33 is high). Reset and boot states (RP2040 pull-downs backed by 100 kOhm on the enables; the
74HCT08 output and MIC_IN low; GP22's 10 kOhm pull-up gives 2.75-2.9 V; VESC_KILL high only in RUN). E-stop opening
under 90 A (gates discharged in tens of us; VM held by the FSESC's capacitors; about 0.4 mJ in the FETs, 1.6 mJ in
the pack leads, 1.3 V into the 2 mF on BAT; the ESC lead's kick freewheeled by D301). Precharge energy (0.28 J per
start). Main-switch thermal (0.76 W total at 33 A; a 90 A pulse adds about 2 C to the bar). Dev-kit over-voltage cut
trips at 18.56 V and releases at 17.85 V. J12 reversal-safe; J14 optocoupler polarity and current fine. Firmware
matches the hardware polarity on every line; tests pass (supervisor 96, Jetson 74). Cost arithmetic matches
($140.67, $11.30 unverified); ten prices spot-checked; no part end-of-life or SMD-only.

## What netcheck.py cannot see

Time (its 30 V case is a DC operating point), the insides of the modules (B1, M5, the PD trigger fall-back, the hub's
400 uF, the FSESC's USB power path), real loads on VM (M3), the Jetson's level shifters (M1), current in GND (M6),
real RDS(on) and heat (M2), the MIC5014 charge pump and off-state clamp (m1, m2), firmware timing (M4, M5, m7, m8),
optocoupler speed (m10), footprints and copper.

## Could not verify

MIC5014 curves and off-state switch resistance; whether the Orin Nano carrier's J12 and J14 inputs use TXB-type
translators (the M1 bench test settles it); the CC/CV module's topology and input capacitance; FSESC Mini 6.7 Pro
input capacitance, idle current, COMM pin order, ADC2 divider, USB power path, and its 14 V rated floor at 12 V;
Castle BEC 2.0 start-up current; Pololu 2813 ON/OFF input impedance and ON-plus-OFF behaviour; PC817 response time
at the chosen loads; IRF9Z34N RDS(on) at -6 V; JBD UART port VDD and logic level; J12 pin 17 after `poweroff`;
dev-kit behaviour below 9 V; flashing through the CH334F; layout-dependent items.

Sources: MIC5014 data sheet (docs.rs-online.com/b032/A700000014314840.pdf), pololu.com/product/2813 and
/product/2577, adafruit.com/product/5997 and /product/4449, findchips.com (IRFB7430PBF, MIC5014YN, IRF9Z34NPBF,
R-78E5.0-1.0, 3568, IRF4905PBF, EEU-FR1V681, MCP2221A-I/P, SQP500JB-10R), forums.developer.nvidia.com threads
292892 and 126698, forum.batc.org.uk viewtopic p=24776, eevblog.com "adding CC to a CV buck", Sharp PC817 data
sheet, phippselectronics.com XL4015 page, the Adafruit CH334F and HUSB238 Eagle files.
