"""Build the ATLAS-BRN-1 schematic: Antmicro's baseboard sheets (vendor/antmicro) with the changes in
fork_config.py, plus the Atlas sheets from design.py hung from Antmicro's root sheet.

    python3 fork.py            (writes atlas_brain.kicad_sch and its sheets next to this file)

Nothing in vendor/ is edited. The output sheets keep Antmicro's file names and UUIDs, so the
footprints on Antmicro's board still find their symbols.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
import eda  # noqa: E402
from sexp import parse, dump, find, find1, q, uq  # noqa: E402
import fork_config as F  # noqa: E402

VENDOR = os.path.join(HERE, 'vendor', 'antmicro')
SHEET_NAMES = {'BA_STACK': 'Atlas stack', 'BB_EFUSE': 'Atlas eFuse', 'BC_POE': 'Atlas PoE', 'BD_LAN': 'Atlas LAN'}
OUT = HERE


def load(name):
    return parse(open(os.path.join(VENDOR, name)).read())[0]


def save(tree, name):
    s = dump(tree)
    s = s.replace(q(F.ANTMICRO_PROJECT), q(F.PROJECT))
    open(os.path.join(OUT, name), 'w').write(s + '\n')


def sym_ref(sym):
    inst = find1(sym, 'instances')
    if inst:
        for pr in find(inst, 'project'):
            for pa in find(pr, 'path'):
                r = find1(pa, 'reference')
                if r:
                    return uq(r[1])
    for p in find(sym, 'property'):
        if uq(p[1]) == 'Reference':
            return uq(p[2])
    return None


def to_global(label, new):
    """(label "X" (at ..) (effects ..) (uuid ..)) -> global label named new, passive shape"""
    at = find1(label, 'at')
    eff = find1(label, 'effects')
    uid = find1(label, 'uuid')
    eff = [e for e in eff]
    just = find1(eff, 'justify')
    if just:
        just[:] = [x for x in just if x != 'bottom']
    return ['global_label', q(new), ['shape', 'passive'], at, ['fields_autoplaced', 'yes'], eff, uid,
            ['property', '"Intersheetrefs"', '"${INTERSHEET_REFS}"', ['at', at[1], at[2], '0'],
             ['effects', ['font', ['size', '1.27', '1.27']], ['hide', 'yes']]]]


def fork_sheet(name, stats):
    t = load(name)
    rm = set(F.REMOVE_REFS.get(name, []))
    ren = F.RENAME_GLOBAL.get(name, {})
    l2g = F.LOCAL_TO_GLOBAL.get(name, {})
    out = []
    gone = set()
    for e in t:
        if isinstance(e, list) and e and e[0] == 'symbol' and find1(e, 'lib_id'):
            r = sym_ref(e)
            if r in rm:
                gone.add(r)
                continue
        if isinstance(e, list) and e and e[0] == 'global_label' and uq(e[1]) in ren:
            new = ren[uq(e[1])]
            if new is None:
                stats['labels_deleted'] += 1
                continue
            e = list(e)
            e[1] = q(new)
            stats['labels_renamed'] += 1
        if isinstance(e, list) and e and e[0] == 'label' and uq(e[1]) in l2g:
            e = to_global(e, l2g[uq(e[1])])
            stats['labels_to_global'] += 1
        out.append(e)
    missing = rm - gone
    if missing:
        raise SystemExit(f'{name}: refs to remove not found: {sorted(missing)}')
    stats['symbols_removed'] += len(gone)
    save(out, name)


def main():
    stats = dict(symbols_removed=0, labels_renamed=0, labels_deleted=0, labels_to_global=0)
    root = load(F.ANTMICRO_PROJECT + '.kicad_sch')
    root_uuid = uq(find1(root, 'uuid')[1])
    kept, freed = [], []
    for s in find(root, 'sheet'):
        nm = [uq(p[2]) for p in find(s, 'property') if uq(p[1]) == 'Sheetname'][0]
        fn = [uq(p[2]) for p in find(s, 'property') if uq(p[1]) == 'Sheetfile'][0]
        page = uq(find1(find1(find1(find1(s, 'instances'), 'project'), 'path'), 'page')[1])
        at = find1(s, 'at')
        (freed if nm in F.REMOVE_SHEETS else kept).append((nm, fn, page, float(at[1]), float(at[2])))
    for nm, fn, page, x, y in kept:
        fork_sheet(fn, stats)

    # the Atlas sheets
    spec_d = os.path.join(HERE, 'design.py')
    import importlib.util
    spec = importlib.util.spec_from_file_location('design', spec_d)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    d = mod.d
    _, sheets = eda.write_schematic(d, OUT, project=F.PROJECT, root_uuid=root_uuid, flags=False, root=False)
    eda.export_json(d, os.path.join(OUT, d.name + '_parts.json'), root_uuid)
    eda.write_symbol_lib(d, os.path.join(OUT, 'atlas.kicad_sym'))

    # root: drop the removed sheet symbols, put the Atlas sheets in their places
    slots = sorted(freed, key=lambda f: int(f[2]))
    if len(slots) < len(sheets):
        raise SystemExit('not enough free sheet slots')
    new_root = []
    rname = F.ANTMICRO_PROJECT + '.kicad_sch'
    rm_root = set(F.REMOVE_REFS.get(rname, []))
    dnp_root = set(getattr(F, 'DNP_REFS', {}).get(rname, []))
    for e in root:
        if isinstance(e, list) and e and e[0] == 'symbol' and find1(e, 'lib_id'):
            r = sym_ref(e)
            if r in rm_root:
                stats['symbols_removed'] += 1
                continue
            if r in dnp_root:
                e = [x for x in e]
                for i, x in enumerate(e):
                    if isinstance(x, list) and x and x[0] == 'dnp':
                        e[i] = ['dnp', 'yes']
                    if isinstance(x, list) and x and x[0] == 'in_bom':
                        e[i] = ['in_bom', 'no']
                stats['dnp'] = stats.get('dnp', 0) + 1
        if isinstance(e, list) and e and e[0] == 'sheet':
            nm = [uq(p[2]) for p in find(e, 'property') if uq(p[1]) == 'Sheetname'][0]
            if nm in F.REMOVE_SHEETS:
                continue
        if isinstance(e, list) and e and e[0] == 'title_block':
            e = ['title_block', ['title', q('ATLAS-BRN-1 brain board')], ['date', q('2026-09-27')], ['rev', q('0.1')],
                 ['company', q('Atlas Autoware (501c3), Fairfax VA')],
                 ['comment', '1', q(f'Fork of Antmicro jetson-orin-baseboard {F.ANTMICRO_COMMIT} (Apache-2.0)')],
                 ['comment', '2', q('Antmicro sheets: SoM, M.2, Ethernet, Peripherals, Supply (edited, see fork_config.py)')],
                 ['comment', '3', q('Atlas sheets: stack connector, input eFuse, camera PoE, lidar Ethernet')]]
        if isinstance(e, list) and e and e[0] == 'sheet_instances':
            for i, (key, title, fname, su) in enumerate(sheets):
                title = SHEET_NAMES.get(key, title)
                _, _, page, x, y = slots[i]
                sheet = parse(f'''(sheet (at {x:.2f} {y:.2f}) (size 12.7 12.7) (fields_autoplaced yes)
 (stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0.0000)) (uuid {q(su)})
 (property "Sheetname" {q(title.split(':')[0][:40])} (at {x:.2f} {y - 0.7:.2f} 0) (effects (font (size 1.27 1.27)) (justify left bottom)))
 (property "Sheetfile" {q(fname)} (at {x:.2f} {y + 13.3:.2f} 0) (effects (font (size 1.27 1.27)) (justify left top)))
 (instances (project {q(F.PROJECT)} (path {q('/' + root_uuid)} (page {q(page)})))))''')[0]
                new_root.append(sheet)
        new_root.append(e)
    save(new_root, F.PROJECT + '.kicad_sch')

    # project file: Antmicro's settings (net classes, rules), renamed, plus the Atlas classes
    pro = json.load(open(os.path.join(VENDOR, F.ANTMICRO_PROJECT + '.kicad_pro')))
    pro['meta']['filename'] = F.PROJECT + '.kicad_pro'
    ns = pro['net_settings']
    have = {c['name'] for c in ns['classes']}
    for c in F.NEW_CLASSES:
        if c['name'] not in have:
            base = dict(ns['classes'][0])
            base.update(c)
            ns['classes'].append(base)
    for c in ns['classes']:
        if c['name'] == 'PoE':
            c['clearance'] = F.POE_CLEARANCE
        c.update(getattr(F, 'CLASS_PATCH', {}).get(c['name'], {}))
        c['via_drill'] = max(c.get('via_drill', 0), F.VIA_DRILL)
    ds = pro['board']['design_settings']
    ds['rules']['min_through_hole_diameter'] = F.VIA_DRILL
    ds['via_dimensions'] = [v if v['diameter'] == 0 else dict(v, drill=max(v['drill'], F.VIA_DRILL))
                            for v in ds.get('via_dimensions', [])]
    pats = ns.setdefault('netclass_patterns', [])
    pats[:] = [p for p in pats if not any(p['pattern'].startswith('/' + s + '/') for s in F.REMOVE_SHEETS)]
    for cls, pat in F.NETCLASS_PATTERNS:
        pats.append({'netclass': cls, 'pattern': pat})
    ns['netclass_assignments'] = {}
    pro.get('sheets', [])
    pro['sheets'] = [[root_uuid, 'Root']] + [[s[3], SHEET_NAMES.get(s[0], s[0])] for s in sheets] + \
        [s for s in pro.get('sheets', []) if s[0] != root_uuid]
    json.dump(pro, open(os.path.join(OUT, F.PROJECT + '.kicad_pro'), 'w'), indent=2)
    dru = open(os.path.join(VENDOR, F.ANTMICRO_PROJECT + '.kicad_dru')).read()
    i = dru.index('(rule clearance_PoE')
    j = dru.index('mm)', i) + 3
    dru = dru[:i] + re.sub(r'\(min [\d.]+mm\)', f'(min {F.POE_CLEARANCE}mm)', dru[i:j]) + dru[j:]
    dru += ''.join(f'\n(rule "land pattern {r}"\n\t(constraint clearance (min 0.12mm))\n'
                   f'\t(condition "A.memberOfFootprint(\'{r}\') && B.memberOfFootprint(\'{r}\')"))\n'
                   for r in F.LAND_PATTERN_REFS)
    open(os.path.join(OUT, F.PROJECT + '.kicad_dru'), 'w').write(dru)
    eda.write_project_files(OUT, F.PROJECT, fp_libs=(), sym_libs=(('atlas', '${KIPRJMOD}/atlas.kicad_sym'),))
    print('fork:', stats, '| Atlas sheets:', [s[2] for s in sheets], '|', len(d.parts), 'new parts')


if __name__ == '__main__':
    main()
