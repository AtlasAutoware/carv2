"""The board as the autorouter sees it (KiCad Python, imported by dsn_export.py and dump_board.py).

prepare(b, bdir, name) changes the loaded board in memory, never on disk:
- drops the 'F:' fills: they are added after routing, so the router must not see them;
- runs the board's own layout.dsn_prep() if it has one (the brain board: Antmicro's planes become
  power layers and its pours on the routing layers get inset keepouts);
- puts back the 'D:' keepouts that protect the pours when the board has none (a board that came
  back from the router has lost them: ses_import removes them), from out/<name>_copper.json.
Returns the objects the caller must keep referenced while the board is in use (SWIG frees them otherwise).
"""
import importlib.util
import json
import os

import pcbnew
from pcbnew import FromMM as MM


def prepare(b, bdir, name, verbose=True):
    held = [z for z in b.Zones() if z.GetZoneName().startswith('F:')]
    for z in held:
        b.Remove(z)
    spec = importlib.util.spec_from_file_location('layout', os.path.join(bdir, 'layout.py'))
    L = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(L)
    if hasattr(L, 'dsn_prep'):
        held += L.dsn_prep(b, pcbnew)
    keep = sum(1 for z in b.Zones() if z.GetIsRuleArea() and z.GetZoneName().startswith('D:'))
    cu_path = os.path.join(bdir, 'out', name + '_copper.json')
    if keep == 0 and hasattr(L, 'PAGE_ORIGIN') and os.path.exists(cu_path):
        OX, OY = L.PAGE_ORIGIN
        W, H = L.SIZE
        LAYER = {'F': pcbnew.F_Cu, 'In1': pcbnew.In1_Cu, 'In2': pcbnew.In2_Cu, 'In3': pcbnew.In3_Cu,
                 'In4': pcbnew.In4_Cu, 'B': pcbnew.B_Cu}
        for r in json.load(open(cu_path)).get('rules', []):
            if not r['name'].startswith('D:'):
                continue
            ra = pcbnew.ZONE(b)
            ra.SetIsRuleArea(True)
            ra.SetDoNotAllowTracks(bool(r['no_tracks']))
            ra.SetDoNotAllowVias(bool(r['no_vias']))
            ra.SetDoNotAllowPads(False)
            ra.SetDoNotAllowFootprints(False)
            ls = pcbnew.LSET()
            for lay in r['layers']:
                ls.AddLayer(LAYER[lay])
            ra.SetLayerSet(ls)
            ra.SetZoneName(r['name'])
            ol = ra.Outline()
            for rings in r['rings']:
                oi = ol.NewOutline()
                for (x, y) in rings[0]:
                    ol.Append(MM(OX + x), MM(OY + (H - y)), oi, -1)
                for hole in rings[1:]:
                    hi = ol.NewHole(oi)
                    for (x, y) in hole:
                        ol.Append(MM(OX + x), MM(OY + (H - y)), oi, hi)
            b.Add(ra)
            held.append(ra)
            keep += 1
        if verbose:
            print('router keepouts restored from the copper file')
    if verbose:
        print('router keepouts in the board:', keep)
    return held
