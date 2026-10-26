"""DRC from KiCad's Python, for KiCad 7 (its kicad-cli has no `pcb drc`; KiCad 8+ use `kicad-cli pcb drc`).

    /usr/bin/python3 drc.py power [--no-refill] [--out FILE]

Loads boards/<board>/<name>.kicad_pcb (with its .kicad_pro net classes and .kicad_dru rules), refills every
zone, and writes <board>/drc.rpt in KiCad's own report format (the one strip_routes.py, pad_vias.py and
mazeroute.py read), then prints a count per violation type. --no-refill checks the fills as saved.
The board file is not changed. There is no schematic parity check here (the schematic is KiCad 9 format).
"""
import os
import re
import sys
from collections import Counter

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[1:]
board = args.pop(0)
bdir = os.path.abspath(os.path.join(HERE, '..', board))
name = [f for f in os.listdir(bdir) if f.endswith('.kicad_pcb')][0][:-len('.kicad_pcb')]
out = os.path.join(bdir, 'drc.rpt')
if '--out' in args:
    out = os.path.abspath(args[args.index('--out') + 1])
b = pcbnew.LoadBoard(os.path.join(bdir, name + '.kicad_pcb'))
if '--no-refill' not in args:
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
ok = pcbnew.WriteDRCReport(b, out, pcbnew.EDA_UNITS_MILLIMETRES, True)
txt = open(out).read()
kinds = Counter(m.group(1) for m in re.finditer(r'^\[(\w+)\]', txt, re.M))
print('drc report', out, 'ok' if ok else 'FAILED')
for line in txt.splitlines():
    if line.startswith('**') and ('Found' in line or 'unconnected' in line.lower()):
        print(line)
for k, n in kinds.most_common():
    print(f'{n:6d}  {k}')
