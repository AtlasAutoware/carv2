# Building the ATLAS-PWR-1 power board

This is the step-by-step for assembling the rev B power board at school, testing it on the bench and getting it
ready for the car. It assumes a soldering bench with the Hakko FM-206 station, flux, solder, a microscope, a
multimeter and a current-limited bench supply. What the board does and why is in `docs/REV_B.md`; the circuit, with
the reason for every value, is `boards/power/design.py`. This version follows the design as changed after the
pre-order review (`docs/review_revb_2026-10-24.md`; the changes are listed in `boards/power/DESIGN_FIXED.md`).

The board is 130 x 84 mm with four copper layers: 2 oz on the top and bottom, and two 1 oz layers inside, one of them
a solid ground plane (`boards/power/LAYOUT_NOTES.md`). It carries 80 through-hole parts on the top (three of them DIP
sockets), 104 chip resistors and capacitors (1206, five of them 1210) on the bottom, two modules on sockets (the
Raspberry Pi Pico and the USB hub), and four modules wired off the board. Work in the order below. It goes from the
flattest parts to the tallest, so the board always sits level on the bench, and it puts the four bench tests where
they catch a mistake before it can do damage.

Where a value in this guide has not been checked on real parts yet, it says "not verified".

## Safety

Read this before you start, and again before test 3.

- **The pack is 121 Wh** (14.4 V nominal, 16.8 V full, 8.4 Ah; `docs/PACK_BUILD.md`) and can deliver hundreds of amps
  into a short. A tool dropped across its leads is that short. The 125 A fuse and the BMS are there for faults;
  never test them on purpose.
- **The pack side of the board is live whenever the XT90-S is plugged in,** even with the car switched off. The power
    button and the main switch come after it. That includes the pack pads, the three big capacitors, the wide copper
  between them and the aluminium bar on the main FETs. On the top, the solder mask is left off over the main pack
  (BAT) and motor-bus (VM) copper on purpose, so it can be tinned: those bare strips are live too.
- **The FET bar is at pack voltage.** All three main FET tabs are bolted to it, and every tab is the FET's drain,
    which is pack plus, and the board says so beside it ("FET bar is at pack voltage"). Nothing metal may touch the bar,
  and nothing may lean on it. On the car a 3 mm acrylic shield
  hangs 2 mm above it under the dev-kit tray; it is always fitted. The four other TO-220 FETs on the board have live
  tabs too.
- **Nothing on the board stops a reversed pack.** A pigtail wired the wrong way round puts the pack TVS (D101) in
  forward conduction across the pack. Check the pigtail and the XT90 polarity with a meter before the pack is ever
  connected (review m15).
- **No pack on this board until tests 1 and 2 have passed.** Test 3 is the first time the board meets the pack, and
  it needs two people, eye protection, an adult supervising and a way to open the E-stop from a distance. The board
  does not go into the car until test 3 has passed.
- **Carbon-fibre filament conducts.** The deck and the printed tray, BMS holder and canopy are made of it. Never let
  a printed part be the only thing between two conductors. The six mounting holes have no copper near them for the
  same reason: the standoffs and the deck under them can conduct. The tray, the BMS holder, the canopy and the splice
  plates can instead be laser-cut from 3 mm birch plywood or cast acrylic, which do not conduct; the FET shield is
  always 3 mm cast acrylic (`mech/README.md` and `mech/PRINTING.md`, "Laser-cut parts").
- **Capacitors stay charged** after the supply is off. Measure across them before you put a tool there.
- **The iron and the flux.** Work with fume extraction or a fan pulling the smoke away from you, keep the iron in its
  holder when you are not using it, wear eye protection when you cut leads, and wash your hands after soldering.
- **Pack work** (wiring the battery assembly, setting the BMS, the first charge) is done with an adult present, on a
  non-flammable surface, with the pack in its box (`docs/PACK_BUILD.md`).

## Tools and consumables

Tools:

- Hakko FM-206 station: a fine tip for the chips, and the largest chisel tip you have for the TO-220 legs, the
  electrolytics and every ground pin (2 oz copper, the wide power copper and the inner ground plane pull heat away fast)
- for the four 10 AWG pads (J101, J102, J901, J902): a hot plate to preheat the board to about 100 C, or a 100-150 W
  iron; a 70 W iron may not wet them (review m19). Each is a 7.5 mm pad with a 3.5 mm hole and a ring of six 0.6 mm
  plated holes, joined solid to its 2 oz pour, which is right for 90 A and is why they are slow to heat
- fine-point tweezers, flush cutters, calipers
- microscope
- multimeter with a continuity beep and a 10 A current range
- current-limited bench supply that reaches at least 19 V (the tests use 5 V at 0.3 A and 14 V at 0.5 A)
- a thermocouple and a meter that reads it
- an oscilloscope for test 3, step 3
- wire strippers for 10 to 24 AWG, crimpers for JST PH (2.0 mm), JST XH (2.5 mm) and Dupont (2.54 mm) contacts, a
  heat gun for heat-shrink
- small flat screwdriver for the trimmers, M3 screwdriver and nut driver
- a laptop with Thonny or `mpremote`, VESC Tool and the Castle Link software; a phone with the JBD app (Xiaoxiang) or
  JBD's PC tool
- a Castle Link V3 programmer for the BEC

Consumables:

- flux (no-clean), solder (thin for the chips, thicker for the big joints), solder wick, isopropyl alcohol and a
  brush to clean flux off
- Kapton tape, heat-shrink, a little glue for the trimmers (the CC/CV buck)
- three M3 x 8 screws and nuts for the FET tabs (on the BOM)
- silicone wire: 10 AWG (pack pigtail), 16 AWG (BEC), 18 AWG (latch), 20 AWG (charge modules), 22 AWG (camera
  regulator input), 24 AWG (latch ON and OFF)
- JST PH and XH housings and crimps, a 1 x 12 Dupont housing and crimps (the harnesses below)
- for test 2: a 1000 uF 35 V capacitor and a 100 Ohm 2 W resistor (the dummy load), and a 1 kOhm resistor of 0.5 W
  or more for the dev-kit feed
- for the CC/CV module: a 4.7 Ohm power resistor rated 50 W (it takes about 30 W at 2.5 A, so only briefly)
- in reserve, in case the real-load precharge check in test 2 fails: a Yageo SQP500JB-4R7 (4.7 Ohm 5 W, the same body
  as R313)
- for test 3: a load for 50 A and 70 A pulses (about 0.33 Ohm and 0.24 Ohm, rated for the pulse energy) with its own
  switch rated for 70 A DC, and 10 AWG leads to it

