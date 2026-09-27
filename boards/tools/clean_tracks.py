"""Tidy a routed board (KiCad Python), then refill and save.

    flatpak run --command=python3 --filesystem=home org.kicad.KiCad clean_tracks.py drive

1. A track that ends on the middle of another track of its net (the routers join onto a track anywhere
   along it) makes KiCad's DRC call the end dangling. The other track is split there, so the two meet
   end to end.
2. A track that runs over a via or a pad of its net and goes on past it is split there too, so the
   part beyond can be seen as a dead end.
3. Unlocked tracks and vias that lead nowhere are taken away, over and over, as long as that does not
   leave any connection open that was made before. A via leads nowhere when it has at most one track
   and no pad or pour of its net on any layer, or when everything it touches is on one layer (then it
   joins nothing; a hand-placed, locked one of those goes too).
"""
import math
import os
import sys

import pcbnew
from pcbnew import VECTOR2I, ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
bdir = os.path.abspath(os.path.join(HERE, '..', sys.argv[1]))
name = [f for f in os.listdir(bdir) if f.endswith('.kicad_pcb')][0][:-len('.kicad_pcb')]
path = os.path.join(bdir, name + '.kicad_pcb')
b = pcbnew.LoadBoard(path)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
EPS = pcbnew.FromMM(0.001)


def segs():
    return [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T]


def foot(p, a, c):
    """foot of p on segment a-c, with the parameter t in [0, 1]"""
    dx, dy = c.x - a.x, c.y - a.y
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return a, 0.0
    t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / L2
    t = max(0.0, min(1.0, t))
    return VECTOR2I(int(a.x + t * dx), int(a.y + t * dy)), t


# ---------------------------------------------------------------- 1. T joins
split = 0
for _ in range(3):
    by = {}
    for t in segs():
        by.setdefault((t.GetNetCode(), t.GetLayer()), []).append(t)
    ends = {}
    for key, ts in by.items():
        for t in ts:
            for e in (t.GetStart(), t.GetEnd()):
                ends.setdefault(key, []).append((e.x, e.y))
    todo = []
    for key, ts in by.items():
        pts = ends[key]
        for t in ts:
            for which, e in (('s', t.GetStart()), ('e', t.GetEnd())):
                # already meets another track end here?
                n_at = sum(1 for (x, y) in pts if abs(x - e.x) <= EPS and abs(y - e.y) <= EPS)
                if n_at > 1:
                    continue
                for o in ts:
                    if o is t:
                        continue
                    f, u = foot(e, o.GetStart(), o.GetEnd())
                    if 0.0 < u < 1.0 and math.hypot(f.x - e.x, f.y - e.y) <= o.GetWidth() / 2:
                        todo.append((t, which, o, f))
                        break
    if not todo:
        break
    done = set()
    for t, which, o, f in todo:
        if id(o) in done or id(t) in done:
            continue
        # o becomes two tracks meeting at f; t's end moves onto f
        o2 = pcbnew.PCB_TRACK(b)
        o2.SetLayer(o.GetLayer())
        o2.SetNet(o.GetNet())
        o2.SetWidth(o.GetWidth())
        o2.SetStart(f)
        o2.SetEnd(o.GetEnd())
        o2.SetLocked(o.IsLocked())
        o.SetEnd(f)
        b.Add(o2)
        (t.SetStart if which == 's' else t.SetEnd)(f)
        done.add(id(o))
        done.add(id(t))
        split += 1


# ---------------------------------------------------------------- 2. tracks running over a via or pad
def anchors():
    out = {}
    for v in b.GetTracks():
        if v.Type() == pcbnew.PCB_VIA_T:
            out.setdefault(v.GetNetCode(), []).append((v.GetPosition(), v))
    for fp in b.GetFootprints():
        for p in fp.Pads():
            out.setdefault(p.GetNetCode(), []).append((p.GetPosition(), p))
    return out


def via_r(v):
    try:
        return v.GetWidth(pcbnew.F_Cu) / 2
    except TypeError:
        return v.GetWidth() / 2


for _ in range(3):
    anc = anchors()
    todo = []
    for t in segs():
        s0, e0 = t.GetStart(), t.GetEnd()
        for c, it in anc.get(t.GetNetCode(), []):
            is_via = it.Type() == pcbnew.PCB_VIA_T
            if not is_via and not it.IsOnLayer(t.GetLayer()):
                continue
            f, u = foot(c, s0, e0)
            # the foot on the track must lie in the via's or pad's copper, so both pieces still touch it
            inside = (math.hypot(f.x - c.x, f.y - c.y) <= via_r(it) - EPS * 20) if is_via else \
                it.GetEffectiveShape(t.GetLayer()).Collide(f, 0)
            if 0.0 < u < 1.0 and inside and \
                    min(math.hypot(f.x - s0.x, f.y - s0.y), math.hypot(f.x - e0.x, f.y - e0.y)) > EPS * 20:
                todo.append((t, f))      # the foot on the track, so the track keeps its line
                break
    if not todo:
        break
    for t, c in todo:
        t2 = pcbnew.PCB_TRACK(b)
        t2.SetLayer(t.GetLayer())
        t2.SetNet(t.GetNet())
        t2.SetWidth(t.GetWidth())
        t2.SetStart(c)
        t2.SetEnd(t.GetEnd())
        t2.SetLocked(t.IsLocked())
        t.SetEnd(c)
        b.Add(t2)
        split += 1


