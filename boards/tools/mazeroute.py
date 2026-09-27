"""Finish the connections the autorouter left open: a grid maze router working on a board dump, with
coupled routing for differential pairs and negotiated rip-up for everything else. Runs anywhere with
numpy, scipy, scikit-image and shapely; KiCad is only needed before (dump_board.py --route-view, drc)
and after (add_routes.py, drc).

    python3 mazeroute.py BOARD DUMP.json DRC.rpt OUT.json [options]

Which nets: every net the DRC report lists as unconnected. GND is left out (its pads reach the planes
through pad_vias.py) unless --gnd, --gnd-pads or --gnd-movable asks for it. For each net, the connected
islands of its copper are worked out from the dump (pads, tracks, vias and the zones' actual fills) and
joined one at a time, nearest island first.

A path runs on the signal layers of a RES mm grid, with through vias where it changes layer. A cell is
open to a track when copper of any other net is at least the larger of the two net classes' clearances
plus half the track width away, the board edge 0.3 mm plus half the width, and the track stays out of
the router keepouts (the 'D:' areas that protect the pours; a pour's own net may enter). A via needs the
same on every layer, 0.25 mm hole to hole, and no overlap with a pad of its own net. Cells right at the
clearance limit cost a little more, so paths keep some room and straighten. Each connection is searched
in a window around the two islands' nearest points (6 mm margin, then 20 mm if that fails).

1. Pairs (--pairs P:N,...): both halves are routed together as one band, the gap held from end to
   end. Whatever the band runs over is taken up and routed again in step 2.
2. Negotiation, in rounds (--iters). Every net is routed through the unlocked copper of other nets at
   a price (--pen, times --grow each round) instead of treating it as a wall. The overlaps left at the
   end of a round are the clashes: the cells where they happen get dearer for good (--hinc), and the
   copper that lost is taken up and routed again next round. It stops when a round ends with no clash
   and nothing failed, or after --minutes. Locked copper (hand-placed escapes, via arrays) and the
   --protect nets never move.

The path is straightened by running, from each point, to the farthest later point it can reach in a
straight line with room to spare, and runs that keep their direction are merged. OUT.json lists the new
tracks and vias per net and the board tracks and vias to take away; add_routes.py applies both. DRC
afterwards is the check.

    --only PAT,...        route just these nets (shell patterns), and whatever they push out of the way
    --first NET,...       route these first, in this order
    --protect PAT,...     nets that are never taken up (default: the power nets)
    --iters N             negotiation rounds (12); --minutes M stops earlier (240)
    --pen X, --grow G     price per cell of running over another net's copper (4), and its growth per
                          round (1.6)
    --hinc H              what a clash adds to its cells for later rounds (1.5)
    --fullrip N           a clashing net with at most N pads is taken up whole, not just the piece (0)
    --wide NET,...        also try a window 200 mm wider for these nets (long runs that must detour)
    --pairs P:N,...       differential pairs; --pairgeom PAT=W/GAP[/W_in/GAP_in[/CLR]] their geometry on
                          the outer (and inner) layers; --only-pairs routes just them
    --reserve PAT=X,...   route matching nets as if X mm wider on each side except near their ends, so
                          the other half of a pair finds room beside them
    --width PAT=W,...     track width for matching nets (else the net class)
    --strip NET,...       take up these nets' unlocked copper first and route them again
    --gnd                 join GND islands too; --gnd-pads REF.PAD,... only islands with these pads;
                          --gnd-movable also lets routes take up unlocked GND tracks
    --clash-log FILE      append each round's failed nets and clash spots (JSON lines), to find the
                          bottleneck when rounds stop improving
    --res MM              grid step (0.05)
"""
import fnmatch
import importlib.util
import json
import math
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from skimage.graph import MCP_Geometric

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[1:]
board, dump_path, rpt_path, out_path = argv[:4]
opts = argv[4:]


def opt(name, default):
    return opts[opts.index(name) + 1] if name in opts else default


RES = float(opt('--res', 0.05))
bdir = os.path.join(HERE, '..', board)
spec = importlib.util.spec_from_file_location('layout', os.path.join(bdir, 'layout.py'))
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)

CLR = 0.2            # mm, copper to copper when a net has no class
EDGE = 0.3           # mm, copper to board edge
H2H = 0.25           # mm, hole to hole
EPS = 0.005          # mm of margin on top of every rule
PARTNER, PGAP = {}, {}   # pair nets: the other half, and the gap they keep to it
PFAC = [float(opt('--pen', 4.0))]   # cost per cell of a path through another net's movable copper (grows)
NCU = L.COPPER_LAYERS
ALL_CU = ['F.Cu'] + ['In%d.Cu' % k for k in range(1, NCU - 1)] + ['B.Cu']
D = json.load(open(dump_path))
PLANES = set(D.get('plane_layers', ['%s.Cu' % k for k, t in getattr(L, 'LAYER_TYPES', {}).items() if t == 'power']))
ROUTE = [l for l in ALL_CU if l not in PLANES]           # layers a track may use

# ----------------------------------------------------------------------------- net classes
WIDTH, VIA = {}, {}
for name, c in getattr(L, 'NETCLASSES', {}).items():
    for n in c['nets']:
        WIDTH[n] = c['width']
        VIA[n] = (c.get('via', 0.6), c.get('drill', 0.3))
NC = D.get('netclass', {})
WOVER = [kv.split('=') for kv in opt('--width', '').split(',') if '=' in kv]
RESERVE = [kv.split('=') for kv in opt('--reserve', '').split(',') if '=' in kv]
WIDE = [n for n in opt('--wide', '').split(',') if n]
GND_MOVABLE = '--gnd-movable' in opts   # unlocked GND tracks may be taken up too (their pads then get joined
                                        # again, usually by a via into the nearest GND pour)
WITH_GND = '--gnd' in opts or '--gnd-pads' in opts or GND_MOVABLE   # also join GND pads the pad-via pass could not
                                  # reach (a via of their own or a track to the nearest GND via, pad or pour)
PROTECT = opt('--protect', 'VM,BATP,BATN,VSYS,CHG_PMID,CHG_SW*,SW_IN,PRE_D,FET_MID,BMS_RSN,VBUS_C,PPHV,'
                           'SERVO_V,LIDAR_V,BUCK_SW,BUCK_VIN,+5V,BST_SW,POE_OUTPUT,POE_52V,STK_VSYS,PSE_*,'
                           'VDD_*,+1V8,+5V0,VIN*').split(',')
protected = lambda n: any(fnmatch.fnmatchcase(n, p) for p in PROTECT)


def width(net):
    for pat, w in WOVER:
        if fnmatch.fnmatchcase(net, pat):
            return float(w)
    return WIDTH.get(net, NC[net][0] if net in NC else 0.2)


def via_size(net):
    return VIA.get(net, (NC[net][2], NC[net][3]) if net in NC else (0.6, 0.3))


def clearance(net):
    return NC[net][1] if net in NC else CLR


base_clearance = clearance


def reserve(net):
    for pat, x in RESERVE:
        if fnmatch.fnmatchcase(net, pat):
            return float(x)
    return 0.0


# ----------------------------------------------------------------------------- the board
e = D['edges']                       # outline bounding box, drawn with a 0.1 mm line
EDGES = (e[0] + 0.05, e[1] + 0.05, e[2] - 0.05, e[3] - 0.05)
pads, tracks, vias = [], [], []
for f in D['fps']:
    for p in f['pads']:
        lay = [l for l in p['layers'] if l in ALL_CU]
        if not lay and not p['drill']:
            continue
        pads.append({'ref': f['ref'], 'n': p['n'], 'net': p['net'], 'bb': p['bb'], 'x': p['x'], 'y': p['y'],
                     'layers': lay, 'drill': p['drill'], 'smd': not p['drill']})
for t in D['tracks']:
    tracks.append({'net': t['net'], 'layer': t['layer'], 'w': t['w'], 'p': t['p'], 'locked': t.get('locked', True),
                   'src': 'board'})
for v in D['vias']:
    vias.append({'net': v['net'], 'x': v['x'], 'y': v['y'], 'dia': v['dia'] or 0.6, 'drill': v['drill'],
                 'locked': v.get('locked', True), 'src': 'board'})

