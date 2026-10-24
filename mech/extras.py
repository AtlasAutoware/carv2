"""Atlas car v2: the parts that finish the car, on top of mech/kit.py (rev B).

    python3 extras.py         build, check against the whole kit, export STEP/STL, write out/extras_report.json

What is here (see docs/COMPLETE_CAR.md for why each one exists; NOTES_REVB.md for what changed in rev B):

  stack_canopy      printed cover over the dev kit and the plugs on its I/O edge, on the four pillars printed on
                    the dev-kit tray and the canopy leg in zone B. Grille 8 mm over the dev kit's fan, two RP-SMA
                    holes for the Wi-Fi antennas on the rear edge.
  bench_stand       printed stand that holds the chassis with the wheels off the bench, for the ESC bench tests
                    at 50 A and 70 A (ARCHITECTURE.md, First power-up).
  cables            every cable run as a path through the model, so its length is known and its clearance is
                    checked like any other part: camera data and power, lidar Ethernet (through its USB dongle) and
                    power (through its regulator on the arch), dev-kit DC lead, 40-pin ribbon, J14 harness, the
                    dev kit's USB-C to J601, the Pico and FSESC USB leads, motor phases, hall sensor, servo, ESC
                    battery leads, pack leads through the fuse and the BMS to the XT90 pair, the board's pack
                    pigtail, balance lead, BMS UART, charge-module wires, side-pod fan, Wi-Fi pigtails.
  bought parts      the lidar RJ45 plug on its dongle, the charge and laptop USB-C plugs through the right pod, the
                    right-angle USB-A plug in J601, the antenna bulkheads and antennas, as envelopes for the checks.

Same frame and parameters as kit.py: +x forward, +y car left, +z up, origin at the deck centre, deck top at z 0.
Chassis numbers are kit.py's estimates (docs/MEASURE_FIRST.md). The power-board connector positions in POWER_CONN
are agent D's (boards/power/HANDOFF_E.md, 24 Oct); the heights of the plugs on them are estimates.
"""
import os
import sys
import json
import math
import itertools

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kit  # noqa: E402
from shapely.geometry import Polygon  # noqa: E402
from kit import P, box, cylz, cyl, union, volume, n_solids, inter, bb_overlap, M3_CLEAR, pw, dk  # noqa: E402
from kit import Sheet, sbox, Point, unary_union, at_z, in_xz, in_yz, tab_centres, slot, tabs_on  # noqa: E402

OUT = kit.OUT

# ----------------------------------------------------------------------------- the rev B stack, from kit.py
Z_POWER_TOP = kit.Z_POWER_TOP                   # 8.6
Z_TRAY_TOP = kit.Z_TRAY1                        # 36.6
Z_DEVKIT_BOT = kit.Z_DEVKIT0                    # 43.6
Z_DEVKIT_TOP = kit.Z_DEVKIT1                    # 45.17
Z_SINK_TOP = kit.Z_SINK_TOP                     # 77.17, top of the dev kit's heatsink and fan
Z_CANOPY = kit.Z_CANOPY                         # 85.6, canopy underside: 8.4 mm over the fan

# ----------------------------------------------------------------------------- canopy
SHEET_CANOPY = 'canopy' in kit.SHEET
CANOPY_T = P['SHEET_T'] if SHEET_CANOPY else 2.4
CANOPY_LIP = 4.0                # stiffening lip hanging down around the edge (printed canopy)
CANOPY_POSTS = kit.tray_pillars() + [kit.CANOPY_LEG_XY]
_px = [p[0] for p in kit.tray_pillars()]
CANOPY_XY = (min(_px) - 8.0, max(_px) + 8.0, kit.POWER[2] - 4.0, 57.0)   # y1: 1.3 mm inboard of the BMS holder
CANOPY_R = 6.0                  # (12 until 24 Oct: its inner corner fillet reached the right-hand posts)
_j = P['JETSON_XY']
JETSON_BOX = (dk(_j[0], 0)[0], dk(_j[1], 0)[0], dk(0, _j[2])[1], dk(0, _j[3])[1])
FAN_C = ((JETSON_BOX[0] + JETSON_BOX[1]) / 2, (JETSON_BOX[2] + JETSON_BOX[3]) / 2)
GRILLE_R = 25.0                 # hex grille over the dev-kit fan (about 40 mm)
# RP-SMA bulkheads: 1/4-36 UNS thread, 6.5 mm hole with a 5.8 mm flat so the jack cannot turn; on the rear edge
ANTENNAS = [(CANOPY_XY[0] + 7.0, -4.0), (CANOPY_XY[0] + 7.0, -50.0)]
RPSMA_HOLE, RPSMA_FLAT = 6.5, 5.8
ANTENNA_L = 120.0               # Bingfu 3 dBi dual-band swivel dipole (Amazon B082SHKT3Q), 12 cm
# laser-cut canopy: a slot-and-tab box in SHEET_T sheet. The skirts stand 2.5 mm in from the top plate's edge so the
# slots are closed, which makes the box 4 mm bigger a side than the printed canopy and keeps 1.5 mm from the posts.
SHEET_CANOPY_XY = (CANOPY_XY[0] - 4.0, CANOPY_XY[1] + 4.0, CANOPY_XY[2] - 4.0, CANOPY_XY[3])
SKIRT_INSET = 2.5


def grille_holes():
    af, pitch = 5.0, 6.6
    cx, cy = FAN_C
    holes = []
    rows = int(GRILLE_R / (pitch * math.sqrt(3) / 2)) + 1
    for j in range(-rows, rows + 1):
        yy = cy + j * pitch * math.sqrt(3) / 2
        off = (pitch / 2) if j % 2 else 0.0
        for i in range(-6, 7):
            xx = cx + i * pitch + off
            if math.hypot(xx - cx, yy - cy) <= GRILLE_R - af / 2:
                holes.append((xx, yy))
    return holes, af


def sheet_canopy():
    """the canopy as a 3 mm slot-and-tab box: a top plate (posts, RP-SMA D-holes, hex grille, engraved name) and four
    skirts CANOPY_SKIRT_H deep whose top tabs go through closed slots in the top; the corners are a three-finger box
    joint (the long skirts keep the top and bottom thirds, the short skirts' fingers fill the middle third)"""
    t, H = P['SHEET_T'], P['CANOPY_SKIRT_H']
    x0, x1, y0, y1 = SHEET_CANOPY_XY
    xs0, xs1, ys0, ys1 = x0 + SKIRT_INSET, x1 - SKIRT_INSET, y0 + SKIRT_INSET, y1 - SKIRT_INSET
    zt, zb = kit.Z_CANOPY, kit.Z_CANOPY - H
    fz0, fz1 = zb + H / 3, zb + 2 * H / 3                        # the middle third: the short skirts' fingers
    hx, af = grille_holes()
    hexes = [Polygon([(xx + af / math.sqrt(3) * math.cos(math.radians(60 * k)), yy + af / math.sqrt(3) * math.sin(math.radians(60 * k)))
                      for k in range(6)]) for (xx, yy) in hx]
    dholes = [Point(x, y).buffer(RPSMA_HOLE / 2, 32).intersection(sbox(x - RPSMA_HOLE, y - RPSMA_FLAT / 2, x + RPSMA_HOLE, y + RPSMA_FLAT / 2))
              for (x, y) in ANTENNAS]
    slots = [slot(c, ys0) for c in tab_centres(xs0, xs1)] + [slot(c, ys1 - t) for c in tab_centres(xs0, xs1)]
    slots += [slot(c, xs0, along_x=False) for c in tab_centres(ys0 + t, ys1 - t)]
    slots += [slot(c, xs1 - t, along_x=False) for c in tab_centres(ys0 + t, ys1 - t)]
    top = sbox(x0, y0, x1, y1).buffer(-2.0).buffer(2.0, 8).difference(unary_union(hexes + dholes + slots))
    mat = '3 mm laser-grade birch plywood (tougher in a roll) or 3 mm clear cast acrylic'
    S = {'laser_canopy_top': Sheet('laser_canopy_top', top, [(x, y, P['LASER_HOLE_M3']) for (x, y) in CANOPY_POSTS],
                                   [('ATLAS', 40.0, 34.0, 13.0)], mat, 1, at_z(zt))}
    # long skirts (along x, right and left): notches at both ends in the middle third
    lng = sbox(xs0, zb, xs1, zt).difference(sbox(xs0 - 1, fz0, xs0 + t, fz1)).difference(sbox(xs1 - t, fz0, xs1 + 1, fz1))
    lng = unary_union([lng] + tabs_on(zt, xs0, xs1))
    S['laser_canopy_skirt_right'] = Sheet('laser_canopy_skirt_right', lng, [], [], mat, 1, in_xz(ys0))
    S['laser_canopy_skirt_left'] = Sheet('laser_canopy_skirt_left', lng, [], [], mat, 1, in_xz(ys1 - t))
    # short skirts (along y, rear and front): fingers into the long skirts' notches
    sht = unary_union([sbox(ys0 + t, zb, ys1 - t, zt), sbox(ys0, fz0, ys0 + t + 0.01, fz1), sbox(ys1 - t - 0.01, fz0, ys1, fz1)]
                      + tabs_on(zt, ys0 + t, ys1 - t))
    S['laser_canopy_skirt_rear'] = Sheet('laser_canopy_skirt_rear', sht, [], [], mat, 1, in_yz(xs0))
    S['laser_canopy_skirt_front'] = Sheet('laser_canopy_skirt_front', sht, [], [], mat, 1, in_yz(xs1 - t))
    return S


