# Wiring: every cable, where it runs and how long it is

## Rev B (Oct 24): power board, dev-kit carrier, FSESC, BMS on the pack

The lengths come from the cable paths in `mech/extras.py`, drawn through the rev B model: the power board's height
map, the dev-kit tray and carrier with the plugs on its I/O edge, the FSESC in its cradle, the BMS on the pack lid,
the sensors and the chassis keep-outs (`mech/NOTES_REVB.md`). "Routed" is the length of the modelled path at the
layout's 130 mm board (the default), with the 150 mm figures for reference; the board's length only changes the runs
that end on its front edge. The last column adds 10 % and 20 mm to the 130 mm figure: for a lead you make it is the
length to cut, for a part's own lead or a bought cable it is the shortest that reaches. The same paths clear the
laser-cut canopy and BMS holder (`SHEET_PARTS=all`).

Three things make these numbers provisional. The connector positions on the power board are placeholders from before
the layout (`extras.POWER_CONN`); agent D's 130 mm layout has since moved some of them (the fan header to the rear
edge, the ESC and pack leads onto wire pads), so update that dict from `boards/power/layout.py` and rerun. The dev kit's headers and ports, the FSESC's ports and the BMS's terminals
are estimates (MEASURE_FIRST items 20, 21 and 25). And at a 150 mm board the lidar's Ethernet cable has no clean
path: the board's front-left corner sits inside the lidar's M12 plugs (MEASURE_FIRST item 12). At 130 mm every run
below is clear of every part and of every other cable.

