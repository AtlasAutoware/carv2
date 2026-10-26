# Board tools

These scripts turn `design.py` and `layout.py` into finished KiCad boards. Some of them run inside
KiCad's Python (`flatpak run --command=python3 --filesystem=home org.kicad.KiCad script.py ...`, marked
**K** below). The rest need plain Python with numpy, scipy, shapely, scikit-image and matplotlib
(`pdfpads.py` also needs PyMuPDF). `run_kicad.sh` wraps the KiCad steps, one argument per step:
`run_kicad.sh drc-drive fab-drive`, `run_kicad.sh render-brain` and so on. It works from the folder
it sits in; a first argument ending in `.tar.gz` is a sync tarball in `.work/` to unpack first.
`pcb-<board>` builds a board again from its placement, so on a routed board it throws the routing away.

## Order of work

1. **Schematic.** `build_sch.py` writes the schematic and the parts JSON. It uses `eda.py` for
   schematic capture and `chips.py` for the pin tables. `check_fp.py` checks that every footprint
   exists with the right pads.
2. **Placement.** `placer.py` runs the board's `layout.py` against a footprint model, then places
   the remaining parts next to the pins they connect to. The drive board's layout sets `KEEP_AUTO`
   now that it is routed, so the other parts stay put when one part is moved. The brain board's
   layout pins its parts by hand instead.
3. **Board.** `build_pcb.py` (**K**) builds the board from the placement and the hand-drawn copper
   in `layout.copper()`: escapes, via arrays, pours and solder mask openings (`C.mask()`, drawn on
   F.Mask/B.Mask). `check_copper.py` checks that copper before KiCad sees it. A layout may set
   `DEFAULT_CLASS` (the Default net class) and `BOARD_RULES` (the board-wide DRC floors) next to
   `NETCLASSES` and `DRU`; `layout.finish()` runs inside KiCad after placement (outline, texts,
   fiducials, markings). `COPPER_LAYERS` and `LAYER_TYPES` set the layer count and which inner layers are
   planes; `STACKUP` (copper and dielectric thickness per layer, surface finish) is written into the board's
   setup as a `(stackup ...)` block, since KiCad 7's Python has no stackup API (the power board, 4 layers).
4. **Autorouting.** `dsn_export.py` (**K**) and `dsn_patch.py` feed Freerouting, and
   `ses_import.py` (**K**) brings the result back. `route_prep.py` holds the view of the board that
   the router sees. `dsn_patch.py` also writes Specctra `class_class` clearances from
   `layout.DSN_CLASS_CLEARANCE` (the router's copy of an isolation rule KiCad holds in the `.kicad_dru`).
   Freerouting 1.9 needs a display even in batch mode: `xvfb-run -a java -jar freerouting.jar -de
   IN.dsn -do OUT.ses -mp 100 -mt 1 -da` (its log warns that `-mt` above 1 can leave clearance errors).
   Copper that must be routed before the autorouter (coupled USB pairs) goes on with
   `mazeroute.py --only-pairs` and `add_routes.py BOARD ROUTES.json --lock`: locked copper reaches
   the DSN as fixed wiring.
5. **Finishing the routing.** `dump_board.py --route-view` (**K**) writes the board to JSON.
   `mazeroute.py` then routes what is still open: coupled differential pairs first, then everything
   else in negotiated rounds. It works on the dump and writes a routes JSON, which `add_routes.py`
   (**K**) applies. Its docstring lists the options.
   - `mazeroute.py` reaches as far as the widest rule needs (it used to stop at 1.0 mm, so no track wider than
     1.4 mm could start: the power board's 2.0 and 2.5 mm supply nets all failed with "no open cell on start"),
     keeps a layout's `DSN_CLASS_CLEARANCE` (the power board's 2 mm BMS isolation) between that class and every
     other net, and takes `--skip REF,...` to leave the low-current branches of a wide net (a sense resistor, a
     test point) for a later, narrower pass (`--width NET=W`). `--win NET,...` makes those nets win every clash:
     the other net's piece is taken up and routed again (for one long net across a board full of short ones; on the
     power board the pushed nets did not always find a new way, so check the open count after it).
   - A board the autorouter leaves with a few dozen open nets can often be closed net by net with
     `mazeroute.py --only NET`: many of them route in one round through space the autorouter did not use.
   - Copper that has to be placed by hand (a supply trunk along a planned corridor, a link through a gap the
     router cannot see) goes in as a routes JSON with `add_routes.py --lock`; the power board's are listed in
     `boards/power/LAYOUT_NOTES.md`.
   - `strip_routes.py` and `strip_box.py` (**K**) take routed copper off so it can be routed again.
   - `move_parts.py` (**K**) moves parts on a routed board to their new placement.
   - `update_zone.py` (**K**) gives a pour a new outline.
   - `zone_islands.py` (**K**) lists which pieces of a pour touch what.
   - On the drive board, the last few ground pads left in islands of the outer ground fill were
     joined by hand: a via or a short track each, checked for clearance before it went on. The board
     file holds the result.
