# Wiring: every cable, where it runs and how long it is

## Rev B (Oct 24): power board, dev-kit carrier, FSESC, BMS on the pack

The lengths come from the cable paths in `mech/extras.py`, drawn through the rev B model: the power board's height
map, the dev-kit tray and carrier with the plugs on its I/O edge, the FSESC in its cradle, the BMS on the pack lid,
the charge modules in the right pod, the sensors and the chassis keep-outs (`mech/NOTES_REVB.md`). The power-board
ends are agent D's final connector positions (`boards/power/HANDOFF_E.md`, "Real connector positions", in
`extras.POWER_CONN`) on the 130 mm layout. "Routed" is the length of the modelled path; "was" is the same run with
the placeholder positions used before D's layout (a run marked "new" did not exist then). The last column adds 10 %
and 20 mm to the routed length: for a lead you make it is the length to cut, for a part's own lead or a bought
cable it is the shortest that reaches. At the 130 mm board every run below is clear of every part and of every other
cable, with the printed parts and with the laser-cut ones (`SHEET_PARTS=all`).

What is still an estimate: the heights of the plugs on the board's headers, the dev kit's headers and ports, the
FSESC's ports, the BMS's terminals, the mated XT90 pair, J601's height and the right-angle plug in it, and the charge
modules (MEASURE_FIRST items 20, 21, 25, 26, 29 to 31). The 150 mm column is gone: D's positions belong to the 130 mm
layout.

