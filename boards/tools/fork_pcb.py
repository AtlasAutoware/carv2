"""Build ATLAS-BRN-1's board from Antmicro's (runs inside KiCad's Python).

    flatpak run --command=python3 --filesystem=home org.kicad.KiCad fork_pcb.py [--geom]

--geom   writes brain/out/atlas_brain_geom.json (footprints of the new parts, for tools/placer.py) and
         brain/out/atlas_brain_obstacles.json (Antmicro parts that stay) and stops.
default  loads vendor/antmicro/jetson-orin-baseboard.kicad_pcb and
           1. deletes the footprints fork_config.py removed from the schematic,
           2. gives every remaining pad the net the forked schematic's netlist gives it,
           3. renames the tracks, vias and zones of renamed nets and deletes those of dead nets,
           4. trims tracks left dangling (repeatedly, until nothing dangles),
           5. extends the outline to 120 x 90 mm and the inner GND planes into the new strip,
           6. adds the Atlas parts at the positions tools/placer.py computed, plus their copper,
         and saves brain/atlas_brain.kicad_pcb. Antmicro's routing is kept as it was.

Board-local coordinates (brain/layout.py, stack.py): X forward from the rear edge (page x 29.75),
Y toward the car's left from the I/O edge (page y 128.75), mm.
"""
import collections
import json
import math
import os
import sys

import pcbnew
from pcbnew import VECTOR2I, FromMM as MM, ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sexp import parse, find, find1, uq  # noqa: E402

BDIR = os.path.abspath(os.path.join(HERE, '..', 'brain'))
sys.path.insert(0, BDIR)
import fork_config as F  # noqa: E402

VENDOR_PCB = os.path.join(BDIR, 'vendor', 'antmicro', F.ANTMICRO_PROJECT + '.kicad_pcb')
OUT_PCB = os.path.join(BDIR, F.PROJECT + '.kicad_pcb')
NETLIST = os.path.join(BDIR, 'out', F.PROJECT + '.net')
PARTS = os.path.join(BDIR, F.PROJECT + '_parts.json')
OX, OY = 29.75, 128.75            # page position of the board-local origin (rear edge, I/O edge)
W, H = 120.0, 90.0                # new outline; Antmicro's was 120 x 60
OLD_H = 60.0
CORNER_R = 1.0

_cands = [os.environ.get('KICAD_FP_DIR', ''), '/app/extensions/Library/footprints',
          os.path.expanduser('~/.local/share/flatpak/runtime/org.kicad.KiCad.Library.Footprints/x86_64/stable/active/files/footprints'),
          '/usr/share/kicad/footprints']
FPDIR = next(c for c in _cands if c and os.path.isdir(c))
LAYER = {'F': pcbnew.F_Cu, 'B': pcbnew.B_Cu, 'In1': pcbnew.In1_Cu, 'In2': pcbnew.In2_Cu, 'In3': pcbnew.In3_Cu,
         'In4': pcbnew.In4_Cu, 'In5': pcbnew.In5_Cu, 'In6': pcbnew.In6_Cu}


def P(x, y):
    return VECTOR2I(MM(OX + x), MM(OY - y))


def back(v):
    return (ToMM(v.x) - OX, OY - ToMM(v.y))


def log(*a):
    print(*a, flush=True)


_graveyard = []      # removed items stay referenced: SWIG would otherwise free them while KiCad still points at them


def drop(b, item):
    b.Remove(item)
    _graveyard.append(item)


# ----------------------------------------------------------------------------- inputs
def read_netlist(path):
    root = parse(open(path).read())[0]
    comps = {}
    for c in find(find1(root, 'components'), 'comp'):
        ref = uq(find1(c, 'ref')[1])
        fp = find1(c, 'footprint')
        comps[ref] = {'value': uq(find1(c, 'value')[1]), 'footprint': uq(fp[1]) if fp else ''}
    pad_net = {}
    nets = {}
    for n in find(find1(root, 'nets'), 'net'):
        name = uq(find1(n, 'name')[1])
        nodes = [(uq(find1(nd, 'ref')[1]), uq(find1(nd, 'pin')[1])) for nd in find(n, 'node')]
        nets[name] = nodes
        for r, p in nodes:
            pad_net[(r, p)] = name
    return comps, pad_net, nets


def board_only(fp):
    """fiducials and logos: on Antmicro's board without a schematic symbol"""
    r = fp.GetReference()
    return r.startswith('FID') or r.startswith('REF') or fp.GetPath().AsString() == ''


