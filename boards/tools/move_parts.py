"""Move parts on a routed board to where out/<board>_placement.json now has them, take up the copper that
belonged to them and add layout.copper()'s locked pieces that the board does not have yet (KiCad Python).
Used when a block is re-placed after routing, so the rest of the board keeps its routes.

    flatpak run --command=python3 --filesystem=home org.kicad.KiCad move_parts.py brain REF,REF,... \
        [--nets NET,NET,...] [--box X0 Y0 X1 Y1 --boxnets NET,NET,...]

--nets     unlocked tracks and vias of these nets go, wherever they are (the block's own nets)
--box      unlocked tracks and vias of the --boxnets nets (shared rails, GND) go when they lie in this
           board-local box
The board is saved in place; keep a copy first.
"""
import importlib.util
import json
import os
import sys

import pcbnew
from pcbnew import VECTOR2I, FromMM as MM, ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
board = sys.argv[1]
refs = sys.argv[2].split(',')
args = sys.argv[3:]


def opt(name, n=1):
    if name not in args:
        return None
    i = args.index(name)
    return args[i + 1] if n == 1 else args[i + 1:i + 1 + n]


bdir = os.path.abspath(os.path.join(HERE, '..', board))
spec = importlib.util.spec_from_file_location('layout', os.path.join(bdir, 'layout.py'))
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)
if hasattr(L, 'PAGE_ORIGIN'):
    OX, OY = L.PAGE_ORIGIN[0], L.PAGE_ORIGIN[1] + L.SIZE[1]
else:                                   # the brain board keeps Antmicro's page position (tools/fork_pcb.py)
    OX, OY = 29.75, 128.75
P = lambda x, y: VECTOR2I(MM(OX + x), MM(OY - y))
local = lambda v: (ToMM(v.x) - OX, OY - ToMM(v.y))

name = [f for f in os.listdir(bdir) if f.endswith('.kicad_pcb')][0][:-len('.kicad_pcb')]
path = os.path.join(bdir, name + '.kicad_pcb')
b = pcbnew.LoadBoard(path)
place = json.load(open(os.path.join(bdir, 'out', L.NAME + '_placement.json')))
held = []

moved = 0
for fp in b.GetFootprints():
    ref = fp.GetReference()
    if ref not in refs:
        continue
    v = place[ref]
    if (v['side'] == 'B') != fp.IsFlipped():
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(v['rot'])
    fp.SetPosition(P(v['x'], v['y']))
    moved += 1

nets = set((opt('--nets') or '').split(',')) - {''}
box = [float(a) for a in opt('--box', 4)] if '--box' in args else None
boxnets = set((opt('--boxnets') or '').split(',')) - {''}


def inside(p):
    x, y = local(p)
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


gone = 0
for t in list(b.GetTracks()):
    if t.IsLocked():
        continue
    n = t.GetNetname()
    ends = [t.GetPosition()] if t.Type() == pcbnew.PCB_VIA_T else [t.GetStart(), t.GetEnd()]
    if n in nets or (box and n in boxnets and all(inside(p) for p in ends)):
        b.Remove(t)
        held.append(t)
        gone += 1

# layout.copper()'s locked tracks and vias of the moved block that the board does not have yet
cu = json.load(open(os.path.join(bdir, 'out', L.NAME + '_copper.json')))
LAY = {'F': pcbnew.F_Cu, 'B': pcbnew.B_Cu}
have_v = {(round(local(t.GetPosition())[0], 3), round(local(t.GetPosition())[1], 3), t.GetNetname())
          for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T}
have_t = {(round(local(t.GetStart())[0], 3), round(local(t.GetStart())[1], 3), round(local(t.GetEnd())[0], 3),
           round(local(t.GetEnd())[1], 3), t.GetNetname()) for t in b.GetTracks() if t.Type() != pcbnew.PCB_VIA_T}
added = 0
for v in cu['vias']:
    if v['net'] not in nets or (round(v['x'], 3), round(v['y'], 3), v['net']) in have_v:
        continue
    via = pcbnew.PCB_VIA(b)
    via.SetPosition(P(v['x'], v['y']))
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetWidth(MM(v['dia']))
    via.SetDrill(MM(v['drill']))
    via.SetNet(b.FindNet(v['net']))
    via.SetLocked(True)
    b.Add(via)
    added += 1
for t in cu['tracks']:
    if t['net'] not in nets or t['layer'] not in LAY:
        continue
    for (x0, y0), (x1, y1) in zip(t['pts'], t['pts'][1:]):
        if (round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3), t['net']) in have_t:
            continue
        tr = pcbnew.PCB_TRACK(b)
        tr.SetStart(P(x0, y0))
        tr.SetEnd(P(x1, y1))
        tr.SetWidth(MM(t['width']))
        tr.SetLayer(LAY[t['layer']])
        tr.SetNet(b.FindNet(t['net']))
        tr.SetLocked(True)
        b.Add(tr)
        added += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(path, b)
print('moved %d parts, took up %d tracks and vias, added %d locked pieces' % (moved, gone, added))
