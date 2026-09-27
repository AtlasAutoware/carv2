"""Take autorouted copper off nets so the router can do them again (KiCad Python).

    flatpak run --command=python3 --filesystem=home org.kicad.KiCad strip_routes.py brain --drc
    flatpak run --command=python3 --filesystem=home org.kicad.KiCad strip_routes.py brain NET [NET ...]

--drc   the nets of every unlocked track or via that <board>/drc.rpt lists in a clearance, short,
        crossing, hole-to-hole, hole-clearance or board-edge violation
NET     names, shell-style patterns allowed (POE_*)
Only unlocked tracks and vias go (hand-placed escapes and Antmicro's routing are locked). GND is never
stripped. Refills and saves.
"""
import fnmatch
import os
import re
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
bdir = os.path.abspath(os.path.join(HERE, '..', sys.argv[1]))
args = sys.argv[2:]
name = [f for f in os.listdir(bdir) if f.endswith('.kicad_pcb')][0][:-len('.kicad_pcb')]
path = os.path.join(bdir, name + '.kicad_pcb')
b = pcbnew.LoadBoard(path)

pats = [a for a in args if not a.startswith('--')]
nets = set()
if '--drc' in args:
    rpt = open(os.path.join(bdir, 'drc.rpt')).read()
    for blk in re.split(r'\n(?=\[)', rpt):
        if not blk.startswith(('[clearance]', '[shorting_items]', '[tracks_crossing]', '[hole_to_hole]',
                               '[hole_clearance]', '[copper_edge_clearance]')):
            continue
        for m in re.finditer(r'(Track|Via) \[([^\]]+)\]', blk):
            nets.add(m.group(2))
keep = []
removed = 0
for t in list(b.GetTracks()):
    n = t.GetNetname()
    if t.IsLocked() or n == 'GND':
        continue
    if n in nets or any(fnmatch.fnmatchcase(n, p) for p in pats):
        b.Remove(t)
        keep.append(t)
        removed += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(path, b)
print(f'stripped {removed} unlocked tracks/vias on {len(nets) + len(pats)} nets/patterns:',
      ' '.join(sorted(nets - {'GND'}) + pats))