zones, keeps = {}, []                # zones: (name, layer) -> {net, polys}; keeps: router keepouts
for a in D.get('areas', []):
    lays = [l for l in a['layers'] if l in ALL_CU]
    if a['rule']:
        keeps.append({'name': a['name'], 'layers': lays, 'tracks': a['no_tracks'], 'vias': a['no_vias'],
                      'polys': [[[tuple(p) for p in ring] for ring in poly] for poly in a['polys']]})
    else:
        for l in lays:
            polys = a.get('fills', {}).get(l)
            if polys is None:
                polys = a['polys']
            zones[(a['name'], l)] = {'net': a['net'], 'layer': l,
                                     'polys': [[[tuple(p) for p in ring] for ring in poly] for poly in polys]}
for k in keeps:
    # a keepout guards its pour against other nets, not against the pour's own net: 'D:<pour>_i_j' is
    # an Atlas pour's, 'D:am_<net>' one over an Antmicro pour
    if k['name'].startswith('D:am_'):
        k['net'] = k['name'][5:]
    else:
        zn = 'P:' + k['name'][2:].rsplit('_', 2)[0]
        k['net'] = next((z['net'] for (n, l), z in zones.items() if n == zn), None)


def poly_shape(polys):
    out = []
    for poly in polys:
        if len(poly[0]) >= 3:
            try:
                out.append(Polygon(poly[0], [h for h in poly[1:] if len(h) >= 3]).buffer(0))
            except Exception:
                pass
    return unary_union(out) if out else None


GND_PADS = []
for rp in opt('--gnd-pads', '').split(','):
    if '.' in rp:
        ref, num = rp.split('.', 1)
        for f in D['fps']:
            if f['ref'] == ref:
                GND_PADS += [(q['x'], q['y']) for q in f['pads'] if q['n'] == num]


# ----------------------------------------------------------------------------- connectivity
def pad_geo(p):
    bb = p['bb']
    if p['drill']:                   # round through-hole pad: its bounding box corners are not copper
        return ('circ', (p['x'], p['y'], min(bb[2] - bb[0], bb[3] - bb[1]) / 2 - 0.02))
    return ('rect', (bb[0] + 0.03, bb[1] + 0.03, bb[2] - 0.03, bb[3] - 0.03))


def shape(kind, g):
    if kind == 'rect':
        return box(*g)
    if kind == 'circ':
        return Point(g[0], g[1]).buffer(max(g[2], 0.01), 12)
    if kind == 'seg':
        return LineString([(g[0], g[1]), (g[2], g[3])]).buffer(max(g[4] / 2, 0.01), 6)
    return poly_shape(g)


def net_items(net):
    """[(layers, kind, geometry)] of all copper of a net"""
    out = []
    for p in pads:
        if p['net'] == net:
            k, g = pad_geo(p)
            out.append((p['layers'], k, g))
    for t in tracks:
        if t['net'] == net:
            out.append(([t['layer']], 'seg', t['p'] + [t['w']]))
    for v in vias:
        if v['net'] == net:
            out.append((list(ALL_CU), 'circ', (v['x'], v['y'], v['dia'] / 2)))
    for (n, l), z in zones.items():
        if z['net'] == net and poly_shape(z['polys']) is not None:
            out.append(([l], 'poly', z['polys']))
    return out


def islands(net):
    """the connected groups of a net's copper, biggest first, each with its routing targets"""
    items = net_items(net)
    shp = [shape(k, g) for (ls, k, g) in items]
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    bbs = [s.bounds for s in shp]
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if not set(items[i][0]) & set(items[j][0]):
                continue
            a, b = bbs[i], bbs[j]
            if a[2] < b[0] - 0.01 or b[2] < a[0] - 0.01 or a[3] < b[1] - 0.01 or b[3] < a[1] - 0.01:
                continue
            if shp[i].distance(shp[j]) < 0.002:
                parent[find(i)] = find(j)
    groups = {}
    for i in range(len(items)):
        groups.setdefault(find(i), []).append(i)
    out = []
    for g in groups.values():
        geos = []
        for i in g:
            ls, k, geo = items[i]
            for l in ls:
                geos.append((l, k, geo))
        out.append({'geos': geos, 'shape': unary_union([shp[i] for i in g])})
    out.sort(key=lambda isl: -len(isl['geos']))
    return out


# ----------------------------------------------------------------------------- rasterising
class Win:
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0 = x0, y0
        self.nx = int(math.ceil((x1 - x0) / RES))
        self.ny = int(math.ceil((y1 - y0) / RES))

    def px(self, x, y):
        return ((x - self.x0) / RES - 0.5, (y - self.y0) / RES - 0.5)

    def xy(self, i, j):
        return (self.x0 + (j + 0.5) * RES, self.y0 + (i + 0.5) * RES)

    def img(self):
        im = Image.new('1', (self.nx, self.ny), 0)
        return im, ImageDraw.Draw(im)

    def poly(self, dr, polys):
        for poly in polys:
            dr.polygon([self.px(*p) for p in poly[0]], fill=1)
            for hole in poly[1:]:
                dr.polygon([self.px(*p) for p in hole], fill=0)

    def inside(self, bb, pad=5.0):
        return not (bb[2] < self.x0 - pad or bb[0] > self.x0 + self.nx * RES + pad or
                    bb[3] < self.y0 - pad or bb[1] > self.y0 + self.ny * RES + pad)


def dist(mask):
    """mm from every cell to the nearest set cell (for the keepout polygons, which only guide)"""
    if not mask.any():
        return np.full(mask.shape, 1e9)
    return ndimage.distance_transform_edt(~mask) * RES


class Field:
    """Exact distance in mm from every cell centre to a set of shapes (rectangles, round-ended
    segments, circles), known up to CAP; farther is reported as CAP."""
    CAP = 1.0

    def __init__(self, win):
        self.win = win
        self.d = np.full((win.ny, win.nx), self.CAP)

    def _patch(self, x0, y0, x1, y1):
        w, c = self.win, self.CAP
        j0 = max(0, int(math.floor((x0 - c - w.x0) / RES - 0.5)))
        j1 = min(w.nx, int(math.ceil((x1 + c - w.x0) / RES + 0.5)))
        i0 = max(0, int(math.floor((y0 - c - w.y0) / RES - 0.5)))
        i1 = min(w.ny, int(math.ceil((y1 + c - w.y0) / RES + 0.5)))
        if j0 >= j1 or i0 >= i1:
            return None
        cx = (w.x0 + (np.arange(j0, j1) + 0.5) * RES)[None, :]
        cy = (w.y0 + (np.arange(i0, i1) + 0.5) * RES)[:, None]
        return i0, i1, j0, j1, cx, cy

    def _put(self, p, d):
        i0, i1, j0, j1 = p[:4]
        sub = self.d[i0:i1, j0:j1]
        np.minimum(sub, d, out=sub)

    def rect(self, bb, extra=0.0):
        p = self._patch(*bb)
        if p:
            cx, cy = p[4], p[5]
            dx = np.maximum(np.maximum(bb[0] - cx, cx - bb[2]), 0.0)
            dy = np.maximum(np.maximum(bb[1] - cy, cy - bb[3]), 0.0)
            self._put(p, np.hypot(dx, dy) - extra)

    def seg(self, x1, y1, x2, y2, hw, extra=0.0):
        p = self._patch(min(x1, x2) - hw, min(y1, y2) - hw, max(x1, x2) + hw, max(y1, y2) + hw)
        if p:
            cx, cy = p[4], p[5]
            vx, vy = x2 - x1, y2 - y1
            l2 = vx * vx + vy * vy
            t = np.clip(((cx - x1) * vx + (cy - y1) * vy) / l2, 0.0, 1.0) if l2 > 0 else 0.0
            self._put(p, np.hypot(cx - (x1 + t * vx), cy - (y1 + t * vy)) - hw - extra)

    def circ(self, x, y, r, extra=0.0):
        p = self._patch(x - r, y - r, x + r, y + r)
        if p:
            self._put(p, np.hypot(p[4] - x, p[5] - y) - r - extra)


