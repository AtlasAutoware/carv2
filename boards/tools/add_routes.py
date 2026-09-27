"""Apply mazeroute.py's result to the board (KiCad Python): take away the tracks and vias it moved,
add its new ones, refill every zone, trim what is left of the taken-up routes, and save.

    flatpak run --command=python3 --filesystem=home org.kicad.KiCad add_routes.py drive ROUTES.json

New tracks and vias go on unlocked, like the autorouter's, so strip_routes.py can take them off again.
"""
import json
import os
import sys

import pcbnew
from pcbnew import VECTOR2I, FromMM as MM, ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
bdir = os.path.abspath(os.path.join(HERE, '..', sys.argv[1]))
name = [f for f in os.listdir(bdir) if f.endswith('.kicad_pcb')][0][:-len('.kicad_pcb')]
path = os.path.join(bdir, name + '.kicad_pcb')
b = pcbnew.LoadBoard(path)
R = json.load(open(sys.argv[2]))
layer = {b.GetLayerName(l): l for l in b.GetEnabledLayers().CuStack()}
close = lambda a, c: abs(a - c) < 0.002

# take away what the router moved
want_t = [(t['net'], t['layer'], t['p']) for t in R.get('remove_tracks', [])]
want_v = [(v['net'], v['x'], v['y']) for v in R.get('remove_vias', [])]
gone, held = 0, []
for t in list(b.GetTracks()):
    if t.IsLocked():
        continue
    if t.Type() == pcbnew.PCB_VIA_T:
        q = t.GetPosition()
        for i, (n, x, y) in enumerate(want_v):
            if n == t.GetNetname() and close(ToMM(q.x), x) and close(ToMM(q.y), y):
                b.Remove(t)
                held.append(t)
                want_v.pop(i)
                gone += 1
                break
    else:
        s, e = t.GetStart(), t.GetEnd()
        p = (ToMM(s.x), ToMM(s.y), ToMM(e.x), ToMM(e.y))
        for i, (n, l, q) in enumerate(want_t):
            if n == t.GetNetname() and l == b.GetLayerName(t.GetLayer()) and all(close(a, c) for a, c in zip(p, q)):
                b.Remove(t)
                held.append(t)
                want_t.pop(i)
                gone += 1
                break
if want_t or want_v:
    print('not found on the board: %d tracks, %d vias' % (len(want_t), len(want_v)))

nt = nv = 0
fresh = set()
for t in R.get('tracks', []):
    net = b.FindNet(t['net'])
    tr = pcbnew.PCB_TRACK(b)
    tr.SetStart(VECTOR2I(MM(t['p'][0]), MM(t['p'][1])))
    tr.SetEnd(VECTOR2I(MM(t['p'][2]), MM(t['p'][3])))
    tr.SetWidth(MM(t['w']))
    tr.SetLayer(layer[t['layer']])
    tr.SetNet(net)
    b.Add(tr)
    fresh.add(tr.m_Uuid.AsString())
    nt += 1
for v in R.get('vias', []):
    net = b.FindNet(v['net'])
    via = pcbnew.PCB_VIA(b)
    via.SetPosition(VECTOR2I(MM(v['x']), MM(v['y'])))
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetWidth(MM(v['dia']))
    via.SetDrill(MM(v['drill']))
    via.SetNet(net)
    b.Add(via)
    fresh.add(via.m_Uuid.AsString())
    nv += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
# pieces of taken-up routes that now end in nothing. A piece only goes when the board stays exactly as
# connected without it: a new track may join an old one in the middle, and the old one's far end can
# then dangle while the piece is still needed.
def unconnected():
    b.BuildConnectivity()
    c = b.GetConnectivity()
    try:
        return c.GetUnconnectedCount(False)
    except TypeError:
        return c.GetUnconnectedCount()


trimmed = 0
base = unconnected()
for _ in range(50):
    conn = b.GetConnectivity()
    dang = [t for t in b.GetTracks() if not t.IsLocked() and conn.TestTrackEndpointDangling(t, False)]
    if not dang:
        break
    for t in dang:
        b.Remove(t)
    if unconnected() <= base:
        held.extend(dang)
        trimmed += len(dang)
        continue
    for t in dang:                      # all at once changed something: one by one
        b.Add(t)
    kept = 0
    for t in dang:
        b.Remove(t)
        if unconnected() <= base:
            held.append(t)
            trimmed += 1
        else:
            b.Add(t)
            kept += 1
    if kept == len(dang):
        break
if trimmed:
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.BuildConnectivity()
conn = b.GetConnectivity()
loose = [t for t in b.GetTracks() if t.m_Uuid.AsString() in fresh and conn.TestTrackEndpointDangling(t, False)]
pcbnew.SaveBoard(path, b)
print('took away %d, added %d tracks and %d vias, trimmed %d dangling pieces, %d new pieces left dangling; '
      'still open: %s' % (gone, nt, nv, trimmed, len(loose), ' '.join(R.get('still_open', [])) or 'none'))
for t in loose[:20]:
    p = t.GetPosition() if t.Type() == pcbnew.PCB_VIA_T else t.GetStart()
    print('  dangling', t.GetNetname(), b.GetLayerName(t.GetLayer()), round(ToMM(p.x), 3), round(ToMM(p.y), 3))
