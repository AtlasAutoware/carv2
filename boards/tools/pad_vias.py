"""After routing: give unconnected surface pads a via into their plane (KiCad Python).

    flatpak run --command=python3 --filesystem=home org.kicad.KiCad pad_vias.py drive [--via 0.6/0.3] [--track 0.25] [NET ...]
    ... pad_vias.py brain --ep U1301.49,U1201.13 [--pitch 1.0]

--pads REF.NUM,...: these pads instead of the DRC report's list (a pad whose only link is a stray
piece of pour shows up in the report as the pour, not as the pad).

--through-pours: a via may also go into an outer-layer pour of another net (the pour flows around
it on the refill); for GND pads that sit inside a power pour, like the input caps of a converter.

--zone-islands: instead, a via into every small piece of the nets' pours that no via or through-hole
pad reaches (a sliver cut off by a row of pads), where one fits and lands in the net's fill on another
layer too.

--ep: instead, a grid of vias inside the listed exposed pads (the thermal and ground vias of a QFN's
centre pad), each one only where it clears every other net on every layer and lands in a plane of
the pad's net.

Reads <board>/drc.rpt (run drc-<board> first) and takes every surface pad of the given nets (GND by
default) that the report lists as unconnected. Next to each it tries a through via, closest first,
joined to the pad by a short track on the pad's layer. A spot counts only if the via and the track
clear every other net on every layer (outer-layer pours included; an inner plane of another net just
gets an antipad), keep hole-to-hole clearance and the board edge, and the via lands inside a fill of
the pad's own net on some inner layer, so it really reaches the plane. Refills and saves.
"""
import math
import os
import re
import sys

import pcbnew
from pcbnew import VECTOR2I, FromMM as MM, ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[1:]
board = argv.pop(0)
via_d, via_h, track_w = 0.6, 0.3, 0.25
nets = []
eps, ep_pitch = [], 1.0
force = []
through_pours = False
while argv:
    a = argv.pop(0)
    if a == '--via':
        via_d, via_h = (float(v) for v in argv.pop(0).split('/'))
    elif a == '--track':
        track_w = float(argv.pop(0))
    elif a == '--ep':
        eps = [tuple(e.split('.')) for e in argv.pop(0).split(',')]
    elif a == '--pitch':
        ep_pitch = float(argv.pop(0))
    elif a == '--through-pours':
        through_pours = True
    elif a == '--zone-islands':
        pass
    elif a == '--pads':
        force = [tuple(e.split('.')) for e in argv.pop(0).split(',')]
    else:
        nets.append(a)
nets = set(nets or ['GND'])

bdir = os.path.abspath(os.path.join(HERE, '..', board))
name = [f for f in os.listdir(bdir) if f.endswith('.kicad_pcb')][0][:-len('.kicad_pcb')]
path = os.path.join(bdir, name + '.kicad_pcb')
b = pcbnew.LoadBoard(path)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())

CLEAR = 0.2          # mm, at least this between the new copper and any other net
HOLE_GAP = 0.25      # mm, hole to hole
EDGE = 0.5           # mm, via copper to the board edge
OUTER = (pcbnew.F_Cu, pcbnew.B_Cu)
cu_layers = [l for l in b.GetEnabledLayers().CuStack()]
inner = [l for l in cu_layers if l not in OUTER]

# ------------------------------------------------------------------ which pads
rpt = open(os.path.join(bdir, 'drc.rpt')).read()
want = []
for blk in re.split(r'\n(?=\[)', rpt):
    if not blk.startswith('[unconnected_items]'):
        continue
    for m in re.finditer(r'\): Pad (\S+) \[([^\]]+)\] of (\S+) on (\S+)', blk):
        num, net, ref, layer = m.groups()
        if net in nets and (ref, num) not in want:
            want.append((ref, num))
if force:                   # pads named on the command line (the DRC may name the pour they sit on instead)
    want = force
print(f'{len(want)} unconnected surface pads on {sorted(nets)}')

outline = pcbnew.SHAPE_POLY_SET()
b.GetBoardPolygonOutlines(outline, True)


def near(item_bb, x, y, r):
    return item_bb.GetLeft() - r < x < item_bb.GetRight() + r and item_bb.GetTop() - r < y < item_bb.GetBottom() + r


def obstacles(x, y, net, reach=MM(4)):
    """items of other nets (and rule areas) near (x, y)"""
    out = {'tracks': [], 'pads': [], 'zones': [], 'rules': [], 'holes': []}
    for t in b.GetTracks():
        if not near(t.GetBoundingBox(), x, y, reach):
            continue
        if t.GetNetname() != net:
            out['tracks'].append(t)
        elif t.Type() == pcbnew.PCB_VIA_T:
            out['holes'].append(t)          # a via of the same net still needs hole-to-hole room
    for fp in b.GetFootprints():
        if not near(fp.GetBoundingBox(), x, y, reach):
            continue
        for p in fp.Pads():
            if near(p.GetBoundingBox(), x, y, reach):
                out['pads'].append(p)
    for z in b.Zones():
        if z.GetIsRuleArea():
            out['rules'].append(z)
        elif z.GetNetname() != net:
            out['zones'].append(z)
    return out