def maps(win, net, w, vd, vh, soft=None, clr=None):
    """free[l] (a track of width w may run here), via_free, dfree[l] (room beyond the rules), and with
    soft = set of movable nets, their tracks and vias turned into penalties: pen[l], pen_via.
    net '__pair__' (a pair's centre line) makes every piece of copper an obstacle, the pair's own too."""
    clr = clearance(net) if clr is None else clr
    def ex(n):
        if n == PARTNER.get(net):             # the other half of a pair: its gap is the rule
            return -max(0.0, clr - PGAP[net])
        return max(0.0, clearance(n) - clr) if n in NC or n in PARTNER else 0.0   # the other class wants more
    cu = {l: Field(win) for l in ALL_CU}          # other nets' fixed copper per layer
    su = {l: Field(win) for l in ALL_CU} if soft is not None else None   # movable copper
    holes = Field(win)                             # every drilled hole, any net
    own_smd = Field(win)                           # this net's surface pads (no via in them)
    for p in pads:
        if not win.inside(p['bb']):
            continue
        other = p['net'] != net or not p['net']
        if other:
            for l in p['layers']:
                cu[l].rect(p['bb'], ex(p['net']))
        if p['drill']:
            holes.circ(p['x'], p['y'], p['drill'] / 2)
            if other and not p['layers']:                      # NPTH: keep copper off its hole too
                for l in ALL_CU:
                    cu[l].circ(p['x'], p['y'], p['drill'] / 2)
        if not other and p['smd']:
            own_smd.rect(p['bb'])
    movable = lambda it: soft is not None and not it['locked'] and it['net'] in soft
    for t in tracks:
        x1, y1, x2, y2 = t['p']
        if t['net'] == net or t['layer'] not in cu:
            continue
        if not win.inside((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))):
            continue
        (su if movable(t) else cu)[t['layer']].seg(x1, y1, x2, y2, t['w'] / 2, ex(t['net']))
    for v in vias:
        if not win.inside((v['x'], v['y'], v['x'], v['y'])):
            continue
        if not movable(v):
            holes.circ(v['x'], v['y'], v['drill'] / 2)
        if v['net'] != net:
            for l in ALL_CU:
                (su if movable(v) else cu)[l].circ(v['x'], v['y'], v['dia'] / 2, ex(v['net']))
    kt = {l: win.img() for l in ROUTE}
    kv = win.img()
    for k in keeps:
        if k['net'] == net:
            continue
        for l in k['layers']:
            if k['tracks'] and l in kt:
                win.poly(kt[l][1], k['polys'])
        if k['vias']:
            win.poly(kv[1], k['polys'])
    ii, jj = np.mgrid[0:win.ny, 0:win.nx]
    cx = win.x0 + (jj + 0.5) * RES
    cy = win.y0 + (ii + 0.5) * RES
    d_edge = np.minimum.reduce([cx - EDGES[0], EDGES[2] - cx, cy - EDGES[1], EDGES[3] - cy])
    A = lambda im: np.array(im[0], dtype=bool)
    free, dfree = {}, {}
    d_all = np.minimum.reduce([cu[l].d for l in ALL_CU])
    for l in ROUTE:
        dfree[l] = np.minimum.reduce([cu[l].d - (clr + w / 2), dist(A(kt[l])) - (w / 2 + RES),
                                      d_edge - (EDGE + w / 2)])
        free[l] = dfree[l] >= EPS
    via_free = ((d_all >= clr + vd / 2 + EPS) & (holes.d >= H2H + vh / 2 + EPS) &
                (dist(A(kv)) >= vd / 2 + RES) & (d_edge >= EDGE + vd / 2 + EPS) &
                (own_smd.d >= vd / 2 + 0.1))
    if soft is None:
        return free, via_free, dfree, None, None
    pen = {l: np.where(su[l].d < clr + w / 2 + EPS, PFAC[0], 0.0) for l in ROUTE}
    s_all = np.minimum.reduce([su[l].d for l in ALL_CU])
    pen_via = np.where(s_all < clr + vd / 2 + EPS, PFAC[0] * 10, 0.0)
    return free, via_free, dfree, pen, pen_via


def cells(win, geo, free_l):
    """grid cells inside one item's copper that a track may start from. A zone fill only counts from
    0.35 mm inside its edge: the fill pulls back from the new tracks when it is poured again, and a
    track ending right at the old edge would then end in nothing."""
    kind, g = geo
    ii, jj = np.mgrid[0:win.ny, 0:win.nx]
    cx = win.x0 + (jj + 0.5) * RES
    cy = win.y0 + (ii + 0.5) * RES
    if kind == 'rect':
        m = (cx >= g[0]) & (cx <= g[2]) & (cy >= g[1]) & (cy <= g[3])
    elif kind == 'seg':
        f = Field(win)
        f.seg(g[0], g[1], g[2], g[3], g[4] / 2)
        m = f.d <= 0
    elif kind == 'circ':
        m = np.hypot(cx - g[0], cy - g[1]) <= g[2]
    else:
        im, dr = win.img()
        win.poly(dr, g)
        m = np.array(im, dtype=bool)
        m = ndimage.binary_erosion(m, iterations=max(1, int(round(0.35 / RES))))
    return list(zip(*np.nonzero(m & free_l)))


# ----------------------------------------------------------------------------- one connection
SZ = 40.0            # layer step length in grid cells: a through via costs about 2 x SZ x RES mm of track
OUTER = 1.2          # outer layers cost a little more per mm: they carry the parts


def fine_pad(geos):
    """centre of the narrowest pad among the targets, if it is fine-pitch, to put a cell centre on it"""
    best = None
    for lay, kind, g in geos:
        if kind == 'rect':
            wmin = min(g[2] - g[0], g[3] - g[1])
            if wmin < 0.4 and (best is None or wmin < best[0]):
                best = (wmin, (g[0] + g[2]) / 2, (g[1] + g[3]) / 2)
    return best


def pts_of(geos):
    pts = []
    for lay, kind, g in geos:
        if kind in ('rect', 'seg'):
            pts += [(g[0], g[1]), (g[2], g[3])]
        elif kind == 'circ':
            pts += [(g[0], g[1])]
        else:
            s = poly_shape(g)
            if s is not None and not s.is_empty:
                b = s.bounds
                pts += [(b[0], b[1]), (b[2], b[3])]
    return pts


# ----------------------------------------------------------------------------- history (negotiation)
HR = 0.25            # mm, grid of the congestion history
HNX = int((EDGES[2] - EDGES[0]) / HR) + 2
HNY = int((EDGES[3] - EDGES[1]) / HR) + 2
HIST = {l: np.zeros((HNY, HNX)) for l in ROUTE}
HIST_VIA = np.zeros((HNY, HNX))


def hist_at(win, h):
    """the history grid sampled at the window's cell centres"""
    j = ((win.x0 + (np.arange(win.nx) + 0.5) * RES - EDGES[0]) / HR).astype(int).clip(0, HNX - 1)
    i = ((win.y0 + (np.arange(win.ny) + 0.5) * RES - EDGES[1]) / HR).astype(int).clip(0, HNY - 1)
    return h[np.ix_(i, j)]


def bump(x, y, layers, amount, r=0.5):
    """more history cost around a spot where two nets fought"""
    j0, j1 = int((x - r - EDGES[0]) / HR), int((x + r - EDGES[0]) / HR) + 1
    i0, i1 = int((y - r - EDGES[1]) / HR), int((y + r - EDGES[1]) / HR) + 1
    j0, i0 = max(j0, 0), max(i0, 0)
    for l in layers:
        if l in HIST:
            HIST[l][i0:i1, j0:j1] += amount
    if len(layers) > 1:
        HIST_VIA[i0:i1, j0:j1] += amount


def build_cost(win, free, via_free, dfree, pen, pen_via):
    nl = len(ROUTE)
    cost = np.full((2 * nl - 1, win.ny, win.nx), np.inf)
    lattice = np.zeros((win.ny, win.nx), bool)
    lattice[::2, ::2] = True
    vok = via_free & lattice
    near_free = {l: ndimage.binary_dilation(free[l], np.ones((3, 3), bool)) for l in ROUTE}
    for k, l in enumerate(ROUTE):
        base = (OUTER if l in ('F.Cu', 'B.Cu') else 1.0) + np.clip(0.08 - dfree[l], 0, None) * 8.0 + hist_at(win, HIST[l])
        if pen is not None:
            base = base + pen[l]
        c = np.where(free[l], base, np.inf)
        # a via may pass through a layer where a track may not go (a keepout without via ban), as
        # long as no open cell touches it, so the path cannot leave on that layer
        c[vok & ~near_free[l]] = 1.0
        cost[2 * k] = c
        if k < nl - 1:
            cost[2 * k + 1] = np.where(vok, 1.0 + (pen_via if pen_via is not None else 0.0) + hist_at(win, HIST_VIA) * 4,
                                       np.inf)
    return cost


