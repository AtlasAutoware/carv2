"""Placement without KiCad. Footprint geometry comes from a geometry dump written by build_pcb.py
(courtyard box and pad boxes of every footprint), normalised to rotation 0 on the top side. The
board's layout.py runs against this model exactly as it does inside KiCad, then the automatic
placer fills in the rest. Output: <board>/out/<name>_placement.json, which build_pcb.py applies.

    python3 placer.py drive [--plot out.png] [--win x0 y0 x1 y1]

Geometry conventions (checked against KiCad 10): board-local offset of a pad = R(rot) * local on the
top side and R(rot) * M_y * local on the bottom side, R = counter-clockwise rotation with Y up,
M_y = mirror about the X axis.

Once a board is routed its layout.py sets KEEP_AUTO = True: every automatically placed part then goes
back where the last run put it (out/<name>_placement.json) as long as that spot is still free. Without
it, pinning or moving one part changes the order the placer works in and shuffles dozens of others.
"""
import importlib.util
import json
import math
import os
import sys

from shapely.geometry import Point, box  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def rot(p, deg):
    a = math.radians(deg)
    c, s = round(math.cos(a)), round(math.sin(a))
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def box_rot(b, deg, mirror):
    x0, y0, x1, y1 = b
    pts = [pt((x, y), deg, mirror) for x in (x0, x1) for y in (y0, y1)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def pt(p, deg, mirror):
    """bottom side: KiCad mirrors about the X axis first, then rotates"""
    if mirror:
        p = (p[0], -p[1])
    return rot(p, deg)


def unpt(q, deg, mirror):
    p = rot(q, -deg)
    return (p[0], -p[1]) if mirror else p


def unbox(b, deg, mirror):
    x0, y0, x1, y1 = b
    pts = [(x, y) for x in (x0, x1) for y in (y0, y1)]
    pts = [unpt(p, deg, mirror) for p in pts]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def build_library(geom, parts):
    """footprint id -> {'crt': box, 'pads': [(num, box, drill)]} at rotation 0, top side"""
    lib = {}
    for f in geom['fps']:
        fid = parts[f['ref']]['footprint']
        if fid in lib:
            continue
        cx, cy = f['pos']
        deg, mir = round(f['rot']) % 360, f['side'] == 'B'
        c = f['crt']
        crt = unbox((c[0] - cx, c[1] - cy, c[2] - cx, c[3] - cy), deg, mir)
        pads = []
        for p in f['pads']:
            if p.get('cu') is False and p['drill'] <= 0:
                continue                    # paste-only apertures (TDSON, VSON tabs) are not copper
            b = p['bb']
            pads.append((p['n'], unbox((b[0] - cx, b[1] - cy, b[2] - cx, b[3] - cy), deg, mir), p['drill']))
        lib[fid] = {'crt': crt, 'pads': pads}
    return lib


class Board:
    """The subset of build_pcb's interface that layout.py uses: place, face, anchor_pad, pad_xy, parts."""

    def __init__(self, bdir):
        self.bdir = bdir
        spec = importlib.util.spec_from_file_location('layout', os.path.join(bdir, 'layout.py'))
        self.L = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.L)
        name = self.L.NAME
        self.parts = {p['ref']: p for p in json.load(open(os.path.join(bdir, name + '_parts.json')))['parts']}
        libpath = os.path.join(bdir, 'out', 'fp_lib.json')
        geom_path = os.path.join(bdir, 'out', name + '_geom.json')
        if os.path.exists(geom_path):
            lib = build_library(json.load(open(geom_path)), self.parts)
            old = json.load(open(libpath)) if os.path.exists(libpath) else {}
            old.update(lib)
            json.dump(old, open(libpath, 'w'))
        self.lib = json.load(open(libpath))
        missing = sorted(set(p['footprint'] for p in self.parts.values()) - set(self.lib))
        if missing:
            raise SystemExit('no geometry for ' + ', '.join(missing) + ' (run build_pcb.py once with them)')
        self.W, self.H = self.L.SIZE
        self.pos = {}

    # -- geometry of a placed part
    def g(self, ref):
        return self.lib[self.parts[ref]['footprint']]

    def crt(self, ref, margin=0.0):
        x, y, deg, side = self.pos[ref]
        b = box_rot(self.g(ref)['crt'], deg, side == 'B')
        return (x + b[0] - margin, y + b[1] - margin, x + b[2] + margin, y + b[3] + margin)

    def pads(self, ref):
        x, y, deg, side = self.pos[ref]
        out = []
        for num, b, drill in self.g(ref)['pads']:
            bb = box_rot(b, deg, side == 'B')
            out.append((num, (x + (bb[0] + bb[2]) / 2, y + (bb[1] + bb[3]) / 2),
                        (x + bb[0], y + bb[1], x + bb[2], y + bb[3]), drill))
        return out

    # -- the layout API
    def place(self, ref, x, y, deg=0, side='F'):
        self.pos[ref] = (x, y, round(deg) % 360, side)

    def pad_xy(self, ref, num):
        for n, c, _, _ in self.pads(ref):
            if n == num:
                return c
        raise KeyError(f'{ref} pad {num}')

    def face(self, ref, x, y, pads, direction, side='F'):
        want = {'up': (0, 1), 'down': (0, -1), 'left': (-1, 0), 'right': (1, 0)}[direction]
        best = None
        for deg in (0, 90, 180, 270):
            self.place(ref, x, y, deg, side)
            ps = [self.pad_xy(ref, n) for n in pads]
            mx = sum(p[0] for p in ps) / len(ps) - x
            my = sum(p[1] for p in ps) / len(ps) - y
            score = mx * want[0] + my * want[1]
            if best is None or score > best[0] + 1e-9:
                best = (score, deg)
        self.place(ref, x, y, best[1], side)
        return best[1]

    def anchor_pad(self, ref, num, x, y, deg=None, side='F'):
        if deg is not None:
            self.place(ref, x, y, deg, side)
        px, py = self.pad_xy(ref, num)
        fx, fy, d, s = self.pos[ref]
        self.place(ref, fx + (x - px), fy + (y - py), d, s)

    def centre(self, ref, cx, cy, deg=0, side='F'):
        """place so that the courtyard centre lands on (cx, cy)"""
        self.place(ref, cx, cy, deg, side)
        b = self.crt(ref)
        self.place(ref, cx - ((b[0] + b[2]) / 2 - cx), cy - ((b[1] + b[3]) / 2 - cy), deg, side)

    # -- automatic placement of everything layout.py did not place
    def has_pth(self, ref):
        return any(d > 0 for _, _, _, d in self.pads(ref)) or ref in getattr(self.L, 'THROUGH', ())

    def auto(self, explicit, keep=None):
        """Place every part not in `explicit` next to the pad it shares a net with. `keep` maps refs to their
        {x, y, rot, side} from an earlier run: such a part goes back there first if that spot is still free, so
        re-placing one part of a routed board does not shuffle the rest (the search order depends on what is
        already placed)."""
        L = self.L
        keep = keep or {}
        rails = set(getattr(L, 'RAILS', ()))
        occ = {'F': [], 'B': []}
        holes = []

        margin = getattr(L, 'AUTO_MARGIN', 0.1)          # half the gap left between automatically placed parts
        ring = getattr(L, 'IC_RING', 0.1)                # kept clear around ICs with 20+ pads for their fan-out

        def add(ref, explicit_part=False):
            big = explicit_part and len(self.parts[ref]['pads']) >= 20
            b = self.crt(ref, ring if big else margin)
            side = self.pos[ref][3]
            if self.is_hole(ref):
                holes.append(ref)
                return
            occ[side].append(b + (ref,))
            if self.has_pth(ref):
                occ['B' if side == 'F' else 'F'].append(b + (ref,))
        for r in explicit:
            add(r, True)
        for (side, x0, y0, x1, y1) in getattr(L, 'NO_AUTO', []):
            occ[side].append((x0, y0, x1, y1, 'keepout'))

        def free(b, side):
            if b[0] < 0.5 or b[1] < 0.5 or b[2] > self.W - 0.5 or b[3] > self.H - 0.5:
                return False
            for o in occ[side]:
                if b[0] < o[2] and b[2] > o[0] and b[1] < o[3] and b[3] > o[1]:
                    return False
            for h in holes:
                if self.circle_hits(h, b, 0.1):
                    return False
            return True

        used = {}
        placed = dict.fromkeys(explicit)        # ordered: ties in anchor_for resolve the same way every run

        def anchor_for(ref):
            p = self.parts[ref]
            best = None
            for num, n in p['pads'].items():
                if not n:
                    continue
                for r2 in placed:
                    if r2 == ref:
                        continue
                    for num2, n2 in self.parts[r2]['pads'].items():
                        if n2 == n:
                            w = (0.5 if n == 'GND' else 1) if n in rails else 10
                            if self.parts[r2]['block'] == p['block']:
                                w *= 3
                            if len(self.parts[r2]['pads']) > 4:
                                w *= 2
                            if r2.startswith('U'):
                                w *= 2
                            key = (w, -used.get((r2, num2), 0))
                            if best is None or key > best[0]:
                                best = (key, r2, num2)
            if best:
                used[(best[1], best[2])] = used.get((best[1], best[2]), 0) + 1
            return best

        pending = [r for r in self.parts if r not in placed]
        unplaced = []
        for _ in range(6):
            nxt = []
            for ref in pending:
                k = keep.get(ref)
                if k:
                    self.place(ref, k['x'], k['y'], k['rot'], k['side'])
                    if free(self.crt(ref, margin), k['side']):
                        add(ref)
                        placed[ref] = None
                        continue
                a = anchor_for(ref)
                if a is None:
                    nxt.append(ref)
                    continue
                _, r2, num2 = a
                side = getattr(L, 'SIDE', {}).get(ref) or self.pos[r2][3]
                px, py = self.pad_xy(r2, num2)
                cx, cy = self.pos[r2][0], self.pos[r2][1]
                dx, dy = px - cx, py - cy
                dn = math.hypot(dx, dy) or 1.0
                ux, uy = dx / dn, dy / dn
                done = False
                for rad in [k * 0.5 for k in range(2, 60)]:
                    for k in range(24):
                        ang = math.atan2(uy, ux) + (k // 2) * (math.pi / 12) * (1 if k % 2 == 0 else -1)
                        tx, ty = px + rad * math.cos(ang), py + rad * math.sin(ang)
                        for deg in ((0, 90) if abs(ux) > abs(uy) else (90, 0)):
                            self.place(ref, round(tx * 4) / 4, round(ty * 4) / 4, deg, side)
                            if free(self.crt(ref, margin), side):
                                done = True
                                break
                        if done:
                            break
                    if done:
                        break
                if done:
                    add(ref)
                    placed[ref] = None
                else:
                    nxt.append(ref)
            if not nxt or nxt == pending:
                unplaced = nxt
                break
            pending = nxt
            unplaced = nxt
        for i, ref in enumerate(unplaced):
            self.place(ref, 5 + (i % 20) * 3, -10 - (i // 20) * 3)
        return unplaced

    def is_hole(self, ref):
        return self.parts[ref]['footprint'].startswith('MountingHole:')

    def circle_hits(self, h, b, margin=0.0):
        hb = self.crt(h)
        cx, cy, r = (hb[0] + hb[2]) / 2, (hb[1] + hb[3]) / 2, (hb[2] - hb[0]) / 2 + margin
        nx, ny = min(max(cx, b[0]), b[2]), min(max(cy, b[1]), b[3])
        return math.hypot(nx - cx, ny - cy) < r

    def conflicts(self):
        refs = list(self.pos)
        out = []
        boxes = {r: self.crt(r) for r in refs}
        for i in range(len(refs)):
            for j in range(i + 1, len(refs)):
                a, c = refs[i], refs[j]
                A, C = boxes[a], boxes[c]
                if not (A[0] < C[2] and A[2] > C[0] and A[1] < C[3] and A[3] > C[1]):
                    continue
                ov = (min(A[2], C[2]) - max(A[0], C[0])) * (min(A[3], C[3]) - max(A[1], C[1]))
                hole = [r for r in (a, c) if self.is_hole(r)]
                if hole and len(hole) == 1:
                    h = hole[0]
                    o = c if h == a else a
                    if not self.circle_hits(h, boxes[o]):
                        continue
                sa, sc = self.pos[a][3], self.pos[c][3]
                if sa == sc and ov > 0.02:
                    out.append(('overlap', round(ov, 2), a, c))
                elif sa != sc:
                    for f1, f2 in ((a, c), (c, a)):
                        if not self.has_pth(f1):
                            continue
                        b = boxes[f2]
                        for n, (px, py), _, d in self.pads(f1):
                            if d > 0 and b[0] < px < b[2] and b[1] < py < b[3]:
                                out.append(('hole-under', f1, n, f2))
                                break
        return out


class Copper:
    """Zones, vias and tracks that a layout's copper(B) step adds. Everything is board-local mm.
    Written to out/<name>_copper.json; build_pcb.py turns it into KiCad objects."""

    def __init__(self, B):
        self.B = B
        self.zones, self.vias, self.tracks, self.rules = [], [], [], []
        self._pads = None

    # ---- obstacles
    def pads_all(self):
        """(net, box, drill, side, ref, num) for every pad on the board"""
        if self._pads is None:
            out = []
            for ref in self.B.pos:
                side = self.B.pos[ref][3]
                for n, c, bb, d in self.B.pads(ref):
                    out.append((self.B.parts[ref]['pads'].get(n, ''), bb, d, side, ref, n))
            self._pads = out
        return self._pads

    def via_ok(self, x, y, net, dia, clear=0.2, edge=0.6):
        B = self.B
        r = dia / 2
        if x < edge + r or y < edge + r or x > B.W - edge - r or y > B.H - edge - r:
            return False
        for pnet, bb, d, side, ref, n in self.pads_all():
            m = r + (clear if (pnet != net or d > 0 or not pnet) else 0.1)
            if bb[0] - m < x < bb[2] + m and bb[1] - m < y < bb[3] + m:
                return False
        for v in self.vias:
            if math.hypot(v['x'] - x, v['y'] - y) < r + v['dia'] / 2 + clear - 1e-6:
                return False
        for t in self.tracks:
            if t['net'] == net:
                continue
            for (x0, y0), (x1, y1) in zip(t['pts'], t['pts'][1:]):
                if seg_dist(x, y, x0, y0, x1, y1) < r + t['width'] / 2 + clear - 1e-6:
                    return False
        for ko in self.rules:
            if ko.get('no_vias') and ko['geom'].contains(Point(x, y)):
                return False
        return True

    # ---- items
    def via(self, x, y, net, drill=0.3, dia=0.6, check=True, locked=True):
        if check and not self.via_ok(x, y, net, dia):
            return False
        self.vias.append({'x': round(x, 4), 'y': round(y, 4), 'net': net, 'drill': drill, 'dia': dia, 'locked': locked})
        return True

    def via_grid(self, net, region, pitch, drill=0.3, dia=0.6, stagger=False):
        """fill a shapely region with vias where nothing is in the way; returns the count"""
        x0, y0, x1, y1 = region.bounds
        n, row = 0, 0
        y = y0 + dia / 2
        while y <= y1 - dia / 2 + 1e-9:
            x = x0 + dia / 2 + (pitch / 2 if stagger and row % 2 else 0)
            while x <= x1 - dia / 2 + 1e-9:
                if region.contains(Point(x, y)) and self.via(x, y, net, drill, dia):
                    n += 1
                x += pitch
            y += pitch
            row += 1
        return n

    def track(self, pts, width, layer, net, locked=True):
        self.tracks.append({'pts': [(round(a, 4), round(b, 4)) for a, b in pts], 'width': width, 'layer': layer,
                            'net': net, 'locked': locked})

    def zone(self, name, net, layer, geom, priority=10, connect='full', clearance=0.25, min_width=0.25,
             dsn=True, thermal_gap=0.3, spoke=0.5):
        """geom: shapely Polygon/MultiPolygon. dsn=False keeps it out of the autorouter's view (fills added after routing)."""
        polys = [geom] if geom.geom_type == 'Polygon' else list(geom.geoms)
        rings = [[list(p.exterior.coords)[:-1]] + [list(h.coords)[:-1] for h in p.interiors] for p in polys]
        self.zones.append({'name': name, 'net': net, 'layer': layer, 'priority': priority, 'rings': rings,
                           'connect': connect, 'clearance': clearance, 'min_width': min_width, 'dsn': dsn,
                           'thermal_gap': thermal_gap, 'spoke': spoke})

    def keepout(self, name, layers, geom, tracks=True, vias=False, zones=False, dsn_only=True):
        """rule area. dsn_only: used only while autorouting (removed afterwards)"""
        rings = [[list(geom.exterior.coords)[:-1]] + [list(h.coords)[:-1] for h in geom.interiors]]
        self.rules.append({'name': name, 'layers': layers, 'rings': rings, 'no_tracks': tracks, 'no_vias': vias,
                           'no_zones': zones, 'dsn_only': dsn_only, 'geom': geom})

    def pad_box(self, ref, num, grow=0.0):
        bs = [bb for n, c, bb, d in self.B.pads(ref) if n == num]
        if not bs:
            raise KeyError(f'{ref} pad {num}')
        x0 = min(b[0] for b in bs) - grow
        y0 = min(b[1] for b in bs) - grow
        x1 = max(b[2] for b in bs) + grow
        y1 = max(b[3] for b in bs) + grow
        return box(x0, y0, x1, y1)

    def dump(self, path):
        rules = [{k: v for k, v in r.items() if k != 'geom'} for r in self.rules]
        json.dump({'zones': self.zones, 'vias': self.vias, 'tracks': self.tracks, 'rules': rules}, open(path, 'w'))


def seg_dist(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((px - x0) * dx + (py - y0) * dy) / L2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def plot(B, path, win=None):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Circle
    W, H = B.W, B.H
    win = win or (0, 0, W, H)
    NETC = {'GND': '#9e9e9e', 'VM': '#e53935', 'BATP': '#fb8c00', 'SW_IN': '#f4511e', 'BATN': '#6d4c41',
            'VSYS': '#8e24aa', '+3V3': '#1e88e5', '+5V': '#00897b', 'SERVO_V': '#c0ca33', 'PHA': '#43a047',
            'PHB': '#43a047', 'PHC': '#43a047', 'BMS_RSN': '#795548', 'FET_MID': '#a1887f', 'PPHV': '#ab47bc',
            'VBUS_C': '#ce93d8', 'CHG_PMID': '#f06292', 'CHG_SW1': '#ffb300', 'CHG_SW2': '#ffb300'}
    pal = ['#ffebee', '#e3f2fd', '#e8f5e9', '#fff3e0', '#f3e5f5', '#e0f7fa', '#fffde7', '#fce4ec', '#ede7f6', '#f1f8e9', '#eceff1']
    blk = {}
    for p in B.parts.values():
        blk.setdefault(p['block'], pal[len(blk) % len(pal)])
    ww, wh = win[2] - win[0], win[3] - win[1]
    if ww / wh > 1.2:
        sc = 20.0 / ww
        fig, axs = plt.subplots(2, 1, figsize=(ww * sc + 1.0, 2 * wh * sc + 1.2), dpi=120)
    else:
        sc = min(22.0 / ww, 14.0 / wh)
        fig, axs = plt.subplots(1, 2, figsize=(2 * ww * sc + 1.5, wh * sc + 1.0), dpi=110)
    for ax, side, title in ((axs[0], 'F', 'TOP'), (axs[1], 'B', 'BOTTOM (seen from the top)')):
        ax.add_patch(Rectangle((0, 0), W, H, fill=False, lw=1.2, ec='k'))
        for ref, (x, y, d, s) in B.pos.items():
            c = B.crt(ref)
            if s == side:
                ax.add_patch(Rectangle((c[0], c[1]), c[2] - c[0], c[3] - c[1], fc=blk[B.parts[ref]['block']], ec='#555', lw=0.4))
            for n, (px, py), bb, drill in B.pads(ref):
                if s != side and drill <= 0:
                    continue
                net = B.parts[ref]['pads'].get(n, '')
                col = NETC.get(net, '#90a4ae' if net else '#ffffff')
                if drill > 0:
                    ax.add_patch(Circle((px, py), max(bb[2] - bb[0], bb[3] - bb[1]) / 2, fc=col, ec='k', lw=0.3, alpha=0.8))
                else:
                    ax.add_patch(Rectangle((bb[0], bb[1]), bb[2] - bb[0], bb[3] - bb[1], fc=col, ec='k', lw=0.2))
            if s == side:
                w = c[2] - c[0]
                ax.text((c[0] + c[2]) / 2, (c[1] + c[3]) / 2, ref, fontsize=3.2 if w < 3 else 4.5 if w < 8 else 6, ha='center', va='center', clip_on=True)
        ax.set_xlim(win[0] - 1, win[2] + 1)
        ax.set_ylim(win[1] - 1, win[3] + 1)
        ax.set_aspect('equal')
        ax.set_title(f'{B.L.NAME} {title}', fontsize=9)
        ax.grid(True, lw=0.2, alpha=0.5)
        ax.set_xticks(range(int(win[0]) // 5 * 5, int(win[2]) + 1, 5 if win[2] - win[0] < 70 else 10))
        ax.set_yticks(range(int(win[1]) // 5 * 5, int(win[3]) + 1, 5 if win[3] - win[1] < 70 else 10))
        ax.tick_params(labelsize=6)
    fig.tight_layout()
    fig.savefig(path)


def main():
    board = sys.argv[1]
    bdir = os.path.abspath(os.path.join(HERE, '..', board))
    B = Board(bdir)
    B.L.place_all(B)
    explicit = list(B.L.placed_refs())
    keep = None
    ppath = os.path.join(bdir, 'out', B.L.NAME + '_placement.json')
    if getattr(B.L, 'KEEP_AUTO', False) and os.path.exists(ppath):
        keep = {r: v for r, v in json.load(open(ppath)).items() if r not in explicit}
    unplaced = B.auto(explicit, keep)
    out = {r: {'x': round(v[0], 4), 'y': round(v[1], 4), 'rot': v[2], 'side': v[3]} for r, v in B.pos.items()}
    json.dump(out, open(os.path.join(bdir, 'out', B.L.NAME + '_placement.json'), 'w'), indent=0)
    cf = B.conflicts()
    for c in sorted(cf, key=str):
        print(*c)
    C = None
    if hasattr(B.L, 'copper'):
        C = Copper(B)
        B.L.copper(B, C)
        C.dump(os.path.join(bdir, 'out', B.L.NAME + '_copper.json'))
        print('copper:', len(C.zones), 'zones,', len(C.vias), 'vias,', len(C.tracks), 'tracks,', len(C.rules), 'rule areas')
    B.copper = C
    print(len(B.pos), 'placed,', len(explicit), 'explicit,', len(unplaced), 'unplaced', unplaced, len(cf), 'conflicts')
    args = sys.argv[2:]
    if '--plot' in args:
        i = args.index('--plot')
        win = None
        if '--win' in args:
            j = args.index('--win')
            win = tuple(float(v) for v in args[j + 1:j + 5])
        plot(B, args[i + 1], win)
        print('plot', args[i + 1])


if __name__ == '__main__':
    main()