6. **Finish.** Run these in order, then run DRC (`drc-<board>`); it should show no unconnected
   items and no clearance errors.
   - `pad_vias.py` (**K**) gives each unconnected pad a via into its plane (on a 2-layer board: into
     the net's fill on the other side). `--via D/H` sets the via. Other modes:
     - `--ep REF.PAD` adds a via grid inside exposed pads.
     - `--pads` works on pads you name.
     - `--through-pours` lets a via go through another net's pour.
     - `--zone-islands` gives stray pieces of pour a via.
   - `dump_board.py --fills NET,...` (**K**) also dumps the filled copper of those nets (GND included).
   - `finish_pcb.py` (**K**) adds GND stitching vias (`--via D/H`, `--pitch MM`), cleans up the
     silkscreen and swaps in 3D models.
   - `clean_tracks.py` (**K**) splits T-joins and tracks that run on past a via or pad, then removes
     dead-end tracks and vias, including vias that only join tracks on one layer.
   - `set_netclasses.py` writes the net classes into the project file (and `DEFAULT_CLASS`,
     `BOARD_RULES` and the `.kicad_dru` when the layout has them).
   - `drc.py` (**K**) runs DRC from KiCad's Python and writes `drc.rpt` in KiCad's report format:
     KiCad 7's `kicad-cli` has no `pcb drc` (KiCad 8+ do; `run_kicad.sh drc-<board>` uses that).
   - `pour_resistance.py` (plain Python) computes the resistance of a high-current path through the
     real filled copper (`dump_board.py BOARD OUT.json --fills BAT,VM,GND` first), with FETs or other
     parts as `--link` resistors, and reports the drop at a given current and the narrowest neck.
     `--cu-um` is the outer copper, `--cu-um-inner` the inner layers (2 oz outside, 1 oz inside: 70 and 35).
7. **Outputs.** `run_kicad.sh fab-<board>` writes Gerbers, drill files, CPL and BOM.
   `render-<board>` and `glb-<board>` write the pictures and the 3D model.
   `check_stack.py` checks the connector between the two boards. `fab_outputs.py <board>` (plain
   Python around `kicad-cli`, KiCad 7 or later, no schematic needed) writes the same fab set for a
   2- or 4-layer board: Gerbers (the inner copper layers too, from `COPPER_LAYERS`) with F/B.Fab, Excellon PTH/NPTH with a map, a zip of the layers a fab needs,
   the bottom SMD CPL and the top parts list, a fab BOM from the board's BOM CSV, and 2D PNG renders
   (PDF plot, `pdftoppm`, ImageMagick trim), one per inner layer as well.

The brain board starts from Antmicro's board rather than step 3: `fork_pcb.py` (**K**) deletes the
removed parts, renets the rest and places the new ones.

## KiCad 7 and KiCad 10

The K tools were written against KiCad 10 (flatpak, the team laptop). They also run under KiCad 7.0
(Debian/Ubuntu `kicad` package, `/usr/bin/python3` with `pcbnew`). `kicompat.py` holds the differences;
each helper keeps the KiCad 10 call and falls back to the KiCad 7 one (`kicompat.K7` from
`pcbnew.GetBuildVersion()`):

| What | KiCad 9/10 | KiCad 7 | Where |
| --- | --- | --- | --- |
| Footprint user fields | `FOOTPRINT.SetField`, `GetField`, `HasField`, `GetFieldText` | `SetProperty`, `GetProperty`, `HasProperty` (plain key/value, no layer or visibility) | `kc.set_field`, `kc.get_field` |
| Do-not-populate | `SetDNP`, `IsDNP` | no DNP attribute: a `DNP` property, and the part is left out of the position files | `kc.set_dnp`, `kc.is_dnp` |
| Flip to the bottom | `Flip(pos, FLIP_DIRECTION_LEFT_RIGHT)` | `Flip(pos, True)` (the same left-right mirror) | `kc.flip` |
| Footprint bounding box | `GetBoundingBox(False)` | `GetBoundingBox(False, False)` | `kc.fp_bbox` |
| Courtyard | rebuilt on demand | cached at load: `BuildCourtyardCaches()` after moving a footprint | `kc.courtyard` |
| Via width | `GetWidth(layer)` | `GetWidth()` | `kc.via_width` |
| Board outline | `GetBoardPolygonOutlines(polys, True)` | `GetBoardPolygonOutlines(polys)` (the second argument is an error handler) | `kc.board_outline` |
| Texts in a footprint | `PCB_TEXT` / `PCB_FIELD` | `FP_TEXT` (`PCB_FP_TEXT_T`) | `kc.is_text` |
| Net classes | `NET_SETTINGS.SetNetclass`, `SetNetclassPatternAssignment`, `GetDefaultNetclass` | `m_DefaultNetClass`, `m_NetClasses`; pattern assignments live only in the project file, so each net gets its class with `NETINFO_ITEM.SetNetClass` and the `.kicad_pro` carries the patterns | `kc.netclass_setup` |
| Saving | `SaveBoard(path, b)` | `SaveBoard(path, b, True)`: without the flag KiCad 7 also rewrites the `.kicad_pro` from the board's project, which for a board made in Python is empty | `kc.save` (every K tool) |
| Board stackup | `BOARD_STACKUP` from `GetStackupDescriptor()` | not wrapped (a SwigPyObject with no methods): `build_pcb.py` writes the `(stackup ...)` block into the saved file before it reloads it, and KiCad keeps it on every later save | `build_pcb.py` |
| Zone fill on a new board | works on a `BOARD()` made in Python | segfaults (no DRC engine until a board is loaded from file): `build_pcb.py` saves, writes the `.kicad_pro`, reloads with `LoadBoard` (which also reads the `.kicad_dru`), then fills | `build_pcb.py` |
| Session import | `ImportSpecctraSES(board, file)` | `ImportSpecctraSES(file)` only works inside the board editor: `ses_import.py` reads the session itself (wires and vias of `network_out`, sizes from the padstack names) | `ses_import.py` |
| DRC | `kicad-cli pcb drc` | none in `kicad-cli`: `pcbnew.WriteDRCReport` | `drc.py` |
| Polygon fracture | `Fracture()` | `Fracture(SHAPE_POLY_SET.PM_FAST)` | `build_pcb.py` (mask openings) |
| Custom rule functions | `memberOfFootprint('REF')` | not available (evaluates false); `intersectsCourtyard('REF')` works in both | the power board's `DRU` |
| 3D renders | `kicad-cli pcb render`, `export glb` | none | `run_kicad.sh render-<board>`, `glb-<board>` on the laptop |

Two placement details that are not version differences but showed up with KiCad 7's footprint dump:
`placer.pad_xy` and `build_pcb.pad_xy` now take the largest pad when several share a number (a wire pad
with a ring of small via pads, which a dump may list in any order), and `placer.build_library` skips
board-only footprints (fiducials).

## Helpers

- `plot_geom.py` and `plot_copper.py` plot a placement and the hand-drawn copper.
- `fpinfo.py` prints a footprint's pads.
- `pdfpads.py` reads pad sizes off TI land-pattern PDFs, for `make_footprints.py`.
- `sexp.py` reads and writes KiCad files.
- `pack_sync.sh` packs the sources for the KiCad machine. It is specific to how these boards were
  built and has a hard-coded path (the build container's copy of the repo).
