"""Bring the autorouter's session back into the board (KiCad Python), refill every zone and save.
Locked tracks and vias (the hand-placed escapes and via arrays) survive the import.

    flatpak run --command=python3 --filesystem=home org.kicad.KiCad ses_import.py drive [--trim]

--trim   afterwards remove unlocked track pieces and vias that end in nothing (left over when parts
         moved since the session was routed), until none are left
Vias whose drill is below the board's minimum through-hole size are opened up to it (the session
names its via padstacks after the net class default, which can be smaller). The session's placement
section is ignored: the board keeps its own part positions.
"""
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
bdir = os.path.abspath(os.path.join(HERE, '..', sys.argv[1]))
trim = '--trim' in sys.argv[2:]
name = [f for f in os.listdir(bdir) if f.endswith('.kicad_pcb')][0][:-len('.kicad_pcb')]
path = os.path.join(bdir, name + '.kicad_pcb')
b = pcbnew.LoadBoard(path)
ses = os.path.join(bdir, 'out', name + '.ses')
# KiCad moves every footprint to the session's (placement) section on import. The board may have been
# re-placed since the session was routed, so import a copy without that section: parts stay where the
# board has them and routes that no longer fit are trimmed below or reported by DRC.
txt = open(ses).read()
i = txt.find('(placement')
if i >= 0:
    depth, j = 0, i
    while True:
        if txt[j] == '(':
            depth += 1
        elif txt[j] == ')':
            depth -= 1
            if depth == 0:
                break
        j += 1
    txt = txt[:i] + txt[j + 1:]
ses_np = ses[:-4] + '_noplace.ses'
open(ses_np, 'w').write(txt)
n0 = len(b.GetTracks())
ok = pcbnew.ImportSpecctraSES(b, ses_np)
n1 = len(b.GetTracks())
gone = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetZoneName().startswith('D:')]
for z in gone:
    b.Remove(z)                      # router-only keepouts
min_drill = b.GetDesignSettings().m_MinThroughDrill
opened = 0
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T and t.GetDrillValue() < min_drill:
        t.SetDrill(min_drill)
        opened += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
trimmed = 0
keep = []                            # removed items stay referenced (SWIG frees them otherwise)
if trim:
    for _ in range(100):
        b.BuildConnectivity()
        conn = b.GetConnectivity()
        dang = [t for t in b.GetTracks() if not t.IsLocked() and conn.TestTrackEndpointDangling(t, False)]
        if not dang:
            break
        for t in dang:
            b.Remove(t)
            keep.append(t)
        trimmed += len(dang)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(path, b)
print('imported', ses, ok, 'tracks+vias', n0, '->', n1, '; removed', len(gone), 'router keepouts;',
      opened, 'vias opened to', pcbnew.ToMM(min_drill), 'mm;', trimmed, 'dangling pieces trimmed')
