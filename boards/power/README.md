# ATLAS-PWR-1 power board (rev B)

The rev B power board sits on the deck under the Jetson dev kit's printed tray. It takes the 4S pack (through the
pack's XT90-S, 125 A fuse and JBD BMS), switches the motor bus for the Flipsky FSESC with a hardware E-stop,
latches the car on and off from a push button, feeds the dev kit, lidar, camera, servo BEC and fan, charges the
pack from USB-C, gives the laptop one USB-C cable to the dev kit, the VESC and a serial console, and carries the
Raspberry Pi Pico supervisor that sequences all of it and talks to the Jetson.

Source of truth: `design.py` (netlist, parts, values and their reasons), `layout.py` (placement, power copper,
outline), `PINMAP.md` (Pico GPIO map). `NOTES.md` has the judgment calls and open questions, `HANDOFF_E.md` what
the layout and routing step needs.

## At a glance

| | |
| --- | --- |
| Size | 130 x 84 mm, 2 layers, 2 oz copper, 1.6 mm, HASL. Six M3 holes at (4,4), (4,80), (75,4), (75,80), (126,4), (126,80) with 7 mm keep-outs |
| Parts | 80 through-hole parts on the top (3 of them DIP sockets); 104 chip resistors and capacitors (1206, five 1210) on the bottom; Pico and USB hub modules on 8.5 mm sockets; 4 modules wired off the board (Pololu latch, camera 12 V regulator, PD trigger, CC/CV buck); a 40 x 15 x 3 mm aluminium bar; plus 11 wire pads, 7 bare test pads and 6 holes |
| Tallest parts | the three 680 uF capacitors (12.5 x 20 mm, about 21 mm installed) and the FETs on their bar (about 20 mm). Everything is under the 23 mm limit of the dev-kit tray |
| Parts cost | USD 149.37 per board at quantity 1 (USD 11.30 of it not verified), table below; the bare PCB is quoted by the layout step |
| Checks | `netcheck.py`: 0 errors, 14 warnings: back-power of 0.05-0.28 mA (below the 0.5 mA limit), and 2.7 mA into the dev kit's 1k-fed inputs while the dev kit is off (allowed: TXB-type inputs, see NOTES) |

Through-hole first, with one exception: the 130 mm length limit leaves no room for about 100 resistors and small
capacitors as through-hole parts, so they are 1206 chips (1210 for the 10 uF) on the bottom side, with the
longer hand-solder pads. They solder with an iron and tweezers. Every IC is a DIP or TO-92/TO-220 part (the
MIC5014, 74HCT08 and MCP2221A in DIP sockets, which are BOM lines), and the two modules with fine-pitch chips (Pico,
hub) are socketed. The pre-order review (`docs/review_revb_2026-10-24.md`) and what changed for it: `DESIGN_FIXED.md`.

## Blocks

| Block | What it does |
| --- | --- |
| A pack input | 10 AWG pads for a pigtail with an XT90 male, which plugs into the XT90-S female on the pack (the female holds the anti-spark resistor); 3 x 680 uF 35 V low-ESR + 1 uF at the pads; 1.5KE20A TVS |
| B BMS link | JBD UART on a JST-XH 4 through two PC817s: the BMS side switches B-, so its ground never meets board ground |
| C main switch | 3 x IRFB7430 (TO-220, on one bar) high-side, driven by a MIC5014 (DIP-8); precharge IRF9Z34N + MF-R050 + 10 Ohm 5 W; a 74HCT08 ANDs the Pico enables with the E-stop loop in hardware; 1.5KE22A on the motor bus; NTC on the bar |
| D latch and rails | Pololu #2813 push-on latch (off board) gives VSYS_SW; RECOM R-78E 5 V behind 4.7 Ohm + P6KE20A; Castle BEC pads (BEC+ on VM, or the alternative BEC+ALT pad on VSYS_SW) and the servo header with 1000 uF; dev-kit feed: 5 A mini blade fuse, P6KE22A, over-voltage cut-off (IRF4905, TL431, trips 18.7 V, releases 17.85 V, 100 nF soft start) that is also the Pico's power-cycle switch; lidar high-side switch with polyfuse and P6KE22A; camera 12 V regulator (Pololu S18V20F12, off board) behind a polyfuse and a P6KE22A |
| E charging | USB-C PD trigger (Adafruit 5807, 20 V) and an XL4015-class CC/CV buck set to 16.80 V / 2.5 A, both off the board in the side pod. The charger side has its own ground, CHG_GND, joined to GND only through the buck's IN- to OUT- (its current shunt), so constant current works. Reverse block IRF4905 that turns fully on only with 20 V present; 5 A fuse into the pack bus; CHG_PRESENT_N to the Pico |
| F debug | Adafruit 5997 CH334F hub (bus powered by the laptop, its USB-C is the laptop port): port 1 on a through-hole USB-A receptacle (one standard USB-A to USB-C cable to the dev kit), port 3 on a 1x4 header to the FSESC (its ground through 2.2 Ohm), port 2 to an MCP2221A console on the dev kit's J14 UART, port 4 spare |
| G supervisor | Raspberry Pi Pico in sockets, ADC dividers for VM and the pack, status and fault LEDs |
| H Jetson | 2x20 shrouded box header for the J12 ribbon (7 pins left open so a reversed ribbon shorts nothing), 1k on the board outputs toward the Jetson (the dev kit level-shifts them), 10k on its outputs toward the board; 1x12 header for the J14 harness with PC817s for the power key and reset, recovery button |
| I ESC | 10 AWG pads for the FSESC, its COMM lead (UART pass-through to J12 pins 8/10, ADC2 kill line), servo-signal input. The COMM and servo-lead grounds go to GND through 3.3 Ohm each, so motor current stays in the ESC- lead |
| J misc | E-stop loop (JST-PH 2), remote button (JST-PH 2, side entry), 4-pin fan header with PWM, holes, test loops |

