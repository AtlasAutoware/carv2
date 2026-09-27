"""Write a board's net classes (layout.NETCLASSES) into its KiCad project file, the same way build_pcb.py
does, without rebuilding the board. Plain Python; run it before DRC after changing a net class.

    python3 set_netclasses.py drive
"""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
board = sys.argv[1]
bdir = os.path.abspath(os.path.join(HERE, '..', board))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location('layout', os.path.join(bdir, 'layout.py'))
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)
NETCLASSES = getattr(L, 'NETCLASSES', {})
pro = os.path.join(bdir, f'{L.NAME}.kicad_pro')
P = json.load(open(pro))
ns = P.setdefault('net_settings', {})
classes = [c for c in ns.get('classes', []) if c.get('name') == 'Default' or c.get('name') not in NETCLASSES]
names = {c.get('name') for c in classes}
for name, c in NETCLASSES.items():
    classes.append({'name': name, 'clearance': c['clearance'], 'track_width': c['width'],
                    'via_diameter': c.get('via', 0.6), 'via_drill': c.get('drill', 0.3),
                    'diff_pair_width': 0.2, 'diff_pair_gap': 0.25, 'wire_width': 6, 'bus_width': 12,
                    'line_style': 0, 'priority': len(classes)})
ns['classes'] = classes
keep = [p for p in ns.get('netclass_patterns', []) if p.get('netclass') not in NETCLASSES]
ns['netclass_patterns'] = keep + [{'netclass': name, 'pattern': n} for name, c in NETCLASSES.items() for n in c['nets']]
rules = P.setdefault('board', {}).setdefault('design_settings', {}).setdefault('rules', {})
low = min([c['clearance'] for c in NETCLASSES.values()] + [rules.get('min_clearance', 0.15)])
rules['min_clearance'] = low          # the board-wide floor may not sit above a class's own clearance
json.dump(P, open(pro, 'w'), indent=2)
print('net classes in', os.path.basename(pro) + ':', ', '.join(c['name'] for c in classes))
