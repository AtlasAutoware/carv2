# Board tools

These scripts turn `design.py` and `layout.py` into finished KiCad boards. Some of them run inside
KiCad's Python (`flatpak run --command=python3 --filesystem=home org.kicad.KiCad script.py ...`, marked
**K** below). The rest need plain Python with numpy, scipy, shapely and scikit-image. `run_kicad.sh`
wraps the KiCad steps, one argument per step (`pcb-drive`, `drc-drive`, `fab-brain` and so on).

## Order of work

1. **Schematic.** `build_sch.py` writes the schematic and the parts JSON. It uses `eda.py` for
   schematic capture and `chips.py` for the pin tables. `check_fp.py` checks that every footprint
   exists with the right pads.
2. **Placement.** `placer.py` runs the board's `layout.py` against a footprint model, then places
   the remaining parts next to the pins they connect to. Once a board is routed, its layout sets
   `KEEP_AUTO`, so the other parts stay put when one part is moved.
3. **Board.** `build_pcb.py` (**K**) builds the board from the placement and the hand-drawn copper
   in `layout.copper()`: escapes, via arrays and pours. `check_copper.py` checks that copper before
   KiCad sees it.
4. **Autorouting.** `dsn_export.py` (**K**) and `dsn_patch.py` feed Freerouting, and
   `ses_import.py` (**K**) brings the result back. `route_prep.py` holds the view of the board that
   the router sees.
5. **Finishing the routing.** `dump_board.py --route-view` (**K**) writes the board to JSON.
   `mazeroute.py` then routes what is still open: coupled differential pairs first, then everything
   else in negotiated rounds. It works on the dump and writes a routes JSON, which `add_routes.py`
   (**K**) applies. Its docstring lists the options.
   - `strip_routes.py` and `strip_box.py` (**K**) take routed copper off so it can be routed again.
   - `move_parts.py` (**K**) moves parts on a routed board to their new placement.
   - `update_zone.py` (**K**) gives a pour a new outline.
   - `zone_islands.py` (**K**) lists which pieces of a pour touch what.
   - On the drive board, the last few ground pads left in islands of the outer ground fill were
     joined by hand: a via or a short track each, checked for clearance before it went on. The board
     file holds the result.
6. **Finish.** Run these in order, then run DRC (`drc-<board>`); it should show no unconnected
   items and no clearance errors.
   - `pad_vias.py` (**K**) gives each unconnected pad a via into its plane. Other modes:
     - `--ep REF.PAD` adds a via grid inside exposed pads.
     - `--pads` works on pads you name.
     - `--through-pours` lets a via go through another net's pour.
     - `--zone-islands` gives stray pieces of pour a via.
   - `finish_pcb.py` (**K**) adds GND stitching vias, cleans up the silkscreen and swaps in 3D models.
   - `clean_tracks.py` (**K**) splits T-joins and tracks that run on past a via or pad, then removes
     dead-end tracks and vias, including vias that only join tracks on one layer.
   - `set_netclasses.py` writes the net classes into the project file.
7. **Outputs.** `run_kicad.sh fab-<board>` writes Gerbers, drill files, CPL and BOM.
   `render-<board>` and `glb-<board>` write the pictures and the 3D model.
   `check_stack.py` checks the connector between the two boards.

The brain board starts from Antmicro's board rather than step 3: `fork_pcb.py` (**K**) deletes the
removed parts, renets the rest and places the new ones.

## Helpers

- `plot_geom.py` and `plot_copper.py` plot a placement and the hand-drawn copper.
- `fpinfo.py` prints a footprint's pads.
- `pdfpads.py` reads pad sizes off TI land-pattern PDFs, for `make_footprints.py`.
- `sexp.py` reads and writes KiCad files.
- `pack_sync.sh` packs the sources for the KiCad machine. It is specific to how these boards were
  built and has a hard-coded path.
