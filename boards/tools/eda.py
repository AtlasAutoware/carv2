"""Tiny schematic-capture framework used by both boards.

A design is a list of parts. Each part has a symbol (a stock KiCad symbol or a box symbol made
from a pin table), a footprint, a pin -> net map and sourcing fields. write_schematic() turns a
design into a hierarchical KiCad schematic, one sheet per block, where every pin carries a net
label; export_json() hands the same data to the PCB builder that runs inside KiCad's Python.
"""
import json
import math
import os
import uuid

from sexp import parse, dump, find, find1, q, uq

HERE = os.path.dirname(os.path.abspath(__file__))
STOCK_DIR = os.environ.get('KICAD_STOCK_SYMBOLS', os.path.join(HERE, '..', 'lib', 'stock_symbols'))

NS = uuid.UUID('7e1f3c52-6a1d-4b8e-9c3a-2b5d0a9e4f10')


def U(*parts):
    return str(uuid.uuid5(NS, '/'.join(str(p) for p in parts)))


# ----------------------------------------------------------------------------- symbols
class Sym:
    """A library symbol: its s-expression and pin geometry {num: (x, y, ang, name, etype, hidden)}."""

    def __init__(self, libid, sexpr, pins):
        self.libid = libid
        self.sexpr = sexpr
        self.pins = pins

    def bbox(self):
        xs = [p[0] for p in self.pins.values()] or [0]
        ys = [p[1] for p in self.pins.values()] or [0]
        return min(xs), max(xs), min(ys), max(ys)


_stock_cache = {}


def _load_lib(lib):
    if lib not in _stock_cache:
        path = os.path.join(STOCK_DIR, lib + '.kicad_sym')
        root = parse(open(path).read())[0]
        _stock_cache[lib] = {uq(s[1]): s for s in find(root, 'symbol')}
    return _stock_cache[lib]


def _pins_of(sym):
    out = {}

    def walk(x):
        for e in x:
            if isinstance(e, list):
                if e and e[0] == 'pin':
                    at = find1(e, 'at')
                    num = uq(find1(e, 'number')[1])
                    nm = uq(find1(e, 'name')[1])
                    hidden = any(isinstance(h, list) and h[:2] == ['hide', 'yes'] for h in e) or 'hide' in e
                    ang = float(at[3]) if len(at) > 3 else 0.0
                    ln = float(find1(e, 'length')[1])
                    out.setdefault(num, (float(at[1]), float(at[2]), ang, nm, e[1], hidden, ln))
                else:
                    walk(e)
    walk(sym)
    return out


def stock(libid):
    lib, name = libid.split(':')
    syms = _load_lib(lib)
    s = syms[name]
    ext = find1(s, 'extends')
    if ext:
        base_name = uq(ext[1])
        base = syms[base_name]
        props = {uq(p[1]): p for p in find(s, 'property')}
        new = []
        for e in base:
            if isinstance(e, list) and e and e[0] == 'property' and uq(e[1]) in props:
                new.append(props[uq(e[1])])
            elif isinstance(e, list) and e and e[0] == 'symbol':
                sub = list(e)
                sub[1] = q(uq(sub[1]).replace(base_name, name))
                new.append(sub)
            else:
                new.append(e)
        s = new
    s = list(s)
    s[1] = q(libid)
    return Sym(libid, s, _pins_of(s))


P_IN, P_OUT, BIDI, PAS, PWR_IN, PWR_OUT, OC, TRI, NC = (
    'input', 'output', 'bidirectional', 'passive', 'power_in', 'power_out', 'open_collector', 'tri_state', 'no_connect')