## Build the design files

From `boards/tools` (KiCad 7 or later installed; the schematic files are KiCad 9 format):

```
python3 make_footprints.py power                                            # this board's footprints in lib/atlas.pretty
KICAD_STOCK_SYMBOLS=/usr/share/kicad/symbols python3 build_sch.py power      # schematic sheets + atlas_power_parts.json
KICAD_FP_DIR=/usr/share/kicad/footprints python3 check_fp.py power           # every footprint exists and matches its symbol
KICAD_FP_DIR=/usr/share/kicad/footprints python3 fp_lib_from_mod.py power    # footprint geometry for the placer (first run only)
python3 placer.py power --plot ../power/out/placement.png                    # placement and power copper (out/*.json)
python3 ../power/netcheck.py                                                 # electrical checks (exits 1 on an error)
python3 ../../bom/revb/make_power_bom.py                                     # bom/revb: BOM CSV and cost per block
```

The PCB itself (build_pcb.py inside KiCad, routing, DRC, fab files) is the layout step: see `HANDOFF_E.md`.

## Assembly order (short; the student guide is docs/BUILD_POWER_BOARD.md)

1. Bottom side first: the 1206/1210 chips (flux, tweezers, iron at about 330 C). Check each against the bottom
   silkscreen; nothing is polarised.
2. The parts that sit under the modules, before their sockets: U302 socket and U801/U802 under the Pico; U601
   socket and U602 under the hub. Keep everything under a module 9 mm tall or less.
3. Low through-hole parts, then sockets and headers, then the TO-92s, TVS diodes, LEDs, fuse holders, R313 and the
   electrolytics (watch the polarity), then the three main FETs bolted to the bar before their legs are soldered.
4. Wire pads last: pack pigtail (10 AWG), ESC (10-12 AWG), BEC and servo leads (16 AWG), dev-kit lead (18 AWG),
   then the off-board modules.

## Settings that must be made before the first drive

| Where | Setting | Why |
| --- | --- | --- |
| JBD BMS (app) | cell over-voltage 4.25 V | above the 4.20 V the charger ends at, so a cell running slightly high does not end the charge or remove regen on a full pack (review m12) |
| CC/CV buck (trimmers, on the bench) | 16.80 V constant voltage, 2.5 A constant current | 4.20 V per cell; set CV with no load, CC into a load bank or a 4.7 Ohm resistor rated 50 W (about 30 W at 2.5 A, so only briefly) |
| FSESC (VESC Tool) | maximum input voltage 18 V | the VESC limits regenerative braking to keep the bus under this, so regen on a full pack stays below the pack TVS (19-21 V) and the dev-kit cut-off (18.7 V) (review m4) |
| FSESC (VESC Tool) | battery cut-off start 13.4 V, end 12.6 V | keeps a sagging pack from pulling VSYS_SW under the dev kit's 9 V and the R-78E's 8 V (review m9) |

## Before wiring the charger: check the CC/CV module (review B1)