| cable | from | to | what | routed mm (L 130) | routed mm (L 150) | length mm |
| --- | --- | --- | --- | ---: | ---: | --- |
| Camera data | dev kit RJ45 | camera M12 | M12 X-coded 8-pin to RJ45, Cat6a, data only (0.5 m cable) | 122 | 122 | needs at least 160 |
| Camera power (M8) | camera M8 GPIO (right angle, up) | power board camera 2-pin (front edge) | LUCID GPIO-M8-5M-RA2-A cut to length: red (VAUX) and black (GND) to the board, other six tied back | 170 | 173 | cut to 210 |
| Lidar Ethernet | USB-Ethernet dongle RJ45 (on the arch leg) | lidar Ethernet M12 | donor SICK M12 D-coded 4-pin to RJ45 (TiM561 Ethernet), into the USB dongle | 41 | 41 | needs at least 70 |
| Lidar dongle USB | USB-Ethernet dongle | dev kit USB-A (port 1) | the dongle's own USB 3 lead (180 mm on the ZimaSpace RTL8153 adapter) | 137 | 137 | needs at least 180 |
| Lidar power | power board lidar Phoenix 2-pin (front edge) | lidar power M12 | donor SICK M12 power cable, cut and stripped into the terminal | 15 | 5 | cut to 40 |
| Dev-kit DC lead | power board DC pads (pack edge) | dev kit DC jack | Tensility 10-01779 5.5 x 2.5 mm right-angle plug, 18 AWG pair, cut to length | 40 | 40 | cut to 70 |
| 40-pin ribbon | dev kit J12 (40-pin) | power board 2 x 20 box header | 2 x 20 IDC ribbon, 150 mm (Adafruit #1988); modelled as three lines across its width | 62 | 62 | needs at least 90 |
| J14 harness | dev kit J14 (button header) | power board 1 x 12 header | 1 x 12 Dupont housing, 8 crimped wires (keyed with a printed clip) | 42 | 42 | cut to 70 |
| Dev-kit USB-C to hub | dev kit USB-C (device mode, 192.168.55.1) | power board USB hub | USB-C to USB-C (or to the hub module socket) 0.25 m, USB 2.0 | 106 | 106 | needs at least 140 |
| Pico USB to dev kit | Pico micro-USB (power board) | dev kit USB-A (port 2) | micro-USB to USB-A, 0.3 m (supervisor USB CDC to the Jetson) | 67 | 67 | needs at least 100 |
| FSESC USB to hub | FSESC USB (front end, position ESTIMATE) | power board USB hub | FSESC micro-USB to the hub (the kit's cable, or a 0.3 m one) | 84 | 84 | needs at least 120 |
| FSESC COMM lead | FSESC COMM port (front end, position ESTIMATE) | power board FSESC header (rear edge) | FSESC COMM lead, JST-PH 7-pin both ends (UART TX/RX/GND, ADC2 kill) | 12 | 12 | needs at least 40 |
| Debug USB-C pigtail | right pod, debug window | power board USB hub | panel-mount USB-C socket with a 0.2 m pigtail to the hub (or a THT receptacle at the board edge: no cable) | 83 | 83 | needs at least 120 |
| Motor phase A | FSESC phase A (motor end) | motor phase A | FSESC 12 AWG phase A lead, 4 mm bullet at the motor | 86 | 86 | cut to 120 |
| Motor phase B | FSESC phase B (motor end) | motor phase B | FSESC 12 AWG phase B lead, 4 mm bullet at the motor | 109 | 109 | cut to 140 |
| Motor phase C | FSESC phase C (motor end) | motor phase C | FSESC 12 AWG phase C lead, 4 mm bullet at the motor | 120 | 120 | cut to 160 |
| Motor hall sensor | FSESC hall port (motor end) | motor sensor port | motor's own 6-pin sensor lead into the FSESC's hall port | 132 | 132 | needs at least 170 |
| ESC battery + | FSESC battery end | power board XT60PW (rear edge) | FSESC 12 AWG battery + lead to an XT60 female | 62 | 62 | cut to 90 |
| ESC battery - | FSESC battery end | power board XT60PW (rear edge) | FSESC 12 AWG battery - lead to an XT60 female | 85 | 85 | cut to 120 |
| Steering servo | power board servo header (front edge) | steering servo | servo's own 3-wire lead | 86 | 125 | needs at least 120 |
| Pack + to fuse | pack + strip (under the lid) | MIDI 125 A fuse, input stud | 10 AWG silicone, pack + (G4 end strip) to the MIDI fuse holder input | 59 | 59 | cut to 90 |
| Fuse to XT90-S | MIDI fuse, output stud | XT90-S male, + (into the board XT90) | 10 AWG silicone, fuse output stud to the XT90-S male (B+) | 64 | 64 | cut to 100 |
| Pack - to BMS | pack - strip (under the lid) | JBD BMS B- | 10 AWG silicone, pack - (G1 end strip) to the BMS B- | 88 | 88 | cut to 120 |
| BMS P- to XT90-S | JBD BMS P- | XT90-S male, - (into the board XT90) | 10 AWG silicone, BMS P- to the XT90-S male (system ground) | 96 | 96 | cut to 130 |
| Balance lead | pack taps B0-B4 and NTC | JBD BMS balance connector | pack's 7-wire sense lead (JST-XH 7-pin) and the adapter harness to the BMS balance and NTC inputs | 163 | 163 | needs at least 200 |
| BMS UART | JBD BMS UART port | power board BMS UART (pack edge) | JBD 4-pin UART lead to the board JST-XH 4-pin (opto-isolated on the board) | 144 | 144 | needs at least 180 |
| Side-pod fan | 40 mm fan (right pod) | power board fan 4-pin (front edge) | fan lead, 4-pin (fan to the power board) | 230 | 250 | needs at least 280 |
| Wi-Fi antenna 1 | M.2 Wi-Fi card (under the carrier) | antenna jack 1, canopy rear edge | MHF4 to RP-SMA bulkhead pigtail, 1.13 mm coax (order 20 cm) | 104 | 104 | needs at least 140 |
| Wi-Fi antenna 2 | M.2 Wi-Fi card (under the carrier) | antenna jack 2, canopy rear edge | MHF4 to RP-SMA bulkhead pigtail, 1.13 mm coax (order 20 cm) | 160 | 160 | needs at least 200 |

### How each one runs (rev B)

- **Camera.** Data: from the dev kit's RJ45 on its I/O edge (toward the pack), forward over the pack lid under the
  canopy, out past the canopy's front edge and up to the camera's M12 plug behind the arch. A 0.5 m M12 X-coded to
  RJ45 cable leaves about 0.38 m to coil; it no longer needs to be PoE-rated. Power: the LUCID M8 GPIO cable leaves
  the camera's rear upward, comes back over the arch bar and down in front of the canopy to the camera 2-pin on the
  power board's front edge. Cut it to about 0.25 m.
- **Lidar.** The USB-Ethernet dongle stands upright against the rear face of the camera arch's left leg, jack down.
  The donor M12-to-RJ45 cable runs from the lidar's Ethernet plug a short way back and up into it; coil the rest
  on the deck under the arch, below the scan plane. The dongle's own USB lead runs back over the board's front, under
  the canopy, into the dev kit's first USB-A port. The lidar power cable goes straight from its M12 plug into the
  Phoenix terminal on the board's front edge.
- **Dev kit.** The DC lead rises from pads on the board's pack edge into the right-angle plug in the DC jack. The
  40-pin ribbon folds over the carrier's right edge, drops outboard of the board (between the board and the right
  pod) and comes in under the tray to the box header near the board's right edge; it shifts about 12 mm rearward on
  the way down to clear the tray's middle standoff. The J14 harness drops the same way a little further forward.
  The dev kit's USB-C runs down past the pack edge to the hub on the board; the Pico's micro-USB comes up from the
  board's pack edge into the second USB-A port.
- **ESC.** The three phase leads leave the FSESC's motor end, go outboard and drop through the deck opening at
  x -112 to -101 in staggered columns, then run under the deck to the motor's end bell; the hall lead goes over them
  and down the same opening. The two battery leads leave the FSESC's front end, which is only 6.5 mm from the power
  board, turn inboard at once and come back into the XT60 on the board's rear edge from behind. The COMM lead goes
  straight to its header on the rear edge, the USB lead over the rear strip to the hub.
- **Servo.** At a board of 130 mm or less, straight down from the front-edge header through the deck slot at x 98.5
  to 103.5 just ahead of the board. At a longer board, back along the right edge, down through the board's notch and
  the extended slot.
- **Battery assembly.** Pack + comes up through the lid's front slot into the MIDI fuse holder on the lid; the fuse's
  other stud goes to the XT90-S. Pack - comes up through the rear slot to the BMS's B- at its rear end; the BMS's P-
  goes to the XT90-S. The XT90-S plugs into the board-mount XT90 on the board's pack edge and is the manual master.
  The pack's 7-pin sense lead goes through its adapter harness to the BMS's balance and NTC inputs, and the BMS's
  UART lead goes to the isolated JST-XH on the board's pack edge.
- **Side-pod fan.** Forward from the fan window along the right edge, low on the deck between the board and the
  pod, to the fan header on the board's front edge: 230 to 250 mm. A fan header on the rear edge would make it about
  60 mm.
- **Wi-Fi.** The two pigtails leave the M.2 card under the carrier, come out under its I/O edge behind the unused
  DisplayPort (the one gap in the row of plugs), and rise and run back to the RP-SMA jacks on the canopy's rear edge.
  The longer run is 161 mm: order 20 cm pigtails (the 15 cm ones on the parts list do not reach).
- **E-stop.** Close its JST-PH on the board's front edge with a wire loop if no button is fitted, or the motor will
  not run.

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