## Check the parts kit

Count every part against `bom/revb/power_board_bom.csv` before you start (the layout's own lists in
`boards/power/out/fab/`, `atlas_power_bom.csv` and `atlas_power_tht_top.csv`, say the same), one block at a time, and
put each block's parts in its own labelled tray. The reference numbers tell you the block: 1xx is block A, 2xx is B,
and so on up to 10xx for block J. Keep each chip value in its tape until you place it: the ceramic capacitors carry no
marking at all, and a loose 10k looks like a loose 100k.

| block | through-hole parts (top) | chips (bottom) | other |
| --- | --- | --- | --- |
| A pack input | 6: C101-C103 680 uF, D101 1.5KE20A, TP101 (red), TP102 (black) | 1: C104 | wire pads J101 (BAT+), J102 (BAT-) |
| B BMS link | 3: J201 JST-XH 4, U201 and U202 PC817 | 5 | |
| C main switch | 13: Q301-Q303 IRFB7430, Q304 IRF9Z34N, Q305 2N3904, U301 MIC5014, U302 74HCT08, F301 MF-R050, R313 10 Ohm 5 W, D301 1.5KE22A, TH301 NTC, D302 red LED, TP301 (red) | 19 | HS301 aluminium bar, 40 x 15 x 3 mm; DIP-8 socket for U301, DIP-14 socket for U302 |
| D latch and rails | 27: Q402 IRF4905; Q405 IRF9Z34N; Q401, Q403, Q406 2N3904; Q404 2N3906; U401 R-78E; U402 TL431; D401 P6KE20A; D404, D405, D406 P6KE22A; D402 1N5817; D403 green LED; SW401 power button; R408 4.7 Ohm 0.6 W; F401 fuse holder; F402, F403 MF-R075; C404 1000 uF; C405 220 uF; J403, J406 1 x 3 headers; J409 Phoenix terminal; TP401, TP402, TP403 (red) | 28 | off the board: MOD401 Pololu #2813, MOD402 Pololu S18V20F12; wire pads BEC+ (J401), BEC-, BEC+ALT (J410), SRV+/SRV-, DEV+/DEV- |
| E charging | 6: Q501 IRF4905; Q502, Q503 2N3904; F501 fuse holder; D501 P6KE24A; D502 1N5247B | 9 | off the board: MOD501 Adafruit 5807 PD trigger, MOD502 CC/CV buck; bare test pad TP502 (CHG_GND) |
| F debug | 5: J601 USB-A receptacle (Wurth 614004134726), J602 and J603 1 x 4 headers, U601 MCP2221A, U602 MCP1700 | 8 | MOD601 Adafruit 5997 hub, on sockets; DIP-14 socket for U601 |
| G supervisor | 3: D701 green LED, D702 red LED, TP701 (red) | 10 | MOD701 Raspberry Pi Pico, on sockets |
| H Jetson | 5: U801, U802 PC817; J801 2 x 20 box header; J802 1 x 12 header; SW801 recovery button | 12 | R801, R802 and R805 are **do not fit** |
| I ESC | 2: J903 JST-PH 7, J904 1 x 3 header | 6 | wire pads ESC+ (J901), ESC- (J902) |
| J the rest | 7: J1001 JST-PH 2, J1002 JST-PH 2 side entry, J1003 fan header, D1001 and D1002 BAT85, Q1001 2N7000, TP1002 (black) | 6 | |
| **total** | **77, plus the 3 DIP sockets = 80** | **104** | |

The 104 chips by value. Resistors: 10k x 21, 100k x 17, 1k x 9, 4.7k x 7, 470 x 5, 47k x 4, 10 Ohm x 3, 6.8k x 2,
18k x 2, 3.3 Ohm x 2, 100 Ohm x 2, and one each of 2.2M, 1.2M, 33k, 22k, 15.0k, 2.2k, 220 Ohm and 2.2 Ohm.
Capacitors: 100 nF x 13, 10 nF x 1, 1 uF x 3 (all 1206), and 10 uF x 5 (1210, the larger ones). Watch the look-alike
values: 2.2 Ohm (R604), 2.2k (R409) and 2.2M (R304) are three different parts, and so are 1.2M (R418) and 1k.

Also in the kit:

- The three DIP sockets: TE 1-2199298-2 (8 pins) for U301 and two TE 1-2199298-3 (14 pins) for U302 and U601. They
  are BOM lines; those three chips are never soldered in.
- The module sockets: two Sullins PPTC201LFBN-RC (1 x 20) for the Pico, two PPTC081LFBN-RC (1 x 8) and one
  PPTC041LFBN-RC (1 x 4) for the hub. They are priced inside the Pico and hub lines of the BOM, so check they were
  ordered.
- Male headers for the Pico (2 x 1 x 20) and the hub (2 x 1 x 8 and 1 x 4), unless the modules came with them.
- Two 5 A mini blade fuses (Littelfuse 0297005.WXNV) for F401 and F501.
- Off the board, for the car: the Castle BEC 2.0, the JBD BMS, the MIDI 125 A fuse and holder, the XT90-S pair, the
  acrylic FET shield (laser-cut), the leads listed under "Harnesses".

## Orientation and polarity

Get these right the first time: a reversed electrolytic or TVS diode fails the moment power goes on, and desoldering
a TO-220 from 2 oz copper is slow. The marks below are the ones the board's KiCad footprints draw. Compare them with
the board renders from the layout step before you start, and have a second person check
every part in this table before it is soldered.

On this board, **pin 1 of every part has a square (or rounded-square) pad.** The other pads are round or oval. Every
polarised part on the top also has a pin-1 dot on the silkscreen beside it, except D702 (the red fault LED) and J1002
(the remote-button connector), where there was no room: for those two, go by the square pad.