The board expects a CC/CV module that senses its output current with a shunt between IN- and OUT- (the common
XL4015 board with two trimmers and an LM358) and gives the charger side its own ground for it. Check the module in
hand: 20 V into IN+/IN-, a 4.7 Ohm power resistor (50 W, briefly) on OUT+/OUT-, then measure from IN- to OUT-. About
0.1 V means a low-side shunt (this board's case: fine). About 0 V with the current still limited by the CC trimmer
means high-side sensing (also fine: IN- and OUT- are joined inside, the CHG_GND pads still work). If the current does
not follow the CC trimmer at all, do not use that module. No alternative module whose published schematic shows
high-side sensing could be verified, so none is named (see NOTES).

## Three bench tests before the pack goes on

Use a bench supply with a current limit for tests 1 and 2. Keep the FSESC, the dev kit and the pack disconnected
until test 2 has passed.

### 1. Logic only, from a 5 V bench supply

Do this before U401 (R-78E) is fitted, so the bench supply does not feed the regulator's output.

1. 5.0 V, limit 0.3 A, into TP402 (+5V) and TP1002 (GND). The green 5 V LED lights; supply current under about
   120 mA with the fan unplugged. TP701 (+3V3) reads 3.2-3.4 V once the Pico runs.
2. E-stop: with a jumper lead in J1001, GP10 (ESTOP_OK) reads about 3.0 V; without it, 0 V.
3. From the Pico REPL drive GP3 (MAIN_EN) high: U301 pin 2 (MIC5014 IN) reads about 4.9 V with the loop closed and
   0 V with it open. Same for GP2: Q305's base gets about 0.7 V only with the loop closed.
4. GP17 and GP18 light the status and fault LEDs; GP14 sets FSESC COMM pin 6 to 3.3 V; GP16 drives the fan.
5. BMS link loop-back: power J201's BMS side from a separate 3.3-5 V source (a USB power bank: J201 pin 1 = +,
   pin 4 = -, never joined to board GND) and bridge J201 pins 2 and 3. Bytes sent on UART0 at 9600 baud come back.
6. Laptop on the hub's USB-C: the hub and a USB serial port (MCP2221A) appear. With the bench supply off and only
   the laptop plugged in, TP402 stays at 0 V (the laptop never powers the car).
7. Later, with the dev kit: one USB-A to USB-C cable from J601 to the dev kit's USB-C gives 192.168.55.1. For
   flashing, NVIDIA documents a direct cable; if flashing through the hub fails, plug the laptop straight into the
   dev kit (review M7).

### 2. Pack bus from a current-limited 14 V at 0.5 A: latch, precharge, main switch

Fit U401 and wire the Pololu #2813 (VIN, VOUT, GND, ON, OFF). Bench supply 14.0 V, limit 0.5 A, on J101/J102.
Dummy load on the ESC pads: 1000 uF 35 V in parallel with 100 Ohm 2 W.

1. Off state: record the supply current (Pololu off current plus leakage). Nothing on VSYS_SW (TP401).
2. Press SW401: TP401 = 14 V, TP402 = 5 V, the Pico boots.
3. Precharge (GP2 high, loop closed): VM (TP301) rises with a time constant of about 10 ms and settles near 12.7 V
   (10.5 Ohm against the 100 Ohm load). Then GP3 high: TP302 (SW_GATE) reads 13-17 V above VM and VM = 14 V; GP2
   low. Open the E-stop: VM falls to 0 V. Close it: VM stays off until the firmware enables it again. Repeat at
   12.0 V: SW_GATE must still be at least 10 V above VM (review m1).
4. Dev-kit feed: DEV+ = 14 V; GP22 low cuts it. Raise the supply slowly: DEV+ drops to 0 V at about 18.7 V and
   returns at about 17.85 V on the way down. Stop at 19.0 V (the pack TVS starts to conduct above 19 V).
5. GP6 high puts 14 V on the lidar terminal; the camera pads carry 14 V through F403.
6. GP9 pulse: the latch turns everything off.
7. Precharge into the real loads (review M3): at 12.0 V, replace the dummy load with the FSESC, the Castle BEC (set
   to 7.5 V) with the servo and the 1000 uF, scope on VM. Precharge must bring VM to within 2.5 V of the supply and
   stop rising. If the BEC's start-up holds VM down, move the BEC's red lead from BEC+ (J401, on VM) to BEC+ALT
   (J410, on VSYS_SW; the latch, rated 6 A continuous, then carries the servo as well as the dev kit, lidar and
   camera, so check that sum at a 12 V pack), or fit a 4.7 Ohm 5 W cement resistor (Yageo SQP500JB-4R7, same body) as R313 (3.6 A peak for about
   10 ms; check that F301, the MF-R050, does not trip).

