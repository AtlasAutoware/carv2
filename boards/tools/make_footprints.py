"""Footprints KiCad's library does not have, drawn from the TI land-pattern drawings.

TI_RDF0022A (TPSM63610): pad centres and sizes read from the vector drawing in the datasheet
(SLVSGU1A page 40, 'EXAMPLE BOARD LAYOUT', scale 12X) with tools/pdfpads.py.
TI_DGX0019A (TPS48111-Q1): same method, SLUSEE5E page 48 (scale 16X). Pin 16 is not populated.
Rev B power board (power_board()): through-hole module footprints, sources in each docstring.

    python3 make_footprints.py            # all
    python3 make_footprints.py power      # only the ATLAS-PWR-1 footprints (leaves the drive ones untouched)
"""
import math
import os
import sys

OUT =os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib', 'atlas.pretty')


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


# ----------------------------------------------------------------------------- rev B power board (ATLAS-PWR-1)
# Through-hole footprints, written in the KiCad 7 file format (version 20221018) so that both the KiCad 7
# build container and KiCad 10 load them (KiCad reads older versions; KiCad 7 refuses newer ones).
# Coordinates are KiCad footprint coordinates: mm, Y down, origin as noted per footprint.

def _txt(kind, text, x, y, layer, size=1.0, th=0.15):
    return (f' (fp_text {kind} "{text}" (at {x:.3f} {y:.3f}) (layer "{layer}")'
            f' (effects (font (size {size} {size}) (thickness {th}))))')


def _rect(x0, y0, x1, y1, layer, w):
    return f' (fp_rect (start {x0:.3f} {y0:.3f}) (end {x1:.3f} {y1:.3f}) (stroke (width {w}) (type solid)) (fill none) (layer "{layer}"))'


def _line(x0, y0, x1, y1, layer, w):
    return f' (fp_line (start {x0:.3f} {y0:.3f}) (end {x1:.3f} {y1:.3f}) (stroke (width {w}) (type solid)) (layer "{layer}"))'


def _circle(x, y, r, layer, w, fill='none'):
    return f' (fp_circle (center {x:.3f} {y:.3f}) (end {x + r:.3f} {y:.3f}) (stroke (width {w}) (type solid)) (fill {fill}) (layer "{layer}"))'


def _pad(num, x, y, size, drill, shape='circle'):
    if shape == 'npth':
        return f' (pad "" np_thru_hole circle (at {x:.3f} {y:.3f}) (size {drill} {drill}) (drill {drill}) (layers "*.Cu" "*.Mask"))'
    sx, sy = (size, size) if not isinstance(size, tuple) else size
    return f' (pad "{num}" thru_hole {shape} (at {x:.3f} {y:.3f}) (size {sx} {sy}) (drill {drill}) (layers "*.Cu" "*.Mask"))'


def tht(name, desc, body, ref_xy, items):
    """body: list of s-expression lines (pads, graphics, texts) already formatted."""
    lines = [f'(footprint "{name}" (version 20221018) (generator "atlas_make_footprints")', ' (layer "F.Cu")',
             f' (descr "{desc}")', ' (attr through_hole)',
             _txt('reference', 'REF**', ref_xy[0], ref_xy[1], 'F.SilkS'),
             _txt('value', name, ref_xy[0], ref_xy[1] + 1.5, 'F.Fab', 0.8, 0.12)]
    lines += body
    lines += items
    lines.append(')')
    open(os.path.join(OUT, name + '.kicad_mod'), 'w').write('\n'.join(lines) + '\n')


def wirepad_10awg():
    """10 AWG wire pad: 3.5 mm plated hole in a 7.5 mm pad, six 0.6 mm plated holes in the ring that tie the
    top and bottom pours together right at the wire (rev A used 6 mm2 SolderWire pads for the same leads)."""
    body = [_pad('1', 0, 0, 7.5, 3.5)]
    for k in range(6):
        a = math.radians(30 + 60 * k)
        body.append(_pad('1', 2.85 * math.cos(a), 2.85 * math.sin(a), 1.0, 0.6))
    body += [_circle(0, 0, 4.0, 'F.CrtYd', 0.05), _circle(0, 0, 3.9, 'F.SilkS', 0.12)]
    tht('WirePad_THT_10AWG_D3.5mm_OD7.5mm', 'Solder hole for a 10-12 AWG lead, 3.5 mm drill, 7.5 mm pad, 6 stitching holes',
        body, (0, -5.0), [])


