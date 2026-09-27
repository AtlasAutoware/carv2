"""List the filled pieces of zones on a built board (KiCad Python): which pieces touch which pads/vias.
flatpak run --command=python3 --filesystem=home org.kicad.KiCad zone_islands.py drive ZONE_NAME_PREFIX"""
import os
import sys

import pcbnew
from pcbnew import ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
bdir = os.path.abspath(os.path.join(HERE, '..', sys.argv[1]))
name = [f for f in os.listdir(bdir) if f.endswith('.kicad_pcb')][0]
b = pcbnew.LoadBoard(os.path.join(bdir, name))
pre = sys.argv[2]
for z in b.Zones():
    if not z.GetZoneName().startswith(pre):
        continue
    for lay in z.GetLayerSet().Seq():
        fp = z.GetFilledPolysList(lay)
        print(z.GetZoneName(), z.GetNetname(), b.GetLayerName(lay), 'outlines', fp.OutlineCount())
        for i in range(fp.OutlineCount()):
            o = fp.Outline(i)
            bb = o.BBox()
            area = abs(o.Area()) / 1e12
            hits = []
            for f in b.GetFootprints():
                for pd in f.Pads():
                    if pd.GetNetCode() == z.GetNetCode() and pd.IsOnLayer(lay):
                        if fp.Contains(pd.GetPosition()) or o.Collide(pd.GetPosition(), 1):
                            hits.append(f.GetReference() + '.' + pd.GetNumber())
            print(f'  #{i} area {area:.2f} mm2 bbox x {ToMM(bb.GetLeft()):.2f}..{ToMM(bb.GetRight()):.2f} '
                  f'y {ToMM(bb.GetTop()):.2f}..{ToMM(bb.GetBottom()):.2f} pads {hits[:8]}')
