"""Fabrication outputs for a 2- or 4-layer board with kicad-cli (KiCad 7 or later) and pdftoppm (plain Python).

    python3 fab_outputs.py power [--bom ../../bom/revb/power_board_bom.csv] [--dpi 300]

Writes into boards/<board>/out/fab/:
  gerbers/                 F.Cu, the inner copper layers (In1.Cu, In2.Cu on a 4-layer board), B.Cu, F/B.Paste,
                           F/B.Silkscreen (mask subtracted), F/B.Mask, Edge.Cuts, F/B.Fab,
                           Excellon drill files (PTH and NPTH apart, mm) and a Gerber X2 drill map
  <name>_gerbers_pcbway.zip   what the fab needs: copper, mask, paste, silkscreen, outline, drill (no Fab layers,
                           no map)
  <name>_cpl_bottom_smd.csv   placement of the bottom-side SMD parts (mm, PCBWay column names)
  <name>_tht_top.csv          the top-side parts (through-hole, sockets, modules, fiducials), mm
  <name>_bom.csv              fab BOM: designators, qty, value, footprint, MPN, manufacturer, side, DNP
  <name>_bom_bottom_smd.csv   the same for the bottom SMD chips only (an assembly quote for that side)
and into boards/<board>/out/render/: top.png, bottom.png (mirrored, seen from below), copper_top.png,
copper_bottom.png (and copper_in1.png, copper_in2.png ... for the inner layers): KiCad's PDF plot rasterised
with pdftoppm and trimmed with ImageMagick. KiCad 8+
can also make 3D renders (`kicad-cli pcb render`,
run_kicad.sh render-<board>); KiCad 7 has no renderer.
"""
import csv
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[1:]
board = args.pop(0)
bdir = os.path.abspath(os.path.join(HERE, '..', board))
spec = importlib.util.spec_from_file_location('layout', os.path.join(bdir, 'layout.py'))
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)
name = L.NAME
pcb = os.path.join(bdir, name + '.kicad_pcb')
fab = os.path.join(bdir, 'out', 'fab')
ger = os.path.join(fab, 'gerbers')
ren = os.path.join(bdir, 'out', 'render')
bom_src = os.path.abspath(args[args.index('--bom') + 1]) if '--bom' in args else \
    os.path.abspath(os.path.join(HERE, '..', '..', 'bom', 'revb', f'{board}_board_bom.csv'))
dpi = args[args.index('--dpi') + 1] if '--dpi' in args else '300'


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit('failed: ' + ' '.join(cmd))
    return r.stdout


shutil.rmtree(fab, ignore_errors=True)
os.makedirs(ger)
os.makedirs(ren, exist_ok=True)

# ---------------------------------------------------------------- gerbers and drill
INNER = ['In%d.Cu' % k for k in range(1, getattr(L, 'COPPER_LAYERS', 2) - 1)]
LAYERS = ['F.Cu'] + INNER + ['B.Cu', 'F.Paste', 'B.Paste', 'F.Silkscreen', 'B.Silkscreen', 'F.Mask', 'B.Mask',
                             'Edge.Cuts', 'F.Fab', 'B.Fab']
run(['kicad-cli', 'pcb', 'export', 'gerbers', '--layers', ','.join(LAYERS), '--subtract-soldermask',
     '-o', ger + '/', pcb])
run(['kicad-cli', 'pcb', 'export', 'drill', '--format', 'excellon', '--excellon-separate-th', '--generate-map',
     '--map-format', 'gerberx2', '--excellon-units', 'mm', '-o', ger + '/', pcb])
files = sorted(os.listdir(ger))
fab_set = [f for f in files if not re.search(r'(F_Fab|B_Fab|-drl_map|_map\.)', f)]
zpath = os.path.join(fab, f'{name}_gerbers_pcbway.zip')
with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in fab_set:
        z.write(os.path.join(ger, f), f)
print('gerbers and drill:', ' '.join(files))
print('zip for the fab:', os.path.basename(zpath), len(fab_set), 'files')

