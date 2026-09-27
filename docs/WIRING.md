# Wiring: every cable, where it runs and how long it is

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
| Wi-Fi antenna 1 | M.2 Wi-Fi card (under the Jetson module) | antenna jack, canopy rear left | u.FL/MHF4 to RP-SMA bulkhead pigtail, 1.13 or 1.37 mm coax | 80 | needs at least 110 |
| Wi-Fi antenna 2 | M.2 Wi-Fi card (under the Jetson module) | antenna jack, canopy rear right | u.FL/MHF4 to RP-SMA bulkhead pigtail, 1.13 or 1.37 mm coax | 67 | needs at least 100 |

## How each one runs

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
  - Check the card's connector before ordering: M.2 cards usually use MHF4, not u.FL.
- **E-stop.** Nothing runs here unless an E-stop button is fitted. Close J504 with a JST-PH wire loop, or the
  motor will not run.
