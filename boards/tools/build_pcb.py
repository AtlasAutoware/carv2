"""Build a board from <board>/<name>_parts.json and <board>/layout.py. Runs inside KiCad's Python:

    flatpak run --command=python3 --filesystem=home org.kicad.KiCad build_pcb.py drive

Placement comes from layout.PLACE (explicit, for everything that matters electrically or
mechanically). Every other part is placed next to the pad of the part it connects to, in the
first free spot, so decoupling capacitors land next to their pins.
"""
import importlib.util
import json
import math
import os
import sys

import pcbnew
from pcbnew import VECTOR2I, FromMM as MM, ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
_cands = [os.environ.get('KICAD_FP_DIR', ''), '/app/extensions/Library/footprints',
          os.path.expanduser('~/.local/share/flatpak/runtime/org.kicad.KiCad.Library.Footprints/x86_64/stable/active/files/footprints'),
          '/usr/share/kicad/footprints']
FPDIR = next(c for c in _cands if c and os.path.isdir(c))
LOCAL = {'atlas': os.path.join(HERE, '..', 'lib', 'atlas.pretty')}

board_name = sys.argv[1]
BDIR = os.path.abspath(os.path.join(HERE, '..', board_name))
spec = importlib.util.spec_from_file_location('layout', os.path.join(BDIR, 'layout.py'))
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)
data = json.load(open(os.path.join(BDIR, f'{L.NAME}_parts.json')))
parts = {p['ref']: p for p in data['parts']}

OX, OY = L.PAGE_ORIGIN
W, H = L.SIZE


def P(x, y):
    """board-local (X forward, Y to car-left, mm) -> KiCad page coordinates"""
    return VECTOR2I(MM(OX + x), MM(OY + (H - y)))


def back(v):
    return (ToMM(v.x) - OX, H - (ToMM(v.y) - OY))


LAYER = {'F': pcbnew.F_Cu, 'In1': pcbnew.In1_Cu, 'In2': pcbnew.In2_Cu, 'In3': pcbnew.In3_Cu, 'In4': pcbnew.In4_Cu,
         'B': pcbnew.B_Cu}

b = pcbnew.BOARD()
b.SetCopperLayerCount(L.COPPER_LAYERS)
ds = b.GetDesignSettings()
nets = {}


def net(name):
    if name not in nets:
        ni = pcbnew.NETINFO_ITEM(b, name)
        b.Add(ni)
        nets[name] = ni
    return nets[name]


for n in sorted(data['nets']):
    net(n)

_fpcache = {}


def load_fp(fpid):
    lib, name = fpid.split(':')
    path = LOCAL.get(lib, os.path.join(FPDIR, lib + '.pretty'))
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise RuntimeError('footprint not found: ' + fpid)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def nc_net(ref, p, num):
    """The name KiCad's netlister gives a pin that has a no-connect flag, so that the board agrees with
    the schematic: unconnected-(REF-PINNAME-PadN), or unconnected-(REF-PadN) when the pin has no name
    of its own. Stacked pins share the net of the visible pin in the stack."""
    num = p.get('pinprimary', {}).get(num, num)
    nm = p.get('pinnames', {}).get(num, '')
    nm = '' if nm in ('~', num) else nm.replace('/', '{slash}')
    return f'unconnected-({ref}-{nm}-Pad{num})' if nm else f'unconnected-({ref}-Pad{num})'


fps = {}
SILK_REF = []
for ref, p in parts.items():
    fp = load_fp(p['footprint'])
    fp.SetReference(ref)
    fp.SetValue(p['value'])
    b.Add(fp)
    for pad in fp.Pads():
        num = pad.GetNumber()
        n = p['pads'].get(num)
        if n:
            pad.SetNet(net(n))
        elif num in p['pads']:
            pad.SetNet(net(nc_net(ref, p, num)))
    fp.SetPath(pcbnew.KIID_PATH(p['path']))
    try:
        fp.SetSheetfile(p['sheetfile'])
        fp.SetSheetname(p['block'])
    except Exception:
        pass
    for k, v in p['fields'].items():
        if k == 'in_bom':
            continue
        if k in ('Description', 'Datasheet'):
            f = fp.GetField(k)
            if f:
                f.SetText(str(v))
                continue
        fp.SetField(k, str(v))
        f = fp.GetField(k)
        f.SetVisible(False)
        f.SetLayer(pcbnew.F_Fab)
    if p['fields'].get('in_bom') == 'no':
        fp.SetExcludedFromBOM(True)
    else:
        fp.SetExcludedFromBOM(False)           # some library footprints (solder jumpers) carry the flag themselves
    if p.get('dnp'):
        fp.SetDNP(True)                        # stays in the BOM, marked DNP, like the schematic symbol
        fp.SetExcludedFromPosFiles(True)
    rf = fp.Reference()
    rf.SetTextSize(VECTOR2I(MM(0.8), MM(0.8)))
    rf.SetTextThickness(MM(0.12))
    fp.Value().SetVisible(False)
    SILK_REF.append(ref)
    fps[ref] = fp