# ----------------------------------------------------------------------------- footprints of the new parts
_dup_src = {}


def new_footprint(b, part):
    """a fresh footprint for an Atlas part: stock library, or a copy of the same Antmicro footprint that is
    already on the board (so the pads are exactly Antmicro's). Normalised: top side, 0 deg."""
    fpid = part['footprint']
    lib, name = fpid.split(':', 1)
    if lib == 'antmicro-footprints':
        src = _dup_src.get(fpid)
        if src is None:
            for f in b.GetFootprints():
                if f.GetFPIDAsString() == fpid:
                    src = f
                    break
            if src is None:
                raise RuntimeError('no Antmicro footprint on the board to copy: ' + fpid)
            _dup_src[fpid] = src
        fp = src.Duplicate(False).Cast()
        if fp.IsFlipped():
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetOrientationDegrees(0)
        for fld in list(fp.GetFields()):
            if not fld.IsMandatory():
                try:
                    fp.Remove(fld)
                    _graveyard.append(fld)
                except Exception:
                    fld.SetText('')
                    fld.SetVisible(False)
        for pd in fp.Pads():
            pd.SetNetCode(0)
        ds = fp.GetField('Datasheet')
        if ds:
            ds.SetText('')           # the schematic symbol is Atlas's, not Antmicro's
    else:
        fp = pcbnew.FootprintLoad(os.path.join(FPDIR, lib + '.pretty'), name)
        if fp is None:
            raise RuntimeError('footprint not found: ' + fpid)
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
    fp.SetReference(part['ref'])
    fp.SetValue(part['value'])
    return fp


def courtyard(fp):
    lay = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
    try:
        poly = fp.GetCourtyard(lay)
        if poly.OutlineCount():
            bb = poly.BBox()
            return bb
    except Exception:
        pass
    return fp.GetBoundingBox(False)


def box_local(bb):
    a, c = back(VECTOR2I(bb.GetLeft(), bb.GetBottom())), back(VECTOR2I(bb.GetRight(), bb.GetTop()))
    return [a[0], a[1], c[0], c[1]]


def geom_entry(fp):
    e = {'ref': fp.GetReference(), 'side': 'B' if fp.IsFlipped() else 'F', 'pos': back(fp.GetPosition()),
         'rot': fp.GetOrientationDegrees(), 'crt': box_local(courtyard(fp)), 'pads': []}
    for pd in fp.Pads():
        e['pads'].append({'n': pd.GetNumber(), 'net': pd.GetNetname(), 'c': back(pd.GetPosition()),
                          'bb': box_local(pd.GetBoundingBox()), 'drill': ToMM(pd.GetDrillSize().x),
                          'cu': bool(pd.IsOnCopperLayer())})
    return e


# ----------------------------------------------------------------------------- steps
def remove_footprints(b, comps):
    gone = []
    for fp in list(b.GetFootprints()):
        r = fp.GetReference()
        if r not in comps and not board_only(fp):
            gone.append(r)
            drop(b, fp)
    return gone


def renet(b, pad_net):
    nets = {}

    def net(name):
        ni = b.FindNet(name)
        if ni is None:
            ni = pcbnew.NETINFO_ITEM(b, name)
            b.Add(ni)
        return ni
    mapping = collections.defaultdict(collections.Counter)
    changed = 0
    for fp in b.GetFootprints():
        if board_only(fp):
            continue
        r = fp.GetReference()
        for pd in fp.Pads():
            num = pd.GetNumber()
            new = pad_net.get((r, num))
            if new is None:
                continue
            old = pd.GetNetname()
            if old:
                mapping[old][new] += 1
            if old != new:
                pd.SetNet(net(new))
                changed += 1
    return mapping, changed, net


def remap_copper(b, mapping, net):
    """tracks, vias and zones follow their pads' new nets; copper of nets without pads goes"""
    dead = split = renamed = 0
    splits = {}
    for t in list(b.GetTracks()) + [z for z in b.Zones() if not z.GetIsRuleArea()]:
        old = t.GetNetname()
        if not old:
            continue
        m = mapping.get(old)
        if not m:
            drop(b, t)
            dead += 1
            continue
        if len(m) == 1:
            new = next(iter(m))
            if new != old:
                t.SetNet(net(new))
                renamed += 1
        else:
            split += 1
            splits[old] = dict(m)
    return dead, renamed, split, splits