def solve(win, cost, starts, ends, dfree, with_cost=False):
    offs = [(0, di, dj) for di in (-1, 0, 1) for dj in (-1, 0, 1) if (di, dj) != (0, 0)] + [(1, 0, 0), (-1, 0, 0)]
    mcp = MCP_Geometric(cost, offsets=offs, sampling=(SZ, 1.0, 1.0))
    cum, _ = mcp.find_costs(starts, ends, find_all_ends=False)
    best = min(ends, key=lambda q: cum[q])
    if not np.isfinite(cum[best]):
        return (None, np.inf) if with_cost else None
    g = geometry(win, mcp.traceback(best), dfree)
    return (g, float(cum[best])) if with_cost else g


def window(pts_a, pts_b, margin, fine=None):
    near_a = sorted(pts_a, key=lambda p: min(math.dist(p, q) for q in pts_b))[:4]
    near_b = sorted(pts_b, key=lambda p: min(math.dist(p, q) for q in pts_a))[:4]
    xs, ys = [p[0] for p in near_a + near_b], [p[1] for p in near_a + near_b]
    x0, y0 = max(EDGES[0], min(xs) - margin), max(EDGES[1], min(ys) - margin)
    if fine:                     # a cell centre on the fine-pitch pad's centre: the escape runs on its axis
        x0 = fine[1] - (math.floor((fine[1] - x0) / RES) + 0.5) * RES
        y0 = fine[2] - (math.floor((fine[2] - y0) / RES) + 0.5) * RES
    return Win(x0, y0, min(EDGES[2], max(xs) + margin), min(EDGES[3], max(ys) + margin))


def route(net, ga, gb, w, vd, vh, margin, soft=None):
    """cheapest path between two groups of targets; (geometry, None) or (None, reason)"""
    pa, pb = pts_of(ga), pts_of(gb)
    if not pa or not pb:
        return None, 'no targets'
    # the window: around the closest parts of the two groups (a big island would make it the whole board)
    win = window(pa, pb, margin, fine_pad(ga + gb))
    free, via_free, dfree, pen, pen_via = maps(win, net, w, vd, vh, soft)
    extra = reserve(net)
    if extra:
        fat = maps(win, net, w + 2 * extra, vd, vh, soft)[0]
        ends_mask = np.zeros((win.ny, win.nx), bool)
        for lay, kind, g in ga + gb:
            if lay in ROUTE:
                for i, j in cells(win, (kind, g), np.ones((win.ny, win.nx), bool)):
                    ends_mask[i, j] = True
        near = ndimage.distance_transform_edt(~ends_mask) * RES < 1.5
        free = {l: np.where(near, free[l], fat[l]) for l in ROUTE}
    starts, ends = [], []
    for lay, kind, g in ga:
        if lay in ROUTE:
            starts += [(2 * ROUTE.index(lay), i, j) for i, j in cells(win, (kind, g), free[lay])]
    for lay, kind, g in gb:
        if lay in ROUTE:
            ends += [(2 * ROUTE.index(lay), i, j) for i, j in cells(win, (kind, g), free[lay])]
    if not starts or not ends:
        return None, 'no open cell on %s' % ('start' if not starts else 'end')
    if '--debug-net' in opts and net == opt('--debug-net', '') and soft is None:
        np.savez_compressed(opt('--debug-out', 'net.npz'), win=np.array([win.x0, win.y0, win.nx, win.ny]),
                            free=np.array([free[l] for l in ROUTE]), via=via_free,
                            starts=np.array(starts), ends=np.array(ends))
    res = solve(win, build_cost(win, free, via_free, dfree, pen, pen_via), starts, ends, dfree)
    return (res, None) if res else (None, 'no path')


# ----------------------------------------------------------------------------- differential pairs
PAIRGEOM = []
for kv in opt('--pairgeom', '').split(','):
    if '=' in kv:
        pat, vals = kv.split('=')
        v = [float(x) for x in vals.split('/')]
        if len(v) == 2:
            v = v + v
        if len(v) == 4:
            v = v + [None]
        PAIRGEOM.append((pat, v))


def pgeom(net, layer):
    """track width, gap to its partner and clearance to other nets for a pair net on a layer"""
    for pat, v in PAIRGEOM:
        if fnmatch.fnmatchcase(net, pat):
            wo, go, wi, gi, cl = v
            outer = layer in ('F.Cu', 'B.Cu')
            return (wo if outer else wi), (go if outer else gi), (cl if cl is not None else base_clearance(net))
    w = width(net)
    return w, max(w, base_clearance(net)), base_clearance(net)


def pair_vias(p):
    """via size and centre spacing of a pair's two vias"""
    vd, vh = via_size(p)
    pv = max(vd + PGAP.get(p, clearance(p)) + 0.005, vh + H2H) + 0.02
    return vd, vh, math.ceil(pv / 0.05) * 0.05


def route_band(p, n, A, B, margin, soft=None, axes=None, layers=None):
    """centre line of a coupled pair from near A to near B: a path for one track as wide as both
    tracks and their gap, whose vias are discs big enough for two vias side by side. axes = (aA, aB), the
    N-to-P vectors at both ends: the line then leaves A and reaches B on the sides that keep P on the
    same side of the pair all the way (no crossover at the pads); both ways round are tried."""
    hb = max(pgeom(p, l)[0] + pgeom(p, l)[1] / 2 for l in ROUTE) + 0.01
    clr = max(pgeom(p, l)[2] for l in ROUTE)
    vd, vh, pv = pair_vias(p)
    win = window([A], [B], margin)
    free, via_free, dfree, pen, pen_via = maps(win, '__pair__', 2 * hb, pv + vd, pv + vh, soft, clr=clr)
    ii, jj = np.mgrid[0:win.ny, 0:win.nx]
    cx = win.x0 + (jj + 0.5) * RES
    cy = win.y0 + (ii + 0.5) * RES
    # open space big enough to go somewhere (not a pocket between header pins), per layer
    room = {}
    for l in ROUTE:
        lab, nlab = ndimage.label(free[l], np.ones((3, 3), bool))
        size = np.bincount(lab.ravel())
        size[0] = 0
        room[l] = size[lab] >= int(2.0 / (RES * RES))
    ends = []
    for e, pt in enumerate((A, B)):
        cand = []
        lays = [l for l in ROUTE if layers is None or l in layers[e]]   # surface pads: start on their layer
        for rt in (1.0, 1.5, 2.0, 3.0, 4.0, 5.0):
            m = np.hypot(cx - pt[0], cy - pt[1]) <= rt
            cand = []
            for k, l in enumerate(ROUTE):
                if l in lays:
                    cand += [(2 * k, i, j) for i, j in zip(*np.nonzero(m & free[l] & room[l]))]
            if len(cand) >= 4:
                break
        ends.append(cand)
    if not ends[0] or not ends[1]:
        return None, 'no room for the pair near its %s end' % ('first' if not ends[0] else 'second')
    if '--debug-band' in opts:
        np.savez_compressed(opt('--debug-band', 'band.npz'), win=np.array([win.x0, win.y0, win.nx, win.ny]),
                            free=np.array([free[l] for l in ROUTE]), via=via_free,
                            starts=np.array(ends[0]), ends=np.array(ends[1]))
    cost = build_cost(win, free, via_free, dfree, pen, pen_via)
    fat_maps = (win, free, via_free)
    if axes is None:
        res = solve(win, cost, ends[0], ends[1], dfree)
        if res:
            res['maps'] = fat_maps
        return (res, None) if res else (None, 'no path')
    (ax, ay), (bx, by) = axes
    xy = lambda c: win.xy(c[1], c[2])
    cands = []
    for s in (1, -1):
        st = [c for c in ends[0] if s * ((xy(c)[0] - A[0]) * ay - (xy(c)[1] - A[1]) * ax) > 0]
        en = [c for c in ends[1] if s * ((B[0] - xy(c)[0]) * by - (B[1] - xy(c)[1]) * bx) > 0]
        if st and en:
            r = solve(win, cost, st, en, dfree, with_cost=True)
            if r[0]:
                r[0]['maps'] = fat_maps
                cands.append(r)
    r = solve(win, cost, ends[0], ends[1], dfree, with_cost=True)
    if r[0]:
        r[0]['maps'] = fat_maps
        cands.append(r)
    if not cands:
        return None, 'no path'
    return sorted(cands, key=lambda c: c[1]), None


