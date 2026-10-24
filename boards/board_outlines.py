"""Board outline, mounting holes, keep-outs and height map for the rev B power board (ATLAS-PWR-1), taken from the
same numbers as ../mech/kit.py so the PCB, the dev-kit tray and the printed deck agree.

    python3 board_outlines.py     -> power/atlas_power_outline.dxf, power/atlas_power_placement.png, outlines.json

Board-local frame: X along the car (+x forward) from the board's rear edge, Y across the car (+y = car left) from
the board's right edge, both in mm; top view. car (x, y) = (X + POWER_X0, Y + POWER_Y0) = (X - 32, Y - 68). Import
the DXF into KiCad (File > Import > Graphics, layer Edge.Cuts for the OUTLINE layer).

The length L is kit.P['POWER_L'] (environment override POWER_L=130 etc.); agent D's layout decides it. Rev A's two
boards (drive, brain) are history: their entries in outlines.json are kept under reva_drive and reva_brain, and their
DXFs and placement PNGs in drive/ and brain/ are no longer regenerated.
"""
import os, sys, json
import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'mech'))
import kit  # noqa: E402
import extras  # noqa: E402  (connector positions the mechanical model assumes)

P = kit.P
L, W = P['POWER_L'], P['POWER_W']
X0, Y0 = P['POWER_X0'], P['POWER_Y0']


def car_to_local(x, y):
    return (round(x - X0, 2), round(y - Y0, 2))


def outline_pts():
    """the board outline, counter-clockwise from the rear-right corner, with the servo notch on Y = 0 if L needs it"""
    n = kit.servo_notch_local()
    pts = [(0.0, 0.0)]
    if n:
        a, b, _, d = n
        pts += [(a, 0.0), (a, d), (b, d), (b, 0.0)]
    pts += [(L, 0.0), (L, W), (0.0, W)]
    return pts, n


def tray_footprint_local():
    """plan rectangles of the dev-kit tray's rails, arms and pads (the parts of the board the tray sits over)"""
    r = kit.TRAY_RAIL
    a, b = kit.LOW_X[0], min(kit.LOW_X[1], L)
    rects = [(a, b, 0, r), (a, b, W - r, W), (a, a + r, 0, W), (b - r, b, 0, W), (0, a, 0, r), (0, a, W - r, W),
             (75 - r / 2, 75 + r / 2, 0, W)]
    if L > b:
        rects += [(b, L, 0, r), (b, L, W - r, W)]
    for (hx, hy) in kit.DEVKIT_HOLES_CAR:
        X, Y = car_to_local(hx, hy)
        rects += [(a, b, max(0, Y - r / 2), min(W, Y + r / 2)), (max(a, X - r / 2), min(b, X + r / 2), 0, W)]
    return rects


# PHASE2 edge assignments (scratchpad PHASE2.md, "Edges") and the positions the mechanical model assumes
EDGES = {
    'Y=84 (pack side)': 'XT90 board-mount for the pack, BMS UART JST-XH 4-pin (isolated), dev-kit DC lead pads',
    'X=0 (rear, ESC bay)': 'ESC output XT60PW/XT90PW, Castle BEC in/out headers, FSESC UART/COMM JST-PH 7-pin',
    'X=L (front)': 'servo 3-pin, lidar power Phoenix 2-pin, camera power JST-XH 2-pin, fan 4-pin, E-stop JST-PH 2-pin, remote button JST-PH 2-pin',
    'Y=0 (right, pod side, z <= 30)': 'charge USB-C (PD trigger module at the edge), debug USB-C, power button (6 mm tactile + remote header)',
    'middle': '2x20 shrouded box header (J12 ribbon), 1x12 header (J14 harness), Pico in 2 x 20-pin sockets, hub module, console module, Pololu latch, R-78E, FET switch with its heatsink in the rear strip',
}


def blocks():
    """(label, X0, X1, Y0, Y1, style, colour) for the placement drawing"""
    B = []
    for (name, a, b, c, d, h) in kit.power_zones():
        col = '#2ca02c' if name.startswith('low') else '#d62728'
        B.append((f'{name}: parts <= {h:g} mm', a, b, c, d, 'zone', col))
    dx0, dx1, dy0, dy1 = P['DEVKIT']
    a, c = car_to_local(dx0, dy0); b, d = car_to_local(dx1, dy1)
    B.append(('dev-kit carrier shadow (100 x 79, on the tray 25 mm up)', a, b, c, d, 'shadow', '#7f7f7f'))
    for name, (X, Y, h) in extras.POWER_CONN.items():
        B.append((f'{name} (mech model)', X - 2, X + 2, Y - 2, Y + 2, 'conn', '#1f77b4'))
    for (name, xc, w, z0, z1) in P['POD_WINDOWS']:
        X = xc - X0
        B.append((f'pod window {name} (z {z0:g}-{z1:g})', X - w / 2, X + w / 2, -6, 0, 'window', '#9467bd'))
    return B


