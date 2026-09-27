"""Board outlines, mounting holes and the placement plan for the two stacked boards, taken from
the same numbers as ../mech/kit.py so the PCBs and the printed deck agree.

    python3 board_outlines.py     -> drive/*.dxf, drive/*_placement.png, brain/*.dxf, brain/*_placement.png

Board-local frame: X along the car (+x forward) from the board's rear edge, Y across the car
(+y = car left) from the board's right edge, both in mm; top view. Import the DXF into KiCad
(File > Import > Graphics, layer Edge.Cuts for the OUTLINE layer).
"""
import os, sys, json
import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'mech'))
import kit  # noqa: E402

P = kit.P
D = P['DRIVE']; B = P['BRAIN']

# (label, x0, x1, y0, y1, side, colour) in board-local mm
DRIVE_BLOCKS = [
    ('ESC power stage: 12 x CSD18510Q5B + 3 x 0.2 mOhm shunts (BOTTOM, on the heat spreader); 1210 ceramics above it on top', 30, 80, 4, 48, 'bottom', '#d62728'),
    ('bulk caps 4-6 x 470 uF 35 V (outside the brain board)', 8, 19, 10, 58, 'top', '#9467bd'),
    ('motor A/B/C pads + 4 mm bullets', -1, 6, 6, 30, 'top', '#8c564b'),
    ('hall JST-ZH 6p', 0, 8, 32, 40, 'top', '#8c564b'),
    ('E-STOP loop', 0, 6, 42, 48, 'top', '#8c564b'),
    ('USB-C charge + debug', -1, 9, 60, 70, 'top', '#1f77b4'),
    ('power button + LEDs', 0, 8, 72, 80, 'top', '#1f77b4'),
    ('charger BQ25798 + TPS25751D + EEPROM', 10, 32, 60, 80, 'top', '#1f77b4'),
    ('USB2514B hub + CP2102N', 32, 48, 66, 80, 'top', '#17becf'),
    ('BMS BQ7791508 + 8 x FET + 0.5 mOhm sense + INA228', 48, 84, 70, 88, 'top', '#2ca02c'),
    ('pack B+ / B- pads (10 AWG)', 50, 76, 86, 91, 'top', '#2ca02c'),
    ('pack sense JST-XH 7p', 86, 98, 82, 90, 'top', '#2ca02c'),
    ('e-switch TPS48111 + 4 x FET + precharge + shunt, LTC2955', 22, 58, 48, 64, 'top', '#ff7f0e'),
    ('STM32F405 + DRV8323RS + LSM6DSO + TCAN1042', 84, 112, 22, 54, 'top', '#e377c2'),
    ('stack header 2 x 20 (to brain board)', 60, 111, 60, 65, 'top', '#7f7f7f'),
    ('servo supply TPSM63610 (7.4 V, 8 A)', 108, 126, 6, 20, 'top', '#bcbd22'),
    ('servo 3-pin', 132, 141, 6, 14, 'top', '#bcbd22'),
    ('lidar eFuse TPS2660 + 2-pin terminal', 118, 141, 36, 50, 'top', '#bcbd22'),
    ('CAN JST-GH 4p', 132, 141, 56, 64, 'top', '#bcbd22'),
]
BRAIN_BLOCKS = [
    ('Jetson Orin Nano module on 260-pin SO-DIMM (+ dev-kit heatsink/fan above)', 22, 94, 12, 72, 'top', '#d62728'),
    ('M.2 Key M 2280 NVMe (BOTTOM)', 10, 90, 10, 32, 'bottom', '#9467bd'),
    ('M.2 Key E 2230 Wi-Fi', 96, 118, 58, 88, 'top', '#9467bd'),
    ('RJ45 #1 camera, PoE PSE (magjack from the Antmicro design)', 100, 122, 12, 28, 'top', '#1f77b4'),
    ('RJ45 #2 lidar (LAN7800 on USB 3)', 100, 122, 32, 48, 'top', '#1f77b4'),
    ('PoE: LT8362 52 V boost + TPS23861 auto PSE', 76, 99, 1, 11, 'top', '#17becf'),
    ('LAN7800 + 25 MHz', 86, 99, 34, 46, 'top', '#17becf'),
    ('module power (Antmicro supply sheet): eFuse, 5 V / 3.3 V bucks', 2, 20, 30, 80, 'top', '#2ca02c'),
    ('fan, RTC CR1220, reset / recovery buttons', 2, 20, 82, 89, 'top', '#ff7f0e'),
    ('stack header 2 x 20 (BOTTOM) + 1.8/3.3 V level shifters', 40, 91, 60, 65, 'bottom', '#7f7f7f'),
]