def canopy_outline():
    x0, x1, y0, y1 = CANOPY_XY
    return box(x0, x1, y0, y1, 0, 1).edges('|Z').fillet(CANOPY_R)


def stack_canopy():
    """the printed canopy"""
    x0, x1, y0, y1 = CANOPY_XY
    top = box(x0, x1, y0, y1, Z_CANOPY, Z_CANOPY + CANOPY_T).edges('|Z').fillet(CANOPY_R)
    outer = box(x0, x1, y0, y1, Z_CANOPY - CANOPY_LIP, Z_CANOPY).edges('|Z').fillet(CANOPY_R)
    inner = box(x0 + 2, x1 - 2, y0 + 2, y1 - 2, Z_CANOPY - CANOPY_LIP - 1, Z_CANOPY + 0.01).edges('|Z').fillet(CANOPY_R - 2)
    c = top.union(outer.cut(inner))
    try:
        c = c.edges('not |Z').edges('>Z').fillet(1.2)          # soften the top edge
    except Exception:
        pass
    # pads under the posts and the two antenna jacks
    for (x, y) in CANOPY_POSTS:
        c = c.union(cylz(x, y, Z_CANOPY - 1.0, Z_CANOPY + 0.01, 10.0))
    for (x, y) in ANTENNAS:
        c = c.union(cylz(x, y, Z_CANOPY - 2.0, Z_CANOPY + 0.01, 14.0))
    # holes: M3 clearance at the posts (M3 x 8 button heads into the posts' inserts), RP-SMA with its flat
    for (x, y) in CANOPY_POSTS:
        c = c.cut(cylz(x, y, Z_CANOPY - 3, Z_CANOPY + CANOPY_T + 1, M3_CLEAR))
    for (x, y) in ANTENNAS:
        h = cylz(x, y, Z_CANOPY - 4, Z_CANOPY + CANOPY_T + 1, RPSMA_HOLE).intersect(
            box(x - RPSMA_HOLE, x + RPSMA_HOLE, y - RPSMA_FLAT / 2, y + RPSMA_FLAT / 2, Z_CANOPY - 5, Z_CANOPY + 5))
        c = c.cut(h)
    # hex grille over the dev kit's fan: 5 mm across flats, 6.6 mm pitch, inside GRILLE_R
    af, pitch = 5.0, 6.6
    cx, cy = FAN_C
    holes = []
    rows = int(GRILLE_R / (pitch * math.sqrt(3) / 2)) + 1
    for j in range(-rows, rows + 1):
        yy = cy + j * pitch * math.sqrt(3) / 2
        off = (pitch / 2) if j % 2 else 0.0
        for i in range(-6, 7):
            xx = cx + i * pitch + off
            if math.hypot(xx - cx, yy - cy) <= GRILLE_R - af / 2:
                holes.append((xx, yy))
    grille = None
    for (xx, yy) in holes:
        h = (cq.Workplane('XY').polygon(6, af / math.cos(math.radians(30))).extrude(CANOPY_T + 2)
             .translate((xx, yy, Z_CANOPY - 1)))
        grille = h if grille is None else grille.union(h)
    c = c.cut(grille)
    # the team name, engraved 0.6 mm into the top (prints first, on the bed), over the plugs
    txt = (cq.Workplane('XY').text('ATLAS', 13.0, 0.6, font='DejaVu Sans', kind='bold', halign='center', valign='center')
           .translate((40.0, 34.0, Z_CANOPY + CANOPY_T - 0.6)))
    c = c.cut(txt)
    return c, len(holes)


def antennas(tilt_deg=0.0):
    """RP-SMA bulkhead jack (nut and body under the canopy) and a dipole on top. tilt swings it backwards."""
    under, over = [], []
    for (x, y) in ANTENNAS:
        under.append(cylz(x, y, Z_CANOPY - 8.0, Z_CANOPY - 2.0, 9.2))           # nut + jack body under the pad
        base = cylz(x, y, Z_CANOPY + CANOPY_T, Z_CANOPY + CANOPY_T + 16.0, 10.0)
        whip = cylz(x, y, Z_CANOPY + CANOPY_T + 16.0, Z_CANOPY + CANOPY_T + ANTENNA_L, 9.0)
        a = base.union(whip)
        if tilt_deg:
            a = a.rotate((x, y, Z_CANOPY + CANOPY_T + 8.0), (x, y + 1, Z_CANOPY + CANOPY_T + 8.0), -tilt_deg)
        over.append(a)
    return union(*under), union(*over)


# ----------------------------------------------------------------------------- mating plugs
def rj45_plug_down(x_mid, y_mid, z_face):
    """RJ45 plug (12.2 x 10 mm body, 21 mm long) and strain-relief boot (14 x 10, 11 mm), leaving a jack face at z_face
    downward"""
    body = box(x_mid - 5.0, x_mid + 5.0, y_mid - 6.1, y_mid + 6.1, z_face - 21.0, z_face)
    boot = box(x_mid - 5.0, x_mid + 5.0, y_mid - 7.0, y_mid + 7.0, z_face - 32.0, z_face - 21.0)
    return body.union(boot), (x_mid, y_mid, z_face - 32.0)


_ue = kit.USB_ETH_BOX
LID_JACK = ((_ue[0] + _ue[1]) / 2, (_ue[2] + _ue[3]) / 2, _ue[4])        # the dongle's RJ45 jack, facing down


def usbc_through_pod(name, face_y):
    """a USB-C plug pushed through a right-pod window into a receptacle whose face is at car y `face_y`: shell 8.4 x 2.6
    into the receptacle, overmold 12.5 x 7 x 22 mm and 15 mm of strain relief, centred on the window"""
    w = kit.pod_window(name)
    if w is None:
        return None, None
    _, xc, ww, z0, z1, _ = w
    zc = (z0 + z1) / 2
    return box(xc - 6.25, xc + 6.25, face_y - 0.5 - 37.0, face_y - 0.5, zc - 3.5, zc + 3.5), (xc, zc, ww, z0, z1)


def j601_plug():
    """right-angle USB-A plug in J601 (the receptacle stands on its edge, opening facing -y): the head beyond the
    receptacle face (J601_PLUG, an estimate) and the point where its cable leaves upward, in the gap between the board
    edge and the pod's inner wall"""
    X, Y, h = POWER_CONN['j601']
    x, y = pw(X, Y)
    zc = Z_POWER_TOP + h
    wx, ly, hz = P['J601_PLUG']
    # the receptacle face is 0.5 mm inside the board edge; the head is taken to stop at the edge (an overmold that
    # reaches below the shell would hit the PCB there)
    head = box(x - wx / 2, x + wx / 2, y - ly, min(y, kit.POWER[2]), zc - hz / 2, zc + hz / 2)
    return head, (x, -(kit.POD['y_in'] - 2.5), zc + hz / 2)


