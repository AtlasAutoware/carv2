# Measure before printing or ordering

The chassis numbers in `mech/kit.py` come from car 1's plate and a keep-out model built from
Traxxas's specs and exploded views. Most are estimates. Each one below is a single parameter
in `kit.py` (`P = dict(...)`), and every script re-runs its checks when a number changes:
`python3 mech/kit.py` rebuilds all parts, repeats the interference test and rewrites the STLs.

Print `fit_coupon_front.stl` and `fit_coupon_rear.stl` first (about 20 g each). They are the
deck's tower saddles and body-post slots cut out of the full deck, so if they drop onto the
towers with the posts through the slots, the deck will too.

| # | measure | parameter | now | why it matters |
| --- | --- | --- | --- | --- |
| 1 | distance between the front and rear shock-tower top edges | `FRONT_TOWER_X`, `REAR_TOWER_X` | 168.3 / -141.7 (310 apart) | saddle positions; the rear one was moved 11.4 mm from car 1 using the wheelbase only |
| 2 | height of the tower top edges below where the deck will sit; old-plate underside to the chassis side-wall top | `TOWER_TOP_BELOW_OLD_PLATE`, `UNDER_CLEARANCE` | 16 / 45 | deck height; everything under the deck is checked against it |
| 3 | body-post positions on each tower (x and y at deck height) | `FRONT_POST`, `REAR_POST` | (180.4, +-38.6) / (-127.7, +-41.1) | the 24 mm post slots have +-8.5 mm of slack |
| 4 | tower thickness at the top | `TOWER_T` | 4 | saddle slot width (tower + 0.6) |
| 5 | battery bay: length, width, inner edge y, floor depth below the side-wall top | `BATT_BAY`, `TUB_DEPTH` | x -75..65, y 15..62, 24 deep | the pack box body is 124 x 44 x 72.4 mm (flange on top) and must fit, with 2.8 mm under it |
| 6 | stock battery hold-down posts: where they are and whether they come out | - | not modelled | they may have to be removed for the pack box |
| 7 | steering servo top (inverted case) and bellcrank sweep under the front of the deck | `SERVO`, `LINKAGE` | top at rim +25 / +12 | front rib and servo cable slot |
| 8 | transmission and motor tops under the rear of the deck | `GEARBOX`, `MOTOR_*` | rim +22 / +23 | rear ribs and the phase-wire slot |
| 9 | front tyre at full lock and full bump against the deck's front corners | `TYRE_*`, `BUMP`, `LOCK_DEG` | clears in the model | the nose taper starts at x 120 for this reason |
| 10 | Triton bottom face: spacing of the four corner M3 holes | `CAM_HOLE_PITCH` | 20 x 20, ESTIMATE | the cradle has +-1.5 mm slots; confirm on the camera (LUCID's manual says 4 corner M3 on the bottom but gives no spacing) |
| 11 | Puller Pro sensor plug: pitch and pin order | drive board J_HALL | JST-ZH 6-pin assumed | decides the board connector |
| 12 | M12 lidar plug bodies behind the TiM561 | `tim561()` estimates | 45 mm long | they run under the camera arch |
| 13 | wheel drop with the chassis lifted (suspension droop), front and rear | `STAND_H` in `mech/extras.py` | 40 mm assumed | the bench stand's height: 125 mm leaves about 13 mm under the tyres at 40 mm of droop |
| 14 | the camera cable's RJ45 plug and boot, width and height | `CAM_PLUG_NOTCH` in `kit.py` | 20 mm slot for a 14 x 10 mm boot | the slot through the right side pod; widen it for a fatter boot |
| 15 | antenna connectors on the M.2 Wi-Fi card from the dev kit | pigtails in `bom/make_bom.py` | MHF4 assumed | order pigtails with the matching plug |
| 16 | brain board corner H4 (brain-local 10, 5) under the camera RJ45 J6 | - | no screw from the top | the 20 mm standoff there only supports the board; the canopy uses the other three corners |