def place(ref, x, y, rot=0, side='F'):
    fp = fps[ref]
    if side == 'B' and not fp.IsFlipped():
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(P(x, y))


def pad_xy(ref, num):
    for pd in fps[ref].Pads():
        if pd.GetNumber() == num:
            return back(pd.GetPosition())
    raise KeyError(f'{ref} pad {num}')


def face(ref, x, y, pads, direction, side='F'):
    """Place so that the centroid of `pads` points in `direction` ('up', 'down', 'left', 'right': board-local)."""
    want = {'up': (0, 1), 'down': (0, -1), 'left': (-1, 0), 'right': (1, 0)}[direction]
    best = None
    for rot in (0, 90, 180, 270):
        place(ref, x, y, rot, side)
        cx, cy = x, y
        ps = [pad_xy(ref, n) for n in pads]
        mx = sum(p[0] for p in ps) / len(ps) - cx
        my = sum(p[1] for p in ps) / len(ps) - cy
        score = mx * want[0] + my * want[1]
        if best is None or score > best[0]:
            best = (score, rot)
    place(ref, x, y, best[1], side)
    return best[1]


def anchor_pad(ref, num, x, y, rot=None, side='F'):
    """Move the footprint so that pad `num` lands exactly on (x, y)."""
    fp = fps[ref]
    if rot is not None:
        place(ref, x, y, rot, side)
    px, py = pad_xy(ref, num)
    fx, fy = back(fp.GetPosition())
    place(ref, fx + (x - px), fy + (y - py), fp.GetOrientationDegrees(), side)


# ----------------------------------------------------------------------------- placement (from tools/placer.py)
PLACEMENT = os.path.join(BDIR, 'out', f'{L.NAME}_placement.json')
placement = json.load(open(PLACEMENT))
missing = [r for r in parts if r not in placement]
if missing:
    raise SystemExit('placement has no position for ' + ', '.join(missing[:20]) + ' (run tools/placer.py first)')
for ref, v in placement.items():
    place(ref, v['x'], v['y'], v['rot'], v['side'])
placed = set(placement)
KEEP_SILK = ('J', 'SW', 'TP', 'U')
for ref in SILK_REF:
    fp = fps[ref]
    led = ref.startswith('D') and parts[ref]['value'].upper() in ('RED', 'GREEN', 'BLUE', 'AMBER', 'YELLOW')
    if not (ref.startswith(KEEP_SILK) or led):
        fp.Reference().SetLayer(pcbnew.B_Fab if fp.IsFlipped() else pcbnew.F_Fab)


def courtyard(fp, margin=0.15):
    lay = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
    try:
        poly = fp.GetCourtyard(lay)
        if poly.OutlineCount():
            bb = poly.BBox()
            return (ToMM(bb.GetLeft()) - margin, ToMM(bb.GetTop()) - margin, ToMM(bb.GetRight()) + margin, ToMM(bb.GetBottom()) + margin)
    except Exception:
        pass
    bb = fp.GetBoundingBox(False)
    return (ToMM(bb.GetLeft()) - margin, ToMM(bb.GetTop()) - margin, ToMM(bb.GetRight()) + margin, ToMM(bb.GetBottom()) + margin)


def side_of(fp):
    return 'B' if fp.IsFlipped() else 'F'


# ----------------------------------------------------------------------------- outline, holes, zones, tracks
L.finish(sys.modules[__name__])

# ----------------------------------------------------------------------------- layer types, net classes, rules
for lay, lt in getattr(L, 'LAYER_TYPES', {'In1': 'power', 'In2': 'power'}).items():
    b.SetLayerType(LAYER[lay],
                   {'power': pcbnew.LT_POWER, 'mixed': pcbnew.LT_MIXED, 'signal': pcbnew.LT_SIGNAL}[lt])