def offset_line(pts, d):
    """polyline moved sideways by d (left of its direction for d > 0), with mitred corners; also the
    normals of its segments"""
    nrm = []
    for a, b in zip(pts, pts[1:]):
        L = math.dist(a, b) or 1e-9
        nrm.append((-(b[1] - a[1]) / L, (b[0] - a[0]) / L))
    if abs(d) < 1e-9:
        return list(pts), nrm
    try:
        o = LineString(pts).offset_curve(d, join_style='mitre', mitre_limit=4.0)
        if o.geom_type == 'LineString' and len(o.coords) >= 2:
            return [tuple(c) for c in o.coords], nrm
    except Exception:
        pass
    out = []                                  # fallback: offset each vertex along the mitre
    for k, p in enumerate(pts):
        if k == 0:
            nx, ny = nrm[0]
        elif k == len(pts) - 1:
            nx, ny = nrm[-1]
        else:
            (ax, ay), (bx, by) = nrm[k - 1], nrm[k]
            s = 1.0 + ax * bx + ay * by
            nx, ny = ((ax + bx) / s, (ay + by) / s) if s > 0.2 else (ax, ay)
        out.append((p[0] + d * nx, p[1] + d * ny))
    return out, nrm


def run_normal(pts, at_end, span=0.5):
    """left normal of a polyline's direction over its first (or last) span mm"""
    seq = list(reversed(pts)) if at_end else list(pts)
    o, q = seq[0], seq[1]
    for q in seq[1:]:
        if math.dist(o, q) >= span:
            break
    dx, dy = (o[0] - q[0], o[1] - q[1]) if at_end else (q[0] - o[0], q[1] - o[1])
    L = math.hypot(dx, dy) or 1e-9
    return -dy / L, dx / L


def simplify_run(pts, tol=0.02):
    """drop points that make no real corner (short zig-zags from the grid)"""
    if len(pts) <= 2:
        return list(pts)
    s = LineString(pts).simplify(tol, preserve_topology=False)
    c = [tuple(v) for v in s.coords]
    c[0], c[-1] = tuple(pts[0]), tuple(pts[-1])
    return c


def cut_back(pts, s):
    """(the polyline without its last s mm, the piece it lost); None when it is not that long"""
    rem = s
    for i in range(len(pts) - 1, 0, -1):
        a, b = pts[i - 1], pts[i]
        L = math.dist(a, b)
        if L >= rem - 1e-9:
            t = (L - rem) / L if L else 0.0
            q = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            return pts[:i] + [q], [q] + pts[i:]
        rem -= L
    return None


def cut_front(pts, s):
    """(the piece of the first s mm, the polyline without it); None when it is not that long"""
    r = cut_back(list(reversed(pts)), s)
    if not r:
        return None
    rest, piece = r
    return list(reversed(piece)), list(reversed(rest))


def band_tracks(p, n, res, sp):
    """the two tracks and the via pairs of a routed centre line; sp = +1 when p starts on the left.
    Returns (tracks, vias, sp at the far end). At each change of layer the two vias sit on a circle
    round the centre line's via point (the router kept that whole disc free of other nets); the angle,
    and which side p takes on the new layer, are the ones that keep the two halves furthest apart. When
    no angle keeps the pair's own gaps there (a sharp turn right at the via), the via point slides along
    the centre line to where one does, if the router's maps (res['maps']) say the via and the moved piece
    of line fit there."""
    runs = []
    for l, a, b in res['segs']:
        if runs and runs[-1][0] == l and math.dist(runs[-1][1][-1], a) < 1e-6:
            runs[-1][1].append(b)
        else:
            runs.append((l, [a, b]))
    runs = [(l, simplify_run(pts)) for l, pts in runs]
    maps = res.get('maps')
    vd, vh, pv = pair_vias(p)
    need_t = PGAP.get(p, 0.1)                       # track to track inside the pair
    need_v = max(need_t, base_clearance(p) - 0.005)  # anything with a via in it

    def dims(l):
        w, g, _ = pgeom(p, l)
        return w, (w + g) / 2

    def fits_line(l, pts):
        if not maps:
            return False
        win, free, _ = maps
        for a, b in zip(pts, pts[1:]):
            k = max(1, int(math.dist(a, b) / (RES / 2)))
            for t in range(k + 1):
                x, y = a[0] + (b[0] - a[0]) * t / k, a[1] + (b[1] - a[1]) * t / k
                i, j = int((y - win.y0) / RES), int((x - win.x0) / RES)
                if not (0 <= i < win.ny and 0 <= j < win.nx) or not free[l][i, j]:
                    return False
        return True

    def fits_via(q):
        if not maps:
            return False
        win, _, vf = maps
        i, j = int((q[1] - win.y0) / RES), int((q[0] - win.x0) / RES)
        return 0 <= i < win.ny and 0 <= j < win.nx and bool(vf[i, j])

    def offsets(l, pts, c, start):
        w, d = dims(l)
        lp, _ = offset_line(pts, c * d)
        ln, _ = offset_line(pts, -c * d)
        if start:
            lp, ln = [start[0]] + lp, [start[1]] + ln
        return lp, ln

    def best_pair(pl, prev_p, prev_n, V, l, pts, cur):
        wl = dims(pl)[0]
        w = dims(l)[0]
        best = None
        for step in range(24):
            th = math.pi * step / 12
            ux, uy = math.cos(th), math.sin(th)
            vp = (V[0] + pv / 2 * ux, V[1] + pv / 2 * uy)
            vn = (V[0] - pv / 2 * ux, V[1] - pv / 2 * uy)
            for c2 in (cur, -cur):
                lp, ln = offsets(l, pts, c2, None)
                P1 = LineString(prev_p[-2:] + [vp]).buffer(wl / 2, 6)
                N1 = LineString(prev_n[-2:] + [vn]).buffer(wl / 2, 6)
                P2 = LineString([vp] + lp[:2]).buffer(w / 2, 6)
                N2 = LineString([vn] + ln[:2]).buffer(w / 2, 6)
                PV, NV = Point(vp).buffer(vd / 2, 12), Point(vn).buffer(vd / 2, 12)
                score = min(P1.distance(N1) - need_t, P2.distance(N2) - need_t,
                            min(PV.distance(N1), PV.distance(N2), NV.distance(P1), NV.distance(P2), PV.distance(NV)) - need_v)
                jog = math.dist(prev_p[-1], vp) + math.dist(vp, lp[0]) + math.dist(prev_n[-1], vn) + math.dist(vn, ln[0])
                key = (min(score, 0.0), -jog)
                if best is None or key > best[0]:
                    best = (key, vp, vn, c2)
        return best

    lines = []                                      # [layer, centre points, cur, start vias]
    cur = sp
    lines.append([runs[0][0], runs[0][1], cur, None])
    for k in range(1, len(runs)):
        l, pts = runs[k]
        prev = lines[-1]
        options = [(0.0, prev[1], pts)]
        for s in (0.15, 0.3, 0.45, 0.6, 0.8, 1.0, 1.3, 1.6):
            r = cut_back(prev[1], s)                 # change layer earlier: the next layer takes the piece
            if r and len(r[0]) >= 2 and fits_via(r[0][-1]) and fits_line(l, r[1]):
                options.append((s, r[0], r[1][:-1] + pts))
            r = cut_front(pts, s)                    # or later: this layer runs on
            if r and len(r[1]) >= 2 and fits_via(r[1][0]) and fits_line(prev[0], r[0]):
                options.append((s, prev[1] + r[0][1:], r[1]))
        options.sort(key=lambda o: o[0])
        chosen = None
        for s, ppts, npts in options:
            prev_p, prev_n = offsets(prev[0], ppts, prev[2], prev[3])
            b = best_pair(prev[0], prev_p, prev_n, ppts[-1], l, npts, prev[2])
            if chosen is None or b[0] > chosen[0][0]:
                chosen = (b, ppts, npts)
            if b[0][0] >= 0:
                break
        (key, vp, vn, c2), ppts, npts = chosen
        prev[1] = ppts
        lines[-1] = prev
        prev.append((vp, vn))                        # end vias
        cur = c2
        lines.append([l, npts, cur, (vp, vn)])
    tr, vi = [], []
    for ln_ in lines:
        l, pts, c, start = ln_[:4]
        end_v = ln_[4] if len(ln_) > 4 else None
        lp, lnn = offsets(l, pts, c, start)
        if end_v:
            lp, lnn = lp + [end_v[0]], lnn + [end_v[1]]
            vi += [{'net': p, 'x': end_v[0][0], 'y': end_v[0][1], 'dia': vd, 'drill': vh},
                   {'net': n, 'x': end_v[1][0], 'y': end_v[1][1], 'dia': vd, 'drill': vh}]
        w = dims(l)[0]
        for net, line in ((p, lp), (n, lnn)):
            for a, b in zip(line, line[1:]):
                if math.dist(a, b) > 1e-4:
                    tr.append({'net': net, 'layer': l, 'w': w, 'p': [a[0], a[1], b[0], b[1]]})
    return tr, vi, cur