def local_holes(holes, x0, y0):
    return [(round(x - x0, 2), round(y - y0, 2)) for (x, y) in holes]


def make(name, outline, holes, extra_holes, blocks, title):
    x0, x1, y0, y1 = outline
    L, W = x1 - x0, y1 - y0
    d = os.path.join(HERE, name); os.makedirs(d, exist_ok=True)
    doc = ezdxf.new('R2010'); msp = doc.modelspace()
    for lay in ('OUTLINE', 'HOLES', 'PLACEMENT', 'LABELS'):
        doc.layers.add(lay)
    msp.add_lwpolyline([(0, 0), (L, 0), (L, W), (0, W)], close=True, dxfattribs={'layer': 'OUTLINE'})
    hs = local_holes(holes, x0, y0) + local_holes(extra_holes, x0, y0)
    for (hx, hy) in hs:
        msp.add_circle((hx, hy), 1.6, dxfattribs={'layer': 'HOLES'})
    for (lab, a, b, c, e, side, col) in blocks:
        msp.add_lwpolyline([(a, c), (b, c), (b, e), (a, e)], close=True, dxfattribs={'layer': 'PLACEMENT'})
        msp.add_text(f'{lab} [{side}]', height=1.2, dxfattribs={'layer': 'LABELS'}).set_placement((a + 0.5, e - 1.8))
    doc.saveas(os.path.join(d, f'atlas_{name}_outline.dxf'))
    fig, ax = plt.subplots(figsize=(12, 12 * W / L + 1.2), dpi=130)
    ax.add_patch(Rectangle((0, 0), L, W, fill=False, lw=2))
    for (lab, a, b, c, e, side, col) in blocks:
        ax.add_patch(Rectangle((a, c), b - a, e - c, facecolor=col, alpha=0.18 if side == 'top' else 0.08,
                               edgecolor=col, lw=1.4, ls='-' if side == 'top' else '--'))
        ax.text(a + 0.8, e - 1.0, lab + ('' if side == 'top' else ' (bottom)'), fontsize=6.3, va='top', color='black', wrap=True)
    for (hx, hy) in hs:
        ax.add_patch(Circle((hx, hy), 1.6, fill=False, lw=1.2))
    ax.annotate('car front (+x)', xy=(L, W / 2), xytext=(L - 22, W + 3), fontsize=8, arrowprops=dict(arrowstyle='->'))
    ax.set_xlim(-4, L + 4); ax.set_ylim(-4, W + 7); ax.set_aspect('equal')
    ax.set_xlabel('mm, from the rear edge'); ax.set_ylabel('mm, from the right edge (car left is up)')
    ax.set_title(title, fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(d, f'atlas_{name}_placement.png')); plt.close(fig)
    return dict(size_mm=[L, W], holes_local=hs)


if __name__ == '__main__':
    rear_standoffs = kit.BRAIN_HOLES[:2]
    info = {
        'drive': make('drive', D, kit.DRIVE_HOLES, rear_standoffs, DRIVE_BLOCKS,
                      'ATLAS-DRV-1 drive board, 140 x 90 mm, 4 layers 2 oz: top view, dashed = bottom side'),
        'brain': make('brain', B, kit.BRAIN_HOLES, [], BRAIN_BLOCKS,
                      'ATLAS-BRN-1 brain board (Jetson carrier), 120 x 90 mm, 8 layers: top view, dashed = bottom side'),
    }
    with open(os.path.join(HERE, 'outlines.json'), 'w') as f:
        json.dump(info, f, indent=1)
    print(json.dumps(info, indent=1))