### 3. Main switch under load: 50 A, then 70 A pulses, thermocouple on the FETs

Use the real pack (its BMS, 125 A fuse and XT90-S in place) or a supply that can deliver 70 A, a load bank on the
ESC pads (about 0.33 Ohm for 50 A, 0.24 Ohm for 70 A, rated for the pulse energy), and a thermocouple taped with
Kapton to the middle FET's tab (the bar is BAT+). Two people, eye protection, and a way to open the E-stop loop
from a distance.

1. 50 A for 2 s, 20 s off, ten times. Watch SW_GATE minus VM (at least 10 V), the drop from BAT to VM (expect
   tens of mV), and the tab temperature (it should not climb more than about 20 C over the run). Compare the
   FET_NTC reading with the thermocouple.
2. 70 A for 1 s, 30 s off, five times, same checks.
3. Open the E-stop during a 50 A pulse with a scope on TP101 (BAT) and TP301 (VM): the spike must stay well under
   the TVS clamps (27.7 V at full TVS current); expect a few volts.
4. Pass: no FET tab above 80 C, no hot spot on the VM pour (a thermal camera helps), switch-off clean.

## Cost per block

Quantity-1 prices read on 2026-10-24 (links in the parts table). Buying for three boards brings the chip resistors
and capacitors down to a few cents each. Not included: the bare PCB, the cables and leads (ribbon, J14 harness,
USB leads, pack pigtail), the BMS, the Castle BEC and the pack hardware, which are car-level items.

| Block | Parts cost (USD) | Of which not verified (USD) |
| --- | ---: | ---: |
| A pack input | 4.76 | 0.00 |
| B BMS link | 1.49 | 0.00 |
| C main switch, precharge, E-stop gate | 24.92 | 2.50 |
| D latch and rails (5 V, servo, dev kit, lidar, camera) | 61.23 | 0.00 |
| E USB-C charging | 21.11 | 8.00 |
| F debug hub and console | 18.76 | 0.30 |
| G Pico supervisor | 8.97 | 0.50 |
| H Jetson ribbon and J14 | 4.04 | 0.00 |
| I ESC interface | 1.06 | 0.00 |
| J E-stop, fan, holes | 3.03 | 0.00 |
| **Total per board** | **149.37** | **11.30** |

## Parts

Generated from `atlas_power_parts.json` by `bom/revb/make_power_bom.py` (the CSV there has descriptions and
reasons). "Verified" = yes: price and part read on the linked page on 2026-10-24; est.: catalogue estimate;
no: not confirmed (the CC/CV module is a generic part, the bar is cut to order).

