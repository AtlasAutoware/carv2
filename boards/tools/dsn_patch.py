"""Adjust a Specctra DSN before routing (plain Python).

    python3 dsn_patch.py drive IN.dsn OUT.dsn [--ignore-gnd]

- Net classes follow boards/<board>/layout.py NETCLASSES, whatever the board file last wrote, so a
  class change needs no board rebuild before the next routing round.
- --ignore-gnd moves GND into a class of its own, GndPlane, for Freerouting's -inc option: every GND
  pad reaches its plane through a fixed via already, and the router then spends its passes on signals.
"""
import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
board, src, dst = sys.argv[1:4]
spec = importlib.util.spec_from_file_location('layout', os.path.join(HERE, '..', board, 'layout.py'))
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)
s = open(src).read()

# class blocks: "(class NAME[,ALIAS...] net net ... (circuit" ... up to the block's closing paren
blocks = []
for m in re.finditer(r'\(class ([^\s()]+)', s):
    i = m.start()
    j = s.index('(circuit', i)
    depth, k = 0, i
    while True:
        if s[k] == '(':
            depth += 1
        elif s[k] == ')':
            depth -= 1
            if depth == 0:
                break
        k += 1
    blocks.append({'start': i, 'nets_end': j, 'end': k + 1, 'name': m.group(1).split(',')[0],
                   'nets': s[m.end():j].split(), 'tail': s[j:k + 1]})
want = {}
for cname, c in getattr(L, 'NETCLASSES', {}).items():
    for n in c['nets']:
        want[n] = cname
if '--ignore-gnd' in sys.argv:
    want['GND'] = 'GndPlane'
names = {b['name'] for b in blocks}
moved = 0
for b in blocks:
    keep = []
    for n in b['nets']:
        target = want.get(n.strip('"'))
        if target and target != b['name'] and (target in names or target == 'GndPlane'):
            moved += 1
        else:
            keep.append(n)
    b['nets'] = keep
for b in blocks:
    b['nets'] += [n for n, t in want.items() if t == b['name'] and n not in b['nets'] and re.search(
        r'\(net "?%s"?[\s)]' % re.escape(n), s)]
out = s[:blocks[0]['start']]
for k, b in enumerate(blocks):
    out += '(class %s %s\n      %s' % (s[b['start'] + 7:s.index(' ', b['start'] + 7)], ' '.join(b['nets']), b['tail'])
    out += s[b['end']:blocks[k + 1]['start']] if k + 1 < len(blocks) else ''
last = blocks[-1]['end']
if '--ignore-gnd' in sys.argv:
    via = re.search(r'\(use_via "([^"]+)"\)', s).group(1)
    out += ('\n    (class GndPlane GND\n      (circuit\n        (use_via "%s")\n      )\n      (rule\n'
            '        (width 250)\n        (clearance 200)\n      )\n    )' % via)
out += s[last:]
open(dst, 'w').write(out)
print('moved %d nets between classes%s' % (moved, '; GND ignored' if '--ignore-gnd' in sys.argv else ''))
