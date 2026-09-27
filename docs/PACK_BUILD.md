# Building the 4S3P 18650 pack

Twelve Molicel P28A (2800 mAh, 35 A, 18.6 x 65.2 mm, 46 g; 18650batterystore.com), 4S3P:
14.4 V nominal, 16.8 V full, 8.4 Ah, about 121 Wh, 105 A maximum. Buy 14 so there are two
spares from the same batch. Do not mix cells from different batches or with different
states of charge; check every cell reads within 0.02 V of the others before welding.

Build it with an adult supervising, on a non-flammable bench, with a bucket of sand and a
fire extinguisher nearby. Nothing in this pack is protected until the BMS on the drive board is connected, so
the strips and leads are live the moment the first joint is welded.

## Layout

Cells stand upright in a 2 x 6 grid. Column i = 0 is the rear of the car, i = 5 the front;
row j = 0 is the side toward the drive board, j = 1 the outboard side. "Facing up" is the
terminal on top.

| group | cells (i, j) | facing up | top strip | bottom strip |
| --- | --- | --- | --- | --- |
| G1 | (0,0) (0,1) (1,0) | - | PACK- tab + B0 tap | G1+ to G2- (B1) |
| G2 | (1,1) (2,0) (2,1) | + | G2+ to G3- (B2) | G1+ to G2- (B1) |
| G3 | (3,0) (3,1) (4,0) | - | G2+ to G3- (B2) | G3+ to G4- (B3) |
| G4 | (4,1) (5,0) (5,1) | + | PACK+ tab + B4 tap | G3+ to G4- (B3) |

Top strips: one over G1 (pack minus), one over G2 + G3 (series joint B2), one over G4 (pack
plus). Bottom strips: one over G1 + G2 (series joint B1), one over G3 + G4 (series joint B3).
Both main terminals end up on top at the two ends, so the 10 AWG leads leave straight up
through the lid slots. The two bottom taps (B1, B3) run up the grooves inside the box wall on
the drive-board side.

## Steps

1. Print `cell_holder_bottom.stl`, `cell_holder_top.stl`, `pack_box.stl`, `pack_lid.stl`.
   The holders have 18.95 mm pockets and 14 mm windows for the welder.
2. Put a fish-paper ring on every positive cap. Load the cells in the bottom holder with the
   orientation in the table, then press the top holder on.
3. Weld two layers of 0.2 x 8 mm pure nickel on every series strip (B1, B2, B3) and one layer
   on the end strips, two to four welds per cell. Test-weld on a spare first: the weld should
   tear the nickel, not peel off.
4. Solder the 10 AWG PACK+ and PACK- leads to the end strips on top, away from the cell caps
   (heat the strip, not the cell). Solder the 24 AWG sense wires: B0 (pack minus) through B4
   (pack plus), plus a 10 kOhm NTC taped between two middle cells, into a 7-pin JST-XH in the
   order the drive board silkscreen shows. Check each tap with a meter: B1-B0, B2-B1, B3-B2,
   B4-B3 should each read one cell voltage.
5. Kapton over every strip and edge, 1 mm foam pad on top, slide the block into the box, lid
   on (six M3 into the deck inserts).
6. Connect the sense lead to the drive board BEFORE the power leads, so the BMS is awake when
   the pack is first connected.

## Why these parts

- Molicel P28A instead of P30B: same size, 35 A instead of 36 A, and it was in stock; the P30B
  was sold out at three stores on 2026-09-26.
- Upright cells: every series joint is on the top or bottom face, where the welder can reach.
  Lying the cells down would force end-to-end joints that cannot be welded after assembly.
- 3P rather than 2P: at 70 A each cell sees about 23 A instead of 35 A, so it runs cooler and
  keeps its voltage up under load.