| Refs | Part | Package | Qty | Unit (USD) | Source | Verified |
| --- | --- | --- | ---: | ---: | --- | --- |
| C101 C102 C103 | 680u 35V, EEU-FR1V681 | CP Radial D12.5mm P5.00mm | 3 | 1.05 | [findchips.com](https://www.findchips.com/search/EEU-FR1V681) | yes |
| C404 | 1000u 16V, EEU-FR1C102 | CP Radial D10.0mm P5.00mm | 1 | 0.80 | [findchips.com](https://www.findchips.com/search/EEU-FR1C102) | yes |
| C405 | 220u 35V, Panasonic EEU-FR1V221 | CP Radial D8.0mm P3.50mm | 1 | 0.73 | [findchips.com](https://www.findchips.com/search/EEU-FR1V221) | yes |
| D1001 D1002 | BAT85S-TAP | D DO-35 SOD27 P2.54mm Vertical KathodeUp | 2 | 0.43 | [findchips.com](https://www.findchips.com/search/BAT85) | yes |
| D101 | 1.5KE20A | D DO-201AD P5.08mm Vertical KathodeUp | 1 | 0.42 | [findchips.com](https://www.findchips.com/search/1.5KE20A) | yes |
| D301 | 1.5KE22A | D DO-201AD P5.08mm Vertical KathodeUp | 1 | 0.29 | [findchips.com](https://www.findchips.com/search/1.5KE22A) | yes |
| D302 D702 | Lite-On LTL-4221N (3 mm red) | LED D3.0mm | 2 | 0.12 | [findchips.com](https://www.findchips.com/search/LTL-4221N) | yes |
| D401 | P6KE20A | D DO-15 P3.81mm Vertical KathodeUp | 1 | 0.54 | [findchips.com](https://www.findchips.com/search/P6KE20A) | yes |
| D402 | 1N5817RLG | D DO-41 SOD81 P3.81mm Vertical KathodeUp | 1 | 0.67 | [findchips.com](https://www.findchips.com/search/1N5817RLG) | yes |
| D403 D701 | Lite-On LTL-4231N (3 mm green) | LED D3.0mm | 2 | 0.10 | [findchips.com](https://www.findchips.com/search/LTL-4231N) | yes |
| D404 D405 D406 | P6KE22A | D DO-15 P3.81mm Vertical KathodeUp | 3 | 0.45 | [findchips.com](https://www.findchips.com/search/P6KE22A) | yes |
| D501 | P6KE24A | D DO-15 P3.81mm Vertical KathodeUp | 1 | 0.54 | [findchips.com](https://www.findchips.com/search/P6KE24A) | yes |
| D502 | 1N5247BTR | D DO-35 SOD27 P2.54mm Vertical KathodeUp | 1 | 0.17 | [findchips.com](https://www.findchips.com/search/1N5247BTR) | yes |
| F301 | MF-R050 | Fuse Bourns MF-R P5.08mm | 1 | 0.47 | [findchips.com](https://www.findchips.com/search/MF-R050) | yes |
| F401 F501 | 5A mini, Keystone 3568 + Littelfuse 0297005.WXNV | Fuseholder Blade Mini Keystone 3568 | 2 | 1.48 | [findchips.com](https://www.findchips.com/search/3568) | yes |
| F402 F403 | MF-R075 | Fuse Bourns MF-R P5.08mm | 2 | 0.25 | [findchips.com](https://www.findchips.com/search/MF-R075) | yes |
| J1001 | B2B-PH-K-S(LF)(SN) | JST PH B2B-PH-K 1x02 P2.00mm Vertical | 1 | 0.12 | [findchips.com](https://www.findchips.com/search/B2B-PH-K-S) | yes |
| J1002 | S2B-PH-K-S(LF)(SN) | JST PH S2B-PH-K 1x02 P2.00mm Horizontal | 1 | 0.12 | [findchips.com](https://www.findchips.com/search/S2B-PH-K-S) | yes |
| J1003 | Molex 47053-1000 | FanPinHeader 1x04 P2.54mm Vertical | 1 | 0.56 | [findchips.com](https://www.findchips.com/search/0470531000) | yes |
| J201 | B4B-XH-A(LF)(SN) | JST XH B4B-XH-A 1x04 P2.50mm Vertical | 1 | 0.11 | [findchips.com](https://www.findchips.com/search/B4B-XH-A) | yes |
| J403 J406 J904 | Wurth 61300311121 | PinHeader 1x03 P2.54mm Vertical | 3 | 0.13 | [findchips.com](https://www.findchips.com/search/61300311121) | yes |
| J409 | 1984617 | TerminalBlock Phoenix PT-1,5-2-3.5-H 1x02 P3.50mm Horizontal | 1 | 0.59 | [findchips.com](https://www.findchips.com/search/1984617) | yes |
| J601 | Wurth 614004134726 | USB A Wuerth 614004134726 Horizontal | 1 | 3.87 | [findchips.com](https://www.findchips.com/search/614004134726) | yes |
| J602 J603 | Wurth 61300411121 | PinHeader 1x04 P2.54mm Vertical | 2 | 0.19 | [findchips.com](https://www.findchips.com/search/61300411121) | yes |
| J801 | Wurth 61204021621 | IDC-Header 2x20 P2.54mm Vertical | 1 | 1.21 | [findchips.com](https://www.findchips.com/search/61204021621) | yes |
| J802 | Wurth 61301211121 | PinHeader 1x12 P2.54mm Vertical | 1 | 0.54 | [findchips.com](https://www.findchips.com/search/61301211121) | yes |
| J903 | B7B-PH-K-S(LF)(SN) | JST PH B7B-PH-K 1x07 P2.00mm Vertical | 1 | 0.33 | [findchips.com](https://www.findchips.com/search/B7B-PH-K-S) | yes |
| Q1001 | 2N7000-G | TO-92 Inline | 1 | 0.50 | [findchips.com](https://www.findchips.com/search/2N7000) | yes |
| Q301 Q302 Q303 | IRFB7430PBF | TO-220-3 Vertical | 3 | 3.69 | [findchips.com](https://www.findchips.com/search/IRFB7430PBF) | yes |
| Q304 Q405 | IRF9Z34NPBF | TO-220-3 Vertical | 2 | 1.08 | [findchips.com](https://www.findchips.com/search/IRF9Z34NPBF) | yes |
| Q305 Q401 Q403 Q406 Q502 Q503 | 2N3904BU | TO-92 Inline | 6 | 0.28 | [findchips.com](https://www.findchips.com/search/2N3904BU) | yes |
| Q402 Q501 | IRF4905PBF | TO-220-3 Vertical | 2 | 2.71 | [findchips.com](https://www.findchips.com/search/IRF4905PBF) | yes |
| Q404 | 2N3906BU | TO-92 Inline | 1 | 0.26 | [findchips.com](https://www.findchips.com/search/2N3906) | yes |
| R313 | SQP500JB-10R | R Axial Power L25.0mm W9.0mm P27.94mm | 1 | 0.52 | [findchips.com](https://www.findchips.com/search/SQP500JB-10R) | yes |
| R408 | 4.7, Vishay MBB02070C4708FCT00 (0.6 W metal film) | R Axial DIN0207 L6.3mm D2.5mm P7.62mm Horizontal | 1 | 0.26 | [findchips.com](https://www.findchips.com/search/MBB02070C4708FCT00) | yes |
| SW401 | PTS645VL58-2 LFS | SW Tactile SPST Angled PTS645Vx58-2LFS | 1 | 0.30 | [findchips.com](https://www.findchips.com/search/PTS645VL582LFS) | yes |
| SW801 | PTS645SL50-2 LFS | SW PUSH 6mm H5mm | 1 | 0.25 | [findchips.com](https://www.findchips.com/search/PTS645SL50-2LFS) | yes |
| TH301 | 10k B3977, NTCLE100E3103JB0 | C Disc D3.0mm W2.0mm P2.50mm | 1 | 0.53 | [findchips.com](https://www.findchips.com/search/NTCLE100E3103JB0) | yes |
| TP101 TP102 TP301 TP401 TP402 TP403 TP701 TP1002 | Keystone 5000 (red) / 5001 (black) | TestPoint Keystone 5000-5004 Miniature | 8 | 0.27 | [findchips.com](https://www.findchips.com/search/36-5000-ND) | yes |
| U201 U202 U801 U802 | PC817X2NSZ9F | DIP-4 W7.62mm | 4 | 0.42 | [findchips.com](https://www.findchips.com/search/PC817X2NSZ9F) | yes |
| U301 | MIC5014YN | DIP-8 W7.62mm Socket | 1 | 3.54 | [findchips.com](https://www.findchips.com/search/MIC5014YN) | yes |
| U302 | SN74HCT08N | DIP-14 W7.62mm Socket | 1 | 0.92 | [findchips.com](https://www.findchips.com/search/SN74HCT08N) | yes |
| U401 | R-78E5.0-1.0 | Converter DCDC RECOM R-78E-0.5 THT | 1 | 4.47 | [findchips.com](https://www.findchips.com/search/R-78E5.0-1.0) | yes |
| U402 | TL431ACLPRE3 | TO-92 Inline | 1 | 0.14 | [findchips.com](https://www.findchips.com/search/TL431ACLPR) | yes |
| U601 | MCP2221A-I/P | DIP-14 W7.62mm Socket | 1 | 3.20 | [findchips.com](https://www.findchips.com/search/MCP2221A-I%2FP) | yes |
| U602 | MCP1700-3302E/TO | TO-92 Inline | 1 | 0.50 | [findchips.com](https://www.findchips.com/search/MCP1700-3302E%2FTO) | yes |
| - | DIP-8 socket for U301 MIC5014 (soldered in its footprint), TE 1-2199298-2 | - | 1 | 0.27 | [findchips.com](https://www.findchips.com/search/1-2199298-2) | yes |
| - | DIP-14 socket for U302 74HCT08 (soldered in its footprint), TE 1-2199298-3 | - | 1 | 0.28 | [findchips.com](https://www.findchips.com/search/1-2199298-3) | yes |
| - | DIP-14 socket for U601 MCP2221A (soldered in its footprint), TE 1-2199298-3 | - | 1 | 0.28 | [findchips.com](https://www.findchips.com/search/1-2199298-3) | yes |
| MOD601 | 5997 | Adafruit 5997 CH334F Hub Headers (module on sockets) | 1 | 8.25 | [adafruit.com](https://www.adafruit.com/product/5997) | yes |
| MOD701 | RPi_Pico, SC0915 | RaspberryPi Pico Socketed 2x20 P17.78mm (module on sockets) | 1 | 6.10 | [findchips.com](https://www.findchips.com/search/SC0915) | yes |
| MOD401 | 2813 | WireLand Pololu 2813 (module off board, wired) | 1 | 8.95 | [pololu.com](https://www.pololu.com/product/2813) | yes |
| MOD402 | 2577 (S18V20F12) | WireLand Pololu S18V20F12 (module off board, wired) | 1 | 29.95 | [pololu.com](https://www.pololu.com/product/2577) | yes |
| MOD501 | 5807 | WireLand PD Trigger (module off board, wired) | 1 | 5.95 | [adafruit.com](https://www.adafruit.com/product/5807) | yes |
| MOD502 | XL4015 CC/CV 5 A module (generic) | WireLand CCCV Buck (module off board, wired) | 1 | 8.00 | - | no |
| HS301 | 6061 bar 40 x 15 x 3 mm, 3 x 3.2 mm holes at 13.0 mm | Heatsink Bar 3xTO220 40x15x3mm (mechanical) | 1 | 1.50 | [sendcutsend.com](https://sendcutsend.com) | no |
| R801 R802 (DNP) | 330, RC1206FR-07330RL | R 1206 3216Metric Pad1.30x1.75mm HandSolder (SMD 1206/1210, bottom) | 0 (+2 DNP) | 0.10 | [findchips.com](https://www.findchips.com/search/RC1206FR-0710KL) | yes |
| C1001 | 10n, KEMET C1206C103K5RACTU (10 nF 50 V X7R 1206) | C 1206 3216Metric Pad1.33x1.80mm HandSolder (SMD 1206/1210, bottom) | 1 | 0.10 | [findchips.com](https://www.findchips.com/search/C1206C103K5RACTU) | yes |
| C104 C603 C604 | 1u 50V, TDK C3216X7R1H105K160AB (1 uF 50 V X7R 1206) | C 1206 3216Metric Pad1.33x1.80mm HandSolder (SMD 1206/1210, bottom) | 3 | 0.65 | [findchips.com](https://www.findchips.com/search/C3216X7R1H105K160AB) | yes |
| C201 C302 C303 C304 C401 C406 C407 C502 C601 C602 C701 ... | 100n, Samsung CL31B104KBCNNNC (100 nF 50 V X7R 1206) | C 1206 3216Metric Pad1.33x1.80mm HandSolder (SMD 1206/1210, bottom) | 13 | 0.14 | [findchips.com](https://www.findchips.com/search/CL31B104KBCNNNC) | yes |
| C301 C402 C403 C501 C702 | 10u 50V, Murata GRM32ER71H106KA12L (10 uF 50 V X7R 1210) | C 1210 3225Metric Pad1.33x2.70mm HandSolder (SMD 1206/1210, bottom) | 5 | 0.86 | [findchips.com](https://www.findchips.com/search/GRM32ER71H106KA12L) | yes |
| R1002 R1004 | 100, RC1206FR-07100RL | R 1206 3216Metric Pad1.30x1.75mm HandSolder (SMD 1206/1210, bottom) | 2 | 0.10 | [findchips.com](https://www.findchips.com/search/RC1206FR-0710KL) | yes |
| R201 R305 R406 R602 R804 R812 R813 R901 R1001 | 1k, RC1206FR-071KL | R 1206 3216Metric Pad1.30x1.75mm HandSolder (SMD 1206/1210, bottom) | 9 (+1 DNP) | 0.10 | [findchips.com](https://www.findchips.com/search/RC1206FR-0710KL) | yes |
| R202 R204 R311 R315 R413 R420 R423 | 4.7k, RC1206FR-074K7L | R 1206 3216Metric Pad1.30x1.75mm HandSolder (SMD 1206/1210, bottom) | 7 | 0.10 | [findchips.com](https://www.findchips.com/search/RC1206FR-0710KL) | yes |
| R203 R705 R706 R814 R815 | 470, RC1206FR-07470RL | R 1206 3216Metric Pad1.30x1.75mm HandSolder (SMD 1206/1210, bottom) | 5 | 0.10 | [findchips.com](https://www.findchips.com/search/RC1206FR-0710KL) | yes |
| R301 R302 R303 | 10, RC1206FR-0710RL | R 1206 3216Metric Pad1.30x1.75mm HandSolder (SMD 1206/1210, bottom) | 3 | 0.10 | [findchips.com](https://www.findchips.com/search/RC1206FR-0710KL) | yes |
| R304 | 2.2M, RC1206FR-072M2L | R 1206 3216Metric Pad1.30x1.75mm HandSolder (SMD 1206/1210, bottom) | 1 | 0.10 | [findchips.com](https://www.findchips.com/search/RC1206FR-0710KL) | yes |
| R306 R307 R308 R312 R404 R407 R414 R416 R424 R701 R703 ... | 100k, RC1206FR-07100KL | R 1206 3216Metric Pad1.30x1.75mm HandSolder (SMD 1206/1210, bottom) | 17 | 0.10 | [findchips.com](https://www.findchips.com/search/RC1206FR-0710KL) | yes |
| R309 R310 R314 R316 R402 R405 R411 R415 R419 R421 R422 ... | 10k, RC1206FR-0710KL | R 1206 3216Metric Pad1.30x1.75mm HandSolder (SMD 1206/1210, bottom) | 21 | 0.10 | [findchips.com](https://www.findchips.com/search/RC1206FR-0710KL) | yes |
| R401 | 33k, RC1206FR-0733KL | R 1206 3216Metric Pad1.30x1.75mm HandSolder (SMD 1206/1210, bottom) | 1 | 0.10 | [findchips.com](https://www.findchips.com/search/RC1206FR-0710KL) | yes |
| R403 | 22k, RC1206FR-0722KL | R 1206 3216Metric Pad1.30x1.75mm HandSolder (SMD 1206/1210, bottom) | 1 | 0.10 | [findchips.com](https://www.findchips.com/search/RC1206FR-0710KL) | yes |
| R409 | 2.2k, RC1206FR-072K2L | R 1206 3216Metric Pad1.30x1.75mm HandSolder (SMD 1206/1210, bottom) | 1 | 0.10 | [findchips.com](https://www.findchips.com/search/RC1206FR-0710KL) | yes |
| R410 | 220, RC1206FR-07220RL | R 1206 3216Metric Pad1.30x1.75mm HandSolder (SMD 1206/1210, bottom) | 1 | 0.10 | [findchips.com](https://www.findchips.com/search/RC1206FR-0710KL) | yes |
| R412 R502 | 6.8k, RC1206FR-076K8L | R 1206 3216Metric Pad1.30x1.75mm HandSolder (SMD 1206/1210, bottom) | 2 | 0.10 | [findchips.com](https://www.findchips.com/search/RC1206FR-0710KL) | yes |
| R417 | 15.0k, RC1206FR-0715KL | R 1206 3216Metric Pad1.30x1.75mm HandSolder (SMD 1206/1210, bottom) | 1 | 0.10 | [findchips.com](https://www.findchips.com/search/RC1206FR-0710KL) | yes |
| R418 | 1.2M, RC1206FR-071M2L | R 1206 3216Metric Pad1.30x1.75mm HandSolder (SMD 1206/1210, bottom) | 1 | 0.10 | [findchips.com](https://www.findchips.com/search/RC1206FR-0710KL) | yes |
| R503 R504 R505 R506 | 47k, RC1206FR-0747KL | R 1206 3216Metric Pad1.30x1.75mm HandSolder (SMD 1206/1210, bottom) | 4 | 0.10 | [findchips.com](https://www.findchips.com/search/RC1206FR-0710KL) | yes |
| R604 | 2.2, RC1206FR-072R2L | R 1206 3216Metric Pad1.30x1.75mm HandSolder (SMD 1206/1210, bottom) | 1 | 0.10 | [findchips.com](https://www.findchips.com/search/RC1206FR-0710KL) | yes |
| R702 R704 | 18k, RC1206FR-0718KL | R 1206 3216Metric Pad1.30x1.75mm HandSolder (SMD 1206/1210, bottom) | 2 | 0.10 | [findchips.com](https://www.findchips.com/search/RC1206FR-0710KL) | yes |
| R905 R906 | 3.3, RC1206FR-073R3L | R 1206 3216Metric Pad1.30x1.75mm HandSolder (SMD 1206/1210, bottom) | 2 | 0.10 | [findchips.com](https://www.findchips.com/search/RC1206FR-0710KL) | yes |
| - | Male headers for the Pico, 2 x 1x20 (or buy a Pico with headers fitted), generic 1x20 2.54 mm | - (loose) | 2 | 0.25 | - | est. |
| - | Male headers for the hub module, 2 x 1x8 + 1x4 (if the module came without them), generic 2.54 mm | - (loose) | 1 | 0.30 | - | est. |
| - | M3 x 8 screws and nuts for the three FET tabs on the bar (all tabs are BAT+, no insulators needed); Kapton tape for the NTC and the outer face of the bar, generic | - (loose) | 1 | 1.00 | - | est. |
