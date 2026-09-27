# What it takes to finish the car

By 27 September the two boards, the pack and the printed kit were done, but a few things a builder needs were
not drawn yet. Later that day the whole car was put together in one model: the kit and boards, every mating
plug and every cable run, plus a stand-in Slash 4x4 underneath. `mech/extras.py` checks all of it against the kit
the same way `mech/kit.py` checks the kit itself.

That turned up two parts that could not have been assembled as drawn. It also showed what was still missing: a
cover over the board stack with somewhere to mount the Wi-Fi antennas, a stand for the bench tests, and a few
small bought parts.

## Fixed in the kit (`mech/kit.py`)

**The camera plug had nowhere to go.** The camera's RJ45 jack (brain board J6, from Antmicro's layout) opens
toward the car's right side, 2 mm from the right side pod's inner wall. The side-pod fan sat directly outboard
of it, at x -46 to -6. A plug and its boot need about 32 mm straight out of the jack.

- The fan moved forward to x -16 to 24 (`FAN_X`). It is now centred on the ESC power stage (x -30 to 20)
  instead of behind it. The 32 mm screw pattern moved with it.
- The right pod has a 20 mm slot, open at the top, through both walls at the jack (`CAM_PLUG_NOTCH`, x -40.5 to
  -20.5, from z 27 up). The plug and boot pass through it with 3 mm to spare on each side and 4.7 mm above the
  slot floor.
- Two pairs of zip-tie slots on the right pod's top (`POD_TIE_SLOTS_X`, x 4 and 70) hold the camera cable.
  From there it runs forward and up to the camera.

**The servo-lead slot was blocked.** The deck slot for the steering servo lead (x 86 to 98) sat over the right
front splice plate (x 67 to 97) and around the joint bolt at (92, -40). That bolt had no deck around it.

- The slot is now 5 x 24 mm at x 98.5 to 103.5 (`SERVO_SLOT`). That is between the splice plates and the cross
  rib at x 104.
- A 3-pin servo plug goes through it on edge.

Both changes rerun clean: `kit.py` reports no interference, and the pack still fits its bay with 2.8 mm under it.

## New parts (`mech/extras.py`)

| part | what it is for | print |
| --- | --- | --- |
| `stack_canopy` | A cover over the board stack. It protects the Jetson and the boards in a roll, gives the Wi-Fi antennas somewhere to mount, and carries a hex grille over the Jetson fan. | PETG-CF, top face down, no supports; 128 x 99 x 6.4 mm, about 41 g solid |
| `bench_stand` | Holds the chassis by its floor with the wheels about 13 mm off the bench. The ESC bench tests at 50 A and 70 A need the wheels free (ARCHITECTURE.md, First power-up). | PLA or PETG, top down; 173 x 123 x 128 mm |

**Canopy details**

- It sits on three M3 x 40 mm male-female standoffs. They screw into the brain board's corner holes in place of
  three of the four M3 x 6 top screws.
- Its underside is at z 70.2, which is 8 mm above the Jetson fan.
- The fourth corner is Antmicro's H4 (brain-local 10, 5). The camera RJ45 sits on top of it, so nothing can go
  into it from above.
- The canopy's lip, standoffs and antennas all sit in the lidar's 90 degree blind sector at the rear. The lidar
  plane check in `out/extras_report.json` shows every one of them at 147 degrees or more from dead ahead.
- **Antennas:** two RP-SMA jacks (6.5 mm hole with a 5.8 mm flat), 60 mm apart at the rear edge.
  - The M.2 Wi-Fi card comes over from the dev kit and sits under the Jetson module. Two pigtails run from it
    to the canopy.
  - The antennas are swivel dipoles, so they can fold back.
- "ATLAS" is engraved 0.6 mm into the top. It prints first, on the bed.

**Bench stand**

- It is a hollow truncated pyramid, 170 x 120 mm at the bench and 150 x 80 mm on top, with a pocket for a 1.5 mm
  foam pad.
- It is 125 mm tall. The chassis floor is about 72 mm off the ground at ride height, so the stand lifts the car
  53 mm. That leaves about 13 mm under the tyres if the suspension drops 40 mm.
- The 40 mm droop is an estimate: measure it (MEASURE_FIRST.md #13).

## Cables

Every cable is modelled as a path through the car. Each path is checked against the kit, the boards, the other
new parts and the chassis keep-outs, and none of them hit anything. `docs/WIRING.md` lists each run, its length
in the model, and the length to cut. The main runs:

- The camera cable comes out of the right pod's slot and runs along the pod's top, then up to the camera.
- Both lidar cables stay under the camera arch, below the scan plane.
- The motor phases and hall lead pass over the drive board's rear edge and under it, then down through the
  existing deck opening to the motor's end bell.
- The servo lead drops through the new slot.
- The pack leads come up through the lid slots and down into the board's through-hole wire pads.

Two cables cross the lidar's scan plane: the camera cable at 142 degrees from dead ahead and one Wi-Fi pigtail
at 180 degrees. Both are inside the blind sector.

## Added to the parts list (`bom/make_bom.py`)

New lines:

- two dual-band RP-SMA antennas and two pigtails
- the three 40 mm canopy standoffs and three screws
- a JST-PH loop that closes the E-stop input when no E-stop button is fitted
- zip ties

They add about $26 of estimated cost, and the car's total is now $1,947.79. The phase 1 figure ($1,362.89)
leaves out the antennas, pigtails and canopy standoffs, which only go with the brain board.

The canopy adds about 30 g of the PETG-CF already on hand. The bench stand is about 0.2 kg of PLA.

## Still to check on the real parts

- The RJ45 plug and boot sizes in the model are typical: 12 x 8 x 21 mm plug, 14 x 10 x 11 mm boot. A fat boot
  on the camera cable may need the slot widened (`CAM_PLUG_NOTCH`).
- The Wi-Fi card's antenna connectors. M.2 cards usually use MHF4, which is smaller than u.FL. Order pigtails to
  match.
- Brain board corner H4: confirm on the real jack that the 20 mm standoff under it needs no screw. The other
  three corners are screwed through the canopy standoffs.
- The chassis stand-in in the renders is drawn from kit.py's keep-out numbers. The suspension, wheels and body
  posts are drawn to look plausible, not measured.
