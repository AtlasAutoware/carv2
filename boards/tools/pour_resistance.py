"""Resistance of a high-current path through a board's real copper (plain Python: numpy, scipy, Pillow).

    python3 pour_resistance.py DUMP.json --from REF.PAD[,..] --to REF.PAD[,..] [--link REF.PAD:REF.PAD:OHM ...]
                               [--nets NET,..] [--res 0.1] [--cu-um 70] [--plating-um 25] [--amps 90]
                               [--report FILE.json]

DUMP.json comes from `dump_board.py BOARD.kicad_pcb DUMP.json --fills NET,..` (filled zones of the nets).
The copper of --nets (default: the nets of the --from/--to/--link pads) is rasterised on every copper layer
on a --res mm grid: zone fills, tracks and pads. Each cell is joined to its four neighbours on the same
layer by the sheet conductance of the foil (copper 1.72e-8 Ohm m at 20 C, --cu-um thick: 70 um = 2 oz
nominal). Vias and plated holes join the layers with the resistance of their barrel (--plating-um wall,
1.6 mm long). Every pad is one node (the soldered lead or wire makes it equipotential); --from pads sit at
1 V, --to pads at 0 V, and each --link puts a resistor between two pads (a FET's on-resistance between its
drain and source pads). Prints the path resistance, the drop at --amps, the voltage of every named pad on
that scale, the drop in each net's copper, and the highest current per mm of copper width (the neck).
Copper only: the leads of the parts, the solder and contact resistance are not included.
"""
import json
import math
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import sparse
from scipy.sparse.linalg import spsolve

RHO = 1.72e-8        # Ohm m, annealed copper at 20 C
BOARD_T = 1.6e-3     # m, barrel length


def opt(args, name, default):
    return args[args.index(name) + 1] if name in args else default