def pico_socketed():
    """Raspberry Pi Pico in two 1x20 female headers. Origin = module centre, USB end at -Y. Pins 1-20 down the
    left column (x -8.89), 21-40 up the right (x +8.89), 2.54 mm pitch, rows 17.78 mm apart (Pico datasheet;
    same coordinates as github.com/ncarandini/KiCad-RP-Pico RPi_Pico_SMD_TH)."""
    body = []
    for n in range(1, 41):
        x = -8.89 if n <= 20 else 8.89
        y = -24.13 + 2.54 * (n - 1) if n <= 20 else 24.13 - 2.54 * (n - 21)
        body.append(_pad(str(n), x, y, 1.7, 1.0, 'rect' if n == 1 else 'circle'))
    # courtyard: the two socket strips only, so low parts (<= 9 mm) can sit between them under the module, whose
    # underside is 11.0 mm up (8.51 mm Sullins PPTC socket + 2.5 mm header spacer); F.Fab shows the module outline
    body += [_rect(-10.5, -25.5, 10.5, 25.5, 'F.Fab', 0.1), _rect(-4.0, -27.0, 4.0, -25.5, 'F.Fab', 0.1)]
    for x in (-8.89, 8.89):
        body.append(_rect(x - 1.37, -25.5, x + 1.37, 25.5, 'F.SilkS', 0.12))
        body.append(_rect(x - 1.6, -26.0, x + 1.6, 26.0, 'F.CrtYd', 0.05))
    body.append(_rect(-4.2, -27.3, 4.2, -26.0, 'F.CrtYd', 0.05))        # micro-USB overhang
    for y in (-25.5, 25.5):
        body.append(_line(-7.2, y, 7.2, y, 'F.SilkS', 0.12))
    body += [_txt('user', 'USB', 0, -24.0, 'F.SilkS', 1.0), _txt('user', 'PICO', 0, 0, 'F.SilkS', 1.5, 0.2),
             _txt('user', '1', -6.6, -24.13, 'F.SilkS', 0.8, 0.12), _txt('user', '40', 6.4, -24.13, 'F.SilkS', 0.8, 0.12),
             _txt('user', '20', -6.4, 24.13, 'F.SilkS', 0.8, 0.12), _txt('user', '21', 6.4, 24.13, 'F.SilkS', 0.8, 0.12)]
    tht('RaspberryPi_Pico_Socketed_2x20_P17.78mm', 'Raspberry Pi Pico on 2 x 1x20 2.54 mm female headers (8.5 mm), 51 x 21 mm; '
        'parts up to 9 mm tall may sit between the strips',
        body, (0, 28.0), [])


def hub_5997():
    """Adafruit 5997 CH334F 4-port USB hub on 1x8 + 1x8 + 1x4 headers. Pads from the Eagle board in
    github.com/adafruit/Adafruit-CH334F-Breakout-PCB (20.32 x 30.48 mm), origin = board centre, USB-C at -Y.
    1-4 upstream VBUS/D+/D-/GND (bottom edge); 5-8 port 1, 9-12 port 2, 13-16 port 3, 17-20 port 4 (VBUS/D+/D-/GND)."""
    pts = [(3.81, 12.70), (1.27, 12.70), (-1.27, 12.70), (-3.81, 12.70)]
    for x, y0 in ((-7.62, -8.89), (7.62, -8.89), (-7.62, 1.27), (7.62, 1.27)):
        pts += [(x, y0 + 2.54 * k) for k in range(4)]
    body = [_pad(str(i + 1), x, y, 1.7, 1.0, 'rect' if i in (0, 4, 8, 12, 16) else 'circle') for i, (x, y) in enumerate(pts)]
    # mounted on female sockets (8.51 mm) so its underside is 11.0 mm up: courtyard = the three socket strips and
    # the USB-C overhang; parts up to 9 mm tall may sit inside the outline
    body += [_rect(-10.16, -15.24, 10.16, 15.24, 'F.Fab', 0.1), _rect(-10.16, -15.24, 10.16, 15.24, 'F.SilkS', 0.12),
             _rect(-9.22, -10.49, -6.02, 10.49, 'F.CrtYd', 0.05), _rect(6.02, -10.49, 9.22, 10.49, 'F.CrtYd', 0.05),
             _rect(-5.41, 11.10, 5.41, 14.30, 'F.CrtYd', 0.05), _rect(-4.8, -16.4, 4.8, -14.9, 'F.CrtYd', 0.05),
             _rect(-4.5, -15.24, 4.5, -12.0, 'F.Fab', 0.1),
             _txt('user', 'USB HUB 5997', 0, -6.0, 'F.SilkS', 1.0), _txt('user', 'UP', 0, 10.8, 'F.SilkS', 0.8, 0.12),
             _txt('user', 'P1', -5.2, -8.9, 'F.SilkS', 0.8, 0.12), _txt('user', 'P2', 5.2, -8.9, 'F.SilkS', 0.8, 0.12),
             _txt('user', 'P3', -5.2, 1.3, 'F.SilkS', 0.8, 0.12), _txt('user', 'P4', 5.2, 1.3, 'F.SilkS', 0.8, 0.12)]
    tht('Adafruit_5997_CH334F_Hub_Headers', 'Adafruit 5997 CH334F USB hub breakout on 2.54 mm female sockets (8.5 mm); '
        'parts up to 9 mm tall may sit under it', body,
        (0, 17.0), [])


