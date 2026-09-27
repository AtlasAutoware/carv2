"""Clearance check of the pre-routed copper (layout.copper()) before KiCad sees it (no KiCad needed).

    python3 check_copper.py drive [x0 y0 x1 y1] [--clear 0.2]

Checks every track and via of <board>/out/<name>_copper.json against the pads of other nets on the
same layer (through-hole pads on every layer), and against the other nets' tracks and vias. Prints
the pairs closer than the clearance (default 0.2 mm, 0.15 mm between pads of one footprint does not
apply here: these are tracks). Zones are not checked: KiCad's fill keeps its own clearance.
"""
import json
import os
import sys

from shapely.geometry import LineString, Point, box

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from placer import Board  # noqa: E402

args = sys.argv[1:]
board = args.pop(0)
clear = 0.2
if '--clear' in args:
    i = args.index('--clear')
    clear = float(args[i + 1])
    del args[i:i + 2]
win = [float(v) for v in args[:4]] if len(args) >= 4 else None
bdir = os.path.abspath(os.path.join(HERE, '..', board))
B = Board(bdir)
pl = json.load(open(os.path.join(bdir, 'out', B.L.NAME + '_placement.json')))
for r, v in pl.items():
    B.place(r, v['x'], v['y'], v['rot'], v['side'])
cu = json.load(open(os.path.join(bdir, 'out', B.L.NAME + '_copper.json')))
INNER = {'In1', 'In2', 'In3', 'In4', 'In5', 'In6'}


def inwin(g):
    if not win:
        return True
    x0, y0, x1, y1 = g.bounds
    return not (x1 < win[0] or x0 > win[2] or y1 < win[1] or y0 > win[3])


items = []          # (geom, net, layers(set or 'all'), label)
for ref, p in pl.items():
    nets = B.parts[ref]['pads'] if ref in B.parts else {}
    for n, c, bb, d in B.pads(ref):
        g = box(*bb)
        if d > 0:
            items.append((g, nets.get(n) or '', 'all', f'{ref}.{n}'))
        else:
            items.append((g, nets.get(n) or '', {p['side']}, f'{ref}.{n}'))
cu_items = []
for t in cu['tracks']:
    g = LineString(t['pts']).buffer(t['width'] / 2, 16)
    cu_items.append((g, t['net'], {t['layer']}, f"track {t['net']} {t['layer']} {t['pts'][0]}->{t['pts'][-1]}"))
for v in cu['vias']:
    g = Point(v['x'], v['y']).buffer(v['dia'] / 2, 16)
    cu_items.append((g, v['net'], 'all', f"via {v['net']} ({v['x']}, {v['y']})"))


def share(a, b):
    if a == 'all' or b == 'all':
        return True
    return bool(a & b)


bad = 0
for i, (g, net, lay, lab) in enumerate(cu_items):
    if not inwin(g):
        continue
    for g2, net2, lay2, lab2 in items + cu_items[i + 1:]:
        if net2 == net and net:
            continue
        if not share(lay, lay2):
            continue
        d = g.distance(g2)
        if d < clear - 1e-6:
            bad += 1
            print(f'{d:.3f}  {lab}  <->  {lab2} [{net2}]')
print(f'{bad} clearance problems (< {clear} mm) among {len(cu_items)} pre-routed items')
