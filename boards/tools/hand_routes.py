"""Hand-placed copper as a routes JSON for add_routes.py (plain Python).

    python3 hand_routes.py power ROUTES.txt OUT.json

ROUTES.txt holds one item per line, in the board-local mm of the board's layout.py (X forward, Y to the car's
left, the frame of HANDOFF_E.md); '#' starts a comment:

    NET LAYER WIDTH x,y x,y ...        a polyline of tracks on F or B (a 2-layer board), width in mm
    via NET x,y [DIAMETER/DRILL]       a through via (default 0.8/0.4)

Apply it with `add_routes.py BOARD OUT.json --lock`, then DRC: nothing here checks clearance. The power board's
hand copper (the servo supply run, the BAT and VSYS_SW feeds, the charge path, the gate drive, the dev-kit feed,
the VM sense links) is boards/power/out/hand_routes.txt; LAYOUT_NOTES.md says why each goes where it does.
"""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
board, src, dst = sys.argv[1:4]
spec = importlib.util.spec_from_file_location('layout', os.path.join(HERE, '..', board, 'layout.py'))
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)
OX, OY = L.PAGE_ORIGIN
H = L.SIZE[1]
P = lambda x, y: (round(OX + x, 4), round(OY + H - y, 4))
LAYER = {'F': 'F.Cu', 'B': 'B.Cu'}
out = {'tracks': [], 'vias': [], 'remove_tracks': [], 'remove_vias': []}
for ln in open(src):
    ln = ln.split('#')[0].strip()
    if not ln:
        continue
    f = ln.split()
    if f[0] == 'via':
        x, y = map(float, f[2].split(','))
        d, h = map(float, (f[3] if len(f) > 3 else '0.8/0.4').split('/'))
        px, py = P(x, y)
        out['vias'].append({'net': f[1], 'x': px, 'y': py, 'dia': d, 'drill': h})
        continue
    net, lay, w = f[0], LAYER[f[1]], float(f[2])
    pts = [tuple(map(float, q.split(','))) for q in f[3:]]
    for a, b in zip(pts, pts[1:]):
        out['tracks'].append({'net': net, 'layer': lay, 'w': w, 'p': list(P(*a) + P(*b))})
json.dump(out, open(dst, 'w'), indent=0)
print(len(out['tracks']), 'tracks', len(out['vias']), 'vias ->', dst)