def make():
    d = os.path.join(HERE, 'power'); os.makedirs(d, exist_ok=True)
    pts, notch = outline_pts()
    holes = [tuple(h) for h in kit.POWER_HOLES_LOCAL]
    doc = ezdxf.new('R2010'); msp = doc.modelspace()
    for lay in ('OUTLINE', 'HOLES', 'KEEPOUT', 'ZONES', 'TRAY', 'PLACEMENT', 'LABELS'):
        doc.layers.add(lay)
    msp.add_lwpolyline(pts, close=True, dxfattribs={'layer': 'OUTLINE'})
    for (hx, hy) in holes:
        msp.add_circle((hx, hy), 1.6, dxfattribs={'layer': 'HOLES'})
        msp.add_circle((hx, hy), kit.POWER_HOLE_KEEPOUT / 2, dxfattribs={'layer': 'KEEPOUT'})
    for (name, a, b, c, e, h) in kit.power_zones():
        msp.add_lwpolyline([(a, c), (b, c), (b, e), (a, e)], close=True, dxfattribs={'layer': 'ZONES'})
        msp.add_text(f'{name} <= {h:g} mm', height=1.4, dxfattribs={'layer': 'LABELS'}).set_placement((a + 0.8, e - 2.2))
    for (a, b, c, e) in tray_footprint_local():
        msp.add_lwpolyline([(a, c), (b, c), (b, e), (a, e)], close=True, dxfattribs={'layer': 'TRAY'})
    doc.saveas(os.path.join(d, 'atlas_power_outline.dxf'))

    fig, ax = plt.subplots(figsize=(13, 13 * (W + 14) / (L + 10) + 1.0), dpi=130)
    ax.add_patch(Polygon(pts, closed=True, fill=False, lw=2))
    for (lab, a, b, c, e, style, col) in blocks():
        if style == 'zone':
            ax.add_patch(Rectangle((a, c), b - a, e - c, facecolor=col, alpha=0.10, edgecolor=col, lw=0.8))
            ax.text(a + 0.8, c + 1.0, lab, fontsize=6.5, color=col)
        elif style == 'shadow':
            ax.add_patch(Rectangle((a, c), b - a, e - c, fill=False, edgecolor=col, lw=1.4, ls='--'))
            ax.text(a + 1.0, e - 2.5, lab, fontsize=7, color=col)
        elif style == 'window':
            ax.add_patch(Rectangle((a, c), b - a, e - c, facecolor=col, alpha=0.35, edgecolor=col))
            ax.text(a, c - 2.0, lab, fontsize=5.5, color=col, rotation=0)
        else:
            ax.add_patch(Rectangle((a, c), b - a, e - c, facecolor=col, alpha=0.6, edgecolor=col))
            ax.text(b + 0.6, c, lab, fontsize=5.5, color=col)
    for (a, b, c, e) in tray_footprint_local():
        ax.add_patch(Rectangle((a, c), b - a, e - c, facecolor='#8c564b', alpha=0.07, edgecolor='none'))
    for (hx, hy) in holes:
        ax.add_patch(Circle((hx, hy), 1.6, fill=False, lw=1.2))
        ax.add_patch(Circle((hx, hy), kit.POWER_HOLE_KEEPOUT / 2, fill=False, lw=0.6, ls=':'))
    if notch:
        ax.text(notch[0] - 6, notch[3] + 1.0, 'servo-lead notch', fontsize=6)
    ax.annotate('car front (+x)', xy=(L, W / 2), xytext=(L - 26, W + 4), fontsize=8, arrowprops=dict(arrowstyle='->'))
    ax.set_xlim(-6, L + 6); ax.set_ylim(-10, W + 8); ax.set_aspect('equal')
    ax.set_xlabel('mm, from the rear edge'); ax.set_ylabel('mm, from the right edge (car left is up)')
    ax.set_title(f'ATLAS-PWR-1 power board rev B, {L:g} x {W:g} mm: height map (green <= {P["POWER_LOW_H"]:g} mm, red <= '
                 f'{P["POWER_TALL_H"]:g} mm), tray rails (brown), holes and keep-outs; blue = connector positions the mech '
                 f'model assumes', fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(d, 'atlas_power_placement.png')); plt.close(fig)
    return dict(size_mm=[L, W], car_origin=[X0, Y0], pcb_z=P['POWER_Z'], outline_local=pts, holes_local=holes, hole_d=3.2,
                hole_keepout_d=kit.POWER_HOLE_KEEPOUT, servo_notch_local=notch,
                height_zones_local=[dict(name=n, x=[a, b], y=[c, e], max_h=h) for (n, a, b, c, e, h) in kit.power_zones()],
                devkit_shadow_local=dict(x=[car_to_local(P['DEVKIT'][0], 0)[0], car_to_local(P['DEVKIT'][1], 0)[0]],
                                         y=[car_to_local(0, P['DEVKIT'][2])[1], car_to_local(0, P['DEVKIT'][3])[1]]),
                tray_underside_above_pcb_top=P['STACK_H'], tray_rails_local=tray_footprint_local(),
                edges=EDGES, mech_assumed_connectors_local={k: list(v) for k, v in extras.POWER_CONN.items()},
                pod_windows_car_x={n: [xc - w / 2, xc + w / 2, z0, z1] for (n, xc, w, z0, z1) in P['POD_WINDOWS']},
                lidar_plug_ends_car_x=round(kit.LIDAR_PLUG_END_X, 2))


if __name__ == '__main__':
    path = os.path.join(HERE, 'outlines.json')
    old = json.load(open(path)) if os.path.exists(path) else {}
    info = {}
    for k in ('drive', 'brain'):                    # rev A entries, kept as history
        if k in old:
            info[f'reva_{k}'] = old[k]
        elif f'reva_{k}' in old:
            info[f'reva_{k}'] = old[f'reva_{k}']
    info['power'] = make()
    with open(path, 'w') as f:
        json.dump(info, f, indent=1)
    print(json.dumps(info['power'], indent=1))
