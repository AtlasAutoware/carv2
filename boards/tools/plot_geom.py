"""Plot a board's placement from out/<name>_geom.json (written by build_pcb.py) and list conflicts.
python3 plot_geom.py drive [out.png] [x0 y0 x1 y1]   (host python + matplotlib; both sides drawn in top view)"""
import json
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle, Circle  # noqa: E402

board = sys.argv[1]
bdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', board)
name = [f for f in os.listdir(bdir) if f.endswith('_parts.json')][0].replace('_parts.json', '')
g = json.load(open(os.path.join(bdir, 'out', name + '_geom.json')))
parts = {p['ref']: p for p in json.load(open(os.path.join(bdir, name + '_parts.json')))['parts']}
W, H = g['size']
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(bdir, 'out', name + '_place.png')
win = [float(v) for v in sys.argv[3:7]] if len(sys.argv) > 6 else [0, 0, W, H]

NETC = {'GND': '#9e9e9e', 'VM': '#e53935', 'BATP': '#fb8c00', 'SW_IN': '#f4511e', 'BATN': '#6d4c41',
        'VSYS': '#8e24aa', '+3V3': '#1e88e5', '+5V': '#00897b', 'SERVO_V': '#c0ca33', 'PHA': '#43a047',
        'PHB': '#43a047', 'PHC': '#43a047', 'BMS_RSN': '#795548', 'FET_MID': '#a1887f'}
BLK = {}
pal = ['#ffebee', '#e3f2fd', '#e8f5e9', '#fff3e0', '#f3e5f5', '#e0f7fa', '#fffde7', '#fce4ec', '#ede7f6', '#f1f8e9', '#eceff1']
for p in parts.values():
    if p['block'] not in BLK:
        BLK[p['block']] = pal[len(BLK) % len(pal)]


def draw(ax, side, title):
    ax.add_patch(Rectangle((0, 0), W, H, fill=False, lw=1.2, ec='k'))
    for f in g['fps']:
        x0, y0, x1, y1 = f['crt']
        same = f['side'] == side
        blk = parts.get(f['ref'], {}).get('block', '')
        if same:
            ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc=BLK.get(blk, '#fff'), ec='#555', lw=0.4, alpha=0.9))
        for pd in f['pads']:
            if side not in pd['lay']:
                continue
            a0, b0, a1, b1 = pd['bb']
            col = NETC.get(pd['net'], '#90a4ae' if pd['net'] else '#ffffff')
            if pd['drill'] > 0:
                r = max(a1 - a0, b1 - b0) / 2
                ax.add_patch(Circle(pd['c'], r, fc=col, ec='k', lw=0.3, alpha=0.8))
            else:
                ax.add_patch(Rectangle((a0, b0), a1 - a0, b1 - b0, fc=col, ec='k', lw=0.2, alpha=0.85))
        if same:
            w = x1 - x0
            fs = 3.2 if w < 3 else 4.5 if w < 8 else 6
            ax.text((x0 + x1) / 2, (y0 + y1) / 2, f['ref'], fontsize=fs, ha='center', va='center', color='#000', alpha=0.9)
    ax.set_xlim(win[0] - 1, win[2] + 1)
    ax.set_ylim(win[1] - 1, win[3] + 1)
    ax.set_aspect('equal')
    ax.set_title(title, fontsize=9)
    ax.grid(True, lw=0.2, alpha=0.5)
    ax.set_xticks(range(int(win[0]) // 10 * 10, int(win[2]) + 1, 10))
    ax.set_yticks(range(int(win[1]) // 10 * 10, int(win[3]) + 1, 10))
    ax.tick_params(labelsize=6)


sc = 0.16 * max(1.0, 140.0 / (win[2] - win[0]))
fig, axs = plt.subplots(2, 1, figsize=((win[2] - win[0]) * sc + 1, 2 * (win[3] - win[1]) * sc + 1.2), dpi=170)
draw(axs[0], 'F', f'{name} TOP side (top view)')
draw(axs[1], 'B', f'{name} BOTTOM side (seen from the top, not mirrored)')
fig.tight_layout()
fig.savefig(out)
print('wrote', out)

# conflicts: courtyards on the same side, and through-hole pads under the other side's parts
probs = []
fl = g['fps']
for i in range(len(fl)):
    for j in range(i + 1, len(fl)):
        a, c = fl[i], fl[j]
        ax0, ay0, ax1, ay1 = a['crt']
        bx0, by0, bx1, by1 = c['crt']
        if not (ax0 < bx1 and ax1 > bx0 and ay0 < by1 and ay1 > by0):
            continue
        ov = (min(ax1, bx1) - max(ax0, bx0)) * (min(ay1, by1) - max(ay0, by0))
        if a['side'] == c['side']:
            if ov > 0.05:
                probs.append(('overlap', round(ov, 2), a['ref'], c['ref']))
        else:
            for f1, f2 in ((a, c), (c, a)):
                x0, y0, x1, y1 = f2['crt']
                for pd in f1['pads']:
                    if pd['drill'] > 0:
                        px, py = pd['c']
                        if x0 < px < x1 and y0 < py < y1:
                            probs.append(('hole-under', f1['ref'], pd['n'], f2['ref']))
                            break
for p in sorted(probs, key=lambda t: str(t)):
    print(*p)
print(len(probs), 'conflicts')