def clr(item, layer):
    try:
        return max(MM(CLEAR), item.GetOwnClearance(layer))
    except Exception:
        return MM(CLEAR)


def spot_ok(pad, net, x, y, obs, in_pad=False):
    r = MM(via_d) / 2
    c = VECTOR2I(int(x), int(y))
    # inside the board, clear of the edge
    if not outline.Contains(c):
        return False
    for i in range(outline.OutlineCount()):
        if outline.Outline(i).SquaredDistance(c, True) < (r + MM(EDGE)) ** 2:
            return False
    via = pcbnew.SHAPE_CIRCLE(c, int(r))
    seg = pcbnew.SHAPE_SEGMENT(pad.GetPosition(), c, MM(track_w))
    play = pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu      # (GetLayer() of a flipped pad can say F.Cu)
    for t in obs['holes']:
        gap = math.hypot(t.GetPosition().x - x, t.GetPosition().y - y) - (t.GetDrillValue() + MM(via_h)) / 2
        if gap < MM(HOLE_GAP):
            return False
    for t in obs['tracks']:
        for l in cu_layers:
            if not t.IsOnLayer(l):
                continue
            sh = t.GetEffectiveShape(l)
            if sh.Collide(via, clr(t, l)):
                return False
            if not in_pad and l == play and sh.Collide(seg, clr(t, l)):
                return False
        if t.Type() == pcbnew.PCB_VIA_T:
            gap = math.hypot(t.GetPosition().x - x, t.GetPosition().y - y) - (t.GetDrillValue() + MM(via_h)) / 2
            if gap < MM(HOLE_GAP):
                return False
    for p in obs['pads']:
        same = p.GetNetname() == net and net != ''
        for l in cu_layers:
            if not p.IsOnLayer(l):
                continue
            sh = p.GetEffectiveShape(l)
            if not same and sh.Collide(via, clr(p, l)):
                return False
            if not same and not in_pad and l == play and sh.Collide(seg, clr(p, l)):
                return False
        if same and not in_pad and p.IsOnLayer(play) and p.GetEffectiveShape(play).Collide(via, 0):
            return False                                   # no via in a pad (its own included)
        if p.HasHole():
            gap = math.hypot(p.GetPosition().x - x, p.GetPosition().y - y) - (max(p.GetDrillSize().x, p.GetDrillSize().y) + MM(via_h)) / 2
            if gap < MM(HOLE_GAP):
                return False
    for z in obs['zones']:
        if through_pours:
            break                    # the pour of the other net refills around the via and its track
        for l in cu_layers:
            if l not in OUTER or not z.IsOnLayer(l):
                continue
            polys = z.GetFilledPolysList(l)
            if polys.Collide(c, int(r + clr(z, l))):
                return False
            if not in_pad and l == play and polys.Collide(pcbnew.SEG(pad.GetPosition(), c), int(MM(track_w) / 2 + clr(z, l))):
                return False
    for z in obs['rules']:
        ol = z.Outline()
        if z.GetDoNotAllowVias() and ol.Contains(c):
            return False
        if not in_pad and z.GetDoNotAllowTracks() and z.IsOnLayer(play) and ol.Collide(pcbnew.SEG(pad.GetPosition(), c), 0):
            return False
    # it has to land in a plane of its own net
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != net:
            continue
        for l in inner:
            if z.IsOnLayer(l) and z.GetFilledPolysList(l).Contains(c):
                return True
    return False