# ------------------------------------------------ 2b. vias that join tracks on one layer only
# (the tracks then get joined directly, inside the via's copper, so the via can go in step 3)
joined = 0
tr_by = {}
for t in segs():
    tr_by.setdefault(t.GetNetCode(), []).append(t)
for v in [v for v in b.GetTracks() if v.Type() == pcbnew.PCB_VIA_T]:
    c, r = v.GetPosition(), via_r(v)
    near = []
    for t in tr_by.get(v.GetNetCode(), []):
        f, u = foot(c, t.GetStart(), t.GetEnd())
        if math.hypot(f.x - c.x, f.y - c.y) <= r + t.GetWidth() / 2:
            near.append(t)
    if len(near) < 2 or len({t.GetLayer() for t in near}) != 1:
        continue
    for t in near:
        for e in (t.GetStart(), t.GetEnd()):
            if math.hypot(e.x - c.x, e.y - c.y) > r:
                continue
            others = [o for o in near if o is not t]
            if any(math.hypot(foot(e, o.GetStart(), o.GetEnd())[0].x - e.x,
                              foot(e, o.GetStart(), o.GetEnd())[0].y - e.y) <= o.GetWidth() / 2 for o in others):
                continue
            best = None
            for o in others:
                f2, u2 = foot(e, o.GetStart(), o.GetEnd())
                dd = math.hypot(f2.x - e.x, f2.y - e.y)
                if math.hypot(f2.x - c.x, f2.y - c.y) <= r and (best is None or dd < best[0]):
                    best = (dd, f2)
            if best:
                j = pcbnew.PCB_TRACK(b)
                j.SetLayer(t.GetLayer())
                j.SetNet(t.GetNet())
                j.SetWidth(min(t.GetWidth(), min(o.GetWidth() for o in others)))
                j.SetStart(VECTOR2I(e.x, e.y))
                j.SetEnd(best[1])
                b.Add(j)
                joined += 1


# ---------------------------------------------------------------- 3. dead ends
def unconnected():
    b.BuildConnectivity()
    c = b.GetConnectivity()
    try:
        return c.GetUnconnectedCount(False)
    except TypeError:
        return c.GetUnconnectedCount()


def dead_vias():
    out = []
    pours = {}
    for z in b.Zones():
        if not z.GetIsRuleArea():
            pours.setdefault(z.GetNetCode(), []).append(z)
    pads = {}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            pads.setdefault(p.GetNetCode(), []).append(p)
    tr = {}
    for t in segs():
        tr.setdefault(t.GetNetCode(), []).append(t)
    for v in b.GetTracks():
        if v.Type() != pcbnew.PCB_VIA_T:
            continue
        try:
            r = v.GetWidth(pcbnew.F_Cu) / 2
        except TypeError:
            r = v.GetWidth() / 2
        c = v.GetPosition()
        n = v.GetNetCode()
        ends = [t for t in tr.get(n, []) for e in (t.GetStart(), t.GetEnd())
                if math.hypot(e.x - c.x, e.y - c.y) <= r + t.GetWidth() / 2]
        lays = {t.GetLayer() for t in ends}
        if lays and len(lays) == 1 and not any(
                p.GetEffectiveShape(l).Collide(c, int(r)) for p in pads.get(n, []) for l in p.GetLayerSet().CuStack()
                if l not in lays) and not any(
                z.GetFilledPolysList(l).Collide(c, int(r)) for z in pours.get(n, []) for l in z.GetLayerSet().CuStack()
                if l not in lays):
            out.append(v)           # everything it touches is on one layer: it joins nothing
            continue
        if v.IsLocked() or len(ends) >= 2:
            continue
        if any(p.GetEffectiveShape(l).Collide(c, int(r)) for p in pads.get(n, []) for l in p.GetLayerSet().CuStack()):
            continue
        if any(z.GetFilledPolysList(l).Collide(c, int(r)) for z in pours.get(n, []) for l in z.GetLayerSet().CuStack()):
            continue
        out.append(v)
    return out


base = unconnected()
trimmed = 0
held = []           # removed items stay referenced: freeing them under KiCad's feet corrupts the board
for _ in range(60):
    b.BuildConnectivity()
    conn = b.GetConnectivity()
    dang = [t for t in segs() if (not t.IsLocked() or t.GetLength() < pcbnew.FromMM(1.0))
            and conn.TestTrackEndpointDangling(t, False)] + dead_vias()
    if not dang:
        break
    removed = 0
    for t in dang:
        b.Remove(t)
        if unconnected() <= base:
            held.append(t)
            removed += 1
        else:
            b.Add(t)
    trimmed += removed
    if not removed:
        break
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(path, b)
b.BuildConnectivity()
conn = b.GetConnectivity()
left = [t for t in segs() if conn.TestTrackEndpointDangling(t, False)]
print('clean: %d T joins split, %d one-layer vias bridged, %d dead-end tracks and vias taken away, %d track ends still dangling' %
      (split, joined, trimmed, len(left)))
for t in left[:15]:
    s = t.GetStart()
    print('  still dangling', t.GetNetname(), b.GetLayerName(t.GetLayer()), round(ToMM(s.x), 3), round(ToMM(s.y), 3))