| cable | from | to | what | routed mm | was (placeholders) | length mm |
| --- | --- | --- | --- | ---: | ---: | --- |
| Camera data | dev kit RJ45 | camera M12 | M12 X-coded 8-pin to RJ45, Cat6a, data only (0.5 m cable) | 122 | 122 | needs at least 160 |
| Camera power (M8 lead) | camera M8 GPIO (right angle, up) | camera 12 V regulator output (on the arch, right leg) | LUCID GPIO-M8-5M-RA2-A cut to length: red (VAUX) and black (GND) to the 12 V regulator output, other six tied back | 89 | 170 | cut to 120 |
| Camera regulator input | power board camera regulator pads MOD402 (front edge) | camera 12 V regulator input | 22 AWG pair, board MOD402 pads (VIN, GND) to the Pololu S18V20F12 input | 53 | new | cut to 80 |
| Lidar Ethernet | USB-Ethernet dongle RJ45 (on the arch leg) | lidar Ethernet M12 | donor SICK M12 D-coded 4-pin to RJ45 (TiM561 Ethernet), into the USB dongle | 41 | 41 | needs at least 70 |
| Lidar dongle USB | USB-Ethernet dongle | dev kit USB-A (port 1) | the dongle's own USB 3 lead (180 mm on the ZimaSpace RTL8153 adapter) | 137 | 137 | needs at least 180 |
| Lidar power | power board lidar Phoenix 2-pin J409 (front edge) | lidar power M12 | donor SICK M12 power cable, cut and stripped into the terminal | 42 | 15 | cut to 70 |
| Dev-kit DC lead | power board DEV+ / DEV- pads (pack side) | dev kit DC jack | Tensility 10-01779 5.5 x 2.5 mm right-angle plug, 18 AWG pair, cut to length | 103 | 40 | cut to 140 |
| 40-pin ribbon | dev kit J12 (40-pin) | power board 2 x 20 box header | 2 x 20 IDC ribbon, 150 mm (Adafruit #1988); modelled as three lines across its width | 60 | 62 | needs at least 90 |
| J14 harness | dev kit J14 (button header) | power board 1 x 12 header J802 (middle) | 1 x 12 Dupont housing, 8 crimped wires (keyed with a printed clip) | 75 | 42 | cut to 110 |
| Dev-kit USB-C to J601 | power board J601 USB-A (pod edge, hub port 1) | dev kit USB-C (device mode, 192.168.55.1) | USB-A right-angle plug (cable leaving the narrow side, so up here) to USB-C, 0.3 m, USB 2.0 | 165 | 106 (to the hub) | needs at least 210 |
| Pico USB to dev kit | Pico micro-USB (power board, pack edge) | dev kit USB-A (port 2) | micro-USB to USB-A, 0.3 m (supervisor USB CDC to the Jetson) | 67 | 67 | needs at least 100 |
| FSESC USB to J602 | FSESC USB (front end, position ESTIMATE) | power board J602 (hub port 3, 1 x 4 header) | FSESC micro-USB lead (the kit's cable) into the USB jack lead on J602 (Adafruit 4449, D's choice); length is the whole run | 121 | 84 (to the hub) | needs at least 160 |
| FSESC COMM lead | FSESC COMM port (front end, position ESTIMATE) | power board J903 (rear edge) | FSESC COMM lead, JST-PH 7-pin both ends (UART TX/RX/GND, ADC2 kill) | 22 | 12 | needs at least 50 |
| PD trigger to board | PD trigger (right pod) | power board PD-trigger pads | 20 AWG pair, PD trigger VOUT / GND (CHG_GND) to the board pads | 50 | new | cut to 80 |
| CC/CV input pair | CC/CV module, input end (right pod) | power board CC/CV pads | 20 AWG pair, CC/CV IN+ / IN- (CHG_GND) to the board pads | 36 | new | cut to 60 |
| CC/CV output pair | CC/CV module, output end (right pod) | power board CC/CV pads | 20 AWG pair, CC/CV OUT+ / OUT- (GND) to the board pads | 60 | new | cut to 90 |
| Motor phase A | FSESC phase A (motor end) | motor phase A | FSESC 12 AWG phase A lead, 4 mm bullet at the motor | 86 | 86 | cut to 120 |
| Motor phase B | FSESC phase B (motor end) | motor phase B | FSESC 12 AWG phase B lead, 4 mm bullet at the motor | 109 | 109 | cut to 140 |
| Motor phase C | FSESC phase C (motor end) | motor phase C | FSESC 12 AWG phase C lead, 4 mm bullet at the motor | 120 | 120 | cut to 160 |
| Motor hall sensor | FSESC hall port (motor end) | motor sensor port | motor's own 6-pin sensor lead into the FSESC's hall port | 132 | 132 | needs at least 170 |
| ESC battery + | FSESC battery end | power board ESC+ pad (rear edge) | FSESC 12 AWG battery + lead, soldered to the board pad | 19 | 62 | cut to 50 |
| ESC battery - | FSESC battery end | power board ESC- pad (rear edge) | FSESC 12 AWG battery - lead, soldered to the board pad | 24 | 85 | cut to 50 |
| Steering servo | steering servo | power board servo header J406 (front edge) | servo's own 3-wire lead | 93 | 86 | needs at least 130 |
| Pack pigtail + | power board BAT+ pad (pack edge) | XT90 male, + (mates with the pack XT90-S) | 10 AWG silicone pigtail, board BAT+ pad to the XT90 male (+) | 58 | new | cut to 90 |
| Pack pigtail - | power board BAT- pad (pack edge) | XT90 male, - (mates with the pack XT90-S) | 10 AWG silicone pigtail, board BAT- pad to the XT90 male (-) | 56 | new | cut to 90 |
| Pack + to fuse | pack + strip (under the lid) | MIDI 125 A fuse, input stud | 10 AWG silicone, pack + (G4 end strip) to the MIDI fuse holder input | 59 | 59 | cut to 90 |
| Fuse to XT90-S | MIDI fuse, output stud | pack XT90-S, + (mates with the board pigtail) | 10 AWG silicone, fuse output stud to the pack XT90-S (B+) | 106 | 64 | cut to 140 |
| Pack - to BMS | pack - strip (under the lid) | JBD BMS B- | 10 AWG silicone, pack - (G1 end strip) to the BMS B- | 88 | 88 | cut to 120 |
| BMS P- to XT90-S | JBD BMS P- | pack XT90-S, - (mates with the board pigtail) | 10 AWG silicone, BMS P- to the pack XT90-S (system ground) | 68 | 96 | cut to 100 |
| Balance lead | pack taps B0-B4 and NTC | JBD BMS balance connector | pack's 7-wire sense lead (JST-XH 7-pin) and the adapter harness to the BMS balance and NTC inputs | 163 | 163 | needs at least 200 |
| BMS UART | JBD BMS UART port | power board J201 BMS UART (pack edge) | JBD 4-pin UART lead to the board J201 JST-XH 4-pin (opto-isolated on the board) | 200 | 144 | needs at least 250 |
| Side-pod fan | 40 mm fan (right pod) | power board fan header J1003 (rear edge) | the fan's own 4-pin lead (fan to the power board) | 88 | 230 | needs at least 120 |
| Wi-Fi antenna 1 | M.2 Wi-Fi card (under the carrier) | antenna jack 1, canopy rear edge | MHF4 to RP-SMA bulkhead pigtail, 1.13 mm coax (order 20 cm) | 104 | 104 | needs at least 140 |
| Wi-Fi antenna 2 | M.2 Wi-Fi card (under the carrier) | antenna jack 2, canopy rear edge | MHF4 to RP-SMA bulkhead pigtail, 1.13 mm coax (order 20 cm) | 160 | 160 | needs at least 200 |

### How each one runs (rev B)

- **Camera.** Data: from the dev kit's RJ45 on its I/O edge (toward the pack), forward over the pack lid under the
  canopy, out past the canopy's front edge and up to the camera's M12 plug behind the arch. A 0.5 m M12 X-coded to
  RJ45 cable leaves about 0.38 m to coil; it no longer needs to be PoE-rated. Power: the board feeds the camera
  through a Pololu S18V20F12 12 V regulator off the board (D's design). D's notes put it "on the tray", but the
  tray is a frame with no free surface outside the carrier, so the model stands it upright against the rear face
  of the camera arch's right leg, the mirror image of the lidar dongle on the left leg. A 22 AWG pair runs from the
  MOD402 pads on the board's front edge up to its input; the LUCID M8 lead, cut to length, runs from the camera down
  the arch to its output.
- **Lidar.** The USB-Ethernet dongle stands upright against the rear face of the camera arch's left leg, jack down.
  The donor M12-to-RJ45 cable runs from the lidar's Ethernet plug a short way back and up into it; coil the rest
  on the deck under the arch, below the scan plane. The dongle's own USB lead runs back over the board's front, under
  the canopy, into the dev kit's first USB-A port. The lidar power cable runs forward from the Phoenix terminal J409
  (wires in from the front) to its M12 plug.
- **Dev kit.** The DC lead leaves the DEV+ / DEV- pads (under the carrier, near the pack edge), runs under the tray
  past the middle standoff, out over the pack edge west of the pack + lead and along the lid's edge under the dev
  kit's plugs to the right-angle plug in the DC jack. The 40-pin ribbon folds over the carrier's right edge, drops
  between the board and the right pod and comes in under the tray to the box header J801. The J14 harness drops the
  same way just behind the laptop plug and runs in under the tray to the 1 x 12 header J802 in the board's middle.
  The Pico's micro-USB comes up from the board's pack edge into the second USB-A port.
- **Dev kit USB-C to J601.** J601 is a USB-A standing on its edge at the board's pod edge, and the cable is USB-A to
  USB-C. A straight USB-A plug needs about 40 mm beyond the board edge (D's estimate); the pod's outer face is 26 mm
  away, so a straight plug would stand out of the pod. The model takes a right-angle USB-A plug whose cable leaves
  the plug's narrow side, which is upward on this receptacle (head about 9 x 12 x 18 mm, an estimate): the head's
  tail stands into a window in the pod's inner wall, and the cable rises in the 8 mm gap between the board and the
  pod, runs forward past the J14 housing, crosses over the carrier's front strip in front of the heatsink, and curls
  down and round under the USB-C plug into it from behind. Plug it in before the right pod goes on. 165 mm routed: a
  0.3 m cable.
- **Laptop.** The laptop's own USB-C cable plugs straight into the hub module's USB-C through both pod walls (car x
  56.5); there is no panel socket and no pigtail any more.
- **ESC.** The three phase leads leave the FSESC's motor end, go outboard and drop through the deck opening at
  x -112 to -101 in staggered columns, then run under the deck to the motor's end bell; the hall lead goes over them
  and down the same opening. The two battery leads come out of the FSESC's front end and go straight onto the ESC+ /
  ESC- pads 5 mm inside the board's rear edge (19 and 24 mm: cut the FSESC's leads to about 50 mm and solder them
  from above). The COMM lead goes to J903 on the rear edge. The FSESC's micro-USB lead runs over the rear strip and in
  under the tray to the USB jack lead on J602 in the board's middle.
- **Charging.** The PD trigger (Adafruit 5807) lies flat in the right pod with its USB-C at the outer wall's charge
  window (car x 19) and runs inboard through a slot in the inner wall; its two wires go to the PD-trigger pads. The
  CC/CV module stands on edge in the pod (car x -50 to 1), its input and output pairs through a window in the inner
  wall to the CC/CV pads. Six wires, one per module terminal: never join IN- and OUT- outside the module.
- **Servo.** Straight down from the servo plug on J406 near the front edge, through the deck slot at x 98.5 to
  103.5 just ahead of the board.
- **Battery assembly.** Pack + comes up through the lid's front slot into the MIDI fuse holder on the lid; the fuse's
  other stud goes to the pack's XT90-S. Pack - comes up through the rear slot to the BMS's B- at its rear end; the
  BMS's P- goes to the XT90-S. The board's 10 AWG pigtail (BAT+ and BAT- pads on its pack edge) ends in an XT90 male;
  the mated pair lies on the lid along x (car x -60 to -14, y 30 to 52) and is the manual master. The pack's 7-pin
  sense lead goes through its adapter harness to the BMS's balance and NTC inputs, and the BMS's UART lead runs over
  the fuse to J201 on the board's pack edge (200 mm: longer than before, because J201 is now near the front).
- **Side-pod fan.** Out of the fan window, forward low on the deck in the gap between the board and the pod, and in
  over the board's rear corner to the fan header J1003 on the rear edge: 88 mm (230 mm when the header was on the
  front edge).
- **Wi-Fi.** The two pigtails leave the M.2 card under the carrier, come out under its I/O edge behind the unused
  DisplayPort (the one gap in the row of plugs), and rise and run back to the RP-SMA jacks on the canopy's rear edge.
  The longer run is 160 mm: order 20 cm pigtails (the 15 cm ones on the parts list do not reach).
- **E-stop.** Close its JST-PH (J1001, front edge) with a wire loop if no button is fitted, or the motor will not
  run.

## Rev A (Sept 27, history)

The lengths come from the cable paths in `mech/extras.py`. Each path is drawn through the car model and checked
against the kit, the boards, the new parts and the chassis keep-outs, and none of them hit anything
(`mech/out/extras_report.json`, `cable_interference`). "Routed" is the length of the modelled path. The last
column adds 10 % and 20 mm:

- For a lead you make, it is the length to cut.
- For a part's own lead or a bought cable, it is the shortest that reaches.

The chassis numbers these paths depend on are estimates (MEASURE_FIRST.md), so cut the 12 AWG and 10 AWG leads
only after the car is measured.

| cable | from | to | what | routed mm | length mm |
| --- | --- | --- | --- | ---: | --- |
| Camera | brain board J6 (RJ45, PoE port) | camera M12 | M12 X-coded 8-pin to RJ45, Cat6a (camera data and PoE power) | 270 | needs at least 320 |
| Lidar Ethernet | brain board J1301 (RJ45) | lidar Ethernet M12 | donor SICK M12 D-coded 4-pin to RJ45 (TiM561 Ethernet) | 94 | needs at least 130 |
| Lidar power | drive board J902 (2-pin terminal) | lidar power M12 | donor SICK M12 power cable, cut and stripped into the terminal | 49 | needs at least 80 |
| Motor phase A | drive board J501 (wire pad) | motor phase A | 12 AWG silicone, phase A, 4 mm bullet at the motor | 215 | cut to 260 |
| Motor phase B | drive board J502 (wire pad) | motor phase B | 12 AWG silicone, phase B, 4 mm bullet at the motor | 204 | cut to 250 |
| Motor phase C | drive board J503 (wire pad) | motor phase C | 12 AWG silicone, phase C, 4 mm bullet at the motor | 173 | cut to 220 |
| Motor hall sensor | drive board J603 | motor sensor port | motor's own sensor lead (6-pin, JST-ZH assumed) | 128 | needs at least 170 |
| Steering servo | drive board J901 | steering servo | servo's own 3-wire lead | 92 | needs at least 130 |
| Pack + | pack + strip (under the lid) | drive board J101 B+ | 10 AWG silicone, pack + (G4 end strip) to B+ | 94 | cut to 130 |
| Pack - | pack - strip (under the lid) | drive board J102 B- | 10 AWG silicone, pack - (G1 end strip) to B- | 68 | cut to 100 |
| Pack sense lead | pack taps B0-B4 and NTC | drive board J103 | 7-wire 24 AWG sense lead, JST-XH 7-pin at the board | 60 | cut to 90 |
| Side-pod fan | 40 mm fan (right pod) | drive board J903 | fan lead, 4-pin (fan to the drive board) | 56 | needs at least 90 |
| Wi-Fi antenna 1 | M.2 Wi-Fi card (under the Jetson module) | antenna jack, canopy rear left | MHF4 to RP-SMA bulkhead pigtail, 15 cm, 1.13 mm coax | 80 | needs at least 110 |
| Wi-Fi antenna 2 | M.2 Wi-Fi card (under the Jetson module) | antenna jack, canopy rear right | MHF4 to RP-SMA bulkhead pigtail, 15 cm, 1.13 mm coax | 67 | needs at least 100 |

### How each one runs (rev A)

- **Camera.**
  - The plug goes straight out of J6 through the slot in the right side pod.
  - The cable turns up and forward, lies along the pod's top (zip-tie slot pairs at x 4 and 70) and climbs to
    the camera's M12 plug behind the camera arch.
  - The LUCID cable on the parts list is 2 m, which leaves about 1.7 m to coil. Tie the coil flat on the rear
    deck under the wing, away from the lidar's field of view.
  - A shorter M12 X-coded to RJ45 cable (0.5 m) avoids the coil; it must be rated for PoE.
- **Lidar Ethernet.**
  - From the TiM561's left M12 plug, under the camera arch, back and up to J1301.
  - J1301 opens toward the car's left, so the plug and boot point left over the pack lid.
  - The donor cable is longer than the run: coil the rest on the deck behind the arch, below the scan plane.
- **Lidar power.**
  - From the right M12 plug, straight back to the J902 terminal at the drive board's front edge.
  - Wire the terminal before the brain board goes on: its screws are under the brain board's front edge.
- **Motor phases and hall lead.**
  - The three 12 AWG pigtails leave their pads toward the right edge and run back along the drive board.
  - They pass over its rear edge and forward again in the 7 mm gap under it, then down through the deck opening
    at x -58 to -46.
  - Under the deck they run out to the motor's end bell. The bullets sit on the end bell at 120 degrees.
  - The hall lead follows the same route to the sensor port.
- **Servo.** Forward from J901, down through the new 5 x 24 mm deck slot at x 98.5 to 103.5, then under the
  cross rib to the servo.
- **Pack.**
  - The 10 AWG leads come up through the lid slots and go down into the drive board's through-hole wire pads:
    pack + (the front end, G4) to B+, pack - (the rear end, G1) to B-.
  - The pack - lead crosses over the pack + lead.
  - The 7-wire sense lead comes out of the middle slot to J103.
  - Connect the sense lead first (PACK_BUILD.md, step 6).
- **Side-pod fan.**
  - The fan's lead comes in through the fan window in the right pod and runs back to J903.
  - It passes inboard of the brain board's 20 mm standoff at the rear-right corner.
- **Wi-Fi.**
  - Two pigtails run from the M.2 card under the Jetson module to the RP-SMA jacks in the canopy.
  - The dev kit's card (AzureWave AW-CB375NF) has MHF4 jacks, so the ordered pigtails are MHF4, 15 cm. The
    slack, 7 to 8 cm each, coils beside the Jetson module.
- **E-stop.** Nothing runs here unless an E-stop button is fitted. Close J504 with a JST-PH wire loop, or the
  motor will not run.
