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


# what sits at each edge in agent D's layout (boards/power/HANDOFF_E.md, 24 Oct); the positions are in
# extras.POWER_CONN and the right pod's windows in kit.P['POD_WINDOWS']
EDGES = {
    'Y=84 (pack side)': 'pack BAT+ / BAT- pads (10 AWG pigtail to an XT90 male), BMS UART J201 JST-XH 4, dev-kit DEV+ / DEV- pads, Pico micro-USB',
    'X=0 (rear, ESC bay)': 'ESC+ / ESC- pads, fan header J1003, FSESC COMM J903 JST-PH 7, SERVO_IN J904, BEC_OUT J403, BEC and servo-supply pads',
    'X=L (front)': 'servo J406, lidar power J409 Phoenix, camera regulator input pads MOD402, E-stop J1001, remote button J1002',
    'Y=0 (right, pod side)': 'hub USB-C (laptop), dev-kit USB-A J601 on its edge, power button SW401 (right angle), status LEDs; the PD trigger and the CC/CV module are off the board in the pod',
    'middle': 'J12 box header J801, J14 header J802, PD-trigger and CC/CV pads, FSESC USB header J602, spare J603, Pico and hub modules on sockets, Pololu latch pads, R-78E, FET switch with its heatsink bar',
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
    if P['FET_SHIELD']:
        a, b, c, d = P['FET_SHIELD_XY']
        B.append((f'acrylic FET shield under the tray (parts <= {P["FET_SHIELD_MAX_H"]:g} mm here)', a, b, c, d, 'shadow', '#e377c2'))
        fb = P['FET_BAR']
        B.append(('heatsink bar + FET tabs (BAT+)', fb[0], fb[1], fb[2], fb[3], 'window', '#d62728'))
    for name, (X, Y, h) in extras.POWER_CONN.items():
        B.append((f'{name}', X - 2, X + 2, Y - 2, Y + 2, 'conn', '#1f77b4'))
    for (name, xc, w, z0, z1, walls) in kit.pod_windows():
        X = xc - X0
        B.append((f'pod window {name} ({walls}, z {z0:g}-{z1:g})', X - w / 2, X + w / 2, -6, 0, 'window', '#9467bd'))
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
    nwin = 0
    for (lab, a, b, c, e, style, col) in blocks():
        if style == 'zone':
            ax.add_patch(Rectangle((a, c), b - a, e - c, facecolor=col, alpha=0.10, edgecolor=col, lw=0.8))
            ax.text(a + 0.8, c + 1.0, lab, fontsize=6.5, color=col)
        elif style == 'shadow':
            ax.add_patch(Rectangle((a, c), b - a, e - c, fill=False, edgecolor=col, lw=1.4, ls='--'))
            ax.text(a + 1.0, e - 2.5, lab, fontsize=7, color=col)
        elif style == 'window':
            ax.add_patch(Rectangle((a, c), b - a, e - c, facecolor=col, alpha=0.35, edgecolor=col))
            ax.text(a, c - 2.0 - 1.6 * (nwin % 3 if c < 0 else 0), lab, fontsize=5.5, color=col, rotation=0)
            nwin += 1 if c < 0 else 0
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
    ax.set_xlim(-6, L + 6); ax.set_ylim(-13, W + 8); ax.set_aspect('equal')
    ax.set_xlabel('mm, from the rear edge'); ax.set_ylabel('mm, from the right edge (car left is up)')
    ax.set_title(f'ATLAS-PWR-1 power board rev B, {L:g} x {W:g} mm: height map (green <= {P["POWER_LOW_H"]:g} mm, red <= '
                 f'{P["POWER_TALL_H"]:g} mm), tray rails (brown), holes and keep-outs; blue = connector positions (agent D, '
                 f'HANDOFF_E) used for the cable runs', fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(d, 'atlas_power_placement.png')); plt.close(fig)
    return dict(size_mm=[L, W], car_origin=[X0, Y0], pcb_z=P['POWER_Z'], outline_local=pts, holes_local=holes, hole_d=3.2,
                hole_keepout_d=kit.POWER_HOLE_KEEPOUT, servo_notch_local=notch,
                height_zones_local=[dict(name=n, x=[a, b], y=[c, e], max_h=h) for (n, a, b, c, e, h) in kit.power_zones()],
                devkit_shadow_local=dict(x=[car_to_local(P['DEVKIT'][0], 0)[0], car_to_local(P['DEVKIT'][1], 0)[0]],
                                         y=[car_to_local(0, P['DEVKIT'][2])[1], car_to_local(0, P['DEVKIT'][3])[1]]),
                tray_underside_above_pcb_top=P['STACK_H'], tray_rails_local=tray_footprint_local(),
                edges=EDGES, connectors_local={k: list(v) for k, v in extras.POWER_CONN.items()},
                connectors_note='board X, Y and the cable entry height above the board top, from agent D (HANDOFF_E, 24 Oct); heights are estimates',
                pod_windows_car_x={n: [xc - w / 2, xc + w / 2, z0, z1, walls] for (n, xc, w, z0, z1, walls) in kit.pod_windows()},
                lidar_plug_ends_car_x=round(kit.LIDAR_PLUG_END_X, 2),
                fet_shield=dict(on=bool(P['FET_SHIELD']), rect_local=list(P['FET_SHIELD_XY']), screws_local=[list(v) for v in P['FET_SHIELD_SCREWS']],
                                max_part_h_under=P['FET_SHIELD_MAX_H'], fet_bar_local=list(P['FET_BAR']),
                                note='3 mm acrylic hung under the tray; nylon nuts under it at the two screws need 2.4 mm, so keep parts under those two points at 18 mm or less'))


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