def main():
    args = sys.argv[1:]
    D = json.load(open(args[0]))
    res = float(opt(args, '--res', 0.1))
    t_cu = float(opt(args, '--cu-um', 70.0)) * 1e-6
    t_pl = float(opt(args, '--plating-um', 25.0)) * 1e-6
    amps = float(opt(args, '--amps', 90.0))
    src = opt(args, '--from', '').split(',')
    dst = opt(args, '--to', '').split(',')
    links = []
    for i, a in enumerate(args):
        if a == '--link':
            p, q, r = args[i + 1].split(':')
            links.append((p, q, float(r)))
    pads = {}
    for f in D['fps']:
        for p in f['pads']:
            pads.setdefault(f"{f['ref']}.{p['n']}", []).append(p)
    named = src + dst + [l[0] for l in links] + [l[1] for l in links]
    for n in named:
        if n not in pads:
            raise SystemExit('no pad ' + n)
    nets = opt(args, '--nets', '')
    nets = set(nets.split(',')) if nets else {pads[n][0]['net'] for n in named}
    layers = ['F.Cu'] + [f'In{k}.Cu' for k in range(1, D['layers'] - 1)] + ['B.Cu']
    x0, y0, x1, y1 = D['edges']
    W, H = int(math.ceil((x1 - x0) / res)) + 2, int(math.ceil((y1 - y0) / res)) + 2
    ij = lambda x, y: ((x - x0) / res + 1, (y - y0) / res + 1)

    # ---------------------------------------------------------------- rasterise: per layer, per net
    grids = {}
    for net in sorted(nets):
        for lay in layers:
            im = Image.new('L', (W, H), 0)
            dr = ImageDraw.Draw(im)
            for a in D.get('areas', []):
                if a['net'] != net or a['rule']:
                    continue
                for rings in a.get('fills', {}).get(lay, []):
                    dr.polygon([ij(*p) for p in rings[0]], fill=1)
                    for hole in rings[1:]:
                        dr.polygon([ij(*p) for p in hole], fill=0)
            for t in D['tracks']:
                if t['net'] == net and t['layer'] == lay:
                    a, b = ij(t['p'][0], t['p'][1]), ij(t['p'][2], t['p'][3])
                    w = t['w'] / res
                    dr.line([a, b], fill=1, width=max(1, int(round(w))))
                    for c in (a, b):
                        dr.ellipse([c[0] - w / 2, c[1] - w / 2, c[0] + w / 2, c[1] + w / 2], fill=1)
            for plist in pads.values():
                for p in plist:
                    if p['net'] == net and lay in p['layers']:
                        a, b = ij(p['bb'][0], p['bb'][1]), ij(p['bb'][2], p['bb'][3])
                        dr.rectangle([a, b], fill=1)
            g = np.array(im, dtype=bool)
            if g.any():
                grids[(net, lay)] = g
    # ---------------------------------------------------------------- unknowns
    index = {}
    n = 0
    for key, g in grids.items():
        idx = -np.ones(g.shape, dtype=np.int64)
        k = int(g.sum())
        idx[g] = np.arange(n, n + k)
        index[key] = idx
        n += k
    pad_node = {}
    for name in sorted(set(named)):
        pad_node[name] = n
        n += 1
    rows, cols, vals = [], [], []

    def cond(i, j, g):
        rows.extend([i, j, i, j])
        cols.extend([i, j, j, i])
        vals.extend([g, g, -g, -g])

    g_sheet = t_cu / RHO            # S per square
    for key, idx in index.items():
        for dy, dx in ((0, 1), (1, 0)):
            a = idx[:idx.shape[0] - dy, :idx.shape[1] - dx]
            b = idx[dy:, dx:]
            m = (a >= 0) & (b >= 0)
            ai, bi = a[m], b[m]
            rows.extend(np.concatenate([ai, bi, ai, bi]))
            cols.extend(np.concatenate([ai, bi, bi, ai]))
            gv = np.full(ai.size, g_sheet)
            vals.extend(np.concatenate([gv, gv, -gv, -gv]))

    def cells(net, lay, bb):
        idx = index.get((net, lay))
        if idx is None:
            return np.array([], dtype=np.int64)
        a, b = ij(bb[0], bb[1]), ij(bb[2], bb[3])
        i0, i1 = int(math.floor(a[1])), int(math.ceil(b[1])) + 1
        j0, j1 = int(math.floor(a[0])), int(math.ceil(b[0])) + 1
        sub = idx[max(i0, 0):i1, max(j0, 0):j1]
        return sub[sub >= 0]

    BIG = 1e7
    # layer links: vias and plated holes (barrel resistance), pads tied into one node per named pad
    n_barrels = 0
    holes = [(v['x'], v['y'], v['drill'], v['dia'], v['net']) for v in D['vias'] if v['net'] in nets]
    for name, plist in pads.items():
        for p in plist:
            if p['net'] in nets and p['drill'] > 0 and len(p['layers']) > 1:
                holes.append(((p['bb'][0] + p['bb'][2]) / 2, (p['bb'][1] + p['bb'][3]) / 2, p['drill'],
                              min(p['bb'][2] - p['bb'][0], p['bb'][3] - p['bb'][1]), p['net']))
    for (x, y, drill, dia, net) in holes:
        r = max(dia / 2, res)
        per = []
        for lay in layers:
            c = cells(net, lay, (x - r * 0.7, y - r * 0.7, x + r * 0.7, y + r * 0.7))
            if c.size:
                per.append(c)
        if len(per) < 2:
            continue
        g_barrel = math.pi * drill * 1e-3 * t_pl / (RHO * BOARD_T)
        for k in range(len(per) - 1):
            cond(int(per[k][0]), int(per[k + 1][0]), g_barrel)
        for c in per:
            for q in c[1:]:
                cond(int(c[0]), int(q), BIG)
        n_barrels += 1
    for name, node in pad_node.items():
        for p in pads[name]:
            for lay in p['layers']:
                for c in cells(p['net'], lay, p['bb']):
                    cond(node, int(c), BIG)
    for p, q, r in links:
        cond(pad_node[p], pad_node[q], 1.0 / r)
    A = sparse.csr_matrix((vals, (rows, cols)), shape=(n, n))
    # Dirichlet: from pads 1 V, to pads 0 V
    fixed = {pad_node[s]: 1.0 for s in src}
    fixed.update({pad_node[d]: 0.0 for d in dst})
    free = np.array([i for i in range(n) if i not in fixed])
    fx = np.array(sorted(fixed))
    vf = np.array([fixed[i] for i in fx])
    # cells that no fixed node reaches make the system singular: keep the component of the fixed nodes
    from scipy.sparse.csgraph import connected_components
    ncomp, lab = connected_components(A != 0, directed=False)
    keep_lab = set(lab[fx])
    free = free[np.isin(lab[free], list(keep_lab))]
    Aff = A[free][:, free]
    b = -A[free][:, fx] @ vf
    v = np.zeros(n)
    v[fx] = vf
    v[free] = spsolve(Aff.tocsc(), b)
    I = -(A[[pad_node[d] for d in dst]] @ v).sum()        # current into the 0 V pads
    R = 1.0 / I
    scale = amps * R                                        # node voltage -> volts at `amps`
    out = {'R_mohm': R * 1e3, 'drop_mV': amps * R * 1e3, 'amps': amps, 'res_mm': res, 'cu_um': t_cu * 1e6,
           'barrels': n_barrels, 'pads_V': {k: round(v[i] * scale * 1e3, 2) for k, i in pad_node.items()}}
    # current density per net and layer: the neck (A per mm of copper width) and the copper's own drop
    neck = []
    for key, idx in index.items():
        V = np.full(idx.shape, np.nan)
        V[idx >= 0] = v[idx[idx >= 0]] * scale
        gx = np.diff(V, axis=1) / (res * 1e-3)
        gy = np.diff(V, axis=0) / (res * 1e-3)
        jx = np.nan_to_num(gx[:-1, :]) if gx.shape[0] > 1 else gx
        jy = np.nan_to_num(gy[:, :-1]) if gy.shape[1] > 1 else gy
        h, w = min(jx.shape[0], jy.shape[0]), min(jx.shape[1], jy.shape[1])
        J = np.hypot(jx[:h, :w], jy[:h, :w]) * t_cu / RHO / 1000.0     # A per mm of width
        J[~((idx[:h, :w] >= 0))] = 0
        if J.size and np.nanmax(J) > 0:
            k = np.unravel_index(np.nanargmax(J), J.shape)
            neck.append({'net': key[0], 'layer': key[1], 'A_per_mm': round(float(J[k]), 1),
                         'at_page_mm': [round(x0 + (k[1] - 1) * res, 1), round(y0 + (k[0] - 1) * res, 1)],
                         'p99_A_per_mm': round(float(np.percentile(J[J > 0], 99)), 1)})
    out['neck'] = neck
    print(json.dumps(out, indent=1))
    rep = opt(args, '--report', None)
    if rep:
        json.dump(out, open(rep, 'w'), indent=1)


if __name__ == '__main__':
    main()
