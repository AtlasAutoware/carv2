"""Check that every footprint a board uses exists and has the pads the schematic connects.
python3 check_fp.py drive   (host python, reads the KiCad footprint library files directly)"""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fpinfo import pads  # noqa: E402

bdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', sys.argv[1])
name = [f for f in os.listdir(bdir) if f.endswith('_parts.json')][0]
data = json.load(open(os.path.join(bdir, name)))
bad = 0
seen = {}
for p in data['parts']:
    fpid = p['footprint']
    if fpid not in seen:
        try:
            seen[fpid] = set(x[0] for x in pads(fpid))
        except Exception as e:
            seen[fpid] = e
    got = seen[fpid]
    if isinstance(got, Exception):
        print('MISSING', p['ref'], fpid, type(got).__name__)
        bad += 1
        continue
    want = set(k for k in p['pads'])
    miss = sorted(want - got)
    extra = sorted(n for n in got - want if n)
    if miss:
        print('PADS', p['ref'], fpid, 'schematic pins with no pad:', miss)
        bad += 1
    if extra and not p['ref'].startswith(('H', 'TP')):
        print('note', p['ref'], fpid, 'pads with no pin:', extra)
print(len(data['parts']), 'parts,', len(seen), 'footprints,', bad, 'problems')
