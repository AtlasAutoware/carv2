"""Give zones on a routed board the outline layout.copper() now has for them (KiCad Python), refill, save.

    flatpak run --command=python3 --filesystem=home org.kicad.KiCad update_zone.py drive P:GND_In2 [NAME ...]
"""
import importlib.util
import json
import os
import sys

import pcbnew
from pcbnew import VECTOR2I, FromMM as MM

HERE = os.path.dirname(os.path.abspath(__file__))
board = sys.argv[1]
names = sys.argv[2:]
bdir = os.path.abspath(os.path.join(HERE, '..', board))
spec = importlib.util.spec_from_file_location('layout', os.path.join(bdir, 'layout.py'))
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)
if hasattr(L, 'PAGE_ORIGIN'):
    OX, OY = L.PAGE_ORIGIN[0], L.PAGE_ORIGIN[1] + L.SIZE[1]
else:
    OX, OY = 29.75, 128.75
cu = json.load(open(os.path.join(bdir, 'out', L.NAME + '_copper.json')))
want = {z['name']: z for z in cu['zones'] if z['name'] in names}
name = [f for f in os.listdir(bdir) if f.endswith('.kicad_pcb')][0][:-len('.kicad_pcb')]
path = os.path.join(bdir, name + '.kicad_pcb')
b = pcbnew.LoadBoard(path)
done = []
for zn in b.Zones():
    z = want.get(zn.GetZoneName())
    if not z:
        continue
    ol = zn.Outline()
    ol.RemoveAllContours()
    for rings in z['rings']:
        oi = ol.NewOutline()
        for (x, y) in rings[0]:
            ol.Append(MM(OX + x), MM(OY - y), oi, -1)
        for hole in rings[1:]:
            hi = ol.NewHole(oi)
            for (x, y) in hole:
                ol.Append(MM(OX + x), MM(OY - y), oi, hi)
    done.append(z['name'])
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(path, b)
print('new outlines:', ', '.join(done) or 'none', '; not on the board:', ', '.join(set(names) - set(done)) or 'none')
