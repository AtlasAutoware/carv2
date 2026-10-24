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
                    power, dev-kit DC lead, 40-pin ribbon, J14 harness, USB leads to the hub and to the dev kit,
                    motor phases, hall sensor, servo, ESC battery leads, pack leads through the fuse and the BMS,
                    balance lead, BMS UART, side-pod fan, Wi-Fi pigtails.
  bought parts      the lidar RJ45 plug on its dongle, the USB-C plugs through the right pod, the antenna bulkheads
                    and antennas, as envelopes for the checks.

Same frame and parameters as kit.py: +x forward, +y car left, +z up, origin at the deck centre, deck top at z 0.
Chassis numbers are kit.py's estimates (docs/MEASURE_FIRST.md). The power-board connector positions in POWER_CONN
are placeholders until agent D's layout reports the real ones.
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
from kit import P, box, cylz, cyl, union, volume, n_solids, inter, bb_overlap, M3_CLEAR, pw, dk  # noqa: E402

OUT = kit.OUT

# ----------------------------------------------------------------------------- the rev B stack, from kit.py
Z_POWER_TOP = kit.Z_POWER_TOP                   # 8.6
Z_TRAY_TOP = kit.Z_TRAY1                        # 36.6
Z_DEVKIT_BOT = kit.Z_DEVKIT0                    # 43.6
Z_DEVKIT_TOP = kit.Z_DEVKIT1                    # 45.17
Z_SINK_TOP = kit.Z_SINK_TOP                     # 77.17, top of the dev kit's heatsink and fan
Z_CANOPY = kit.Z_CANOPY                         # 85.17, canopy underside: CANOPY_GAP over the fan

# ----------------------------------------------------------------------------- canopy
CANOPY_T = 2.4
CANOPY_LIP = 4.0                # stiffening lip hanging down around the edge
CANOPY_POSTS = kit.tray_pillars() + [kit.CANOPY_LEG_XY]
_px = [p[0] for p in kit.tray_pillars()]
CANOPY_XY = (min(_px) - 8.0, max(_px) + 8.0, kit.POWER[2] - 4.0, 57.0)   # y1: 1.3 mm inboard of the BMS holder
CANOPY_R = 12.0
_j = P['JETSON_XY']
JETSON_BOX = (dk(_j[0], 0)[0], dk(_j[1], 0)[0], dk(0, _j[2])[1], dk(0, _j[3])[1])
FAN_C = ((JETSON_BOX[0] + JETSON_BOX[1]) / 2, (JETSON_BOX[2] + JETSON_BOX[3]) / 2)
GRILLE_R = 25.0                 # hex grille over the dev-kit fan (about 40 mm)
# RP-SMA bulkheads: 1/4-36 UNS thread, 6.5 mm hole with a 5.8 mm flat so the jack cannot turn; on the rear edge
ANTENNAS = [(CANOPY_XY[0] + 7.0, -4.0), (CANOPY_XY[0] + 7.0, -50.0)]
RPSMA_HOLE, RPSMA_FLAT = 6.5, 5.8
ANTENNA_L = 120.0               # Bingfu 3 dBi dual-band swivel dipole (Amazon B082SHKT3Q), 12 cm


def canopy_outline():
    x0, x1, y0, y1 = CANOPY_XY
    return box(x0, x1, y0, y1, 0, 1).edges('|Z').fillet(CANOPY_R)


def stack_canopy():
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


def usbc_through_pod(name):
    """a USB-C plug pushed through the right pod's window to the board edge: shell 8.4 x 2.6 into the receptacle,
    overmold 12.5 x 7 x 22 mm and 15 mm of strain relief, centred on the window"""
    for (n, xc, w, z0, z1) in P['POD_WINDOWS']:
        if n == name:
            zc = (z0 + z1) / 2
            y_edge = kit.POWER[2]
            return box(xc - 6.25, xc + 6.25, kit.POD['y_out'] * -1 - 15.0, y_edge - 4.0, zc - 3.5, zc + 3.5), (xc, zc, w, z0, z1)
    return None, None


