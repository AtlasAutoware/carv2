"""Last steps on a routed board (KiCad Python): 3D model fixes, GND stitching vias between the outer
GND fills and the inner planes, silkscreen cleanup, refill, save.

    flatpak run --command=python3 --filesystem=home org.kicad.KiCad finish_pcb.py drive [--no-stitch] [--no-silk]

Stitching: a via goes on a 3 mm grid wherever a 0.6 mm GND via plus 0.25 mm fits inside the GND
copper of every layer (so it touches no other net anywhere) and keeps 1 mm from other holes
and 0.3 mm from every pad. Silkscreen: a reference that lands on a pad, another reference or
footprint outline, or the board edge is tried at the four sides of its footprint; if none is
free it moves to the fab layer. Outline strokes of a footprint that run over another footprint's
pads are removed (the fab would clip them anyway).
"""
import math
import os
import sys

import pcbnew
from pcbnew import VECTOR2I, FromMM as MM, ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
bdir = os.path.abspath(os.path.join(HERE, '..', sys.argv[1]))
name = [f for f in os.listdir(bdir) if f.endswith('.kicad_pcb')][0][:-len('.kicad_pcb')]
path = os.path.join(bdir, name + '.kicad_pcb')
args = sys.argv[2:]
b = pcbnew.LoadBoard(path)
filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())

CU = {b.GetLayerName(l): l for l in b.GetEnabledLayers().CuStack()}     # every copper layer the board has


# ----------------------------------------------------------------------------- stitching vias
def gnd_fills():
    """per copper layer: the filled GND polygons"""
    out = {}
    for z in b.Zones():
        if z.GetNetname() != 'GND' or z.GetIsRuleArea():
            continue
        for lay in z.GetLayerSet().Seq():
            if lay in CU.values():
                out.setdefault(lay, []).append(z.GetFilledPolysList(lay))
    return out


def inside(polys, x, y, r):
    """(x, y) and a ring of 16 points at radius r all lie in one of the polygon sets"""
    pts = [VECTOR2I(x, y)] + [VECTOR2I(int(x + r * math.cos(k * math.pi / 8)), int(y + r * math.sin(k * math.pi / 8)))
                              for k in range(16)]
    for ps in polys:
        if all(ps.Contains(p) for p in pts):
            return True
    return False


def stitch(pitch=3.0, dia=0.6, drill=0.3, margin=0.25, hole_gap=1.0, pad_gap=0.3):
    fills = gnd_fills()
    if len(fills) < len(CU):
        print('stitch: GND is not on every copper layer here, skipped')
        return 0
    gnd = b.FindNet('GND')
    holes = [(v.GetPosition().x, v.GetPosition().y) for v in b.GetTracks() if v.Type() == pcbnew.PCB_VIA_T]
    pads = []
    for fp in b.GetFootprints():
        for pd in fp.Pads():
            bb = pd.GetBoundingBox()
            pads.append((bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()))
            if pd.GetDrillSize().x > 0:
                holes.append((pd.GetPosition().x, pd.GetPosition().y))
    bb = b.GetBoardEdgesBoundingBox()
    r = MM(dia / 2 + margin)
    n = 0
    step = MM(pitch)
    y = bb.GetTop() + step // 2
    while y < bb.GetBottom():
        x = bb.GetLeft() + step // 2
        while x < bb.GetRight():
            ok = all(inside(fills[lay], x, y, r) for lay in CU.values())
            if ok:
                ok = all(math.hypot(x - hx, y - hy) >= MM(hole_gap) for hx, hy in holes)
            if ok:
                m = MM(dia / 2 + pad_gap)
                ok = not any(x0 - m < x < x1 + m and y0 - m < y < y1 + m for x0, y0, x1, y1 in pads)
            if ok:
                v = pcbnew.PCB_VIA(b)
                v.SetPosition(VECTOR2I(x, y))
                v.SetViaType(pcbnew.VIATYPE_THROUGH)
                v.SetWidth(MM(dia))
                v.SetDrill(MM(drill))
                v.SetNet(gnd)
                b.Add(v)
                holes.append((x, y))
                n += 1
            x += step
        y += step
    return n


# ----------------------------------------------------------------------------- silkscreen
SILK = (pcbnew.F_SilkS, pcbnew.B_SilkS)


def rect(bb, grow=0):
    return (bb.GetLeft() - grow, bb.GetTop() - grow, bb.GetRight() + grow, bb.GetBottom() + grow)


def hit(a, c):
    return a[0] < c[2] and a[2] > c[0] and a[1] < c[3] and a[3] > c[1]