def husb238_5807():
    """Adafruit 5807 HUSB238 PD trigger on a 1x6 male header row (with a gap) plus two pins through the
    terminal-block holes for VOUT/GND. Pads from github.com/adafruit/Adafruit-USB-Type-C-Power-Delivery-Dummy-
    Breakout-PCB (20.32 x 23.495 mm), origin = board centre, USB-C at -Y (put that edge on the board edge).
    1 SDA, 2 SCL, 3 VOUT, 4 GND, 5 D-, 6 D+, 7 TB+ (VOUT), 8 TB- (GND)."""
    y = 9.2075
    pts = [('1', -7.62, y), ('2', -5.08, y), ('3', -2.54, y), ('4', 2.54, y), ('5', 5.08, y), ('6', 7.62, y),
           ('7', -1.80, 7.1755), ('8', 1.70, 7.1755)]
    body = [_pad(n, x, yy, 1.6 if n in '78' else 1.7, 1.0, 'rect' if n == '3' else 'circle') for n, x, yy in pts]
    body += [_rect(-10.16, -11.75, 10.16, 11.75, 'F.Fab', 0.1), _rect(-10.16, -11.75, 10.16, 11.75, 'F.SilkS', 0.12),
             _rect(-10.5, -12.1, 10.5, 12.1, 'F.CrtYd', 0.05), _rect(-4.5, -11.75, 4.5, -8.0, 'F.Fab', 0.1),
             _txt('user', 'USB-C PD 5807', 0, -3.0, 'F.SilkS', 1.0), _txt('user', 'OUT', -2.54, 5.6, 'F.SilkS', 0.7, 0.12),
             _txt('user', 'GND', 2.54, 5.6, 'F.SilkS', 0.7, 0.12)]
    tht('Adafruit_5807_HUSB238_Headers', 'Adafruit 5807 HUSB238 USB-C PD trigger on 2.54 mm headers', body,
        (0, 13.5), [])


def wireland(name, desc, pads, outline=None, title=''):
    """Labelled solder holes for a module that is wired to the board. pads: (num, x, y, drill, pad, label).
    outline: (w, h, cx, cy) of the module drawn where it sits (foam tape), or None for an off-board module."""
    body = []
    xs, ys = [], []
    for num, x, y, dr, pd, lab in pads:
        body.append(_pad(num, x, y, pd, dr, 'rect' if num == '1' else 'circle'))
        body.append(_txt('user', lab, x + pd / 2 + 1.6, y, 'F.SilkS', 0.8, 0.12))
        xs += [x - pd / 2, x + pd / 2 + 3.4]
        ys += [y - pd / 2, y + pd / 2]
    if outline:
        w, h, cx, cy = outline
        body += [_rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, 'F.Fab', 0.1),
                 _rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, 'F.SilkS', 0.12)]
        xs += [cx - w / 2, cx + w / 2]
        ys += [cy - h / 2, cy + h / 2]
    if title:
        tx = (outline[2] if outline else (min(xs) + max(xs)) / 2)
        ty = (outline[3] if outline else min(ys) - 1.2)
        body.append(_txt('user', title, tx, ty, 'F.SilkS', 0.8, 0.12))
    body.append(_rect(min(xs) - 0.3, min(ys) - 0.3 - (2.0 if title and not outline else 0), max(xs) + 0.3,
                      max(ys) + 0.3, 'F.CrtYd', 0.05))
    tht(name, desc, body, ((min(xs) + max(xs)) / 2, max(ys) + 1.6), [])