# ----------------------------------------------------------------------------- power-board connectors
# board-local (X, Y, height of the cable entry above the PCB top). PLACEHOLDERS until agent D's layout: PHASE2 fixes
# only which edge each one faces.
L_ = P['POWER_L']
POWER_CONN = dict(
    esc_out=(0.0, P['ESC_OUT_Y'], 4.5),      # rear edge, XT60PW; kit.esc_out_plug
    vesc_comm=(0.0, 14.0, 6.0),             # rear edge, JST-PH 7-pin for the FSESC COMM lead (UART + ADC2 kill)
    xt90=(8.0, 84.0, 8.5),                  # pack edge, XT90 board-mount; kit.xt90s_pack
    bms_uart=(22.0, 84.0, 3.0),             # pack edge, JST-XH 4-pin (isolated)
    dc_out=(28.0, 84.0, 1.5),               # pack edge, dev-kit DC lead pads
    pico_usb=(102.0, 84.0, 11.0),           # the Pico's micro-USB at the pack edge (Pico in sockets)
    hub=(70.0, 40.0, 10.0),                 # USB 2.0 hub module, its downstream sockets
    j12_box=(40.0, 8.5, 18.0),              # 2 x 20 shrouded box header + IDC plug top
    j14_hdr=(92.0, 13.5, 14.0),             # 1 x 12 header + Dupont housing top
    servo=(L_, 14.0, 6.0), fan=(L_, 24.0, 5.0), camera_pwr=(L_, 34.0, 6.0), lidar_pwr=(L_, 58.0, 6.0),
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
                            (105.0, 20.0, 70.0), (110.0, 16.0, 80.0), (111.0, 11.0, 100.0), (112.0, 8.0, 116.0), cam_start])
    D['camera_power'] = dict(d=4.5, spec='LUCID GPIO-M8-5M-RA2-A cut to length: red (VAUX) and black (GND) to the board, other six tied back',
                             ends=('camera M8 GPIO (right angle, up)', 'power board camera 2-pin (front edge)'),
                             pts=[m8_top, (m8_top[0] - 2, -8.0, m8_top[2] + 7.0), (138.0, -13.0, m8_top[2] + 8.0),
                                  (122.0, -22.0, 130.0), (112.0, -30.0, 104.0), (108.0, -33.0, 70.0),
                                  (max(xf + 8.0, 106.0), -34.0, 32.0), (xf + 6.0, -34.0, zt + 9.0), pc('camera_pwr')])
    # ---- lidar: Ethernet through the USB dongle on the arch, power from the board's front edge
    D['lidar_ethernet'] = dict(d=6.0, spec='donor SICK M12 D-coded 4-pin to RJ45 (TiM561 Ethernet), into the USB dongle',
                               ends=('USB-Ethernet dongle RJ45 (on the arch leg)', 'lidar Ethernet M12'),
                               pts=[lid_boot, (lid_boot[0] - 2.0, lid_boot[1] - 1.0, lid_boot[2] - 3.0), (lid_boot[0] - 8.0, lid_boot[1] - 4.0, 5.5),
                                    (114.0, 17.0, 8.0), (105.0, 12.5, 13.0), (109.0, 10.3, 15.0), lid_eth])
    D['lidar_usb'] = dict(d=4.0, spec="the dongle's own USB 3 lead (180 mm on the ZimaSpace RTL8153 adapter)",
                          ends=('USB-Ethernet dongle', 'dev kit USB-A (port 1)'),
                          pts=[(LID_JACK[0], LID_JACK[1], _ue[5] + 1.0), (LID_JACK[0], LID_JACK[1], _ue[5] + 4.0), (125.0, 30.0, 93.0),
                               (117.0, 40.0, 88.0), (106.0, 41.0, 77.0), (90.0, 40.0, 70.0), (60.0, 50.0, 60.0), (40.0, 54.0, 54.0),
                               (pe['usb_a_lidar'][0], pe['usb_a_lidar'][1] + 7.0, pe['usb_a_lidar'][2] + 1.0), pe['usb_a_lidar']])
    lp = pc('lidar_pwr')
    lpts = [(lp[0] + 2.0, lid_pwr[1], lp[2]), (lp[0] + 8.0, lid_pwr[1], lp[2] + 0.2), (lid_pwr[0] - 4.0, lid_pwr[1], lid_pwr[2]), lid_pwr]
    if lid_pwr[0] - lp[0] < 16.0:                                # board front close to (or past) the plug end: straight in
        lpts = [(lp[0] + 2.0, lid_pwr[1], lp[2]), lid_pwr]
    D['lidar_power'] = dict(d=5.5, spec='donor SICK M12 power cable, cut and stripped into the terminal',
                            ends=('power board lidar Phoenix 2-pin (front edge)', 'lidar power M12'), pts=lpts)
    # ---- the dev kit's own leads
    D['devkit_dc'] = dict(d=4.5, spec='Tensility 10-01779 5.5 x 2.5 mm right-angle plug, 18 AWG pair, cut to length',
                          ends=('power board DC pads (pack edge)', 'dev kit DC jack'),
                          pts=[pc('dc_out'), (pc('dc_out')[0], 22.0, 14.0), (pc('dc_out')[0] - 1.0, 28.0, 30.0),
                               (pe['dc_plug'][0], pe['dc_plug'][1], pe['dc_plug'][2] - 8.0), pe['dc_plug']])
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
    D['j14'] = dict(d=4.0, spec='1 x 12 Dupont housing, 8 crimped wires (keyed with a printed clip)',
                    ends=('dev kit J14 (button header)', 'power board 1 x 12 header'),
                    pts=[(hx0 + 2.0, hy, hz), (hx0 + 2.0, hy - 1.5, hz - 3.0), (hx0 + 3.0, -73.5, 32.0), (hx0 + 4.0, -73.0, 26.0),
                         (hx0 + 6.0, -66.0, 26.0), (jh[0], jh[1] - 4.0, jh[2] + 3.0), jh])
    hub = pc('hub')
    D['devkit_usbc'] = dict(d=4.5, spec='USB-C to USB-C (or to the hub module socket) 0.25 m, USB 2.0',
                            ends=('dev kit USB-C (device mode, 192.168.55.1)', 'power board USB hub'),
                            pts=[pe['usb_c_hub'], (pe['usb_c_hub'][0] + 3.0, pe['usb_c_hub'][1] + 3.0, pe['usb_c_hub'][2] - 6.0),
                                 (86.0, 28.0, 30.0), (84.0, 17.0, 26.0), (70.0, 5.0, 25.0), (hub[0] + 6.0, hub[1] + 10.0, hub[2] + 4.0), hub])
    pu = pc('pico_usb')
    D['pico_usb'] = dict(d=4.0, spec='micro-USB to USB-A, 0.3 m (supervisor USB CDC to the Jetson)',
                         ends=('Pico micro-USB (power board)', 'dev kit USB-A (port 2)'),
                         pts=[(pu[0], pu[1] + 2.0, pu[2]), (pu[0] + 1.0, pu[1] + 10.0, pu[2] + 8.0), (69.0, 40.0, 40.0),
                              (52.0, 54.0, 49.0), (pe['usb_a_pico'][0], pe['usb_a_pico'][1] + 7.0, pe['usb_a_pico'][2] + 0.5), pe['usb_a_pico']])
    D['vesc_usb'] = dict(d=4.0, spec="FSESC micro-USB to the hub (the kit's cable, or a 0.3 m one)",
                         ends=('FSESC USB (front end, position ESTIMATE)', 'power board USB hub'),
                         pts=[(e_front + 1.0, ecy - 14.0, ez + 11.0), (e_front + 3.5, ecy - 14.0, ez + 15.0), (-30.0, -46.0, 30.0),
                              (-10.0, -38.0, 28.0), (hub[0] - 8.0, hub[1] - 2.0, hub[2] + 4.0), hub])
    vc = pc('vesc_comm')
    D['vesc_comm'] = dict(d=3.0, spec='FSESC COMM lead, JST-PH 7-pin both ends (UART TX/RX/GND, ADC2 kill)',
                          ends=('FSESC COMM port (front end, position ESTIMATE)', 'power board FSESC header (rear edge)'),
                          pts=[(e_front + 1.0, ecy - 16.0, ez - 3.0), (e_front + 3.0, ecy - 17.0, ez - 1.0), (vc[0] - 2.0, vc[1], vc[2]),
                               (vc[0] + 1.0, vc[1], vc[2])])
    # ---- debug USB-C: a panel-mount socket in the right pod's window, its pigtail to the hub
    _, dbg = usbc_through_pod('debug_usbc')
    zc = (dbg[3] + dbg[4]) / 2
    D['debug_usbc'] = dict(d=4.0, spec='panel-mount USB-C socket with a 0.2 m pigtail to the hub (or a THT receptacle at the board edge: no cable)',
                           ends=('right pod, debug window', 'power board USB hub'),
                           pts=[(dbg[0], -84.0, zc), (dbg[0], -74.0, zc), (dbg[0] - 2.0, -64.0, zc + 3.0), (60.0, -42.0, 22.0),
                                (hub[0] + 6.0, hub[1] - 6.0, hub[2] + 4.0), hub])
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
    # ---- ESC battery leads: out of the ESC's front end, a U-turn into the XT60 plug on the board's rear edge
    # the case's front end is only POWER_X0 - (ESC_C + L/2) = 6.5 mm from the board edge, so the leads turn inboard at
    # once, run over the XT60 plug and come back into it from behind (a U-loop; the + lead low, the - lead high)
    eo = pc('esc_out'); xe = kit.POWER[0] - 16.0
    for k, (ys, dy, zl) in (('plus', (ecy + 8.0, 3.5, 0.0)), ('minus', (ecy - 8.0, -3.5, 8.0))):
        xg = (e_front + kit.POWER[0]) / 2
        D[f'esc_battery_{k}'] = dict(d=4.2, spec=f"FSESC 12 AWG battery {'+' if k == 'plus' else '-'} lead to an XT60 female",
                                     ends=('FSESC battery end', 'power board XT60PW (rear edge)'),
                                     pts=[(e_front + 1.0, ys, ez + zl / 2), (xg, ys + 2.0, ez + 2.0 + zl), (xg, -14.0, 18.0 + zl),
                                          (xe + 8.0, eo[1] - 7.0 + dy, 23.0 + zl), (xe - 7.0, eo[1] - 2.0 + dy, 22.0 + zl),
                                          (xe - 12.0, eo[1] + dy, 16.0), (xe - 4.0, eo[1] + dy, eo[2]), (xe - 1.0, eo[1] + dy, eo[2])])
    # ---- servo: the servo's own lead from the front-edge header down through the deck slot (or the board's notch)
    sv = pc('servo')
    srv_end = (126.0, -24.0, kit.Z_RIM + P['SERVO'][4] - 6.0)
    under = [(101.0, -50.0, -8.0), (101.0, -45.0, -19.0), (112.0, -33.0, -23.0), srv_end]
    if kit.servo_notch_local():
        pts = [(sv[0] + 14.0, sv[1], sv[2]), (sv[0] + 19.0, sv[1] - 4.0, sv[2]), (sv[0] + 10.0, -70.0, 14.0),
               (106.0, -70.0, 12.0), (101.0, -66.0, 9.0), (101.0, -64.0, 3.0), (101.0, -62.0, -3.0)] + under
    else:
        pts = [(sv[0] + 14.0, sv[1], sv[2]), (max(sv[0] + 19.0, 108.0), sv[1] - 2.0, sv[2] - 1.0), (101.0, -55.0, 6.0),
               (101.0, -55.0, 1.0), (101.0, -54.0, -3.0)] + under
    D['servo'] = dict(d=3.2, spec="servo's own 3-wire lead", ends=('power board servo header (front edge)', 'steering servo'), pts=pts)
    # ---- battery assembly: pack + through the MIDI fuse, pack - through the BMS, both to the XT90-S
    fx0, fx1, fy0, fy1 = kit.MIDI_FUSE_XY; fz = kit.Z_LID_TOP + kit.MIDI_FUSE_H
    stud_in, stud_out = (fx1 - 6.0, (fy0 + fy1) / 2, fz + 1.0), (fx0 + 6.0, (fy0 + fy1) / 2, fz + 1.0)
    xt = pc('xt90'); xt_end = kit.POWER[3] + 30.0
    D['pack_plus'] = dict(d=5.8, spec='10 AWG silicone, pack + (G4 end strip) to the MIDI fuse holder input',
                          ends=('pack + strip (under the lid)', 'MIDI 125 A fuse, input stud'),
                          pts=[(48.2, 21.0, 3.0), (48.2, 20.5, 12.0), (54.0, 21.0, 30.0), (stud_in[0], 24.0, fz + 8.0),
                               (stud_in[0], stud_in[1], fz + 6.0), stud_in])
    D['fuse_to_xt90'] = dict(d=5.8, spec='10 AWG silicone, fuse output stud to the XT90-S male (B+)',
                             ends=('MIDI fuse, output stud', 'XT90-S male, + (into the board XT90)'),
                             pts=[stud_out, (stud_out[0], stud_out[1], fz + 7.0), (-4.0, 46.0, 40.0), (xt[0] + 5.0, xt_end + 9.0, 30.0),
                                  (xt[0] + 5.0, xt_end + 4.0, xt[2]), (xt[0] + 5.0, xt_end, xt[2])])
    bt = (bx0 - 1.0, bms_y, bz0 + 22.0)                         # BMS B- / P- terminals at its rear end (ESTIMATE)
    D['pack_minus'] = dict(d=5.8, spec='10 AWG silicone, pack - (G1 end strip) to the BMS B-',
                           ends=('pack - strip (under the lid)', 'JBD BMS B-'),
                           pts=[(-48.0, 21.0, 3.0), (-48.0, 20.0, 12.0), (-56.0, 28.0, 30.0), (-74.0, 46.0, bt[2]), (bx0 - 8.0, bms_y - 2.0, bt[2]),
                                (bx0 - 4.0, bms_y, bt[2]), bt])
    bp = (bx0 - 1.0, bms_y, bz0 + 40.0)
    D['bms_p_minus'] = dict(d=5.8, spec='10 AWG silicone, BMS P- to the XT90-S male (system ground)',
                            ends=('JBD BMS P-', 'XT90-S male, - (into the board XT90)'),
                            pts=[bp, (bx0 - 5.0, bms_y, bp[2]), (bx0 - 8.0, bms_y - 6.0, bp[2] - 4.0), (-62.0, 50.0, 38.0),
                                 (xt[0] - 5.0, xt_end + 9.0, 30.0), (xt[0] - 5.0, xt_end + 4.0, xt[2]), (xt[0] - 5.0, xt_end, xt[2])])
    bb = (bx0 - 1.0, bms_y, bz0 + 62.0)
    D['pack_sense'] = dict(d=4.5, spec="pack's 7-wire sense lead (JST-XH 7-pin) and the adapter harness to the BMS balance and NTC inputs",
                           ends=('pack taps B0-B4 and NTC', 'JBD BMS balance connector'),
                           pts=[(0.0, 21.0, 3.0), (1.5, 21.0, 10.0), (2.5, 26.0, 36.0), (6.0, 40.0, 47.0), (-2.0, 46.0, 53.0), (-20.0, 50.0, 58.0), (-60.0, 54.0, 64.0),
                                (bx0 - 8.0, bms_y - 2.0, bb[2]), (bx0 - 4.0, bms_y, bb[2]), bb])
    bu = pc('bms_uart')
    bm = (bx0 - 1.0, bms_y, bz0 + 80.0)
    D['bms_uart'] = dict(d=3.0, spec='JBD 4-pin UART lead to the board JST-XH 4-pin (opto-isolated on the board)',
                         ends=('JBD BMS UART port', 'power board BMS UART (pack edge)'),
                         pts=[bm, (bx0 - 6.0, bms_y - 1.0, bm[2]), (bx0 - 8.0, bms_y - 8.0, bm[2] - 10.0), (-62.0, 50.0, 46.0),
                              (-30.0, 40.0, 36.0), (bu[0], 26.0, 30.0), (bu[0], 20.0, bu[2] + 4.0), (bu[0], kit.POWER[3] + 1.0, bu[2])])
    # ---- side-pod fan: forward along the right edge to the board's fan header (front edge per PHASE2)
    f0 = kit.FAN_X[0]; fh = pc('fan')
    D['side_fan'] = dict(d=2.2, spec='fan lead, 4-pin (fan to the power board)',
                         ends=('40 mm fan (right pod)', 'power board fan 4-pin (front edge)'),
                         pts=[(f0 + 2.0, -79.0, 5.0), (f0 + 2.0, -77.3, 10.0), (f0 + 6.0, -73.0, 8.0), (-40.0, -72.5, 7.0),
                              (60.0, -72.5, 7.0), (xf - 14.0, -72.0, 7.0), (xf + 3.0, -70.0, 10.0), (fh[0] + 5.0, fh[1] - 11.0, fh[2]),
                              (fh[0] + 2.0, fh[1], fh[2])])
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
    ant_under, ant_over = antennas()
    lid_plug, _ = rj45_plug_down(*LID_JACK)
    chg, _ = usbc_through_pod('charge_usbc')
    dbg, dw = usbc_through_pod('debug_usbc')
    zc = (dw[3] + dw[4]) / 2
    # panel-mount USB-C socket in the debug window (12 x 7 mm body, flange on the outer wall) with the cable plug
    dbg_panel = box(dw[0] - 6.0, dw[0] + 6.0, -kit.POD['y_out'] - 15.0, -kit.POD['y_in'] - 6.0, zc - 3.5, zc + 3.5)
    new_parts = dict(stack_canopy=canopy)
    new_comps = dict(antenna_jacks=ant_under, antennas=ant_over, rj45_plug_lidar=lid_plug,
                     usbc_plug_charge=chg, usbc_panel_debug=dbg_panel)
    cables = cable_defs()
    stand = bench_stand()
    return (S, comps, parts, extras, info), new_parts, new_comps, cables, stand, n_hex