def silk():
    edge = rect(b.GetBoardEdgesBoundingBox(), -MM(0.4))
    pads = {lay: [] for lay in SILK}                  # mask openings per side, with the owning footprint
    outl = {lay: [] for lay in SILK}                  # footprint outline strokes per side
    for fp in b.GetFootprints():
        for pd in fp.Pads():
            for sl, cl in ((pcbnew.F_SilkS, pcbnew.F_Mask), (pcbnew.B_SilkS, pcbnew.B_Mask)):
                if pd.IsOnLayer(cl):
                    pads[sl].append((rect(pd.GetBoundingBox(), MM(0.1)), fp.GetReference()))
        for it in fp.GraphicalItems():
            if it.GetLayer() in SILK and it.Type() != pcbnew.PCB_TEXT_T:
                outl[it.GetLayer()].append((rect(it.GetBoundingBox(), MM(0.05)), fp.GetReference(), it))
    # 1) outline strokes over another footprint's pads: remove
    cut = 0
    for lay in SILK:
        keep = []
        for r_, ref, it in outl[lay]:
            if any(hit(r_, p) for p, pref in pads[lay] if pref != ref):
                b.FindFootprintByReference(ref).Remove(it)
                cut += 1
            else:
                keep.append((r_, ref, it))
        outl[lay] = keep
    # 2) references
    placed = {lay: [] for lay in SILK}
    moved = fab = 0
    def fbox(f):
        try:
            return f.GetBoundingBox(False)
        except TypeError:
            return f.GetBoundingBox(False, False)
    fps = sorted(b.GetFootprints(), key=lambda f: -fbox(f).GetArea())
    for fp in fps:
        rf = fp.Reference()
        lay = rf.GetLayer()
        if lay not in SILK or not rf.IsVisible():
            continue
        ref = fp.GetReference()

        def free(rr):
            if not (edge[0] <= rr[0] and rr[2] <= edge[2] and edge[1] <= rr[1] and rr[3] <= edge[3]):
                return False
            if any(hit(rr, p) for p, pref in pads[lay]):
                return False
            if any(hit(rr, o) for o, oref, it in outl[lay] if oref != ref):
                return False
            return not any(hit(rr, q) for q in placed[lay])

        cur = rect(rf.GetBoundingBox(), MM(0.05))
        if free(cur):
            placed[lay].append(cur)
            continue
        crt = fp.GetCourtyard(pcbnew.F_CrtYd if lay == pcbnew.F_SilkS else pcbnew.B_CrtYd)
        cb = crt.BBox() if crt.OutlineCount() else fbox(fp)
        cx, cy = cb.Centre().x, cb.Centre().y
        w, h = cur[2] - cur[0], cur[3] - cur[1]
        cands = [(cx, cb.GetTop() - h // 2 - MM(0.15)), (cx, cb.GetBottom() + h // 2 + MM(0.15)),
                 (cb.GetLeft() - w // 2 - MM(0.15), cy), (cb.GetRight() + w // 2 + MM(0.15), cy)]
        done = False
        for (px, py) in cands:
            rf.SetPosition(VECTOR2I(int(px), int(py)))
            rr = rect(rf.GetBoundingBox(), MM(0.05))
            if free(rr):
                placed[lay].append(rr)
                moved += 1
                done = True
                break
        if not done:
            rf.SetLayer(pcbnew.F_Fab if lay == pcbnew.F_SilkS else pcbnew.B_Fab)
            fab += 1
    return cut, moved, fab


# ----------------------------------------------------------------------------- 3D models
# Parts whose land pattern comes from a library footprint of a shorter package. The pads suit the part;
# only the 3D model (renders, STEP export, height checks) needs the right body.
MODEL_BY_MPN = {
    # Panasonic 10 x 12.5 mm can (12.8 mm max) on the Nichicon 10 x 10 land pattern, which covers its terminals
    'EEH-ZU1V331P': '${KICAD10_3DMODEL_DIR}/Capacitor_SMD.3dshapes/CP_Elec_10x12.5.step',
}


def models():
    n = 0
    for fp in b.GetFootprints():
        new = MODEL_BY_MPN.get(fp.GetFieldText('MPN') if fp.HasField('MPN') else '')
        if new and len(fp.Models()):
            fp.Models()[0].m_Filename = new
            n += 1
    return n


print('3D models swapped:', models())
if '--no-stitch' not in args:
    print('stitching vias:', stitch())
if '--no-silk' not in args:
    print('silk: outline strokes removed %d, references moved %d, references to fab %d' % silk())
filler.Fill(b.Zones())
pcbnew.SaveBoard(path, b)
print('saved', path)