class Chip:
    """A box symbol defined by a pin table.

    pins: list of (numbers, name, etype, side); numbers is a str or a list of str (stacked pins),
    side is 'L', 'R', 'T' or 'B'.
    """

    def __init__(self, name, pins, footprint='', ref='U', desc='', datasheet='', mpn='', mfr='', width=None):
        self.name = name
        self.pins = [(([n] if isinstance(n, str) else list(n)), nm, t, sd) for (n, nm, t, sd) in pins]
        self.footprint = footprint
        self.ref = ref
        self.desc = desc
        self.datasheet = datasheet
        self.mpn = mpn
        self.mfr = mfr
        self.width = width
        self._sym = None

    def names(self):
        d = {}
        for nums, nm, t, sd in self.pins:
            d.setdefault(nm, []).extend(nums)
        return d

    def sym(self, lib='atlas'):
        if self._sym:
            return self._sym
        libid = f'{lib}:{self.name}'
        side = {'L': [], 'R': [], 'T': [], 'B': []}
        for p in self.pins:
            side[p[3]].append(p)
        n = max(len(side['L']), len(side['R']), 1)
        h = (n + 1) * 2.54
        maxl = max([len(p[1]) for p in side['L']] + [0])
        maxr = max([len(p[1]) for p in side['R']] + [0])
        w = self.width or max(10.16, math.ceil(((maxl + maxr) * 1.0 + 4) / 2.54) * 2.54,
                              (max(len(side['T']), len(side['B'])) + 1) * 2.54)
        hw = round(w / 2 / 1.27) * 1.27
        ht = math.ceil(h / 2 / 2.54) * 2.54
        pins_sx = []
        geo = {}

        def pin(nums, nm, typ, x, y, ang):
            for k, num in enumerate(nums):
                hide = ' (hide yes)' if k > 0 else ''
                t = typ if (k == 0 or typ == 'no_connect') else 'passive'   # hidden stacked copies must not be power_in (implicit nets)
                pins_sx.append(f'(pin {t} line (at {x:.2f} {y:.2f} {ang}) (length 2.54){hide} '
                               f'(name {q(nm)} (effects (font (size 1.016 1.016)))) '
                               f'(number {q(num)} (effects (font (size 1.016 1.016)))))')
                geo[num] = (x, y, float(ang), nm, typ, k > 0, 2.54)
        for i, (nums, nm, typ, sd) in enumerate(side['L']):
            pin(nums, nm, typ, -hw - 2.54, ht - 2.54 * (i + 1), 0)
        for i, (nums, nm, typ, sd) in enumerate(side['R']):
            pin(nums, nm, typ, hw + 2.54, ht - 2.54 * (i + 1), 180)
        for i, (nums, nm, typ, sd) in enumerate(side['T']):
            x = -2.54 * (len(side['T']) - 1) / 2 + 2.54 * i
            pin(nums, nm, typ, round(x / 1.27) * 1.27, ht + 2.54, 270)
        for i, (nums, nm, typ, sd) in enumerate(side['B']):
            x = -2.54 * (len(side['B']) - 1) / 2 + 2.54 * i
            pin(nums, nm, typ, round(x / 1.27) * 1.27, -ht - 2.54, 90)
        s = f'''(symbol {q(libid)} (pin_names (offset 0.508)) (exclude_from_sim no) (in_bom yes) (on_board yes)
 (property "Reference" {q(self.ref)} (at 0 {ht + 3.81 + (2.54 if side['T'] else 0):.2f} 0) (effects (font (size 1.27 1.27))))
 (property "Value" {q(self.name)} (at 0 {-ht - 3.81 - (2.54 if side['B'] else 0):.2f} 0) (effects (font (size 1.27 1.27))))
 (property "Footprint" {q(self.footprint)} (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
 (property "Datasheet" {q(self.datasheet)} (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
 (property "Description" {q(self.desc)} (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
 (symbol "{self.name}_0_1" (rectangle (start {-hw:.2f} {ht:.2f}) (end {hw:.2f} {-ht:.2f}) (stroke (width 0.254) (type default)) (fill (type background))))
 (symbol "{self.name}_1_1" {' '.join(pins_sx)}))'''
        self._sym = Sym(libid, parse(s)[0], geo)
        return self._sym