# expected contacts: a part and the thing it is fastened to or plugged into
TOUCH = {frozenset(p) for p in (
    ('stack_canopy', 'devkit_tray'), ('stack_canopy', 'canopy_leg'), ('antenna_jacks', 'stack_canopy'),
    ('antennas', 'stack_canopy'), ('antenna_jacks', 'antennas'), ('rj45_plug_lidar', 'usb_eth_adapter'),
    ('usbc_plug_charge', 'power_parts_low'), ('usbc_panel_debug', 'side_pod_right'))}
_BOARD = {'power_parts_low', 'power_parts_tall'}
_PACK = {'pack_lid', 'pack_box', 'cells_4s3p', 'cell_holder_top'}
# what each cable may touch: its connectors, and where it ends on the power board, the board's height-map blocks
# (those blocks are envelopes for parts the leads are routed between on the real board)
CABLE_OK = {
    'camera': {'devkit_plugs', 'camera_plug'},
    'camera_power': {'camera_m8_plug'} | _BOARD,
    'lidar_ethernet': {'rj45_plug_lidar', 'lidar_connectors'},
    'lidar_usb': {'usb_eth_adapter', 'devkit_plugs'},
    'lidar_power': {'lidar_connectors'} | _BOARD,
    'devkit_dc': {'devkit_plugs'} | _BOARD,
    'ribbon_40pin_a': {'devkit_header_plugs'} | _BOARD, 'ribbon_40pin_b': {'devkit_header_plugs'} | _BOARD,
    'ribbon_40pin_c': {'devkit_header_plugs'} | _BOARD,
    'j14': {'devkit_header_plugs'} | _BOARD,
    'devkit_usbc': {'devkit_plugs'} | _BOARD,
    'pico_usb': {'devkit_plugs'} | _BOARD,
    'vesc_usb': {'esc_case'} | _BOARD,
    'vesc_comm': {'esc_case'} | _BOARD,
    'debug_usbc': {'usbc_panel_debug', 'side_pod_right'} | _BOARD,
    'motor_A': {'esc_case', 'motor'}, 'motor_B': {'esc_case', 'motor'}, 'motor_C': {'esc_case', 'motor'},
    'hall': {'esc_case', 'motor'},
    'esc_battery_plus': {'esc_case', 'esc_out_plug'}, 'esc_battery_minus': {'esc_case', 'esc_out_plug'},
    'servo': {'steering_servo'} | _BOARD,
    'pack_plus': _PACK | {'midi_fuse'},
    'fuse_to_xt90': {'midi_fuse', 'xt90s_pack'},
    'pack_minus': _PACK | {'bms'},
    'bms_p_minus': {'bms', 'xt90s_pack'},
    'pack_sense': _PACK | {'bms'},
    'bms_uart': {'bms'} | _BOARD,
    'side_fan': {'fan_40mm', 'side_pod_right'} | _BOARD,
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
    win = {n: (xc, w, z0, z1) for (n, xc, w, z0, z1) in P['POD_WINDOWS']}
    chg_bb = new_comps['usbc_plug_charge'].val().BoundingBox()
    xc, w, z0, z1 = win['charge_usbc']
    cl = dict(canopy_over_jetson_fan_mm=round(Z_CANOPY - Z_SINK_TOP, 2),
              canopy_over_devkit_plugs_mm=round(Z_CANOPY - CANOPY_LIP - plug_top, 2),
              canopy_over_j12_idc_mm=round(Z_CANOPY - idc_top, 2),
              canopy_to_bms_mm=round(kit.bms_place()[2] - CANOPY_XY[3], 2),
              charge_plug_in_window_side_gap_mm=round(min(chg_bb.xmin - (xc - w / 2), (xc + w / 2) - chg_bb.xmax), 2),
              charge_plug_in_window_z_gap_mm=round(min(chg_bb.zmin - z0, z1 - chg_bb.zmax), 2))
    return rows, cable_hits, cable_cross, fov, cl


def export(new_parts, new_comps, stand):
    res = {}
    orient = dict(stack_canopy=((1, 0, 0), 180), bench_stand=((1, 0, 0), 180))
    for name, p in list(new_parts.items()) + [('bench_stand', stand)]:
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
    items = [(parts[k], grey) for k in ('devkit_tray', 'canopy_leg', 'pack_lid', 'bms_fence')] + [(comps[k], blue) for k in keys + ('bms',)]
    items += [(new_parts['stack_canopy'], light), (new_comps['antenna_jacks'], grey), (new_comps['antennas'], grey)]
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
    renders(kb, new_parts, new_comps, stand)
    wt = wiring_table(cables)
    rep = dict(z=dict(power_top=Z_POWER_TOP, tray_top=Z_TRAY_TOP, devkit_bottom=Z_DEVKIT_BOT, devkit_top=Z_DEVKIT_TOP,
                      sink_top=Z_SINK_TOP, canopy_underside=Z_CANOPY),
               power_L=P['POWER_L'], canopy_xy=CANOPY_XY, canopy_posts=CANOPY_POSTS, antennas=ANTENNAS, fan_centre=FAN_C,
               grille_holes=n_hex, power_conn_local=POWER_CONN, clearances=cl,
               interference=rows, cable_interference=cable_hits, cable_crossings=cable_cross, lidar_plane=fov, parts=res, wiring=wt,
               cables={k: dict(d=c['d'], pts=[[round(v, 2) for v in p] for p in c['path']]) for k, c in cables.items()})
    with open(os.path.join(OUT, 'extras_report.json'), 'w') as f:
        json.dump(rep, f, indent=1, default=str)
    print(json.dumps({k: rep[k] for k in ('clearances', 'interference', 'cable_interference', 'cable_crossings', 'lidar_plane')}, indent=1))
    for k, v in res.items():
        print(f'{k:16s} bed {v["bed_xyz"]}  {v["volume_cm3"]:6.1f} cm3  ~{v["mass_g_solid_petgcf"]:.0f} g solid  fits250={v["fits_250_bed"]} solids={v["solids"]}')
    for r in wt:
        print(f"{r['cable']:18s} {r['routed_mm']:5d} mm routed, cut {r['cut_mm']} mm  {r['spec']}")