def trim_dangling(b, rounds=400):
    """repeatedly remove track segments and vias that end in nothing (the stubs left by removed parts)"""
    total = 0
    for i in range(rounds):
        b.BuildConnectivity()
        conn = b.GetConnectivity()
        dang = [t for t in b.GetTracks() if conn.TestTrackEndpointDangling(t, False)]
        if not dang:
            break
        for t in dang:
            drop(b, t)
        total += len(dang)
    return total, i


def outline(b):
    for d in list(b.GetDrawings()):
        if d.GetLayer() == pcbnew.Edge_Cuts:
            drop(b, d)
    r = CORNER_R
    pts = [((r, 0), (W - r, 0)), ((W, r), (W, H - r)), ((W - r, H), (r, H)), ((0, H - r), (0, r))]
    for (x0, y0), (x1, y1) in pts:
        s = pcbnew.PCB_SHAPE(b)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(x0, y0))
        s.SetEnd(P(x1, y1))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(MM(0.1))
        b.Add(s)
    k = r * (1 - math.sqrt(0.5))
    for (sx, sy), (mx, my), (ex, ey) in (((0, r), (k, k), (r, 0)), ((W - r, 0), (W - k, k), (W, r)),
                                         ((W, H - r), (W - k, H - k), (W - r, H)), ((r, H), (k, H - k), (0, H - r))):
        s = pcbnew.PCB_SHAPE(b)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(P(sx, sy), P(mx, my), P(ex, ey))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(MM(0.1))
        b.Add(s)


def extend_planes(b):
    """Antmicro's full-board GND planes grow into the new strip"""
    n = 0
    strip = pcbnew.SHAPE_POLY_SET()
    strip.NewOutline()
    for x, y in ((0.3, OLD_H - 2.0), (W - 0.3, OLD_H - 2.0), (W - 0.3, H - 0.3), (0.3, H - 0.3)):
        strip.Append(MM(OX + x), MM(OY - y))
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != 'GND':
            continue
        bb = z.GetBoundingBox()
        if ToMM(bb.GetWidth()) > 100 and ToMM(bb.GetHeight()) > 50:
            ol = z.Outline()
            ol.BooleanAdd(strip)
            ol.Simplify()
            n += 1
    return n


