"""Footprints KiCad's library does not have, drawn from the TI land-pattern drawings.

TI_RDF0022A (TPSM63610): pad centres and sizes read from the vector drawing in the datasheet
(SLVSGU1A page 40, 'EXAMPLE BOARD LAYOUT', scale 12X) with tools/pdfpads.py.
TI_DGX0019A (TPS48111-Q1): same method, SLUSEE5E page 48 (scale 16X). Pin 16 is not populated.
"""
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib', 'atlas.pretty')


def fp(name, desc, pads, body, crt, ref_y, value_y, paste_ratio=None):
    lines = [f'(footprint "{name}" (version 20241229) (generator "atlas_make_footprints") (layer "F.Cu")',
             f' (descr "{desc}") (attr smd)',
             f' (property "Reference" "REF**" (at 0 {ref_y} 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
             f' (property "Value" "{name}" (at 0 {value_y} 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))']
    bx, by = body
    lines.append(f' (fp_rect (start {-bx / 2} {-by / 2}) (end {bx / 2} {by / 2}) (stroke (width 0.1) (type solid)) (fill no) (layer "F.Fab"))')
    cx, cy = crt
    lines.append(f' (fp_rect (start {-cx} {-cy}) (end {cx} {cy}) (stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd"))')
    # silkscreen corner marks and pin-1 dot
    sx, sy = bx / 2 + 0.12, by / 2 + 0.12
    for x0, y0, x1, y1 in ((-sx, -sy, -sx + 0.8, -sy), (sx, -sy, sx - 0.8, -sy), (-sx, sy, -sx + 0.8, sy), (sx, sy, sx - 0.8, sy)):
        lines.append(f' (fp_line (start {x0:.3f} {y0:.3f}) (end {x1:.3f} {y1:.3f}) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))')
    lines.append(f' (fp_circle (center {-cx + 0.35:.3f} {-cy + 0.35:.3f}) (end {-cx + 0.5:.3f} {-cy + 0.35:.3f}) (stroke (width 0.3) (type solid)) (fill yes) (layer "F.SilkS"))')
    for num, x, y, w, h in pads:
        extra = ''
        if paste_ratio and num in paste_ratio:
            extra = f' (solder_paste_margin_ratio {paste_ratio[num]})'
        lines.append(f' (pad "{num}" smd roundrect (at {x:.4f} {y:.4f}) (size {w:.4f} {h:.4f}) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.1){extra})')
    lines.append(')')
    open(os.path.join(OUT, name + '.kicad_mod'), 'w').write('\n'.join(lines) + '\n')


def rdf0022a():
    pads = [('1', -2.751, -2.925, 1.401, 0.900)]
    for i, n in enumerate(range(2, 9)):
        pads.append((str(n), -2.851, -1.95 + 0.65 * i, 1.2, 0.25))
    pads.append(('9', -2.751, 2.925, 1.401, 0.900))
    pads.append(('10', 2.751, 2.925, 1.401, 0.900))
    for i, n in enumerate(range(11, 18)):
        pads.append((str(n), 2.851, 1.95 - 0.65 * i, 1.2, 0.25))
    pads.append(('18', 2.751, -2.925, 1.401, 0.900))
    for i, n in enumerate(range(19, 23)):
        pads.append((str(n), 0.0, -2.25 + 1.5 * i, 3.3, 1.0))
    fp('TI_RDF0022A_B3QFN-22_6.5x7.5mm', 'TI RDF0022A B3QFN-22 (TPSM63610), land pattern from SLVSGU1A', pads,
       (6.5, 7.5), (3.75, 4.05), -5.0, 5.0, paste_ratio={str(n): -0.1 for n in range(19, 23)})


def dgx0019a():
    pads = []
    for i in range(10):
        pads.append((str(i + 1), -2.2, -2.25 + 0.5 * i, 1.45, 0.30))
    for i, n in enumerate(range(11, 21)):
        if n == 16:
            continue
        pads.append((str(n), 2.2, 2.25 - 0.5 * i, 1.45, 0.30))
    fp('TI_DGX0019A_VSSOP-19_3x5.1mm_P0.5mm', 'TI DGX0019A VSSOP-19 (TPS4811-Q1), land pattern from SLUSEE5E, pin 16 removed',
       pads, (3.0, 5.1), (3.2, 2.85), -3.6, 3.6)


def wirepad():
    """Solder pad for a 12 AWG motor lead on the top side. Ten plated holes in two rows carry the
    current down to the phase copper on the bottom. The rows sit at +-0.9 mm so that on the bottom
    they land in the 4.3 mm strip between the low-side drain tabs and the high-side source pins.
    Open on top (solder fills them when the wire goes on), tented on the bottom (thermal pad side)."""
    name = 'WirePad_SMD_9x7mm_10Vias'
    lines = [f'(footprint "{name}" (version 20241229) (generator "atlas_make_footprints") (layer "F.Cu")',
             ' (descr "SMD solder pad for a 12 AWG wire, 10 x 0.5 mm plated holes to the phase copper, tented on the bottom") (attr smd)',
             ' (property "Reference" "REF**" (at 0 -5 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
             f' (property "Value" "{name}" (at 0 5 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))',
             ' (fp_rect (start -4.9 -3.9) (end 4.9 3.9) (stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd"))',
             ' (pad "1" smd roundrect (at 0 0) (size 9 7) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.08) (solder_paste_margin_ratio -0.4))']
    for i in range(5):
        for j in range(2):
            x = -3.2 + 1.6 * i
            y = -0.9 + 1.8 * j
            lines.append(f' (pad "1" thru_hole circle (at {x:.2f} {y:.2f}) (size 0.9 0.9) (drill 0.5) (layers "*.Cu" "F.Mask") (remove_unused_layers no))')
    lines.append(')')
    open(os.path.join(OUT, name + '.kicad_mod'), 'w').write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    rdf0022a()
    dgx0019a()
    wirepad()
    print('wrote', sorted(os.listdir(OUT)))