ds.m_MinClearance = MM(0.15)
ds.m_TrackMinWidth = MM(0.15)
ds.m_ViasMinSize = MM(0.5)
ds.m_MinThroughDrill = MM(0.2)
ds.m_HoleClearance = MM(0.2)
ds.m_HoleToHoleMin = MM(0.25)
ds.m_CopperEdgeClearance = MM(0.3)
NETCLASSES = getattr(L, 'NETCLASSES', {})
nset = ds.m_NetSettings
dflt = nset.GetDefaultNetclass()
dflt.SetClearance(MM(0.2))
dflt.SetTrackWidth(MM(0.2))
dflt.SetViaDiameter(MM(0.6))
dflt.SetViaDrill(MM(0.3))
for name, c in NETCLASSES.items():
    nc = pcbnew.NETCLASS(name)
    nc.SetClearance(MM(c['clearance']))
    nc.SetTrackWidth(MM(c['width']))
    nc.SetViaDiameter(MM(c.get('via', 0.6)))
    nc.SetViaDrill(MM(c.get('drill', 0.3)))
    nset.SetNetclass(name, nc)
    for n in c['nets']:
        nset.SetNetclassPatternAssignment(n, name)

# ----------------------------------------------------------------------------- copper from the placer (zones, vias, tracks)
COPPER = os.path.join(BDIR, 'out', f'{L.NAME}_copper.json')
cu = json.load(open(COPPER)) if os.path.exists(COPPER) else {'zones': [], 'vias': [], 'tracks': []}


def xy(x, y):
    return (MM(OX + x), MM(OY + (H - y)))


for z in cu['zones']:
    zn = pcbnew.ZONE(b)
    zn.SetLayer(LAYER[z['layer']])
    zn.SetNet(net(z['net']))
    zn.SetAssignedPriority(z['priority'])
    zn.SetLocalClearance(MM(z['clearance']))
    zn.SetMinThickness(MM(z['min_width']))
    zn.SetPadConnection({'full': pcbnew.ZONE_CONNECTION_FULL, 'thermal': pcbnew.ZONE_CONNECTION_THERMAL,
                         'tht': pcbnew.ZONE_CONNECTION_THT_THERMAL}[z['connect']])
    zn.SetThermalReliefGap(MM(z['thermal_gap']))
    zn.SetThermalReliefSpokeWidth(MM(z['spoke']))
    zn.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    zn.SetZoneName(z['name'])
    ol = zn.Outline()
    for rings in z['rings']:
        oi = ol.NewOutline()
        for (x, y) in rings[0]:
            ol.Append(*xy(x, y), oi, -1)
        for hole in rings[1:]:
            hi = ol.NewHole(oi)
            for (x, y) in hole:
                ol.Append(*xy(x, y), oi, hi)
    b.Add(zn)
for r in cu.get('rules', []):
    # rule areas; 'D:' ones only guide the autorouter and are deleted when its session comes back
    ra = pcbnew.ZONE(b)
    ra.SetIsRuleArea(True)
    ra.SetDoNotAllowTracks(bool(r['no_tracks']))
    ra.SetDoNotAllowVias(bool(r['no_vias']))
    ra.SetDoNotAllowPads(False)
    ra.SetDoNotAllowFootprints(False)
    try:
        ra.SetDoNotAllowZoneFills(bool(r['no_zones']))
    except AttributeError:
        ra.SetDoNotAllowCopperPour(bool(r['no_zones']))
    ls = pcbnew.LSET()
    for lay in r['layers']:
        ls.AddLayer(LAYER[lay])
    ra.SetLayerSet(ls)
    ra.SetZoneName(r['name'])
    ol = ra.Outline()
    for rings in r['rings']:
        oi = ol.NewOutline()
        for (x, y) in rings[0]:
            ol.Append(*xy(x, y), oi, -1)
        for hole in rings[1:]:
            hi = ol.NewHole(oi)
            for (x, y) in hole:
                ol.Append(*xy(x, y), oi, hi)
    b.Add(ra)
for v in cu['vias']:
    via = pcbnew.PCB_VIA(b)
    via.SetPosition(VECTOR2I(*xy(v['x'], v['y'])))
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetWidth(MM(v['dia']))
    via.SetDrill(MM(v['drill']))
    via.SetNet(net(v['net']))
    via.SetLocked(bool(v.get('locked', True)))
    b.Add(via)
