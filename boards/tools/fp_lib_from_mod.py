"""Write <board>/out/fp_lib.json for placer.py straight from the .kicad_mod files, without KiCad.

    python3 fp_lib_from_mod.py power      (KICAD_FP_DIR = the stock footprint folder, as for fpinfo.py)

placer.py normally takes footprint geometry from the geometry dump that build_pcb.py writes inside KiCad, which
needs a placement first. This bootstraps a new board: courtyard box and pad boxes of every footprint at rotation 0
on the top side, in board-local orientation (Y up), the same convention build_library() in placer.py produces.
Entries already in fp_lib.json (from a real KiCad dump) are kept unless --force is given.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexp import parse, find, find1, uq  # noqa: E402
from fpinfo import FPDIR, LOCAL  # noqa: E402


def geometry(fpid):
    lib, name = fpid.split(':')
    path = os.path.join(LOCAL.get(lib, os.path.join(FPDIR, lib + '.pretty')), name + '.kicad_mod')
    root = parse(open(path).read())[0]
    pads = []
    for p in find(root, 'pad'):
        at = find1(p, 'at')
        sz = find1(p, 'size')
        x, y = float(at[1]), float(at[2])
        rot = float(at[3]) if len(at) > 3 else 0.0
        w, h = float(sz[1]), float(sz[2])
        if round(rot) % 180 == 90:
            w, h = h, w
        dr = find1(p, 'drill')
        drill = 0.0
        if dr is not None:
            vals = [v for v in dr[1:] if not isinstance(v, list) and v != 'oval']
            drill = float(vals[0]) if vals else 0.0
        layers = find1(p, 'layers')
        cu = any('Cu' in uq(l) for l in layers[1:]) if layers else True
        if not cu and drill <= 0:
            continue
        pads.append([uq(p[1]), [x - w / 2, -(y + h / 2), x + w / 2, -(y - h / 2)], drill])
    xs, ys = [], []
    for kind in ('fp_line', 'fp_rect', 'fp_circle', 'fp_poly', 'fp_arc'):
        for g in find(root, kind):
            lay = find1(g, 'layer')
            if not lay or uq(lay[1]) != 'F.CrtYd':
                continue
            if kind == 'fp_circle':
                c, e = find1(g, 'center'), find1(g, 'end')
                cx, cy = float(c[1]), float(c[2])
                r = math.hypot(float(e[1]) - cx, float(e[2]) - cy)
                xs += [cx - r, cx + r]
                ys += [cy - r, cy + r]
                continue
            pts = []
            for key in ('start', 'end', 'mid'):
                e = find1(g, key)
                if e:
                    pts.append((float(e[1]), float(e[2])))
            pl = find1(g, 'pts')
            if pl:
                pts += [(float(e[1]), float(e[2])) for e in find(pl, 'xy')]
            xs += [p[0] for p in pts]
            ys += [p[1] for p in pts]
    if xs:
        crt = [min(xs), -max(ys), max(xs), -min(ys)]
    else:
        bx = [b for _, b, _ in pads]
        crt = [min(b[0] for b in bx) - 0.25, min(b[1] for b in bx) - 0.25,
               max(b[2] for b in bx) + 0.25, max(b[3] for b in bx) + 0.25]
    return {'crt': crt, 'pads': pads}


def main():
    board = sys.argv[1]
    force = '--force' in sys.argv
    bdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', board)
    name = [f for f in os.listdir(bdir) if f.endswith('_parts.json')][0]
    parts = json.load(open(os.path.join(bdir, name)))['parts']
    os.makedirs(os.path.join(bdir, 'out'), exist_ok=True)
    path = os.path.join(bdir, 'out', 'fp_lib.json')
    lib = json.load(open(path)) if os.path.exists(path) else {}
    n = 0
    for fid in sorted(set(p['footprint'] for p in parts)):
        if fid in lib and not force:
            continue
        lib[fid] = geometry(fid)
        n += 1
    json.dump(lib, open(path, 'w'))
    print(f'{n} footprints written to {path} ({len(lib)} in total)')


if __name__ == '__main__':
    main()