# ----------------------------------------------------------------------------- power-board connectors
# board-local (X, Y, height of the cable entry above the PCB top), from agent D's layout (boards/power/HANDOFF_E.md,
# "Real connector positions", 24 Oct). Positions are pad-group centres; the heights are estimates of the header plus
# its mating plug (D's where given). The front-edge entries keep their distance from the front edge if POWER_L changes.
L_ = P['POWER_L']
_F = L_ - 130.0
POWER_CONN = dict(
    esc_plus=(5.0, 42.0, 1.5), esc_minus=(5.0, 54.0, 1.5),     # ESC+ / ESC- wire pads, 10-12 AWG soldered from above
    vesc_comm=(2.7, 27.6, 8.0),             # J903 JST-PH 7 vertical, rear edge (pins Y 21.6-33.6)
    fan=(3.6, 13.4, 11.0),                  # J1003 4-pin fan header, rear edge (pins Y 9.6-17.2)
    bat_plus=(19.5, 79.6, 1.5), bat_minus=(6.25, 65.6, 1.5),   # pack pigtail pads, 10 AWG over the Y = 84 edge
    bms_uart=(85.3, 81.0, 10.0),            # J201 JST-XH 4 vertical, pack edge
    dev_plus=(92.0, 74.0, 1.5), dev_minus=(92.0, 68.2, 1.5),   # dev-kit DC lead pads, 18 AWG
    pico_usb=(106.5, 83.4, 13.9),           # the Pico's micro-USB, facing +Y (D: 13.9 mm above the board)
    hub_usbc=(88.5, -0.4, 14.2),            # the hub module's USB-C, facing -Y: the laptop port (D: centre about 14.2)
    j601=(102.8, 0.5, P['J601_H'] / 2),     # USB-A on its edge, face at Y 0.5, opening facing -Y (height: estimate)
    j602=(109.3, 16.0, 12.0),               # 1 x 4 header for the FSESC USB (Adafruit 4449 jack lead, D's choice)
    j12_box=(41.1, 7.3, 18.0),              # J801 2 x 20 shrouded box header + IDC plug (D: about 18)
    j14_hdr=(93.0, 48.4, 14.0),             # J802 1 x 12 vertical header + Dupont housing
    chg_pd=(19.3, 21.0, 1.5), chg_cccv=(26.9, 24.0, 1.5),     # PD-trigger and CC/CV wire pads (modules in the pod)
    servo=(127.6 + _F, 17.1, 17.0),         # J406 1 x 3, front edge (servo plug about 17 mm, D's estimate for J403)
    lidar_pwr=(125.0 + _F, 26.8, 4.5),      # J409 Phoenix PT 1,5/2-3,5-H, wires enter from +X
    camera_pads=(125.1 + _F, 44.6, 1.5),    # MOD402 camera regulator input pads (VIN Y 46.5, GND Y 42.7)
)


def pc(name, dz=0.0):
    X, Y, h = POWER_CONN[name]
    x, y = pw(X, Y)
    return (x, y, Z_POWER_TOP + h + dz)


# ----------------------------------------------------------------------------- cables
def catmull(pts, step=4.0):
    """smooth path through the waypoints (centripetal-ish Catmull-Rom), sampled about every `step` mm"""
    P_ = [pts[0]] + list(pts) + [pts[-1]]
    out = [pts[0]]
    for i in range(1, len(P_) - 2):
        p0, p1, p2, p3 = P_[i - 1], P_[i], P_[i + 1], P_[i + 2]
        seg = math.dist(p1, p2)
        n = max(2, int(seg / step))
        for k in range(1, n + 1):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[c]) + (-p0[c] + p2[c]) * t + (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * t2
                                    + (-p0[c] + 3 * p1[c] - 3 * p2[c] + p3[c]) * t3) for c in range(3)))
    return out