# ----------------------------------------------------------------------------- main
def main():
    geom_only = '--geom' in sys.argv
    comps, pad_net, nets = read_netlist(NETLIST)
    parts = {p['ref']: p for p in json.load(open(PARTS))['parts']}
    b = pcbnew.LoadBoard(VENDOR_PCB)
    gone = remove_footprints(b, comps)
    log('removed', len(gone), 'footprints')
    have = {fp.GetReference() for fp in b.GetFootprints()}
    missing = sorted(r for r in comps if r not in have and r not in parts)
    if missing:
        raise SystemExit('in the netlist but neither on the board nor new: ' + ', '.join(missing[:30]))

    if geom_only:
        # the same clean-up as the real run, so the copper left over is what the new parts must avoid
        mapping, changed, net = renet(b, pad_net)
        remap_copper(b, mapping, net)
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
        n, rounds = trim_dangling(b)
        log('geom: trimmed', n, 'stubs')
        cu = {'tracks': [], 'vias': [], 'zones': []}
        names = {pcbnew.F_Cu: 'F', pcbnew.B_Cu: 'B'}
        for t in b.GetTracks():
            if t.Type() == pcbnew.PCB_VIA_T:
                x, y = back(t.GetPosition())
                try:
                    wv = t.GetWidth(pcbnew.F_Cu)
                except TypeError:
                    wv = t.GetWidth()
                cu['vias'].append({'x': x, 'y': y, 'r': ToMM(wv) / 2, 'net': t.GetNetname()})
            elif t.GetLayer() in names:
                cu['tracks'].append({'layer': names[t.GetLayer()], 'a': back(t.GetStart()), 'b': back(t.GetEnd()),
                                     'w': ToMM(t.GetWidth()), 'net': t.GetNetname()})
        for z in b.Zones():
            if z.GetIsRuleArea() or z.GetNetname() in ('GND', ''):
                continue
            for lay, nm in names.items():
                if z.IsOnLayer(lay):
                    cu['zones'].append({'layer': nm, 'net': z.GetNetname(), 'bb': box_local(z.GetBoundingBox())})
        json.dump(cu, open(os.path.join(BDIR, 'out', F.PROJECT + '_copper_obstacles.json'), 'w'))
        log('geom: copper left on the outer layers:', len(cu['tracks']), 'tracks', len(cu['vias']), 'vias',
            len(cu['zones']), 'power pours')
        g = {'size': [W, H], 'fps': []}
        for ref, p in parts.items():
            fp = new_footprint(b, p)
            b.Add(fp)
            fp.SetPosition(P(-50, -50))
            g['fps'].append(geom_entry(fp))
        os.makedirs(os.path.join(BDIR, 'out'), exist_ok=True)
        json.dump(g, open(os.path.join(BDIR, 'out', F.PROJECT + '_geom.json'), 'w'))
        obs = []
        for fp in b.GetFootprints():
            if fp.GetReference() in parts:
                continue
            e = geom_entry(fp)
            e['pth'] = any(pd.GetDrillSize().x > 0 for pd in fp.Pads())
            e['holes'] = [{'c': back(pd.GetPosition()), 'r': ToMM(max(pd.GetSize().x, pd.GetSize().y,
                                                                           pd.GetDrillSize().x)) / 2}
                          for pd in fp.Pads() if pd.GetDrillSize().x > 0]
            obs.append(e)
        json.dump(obs, open(os.path.join(BDIR, 'out', F.PROJECT + '_obstacles.json'), 'w'))
        log('geometry of', len(parts), 'new parts and', len(obs), 'Antmicro footprints written')
        return

    mapping, changed, net = renet(b, pad_net)
    log('pads renetted:', changed)
    for refs in getattr(F, 'DNP_REFS', {}).values():
        for r in refs:
            fp = b.FindFootprintByReference(r)
            if fp:
                fp.SetDNP(True)                      # as in the forked schematic
                fp.SetExcludedFromBOM(True)
    dead, renamed, split, splits = remap_copper(b, mapping, net)
    log('copper items: dead-net removed', dead, 'renamed', renamed, 'on split nets', split)
    for k, v in splits.items():
        log('  split net', k, v)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    n, rounds = trim_dangling(b)
    log('dangling track/via stubs removed:', n, 'in', rounds, 'rounds')
    drilled = 0
    for t in b.GetTracks():
        t.SetLocked(True)            # Antmicro's routing: fixed for the autorouter, kept by the session import
        if t.Type() == pcbnew.PCB_VIA_T and t.GetDrillValue() < MM(F.VIA_DRILL):
            t.SetDrill(MM(F.VIA_DRILL))          # see fork_config.VIA_DRILL
            drilled += 1
    log('vias opened to', F.VIA_DRILL, 'mm drill:', drilled)
    outline(b)

    # the Atlas parts
    placement = json.load(open(os.path.join(BDIR, 'out', F.PROJECT + '_placement.json')))
    for ref, p in parts.items():
        fp = new_footprint(b, p)
        b.Add(fp)
        for pd in fp.Pads():
            n_ = pad_net.get((ref, pd.GetNumber()))
            if n_:
                pd.SetNet(net(n_))
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
        fp.SetExcludedFromBOM(p['fields'].get('in_bom') == 'no')
        rf = fp.Reference()
        rf.SetTextSize(VECTOR2I(MM(0.8), MM(0.8)))
        rf.SetTextThickness(MM(0.12))
        fp.Value().SetVisible(False)
        v = placement[ref]
        if v['side'] == 'B':
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetOrientationDegrees(v['rot'])
        fp.SetPosition(P(v['x'], v['y']))
        if not ref.startswith(('J', 'U', 'H')):
            fp.Reference().SetLayer(pcbnew.B_Fab if fp.IsFlipped() else pcbnew.F_Fab)
    log('added', len(parts), 'Atlas parts')

    # copper from layout.copper() (same JSON as the drive board)
    cu_path = os.path.join(BDIR, 'out', F.PROJECT + '_copper.json')
    cu = json.load(open(cu_path)) if os.path.exists(cu_path) else {'zones': [], 'vias': [], 'tracks': [], 'rules': []}

    def xy(x, y):
        return (MM(OX + x), MM(OY - y))
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
    log('copper:', len(cu['zones']), 'zones', len(cu['vias']), 'vias', len(cu['tracks']), 'tracks', len(cu.get('rules', [])), 'rule areas')
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(OUT_PCB, b, True)          # keep fork.py's project file (classes, rules): this board came from Antmicro's
    log('saved', OUT_PCB, len(b.GetFootprints()), 'footprints', len(b.GetTracks()), 'tracks+vias', len(b.Zones()), 'zones')


if __name__ == '__main__':
    main()
