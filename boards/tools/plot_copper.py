"""Plot the copper step's zones, vias and tracks per layer over the placement.
python3 plot_copper.py drive out.png [layers F,B,In2] [x0 y0 x1 y1]"""
import json
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Polygon as MPoly, Rectangle, Circle  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from placer import Board  # noqa: E402

board, out = sys.argv[1], sys.argv[2]
layers = sys.argv[3].split(',') if len(sys.argv) > 3 else ['F', 'B']
bdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', board)
B = Board(os.path.abspath(bdir))
pl = json.load(open(os.path.join(bdir, 'out', B.L.NAME + '_placement.json')))
for r, v in pl.items():
    B.place(r, v['x'], v['y'], v['rot'], v['side'])
cu = json.load(open(os.path.join(bdir, 'out', B.L.NAME + '_copper.json')))
win = [float(v) for v in sys.argv[4:8]] if len(sys.argv) > 7 else [0, 0, B.W, B.H]

COL = {}
pal = ['#e53935', '#fb8c00', '#8e24aa', '#43a047', '#1e88e5', '#6d4c41', '#00897b', '#c0ca33', '#f06292', '#5e35b1',
       '#ffb300', '#26a69a', '#8d6e63', '#ec407a', '#7cb342']


def col(net):
    if net == 'GND':
        return '#9e9e9e'
    if net not in COL:
        COL[net] = pal[len(COL) % len(pal)]
    return COL[net]


ww, wh = win[2] - win[0], win[3] - win[1]
n = len(layers)
sc = min(20.0 / ww, 10.0 / wh)
fig, axs = plt.subplots(n, 1, figsize=(ww * sc + 1, n * wh * sc + 1), dpi=110)
axs = [axs] if n == 1 else axs
for ax, lay in zip(axs, layers):
    ax.add_patch(Rectangle((0, 0), B.W, B.H, fill=False, lw=1, ec='k'))
    for z in sorted(cu['zones'], key=lambda z: z['priority']):
        if z['layer'] != lay or z['name'].startswith('F:'):
            continue
        for rings in z['rings']:
            ax.add_patch(MPoly(rings[0], closed=True, fc=col(z['net']), ec='k', lw=0.3, alpha=0.35))
            for h in rings[1:]:
                ax.add_patch(MPoly(h, closed=True, fc='white', ec='k', lw=0.2, alpha=0.9))
            cx = sum(p[0] for p in rings[0]) / len(rings[0])
            cy = sum(p[1] for p in rings[0]) / len(rings[0])
            if win[0] < cx < win[2] and win[1] < cy < win[3]:
                ax.text(cx, cy, z['net'], fontsize=5, ha='center', color='k', clip_on=True)
    if lay in ('F', 'B'):
        for ref, (x, y, d, s) in B.pos.items():
            for num, c, bb, drill in B.pads(ref):
                if s != lay and drill <= 0:
                    continue
                net = B.parts[ref]['pads'].get(num, '')
                ax.add_patch(Rectangle((bb[0], bb[1]), bb[2] - bb[0], bb[3] - bb[1], fc=col(net) if net else 'w',
                                       ec='k', lw=0.15, alpha=0.9))
    for t in cu['tracks']:
        if t['layer'] == lay:
            xs, ys = zip(*t['pts'])
            ax.plot(xs, ys, color=col(t['net']), lw=t['width'] * 3, solid_capstyle='round')
    for v in cu['vias']:
        ax.add_patch(Circle((v['x'], v['y']), v['dia'] / 2, fc=col(v['net']), ec='k', lw=0.2))
    ax.set_xlim(win[0], win[2])
    ax.set_ylim(win[1], win[3])
    ax.set_aspect('equal')
    ax.set_title(f'{B.L.NAME} {lay}', fontsize=9)
    ax.tick_params(labelsize=6)
fig.tight_layout()
fig.savefig(out)
print('wrote', out)
