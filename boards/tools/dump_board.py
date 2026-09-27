"""Dump any KiCad board to JSON for analysis outside KiCad (KiCad Python):
footprints (ref, value, fpid, position in mm, rotation, side, DNP, pads with net / bbox / drill / layers),
tracks and vias per net, zones (name, net, layers, priority, outline bbox), board outline bbox.

    flatpak run --command=python3 --filesystem=home org.kicad.KiCad dump_board.py IN.kicad_pcb OUT.json [--route-view]

--route-view   dump the board as the autorouter sees it (route_prep.prepare), and add every zone's and
               rule area's outline ('areas': name, net, rule, layers, no_tracks, no_vias, polygons as
               [outline, holes...] in page mm) and the plane layers, for mazeroute.py
"""
import json
import os
import sys

import pcbnew
from pcbnew import ToMM

b = pcbnew.LoadBoard(sys.argv[1])
held = []
if '--route-view' in sys.argv:
    from route_prep import prepare
    bpath = os.path.abspath(sys.argv[1])
    held = prepare(b, os.path.dirname(bpath), os.path.basename(bpath)[:-len('.kicad_pcb')], verbose=False)


def bb(r):
    return [round(ToMM(r.GetLeft()), 4), round(ToMM(r.GetTop()), 4), round(ToMM(r.GetRight()), 4), round(ToMM(r.GetBottom()), 4)]


out = {'edges': bb(b.GetBoardEdgesBoundingBox()), 'layers': b.GetCopperLayerCount(), 'fps': [], 'tracks': [], 'vias': [], 'zones': []}
for f in b.GetFootprints():
    p = f.GetPosition()
    e = {'ref': f.GetReference(), 'value': f.GetValue(), 'fpid': f.GetFPIDAsString(), 'x': round(ToMM(p.x), 4),
         'y': round(ToMM(p.y), 4), 'rot': f.GetOrientationDegrees(), 'side': 'B' if f.IsFlipped() else 'F',
         'dnp': bool(f.IsDNP()), 'bb': bb(f.GetBoundingBox(False)), 'pads': []}
    try:
        e['sheet'] = f.GetSheetname()
    except Exception:
        pass
    for pd in f.Pads():
        q = pd.GetPosition()
        e['pads'].append({'n': pd.GetNumber(), 'net': pd.GetNetname(), 'x': round(ToMM(q.x), 4), 'y': round(ToMM(q.y), 4),
                          'bb': bb(pd.GetBoundingBox()), 'drill': round(ToMM(pd.GetDrillSize().x), 3),
                          'layers': [b.GetLayerName(l) for l in pd.GetLayerSet().Seq() if pcbnew.IsCopperLayer(l)]})
    out['fps'].append(e)
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        q = t.GetPosition()
        out['vias'].append({'net': t.GetNetname(), 'x': round(ToMM(q.x), 4), 'y': round(ToMM(q.y), 4),
                            'dia': round(ToMM(t.GetWidth(pcbnew.F_Cu) if hasattr(t, 'GetWidth') else 0), 3),
                            'drill': round(ToMM(t.GetDrill()), 3), 'locked': bool(t.IsLocked())})
    else:
        s, e_ = t.GetStart(), t.GetEnd()
        out['tracks'].append({'net': t.GetNetname(), 'layer': b.GetLayerName(t.GetLayer()), 'w': round(ToMM(t.GetWidth()), 3),
                              'p': [round(ToMM(s.x), 4), round(ToMM(s.y), 4), round(ToMM(e_.x), 4), round(ToMM(e_.y), 4)],
                              'locked': bool(t.IsLocked())})
for z in b.Zones():
    out['zones'].append({'name': z.GetZoneName(), 'net': z.GetNetname(), 'rule': bool(z.GetIsRuleArea()),
                         'layers': [b.GetLayerName(l) for l in z.GetLayerSet().Seq()], 'prio': z.GetAssignedPriority(),
                         'bb': bb(z.GetBoundingBox())})
if '--route-view' in sys.argv:
    out['areas'] = []
    for z in b.Zones():
        ol = z.Outline()
        polys = []
        for i in range(ol.OutlineCount()):
            o = ol.Outline(i)
            rings = [[(round(ToMM(o.CPoint(k).x), 4), round(ToMM(o.CPoint(k).y), 4)) for k in range(o.PointCount())]]
            for h in range(ol.HoleCount(i)):
                hole = ol.Hole(i, h)
                rings.append([(round(ToMM(hole.CPoint(k).x), 4), round(ToMM(hole.CPoint(k).y), 4))
                              for k in range(hole.PointCount())])
            polys.append(rings)
        rule = bool(z.GetIsRuleArea())
        fills = {}
        if not rule and z.GetNetname() != 'GND':       # the copper the zone really has (as last filled)
            for l in z.GetLayerSet().Seq():
                if not pcbnew.IsCopperLayer(l):
                    continue
                fp = z.GetFilledPolysList(l)
                rings_l = []
                for i in range(fp.OutlineCount()):
                    o = fp.Outline(i)
                    rr = [[(round(ToMM(o.CPoint(k).x), 3), round(ToMM(o.CPoint(k).y), 3)) for k in range(o.PointCount())]]
                    for h in range(fp.HoleCount(i)):
                        hole = fp.Hole(i, h)
                        rr.append([(round(ToMM(hole.CPoint(k).x), 3), round(ToMM(hole.CPoint(k).y), 3))
                                   for k in range(hole.PointCount())])
                    rings_l.append(rr)
                fills[b.GetLayerName(l)] = rings_l
        out['areas'].append({'name': z.GetZoneName(), 'net': z.GetNetname(), 'rule': rule,
                             'layers': [b.GetLayerName(l) for l in z.GetLayerSet().Seq()],
                             'no_tracks': rule and bool(z.GetDoNotAllowTracks()),
                             'no_vias': rule and bool(z.GetDoNotAllowVias()), 'polys': polys, 'fills': fills})
    out['plane_layers'] = [b.GetLayerName(l) for l in b.GetEnabledLayers().CuStack()
                           if b.GetLayerType(l) == pcbnew.LT_POWER]
    out['netclass'] = {}                       # net: [track width, clearance, via diameter, via drill]
    err = None
    for code in range(1, b.GetNetCount()):
        ni = b.FindNet(code)
        if ni is None:
            continue
        try:
            nc = b.GetDesignSettings().m_NetSettings.GetEffectiveNetClass(ni.GetNetname())
            out['netclass'][ni.GetNetname()] = [round(ToMM(nc.GetTrackWidth()), 3), round(ToMM(nc.GetClearance()), 3),
                                                round(ToMM(nc.GetViaDiameter()), 3), round(ToMM(nc.GetViaDrill()), 3)]
        except Exception as e:
            err = e
    if err is not None:
        print('net classes: some nets skipped:', err)
json.dump(out, open(sys.argv[2], 'w'))
print('fps', len(out['fps']), 'tracks', len(out['tracks']), 'vias', len(out['vias']), 'zones', len(out['zones']))