VMERGE = 0.5         # mm: two layer changes closer than this along the path become one via


def geometry(win, path, dfree):
    """grid path -> tracks and vias, straightened"""
    # a straight line longer than one step must keep every cell it crosses this far inside the
    # rules: the line can pass up to half a cell diagonal from the centre it is judged by
    strict = {l: dfree[l] >= RES * 0.72 + EPS for l in dfree}
    runs = []
    for (z, i, j) in path:
        if z % 2:                    # via layer
            continue
        l = ROUTE[z // 2]
        if runs and runs[-1][0] == l:
            runs[-1][1].append((i, j))
        else:
            runs.append([l, [(i, j)]])
    # a short run between two layer changes: one via instead of two (their holes would be too close)
    k = 1
    while k < len(runs) - 1:
        stub, prv, nxt = runs[k], runs[k - 1], runs[k + 1]
        if len(stub[1]) * RES < VMERGE:
            a, b = stub[1][0], stub[1][-1]
            if line_ok(strict[nxt[0]], a, nxt[1][0]):          # the next layer jogs over from the first via
                nxt[1].insert(0, a)
                runs.pop(k)
            elif line_ok(strict[prv[0]], prv[1][-1], b):       # or the previous layer runs on to the second
                prv[1].append(b)
                runs.pop(k)
            else:
                k += 1
                continue
            if runs[k - 1][0] == runs[k][0]:                    # back on the same layer: no via at all
                runs[k - 1][1].extend(runs[k][1][1:])
                runs.pop(k)
            continue
        k += 1
    vias_out = []
    for r in runs[1:]:
        xy = win.xy(*r[1][0])
        if not vias_out or vias_out[-1] != xy:
            vias_out.append(xy)      # one through via, however many layers it crosses here
    segs = []
    for l, pts in runs:
        if len(pts) < 2:
            continue
        keep = [pts[0]]
        k = 0
        while k < len(pts) - 1:
            m = len(pts) - 1
            while m > k + 1 and not line_ok(strict[l], pts[k], pts[m]):
                m -= 1
            keep.append(pts[m])
            k = m
        pts2 = [keep[0]]
        for q in keep[1:]:                    # merge runs that keep the same direction
            if len(pts2) >= 2:
                (a0, b0), (a1, b1) = pts2[-2], pts2[-1]
                if (a1 - a0) * (q[1] - b1) == (b1 - b0) * (q[0] - a1) and \
                        (a1 - a0) * (q[0] - a1) + (b1 - b0) * (q[1] - b1) > 0:
                    pts2[-1] = q
                    continue
            if q != pts2[-1]:
                pts2.append(q)
        for a, b in zip(pts2, pts2[1:]):
            segs.append((l, win.xy(*a), win.xy(*b)))
    return {'segs': segs, 'vias': vias_out}


def line_ok(fr, a, b):
    n = int(max(abs(b[0] - a[0]), abs(b[1] - a[1])) * 3) + 1
    for t in np.linspace(0, 1, n + 1)[1:-1]:
        i = int(round(a[0] + (b[0] - a[0]) * t))
        j = int(round(a[1] + (b[1] - a[1]) * t))
        if not fr[i, j]:
            return False
    return True


def conflicts(net, res, w, vd):
    """movable tracks and vias of other nets that the new route comes too close to"""
    lay_shapes = {l: [] for l in ALL_CU}
    for l, a, b in res['segs']:
        lay_shapes[l].append(LineString([a, b]).buffer(w / 2, 6))
    for x, y in res['vias']:
        for l in ALL_CU:
            lay_shapes[l].append(Point(x, y).buffer(vd / 2, 12))
    lay_u = {l: unary_union(s) for l, s in lay_shapes.items() if s}
    out = []
    for t in tracks:
        if t['net'] == net or t['locked'] or t['layer'] not in lay_u:
            continue
        g = LineString([(t['p'][0], t['p'][1]), (t['p'][2], t['p'][3])]).buffer(t['w'] / 2, 6)
        if g.distance(lay_u[t['layer']]) < max(clearance(net), clearance(t['net'])) - 1e-4:
            out.append(t)
    for v in vias:
        if v['net'] == net or v['locked']:
            continue
        g = Point(v['x'], v['y']).buffer(v['dia'] / 2, 12)
        c = max(clearance(net), clearance(v['net'])) - 1e-4
        if any(g.distance(u) < c for u in lay_u.values()):
            out.append(v)
        else:
            for x, y in res['vias']:            # hole to hole
                if math.hypot(v['x'] - x, v['y'] - y) - (v['drill'] + 0.25) / 2 < H2H:
                    out.append(v)
                    break
    return out


# ----------------------------------------------------------------------------- the queue
def unconnected_nets():
    rpt = open(rpt_path).read()
    nets = []
    for blk in re.split(r'\n(?=\[)', rpt):
        if blk.startswith('[unconnected_items]'):
            for n in re.findall(r'\[([^\]]+)\]', blk.split('\n', 1)[1]):
                if (n != 'GND' or WITH_GND) and n not in nets:
                    nets.append(n)
    return nets


def jobs_for(net):
    """island pairs to join for a net, nearest first (a spanning tree grown from the biggest island)"""
    isl = islands(net)
    if len(isl) < 2:
        return []
    tree = isl[0]['shape']
    rest = isl[1:]
    out = []
    geos_tree = list(isl[0]['geos'])
    while rest:
        k = min(range(len(rest)), key=lambda i: tree.distance(rest[i]['shape']))
        out.append((net, geos_tree, rest[k]['geos'], tree.distance(rest[k]['shape'])))
        geos_tree = geos_tree + rest[k]['geos']
        tree = unary_union([tree, rest[k]['shape']])
        rest.pop(k)
    return out


FIRST = [n for n in opt('--first', '').split(',') if n]
rank = lambda n: FIRST.index(n) if n in FIRST else len(FIRST)
PAIRS = [tuple(kv.split(':')) for kv in opt('--pairs', '').split(',') if ':' in kv]
PAIRNETS = {n for pr in PAIRS for n in pr}
PARTNER.update({a: b for a, b in PAIRS})
PARTNER.update({b: a for a, b in PAIRS})
PGAP.update({n: min(pgeom(n, l)[1] for l in ROUTE) - 0.005 for n in PAIRNETS})
STRIP = [n for n in opt('--strip', '').split(',') if n]
ITERS = int(opt('--iters', 12))
FULLRIP = int(opt('--fullrip', 0))       # nets with at most this many pads are taken up whole when they clash
_npads = {}


def npads(net):
    if net not in _npads:
        _npads[net] = sum(1 for p in pads if p['net'] == net)
    return _npads[net]

GROW = float(opt('--grow', 1.6))
HINC = float(opt('--hinc', 1.5))
MINUTES = float(opt('--minutes', 240))
T0 = __import__('time').time()
def clearance(net):             # noqa: F811  a pair keeps its own (wider) clearance to everything else
    if net in PAIRNETS:
        return max(pgeom(net, l)[2] for l in ROUTE)
    return base_clearance(net)


# nets whose unlocked copper is stripped before anything is routed (a pair routed again, a moved block)
stripped = 0
for net in STRIP:
    for it in [t for t in tracks if t['net'] == net and not t['locked']]:
        tracks.remove(it)
        stripped += 1
    for it in [v for v in vias if v['net'] == net and not v['locked']]:
        vias.remove(it)
        stripped += 1
if STRIP:
    print('stripped %d tracks and vias of %d nets' % (stripped, len(STRIP)))

nets = unconnected_nets()
for n in STRIP + sorted(PAIRNETS):
    if n not in nets and n != 'GND':
        nets.append(n)
nets = [n for n in nets if len(islands(n)) > 1]
nets.sort(key=lambda n: (rank(n), min((j[3] for j in jobs_for(n)), default=0)))
print('%d nets to finish: %s' % (len(nets), ' '.join(nets)))
PROTECT_DYN = set()
_protected = protected


def protected(n):               # noqa: F811
    return n in PROTECT_DYN or _protected(n)


class Movable:
    """nets whose unlocked copper a route may run through, at a price: all but the protected nets,
    GND and the net being routed"""
    def __init__(self, net):
        self.net = net

    def __contains__(self, n):
        return n != self.net and (n != 'GND' or GND_MOVABLE) and not protected(n)


def add(net, res, w, vd, vh, fresh):
    for l, a, b in res['segs']:
        t = {'net': net, 'layer': l, 'w': w, 'p': [a[0], a[1], b[0], b[1]], 'locked': False, 'src': 'new'}
        tracks.append(t)
        fresh.append(t)
    for x, y in res['vias']:
        v = {'net': net, 'x': x, 'y': y, 'dia': vd, 'drill': vh, 'locked': False, 'src': 'new'}
        vias.append(v)
        fresh.append(v)


def isl_key(geos):
    return tuple(sorted((l, k, str(g)[:80]) for l, k, g in geos))[:6]


def join(net, fresh, soft_ok=True, limit=40):
    """join the islands of a net one by one; False when one of them cannot be reached (for GND the
    others are still tried: its islands are separate pads, one walled in says nothing of the next)"""
    bad = set()
    for _ in range(limit):
        jobs = [j for j in jobs_for(net) if isl_key(j[2]) not in bad]
        if net == 'GND':            # only pads that hang loose; stray bits of pour are the pours' business
            jobs = [j for j in jobs if any(k in ('rect', 'circ') for l, k, g in j[2])]
            if GND_PADS:            # and only the ones named (the DRC's list)
                jobs = [j for j in jobs if any(k == 'rect' and g[0] <= x <= g[2] and g[1] <= y <= g[3]
                                               for l, k, g in j[2] for (x, y) in GND_PADS)]
        if not jobs:
            return not bad
        _, ga, gb, _ = jobs[0]
        w = width(net)
        vd, vh = via_size(net)
        res = None
        tries = [(w, vd, vh, 6, None), (w, vd, vh, 20, None),
                 (max(0.15, min(w, 0.2)), min(vd, 0.5), min(vh, 0.25), 20, None)]
        if soft_ok:
            tries.append((max(0.15, min(w, 0.2)), min(vd, 0.5), min(vh, 0.25), 20, Movable(net)))
        if any(fnmatch.fnmatchcase(net, pat) for pat in WIDE):
            # the nearest copper of the other island may be walled in (a bus between two others on an
            # inner layer): look over the whole board for a place to join it
            tries.append((w, vd, vh, 200, None))
        for ww, vvd, vvh, margin, soft in tries:
            res, why = route(net, ga, gb, ww, vvd, vvh, margin, soft=soft)
            if res:
                break
        if not res:
            print('  FAILED %-14s %s' % (net, why))
            if net == 'GND':
                bad.add(isl_key(gb))
                continue
            return False
        add(net, res, ww, vvd, vvh, fresh)
    return False


def shape_of(it):
    if 'layer' in it:
        return LineString([(it['p'][0], it['p'][1]), (it['p'][2], it['p'][3])]).buffer(it['w'] / 2, 6)
    return Point(it['x'], it['y']).buffer(it['dia'] / 2, 12)


def layers_of(it):
    return {it['layer']} if 'layer' in it else set(ALL_CU)


def overlaps(fresh):
    """(a, b, spot, layers): a fresh item too close to a movable item of another net"""
    from shapely.strtree import STRtree
    from shapely.ops import nearest_points
    here = {id(t) for t in tracks} | {id(v) for v in vias}
    cand = [it for it in tracks + vias if not it['locked'] and (it['net'] != 'GND' or GND_MOVABLE)
            and not protected(it['net'])]
    cand += [it for it in fresh if id(it) in here and protected(it['net'])]
    shp = [shape_of(it) for it in cand]
    tree = STRtree(shp)
    out, seen = [], set()
    for a in fresh:
        if id(a) not in here:
            continue
        sa, la = shape_of(a), layers_of(a)
        for k in tree.query(sa.buffer(0.5)):
            b = cand[k]
            if b is a or b['net'] == a['net'] or PARTNER.get(a['net']) == b['net'] or not (la & layers_of(b)):
                continue
            key = tuple(sorted((id(a), id(b))))
            if key in seen:
                continue
            clash = sa.distance(shp[k]) < max(clearance(a['net']), clearance(b['net'])) - 1e-4
            if not clash and 'layer' not in a and 'layer' not in b:
                clash = math.hypot(a['x'] - b['x'], a['y'] - b['y']) - (a['drill'] + b['drill']) / 2 < H2H - 1e-4
            if clash:
                seen.add(key)
                pa, pb = nearest_points(sa, shp[k])
                out.append((a, b, ((pa.x + pb.x) / 2, (pa.y + pb.y) / 2), sorted(la & layers_of(b))))
    return out


def take_up(it):
    (tracks if 'layer' in it else vias).remove(it)


# ---------------------------------------------------------------- 1. the pairs, before anything else
PAIR_GONE = set()
for p, n in PAIRS:
    fresh = []
    # join each half's own islands until two are left (the far ends of the pair)
    for net in (p, n):
        while len(islands(net)) > 2:
            jobs = jobs_for(net)
            _, ga, gb, _ = min(jobs, key=lambda j: j[3])
            res = None
            for margin in (6, 20):
                res, why = route(net, ga, gb, width(net), *via_size(net), margin)
                if res:
                    break
            if not res:
                break
            add(net, res, width(net), *via_size(net), fresh)
    ip, iN = islands(p), islands(n)
    if len(ip) != 2 or len(iN) != 2:
        print('  PAIR %s/%s: %d and %d islands, not two each; routed as single nets' % (p, n, len(ip), len(iN)))
        continue
    from shapely.ops import nearest_points
    # which N island sits at which end
    if ip[0]['shape'].distance(iN[0]['shape']) + ip[1]['shape'].distance(iN[1]['shape']) > \
            ip[0]['shape'].distance(iN[1]['shape']) + ip[1]['shape'].distance(iN[0]['shape']):
        iN = [iN[1], iN[0]]
    ends = []
    for k in (0, 1):
        a = nearest_points(ip[k]['shape'], ip[1 - k]['shape'])[0]
        b = nearest_points(iN[k]['shape'], iN[1 - k]['shape'])[0]
        ends.append(((a.x + b.x) / 2, (a.y + b.y) / 2, (a.x, a.y), (b.x, b.y)))
    axes = tuple((e[2][0] - e[3][0], e[2][1] - e[3][1]) for e in ends)
    # an end whose two pads sit apart (a switch with P on one side and N on the other) has no side to
    # keep: its stubs go round the part either way
    split_a, split_b = (math.hypot(*a) > 1.5 for a in axes)
    split = split_a or split_b
    # the layers the pair may start on at each end: those of the pads there (all, for through-hole pads)
    end_layers = []
    for k in (0, 1):
        ls = {l for isl in (ip[k], iN[k]) for (l, kind, g) in isl['geos'] if kind in ('rect', 'circ') and l in ROUTE}
        end_layers.append(ls or set(ROUTE))
    def end_dir(segs, first):
        """direction of travel over the first (or last) millimetre of a centre line"""
        pts = [segs[0][1]] + [s[2] for s in segs] if first else [segs[-1][2]] + [s[1] for s in reversed(segs)]
        o, run = pts[0], 0.0
        for q in pts[1:]:
            run = math.dist(o, q)
            if run >= 1.0:
                break
        d = (q[0] - o[0], q[1] - o[1]) if first else (o[0] - q[0], o[1] - q[1])
        L = math.hypot(*d) or 1e-9
        return d[0] / L, d[1] / L

    def sides(g):
        """p's side at the start (from the pads there) and whether the far end then needs a crossover"""
        (dx, dy), (ex, ey) = end_dir(g['segs'], True), end_dir(g['segs'], False)
        pa, na = ends[0][2], ends[0][3]
        pb, nb = ends[1][2], ends[1][3]
        s0 = 1 if dx * (pa[1] - na[1]) - dy * (pa[0] - na[0]) >= 0 else -1
        s1 = 1 if ex * (pb[1] - nb[1]) - ey * (pb[0] - nb[0]) >= 0 else -1
        if split_b:                     # nothing to match at the far end
            return s0, False
        if split_a:                     # nothing to match at the start: start on whichever side the far end wants
            return (s0 if band_tracks(p, n, g, s0)[2] == s1 else -s0), False
        return s0, band_tracks(p, n, g, s0)[2] != s1

    res, why = None, None
    for margin, soft in ((8, None), (20, None), (20, Movable('__pair__'))):
        cands, why = route_band(p, n, ends[0][:2], ends[1][:2], margin, soft, None if split else axes, end_layers)
        if cands and split:
            cands = [(cands, 0.0)]
        if cands:
            if '--debug-pairs' in opts:
                for g, cst in cands:
                    print('    candidate %s: cost %.0f, %.1f mm, %d vias, crossover %s' % (
                        p, cst, sum(math.dist(a, b) for _, a, b in g['segs']), len(g['vias']), sides(g)[1]))
            # the cheapest centre line that keeps P on one side; a crossover only when nothing else routes
            ok = [c for c in cands if not sides(c[0])[1]]
            res = (ok or cands)[0][0]
            break
    if not res:
        print('  PAIR %s/%s FAILED: %s' % (p, n, why))
        continue
    sp, twist = sides(res)
    trs, vis, _ = band_tracks(p, n, res, sp)
    for t in trs:
        t.update({'locked': False, 'src': 'new'})
        tracks.append(t)
        fresh.append(t)
    for v in vis:
        v.update({'locked': False, 'src': 'new'})
        vias.append(v)
        fresh.append(v)
    PROTECT_DYN.update((p, n))
    ov = overlaps(fresh)
    gone = sorted({b['net'] for a, b, _, _ in ov})
    for a, b, spot, lays in ov:
        if b in tracks or b in vias:
            take_up(b)
    ok = join(p, fresh) & join(n, fresh)
    # the stubs from the pads may have gone through other nets' copper (the soft try): take that up too
    ov = overlaps(fresh)
    gone = sorted(set(gone) | {b['net'] for a, b, _, _ in ov})
    for a, b, spot, lays in ov:
        if b in tracks or b in vias:
            take_up(b)
    # the two halves must keep their own gap to each other everywhere (their stubs and vias too)
    close = []
    mine = lambda net: [it for it in tracks + vias if it['net'] == net]
    for a in mine(p):
        sa, la = shape_of(a), layers_of(a)
        for b in mine(n):
            if la & layers_of(b):
                need = PGAP[p] if ('layer' in a and 'layer' in b) else base_clearance(p)
                if sa.distance(shape_of(b)) < need - 0.005:
                    close.append(b)
    if close:
        print('  PAIR %s/%s: %d places closer than the pair gap' % (p, n, len(close)))
    ln = sum(math.dist(a, b) for _, a, b in res['segs'])
    print('  PAIR %s/%s: %.1f mm, %d via pairs%s%s%s' % (p, n, ln, len(vis) // 2,
          '; took up ' + ', '.join(gone) if gone else '', '; ends need a crossover' if twist else '',
          '' if ok else '; a pad could not reach the pair'))
    for g in gone:
        if g not in nets:
            nets.append(g)
        PAIR_GONE.add(g)

# ---------------------------------------------------------------- 2. everything else, negotiated
active = [n for n in nets if n not in PAIRNETS] + [n for n in sorted(PAIRNETS) if len(islands(n)) > 1]
if '--only-pairs' in opts:        # just the pairs, and whatever they pushed out of the way
    active = [n for n in active if n in PAIR_GONE or n in PAIRNETS]
    nets = [n for n in nets if n in PAIR_GONE or n in PAIRNETS]
ONLY = [n for n in opt('--only', '').split(',') if n]
if ONLY:                          # a group of nets at a time (and whatever they push out of the way)
    keep = lambda n: any(fnmatch.fnmatchcase(n, pat) for pat in ONLY) or n in PAIR_GONE
    active = [n for n in active if keep(n)]
    nets = [n for n in nets if keep(n)]
failed = []
touched = set(nets)
for it in range(ITERS):
    PFAC[0] = float(opt('--pen', 4.0)) * GROW ** it
    fresh, failed = [], []
    for net in active:
        if not jobs_for(net):
            continue
        if not join(net, fresh):
            failed.append(net)
    ov = overlaps(fresh)
    if '--clash-log' in opts:     # where the nets still fight, round by round (to see a bottleneck)
        with open(opt('--clash-log', 'clash.jsonl'), 'a') as fh:
            fh.write(json.dumps({'round': it + 1, 'failed': failed,
                                 'clashes': [(a['net'], b['net'], round(sp[0], 2), round(sp[1], 2), ls)
                                             for a, b, sp, ls in ov]}) + '\n')
    last = it == ITERS - 1 or (__import__('time').time() - T0) / 60 > MINUTES
    print('round %d: %d nets, %d new pieces, %d clashes, %d failed%s' %
          (it + 1, len(active), len(fresh), len(ov), len(failed), ' (last)' if last else ''), flush=True)
    if not ov and not failed:
        break
    nxt = set(failed)
    whole = set()
    for a, b, spot, lays in ov:
        bump(spot[0], spot[1], lays, HINC)
        movable = [x for x in (a, b) if not x['locked'] and not protected(x['net'])]
        if last:                                   # no more rounds: only one of the two goes, the newcomer if it can
            movable = movable[:1]
        for x in movable:
            if not last and npads(x['net']) <= FULLRIP:
                whole.add(x['net'])                # a small net is routed again from its pads
            elif x in tracks or x in vias:
                take_up(x)
            nxt.add(x['net'])
    for net in whole:
        for it in [t for t in tracks if t['net'] == net and not t['locked']] + \
                  [v for v in vias if v['net'] == net and not v['locked']]:
            take_up(it)
    touched |= nxt
    if last:
        break
    active = sorted(nxt, key=lambda n: (rank(n), n not in nets, min((j[3] for j in jobs_for(n)), default=0)))

still = [n for n in sorted(touched | PAIRNETS | set(failed)) if len(islands(n)) > 1]
new_tracks = [t for t in tracks if t['src'] == 'new']
new_vias = [v for v in vias if v['src'] == 'new']
kept_t = {(t['net'], t['layer'], tuple(t['p'])) for t in tracks if t['src'] == 'board'}
kept_v = {(v['net'], v['x'], v['y']) for v in vias if v['src'] == 'board'}
gone_tracks = [t for t in D['tracks'] if (t['net'], t['layer'], tuple(t['p'])) not in kept_t]
gone_vias = [v for v in D['vias'] if (v['net'], v['x'], v['y']) not in kept_v]
json.dump({'tracks': [{'net': t['net'], 'layer': t['layer'], 'w': t['w'], 'p': t['p']} for t in new_tracks],
           'vias': [{'net': v['net'], 'x': v['x'], 'y': v['y'], 'dia': v['dia'], 'drill': v['drill']} for v in new_vias],
           'remove_tracks': gone_tracks, 'remove_vias': gone_vias, 'still_open': still},
          open(out_path, 'w'), indent=1)
print('%d new tracks, %d new vias; %d board tracks and %d vias taken up; still open: %s' %
      (len(new_tracks), len(new_vias), len(gone_tracks), len(gone_vias), ' '.join(still) or 'none'))