for t in cu['tracks']:
    for (x0, y0), (x1, y1) in zip(t['pts'], t['pts'][1:]):
        tr = pcbnew.PCB_TRACK(b)
        tr.SetStart(VECTOR2I(*xy(x0, y0)))
        tr.SetEnd(VECTOR2I(*xy(x1, y1)))
        tr.SetWidth(MM(t['width']))
        tr.SetLayer(LAYER[t['layer']])
        tr.SetNet(net(t['net']))
        tr.SetLocked(bool(t.get('locked', True)))
        b.Add(tr)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())

out = os.path.join(BDIR, f'{L.NAME}.kicad_pcb')
pcbnew.SaveBoard(out, b)


def dump_geometry(path):
    """Board-local geometry of every footprint and pad, for plots and checks outside KiCad."""
    g = {'size': [W, H], 'fps': []}
    for fp in b.GetFootprints():
        x0, y0, x1, y1 = courtyard(fp, 0)
        a, c = back(VECTOR2I(MM(x0), MM(y1))), back(VECTOR2I(MM(x1), MM(y0)))
        e = {'ref': fp.GetReference(), 'side': side_of(fp), 'pos': back(fp.GetPosition()),
             'rot': fp.GetOrientationDegrees(), 'crt': [a[0], a[1], c[0], c[1]], 'pads': []}
        for pd in fp.Pads():
            bb = pd.GetBoundingBox()
            p0, p1 = back(VECTOR2I(bb.GetLeft(), bb.GetBottom())), back(VECTOR2I(bb.GetRight(), bb.GetTop()))
            lay = 'FB' if pd.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) else side_of(fp)
            e['pads'].append({'n': pd.GetNumber(), 'net': pd.GetNetname(), 'c': back(pd.GetPosition()),
                              'bb': [p0[0], p0[1], p1[0], p1[1]], 'lay': lay, 'drill': ToMM(pd.GetDrillSize().x),
                              'cu': bool(pd.IsOnCopperLayer())})
        g['fps'].append(e)
    json.dump(g, open(path, 'w'))


os.makedirs(os.path.join(BDIR, 'out'), exist_ok=True)
dump_geometry(os.path.join(BDIR, 'out', f'{L.NAME}_geom.json'))
print('saved', out, len(b.GetFootprints()), 'footprints', len(b.GetTracks()), 'tracks+vias', len(b.Zones()), 'zones')

if getattr(L, 'DRU', None):
    open(os.path.join(BDIR, f'{L.NAME}.kicad_dru'), 'w').write(L.DRU)

# net classes also go into the project file (KiCad keeps them there)
pro = os.path.join(BDIR, f'{L.NAME}.kicad_pro')
if os.path.exists(pro) and NETCLASSES:
    P_ = json.load(open(pro))
    ns = P_.setdefault('net_settings', {})
    classes = [c for c in ns.get('classes', []) if c.get('name') == 'Default']
    for c in classes:
        c.update({'clearance': 0.2, 'track_width': 0.2, 'via_diameter': 0.6, 'via_drill': 0.3})
    for name, c in NETCLASSES.items():
        classes.append({'name': name, 'clearance': c['clearance'], 'track_width': c['width'],
                        'via_diameter': c.get('via', 0.6), 'via_drill': c.get('drill', 0.3),
                        'diff_pair_width': 0.2, 'diff_pair_gap': 0.25, 'wire_width': 6, 'bus_width': 12,
                        'line_style': 0, 'priority': len(classes)})
    ns['classes'] = classes
    ns['netclass_patterns'] = [{'netclass': name, 'pattern': n} for name, c in NETCLASSES.items() for n in c['nets']]
    sev = P_.setdefault('board', {}).setdefault('design_settings', {}).setdefault('rule_severities', {})
    sev.update({'lib_footprint_issues': 'ignore', 'lib_footprint_mismatch': 'ignore'})
    rules = P_.setdefault('board', {}).setdefault('design_settings', {}).setdefault('rules', {})
    rules.update({'min_clearance': 0.15, 'min_track_width': 0.15, 'min_via_diameter': 0.5, 'min_via_annular_width': 0.1,
                  'min_through_hole_diameter': 0.2, 'min_hole_clearance': 0.2, 'min_hole_to_hole': 0.25,
                  'min_copper_edge_clearance': 0.3})
    json.dump(P_, open(pro, 'w'), indent=2)
    print('net classes written to', pro)