# ----------------------------------------------------------------------------- design
class Part:
    def __init__(self, ref, value, sym, footprint, conns, block, fields=None, dnp=False, side='F', note=''):
        self.ref = ref
        self.value = value
        self.sym = sym              # Sym
        self.footprint = footprint
        self.conns = conns          # {pin number: net}
        self.block = block
        self.fields = fields or {}
        self.dnp = dnp
        self.side = side
        self.note = note


class Design:
    def __init__(self, name, title, rev='0.1', company='Atlas Autoware (501c3), Fairfax VA', date='2026-09-27',
                 ref_base=0):
        self.name = name
        self.ref_base = ref_base    # block n numbers its parts from ref_base + 100 n (the brain board starts at 1001)
        self.title = title
        self.rev = rev
        self.company = company
        self.date = date
        self.parts = []
        self.blocks = []            # (key, title, notes)
        self.cur = None
        self.refs = set()
        self.nc_nets = set()
        self._count = {}

    def block(self, key, title, notes=()):
        self.blocks.append((key, title, list(notes)))
        self.cur = key

    def _resolve(self, ref):
        """A bare prefix ('R', 'C', 'TP') gets the next number in the current block: block n uses n01..n99."""
        if any(ch.isdigit() for ch in ref):
            return ref
        base = self.ref_base + 100 * len(self.blocks)
        k = (self.cur, ref)
        self._count[k] = self._count.get(k, 0) + 1
        if self._count[k] > 99:
            raise ValueError(f'more than 99 {ref} in block {self.cur}')
        return f'{ref}{base + self._count[k]}'

    def _add(self, p):
        p.ref = self._resolve(p.ref)
        if p.ref in self.refs:
            raise ValueError('duplicate ref ' + p.ref)
        self.refs.add(p.ref)
        self.parts.append(p)
        return p

    def chip(self, ref, chip, conns, value=None, dnp=False, side='F', mpn=None, mfr=None, desc=None, note='', **fields):
        """conns: {pin name or pin number: net}. Every pin of the chip must be given (None = no connect)."""
        sym = chip.sym()
        names = chip.names()
        pinmap = {}
        for k, net in conns.items():
            if k in names:
                for num in names[k]:
                    pinmap[num] = net
            elif k in sym.pins:
                pinmap[k] = net
            else:
                raise KeyError(f'{ref}: {chip.name} has no pin {k}')
        missing = [n for n in sym.pins if n not in pinmap]
        if missing:
            raise KeyError(f'{ref}: {chip.name} pins not connected: ' + ', '.join(
                f'{n}({sym.pins[n][3]})' for n in missing))
        f = dict(MPN=mpn or chip.mpn, Manufacturer=mfr or chip.mfr, Description=desc or chip.desc)
        f.update(fields)
        return self._add(Part(ref, value or chip.name, sym, chip.footprint, pinmap, self.cur, f, dnp, side, note))

    def stock(self, ref, libid, value, footprint, conns, dnp=False, side='F', mpn='', mfr='', desc='', note='', **fields):
        sym = stock(libid)
        for k in conns:
            if k not in sym.pins:
                raise KeyError(f'{ref}: {libid} has no pin {k}')
        missing = [n for n in sym.pins if n not in conns]
        if missing:
            raise KeyError(f'{ref}: {libid} pins not connected: {missing}')
        f = dict(MPN=mpn, Manufacturer=mfr, Description=desc)
        f.update(fields)
        return self._add(Part(ref, value, sym, footprint, dict(conns), self.cur, f, dnp, side, note))

    # ---- helpers for the common two-pin parts
    def R(self, ref, value, a, b, size='0402', mpn='', desc='', dnp=False, side='F', **kw):
        fp = {'0201': 'Resistor_SMD:R_0201_0603Metric', '0402': 'Resistor_SMD:R_0402_1005Metric',
              '0603': 'Resistor_SMD:R_0603_1608Metric', '0805': 'Resistor_SMD:R_0805_2012Metric',
              '1206': 'Resistor_SMD:R_1206_3216Metric', '2512': 'Resistor_SMD:R_2512_6332Metric'}.get(size, size)
        return self.stock(ref, 'Device:R', value, fp, {'1': a, '2': b}, dnp=dnp, side=side, mpn=mpn,
                          desc=desc or f'resistor {value} {size}', **kw)

    def C(self, ref, value, a, b, size='0402', mpn='', desc='', dnp=False, side='F', **kw):
        fp = {'0201': 'Capacitor_SMD:C_0201_0603Metric', '0402': 'Capacitor_SMD:C_0402_1005Metric',
              '0603': 'Capacitor_SMD:C_0603_1608Metric', '0805': 'Capacitor_SMD:C_0805_2012Metric',
              '1206': 'Capacitor_SMD:C_1206_3216Metric', '1210': 'Capacitor_SMD:C_1210_3225Metric'}.get(size, size)
        return self.stock(ref, 'Device:C', value, fp, {'1': a, '2': b}, dnp=dnp, side=side, mpn=mpn,
                          desc=desc or f'capacitor {value} {size}', **kw)

    def CP(self, ref, value, pos, neg, fp, mpn='', desc='', side='F', **kw):
        return self.stock(ref, 'Device:C_Polarized', value, fp, {'1': pos, '2': neg}, side=side, mpn=mpn, desc=desc, **kw)

    def L(self, ref, value, a, b, fp, mpn='', desc='', side='F', **kw):
        return self.stock(ref, 'Device:L', value, fp, {'1': a, '2': b}, side=side, mpn=mpn, desc=desc, **kw)

    def FB(self, ref, value, a, b, size='0603', mpn='', desc='', side='F', **kw):
        fp = {'0402': 'Inductor_SMD:L_0402_1005Metric', '0603': 'Inductor_SMD:L_0603_1608Metric',
              '0805': 'Inductor_SMD:L_0805_2012Metric'}[size]
        return self.stock(ref, 'Device:FerriteBead', value, fp, {'1': a, '2': b}, side=side, mpn=mpn, desc=desc, **kw)

    def LED(self, ref, color, anode, cathode, size='0603', mpn='', side='F', **kw):
        fp = {'0402': 'LED_SMD:LED_0402_1005Metric', '0603': 'LED_SMD:LED_0603_1608Metric'}[size]
        return self.stock(ref, 'Device:LED', color, fp, {'1': cathode, '2': anode}, side=side, mpn=mpn,
                          desc=f'LED {color} {size}', **kw)

    def D(self, ref, value, anode, cathode, fp, kind='D', mpn='', desc='', side='F', **kw):
        libid = {'D': 'Device:D', 'S': 'Device:D_Schottky', 'Z': 'Device:D_Zener', 'TVS': 'Device:D_TVS'}[kind]
        conns = {'1': cathode, '2': anode} if kind != 'TVS' else {'1': cathode, '2': anode}
        return self.stock(ref, libid, value, fp, conns, side=side, mpn=mpn, desc=desc, **kw)

    def TP(self, ref, net, fp='TestPoint:TestPoint_Pad_D1.0mm', side='F'):
        return self.stock(ref, 'Connector:TestPoint', net, fp, {'1': net}, side=side, desc='test point', in_bom='no')

    # ---- queries
    def nets(self):
        s = {}
        for p in self.parts:
            for num, net in p.conns.items():
                if net is None:
                    continue
                s.setdefault(net, []).append((p.ref, num))
        return s

    def check(self):
        """Nets with a single pin are usually typos."""
        bad = []
        for net, nodes in self.nets().items():
            if len(nodes) < 2 and net not in self.nc_nets:
                bad.append((net, nodes))
        return bad


