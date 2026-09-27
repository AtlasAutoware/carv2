"""Take unlocked tracks and vias of one net off a small area (KiCad Python), refill and save. For the few
router leftovers that strip_routes.py cannot take (GND, or one piece of a big net).

    flatpak run --command=python3 --filesystem=home org.kicad.KiCad strip_box.py drive NET X0 Y0 X1 Y1 [--locked] [--vias]

X0..Y1 are board-local mm (the frame of layout.py). A track goes when both its ends are inside.
--locked takes locked pieces too (vias from a layout.py via grid that a change of layout.py dropped),
--vias only vias.
"""
import importlib.util
import os
import sys

import pcbnew
from pcbnew import ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
board, net = sys.argv[1], sys.argv[2]
x0, y0, x1, y1 = map(float, sys.argv[3:7])
locked_too = '--locked' in sys.argv
vias_only = '--vias' in sys.argv
bdir = os.path.abspath(os.path.join(HERE, '..', board))
spec = importlib.util.spec_from_file_location('layout', os.path.join(bdir, 'layout.py'))
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)
OX, OY = L.PAGE_ORIGIN
H = L.SIZE[1]
name = [f for f in os.listdir(bdir) if f.endswith('.kicad_pcb')][0][:-len('.kicad_pcb')]
path = os.path.join(bdir, name + '.kicad_pcb')
b = pcbnew.LoadBoard(path)


def inside(p):
    x, y = ToMM(p.x) - OX, OY + H - ToMM(p.y)
    return x0 <= x <= x1 and y0 <= y <= y1


gone = []
for t in list(b.GetTracks()):
    if (t.IsLocked() and not locked_too) or t.GetNetname() != net:
        continue
    if vias_only and t.Type() != pcbnew.PCB_VIA_T:
        continue
    ends = [t.GetPosition()] if t.Type() == pcbnew.PCB_VIA_T else [t.GetStart(), t.GetEnd()]
    if all(inside(p) for p in ends):
        b.Remove(t)
        gone.append(t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(path, b)
print('removed %d pieces of %s' % (len(gone), net))