| part type | parts | the mark on the part | the mark on the board |
| --- | --- | --- | --- |
| electrolytic capacitors | C101, C102, C103, C404, C405 | the stripe on the can is minus; the long lead is plus | a "+" beside the square pad; the hatched half of the circle is minus |
| diodes and TVS diodes, standing up | D101, D301 (DO-201); D401, D404, D405, D406, D501 (DO-15); D402 (DO-41); D502, D1001, D1002 (DO-35) | the band is the cathode | the body stands on the circle; the band end is at the top, and its lead bends down into the square pad marked "K" |
| LEDs | D302, D403, D701, D702 | the short lead and the flat side of the rim are the cathode | the square pad and the flat side of the outline |
| TO-220 FETs | Q301, Q302, Q303 (IRFB7430, on the bar); Q402, Q501 (IRF4905); Q304, Q405 (IRF9Z34N) | the metal tab is the back | the double line across the outline is the tab side; pin 1 (square pad) is the gate |
| TO-92 parts | 2N3904: Q305, Q401, Q403, Q406, Q502, Q503; 2N3906: Q404; 2N7000: Q1001; TL431: U402; MCP1700: U602 | the flat face | the straight side of the outline; pin 1 (square pad) is E for the 2N3904 and 2N3906, S for the 2N7000, REF for the TL431, GND for the MCP1700 |
| DIP sockets and chips | U301 MIC5014 (8 pins), U302 74HCT08 and U601 MCP2221A (14 pins) in sockets; U201, U202, U801, U802 PC817 (4 pins) soldered in | the notch or dot at pin 1 | the notch in the outline and the square pad |
| 5 V regulator | U401 RECOM R-78E | pin 1 is +Vin (check the datasheet drawing for which face is the front) | the square pad, and the body sits over the outline |
| connectors | J201, J903, J1001, J1002, J1003, J801, J802, J409, J601 | the locking ramp, the key slot in the shroud, the wire entry, the USB opening | the outline: J801's key slot is a gap in one long side of its outline, and a small triangle points at its pin 1; J802's pin 1 is the end toward the pack edge; J409's wire entries face the front edge; J601 (USB-A) has its opening at the pod edge, and its four shell pads are soldered too |
| modules | MOD701 Pico, MOD601 hub | the USB connector | the Pico's USB end faces the pack edge; the hub's USB-C faces the pod edge (the long edge with the power button) |

The TO-92 parts all look the same. Read the marking on every one with the microscope before it goes in: a 2N3906 in a
2N3904's place, or a TL431 in a transistor's place, gives a board that powers up and then does the wrong thing.

The TO-220s look the same too, and there are three kinds: the three on the bar are the IRFB7430 (N-channel); Q402
(dev-kit feed) and Q501 (charge reverse block) are the IRF4905 (P-channel, 20 mOhm); Q304 (precharge) and Q405
(lidar) are the IRF9Z34N (P-channel). Read the marking on each one.

Not polarised: the chip resistors and capacitors, the polyfuses (F301, F402, F403), the NTC (TH301), the fuse holders,
R313 and R408, and the two push buttons.

Test loops: black for the two ground loops (TP102 and TP1002), red for the other six.

## Order of assembly

### 1. Inspect the bare board