# ---------------------------------------------------------------- placement files
raw_b = os.path.join(fab, 'pos_bottom_raw.csv')
raw_f = os.path.join(fab, 'pos_top_raw.csv')
run(['kicad-cli', 'pcb', 'export', 'pos', '--side', 'back', '--format', 'csv', '--units', 'mm', '--smd-only',
     '-o', raw_b, pcb])
run(['kicad-cli', 'pcb', 'export', 'pos', '--side', 'front', '--format', 'csv', '--units', 'mm', '-o', raw_f, pcb])


def recolumn(src, dst):
    rows = list(csv.DictReader(open(src)))
    with open(dst, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['Designator', 'Value', 'Package', 'Mid X', 'Mid Y', 'Rotation', 'Layer'])
        for r in rows:
            w.writerow([r['Ref'], r['Val'], r['Package'], r['PosX'], r['PosY'], r['Rot'],
                        'Bottom' if r['Side'].lower().startswith('b') else 'Top'])
    os.remove(src)
    return len(rows)


nb = recolumn(raw_b, os.path.join(fab, f'{name}_cpl_bottom_smd.csv'))
nf = recolumn(raw_f, os.path.join(fab, f'{name}_tht_top.csv'))
print(f'CPL: {nb} bottom SMD parts, {nf} top parts')

# ---------------------------------------------------------------- BOM
if os.path.exists(bom_src):
    rows = list(csv.DictReader(open(bom_src)))
    out = []
    for r in rows:
        refs = r['refs'].split() if r['refs'] not in ('', '-') else []
        dnp = r.get('dnp_refs', '').split()
        side = 'bottom (SMD)' if 'SMD' in r['assembly'] else ('top (through-hole)' if r['assembly'] == 'through-hole'
                                                               else r['assembly'])
        out.append({'Designator': ' '.join(refs) or '-', 'Qty': r['qty'], 'Value': r['value'], 'Footprint': r['footprint'],
                    'MPN': r['mpn'], 'Manufacturer': r['manufacturer'], 'Side': side,
                    'DNP': ' '.join(dnp)})
    cols = ['Designator', 'Qty', 'Value', 'Footprint', 'MPN', 'Manufacturer', 'Side', 'DNP']
    for fn, sel in ((f'{name}_bom.csv', out), (f'{name}_bom_bottom_smd.csv', [o for o in out if o['Side'].startswith('bottom')])):
        with open(os.path.join(fab, fn), 'w', newline='') as fh:
            w = csv.DictWriter(fh, cols)
            w.writeheader()
            w.writerows(sel)
    print(f'BOM: {len(out)} lines from {os.path.relpath(bom_src, bdir)}')
else:
    print('BOM source not found:', bom_src)

# ---------------------------------------------------------------- 2D renders (PDF plot -> PNG)
VIEWS = {
    'top': (['F.Cu', 'F.Mask', 'F.Silkscreen', 'Edge.Cuts'], False),
    'bottom': (['B.Cu', 'B.Mask', 'B.Silkscreen', 'Edge.Cuts'], True),
    'copper_top': (['F.Cu', 'Edge.Cuts'], False),
    'copper_bottom': (['B.Cu', 'Edge.Cuts'], True),
}
for lay in INNER:                                   # inner layers seen from the top
    VIEWS['copper_' + lay.split('.')[0].lower()] = ([lay, 'Edge.Cuts'], False)
tmp = os.path.join(ren, '_tmp')
os.makedirs(tmp, exist_ok=True)
for view, (lays, mirror) in VIEWS.items():
    pdf = os.path.join(tmp, view + '.pdf')
    cmd = ['kicad-cli', 'pcb', 'export', 'pdf', '--layers', ','.join(lays), '-o', pdf, pcb]
    if mirror:
        cmd.insert(4, '--mirror')
    run(cmd)
    page = os.path.join(tmp, view)
    run(['pdftoppm', '-png', '-r', dpi, '-singlefile', pdf, page])
    # the plot sits on the drawing sheet's page: trim to the board and leave a small white border
    run(['convert', page + '.png', '-trim', '+repage', '-bordercolor', 'white', '-border', '40',
         os.path.join(ren, view + '.png')])
shutil.rmtree(tmp)
print('renders:', ' '.join(sorted(os.listdir(ren))))