def heatsink_bar():
    """Aluminium bar 40 x 15 x 3 mm standing behind the three TO-220 tabs (13.0 mm FET pitch), bolted through the
    tab holes. No pads: courtyard and silkscreen only. The bar is at BAT+ (the tabs are the drains)."""
    body = [_rect(-20.0, -1.5, 20.0, 1.5, 'F.Fab', 0.1), _rect(-20.0, -1.5, 20.0, 1.5, 'F.SilkS', 0.12),
            _rect(-20.0, -1.5, 20.0, 1.5, 'F.CrtYd', 0.05),
            _txt('user', 'HEATSINK = BAT+  INSULATE', 0, 3.0, 'F.SilkS', 0.8, 0.12)]
    tht('Heatsink_Bar_3xTO220_40x15x3mm', 'Bar heatsink behind three TO-220 tabs, 40 x 15 x 3 mm, live at BAT+', body,
        (0, -3.2), [])


def mfr_ptc():
    """Bourns MF-R radial PTC (MF-R050, MF-R075): two leads 5.1 mm apart (0.2 in grid), 1.0 mm holes."""
    body = [_pad('1', 0, 0, 1.8, 1.0, 'rect'), _pad('2', 5.08, 0, 1.8, 1.0),
            _rect(-1.2, -1.6, 6.28, 1.6, 'F.Fab', 0.1), _rect(-1.3, -1.7, 6.38, 1.7, 'F.SilkS', 0.12),
            _rect(-1.6, -2.0, 6.68, 2.0, 'F.CrtYd', 0.05)]
    tht('Fuse_Bourns_MF-R_P5.08mm', 'Bourns MF-R radial resettable fuse, 5.1 mm lead spacing', body, (2.54, -3.0), [])


def mounting_hole_m3():
    """M3 clearance hole, not plated, with a 7 mm keep-out ring (standoff and washer)."""
    body = [_pad('', 0, 0, 3.2, 3.2, 'npth'), _circle(0, 0, 3.5, 'F.CrtYd', 0.05), _circle(0, 0, 3.5, 'F.Fab', 0.1),
            _circle(0, 0, 3.6, 'F.SilkS', 0.12)]
    tht('MountingHole_3.2mm_M3_Keepout7mm', 'M3 mounting hole 3.2 mm NPTH, 7 mm keep-out', body, (0, -4.6), [])


def power_board():
    wirepad_10awg()
    pico_socketed()
    hub_5997()
    heatsink_bar()
    mfr_ptc()
    mounting_hole_m3()
    # off-board modules: holes only. Pololu #2813 (on the tray, foam tape): 18 AWG for VIN/VOUT/GND, 24 AWG for ON/OFF
    wireland('WireLand_Pololu_2813', 'Pololu 2813 pushbutton power switch (off board), wired to labelled holes',
             [('1', 0.0, 0.0, 1.4, 3.0, 'VIN'), ('2', 0.0, 4.0, 1.4, 3.0, 'VOUT'), ('3', 0.0, 8.0, 1.4, 3.0, 'GND'),
              ('4', 0.0, 11.5, 1.0, 2.0, 'ON'), ('5', 0.0, 14.04, 1.0, 2.0, 'OFF')], title='LATCH')
    wireland('WireLand_Pololu_S18V20F12', 'Pololu S18V20F12 12 V regulator input (off board), wired to labelled holes',
             [('1', 0.0, 0.0, 1.0, 2.0, 'VIN'), ('2', 0.0, 3.81, 1.0, 2.0, 'GND')], title='CAM REG')
    wireland('WireLand_PD_Trigger', 'USB-C PD trigger output (off board, Adafruit 5807 terminal holes), 20 AWG',
             [('1', 0.0, 0.0, 1.4, 3.0, 'PD+'), ('2', 0.0, 5.08, 1.4, 3.0, 'PD-')], title='PD 20V')
    wireland('WireLand_CCCV_Buck', 'CC/CV buck module (off board), wired to labelled holes, 16 AWG',
             [('1', 0.0, 0.0, 1.7, 3.5, 'IN+'), ('2', 0.0, 5.08, 1.7, 3.5, 'IN-'), ('3', 0.0, 10.16, 1.7, 3.5, 'OUT+'),
              ('4', 0.0, 15.24, 1.7, 3.5, 'OUT-')], title='CC/CV')


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    which = sys.argv[1:] or ['drive', 'power']
    if 'drive' in which:
        rdf0022a()
        dgx0019a()
        wirepad()
    if 'power' in which:
        power_board()
    print('wrote', sorted(os.listdir(OUT)))