def ep_vias(ref, num):
    """a grid of vias inside an exposed pad, where they fit"""
    fp = b.FindFootprintByReference(ref)
    pad = fp.FindPadByNumber(num) if fp else None
    if pad is None:
        return None
    net = pad.GetNetname()
    bb = pad.GetBoundingBox()
    inset = MM(via_d) / 2 + MM(0.1)
    pitch = MM(ep_pitch)

    def axis(lo, hi):
        n = max(1, int((hi - lo - 2 * inset) // pitch) + 1)
        start = (lo + hi) / 2 - (n - 1) * pitch / 2
        return [start + i * pitch for i in range(n)]
    obs = obstacles(bb.Centre().x, bb.Centre().y, net, reach=MM(8))
    n = 0
    shape = pad.GetEffectiveShape(pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu)
    for y in axis(bb.GetTop(), bb.GetBottom()):
        for x in axis(bb.GetLeft(), bb.GetRight()):
            c = VECTOR2I(int(x), int(y))
            # the whole via inside the pad
            ring = [VECTOR2I(int(x + MM(via_d) / 2 * math.cos(k * math.pi / 4)), int(y + MM(via_d) / 2 * math.sin(k * math.pi / 4)))
                    for k in range(8)]
            if not all(shape.Collide(q, 0) for q in [c] + ring):
                continue
            if not spot_ok(pad, net, x, y, obs, in_pad=True):
                continue
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(c)
            v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetWidth(MM(via_d))
            v.SetDrill(MM(via_h))
            v.SetNet(pad.GetNet())
            b.Add(v)
            obs['holes'].append(v)           # hole to hole against the next ones
            n += 1
    return n


def island_vias(max_area=200.0):
    """one via into every small fill piece of the nets that no via or through-hole pad of theirs reaches
    yet, where the via also lands in a fill of the same net on another layer"""
    n = 0
    fills = [z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname() in nets]
    thru = [(t.GetPosition(), t.GetNetname()) for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.HasHole():
                thru.append((p.GetPosition(), p.GetNetname()))
    anypad = next((p for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetname() in nets), None)
    r = MM(via_d) / 2
    for z in fills:
        net = z.GetNetname()
        for lay in z.GetLayerSet().CuStack():
            polys = z.GetFilledPolysList(lay)
            for i in range(polys.OutlineCount()):
                ol = polys.Outline(i)
                area = abs(ol.Area()) / 1e12
                if area < 0.4 or area > max_area:
                    continue
                if any(nn == net and ol.PointInside(c) for c, nn in thru):
                    continue
                bb = ol.BBox()
                cx, cy = bb.Centre().x, bb.Centre().y
                step = MM(0.25)
                pts = [(x, y) for x in range(bb.GetLeft(), bb.GetRight() + 1, step)
                       for y in range(bb.GetTop(), bb.GetBottom() + 1, step)]
                pts.sort(key=lambda q: (q[0] - cx) ** 2 + (q[1] - cy) ** 2)
                for x, y in pts:
                    c = VECTOR2I(int(x), int(y))
                    ring = [VECTOR2I(int(x + (r + MM(0.1)) * math.cos(k * math.pi / 6)),
                                     int(y + (r + MM(0.1)) * math.sin(k * math.pi / 6))) for k in range(12)]
                    if not ol.PointInside(c) or not all(ol.PointInside(q) for q in ring):
                        continue
                    if not any(z2.GetFilledPolysList(l2).Contains(c) for z2 in fills if z2.GetNetname() == net
                               for l2 in z2.GetLayerSet().CuStack() if l2 != lay):
                        continue
                    obs = obstacles(x, y, net, reach=MM(3))
                    if not spot_ok(anypad, net, x, y, obs, in_pad=True):
                        continue
                    v = pcbnew.PCB_VIA(b)
                    v.SetPosition(c)
                    v.SetViaType(pcbnew.VIATYPE_THROUGH)
                    v.SetWidth(MM(via_d))
                    v.SetDrill(MM(via_h))
                    v.SetNet(b.FindNet(net))
                    b.Add(v)
                    thru.append((c, net))
                    n += 1
                    print('  island via', net, b.GetLayerName(lay), '%.2f mm2' % area, round(ToMM(x), 2), round(ToMM(y), 2))
                    break
    return n


if '--zone-islands' in sys.argv:
    print('island vias:', island_vias())
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(path, b)
    sys.exit(0)

if eps:
    for ref, num in eps:
        print('%s pad %s: %s vias' % (ref, num, ep_vias(ref, num)))
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(path, b)
    sys.exit(0)

added, failed = 0, []
holes_new = []
for ref, num in want:
    fp = b.FindFootprintByReference(ref)
    pad = fp.FindPadByNumber(num) if fp else None
    if pad is None or pad.HasHole():
        continue
    net = pad.GetNetname()
    px, py = pad.GetPosition().x, pad.GetPosition().y
    obs = obstacles(px, py, net)
    obs['holes'] += holes_new
    size = max(pad.GetBoundingBox().GetWidth(), pad.GetBoundingBox().GetHeight()) / 2
    done = False
    for k in range(12):
        d = size + MM(via_d) / 2 + MM(CLEAR) + MM(0.25) * k
        for i in range(24):
            a = math.pi * 2 * i / 24
            x, y = px + d * math.cos(a), py + d * math.sin(a)
            if spot_ok(pad, net, x, y, obs):
                v = pcbnew.PCB_VIA(b)
                v.SetPosition(VECTOR2I(int(x), int(y)))
                v.SetViaType(pcbnew.VIATYPE_THROUGH)
                v.SetWidth(MM(via_d))
                v.SetDrill(MM(via_h))
                v.SetNet(pad.GetNet())
                b.Add(v)
                t = pcbnew.PCB_TRACK(b)
                t.SetStart(pad.GetPosition())
                t.SetEnd(VECTOR2I(int(x), int(y)))
                t.SetWidth(MM(track_w))
                t.SetLayer(pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu)
                t.SetNet(pad.GetNet())
                b.Add(t)
                holes_new.append(v)
                added += 1
                done = True
                break
        if done:
            break
    if not done:
        failed.append(f'{ref}.{num}')
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(path, b)
print(f'pad vias: {added} added; no room next to {len(failed)}: {" ".join(failed)}')
