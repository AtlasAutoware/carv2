"""Bring the autorouter's session back into the board (KiCad Python), refill every zone and save.
Locked tracks and vias (the hand-placed escapes and via arrays) survive the import.

    flatpak run --command=python3 --filesystem=home org.kicad.KiCad ses_import.py drive [--trim]

--trim   afterwards remove unlocked track pieces and vias that end in nothing (left over when parts
         moved since the session was routed), until none are left
Vias whose drill is below the board's minimum through-hole size are opened up to it (the session
names its via padstacks after the net class default, which can be smaller). The session's placement
section is ignored: the board keeps its own part positions.
"""
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kicompat as kc  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
bdir = os.path.abspath(os.path.join(HERE, '..', sys.argv[1]))
trim = '--trim' in sys.argv[2:]
name = [f for f in os.listdir(bdir) if f.endswith('.kicad_pcb')][0][:-len('.kicad_pcb')]
path = os.path.join(bdir, name + '.kicad_pcb')
b = pcbnew.LoadBoard(path)
ses = os.path.join(bdir, 'out', name + '.ses')
# KiCad moves every footprint to the session's (placement) section on import. The board may have been
# re-placed since the session was routed, so import a copy without that section: parts stay where the
# board has them and routes that no longer fit are trimmed below or reported by DRC.
txt = open(ses).read()
i = txt.find('(placement')
if i >= 0:
    depth, j = 0, i
    while True:
        if txt[j] == '(':
            depth += 1
        elif txt[j] == ')':
            depth -= 1
            if depth == 0:
                break
        j += 1
    txt = txt[:i] + txt[j + 1:]
ses_np = ses[:-4] + '_noplace.ses'
open(ses_np, 'w').write(txt)


def import_ses_python(b, text):
    """KiCad 7: pcbnew.ImportSpecctraSES works only inside the board editor (it takes no board). This does what
    KiCad's importer does: unlocked tracks and vias go, then every wire and via of the session's network_out
    comes in on its net; items the session marks fix/protect are the board's own locked copper and stay as
    they are. Coordinates: session units per its (resolution), Y up; the via size and drill come from the
    padstack name KiCad gave it (Via[0-1]_<dia>:<drill>_um)."""
    import re
    from sexp import parse
    from pcbnew import VECTOR2I

    tree = parse(text)[0]

    def find(x, key):
        return [e for e in x if isinstance(e, list) and e and e[0] == key]

    routes = find(tree, 'routes')[0]
    res = find(routes, 'resolution')[0]
    unit, per = res[1], float(res[2])
    to_mm = {'um': 0.001, 'mm': 1.0, 'mil': 0.0254, 'inch': 25.4}[unit] / per
    for t in list(b.GetTracks()):
        if not t.IsLocked():
            b.Remove(t)
            held.append(t)
    layer = {b.GetLayerName(l): l for l in b.GetEnabledLayers().CuStack()}
    pads = {}
    for ps in find(find(routes, 'library_out')[0], 'padstack') if find(routes, 'library_out') else []:
        m = re.search(r'_(\d+(?:\.\d+)?):(\d+(?:\.\d+)?)_um', ps[1].strip('"'))
        if m:
            pads[ps[1].strip('"')] = (float(m.group(1)) / 1000, float(m.group(2)) / 1000)
    MM = pcbnew.FromMM
    pt = lambda x, y: VECTOR2I(MM(float(x) * to_mm), MM(-float(y) * to_mm))
    nt = nv = 0
    for net in find(find(routes, 'network_out')[0], 'net'):
        ni = b.FindNet(net[1].strip('"'))
        if ni is None:
            print('session net not on the board:', net[1])
            continue
        for w in find(net, 'wire'):
            ty = find(w, 'type')
            if ty and ty[0][1] in ('fix', 'protect'):
                continue
            for path in find(w, 'path'):
                lay, width, xy = path[1].strip('"'), float(path[2]) * to_mm, path[3:]
                pts = [pt(xy[i], xy[i + 1]) for i in range(0, len(xy) - 1, 2)]
                for p0, p1 in zip(pts, pts[1:]):
                    tr = pcbnew.PCB_TRACK(b)
                    tr.SetStart(p0)
                    tr.SetEnd(p1)
                    tr.SetWidth(MM(width))
                    tr.SetLayer(layer[lay])
                    tr.SetNet(ni)
                    b.Add(tr)
                    nt += 1
        for v in find(net, 'via'):
            ty = find(v, 'type')
            if ty and ty[0][1] in ('fix', 'protect'):
                continue
            name = v[1].strip('"')
            dia, drill = pads.get(name, (0.8, 0.4))
            via = pcbnew.PCB_VIA(b)
            via.SetPosition(pt(v[2], v[3]))
            via.SetViaType(pcbnew.VIATYPE_THROUGH)
            via.SetWidth(MM(dia))
            via.SetDrill(MM(drill))
            via.SetNet(ni)
            b.Add(via)
            nv += 1
    print(f'session read in Python (KiCad 7): {nt} track segments, {nv} vias')
    return True


held = []
n0 = len(b.GetTracks())
try:
    ok = pcbnew.ImportSpecctraSES(b, ses_np)
except TypeError:
    ok = import_ses_python(b, txt)
n1 = len(b.GetTracks())
gone = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetZoneName().startswith('D:')]
for z in gone:
    b.Remove(z)                      # router-only keepouts
min_drill = b.GetDesignSettings().m_MinThroughDrill
opened = 0
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T and t.GetDrillValue() < min_drill:
        t.SetDrill(min_drill)
        opened += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
trimmed = 0
keep = []                            # removed items stay referenced (SWIG frees them otherwise)
if trim:
    for _ in range(100):
        b.BuildConnectivity()
        conn = b.GetConnectivity()
        dang = [t for t in b.GetTracks() if not t.IsLocked() and conn.TestTrackEndpointDangling(t, False)]
        if not dang:
            break
        for t in dang:
            b.Remove(t)
            keep.append(t)
        trimmed += len(dang)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
kc.save(path, b)
print('imported', ses, ok, 'tracks+vias', n0, '->', n1, '; removed', len(gone), 'router keepouts;',
      opened, 'vias opened to', pcbnew.ToMM(min_drill), 'mm;', trimmed, 'dangling pieces trimmed')