def path_len(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def plug_ends():
    io = kit.devkit_io_boxes()
    return {k: v['end'] for k, v in kit.devkit_plug_boxes(io).items()}


def cable_defs():
    D = {}
    pe = plug_ends()
    xf = kit.POWER[1]                                            # power board front edge (car x)
    zt = Z_POWER_TOP
    cam_axis = kit.ARCH_TOP + 4.0 + 14.5
    cam_x0 = P['LIDAR_FRONT_X'] - P['CAM_LENS_L'] - 45.0        # camera rear face
    cam_start = (cam_x0 - P['CAM_M12_L'], 6.0, cam_axis)         # end of kit's camera_plug (M12 X-coded)
    m8_top = (cam_x0 - 8.0, -8.0, kit.ARCH_TOP + 4.0 + 30.0)     # cable exit of the M8 right-angle plug ('Up')
    lid_eth = (kit.LIDAR_PLUG_END_X, 10.0, P['PLINTH_T'] + 9.0)  # ends of kit's lidar_connectors (M12)
    lid_pwr = (kit.LIDAR_PLUG_END_X, -10.0, P['PLINTH_T'] + 9.0)
    _, lid_boot = rj45_plug_down(*LID_JACK)
    motor_axis = (P['MOTOR_X'], kit.Z_RIM + P['MOTOR_AXIS_ABOVE_RIM'])
    y_bell = P['MOTOR_Y'][0] - 4.0                               # just outboard of the motor's end bell
    L_e, W_e, H_e = P['ESC_CASE']; ecx, ecy = P['ESC_C']
    e_rear, e_front = ecx - L_e / 2, ecx + L_e / 2
    ez = kit.CRADLE_T + 8.0
    po = P['PHASE_OPENING']; pox = (po[0] + po[1]) / 2; poy = po[2] + 6.0
    bx0, bx1, by0, by1, bz0, bz1 = kit.bms_place()
    bms_y = (by0 + by1) / 2

    # ---- camera: data from the dev kit's RJ45 over the pack lid and up to the camera, power from the board's front
    D['camera'] = dict(d=7.0, spec='M12 X-coded 8-pin to RJ45, Cat6a, data only (0.5 m cable)',
                       ends=('dev kit RJ45', 'camera M12'),
                       pts=[pe['rj45_camera'], (66.0, 54.0, 53.0), (72.0, 46.0, 54.0), (88.0, 30.0, 57.0), (100.0, 24.0, 63.0),
                            (108.0, 22.0, 66.0), (113.5, 18.0, 74.0), (114.0, 14.0, 95.0), (113.0, 9.0, 112.0), (113.5, 7.0, 118.0), cam_start])
    rg = kit.CAM_REG_BOX; rgx, rgy = (rg[0] + rg[1]) / 2, (rg[2] + rg[3]) / 2
    D['camera_power'] = dict(d=4.5, spec='LUCID GPIO-M8-5M-RA2-A cut to length: red (VAUX) and black (GND) to the 12 V regulator output, other six tied back',
                             ends=('camera M8 GPIO (right angle, up)', 'camera 12 V regulator output (on the arch, right leg)'),
                             pts=[m8_top, (m8_top[0] - 2, -8.0, m8_top[2] + 7.0), (138.0, -13.0, m8_top[2] + 8.0),
                                  (rgx + 1.0, rgy + 3.0, 122.0), (rgx, rgy, 98.0), (rgx, rgy, rg[5] + 4.0), (rgx, rgy, rg[5])])
    cp = pc('camera_pads')
    D['camera_reg_in'] = dict(d=3.0, spec='22 AWG pair, board MOD402 pads (VIN, GND) to the Pololu S18V20F12 input',
                              ends=('power board camera regulator pads MOD402 (front edge)', 'camera 12 V regulator input'),
                              pts=[(rgx, rgy, rg[4]), (rgx, rgy, rg[4] - 4.0), (rgx - 8.0, rgy - 0.5, 34.0), (112.0, -26.0, 30.0),
                                   (100.0, -24.0, 22.0), (cp[0] + 2.5, cp[1], cp[2] + 4.0), (cp[0], cp[1], cp[2] + 2.0), cp])
    # ---- lidar: Ethernet through the USB dongle on the arch, power from the board's front edge
    D['lidar_ethernet'] = dict(d=6.0, spec='donor SICK M12 D-coded 4-pin to RJ45 (TiM561 Ethernet), into the USB dongle',
                               ends=('USB-Ethernet dongle RJ45 (on the arch leg)', 'lidar Ethernet M12'),
                               pts=[lid_boot, (lid_boot[0] - 2.0, lid_boot[1] - 1.0, lid_boot[2] - 3.0), (lid_boot[0] - 8.0, lid_boot[1] - 4.0, 5.5),
                                    (114.0, 17.0, 8.0), (105.0, 12.5, 13.0), (109.0, 10.3, 15.0), lid_eth])
    D['lidar_usb'] = dict(d=4.0, spec="the dongle's own USB 3 lead (180 mm on the ZimaSpace RTL8153 adapter)",
                          ends=('USB-Ethernet dongle', 'dev kit USB-A (port 1)'),
                          pts=[(LID_JACK[0], LID_JACK[1], _ue[5] + 1.0), (LID_JACK[0], LID_JACK[1], _ue[5] + 4.0), (125.0, 30.0, 93.0),
                               (117.0, 40.0, 88.0), (110.0, 41.0, 72.0), (88.0, 35.0, 68.0), (60.0, 48.0, 60.0), (40.0, 54.0, 54.0),
                               (pe['usb_a_lidar'][0], pe['usb_a_lidar'][1] + 7.0, pe['usb_a_lidar'][2] + 1.0), pe['usb_a_lidar']])
    lp = pc('lidar_pwr')                                         # J409: the wires enter from +x
    lpts = [(lp[0] + 1.0, lp[1], lp[2]), (lp[0] + 5.0, lp[1], lp[2] + 0.3), (lp[0] + 10.0, lp[1] + 4.0, lp[2] + 0.8),
            (lid_pwr[0] - 6.0, lid_pwr[1] - 8.0, lid_pwr[2]), (lid_pwr[0] - 2.0, lid_pwr[1], lid_pwr[2]), lid_pwr]
    D['lidar_power'] = dict(d=5.5, spec='donor SICK M12 power cable, cut and stripped into the terminal',
                            ends=('power board lidar Phoenix 2-pin J409 (front edge)', 'lidar power M12'), pts=lpts)
    # ---- the dev kit's own leads
    dv = pw(POWER_CONN['dev_plus'][0], (POWER_CONN['dev_plus'][1] + POWER_CONN['dev_minus'][1]) / 2)
    dz = Z_POWER_TOP + POWER_CONN['dev_plus'][2]
    pdc = pe['dc_plug']
    D['devkit_dc'] = dict(d=4.5, spec='Tensility 10-01779 5.5 x 2.5 mm right-angle plug, 18 AWG pair, cut to length',
                          ends=('power board DEV+ / DEV- pads (pack side)', 'dev kit DC jack'),
                          pts=[(dv[0], dv[1], dz), (dv[0], dv[1], dz + 4.0), (dv[0] - 4.0, 5.0, 24.0), (48.0, 6.0, 28.0), (38.0, 6.5, 28.5),
                               (34.0, 14.0, 29.5), (30.0, 19.5, 33.5), (24.0, 19.5, 38.0), (10.0, 19.5, 38.5), (pdc[0], 20.5, 38.5), (pdc[0], 27.0, 39.0),
                               (pdc[0], pdc[1], pdc[2] - 3.5), pdc])
    jb = pc('j12_box')
    j12 = P['DEVKIT_J12']; jx = dk((j12[0] + j12[1]) / 2, 0)[0]; jy = dk(0, (j12[2] + j12[3]) / 2)[1]
    zi = Z_DEVKIT_TOP + 17.5
    for k, d in (('a', -22.0), ('b', 0.0), ('c', 22.0)):
        D[f'ribbon_40pin_{k}'] = dict(d=1.6, spec='2 x 20 IDC ribbon, 150 mm (Adafruit #1988); modelled as three lines across its width',
                                      ends=('dev kit J12 (40-pin)', 'power board 2 x 20 box header'), table=(k == 'b'),
                                      pts=[(jx + d, jy, zi), (jx + d, jy - 2.5, zi + 3.0), (jx + d, -68.0, zi + 3.0),
                                           (jx + d, -71.5, zi - 3.0), ((jx + jb[0]) / 2 + d, -71.5, 42.0),
                                           (jb[0] + d, -71.5, 31.0), (jb[0] + d, -67.0, 29.0), (jb[0] + d, jb[1] - 3.0, 29.0),
                                           (jb[0] + d, jb[1], jb[2])])
    j14 = P['DEVKIT_J14']; hx0 = dk(j14[0], 0)[0]; hy = P['DEVKIT'][2] - 9.0; hz = Z_DEVKIT_TOP + 1.5
    jh = pc('j14_hdr')
    # the bundle leaves the Dupont housing's rear end and drops between the ribbon and the laptop plug, then runs in under
    # the tray (over the parts, 2 mm under the tray, above the FSESC USB lead) to the 1 x 12 header in the board's middle
    D['j14'] = dict(d=4.0, spec='1 x 12 Dupont housing, 8 crimped wires (keyed with a printed clip)',
                    ends=('dev kit J14 (button header)', 'power board 1 x 12 header J802 (middle)'),
                    pts=[(hx0 + 2.0, hy, hz), (hx0 + 0.5, hy - 1.5, hz - 3.0), (47.5, -73.5, 37.0), (47.0, -73.0, 31.0),
                         (48.5, -67.0, 30.5), (55.0, -42.0, 30.0), (60.0, -27.0, 28.0), (jh[0], jh[1] - 2.0, jh[2] + 3.0), jh])
    # ---- dev kit USB-C to the board's J601 (hub port 1): right-angle USB-A plug, cable up the gap between the board
    # edge and the pod, forward past the J14 housing, over the carrier's front strip (in front of the heatsink) to the
    # I/O edge, then down and round under the USB-C plug into it from behind
    _, j6 = j601_plug()
    uc = pe['usb_c_hub']
    D['devkit_usb'] = dict(d=4.5, spec='USB-A right-angle plug (cable leaving the narrow side, so up here) to USB-C, 0.3 m, USB 2.0',
                           ends=('power board J601 USB-A (pod edge, hub port 1)', 'dev kit USB-C (device mode, 192.168.55.1)'),
                           pts=[j6, (j6[0], j6[1], j6[2] + 5.0), (j6[0] + 4.0, j6[1], 36.0), (82.0, -73.5, 40.0), (86.5, -72.0, 43.5),
                                (86.5, -66.0, 47.5), (85.5, -60.0, 49.5), (85.0, -40.0, 50.0), (85.5, 5.0, 50.5), (88.5, 14.0, 50.0),
                                (89.5, 19.0, 44.0), (89.5, 24.0, 37.0), (86.0, 36.0, 34.0), (81.5, 45.0, 40.0),
                                (uc[0], uc[1] + 1.5, uc[2] - 1.5), uc])
    pu = pc('pico_usb')
    D['pico_usb'] = dict(d=4.0, spec='micro-USB to USB-A, 0.3 m (supervisor USB CDC to the Jetson)',
                         ends=('Pico micro-USB (power board, pack edge)', 'dev kit USB-A (port 2)'),
                         pts=[(pu[0], pu[1] + 2.0, pu[2]), (pu[0], pu[1] + 12.0, pu[2] + 3.0), (pu[0] + 0.5, 32.0, 33.0), (69.0, 41.0, 40.0),
                              (55.0, 52.0, 49.0), (pe['usb_a_pico'][0], pe['usb_a_pico'][1] + 7.0, pe['usb_a_pico'][2] + 0.5), pe['usb_a_pico']])
    j2 = pc('j602')
    D['vesc_usb'] = dict(d=4.0, spec="FSESC micro-USB lead (the kit's cable) into the USB jack lead on J602 (Adafruit 4449, D's choice); length is the whole run",
                         ends=('FSESC USB (front end, position ESTIMATE)', 'power board J602 (hub port 3, 1 x 4 header)'),
                         pts=[(e_front + 1.0, ecy - 14.0, ez + 11.0), (e_front + 3.5, ecy - 14.0, ez + 14.0), (-25.0, -50.0, 29.0),
                              (0.0, -51.0, 28.0), (40.0, -52.0, 25.0), (60.0, -52.0, 24.5), (j2[0] - 4.0, j2[1], j2[2] + 3.0),
                              (j2[0], j2[1], j2[2] + 3.0), j2])
    vc = pc('vesc_comm')
    D['vesc_comm'] = dict(d=3.0, spec='FSESC COMM lead, JST-PH 7-pin both ends (UART TX/RX/GND, ADC2 kill)',
                          ends=('FSESC COMM port (front end, position ESTIMATE)', 'power board J903 (rear edge)'),
                          pts=[(e_front + 1.0, ecy - 16.0, ez - 3.0), (e_front + 3.0, ecy - 16.0, ez - 1.0), (vc[0] - 3.7, vc[1] - 3.6, vc[2] - 2.0),
                               (vc[0] - 0.7, vc[1] - 1.1, vc[2] + 3.0), (vc[0], vc[1], vc[2] + 3.0), vc])
    # ---- charging: the PD trigger and the CC/CV in the right pod, wired to their pads in the board's rear middle
    # (six wires, one per module terminal; IN- and OUT- are joined only inside the module, review B1). The IN and OUT
    # pairs are taken to land 2 mm either side of D's pad-group centre
    pdb = kit.PD_BOX; cv = kit.CCCV_BOX
    p1, p2 = pc('chg_pd'), pc('chg_cccv')
    pdx = (pdb[0] + pdb[1]) / 2
    D['charge_pd'] = dict(d=2.5, spec='20 AWG pair, PD trigger VOUT / GND (CHG_GND) to the board pads',
                          ends=('PD trigger (right pod)', 'power board PD-trigger pads'),
                          pts=[(pdx, pdb[3] - 0.6, pdb[5] + 0.6), (pdx - 2.0, pdb[3] + 3.0, pdb[5] + 2.0), (8.0, -62.0, 22.0),
                               (-6.0, -53.0, 22.5), (p1[0], p1[1], p1[2] + 6.0), (p1[0], p1[1], p1[2] + 3.0), p1])
    cz = (cv[4] + cv[5]) / 2
    D['cccv_in'] = dict(d=2.5, spec='20 AWG pair, CC/CV IN+ / IN- (CHG_GND) to the board pads',
                        ends=('CC/CV module, input end (right pod)', 'power board CC/CV pads'),
                        pts=[(cv[1] - 3.0, cv[3] + 0.6, cz), (cv[1] - 4.0, -72.0, cz - 2.0), (p2[0] + 2.5, -60.0, 15.0),
                             (p2[0] + 2.0, p2[1] - 4.0, p2[2] + 3.0), (p2[0] + 2.0, p2[1], p2[2] + 2.0), (p2[0] + 2.0, p2[1], p2[2])])
    D['cccv_out'] = dict(d=2.5, spec='20 AWG pair, CC/CV OUT+ / OUT- (GND) to the board pads',
                         ends=('CC/CV module, output end (right pod)', 'power board CC/CV pads'),
                         pts=[(cv[0] + 3.0, cv[3] + 0.6, cz), (cv[0] + 6.0, -72.0, cz - 2.0), (-34.0, -70.0, 20.0), (-24.0, -66.5, 22.0),
                              (-18.0, -58.0, 20.0), (-11.0, -51.0, 14.0), (p2[0] - 3.4, p2[1] - 2.5, p2[2] + 2.0),
                              (p2[0] - 2.0, p2[1], p2[2] + 2.0), (p2[0] - 2.0, p2[1], p2[2])])
    # ---- motor side: phases and hall from the ESC's motor end straight down through the opening
    # descent columns in the opening, staggered in x and y so no lead crosses another's drop; above the deck the
    # leads are stacked 5 mm apart in z (A lowest, and A comes round behind the opening), the hall lead runs over them
    r_ = 2.1
    cols = [(po[0] + r_ + 0.2, po[2] + r_ + 0.4), (po[0] + 5.5, po[2] + 7.0), (po[1] - r_ - 0.5, po[2] + 11.6)]
    above = [[(po[0] - 0.5, ecy - 12.0, 7.0), (po[0] - 1.0, po[2] + 6.0, 6.0), (po[0] + 1.0, po[2] + 2.0, 4.0)],
             [(cols[1][0] - 1.0, cols[1][1] + 4.0, 10.0)],
             [(cols[2][0] - 1.0, cols[2][1] + 4.0, 15.0)]]
    for i, k in enumerate('ABC'):
        ang = math.radians(90 + 120 * i)
        end = (motor_axis[0] + 9.0 * math.cos(ang), y_bell, motor_axis[1] + 9.0 * math.sin(ang))
        ys = ecy - 10.0 + 10.0 * i
        cx_, cy_ = cols[i]
        D[f'motor_{k}'] = dict(d=4.2, spec=f'FSESC 12 AWG phase {k} lead, 4 mm bullet at the motor',
                               ends=(f'FSESC phase {k} (motor end)', f'motor phase {k}'),
                               pts=[(e_rear - 1.0, ys, ez), (e_rear - 3.0, ys - 2.0, ez - 4.0 + 5.0 * i)] + above[i] +
                                   [(cx_, cy_, 1.0), (cx_, cy_, -8.0), (cx_ - 1.5, cy_ - 10.0, -20.0 - 3.0 * i),
                                    (end[0] + 2.0, y_bell - 3.0, end[2] + 3.0), end])
    hx_, hy_ = po[1] - 2.1, po[2] + 3.0
    D['hall'] = dict(d=3.2, spec="motor's own 6-pin sensor lead into the FSESC's hall port",
                     ends=('FSESC hall port (motor end)', 'motor sensor port'),
                     pts=[(e_rear - 1.0, ecy + 17.0, ez - 3.0), (e_rear - 3.0, ecy + 16.0, ez + 12.0), (hx_, hy_ + 6.0, 21.0),
                          (hx_, hy_, 9.0), (hx_, hy_, 1.0), (hx_, hy_, -8.0), (hx_ - 1.3, hy_ - 8.0, -14.0), (-118.0, -84.0, -16.0),
                          (-124.0, y_bell + 2.0, motor_axis[1] + 17.0)])
    # ---- ESC battery leads: out of the ESC's front end (exits ESTIMATE) and onto the ESC+ / ESC- pads just inside the
    # board's rear edge, soldered from above
    for k, ys, dzl in (('plus', ecy + 4.0, 0.0), ('minus', ecy + 12.0, 3.0)):
        pad = pc('esc_' + k)
        D[f'esc_battery_{k}'] = dict(d=4.2, spec=f"FSESC 12 AWG battery {'+' if k == 'plus' else '-'} lead, soldered to the board pad",
                                     ends=('FSESC battery end', f"power board ESC{'+' if k == 'plus' else '-'} pad (rear edge)"),
                                     pts=[(e_front + 1.0, ys, ez + dzl / 2), (e_front + 3.0, ys + 0.5 * (pad[1] - ys), ez + 3.0 + dzl),
                                          (pad[0] - 4.0, pad[1] - 1.0, 17.0 + dzl), (pad[0] - 0.5, pad[1], 15.0), (pad[0], pad[1], pad[2] + 2.5), pad])
    # ---- servo: the servo's own lead from the front-edge header down through the deck slot (or the board's notch)
    sv = pc('servo')                                             # J406, the plug from above
    srv_end = (126.0, -24.0, kit.Z_RIM + P['SERVO'][4] - 6.0)
    under = [(101.0, -50.0, -8.0), (101.0, -45.0, -19.0), (112.0, -33.0, -23.0), srv_end]
    if kit.servo_notch_local():
        pts = [sv, (sv[0], sv[1], sv[2] + 3.0), (sv[0] + 3.0, sv[1] - 2.0, sv[2] + 3.0), (xf + 5.0, -70.0, 14.0),
               (106.0, -70.0, 12.0), (101.0, -66.0, 9.0), (101.0, -64.0, 3.0), (101.0, -62.0, -3.0)] + under
    else:
        pts = [sv, (sv[0], sv[1], sv[2] + 3.0), (sv[0] + 3.0, sv[1] - 0.5, sv[2] + 4.0), (100.0, -52.5, 20.0),
               (101.0, -54.0, 9.0), (101.0, -55.0, 1.0), (101.0, -54.0, -3.0)] + under
    pts = pts[::-1]
    D['servo'] = dict(d=3.2, spec="servo's own 3-wire lead", ends=('steering servo', 'power board servo header J406 (front edge)'), pts=pts)
    # ---- battery assembly: pack + through the MIDI fuse, pack - through the BMS, both to the pack's XT90-S; that mates
    # with the XT90 male on the board's 10 AWG pigtail (HANDOFF_E), the pair lying on the lid (kit.XT90_BOX). Pins: +
    # on the north side (y + 4), - on the south side (estimate; check the polarity marks on the housings)
    fx0, fx1, fy0, fy1 = kit.MIDI_FUSE_XY; fz = kit.Z_LID_TOP + kit.MIDI_FUSE_H
    stud_in, stud_out = (fx1 - 6.0, (fy0 + fy1) / 2, fz + 1.0), (fx0 + 6.0, (fy0 + fy1) / 2, fz + 1.0)
    xb = kit.XT90_BOX; xcy = (xb[2] + xb[3]) / 2; xz = (xb[4] + xb[5]) / 2
    xpack_p, xpack_m = (xb[0] - 1.0, xcy + 4.0, xz), (xb[0] - 1.0, xcy - 4.0, xz)      # XT90-S (pack side), -x end
    xbrd_p, xbrd_m = (xb[1] + 1.0, xcy + 4.0, xz), (xb[1] + 1.0, xcy - 4.0, xz)        # XT90 male (board pigtail), +x end
    bp_, bm_ = pc('bat_plus'), pc('bat_minus')
    D['pack_pigtail_plus'] = dict(d=5.8, spec='10 AWG silicone pigtail, board BAT+ pad to the XT90 male (+)',
                                  ends=('power board BAT+ pad (pack edge)', 'XT90 male, + (mates with the pack XT90-S)'),
                                  pts=[bp_, (bp_[0], bp_[1], bp_[2] + 5.0), (bp_[0] + 2.5, 18.0, 24.0), (-4.0, 32.0, 26.0), (-3.0, xcy + 1.0, 19.0),
                                       (xbrd_p[0] + 6.0, xbrd_p[1], xz + 1.0), xbrd_p])
    D['pack_pigtail_minus'] = dict(d=5.8, spec='10 AWG silicone pigtail, board BAT- pad to the XT90 male (-)',
                                   ends=('power board BAT- pad (pack edge)', 'XT90 male, - (mates with the pack XT90-S)'),
                                   pts=[bm_, (bm_[0], bm_[1], bm_[2] + 5.0), (bm_[0] + 6.0, 12.0, 20.0), (-16.0, 26.0, 18.0), (-9.0, xcy - 5.0, 15.0),
                                        (xbrd_m[0] + 4.0, xbrd_m[1], xz + 0.5), xbrd_m])
    D['pack_plus'] = dict(d=5.8, spec='10 AWG silicone, pack + (G4 end strip) to the MIDI fuse holder input',
                          ends=('pack + strip (under the lid)', 'MIDI 125 A fuse, input stud'),
                          pts=[(48.2, 21.0, 3.0), (48.2, 20.5, 12.0), (54.0, 21.0, 30.0), (stud_in[0], 24.0, fz + 8.0),
                               (stud_in[0], stud_in[1], fz + 6.0), stud_in])
    D['fuse_to_xt90'] = dict(d=5.8, spec='10 AWG silicone, fuse output stud to the pack XT90-S (B+)',
                             ends=('MIDI fuse, output stud', 'pack XT90-S, + (mates with the board pigtail)'),
                             pts=[stud_out, (stud_out[0], stud_out[1], fz + 7.0), (2.0, 48.0, 34.0), (-12.0, 51.0, 29.0), (-40.0, 50.5, 25.5),
                                  (-64.5, 49.5, 21.0), (xpack_p[0] - 6.0, xpack_p[1] + 0.5, xz + 2.0), xpack_p])
    bt = (bx0 - 1.0, bms_y, bz0 + 22.0)                         # BMS B- / P- terminals at its rear end (ESTIMATE)
    D['pack_minus'] = dict(d=5.8, spec='10 AWG silicone, pack - (G1 end strip) to the BMS B-',
                           ends=('pack - strip (under the lid)', 'JBD BMS B-'),
                           pts=[(-48.0, 21.0, 3.0), (-48.0, 20.0, 12.0), (-56.0, 28.0, 30.0), (-74.0, 46.0, bt[2]), (bx0 - 8.0, bms_y - 2.0, bt[2]),
                                (bx0 - 4.0, bms_y, bt[2]), bt])
    bp = (bx0 - 1.0, bms_y, bz0 + 40.0)
    D['bms_p_minus'] = dict(d=5.8, spec='10 AWG silicone, BMS P- to the pack XT90-S (system ground)',
                            ends=('JBD BMS P-', 'pack XT90-S, - (mates with the board pigtail)'),
                            pts=[bp, (bx0 - 5.0, bms_y, bp[2]), (bx0 - 9.0, bms_y - 6.0, bp[2] - 3.0), (bx0 - 8.0, 50.0, 34.0),
                                 (bx0 + 0.0, xpack_m[1] + 3.0, 20.0), (xpack_m[0] - 6.0, xpack_m[1], xz + 1.0), xpack_m])
    bb = (bx0 - 1.0, bms_y, bz0 + 62.0)
    D['pack_sense'] = dict(d=4.5, spec="pack's 7-wire sense lead (JST-XH 7-pin) and the adapter harness to the BMS balance and NTC inputs",
                           ends=('pack taps B0-B4 and NTC', 'JBD BMS balance connector'),
                           pts=[(0.0, 21.0, 3.0), (1.5, 21.0, 10.0), (2.5, 26.0, 36.0), (6.0, 40.0, 47.0), (-2.0, 46.0, 53.0), (-20.0, 50.0, 58.0), (-60.0, 54.0, 64.0),
                                (bx0 - 8.0, bms_y - 2.0, bb[2]), (bx0 - 4.0, bms_y, bb[2]), bb])
    bu = pc('bms_uart')
    bm = (bx0 - 1.0, bms_y, bz0 + 80.0)
    D['bms_uart'] = dict(d=3.0, spec='JBD 4-pin UART lead to the board J201 JST-XH 4-pin (opto-isolated on the board)',
                         ends=('JBD BMS UART port', 'power board J201 BMS UART (pack edge)'),
                         pts=[bm, (bx0 - 6.0, bms_y - 1.0, bm[2]), (bx0 - 8.0, bms_y - 8.0, bm[2] - 10.0), (-62.0, 50.0, 46.0),
                              (-40.0, 36.0, 38.0), (-15.0, 30.0, 34.5), (20.0, 30.0, 35.0), (38.0, 28.0, 36.0), (43.0, 21.0, 34.0),
                              (45.5, 16.5, 26.5), (bu[0] - 3.8, bu[1] + 0.5, bu[2] + 3.9), (bu[0], bu[1], bu[2] + 3.0), bu])
    # ---- side-pod fan: out of the fan window, forward in the gap between the pod and the board, onto the fan header
    # J1003 on the board's rear edge (HANDOFF_E moved it there)
    f0 = kit.FAN_X[0]; fh = pc('fan')
    D['side_fan'] = dict(d=2.2, spec="the fan's own 4-pin lead (fan to the power board)",
                         ends=('40 mm fan (right pod)', 'power board fan header J1003 (rear edge)'),
                         pts=[(f0 + 2.0, -79.0, 5.0), (f0 + 2.0, -77.3, 10.0), (f0 + 6.0, -73.0, 8.0), (-60.0, -72.5, 8.0),
                              (-42.0, -72.0, 9.0), (-36.0, -68.0, 13.0), (-33.0, -61.0, 19.0),
                              (fh[0], fh[1] - 2.0, fh[2] + 3.0), fh])
    # ---- Wi-Fi: from the M.2 card under the carrier out under the I/O edge (behind the unused DisplayPort, the one
    # gap in the plugs) and up and back to the canopy jacks. The rear and front edges are no way out: the power
    # board's 35 mm strips reach up to the carrier's underside there.
    wifi = (dk(36.0, 0)[0], dk(0, 36.0)[1], Z_DEVKIT_BOT - 3.0)    # card's MHF4 jacks (J10 position: ESTIMATE)
    yo = P['DEVKIT'][3]
    for i, (ax, ay) in enumerate(ANTENNAS):
        s0 = 1.5 if i == 0 else -1.5
        pts = [(wifi[0], wifi[1] + 4.0 * s0, wifi[2]), (14.0 + s0, -5.0, wifi[2] - 0.5), (10.0 + s0, yo - 4.0, wifi[2] - 0.5),
               (10.0 + s0, yo + 4.5, wifi[2] + 4.0), (6.0 + s0, yo + 3.0, 62.0)]
        if i == 0:
            pts += [(-15.0, ay + 8.0, 74.0), (ax, ay, Z_CANOPY - 8.0)]
        else:
            pts += [(-8.0, yo - 8.0, 66.0), (-8.0, -30.0, 68.0), (-14.0, ay + 2.0, 72.0), (ax, ay, Z_CANOPY - 8.0)]
        D[f'wifi_{i + 1}'] = dict(d=1.8, spec='MHF4 to RP-SMA bulkhead pigtail, 1.13 mm coax (order 20 cm)',
                                  ends=('M.2 Wi-Fi card (under the carrier)', f'antenna jack {i + 1}, canopy rear edge'), pts=pts)
    for k, c in D.items():
        c['path'] = catmull(c['pts'])
        c['length_mm'] = round(path_len(c['path']), 1)
    return D


def cable_solids(c, skip_ends=6.0):
    """the cable as a chain of short cylinders (for the clearance checks); the first and last `skip_ends` mm
    are left out, where it enters its connector"""
    path = c['path']
    segs = []
    run = 0.0
    total = c['length_mm']
    for a, b in zip(path, path[1:]):
        L = math.dist(a, b)
        s0, s1 = run, run + L
        run = s1
        if s1 < skip_ends or s0 > total - skip_ends or L < 0.05:
            continue
        v = tuple((b[i] - a[i]) / L for i in range(3))
        segs.append(cq.Workplane('XY').add(cq.Solid.makeCylinder(c['d'] / 2, L, cq.Vector(*a), cq.Vector(*v))))
    return segs


# ----------------------------------------------------------------------------- bench stand
STAND_H = 125.0     # bench to the chassis floor: floor is ~72 mm up at ride height (kit Z_FLOOR vs the tyre bottom);
                    # +53 mm leaves the tyres ~13 mm clear even with 40 mm of suspension droop (droop is an estimate)


def bench_stand():
    """Printed stand: a hollow truncated pyramid, 170 x 120 at the bench, 150 x 80 under the chassis floor,
    with a 1.5 mm pocket for a foam pad on top and slotted sides. Prints top down (the pad face on the bed)."""
    t = 3.0
    base = cq.Workplane('XY').rect(170, 120).workplane(offset=STAND_H).rect(150, 80).loft()
    inner = cq.Workplane('XY').workplane(offset=-1).rect(170 - 2 * t - 1.2, 120 - 2 * t - 1.2) \
        .workplane(offset=STAND_H - 5 + 1).rect(150 - 2 * t, 80 - 2 * t).loft()
    s = base.cut(inner)
    s = s.cut(box(-66, 66, -31, 31, STAND_H - 1.5, STAND_H + 1))                  # foam pad pocket
    # slotted windows, rounded ends (printable with the stand upside down)
    for x in (-50, -17, 17, 50):
        s = s.cut(cq.Workplane('XZ').center(x, STAND_H / 2 - 4).slot2D(76, 20, 90).extrude(200, both=True))
    for y in (-18, 18):
        s = s.cut(cq.Workplane('YZ').center(y, STAND_H / 2 - 4).slot2D(76, 22, 90).extrude(200, both=True))
    s = s.cut(box(-12, 12, -70, 70, 8, 20))                                      # finger slots to lift it
    return s.translate((0, 0, kit.Z_FLOOR - STAND_H))


# ----------------------------------------------------------------------------- build + checks
def build(kit_build=None):
    S, comps, parts, extras, info = kit_build or kit.build()
    canopy, n_hex = stack_canopy()
    canopy_sheets = sheet_canopy()
    ant_under, ant_over = antennas()
    lid_plug, _ = rj45_plug_down(*LID_JACK)
    chg, _ = usbc_through_pod('charge_usbc', kit.PD_BOX[2])               # into the PD trigger, face at the outer wall
    lap, _ = usbc_through_pod('debug_usbc', pw(*POWER_CONN['hub_usbc'][:2])[1])   # the laptop's plug, into the hub
    j6, _ = j601_plug()
    new_parts = dict(stack_canopy=canopy) if not SHEET_CANOPY else {k: sh.solid() for k, sh in canopy_sheets.items()}
    new_comps = dict(antenna_jacks=ant_under, antennas=ant_over, rj45_plug_lidar=lid_plug,
                     usbc_plug_charge=chg, usbc_plug_laptop=lap, j601_plug=j6)
    cables = cable_defs()
    stand = bench_stand()
    info['canopy_sheets'] = canopy_sheets
    return (S, comps, parts, extras, info), new_parts, new_comps, cables, stand, n_hex


# expected contacts: a part and the thing it is fastened to or plugged into
TOUCH = {frozenset(p) for p in (
    ('antenna_jacks', 'stack_canopy'), ('antennas', 'stack_canopy'), ('antenna_jacks', 'antennas'),
    ('antenna_jacks', 'laser_canopy_top'), ('antennas', 'laser_canopy_top'), ('rj45_plug_lidar', 'usb_eth_adapter'),
    ('usbc_plug_charge', 'pd_trigger'))}
_BOARD = {'power_parts_low', 'power_parts_tall'}
_PACK = {'pack_lid', 'pack_box', 'cells_4s3p', 'cell_holder_top'}
# what each cable may touch: its connectors, and where it ends on the power board, the board's height-map blocks
# (those blocks are envelopes for parts the leads are routed between on the real board)
CABLE_OK = {
    'camera': {'devkit_plugs', 'camera_plug'},
    'camera_power': {'camera_m8_plug', 'camera_regulator'},
    'camera_reg_in': {'camera_regulator'} | _BOARD,
    'lidar_ethernet': {'rj45_plug_lidar', 'lidar_connectors'},
    'lidar_usb': {'usb_eth_adapter', 'devkit_plugs'},
    'lidar_power': {'lidar_connectors'} | _BOARD,
    'devkit_dc': {'devkit_plugs'} | _BOARD,
    'ribbon_40pin_a': {'devkit_header_plugs'} | _BOARD, 'ribbon_40pin_b': {'devkit_header_plugs'} | _BOARD,
    'ribbon_40pin_c': {'devkit_header_plugs'} | _BOARD,
    'j14': {'devkit_header_plugs'} | _BOARD,
    'devkit_usb': {'devkit_plugs', 'j601_plug'},
    'pico_usb': {'devkit_plugs'} | _BOARD,
    'vesc_usb': {'esc_case'} | _BOARD,
    'vesc_comm': {'esc_case'} | _BOARD,
    'charge_pd': {'pd_trigger'} | _BOARD, 'cccv_in': {'cccv_module'} | _BOARD, 'cccv_out': {'cccv_module'} | _BOARD,
    'motor_A': {'esc_case', 'motor'}, 'motor_B': {'esc_case', 'motor'}, 'motor_C': {'esc_case', 'motor'},
    'hall': {'esc_case', 'motor'},
    'esc_battery_plus': {'esc_case'} | _BOARD, 'esc_battery_minus': {'esc_case'} | _BOARD,
    'servo': {'steering_servo'} | _BOARD,
    'pack_plus': _PACK | {'midi_fuse'},
    'fuse_to_xt90': {'midi_fuse', 'xt90_pair'},
    'pack_pigtail_plus': {'xt90_pair'} | _BOARD, 'pack_pigtail_minus': {'xt90_pair'} | _BOARD,
    'pack_minus': _PACK | {'bms'},
    'bms_p_minus': {'bms', 'xt90_pair'},
    'pack_sense': _PACK | {'bms'},
    'bms_uart': {'bms'} | _BOARD,
    'side_fan': {'fan_40mm'} | _BOARD,
    'wifi_1': {'devkit_bottom_parts', 'antenna_jacks'},
    'wifi_2': {'devkit_bottom_parts', 'antenna_jacks'},
}


def checks(kb, new_parts, new_comps, cables):
    S, comps, parts, extras, info = kb
    rows = []
    old = list(parts.items()) + list(comps.items()) + list(S.items())
    new = list(new_parts.items()) + list(new_comps.items())
    for (na, a), (nb, b) in itertools.combinations(new, 2):
        if frozenset((na, nb)) in TOUCH:
            continue
        v = inter(a, b)
        if v > 0.5:
            rows.append((na, nb, round(v, 1)))
    for na, a in new:
        for nb, b in old:
            if frozenset((na, nb)) in TOUCH:
                continue
            v = inter(a, b)
            if v > 0.5:
                rows.append((na, nb, round(v, 1)))
    cable_hits = []
    everything = old + new
    for cn, c in cables.items():
        segs = cable_solids(c)
        hits = {}
        for s in segs:
            for nb, b in everything:
                if nb in CABLE_OK.get(cn, ()):
                    continue
                if not bb_overlap(s, b):
                    continue
                v = inter(s, b)
                if v > 0.2:
                    hits[nb] = round(hits.get(nb, 0) + v, 1)
        for nb, v in hits.items():
            cable_hits.append((cn, nb, v))
    # cables against each other (a crossing that is closer than the two radii)
    cable_cross = []
    names = list(cables)
    for a, b in itertools.combinations(names, 2):
        if a.startswith('ribbon') and b.startswith('ribbon'):
            continue
        pa, pb = cables[a]['path'], cables[b]['path']
        r = (cables[a]['d'] + cables[b]['d']) / 2
        dmin = min(math.dist(p, q) for p in pa[2:-2] for q in pb[2:-2]) if len(pa) > 4 and len(pb) > 4 else 99.0
        if dmin < r - 0.5:
            cable_cross.append((a, b, round(dmin, 1), round(r, 1)))
    # lidar scan plane: the new parts and cables within +-6 mm of it must sit in the rear blind sector
    zc = info['scan_z']
    lx = P['LIDAR_FRONT_X'] - 30.5
    slab = box(-400, 400, -300, 300, zc - 6, zc + 6)
    fov = []
    items = new + [(f'cable:{k}', union(*cable_solids(c, 0.0))) for k, c in cables.items() if cable_solids(c, 0.0)]
    for name, s in items:
        try:
            if not bb_overlap(s, slab):
                continue
            sec = s.intersect(slab)
            if volume(sec) < 0.1:
                continue
            bbx = sec.val().BoundingBox()
        except Exception:
            continue
        bearings = [abs(math.degrees(math.atan2(y, x - lx))) for x in (bbx.xmin, bbx.xmax) for y in (bbx.ymin, bbx.ymax)]
        fov.append((name, round(min(bearings), 1), 'inside blind sector' if min(bearings) >= 135 else 'IN VIEW'))
    # clearances worth reporting
    io = kit.devkit_io_boxes(); pl = kit.devkit_plug_boxes(io)
    plug_top = max(v['box'].val().BoundingBox().zmax for v in pl.values())
    idc_top = comps['devkit_header_plugs'].val().BoundingBox().zmax
    def in_window(comp, wname):
        bb_ = new_comps[comp].val().BoundingBox()
        _, xc, w, z0, z1, _ = kit.pod_window(wname)
        return [round(min(bb_.xmin - (xc - w / 2), (xc + w / 2) - bb_.xmax), 2), round(min(bb_.zmin - z0, z1 - bb_.zmax), 2)]
    cxy = SHEET_CANOPY_XY if SHEET_CANOPY else CANOPY_XY
    cl = dict(canopy=('laser box' if SHEET_CANOPY else 'printed'), canopy_over_jetson_fan_mm=round(Z_CANOPY - Z_SINK_TOP, 2),
              canopy_over_devkit_plugs_mm=round(Z_CANOPY - (0.0 if SHEET_CANOPY else CANOPY_LIP) - plug_top, 2),
              canopy_over_j12_idc_mm=round(Z_CANOPY - idc_top, 2),
              canopy_to_bms_mm=round(kit.bms_place()[2] - cxy[3], 2),
              plug_in_window_side_and_z_gap_mm=dict(charge_usbc=in_window('usbc_plug_charge', 'charge_usbc'),
                                                    laptop_usbc=in_window('usbc_plug_laptop', 'debug_usbc'),
                                                    j601_head=in_window('j601_plug', 'devkit_usba')),
              cccv_module_in_window_side_and_z_gap_mm=[round(min(kit.CCCV_BOX[0] - (kit.pod_window('cccv')[1] - kit.pod_window('cccv')[2] / 2),
                                                                 (kit.pod_window('cccv')[1] + kit.pod_window('cccv')[2] / 2) - kit.CCCV_BOX[1]), 2),
                                                       round(min(kit.CCCV_BOX[4] - kit.pod_window('cccv')[3], kit.pod_window('cccv')[4] - kit.CCCV_BOX[5]), 2)],
              cccv_module_depth_past_pod_inside_mm=round(P['CCCV'][2] - (kit.POD['y_out'] - kit.POD['y_in'] - 2 * kit.POD['t']), 2),
              pd_trigger_past_inner_wall_into_gap_mm=round(kit.PD_BOX[3] - (-kit.POD['y_in']), 2),
              j601_head_past_board_edge_mm=round(P['J601_PLUG'][1] - 0.5, 2))
    return rows, cable_hits, cable_cross, fov, cl


def export(new_parts, new_comps, stand):
    res = {}
    orient = dict(stack_canopy=((1, 0, 0), 180), bench_stand=((1, 0, 0), 180))
    for name, p in list(new_parts.items()) + [('bench_stand', stand)]:
        if name.startswith('laser_'):
            cq.exporters.export(p, os.path.join(OUT, 'step', f'{name}.step'))
            continue
        ax, ang = orient.get(name, (None, 0))
        q = p.rotate((0, 0, 0), ax, ang) if ax else p
        bb = q.val().BoundingBox()
        q = q.translate((-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))
        cq.exporters.export(p, os.path.join(OUT, 'step', f'{name}.step'))
        cq.exporters.export(q, os.path.join(OUT, 'stl', f'{name}.stl'), tolerance=0.05, angularTolerance=0.15)
        bb = q.val().BoundingBox()
        v = volume(p) / 1000.0
        res[name] = dict(bed_xyz=[round(bb.xlen, 1), round(bb.ylen, 1), round(bb.zlen, 1)], volume_cm3=round(v, 1),
                         mass_g_solid_petgcf=round(v * 1.30, 0), fits_250_bed=bool(max(bb.xlen, bb.ylen) <= 250 and bb.zlen <= 250),
                         solids=n_solids(p))
    for name, p in new_comps.items():
        cq.exporters.export(p, os.path.join(OUT, 'step', f'bought_{name}.step'))
    return res


def renders(kb, new_parts, new_comps, stand):
    from render import render
    S, comps, parts, _, _ = kb
    grey = (0.22, 0.22, 0.25); blue = (0.25, 0.5, 0.95); light = (0.75, 0.75, 0.78)
    keys = ('power_pcb', 'power_parts_low', 'power_parts_tall', 'tray_standoffs_25mm', 'power_standoffs_7mm', 'devkit_pcb',
            'devkit_bottom_parts', 'jetson_module_and_sink', 'devkit_io', 'devkit_plugs', 'devkit_headers', 'devkit_header_plugs')
    items = [(v, grey) for k, v in parts.items() if k in ('devkit_tray', 'laser_devkit_tray', 'devkit_spacers', 'canopy_leg', 'pack_lid',
                                                           'bms_fence', 'laser_bms_base', 'laser_bms_wall_in', 'laser_bms_wall_out', 'laser_fet_shield')]
    items += [(comps[k], blue) for k in keys + ('bms', 'fet_bar') + (('canopy_standoffs',) if 'canopy_standoffs' in comps else ())]
    items += [(v, light) for k, v in new_parts.items() if 'canopy' in k] + [(new_comps['antenna_jacks'], grey), (new_comps['antennas'], grey)]
    render(items, os.path.join(OUT, 'renders', 'stack_canopy.png'), views=[(28, -58), (28, 122)],
           title='rev B canopy over the dev kit and its plugs, on the tray pillars and the zone B leg; BMS on edge behind')
    render([(stand, grey)], os.path.join(OUT, 'renders', 'bench_stand.png'), views=[(22, -60)], title='bench stand (PLA)')


def wiring_table(cables):
    rows = []
    for k, c in cables.items():
        if not c.get('table', True):
            continue
        L = c['length_mm']
        rows.append(dict(cable=k.replace('_b', '') if k.startswith('ribbon') else k, spec=c['spec'], from_=c['ends'][0], to=c['ends'][1],
                         d_mm=c['d'], routed_mm=round(L), cut_mm=int(math.ceil((L * 1.1 + 20) / 10.0) * 10)))
    return rows


if __name__ == '__main__':
    kb, new_parts, new_comps, cables, stand, n_hex = build()
    rows, cable_hits, cable_cross, fov, cl = checks(kb, new_parts, new_comps, cables)
    res = export(new_parts, new_comps, stand)
    laser = kit.export_laser(kb[4]['canopy_sheets'])
    renders(kb, new_parts, new_comps, stand)
    wt = wiring_table(cables)
    rep = dict(z=dict(power_top=Z_POWER_TOP, tray_top=Z_TRAY_TOP, devkit_bottom=Z_DEVKIT_BOT, devkit_top=Z_DEVKIT_TOP,
                      sink_top=Z_SINK_TOP, canopy_underside=Z_CANOPY),
               power_L=P['POWER_L'], canopy_xy=CANOPY_XY, canopy_posts=CANOPY_POSTS, antennas=ANTENNAS, fan_centre=FAN_C,
               grille_holes=n_hex, power_conn_local=POWER_CONN, clearances=cl,
               sheet_parts_in_checks=sorted(kit.SHEET), laser=laser,
               interference=rows, cable_interference=cable_hits, cable_crossings=cable_cross, lidar_plane=fov, parts=res, wiring=wt,
               cables={k: dict(d=c['d'], pts=[[round(v, 2) for v in p] for p in c['path']]) for k, c in cables.items()})
    with open(os.path.join(OUT, 'extras_report.json'), 'w') as f:
        json.dump(rep, f, indent=1, default=str)
    print(json.dumps({k: rep[k] for k in ('clearances', 'interference', 'cable_interference', 'cable_crossings', 'lidar_plane')}, indent=1))
    for k, v in res.items():
        print(f'{k:16s} bed {v["bed_xyz"]}  {v["volume_cm3"]:6.1f} cm3  ~{v["mass_g_solid_petgcf"]:.0f} g solid  fits250={v["fits_250_bed"]} solids={v["solids"]}')
    for r in wt:
        print(f"{r['cable']:18s} {r['routed_mm']:5d} mm routed, cut {r['cut_mm']} mm  {r['spec']}")