# ----------------------------------------------------------------------------- schematic writer
PAPERS = [('A4', 297, 210), ('A3', 420, 297), ('A2', 594, 420), ('A1', 841, 594)]


def _xf(px, py, X, Y, rot):
    r = math.radians(rot)
    x = px * math.cos(r) - py * math.sin(r)
    y = px * math.sin(r) + py * math.cos(r)
    return X + x, Y - y


def _snap(v, g=1.27):
    return round(v / g) * g


def _label_len(net):
    return 1.27 * 0.75 * len(net) + 4


def write_schematic(d, outdir, project=None, root_uuid=None, flags=True, root=True):
    """root_uuid: the UUID of the root sheet the block sheets hang from (the brain board hangs them
    from Antmicro's root sheet). flags=False leaves the PWR_FLAGs to the rest of the design.
    root=False writes only the block sheets."""
    project = project or d.name
    os.makedirs(outdir, exist_ok=True)
    root_uuid = root_uuid or U(d.name, 'root')
    nets = d.nets()
    net_blocks = {}
    for p in d.parts:
        for net in p.conns.values():
            if net:
                net_blocks.setdefault(net, set()).add(p.block)
    # power flags: nets with power_in pins and no power_out pin
    flag_nets = []
    for net, nodes in nets.items():
        types = []
        for ref, num in nodes:
            part = next(pp for pp in d.parts if pp.ref == ref)
            types.append(part.sym.pins[num][4])
        if flags and 'power_in' in types and 'power_out' not in types:
            flag_nets.append(net)
    flag_home = {}
    for net in flag_nets:
        for p in d.parts:
            if net in p.conns.values():
                flag_home[net] = p.block
                break

    sheet_files = []
    for bi, (key, title, notes) in enumerate(d.blocks):
        parts = [p for p in d.parts if p.block == key]
        sheet_uuid = U(d.name, 'sheet', key)
        fname = f'{d.name}_{key.lower()}.kicad_sch'
        items = []
        libs = {}
        placed = []
        big = [p for p in parts if len(p.sym.pins) > 4 or p.sym.libid.startswith('atlas:')]
        small = [p for p in parts if p not in big]
        # big parts in rows
        x0, y0 = 25.4, 45.72 + 5.08 * min(len(notes), 14)
        maxw = 540
        x, y, rowh = x0, y0, 0
        for p in big:
            xmin, xmax, ymin, ymax = p.sym.bbox()
            lw = max([_label_len(n) for n in p.conns.values() if n] + [8])
            w = (xmax - xmin) + 2 * lw + 12
            h = (ymax - ymin) + 16
            if x + w > x0 + maxw and x > x0:
                x = x0
                y += rowh
                rowh = 0
            cx = _snap(x + lw + 4 - xmin, 2.54)
            cy = _snap(y + ymax + 8, 2.54)
            placed.append((p, cx, cy, 0))
            x += w
            rowh = max(rowh, h)
        y += rowh + 10
        # small parts on a grid, 2-pin parts turned horizontal
        col, ncol = 0, 7
        cw, ch = 76.2, 12.7
        for p in small:
            cx = _snap(x0 + 30 + col * cw, 2.54)
            rot = 90 if len(p.sym.pins) == 2 else 0
            placed.append((p, cx, _snap(y, 2.54), rot))
            col += 1
            if col >= ncol:
                col = 0
                y += ch if len(p.sym.pins) <= 2 else 20.32
        ymax_used = y + 30
        paper = next(pp for pp in PAPERS if pp[1] >= x0 + maxw * 0.9 and pp[2] >= ymax_used) if ymax_used < 594 else PAPERS[-1]
        if ymax_used <= 420 and paper[0] == 'A1':
            paper = PAPERS[2]
        # title and notes
        items.append(f'(text {q(title)} (exclude_from_sim no) (at 25.4 25.4 0) (effects (font (size 3 3) (thickness 0.5) bold) (justify left)) (uuid {q(U(d.name, key, "title"))}))')
        for i, t in enumerate(notes[:14]):
            items.append(f'(text {q(t)} (exclude_from_sim no) (at 25.4 {33.02 + i * 5.08} 0) (effects (font (size 1.8 1.8)) (justify left)) (uuid {q(U(d.name, key, "note", i))}))')
        for p, X, Y, rot in placed:
            libs[p.sym.libid] = p.sym
            su = U(d.name, 'sym', p.ref)
            props = []

            def prop(k, v, dx=0.0, dy=0.0, hide=False, size=1.27):
                props.append(f'(property {q(k)} {q(v)} (at {X + dx:.2f} {Y + dy:.2f} 0) (effects (font (size {size} {size})) {"(hide yes)" if hide else ""}))')
            if rot == 90:
                prop('Reference', p.ref, 0, -2.54)
                prop('Value', p.value, 0, 2.54, size=1.0)
            else:
                xmin, xmax, ymin, ymax = p.sym.bbox()
                prop('Reference', p.ref, 0, -ymax - 3.5)
                prop('Value', p.value, 0, -ymin + 3.5)
            prop('Footprint', p.footprint, hide=True)
            prop('Datasheet', p.fields.get('Datasheet', ''), hide=True)
            for k, v in p.fields.items():
                if k in ('Datasheet', 'in_bom'):
                    continue
                prop(k, v or '', hide=True)
            pin_uuids = ' '.join(f'(pin {q(n)} (uuid {q(U(d.name, p.ref, "pin", n))}))' for n in p.sym.pins)
            in_bom = 'no' if p.fields.get('in_bom') == 'no' else 'yes'
            items.append(f'''(symbol (lib_id {q(p.sym.libid)}) (at {X:.2f} {Y:.2f} {rot}) (unit 1) (exclude_from_sim no) (in_bom {in_bom}) (on_board yes) (dnp {"yes" if p.dnp else "no"}) (uuid {q(su)})
 {' '.join(props)} {pin_uuids}
 (instances (project {q(project)} (path {q("/" + root_uuid + "/" + sheet_uuid)} (reference {q(p.ref)}) (unit 1)))))''')
            done_pts = set()
            for num, (px, py, ang, nm, typ, hidden, ln) in p.sym.pins.items():
                net = p.conns.get(num)
                sx, sy = _xf(px, py, X, Y, rot)
                sx, sy = round(sx, 2), round(sy, 2)
                if (sx, sy) in done_pts:
                    continue
                done_pts.add((sx, sy))
                if net is None:
                    items.append(f'(no_connect (at {sx} {sy}) (uuid {q(U(d.name, p.ref, "nc", num))}))')
                    continue
                la = int((ang + 180 + rot) % 360)
                glob = True   # every net by its plain name, so the board's net names match the schematic's
                just = 'left' if la in (0, 90) else 'right'
                if glob:
                    items.append(f'(global_label {q(net)} (shape passive) (at {sx} {sy} {la}) (fields_autoplaced yes) (effects (font (size 1.27 1.27)) (justify {just})) (uuid {q(U(d.name, p.ref, "lbl", num))}) (property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {sx} {sy} 0) (effects (font (size 1.27 1.27)) (hide yes))))')
                else:
                    items.append(f'(label {q(net)} (at {sx} {sy} {la}) (fields_autoplaced yes) (effects (font (size 1.27 1.27)) (justify {just} bottom)) (uuid {q(U(d.name, p.ref, "lbl", num))}))')
        # power flags that live on this sheet
        fx = 25.4
        fy = _snap(ymax_used - 10, 2.54)
        for i, net in enumerate([n for n in flag_nets if flag_home.get(n) == key]):
            X = _snap(fx + 25.4 * i, 2.54)
            libs['power:PWR_FLAG'] = stock('power:PWR_FLAG')
            su = U(d.name, 'flag', net)
            items.append(f'''(symbol (lib_id "power:PWR_FLAG") (at {X} {fy} 0) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (uuid {q(su)})
 (property "Reference" "#FLG{bi:02d}{i:02d}" (at {X} {fy - 3.81} 0) (effects (font (size 1.27 1.27)) (hide yes)))
 (property "Value" "PWR_FLAG" (at {X} {fy - 5.5} 0) (effects (font (size 1.0 1.0))))
 (property "Footprint" "" (at {X} {fy} 0) (effects (font (size 1.27 1.27)) (hide yes)))
 (property "Datasheet" "" (at {X} {fy} 0) (effects (font (size 1.27 1.27)) (hide yes)))
 (pin "1" (uuid {q(U(d.name, "flagpin", net))}))
 (instances (project {q(project)} (path {q("/" + root_uuid + "/" + sheet_uuid)} (reference "#FLG{bi:02d}{i:02d}") (unit 1)))))''')
            items.append(f'(global_label {q(net)} (shape passive) (at {X} {fy} 270) (fields_autoplaced yes) (effects (font (size 1.27 1.27)) (justify right)) (uuid {q(U(d.name, "flaglbl", net))}) (property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {X} {fy} 0) (effects (font (size 1.27 1.27)) (hide yes))))')
        lib_sx = '\n'.join(dump(s.sexpr, 1) for s in libs.values())
        sch = f'''(kicad_sch (version 20250114) (generator "eeschema") (generator_version "9.0")
 (uuid {q(sheet_uuid)})
 (paper {q(paper[0])})
 (title_block (title {q(d.title + ": " + title)}) (date {q(d.date)}) (rev {q(d.rev)}) (company {q(d.company)}) (comment 1 "Generated from design.py by tools/eda.py; edit the Python, not this file"))
 (lib_symbols {lib_sx})
 {chr(10).join(items)}
 (embedded_fonts no))
'''
        open(os.path.join(outdir, fname), 'w').write(sch)
        sheet_files.append((key, title, fname, sheet_uuid))
    if not root:
        return root_uuid, sheet_files
    # root sheet with one sheet symbol per block
    items = []
    for i, (key, title, fname, su) in enumerate(sheet_files):
        cx = 25.4 + (i % 4) * 96.52
        cy = 50.8 + (i // 4) * 38.1
        items.append(f'''(sheet (at {cx:.2f} {cy:.2f}) (size 83.82 25.4) (fields_autoplaced yes) (stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0.0000)) (uuid {q(su)})
 (property "Sheetname" {q(key + " " + title[:48])} (at {cx:.2f} {cy - 0.7:.2f} 0) (effects (font (size 1.27 1.27)) (justify left bottom)))
 (property "Sheetfile" {q(fname)} (at {cx:.2f} {cy + 26:.2f} 0) (effects (font (size 1.27 1.27)) (justify left top)))
 (instances (project {q(project)} (path {q("/" + root_uuid)} (page {q(str(i + 2))})))))''')
    root = f'''(kicad_sch (version 20250114) (generator "eeschema") (generator_version "9.0")
 (uuid {q(root_uuid)})
 (paper "A3")
 (title_block (title {q(d.title)}) (date {q(d.date)}) (rev {q(d.rev)}) (company {q(d.company)}) (comment 1 "Generated from design.py by tools/eda.py; edit the Python, not this file"))
 (lib_symbols)
 (text {q(d.title)} (exclude_from_sim no) (at 25.4 30 0) (effects (font (size 4 4) (thickness 0.6) bold) (justify left)) (uuid {q(U(d.name, "roottitle"))}))
 {chr(10).join(items)}
 (sheet_instances (path "/" (page "1")))
 (embedded_fonts no))
'''
    open(os.path.join(outdir, f'{project}.kicad_sch'), 'w').write(root)
    return root_uuid, sheet_files


def _primaries(pins):
    """{pin number: number of the visible pin stacked at the same spot}. KiCad names the net of a
    stacked group after that pin, so the board needs the same mapping for no-connect pads."""
    vis = {(round(v[0], 3), round(v[1], 3)): k for k, v in pins.items() if not v[5]}
    return {k: k if v[4] == 'no_connect' else vis.get((round(v[0], 3), round(v[1], 3)), k)   # NC pins never join
            for k, v in pins.items()}


def export_json(d, path, root_uuid=None):
    root_uuid = root_uuid or U(d.name, 'root')
    out = []
    for p in d.parts:
        out.append(dict(ref=p.ref, value=p.value, footprint=p.footprint,
                        pads={k: v for k, v in p.conns.items()}, block=p.block, dnp=p.dnp, side=p.side,
                        fields={k: (v or '') for k, v in p.fields.items()},
                        path='/' + U(d.name, 'sheet', p.block) + '/' + U(d.name, 'sym', p.ref),
                        sheetfile=f'{d.name}_{p.block.lower()}.kicad_sch',
                        pintypes={k: v[4] for k, v in p.sym.pins.items()},
                        pinnames={k: v[3] for k, v in p.sym.pins.items()},
                        pinprimary=_primaries(p.sym.pins)))
    json.dump(dict(name=d.name, parts=out, nets=sorted(d.nets())), open(path, 'w'), indent=0)
    return out


def write_symbol_lib(d, path, lib='atlas'):
    """Library file with every box symbol the design uses, so the schematic stays editable in KiCad."""
    seen = {}
    for p in d.parts:
        if p.sym.libid.startswith(lib + ':'):
            seen[p.sym.libid] = p.sym
    body = '\n'.join(dump(s.sexpr, 1).replace(f'"{lib}:', '"', 1) for s in seen.values())
    open(path, 'w').write(f'(kicad_symbol_lib (version 20241209) (generator "atlas_eda") (generator_version "9.0")\n{body})\n')
    return len(seen)


def write_project_files(outdir, project, fp_libs=(('atlas', '${KIPRJMOD}/../lib/atlas.pretty'),),
                        sym_libs=(('atlas', '${KIPRJMOD}/atlas.kicad_sym'),)):
    fl = '\n'.join(f'  (lib (name "{n}")(type "KiCad")(uri "{u}")(options "")(descr ""))' for n, u in fp_libs)
    sl = '\n'.join(f'  (lib (name "{n}")(type "KiCad")(uri "{u}")(options "")(descr ""))' for n, u in sym_libs)
    open(os.path.join(outdir, 'fp-lib-table'), 'w').write(f'(fp_lib_table\n  (version 7)\n{fl}\n)\n')
    open(os.path.join(outdir, 'sym-lib-table'), 'w').write(f'(sym_lib_table\n  (version 7)\n{sl}\n)\n')


def write_kicad_pro(outdir, project, text_vars=None):
    pro = {
        "meta": {"filename": f"{project}.kicad_pro", "version": 3},
        "board": {"design_settings": {"defaults": {}, "rules": {}}},
        "erc": {"rule_severities": {"lib_symbol_issues": "ignore", "lib_symbol_mismatch": "ignore",
                                    "footprint_link_issues": "ignore", "single_global_label": "ignore",
                                    "unconnected_wire_endpoint": "warning", "simulation_model_issue": "ignore"}},
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "net_settings": {"classes": [{"name": "Default", "clearance": 0.15, "track_width": 0.2, "via_diameter": 0.6,
                                      "via_drill": 0.3, "diff_pair_width": 0.2, "diff_pair_gap": 0.15}],
                         "meta": {"version": 3}},
        "schematic": {"meta": {"version": 1}},
        "text_variables": text_vars or {},
    }
    json.dump(pro, open(os.path.join(outdir, f'{project}.kicad_pro'), 'w'), indent=2)
