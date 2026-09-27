"""Export the board for the autorouter (KiCad Python). The board is first put in the state the router
should see (route_prep.prepare: no 'F:' fills, the board's own dsn_prep, the 'D:' keepouts that
protect the pours); everything else goes in as KiCad writes it: zones become planes (the router
connects to them and routes around them), locked tracks and vias become protected wiring, inner
layers of type 'power' are planes the router does not route on. The board file is not changed.

    flatpak run --command=python3 --filesystem=home org.kicad.KiCad dsn_export.py drive
"""
import os
import sys

import pcbnew

from route_prep import prepare

HERE = os.path.dirname(os.path.abspath(__file__))
bdir = os.path.abspath(os.path.join(HERE, '..', sys.argv[1]))
name = [f for f in os.listdir(bdir) if f.endswith('.kicad_pcb')][0][:-len('.kicad_pcb')]
b = pcbnew.LoadBoard(os.path.join(bdir, name + '.kicad_pcb'))
held = prepare(b, bdir, name)
os.makedirs(os.path.join(bdir, 'out'), exist_ok=True)
out = os.path.join(bdir, 'out', name + '.dsn')
ok = pcbnew.ExportSpecctraDSN(b, out)
print('exported', out, ok)
