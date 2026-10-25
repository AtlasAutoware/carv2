"""Small differences between KiCad 7 and KiCad 9/10 pcbnew that the K tools meet (KiCad Python).

The tools were written against KiCad 10 (flatpak, the team laptop). The build container has KiCad 7.0.11
(Debian), whose Python API differs in a few places. Each helper here keeps the KiCad 10 call as it was and
falls back to the KiCad 7 one, so the same scripts run on both. See boards/tools/README.md for the list.
"""
import pcbnew

VERSION = pcbnew.GetBuildVersion()
MAJOR = int(VERSION.split('.')[0]) if VERSION[:1].isdigit() else 10
K7 = MAJOR < 8


def flip(fp):
    """put a top-side footprint on the bottom, mirrored left-right (KiCad 9+: FLIP_DIRECTION enum;
    KiCad 7: a bool, True = left-right)"""
    fp.Flip(fp.GetPosition(), getattr(pcbnew, 'FLIP_DIRECTION_LEFT_RIGHT', True))


def set_field(fp, key, value, layer=None, visible=False):
    """a user field on a footprint. KiCad 8+: a PCB_FIELD (hidden, on `layer`); KiCad 7: a footprint
    property (plain key/value, no layer or visibility of its own)"""
    if hasattr(fp, 'SetField'):
        if key in ('Description', 'Datasheet'):
            f = fp.GetField(key)
            if f:
                f.SetText(str(value))
                return
        fp.SetField(key, str(value))
        f = fp.GetField(key)
        f.SetVisible(visible)
        if layer is not None:
            f.SetLayer(layer)
    else:
        fp.SetProperty(key, str(value))


def get_field(fp, key, default=''):
    if hasattr(fp, 'HasField'):
        return fp.GetFieldText(key) if fp.HasField(key) else default
    return fp.GetProperty(key) if fp.HasProperty(key) else default


def set_dnp(fp, dnp=True):
    """KiCad 8+ has a DNP attribute; KiCad 7 has none, so the part keeps a 'DNP' property and is left out
    of the position files (the BOM tools read the property)"""
    if hasattr(fp, 'SetDNP'):
        fp.SetDNP(dnp)
    elif dnp:
        fp.SetProperty('DNP', 'DNP')
    else:
        try:
            fp.RemoveProperty('DNP')
        except Exception:
            pass
    fp.SetExcludedFromPosFiles(bool(dnp))


def is_dnp(fp):
    if hasattr(fp, 'IsDNP'):
        return bool(fp.IsDNP())
    return fp.HasProperty('DNP')


def fp_bbox(fp):
    """footprint bounding box without its texts (KiCad 7 takes two flags, KiCad 9+ one)"""
    try:
        return fp.GetBoundingBox(False)
    except TypeError:
        return fp.GetBoundingBox(False, False)


def courtyard(fp, layer):
    """the footprint's courtyard polygon set; KiCad 7 caches it at load, so rebuild it after a move"""
    if K7:
        fp.BuildCourtyardCaches()
    return fp.GetCourtyard(layer)


def via_width(v, layer=None):
    """KiCad 9+ vias have a width per layer; KiCad 7 one width"""
    try:
        return v.GetWidth(pcbnew.F_Cu if layer is None else layer)
    except TypeError:
        return v.GetWidth()


def board_outline(b):
    """the board outline as a SHAPE_POLY_SET (KiCad 7: (polys, error handler, arcs); KiCad 9+: (polys, infer))"""
    outline = pcbnew.SHAPE_POLY_SET()
    try:
        b.GetBoardPolygonOutlines(outline, True)
    except TypeError:
        b.GetBoardPolygonOutlines(outline)
    return outline


def is_text(item):
    """a text item inside a footprint (KiCad 7: FP_TEXT; KiCad 8+: PCB_TEXT / PCB_FIELD)"""
    t = item.Type()
    return t in (pcbnew.PCB_TEXT_T, getattr(pcbnew, 'PCB_FP_TEXT_T', -1), getattr(pcbnew, 'PCB_FIELD_T', -1))


def save(path, b):
    """save the board. KiCad 7's SaveBoard also writes the project file from the board's (empty, for a board
    built in Python) project, which would wipe the net classes and the schematic's settings in the
    .kicad_pro, so on KiCad 7 the project file is left alone (the tools write it as JSON)."""
    if K7:
        return pcbnew.SaveBoard(path, b, True)
    return pcbnew.SaveBoard(path, b)


def netclass_setup(b, default, classes):
    """net classes in the board's design settings. default/classes: {'clearance','width','via','drill'} mm,
    classes also 'nets'. KiCad 9+: classes and pattern assignments in the board's NET_SETTINGS. KiCad 7
    keeps the pattern assignments in the project only (not reachable from Python), so there each net gets
    its class directly; the .kicad_pro written by build_pcb.py / set_netclasses.py carries the patterns for
    the next load."""
    MM = pcbnew.FromMM
    ds = b.GetDesignSettings()
    nset = ds.m_NetSettings

    def fill(nc, c):
        nc.SetClearance(MM(c['clearance']))
        nc.SetTrackWidth(MM(c['width']))
        nc.SetViaDiameter(MM(c.get('via', 0.6)))
        nc.SetViaDrill(MM(c.get('drill', 0.3)))

    if hasattr(nset, 'GetDefaultNetclass'):
        fill(nset.GetDefaultNetclass(), default)
        for name, c in classes.items():
            nc = pcbnew.NETCLASS(name)
            fill(nc, c)
            nset.SetNetclass(name, nc)
            for n in c['nets']:
                nset.SetNetclassPatternAssignment(n, name)
        return
    fill(nset.m_DefaultNetClass, default)
    made = {}
    for name, c in classes.items():
        nc = pcbnew.NETCLASS(name)
        fill(nc, c)
        nset.m_NetClasses[name] = nc
        made[name] = nset.m_NetClasses[name]
    by_net = {n: name for name, c in classes.items() for n in c['nets']}
    for ni in b.GetNetsByName().values():
        cname = by_net.get(ni.GetNetname())
        if cname:
            ni.SetNetClass(made[cname])