Look at both sides under the microscope for scratches through the copper and for solder mask missing between pads.
The bare copper strips on the top over the BAT and VM pours are meant to be bare. The two inner layers cannot be seen;
the meter checks below cover them.
Then, with the meter on continuity, check that none of these beep against GND (TP102): the pack pad BAT+, the motor bus
(the ESC+ pad), VSYS_SW (TP401), +5V (TP402), +3V3 (TP701). Check also that J201 pin 4 (the BMS's ground) does not
beep against GND: the two grounds must never meet on this board. Nor may TP502 (CHG_GND, the charger side's ground):
on the car it meets GND only inside the CC/CV module.

Write the board's serial number in the box on the silkscreen.

### 2. The chips on the bottom (104)

Turn the board upside down. Every chip goes on the bottom side. None of them is polarised. Work one value at a time:
take one tape, place every part of that value, then the next.

**Finding each chip's place.** The bottom silkscreen shows the reference for 69 of the 107 bottom parts (the 104 chips
plus the empty R801, R802 and R805 places). The other 38, mostly packed under the Pico and the hub, had no room for
their reference and have it only on the bottom fab layer:

C1001, C303, C402, C407, C603, C702, C704, R1001, R1003, R1004, R203, R314, R316, R401, R402, R411, R412, R413, R417,
R421, R422, R501, R503, R506, R602, R603, R705, R806, R807, R811, R812, R813, R814, R815, R903, R904, R905, R906.

For those, print the bottom fab layer as an assembly drawing: `boards/power/out/fab/gerbers/atlas_power-B_Fab.gbr`,
opened in any Gerber viewer (it is not in the zip that goes to PCBWay). The placement file
`boards/power/out/fab/atlas_power_cpl_bottom_smd.csv` lists every bottom chip with its value, its position in mm and
its rotation, and `boards/power/out/render/bottom.png` shows the bottom silkscreen as seen from below. Tick each part
off on the printout as it goes on.

Iron at about 330 C (`boards/power/README.md`). The 1206 pads are KiCad's longer hand-solder pads, so there is room
for the tip. **Tack one end, then solder the other:**

1. Put flux on both pads.
2. Put a small amount of solder on one pad only. Use the same side every time (the right-hand pad if you are right
   handed).
3. Pick up the chip with tweezers and hold it flat on the board, centred on its two pads. Touch the iron to the
   tinned pad: the solder melts and the end of the chip sinks into it. Take the iron away and keep the tweezers still
   for a second.
4. Look under the microscope. The chip must be flat and centred. If it is not, reheat that end and nudge it.
5. Solder the other end: tip on the pad and the end of the chip together, then feed a little solder into the joint.
6. Go back to the first end and reflow it with a touch of fresh solder, because that end was soldered before the chip
   was heated properly.

A good joint is a smooth, concave fillet from the pad up the end of the chip. A ball of solder that does not wet the
end, a bridge to the next pad or a chip standing on one end ("tombstone") all get fixed now. Do not press hard on
the ceramic capacitors: they crack.

The 1210 parts (the five 10 uF) are soldered the same way.

### 3. The parts that sit under the modules

The Pico and the hub stand on 8.5 mm sockets, and a few parts sit underneath them. Solder these before the sockets,
because the sockets are in the way afterwards:

- under the Pico: the U302 socket (74HCT08), U801 and U802 (PC817);
- under the hub: the U601 socket (MCP2221A) and U602 (MCP1700, TO-92).

Nothing under a module may be taller than 9 mm above the board, including a chip in its socket. Push U602 down until
its top is under 9 mm and check with the calipers.

### 4. The lowest through-hole parts

- R408 (4.7 Ohm 0.6 W, lying flat)
- the U301 socket (MIC5014), U201 and U202 (PC817)
- the small standing diodes: D402 (1N5817), D502 (1N5247B), D1001 and D1002 (BAT85)
- the four LEDs: D302, D403, D701, D702
- the eight test loops
- SW801 (the recovery button)

Insert, bend the leads slightly so the part stays put, turn the board over, solder, cut the leads. Check the
orientation table before each type.

Every through-hole ground pin on the board is also joined to the inner ground plane, so ground joints take longer to
heat than the others. Use the bigger tip on them and check that the solder has run through the hole and shows on the
top. The dev-kit return pad, J408 (DEV-), is joined with no thermal spokes at all.

### 5. TO-92 parts, polyfuses and the NTC

- the transistors and the TL431: Q305, Q401, Q403, Q404, Q406, Q502, Q503, Q1001, U402
- the polyfuses: F301, F402, F403
- TH301, the NTC: leave its legs long, because it is bent against the FET bar in step 7

### 6. Sockets, headers and connectors

- The Pico sockets (2 x 1 x 20) and the hub sockets (2 x 1 x 8 and 1 x 4). To keep them straight, plug the module
  (with its male headers soldered on) into the sockets, put the sockets into the board, solder one pin at each end of
  each strip, check that everything sits flat, then solder the rest and take the module out again.
- J601, the through-hole USB-A receptacle for the dev kit, at the pod edge between the hub and the power button,
  opening facing out over the edge. Solder its four pins and its four shell pads.
- J801 (2 x 20 box header, key slot as drawn), J802 (1 x 12), J602 and J603 (1 x 4), J403, J406, J904 (1 x 3)
- J903 (JST-PH 7), J201 (JST-XH 4), J1001 (JST-PH 2), J1002 (JST-PH 2 side entry), J1003 (fan header), J409 (Phoenix
  terminal, wire entries toward the front edge)
- SW401, the right-angle power button, at the pod edge
- the two mini blade fuse holders, F401 and F501

The connectors take a lot of force when cables go on and off. Make sure every pin has a full fillet on the bottom.

### 7. Power parts

Leave U401 (the R-78E) out for now. Test 1 needs it out.

- The TVS diodes, standing: D101 and D301 (DO-201), D401, D404, D405, D406 and D501 (DO-15). Check the band of each
  one, and the type: D401 is a P6KE20A, D404, D405 and D406 are P6KE22A, D501 is a P6KE24A.
- R313 (10 Ohm 5 W cement resistor), lying flat.
- The four P-channel FETs, standing on their own: Q402 and Q501 (IRF4905), Q304 and Q405 (IRF9Z34N). Their tabs
  are live, and they must not touch each other or anything else.
- The three IRFB7430 on the bar:
  1. Bolt Q301, Q302 and Q303 to the bar with the three M3 x 8 screws and nuts, tabs flat against the bar, legs
     straight and parallel. No insulators go between the tabs and the bar: all three tabs are the drain, at pack
     plus, the same as the bar. A thin film of thermal paste on each tab helps (not on the BOM).
  2. Put the whole assembly into the board. The bar stands on its 15 mm edge behind the FETs, on the wide pack-plus
     copper. Check that it sits flat and that the FET bodies are square to the board. Push the FETs fully down: the
     acrylic shield hangs 2 mm above the highest live point, and everything under it must stay at 21 mm or less.
     Measure that highest point (tab tops or bar) with the calipers and write it on the sign-off sheet; it is
     MEASURE_FIRST item 28 (the model assumes 20 mm).
  3. Solder the nine legs. This is 2 oz copper on a large pour: use the big chisel tip and give each joint time.
     The joint is done when the solder has run down through the hole and shows on the top side.
  4. Kapton tape over the bar's outer face. Bend TH301 so it touches the bar, with a layer of Kapton between them, and
     tape it there.

### 8. Electrolytic capacitors

C405 (220 uF), C404 (1000 uF), then C101, C102 and C103 (680 uF, the tallest parts on the board, about 21 mm). Plus
to the "+" mark, every time.

### 9. Chips into their sockets, fuses, modules

- MIC5014 into U301, 74HCT08 into U302, MCP2221A into U601. Notch to notch. Check that no pin folded under the chip.
- The two 5 A fuses into F401 and F501.
- Flash MicroPython onto the Pico first (see "Module set-up"), then plug the Pico in with its USB end toward the pack
  edge. Plug the hub in with its USB-C at the pod edge.

**Stop here and do test 1.**

### 10. The 5 V regulator and the latch

After test 1 has passed: solder U401 (R-78E, pin 1 in the square pad), and wire the Pololu #2813 to the latch pads
(18 AWG for VIN, VOUT and GND, 24 AWG for ON and OFF; see "Harnesses").

**Do test 2.** It needs the bench supply on the pack pads (J101 +, J102 -). Either solder a short pair of temporary
leads into them (0.5 A, so 16-18 AWG is plenty), or fit the pack pigtail now (step 11) and use a lead with the mating
XT90 to reach the supply.

### 11. Wire pads

After test 2 has passed:

- The pack pigtail into J101 (BAT+) and J102 (BAT-): 10 AWG with an XT90 male on the end (the pack carries the XT90-S
  female, the half with the anti-spark resistor). Preheat the board on the hot plate (about 100 C) or use the 100-150
  W iron: these pads are joined solid, with no thermal spokes, to large 2 oz pours. Tin the wire first, then heat the
  pad and the wire together and feed solder until the hole is full. Then check with the meter that the XT90's plus
  contact goes to BAT+ (TP101).
- For test 3, the load goes on the ESC pads (J901 ESC+, J902 ESC-) with 10 AWG leads. If the FSESC will connect through
  an XT60 pigtail (`design.py` allows that), solder the pigtail now and use it for the load too.

**Do test 3** (pack, 50 A and 70 A).

After test 3 has passed:

- The FSESC's battery leads (or its pigtail) into J901 and J902. Run ESC+ and ESC- together as one pair and tie them
  down so they cannot pull on the pads (review M6).
- The Castle BEC's input leads (16 AWG): black to BEC-, red to BEC+ (J401, on the motor bus). Leave the red lead long
  enough to reach BEC+ALT (J410) as well, in case test 4 moves it there.

**Do test 4** (precharge into the real FSESC and BEC).

Then the dev-kit lead (DEV+, DEV-, 18 AWG) and the wires to the off-board modules (camera regulator, PD trigger,
CC/CV buck; see "Harnesses"). Clean the flux off both sides with isopropyl alcohol and check the whole board under the
microscope once more.

## The bench tests

Tests 1 and 2 use a current-limited bench supply and keep the FSESC, the dev kit and the pack off the board. Test 3
is the first time the board meets the pack. Test 4 checks the precharge with the real FSESC and Castle BEC. Write
the readings on the sign-off sheet at the end. To drive the Pico's pins in tests 1 and 2, use its REPL (Thonny's
shell, or `mpremote`) with only MicroPython on it, before the supervisor files are copied. For example:

```
from machine import Pin
Pin(3, Pin.OUT).value(1)      # GP3 (MAIN_EN) high
Pin(3, Pin.OUT).value(0)      # and low again
```

The pin numbers and what each one does are in `boards/power/PINMAP.md`.

### Test 1: logic only, from 5 V

U401 must be out (step 7), so the bench supply does not feed the regulator's output. The Pico (with MicroPython) and
the hub are in their sockets, the three DIP chips in theirs. Fan unplugged.

1. Bench supply at 5.0 V, current limit 0.3 A, plus to TP402 (+5V), minus to TP1002 (GND). The green 5 V LED (D403)
   lights. The supply current stays under about 120 mA. TP701 (+3V3) reads 3.2-3.4 V once the Pico runs.
2. E-stop input: with a wire loop in J1001, GP10 reads about 3.0 V (Pico pin 14); without it, 0 V.
3. Drive GP3 (MAIN_EN) high: U301 pin 2 (the MIC5014's input) reads about 4.9 V with the loop in J1001, and 0 V
   without it. Drive GP2 (PRECHARGE_EN) high: Q305's base reads about 0.7 V only with the loop in. Set both low
   again.
4. GP17 and GP18 light the status and fault LEDs (D701 and D702, at the pod edge beside the power button). GP14 puts
   3.3 V on J903 pin 6. Plug the fan in: GP16 changes its speed.
5. BMS link loop-back. Power the BMS side of J201 from a separate 3.3-5 V source, such as a USB power bank: J201 pin 1
   plus, pin 4 minus. Its minus must never touch the board's GND. Join J201 pins 2 and 3 with a wire. Bytes sent on
   UART0 at 9600 baud come back:
   ```
   from machine import UART, Pin
   import time
   u = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))
   u.write(b'atlas'); time.sleep(0.1); print(u.read())     # b'atlas'
   ```
   If a scope is free, look at the returning signal on GP1 while you send: the edges must be clean well inside the
   104 us bit time at 9600 baud (review m10; the optocouplers' speed at these loads is not verified).
6. Laptop on the hub's USB-C: the laptop sees a USB hub and a USB serial port (the MCP2221A). Then switch the bench
   supply off and leave only the laptop plugged in: TP402 stays at 0 V. The laptop must never power the car.
7. Later, with the dev kit: one ordinary USB-A to USB-C cable from J601 to the dev kit's USB-C gives the Jetson at
   192.168.55.1. For flashing JetPack, NVIDIA documents a direct cable; if flashing through the hub fails, plug the
   laptop straight into the dev kit's USB-C (review M7).

Pass: every step as described, and nothing warm.

### Test 2: the pack bus from 14 V at 0.5 A

U401 fitted, the Pololu latch wired. Bench supply at 14.0 V, current limit 0.5 A, on the pack pads (J101 plus, J102
minus). On the ESC pads, the dummy load: 1000 uF 35 V in parallel with 100 Ohm 2 W.

1. Off state: write down the supply current (the latch's off current plus leakage). TP401 (VSYS_SW) reads 0 V. If the
   latch switches itself on when the supply is applied, write that down too (review m17).
2. Press SW401: TP401 reads 14 V, TP402 reads 5 V, the Pico starts.
3. With the loop in J1001, drive GP2 high (precharge). The motor bus (TP301) rises with a time constant of about
   10 ms and settles near 12.7 V (10.5 Ohm against the 100 Ohm load). Drive GP3 high: SW_GATE (the bare test pad
   TP302) reads 13-17 V above the motor bus, and the motor bus reads 14 V. Drive GP2 low.
4. Pull the loop out of J1001: the motor bus falls to 0 V. **Drive GP3 low before you put the loop back.** At the REPL
   nothing drops GP3 for you, and with GP3 still high the switch would close again the moment the loop closes. With
   the supervisor firmware running, the Pico drops it as soon as the loop opens and waits for a button press.
5. Set the supply to 12.0 V and repeat step 3: SW_GATE must still be at least 10 V above the motor bus (review m1).
   Then back to 14.0 V and GP3 low.
6. Dev-kit feed. Put a load across DEV+ and DEV- for this step (a resistor of about 1 kOhm, 0.5 W or more): with
   nothing connected, C405 holds DEV+ up after the feed is cut. DEV+ reads 14 V. Drive GP22 low: DEV+ drops to 0 V;
   back high, 14 V. With GP3 low, raise the supply slowly: DEV+ drops to 0 V at about 18.7 V, and comes back at about
   17.85 V on the way down. Do not go above 19.0 V: the pack TVS starts to conduct above 19 V.
7. GP6 high puts 14 V on the lidar terminal (J409). The camera pads carry 14 V through F403.
8. A short high pulse on GP9: the latch switches everything off.

Pass: every step as described, and nothing warm.

### Test 3: the main switch under load, with the pack

This is the dangerous one. Two people, eye protection, an adult supervising, the pack in its box with its BMS set
up, the 125 A fuse and the XT90-S in place (see "Module set-up" for the BMS). Run the E-stop loop on a long lead so
it can be opened from a distance. A bench supply that can deliver 70 A works instead of the pack.

- The load on the ESC pads: about 0.33 Ohm for 50 A and 0.24 Ohm for 70 A, rated for the pulse energy.
- The pulses come from the load's own switch (a switch or contactor rated for 70 A DC, or an electronic load's pulse
  mode), never from the main switch. One person works that switch and times the pulses with a stopwatch; the other
  watches the meters and keeps a hand on the E-stop.
- A thermocouple taped with Kapton to the middle FET's tab. The tab is at pack voltage, so the Kapton is the
  insulation between them. If you have a second one, tape it to C101 (review m21).
- A scope on TP101 (pack bus) and TP301 (motor bus) for step 3.

With the load's switch open, switch the car on, precharge and close the main switch (GP2, then GP3, then GP2 low; or
the supervisor firmware). The main switch now stays closed for the whole test, as it does in the car: there it
closes after precharge with the ESC idle and only opens under load when the E-stop is pulled. Closing the main switch
straight into a 50 A load is not part of the test.

1. 50 A for 2 s, then 20 s off, ten times. Watch: SW_GATE minus the motor bus stays at 10 V or more; the drop from the
   pack bus to the motor bus is tens of millivolts (the layout's copper model gives 1.035 mOhm from J101 to J901 with
   the FETs at their maximum resistance: about 52 mV at 50 A and 72 mV at 70 A, measured pad to pad); the tab
   temperature climbs no more than about 20 C over the run. Compare the Pico's FET_NTC reading with the thermocouple.
2. 70 A for 1 s, then 30 s off, five times, with the same checks.
3. Open the E-stop during a 50 A pulse, with the scope on TP101 and TP301. The spike must stay well under the TVS
   clamps (27.7 V at full TVS current); expect a few volts.

Pass: no FET tab above 80 C, no hot spot on the motor-bus copper (a thermal camera helps, review m20), and a clean
switch-off. Write down the capacitor temperature too.

The turn-off time of the three FETs (estimated at 0.1-0.4 ms in `design.py`) is not verified; step 3 is where you see
it.

### Test 4: precharge into the real FSESC and BEC

The precharge has to bring the motor bus up through about 10.6 Ohm while the FSESC boots and the Castle BEC starts
the servo, and on the team's simulator that can fail at a low pack (review M3). Check it on the real parts. Bench
supply at 12.0 V (the worst case), with the current limit raised above the precharge peak (about 1.1 A at 12 V
through 10.6 Ohm). The FSESC on the ESC pads with the motor unplugged, the Castle BEC set to 7.5 V (see "Module
set-up") on BEC+ and BEC-, its output in J403, the servo in J406, the E-stop loop in J1001. Scope on TP301.

1. Precharge (GP2 high at the REPL, or a button press with the supervisor firmware): the motor bus must come to
   within 2.5 V of the supply and stop rising.
2. If the BEC's start-up holds the motor bus down, either move the BEC's red lead from BEC+ (J401, on the motor bus)
   to BEC+ALT (J410, on VSYS_SW), or fit the 4.7 Ohm 5 W resistor (SQP500JB-4R7) as R313. With J410 the Pololu
   latch, rated 6 A continuous, carries the servo as well as the dev kit, lidar and camera, so check that sum at a
   12 V pack. With 4.7 Ohm the precharge peak is about 3.6 A for about 10 ms; check that F301 (the MF-R050) does not
   trip.
3. With only the laptop on the FSESC's USB (everything else off), measure the motor bus. Above 1 V means the FSESC
   feeds its USB power back into it; cut the VBUS wire in the FSESC's USB lead (review m14).

## Module set-up

Set up each module on the bench before it is wired into the car.

### Settings that must be made before the first drive

From `boards/power/README.md`. The review traced a real fault to each one if it is left at its default.

| where | setting | why |
| --- | --- | --- |
| JBD BMS (app) | cell over-voltage 4.25 V | above the 4.20 V the charger ends at, so a cell running slightly high does not end the charge or take away regen on a full pack (review m12) |
| CC/CV buck (trimmers, on the bench) | 16.80 V constant voltage, 2.5 A constant current | 4.20 V per cell; set CV with no load, CC into a load (below) |
| FSESC (VESC Tool) | maximum input voltage 18 V | VESC limits regenerative braking to keep the bus under this, so regen on a full pack stays below the pack TVS (19-21 V) and the dev-kit cut-off (18.7 V) (review m4) |
| FSESC (VESC Tool) | battery cut-off start 13.4 V, end 12.6 V | keeps a sagging pack from pulling VSYS_SW under the dev kit's 9 V and the R-78E's 8 V (review m9) |

### Castle BEC 2.0: 7.5 V

It ships at 5.25 V and is adjustable from 4.75 to 12 V (Holmes Hobbies listing). Connect it to the Castle Link V3 and
set the output to 7.5 V in the Castle Link software. Then feed its input from the bench supply (14 V) with no servo
on its output and measure 7.5 V on the output plug's plus and minus pins before the servo is ever connected.

### PD trigger (Adafruit 5807): 20 V

On the back of the 5807, cut the 5V jumper (with every voltage jumper open, it asks for 20 V) and the 1A jumper (with
both current jumpers open, 3 A) (`design.py`, block E). Plug in the 65 W USB-C PD charger and measure VOUT to GND
with nothing connected: 20 V. If it reads 5 V, a jumper is not cut through, or the charger cannot give 20 V.

### CC/CV buck: check it, then 16.80 V and 2.5 A

The buck is a generic XL4015-class module; its markings, limits and trimmers vary between sellers, and none of it is
verified. Check the listing you bought from.

**First, check how it senses current (review B1, 5 minutes).** The board gives the charger side its own ground,
CHG_GND, and joins it to GND only through the module, from IN- to OUT-, because the common XL4015 board measures its
output current with a shunt between those two terminals. Feed the module 20 V on IN+ and IN- (from the PD trigger or
the bench supply), put the 4.7 Ohm 50 W resistor on OUT+ and OUT- (it gets hot: only for a few seconds), and measure
the voltage from IN- to OUT-:

- about 0.1 V: a low-side shunt, which is what the board is built for. Fine.
- about 0 V, and the current still follows the CC trimmer: high-side sensing (IN- and OUT- are joined inside). Also
  fine; the CHG_GND pads still work.
- the current does not follow the CC trimmer at all: do not use this module.

**Then set it:**

1. Input at 20 V, nothing on the output. Meter on volts across OUT+ and OUT-. Turn the voltage trimmer (CV) until it
   reads **16.80 V**.
2. The 4.7 Ohm resistor on the output again, with the meter on its 10 A range in series with it. Turn the current
   trimmer (CC) until it reads **2.5 A** (the output then sits near 11.8 V, so the module is in constant current).
   Be quick: the resistor takes about 30 W.
3. Take the load off, check the output still reads 16.80 V, and glue both trimmers so vibration cannot move them.

Why 16.80 V and not 17.1 V: the board's reverse block is a P-FET that is fully on while the charger is present, so
there is no diode drop to make up, and 16.80 V is 4.20 V per cell.

On the car, the module's six terminals each get their own wire to the board (see "Harnesses"). Never join IN- and
OUT- outside the module: that bypasses its current sensing, and the charge then runs at whatever the charger gives
(about 4 A, review B1). TP502 on the board is CHG_GND, for measuring.

Only after this is set does its OUT+ go to the board.

### JBD BMS: settings for the 4S NMC pack

With the Xiaoxiang app over Bluetooth, or JBD's PC tool (`docs/FLASHING.md`, rev B):

| setting | value |
| --- | --- |
| cells | 4, Li-ion (NMC) |
| cell over-voltage | 4.25 V (review m12; the charger ends at 4.20 V) |
| cell under-voltage | 3.00 V |
| discharge over-current | above 90 A (the VESC's battery limit), 1-2 s delay |
| charge over-current | about 20 A |
| charge over-temperature | 50 C |
| discharge over-temperature | 65 C |
| design capacity | 8.4 Ah |

The short-circuit setting and the release values are not specified anywhere yet; leave them at JBD's defaults and
write down what they are. Save, read the settings back, and check that every cell voltage in the app matches your
meter at the pack's balance connector.

Before anything goes onto the BMS, check every tap with a meter at the pack's 7-pin XH: B1-B0, B2-B1, B3-B2 and
B4-B3 each read one cell voltage (`docs/PACK_BUILD.md`, step 4). Then wire the battery assembly in the order the
manual for your JBD board gives (manufacturers differ on whether B- or the balance lead goes first).

Before the BMS's UART lead goes into J201, measure the voltage between its pins 1 (VDD) and 4 (GND), and the idle
level of its TX (pin 2) against pin 4. 3.3-5 V is expected, not verified. If VDD is 5 V while TX idles at 3.3 V, stop:
the board's optocoupler stage then leaks and the Pico's RX may never idle high, and the stage has to be changed first
(review m11). And remember that the BMS's GND is the pack's B-: it never connects to the board's GND.

### Pico: MicroPython, then the supervisor

1. Hold the Pico's BOOTSEL button and plug it into the laptop. It appears as a drive called RPI-RP2. Drag the
   MicroPython UF2 for the Pico onto it (https://micropython.org/download/RPI_PICO/; a Pico 2 needs RPI_PICO2). It
   restarts as a USB serial port. That is all tests 1 and 2 need.
2. After test 2, copy the six supervisor files from `firmware/supervisor/` to the Pico (not `sim.py` or `tests/`):
   ```
   cd firmware/supervisor
   mpremote connect /dev/ttyACM0 cp pins.py hal.py jbd.py link.py sequencer.py main.py :
   mpremote connect /dev/ttyACM0 reset
   ```
   or open each file in Thonny and use File > Save as... > Raspberry Pi Pico.
3. `screen /dev/ttyACM0 115200` shows a status line every second. After a reset it waits in LOCKOUT for a button
   press before it precharges; that is on purpose. Holding the power button at start-up until both LEDs light gets you
   back to the REPL (`firmware/supervisor/README.md`).

### FSESC

Set up in VESC Tool through the board's debug USB-C (UART at 115200, kill switch on ADC2, servo output, timeout,
limits): `docs/SOFTWARE.md` ("The FSESC") and `docs/FLASHING.md` (B4). Two of its settings are on the must-set list
above: maximum input voltage 18 V, and battery cut-off from 13.4 V (start) to 12.6 V (end).

## Harnesses

Lengths are from `docs/WIRING.md` (rev B), modelled with the board's final connector positions: "cut to" is the length
to cut for a lead you make, "at least" is the shortest bought cable that reaches. The heights of the plugs, the dev
kit's and the FSESC's ports, the BMS terminals and the charge modules are still estimates there (MEASURE_FIRST items
20, 21, 25, 26 and 29 to 31), so check each run on the car before you cut. Where WIRING.md has no number, the table
says so.

| harness | from | to | wire, connectors | length |
| --- | --- | --- | --- | --- |
| pack + to fuse | pack + strip | MIDI fuse input stud | 10 AWG, M5 ring terminal | cut to 90 mm |
| fuse to XT90-S | MIDI fuse output stud | pack XT90-S female, + | 10 AWG | cut to 140 mm |
| pack - to BMS | pack - strip | JBD B- | 10 AWG | cut to 120 mm |
| BMS to XT90-S | JBD P- | pack XT90-S female, - | 10 AWG | cut to 100 mm |
| balance adapter | pack 7-pin JST-XH (B0-B4, NTC, NTC return) | JBD balance connector and NTC input | adapter harness | at least 200 mm |
| pack pigtail | board J101 (BAT+), J102 (BAT-) | XT90 male, mates with the pack's XT90-S female | 10 AWG pair | cut to 90 mm each |
| BMS UART | JBD 4-pin UART port | board J201 (JST-XH 4) | adapter lead | at least 250 mm |
| J12 ribbon | dev kit J12 | board J801 | 40-wire IDC ribbon, 150 mm (Adafruit 1988), bought | at least 90 mm |
| J14 harness | dev kit J14 | board J802 | 1 x 12 Dupont housing at both ends, 8 wires | cut to 110 mm |
| FSESC COMM | FSESC COMM port | board J903 | JST-PH 7 at both ends, 4 wires | at least 50 mm |
| servo signal | FSESC servo/PPM port | board J904 | 3-pin lead (the FSESC kit includes a PPM cable) | not in WIRING.md |
| ESC battery leads | FSESC battery end | board ESC+ (J901), ESC- (J902) | the FSESC's own 12 AWG leads, run as one tied pair | cut to 50 mm each |
| Castle BEC | board BEC+ (J401; or BEC+ALT, J410, if test 4 says so), BEC- pads; its output into J403 | the BEC | its own 16 AWG leads and servo plug; the red lead long enough to reach J410 | not in WIRING.md |
| camera power | camera M8 GPIO connector | Pololu S18V20F12 output (upright on the camera arch's right leg) | LUCID GPIO-M8-5M-RA2-A, cut | cut to 120 mm |
| camera regulator input | board camera pads (MOD402, front edge) | S18V20F12 input | 22 AWG pair | cut to 80 mm |
| dev-kit DC lead | board DEV+, DEV- | dev kit DC jack | Tensility 10-01779 (5.5 x 2.5 mm right-angle plug, 18 AWG), cut | cut to 140 mm |
| latch | board latch pads | Pololu #2813 | 18 AWG VIN, VOUT, GND; 24 AWG ON, OFF | not in WIRING.md |
| PD trigger | board PD-trigger pads | Adafruit 5807 VOUT and GND (CHG_GND), in the right pod | 20 AWG pair | cut to 80 mm |
| CC/CV input | board CC/CV pads | buck IN+ and IN- (CHG_GND) | 20 AWG pair | cut to 60 mm |
| CC/CV output | board CC/CV pads | buck OUT+ and OUT- (GND) | 20 AWG pair | cut to 90 mm |
| dev kit USB-C | board J601 (USB-A receptacle at the pod edge, hub port 1) | dev kit USB-C | USB 2.0 cable, right-angle USB-A plug (cable leaving the plug's narrow side) to USB-C, 0.3 m; plug it in before the right pod goes on | at least 210 mm |
| FSESC USB | board J602 (hub port 3, 1 x 4 header) | FSESC micro-USB | Adafruit 4449 jack lead and the FSESC's micro-USB cable | at least 160 mm, the whole run |
| Pico USB | Pico micro-USB | a dev kit USB-A port | micro-USB to USB-A, 0.3 m | at least 100 mm |
| laptop port | the laptop | the hub module's USB-C, through both pod walls | the laptop's own USB-C cable; no panel socket or pigtail | |
| lidar power | board J409 | lidar power M12 | the donor SICK M12 power cable, cut and stripped | cut to 70 mm |
| fan | 40 mm fan in the right pod | board J1003 (rear edge) | the fan's own 4-pin lead | at least 120 mm |
| E-stop | board J1001 | the E-stop button | JST-PH 2; with no button, a lead with its two wires joined | |

Notes on the ones that can go wrong:

- **BMS UART.** On the board, J201 is 1 VDD, 2 TX, 3 RX, 4 GND, the same order as the JBD port in the Overkill/JBD
  manual, so the lead runs pin 1 to pin 1. The connector on the JBD is assumed to be a JST-PA 2.0, not verified. The
  JBD's Bluetooth connector is wired the other way round, so check you are on the UART port.
- **J12 ribbon.** The board end has a keyed shroud. The dev kit's J12 is not shrouded: line up the ribbon's red stripe
  with pin 1 by eye. A ribbon on the wrong way round shorts nothing (the board leaves the pins that would short
  open), but nothing works either.
- **J14 harness.** Wires on pins 3, 4, 7, 8, 9, 10, 11 and 12, pin n to pin n. Pins 1, 2, 5 and 6 stay empty; a wire
  between 5 and 6 would turn off the dev kit's auto power-on. Mark pin 1 on both housings and fit the printed key
  clip: a housing turned round puts the console's TX on FORCE_RECOVERY*.
- **FSESC COMM.** On the board, J903 is 1 3V3, 2 GND, 3 TX (the FSESC's TX), 4 RX, 5 ADC1, 6 ADC2, 7 PPM. Only GND, TX,
  RX and ADC2 get wires. The FSESC's own pin order is not published and not verified: read the silkscreen on the
  FSESC and move the crimps in the housing until GND, TX, RX and ADC2 land where the board expects them. Never connect
  the FSESC's 3.3 V pin.
- **FSESC grounds.** The COMM ground (J903 pin 2), the servo-lead ground (J904 pin 3) and the FSESC's USB ground (J602
  pin 4) go to the board's GND through 3.3, 3.3 and 2.2 Ohm on purpose, so the motor current stays in the ESC- lead
  (review M6). Never add another ground wire between the FSESC and the board.
- **Adafruit 4449 lead (J602, and J603 if used).** Red is VBUS, white D-, green D+, black GND: pins 1 to 4 in that
  order, with pin 1 (VBUS) on the square pad.
- **Dev kit USB.** J601 is a normal USB-A socket: one USB-A to USB-C cable to the dev kit's USB-C port gives USB
  networking (192.168.55.1). For flashing JetPack, if it fails through the hub, plug the laptop straight into the dev
  kit's USB-C (review M7).
- **Charge modules.** Six separate wires, in three pairs. The PD trigger's GND and the buck's IN- go to the CHG_GND
  pads, the buck's OUT- to GND. Never join IN- and OUT- outside the module (review B1).
- **Pack pigtail.** The board's pigtail ends in an XT90 male; the pack's lead ends in the XT90-S female, the half with
  the anti-spark resistor. Meter-check the polarity at both connectors before the first connection (review m15).
- **Dev-kit DC lead.** The jack is centre positive. With the board powered, check with the meter that the plug's centre
  pin is plus before it goes into the dev kit.
- **Camera power.** Red (pin 1, VAUX) and black (pin 5, GND) of the M8 cable go to the regulator's 12 V output. Cut the
  other six wires back, insulate each one and tie them back.
- **E-stop.** With J1001 empty the motor never runs. Fit the button or the joined lead.
- **Ribbon and harness security.** Ribbons work loose under vibration; a dab of hot glue or a printed clamp at the
  board end helps.

## Sign-off

Builder and checker sign each line. Keep this sheet with the board's serial number.

Board serial number: ________  Builder: ________  Checker: ________  Date: ________

- [ ] Kit counted against the BOM, block by block; R801, R802 and R805 left empty.
- [ ] Every part in the orientation table checked by a second person before soldering; the three TO-220 types and
      the three TVS types each in their own places.
- [ ] Under the microscope: no bridges on the bottom chips, the DIP sockets, the module sockets, J801, J903 or J601;
      no tombstoned chips.
- [ ] Heights: nothing under the Pico or the hub above 9 mm; nothing in the tray area above 23 mm, fuse holders with
      their fuses in. Highest live point of the FET bar and tabs: ______ mm (21 mm at most under the shield).
- [ ] No continuity from GND to BAT+, the motor bus, VSYS_SW, +5V or +3V3 (a short chirp while the capacitors charge
      is fine); no continuity between J201 pin 4 and GND.
- [ ] FET bar: three nuts tight, Kapton on its outer face, NTC against it with Kapton between.
- [ ] Test 1 passed. Supply current at 5 V: ______ mA. TP701: ______ V.
- [ ] Test 2 passed. Off current at 14 V: ______. SW_GATE minus the motor bus at 12 V: ______ V. Over-voltage
      cut-off trips at ______ V and releases at ______ V.
- [ ] Test 3 passed. Highest tab temperature at 50 A: ______ C; at 70 A: ______ C. C101: ______ C. Switch-off spike:
      ______ V.
- [ ] Test 4 passed. Motor bus after precharge at 12.0 V: ______ V. BEC on BEC+ (J401) / BEC+ALT (J410), R313
      10 / 4.7 Ohm (circle). Motor bus with only the laptop on the FSESC's USB: ______ V.
- [ ] Castle BEC measured at 7.5 V before the servo was connected: ______ V.
- [ ] PD trigger: 20 V. CC/CV module check, IN- to OUT- at 2.5 A: ______ V. Buck set to 16.80 V and 2.5 A, trimmers
      glued.
- [ ] JBD settings saved and read back, cell over-voltage 4.25 V; cell voltages match the meter; UART VDD: ______ V,
      TX idle: ______ V.
- [ ] FSESC: maximum input voltage 18 V; battery cut-off 13.4 V to 12.6 V.
- [ ] Pico: MicroPython and the six supervisor files; a status line seen every second.
- [ ] Harnesses: J14 pin 1 marked and key clip on; ribbon stripe on pin 1; COMM crimps checked against the FSESC
      silkscreen, 3.3 V pin empty; DC lead centre positive; pack pigtail and XT90 polarity checked; charge modules on
      six separate wires.
- [ ] Acrylic FET shield fitted under the dev-kit tray.
- [ ] E-stop button or joined lead in J1001.
- [ ] Flux cleaned off both sides.
