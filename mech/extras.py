"""Atlas car v2: the parts that finish the car, on top of mech/kit.py.

    python3 extras.py         build, check against the whole kit, export STEP/STL, write out/extras_report.json

What is here (see docs/COMPLETE_CAR.md for why each one exists):

  stack_canopy      printed cover over the board stack, on three M3 x 40 mm standoffs from the brain board's
                    corner holes. Grille over the Jetson fan, two RP-SMA holes for the Wi-Fi antennas.
  bench_stand       printed stand that holds the chassis with the wheels off the bench, for the ESC bench tests
                    at 50 A and 70 A (ARCHITECTURE.md, First power-up).
  cables            every cable run as a path through the model, so its length is known and its clearance is
                    checked like any other part: camera, lidar Ethernet and power, motor phases, hall sensor,
                    servo, pack leads and sense lead, side-pod fan, Wi-Fi pigtails.
  bought parts      the mating plugs (both RJ45 plugs and boots), the canopy standoffs, the antenna bulkheads and
                    antennas, as envelopes for the checks.

Same frame and parameters as kit.py: +x forward, +y car left, +z up, origin at the deck centre, deck top at z 0.
Chassis numbers are kit.py's estimates (docs/MEASURE_FIRST.md).
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
from kit import P, box, cylz, cyl, union, volume, n_solids, inter, bb_overlap, M3_CLEAR  # noqa: E402

OUT = kit.OUT

# ----------------------------------------------------------------------------- the board stack, from kit.py
Z_DRIVE_TOP = P['DRIVE_Z'] + P['PCB_T']                      # 8.6
Z_BRAIN_BOT = Z_DRIVE_TOP + P['STACK_H']                     # 28.6
Z_BRAIN_TOP = Z_BRAIN_BOT + P['PCB_T']                       # 30.2
Z_SINK_TOP = Z_BRAIN_TOP + P['JETSON_SINK_H']                # 62.2, top of the dev-kit heatsink and fan

# ----------------------------------------------------------------------------- canopy
CANOPY_STANDOFF = 40.0          # M3 x 40 mm male-female hex standoffs, 5.5 mm across flats
CANOPY_T = 2.4
CANOPY_LIP = 4.0                # stiffening lip hanging down around the edge
Z_CANOPY = Z_BRAIN_TOP + CANOPY_STANDOFF                     # 70.2, canopy underside: 8 mm over the Jetson fan
CANOPY_XY = (-44.0, 84.0, -79.0, 20.0)                       # 4 mm past the brain board, 5 mm on the right
CANOPY_R = 12.0
# three of the brain board's four corners (kit.BRAIN_HOLES): brain-local (115.06, 5.06) = Antmicro H3,
# (6, 84) = H1001, (114, 84) = H1002. The fourth, brain-local (10.06, 5.06) = Antmicro H4, is under the camera's
# RJ45 jack J6, so nothing can be screwed into it from the top.
CANOPY_POSTS = [kit.BRAIN_HOLES[i] for i in (1, 2, 3)]
JETSON_BOX = (-11.9, 58.0, -66.5, -21.2)                     # kit.boards()['jetson_module_and_sink'] in plan
FAN_C = ((JETSON_BOX[0] + JETSON_BOX[1]) / 2, (JETSON_BOX[2] + JETSON_BOX[3]) / 2)
GRILLE_R = 25.0                 # hex grille over the dev-kit fan (about 40 mm)
# RP-SMA bulkheads: 1/4-36 UNS thread, 6.5 mm hole with a 5.8 mm flat so the jack cannot turn; 60 mm apart
ANTENNAS = [(-36.0, 0.0), (-36.0, -60.0)]
RPSMA_HOLE, RPSMA_FLAT = 6.5, 5.8
ANTENNA_L = 108.0               # 2.4/5 GHz dipole ("rubber duck"), about 108 mm long with its swivel


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
    # pads under the three posts and the two antenna jacks
    for (x, y) in CANOPY_POSTS:
        c = c.union(cylz(x, y, Z_CANOPY - 1.0, Z_CANOPY + 0.01, 10.0))
    for (x, y) in ANTENNAS:
        c = c.union(cylz(x, y, Z_CANOPY - 2.0, Z_CANOPY + 0.01, 14.0))
    # holes: M3 clearance at the posts (M3 x 6 button heads into the standoffs), RP-SMA with its flat
    for (x, y) in CANOPY_POSTS:
        c = c.cut(cylz(x, y, Z_CANOPY - 3, Z_CANOPY + CANOPY_T + 1, M3_CLEAR))
    for (x, y) in ANTENNAS:
        h = cylz(x, y, Z_CANOPY - 4, Z_CANOPY + CANOPY_T + 1, RPSMA_HOLE).intersect(
            box(x - RPSMA_HOLE, x + RPSMA_HOLE, y - RPSMA_FLAT / 2, y + RPSMA_FLAT / 2, Z_CANOPY - 5, Z_CANOPY + 5))
        c = c.cut(h)
    # hex grille over the Jetson fan: 5 mm across flats, 6.6 mm pitch, inside GRILLE_R
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
    # the team name, engraved 0.6 mm into the top (prints first, on the bed)
    txt = (cq.Workplane('XY').text('ATLAS', 13.0, 0.6, font='DejaVu Sans', kind='bold', halign='center', valign='center')
           .translate((30.0, 2.0, Z_CANOPY + CANOPY_T - 0.6)))
    c = c.cut(txt)
    return c, len(holes)


def canopy_standoffs():
    return union(*[cq.Workplane('XY').polygon(6, 5.5 / math.cos(math.radians(30))).extrude(CANOPY_STANDOFF)
                   .translate((x, y, Z_BRAIN_TOP)) for (x, y) in CANOPY_POSTS])


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
def rj45_plug(x_mid, y_face, z_mid, sign):
    """RJ45 plug (11.7 x 8 mm body, 21 mm long) and strain-relief boot (14 x 10, 11 mm), leaving the jack face
    y_face in direction sign (+1 = toward +y)."""
    ya, yb = sorted((y_face, y_face + sign * 21.0))
    yc, yd = sorted((y_face + sign * 21.0, y_face + sign * 32.0))
    body = box(x_mid - 6.1, x_mid + 6.1, ya, yb, z_mid - 5.0, z_mid + 5.0)
    boot = box(x_mid - 7.0, x_mid + 7.0, yc, yd, z_mid - 5.0, z_mid + 5.0)
    return body.union(boot), (x_mid, y_face + sign * 32.0, z_mid)


RJ45_Z = Z_BRAIN_TOP + 6.5          # plug axis height over the brain board (jack 13.5 tall)
CAM_JACK = (-30.5, -73.9)           # kit rj45_poe_camera: x -39.4..-21.6, opening at y -73.9 toward the car's right
LID_JACK = (61.4, 15.8)             # kit rj45_lidar: x 53.2..69.6, opening at y 15.8 toward the car's left


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


def pod_top_z(y):
    """z of the side pod's top surface at |y| (kit.side_pod profile: (80, 50) to (89, 47))"""
    y = abs(y)
    return 50.0 - max(0.0, min(9.0, y - 80.0)) / 3.0


def cable_defs():
    cam_start = (114.5, 6.0, kit.ARCH_TOP + 4.0 + 14.5)        # end of kit's camera_plug (M12 X-coded)
    lid_eth = (114.63, 10.0, P['PLINTH_T'] + 9.0)               # ends of kit's lidar_connectors (M12)
    lid_pwr = (114.63, -10.0, P['PLINTH_T'] + 9.0)
    _, cam_boot = rj45_plug(CAM_JACK[0], CAM_JACK[1], RJ45_Z, -1)
    _, lid_boot = rj45_plug(LID_JACK[0], LID_JACK[1], RJ45_Z, +1)
    zc = pod_top_z(86.0) + 3.5 + 1.5                            # camera cable lying on the right pod
    zt = Z_DRIVE_TOP                                             # drive board top
    motor_axis = (P['MOTOR_X'], kit.Z_RIM + P['MOTOR_AXIS_ABOVE_RIM'])
    y_bell = P['MOTOR_Y'][0] - 4.0                               # just outboard of the motor's end bell
    D = {}
    D['camera'] = dict(d=7.0, spec='M12 X-coded 8-pin to RJ45, Cat6a (camera data and PoE power)',
                       ends=('brain board J6 (RJ45, PoE port)', 'camera M12'),
                       pts=[cam_boot, (cam_boot[0], cam_boot[1] - 8, cam_boot[2] + 2), (-27.0, -113.0, 49.0),
                            (-16.0, -99.0, zc + 0.5), (4.0, -86.0, zc), (70.0, -86.0, zc), (92.0, -81.0, 62.0),
                            (96.0, -52.0, 86.0), (94.0, -18.0, 104.0), (105.0, 3.0, 118.0), cam_start])
    D['lidar_ethernet'] = dict(d=6.0, spec='donor SICK M12 D-coded 4-pin to RJ45 (TiM561 Ethernet)',
                               ends=('brain board J1301 (RJ45)', 'lidar Ethernet M12'),
                               pts=[lid_boot, (lid_boot[0], lid_boot[1] + 8, lid_boot[2]), (72.0, 62.0, 32.0),
                                    (92.0, 48.0, 23.0), (105.0, 24.0, 17.0), (111.0, 12.5, 15.0), lid_eth])
    D['lidar_power'] = dict(d=5.5, spec='donor SICK M12 power cable, cut and stripped into the terminal',
                            ends=('drive board J902 (2-pin terminal)', 'lidar power M12'),
                            pts=[(79.0, -38.5, zt + 2.6), (85.0, -38.5, zt + 3.0), (95.0, -33.0, 12.0),
                                 (107.0, -17.0, 14.0), (111.0, -11.0, 15.0), lid_pwr])
    ph = {'A': 10.5, 'B': -6.0, 'C': -22.5}                      # J501..J503 wire pads, drive-local y 35.5 -> car -38.5
    lanes = {'A': -58.0, 'B': -52.0, 'C': -46.0}
    for i, (k, xp) in enumerate(ph.items()):
        ang = math.radians(90 + 120 * i)
        end = (motor_axis[0] + 9.0 * math.cos(ang), y_bell, motor_axis[1] + 9.0 * math.sin(ang))
        yl = lanes[k]
        D[f'motor_{k}'] = dict(d=4.2, spec=f'12 AWG silicone, phase {k}, 4 mm bullet at the motor',
                               ends=(f'drive board J50{i + 1} (wire pad)', f'motor phase {k}'),
                               pts=[(xp, -38.5, zt + 2.2), (xp - 3, yl + 4, zt + 3.5), (xp - 12, yl, zt + 4.5),
                                    (-56.0, yl, zt + 5.0), (-63.5, yl, zt + 1.0), (-63.5, yl, 3.6),
                                    (-52.0, yl, 3.6), (-52.0, yl, -8.0), (-60.0, yl - 6, -24.0),
                                    (-95.0, -74.0 + 3 * i, -30.0 - 2 * i), (-116.0, y_bell - 2, end[2] + 4), end])
    D['hall'] = dict(d=3.2, spec="motor's own sensor lead (6-pin, JST-ZH assumed)",
                     ends=('drive board J603', 'motor sensor port'),
                     pts=[(-56.8, -53.5, zt + 7.0), (-60.5, -53.5, zt + 9.0), (-65.5, -55.0, zt + 2.0), (-65.5, -55.0, 2.5),
                          (-54.0, -55.0, 2.4), (-52.0, -55.0, -8.0), (-72.0, -66.0, -22.0), (-110.0, -80.0, -24.0),
                          (-124.0, y_bell + 2.0, motor_axis[1] + 17.0)])
    D['servo'] = dict(d=3.2, spec="servo's own 3-wire lead",
                      ends=('drive board J901', 'steering servo'),
                      pts=[(77.2, -55.0, zt + 13.0), (88.0, -48.0, zt + 10.5), (100.0, -41.0, 12.0), (101.0, -40.0, 6.0),
                           (101.0, -40.0, 2.0), (101.0, -40.0, -3.0), (101.0, -40.0, -8.0), (101.0, -39.5, -19.0), (112.0, -33.0, -23.0),
                           (126.0, -24.0, kit.Z_RIM + P['SERVO'][4] - 6.0)])
    D['pack_plus'] = dict(d=5.8, spec='10 AWG silicone, pack + (G4 end strip) to B+',
                          ends=('pack + strip (under the lid)', 'drive board J101 B+'),
                          pts=[(48.2, 21.0, 3.0), (48.2, 22.0, 13.0), (20.0, 22.5, 15.0), (-18.0, 22.0, 15.5),
                               (-25.5, 14.0, 14.0), (-25.5, 11.5, zt + 1.0)])
    D['pack_minus'] = dict(d=5.8, spec='10 AWG silicone, pack - (G1 end strip) to B-',
                           ends=('pack - strip (under the lid)', 'drive board J102 B-'),
                           pts=[(-48.0, 21.0, 3.0), (-47.0, 27.0, 17.0), (-24.0, 28.5, 22.5), (-15.0, 19.0, 21.0),
                                (-13.5, 12.5, 15.0), (-13.5, 11.5, zt + 1.0)])
    D['pack_sense'] = dict(d=4.5, spec='7-wire 24 AWG sense lead, JST-XH 7-pin at the board',
                           ends=('pack taps B0-B4 and NTC', 'drive board J103'),
                           pts=[(0.0, 21.0, 3.0), (0.0, 22.5, 13.0), (30.0, 21.5, 13.5), (43.0, 17.5, 12.5), (46.5, 13.0, 11.8)])
    D['side_fan'] = dict(d=2.2, spec='fan lead, 4-pin (fan to the drive board)',
                         ends=('40 mm fan (right pod)', 'drive board J903'),
                         pts=[(FAN_X0 + 2.0, -79.0, 5.0), (FAN_X0 + 2.0, -77.3, 10.0), (FAN_X0 + 1.0, -75.8, 14.0),
                              (-20.0, -66.0, zt + 4.0), (-40.0, -62.5, zt + 3.5), (-48.3, -66.0, zt + 5.0),
                              (-48.3, -69.5, zt + 9.0)])
    wifi = (18.0, -41.0, Z_BRAIN_TOP + 3.3)                      # antenna jacks of the M.2 Wi-Fi card under the module
    D['wifi_1'] = dict(d=1.8, spec='u.FL/MHF4 to RP-SMA bulkhead pigtail, 1.13 or 1.37 mm coax',
                       ends=('M.2 Wi-Fi card (under the Jetson module)', 'antenna jack, canopy rear left'),
                       pts=[(wifi[0], wifi[1] + 4, wifi[2]), (12.0, -17.0, 38.0), (-8.0, -4.0, 50.0), (-28.0, 0.0, 58.0),
                            (ANTENNAS[0][0], ANTENNAS[0][1], Z_CANOPY - 8.0)])
    D['wifi_2'] = dict(d=1.8, spec='u.FL/MHF4 to RP-SMA bulkhead pigtail, 1.13 or 1.37 mm coax',
                       ends=('M.2 Wi-Fi card (under the Jetson module)', 'antenna jack, canopy rear right'),
                       pts=[(wifi[0], wifi[1] - 4, wifi[2]), (-6.0, -47.0, 34.8), (-18.0, -52.0, 44.0), (-31.0, -58.0, 56.0),
                            (ANTENNAS[1][0], ANTENNAS[1][1], Z_CANOPY - 8.0)])
    for k, c in D.items():
        c['path'] = catmull(c['pts'])
        c['length_mm'] = round(path_len(c['path']), 1)
    return D


FAN_X0 = kit.FAN_X[0]


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
        if s1 < skip_ends or s0 > total - skip_ends or L < 1e-6:
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
    cam_plug, _ = rj45_plug(CAM_JACK[0], CAM_JACK[1], RJ45_Z, -1)
    lid_plug, _ = rj45_plug(LID_JACK[0], LID_JACK[1], RJ45_Z, +1)
    new_parts = dict(stack_canopy=canopy)
    new_comps = dict(canopy_standoffs=canopy_standoffs(), antenna_jacks=ant_under, antennas=ant_over,
                     rj45_plug_camera=cam_plug, rj45_plug_lidar=lid_plug)
    cables = cable_defs()
    stand = bench_stand()
    return (S, comps, parts, extras, info), new_parts, new_comps, cables, stand, n_hex


# expected contacts: a part and the thing it is fastened to or plugged into
TOUCH = {frozenset(p) for p in (
    ('canopy_standoffs', 'brain_pcb'), ('canopy_standoffs', 'stack_canopy'), ('antenna_jacks', 'stack_canopy'),
    ('antennas', 'stack_canopy'), ('antenna_jacks', 'antennas'), ('rj45_plug_camera', 'rj45_poe_camera'),
    ('rj45_plug_lidar', 'rj45_lidar'))}
# what each cable may touch: its connectors, and the board it lies on (the drive board's 3 mm parts blanket
# stands for small parts the leads are routed between on the real board)
CABLE_OK = {
    'camera': {'rj45_plug_camera', 'camera_plug'},
    'lidar_ethernet': {'rj45_plug_lidar', 'lidar_connectors'},
    'lidar_power': {'lidar_connectors', 'drive_top_parts'},
    'motor_A': {'drive_top_parts', 'motor'}, 'motor_B': {'drive_top_parts', 'motor'}, 'motor_C': {'drive_top_parts', 'motor'},
    'hall': {'drive_top_parts', 'motor'},
    'servo': {'drive_top_parts', 'steering_servo'},
    'pack_plus': {'pack_lid', 'pack_box', 'cells_4s3p', 'cell_holder_top', 'drive_top_parts'},
    'pack_minus': {'pack_lid', 'pack_box', 'cells_4s3p', 'cell_holder_top', 'drive_top_parts'},
    'pack_sense': {'pack_lid', 'pack_box', 'cells_4s3p', 'cell_holder_top', 'drive_top_parts'},
    'side_fan': {'fan_40mm', 'side_pod_right', 'drive_top_parts'},
    'wifi_1': {'jetson_module_and_sink', 'antenna_jacks'},
    'wifi_2': {'jetson_module_and_sink', 'antenna_jacks'},
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
    # lidar scan plane: the new parts and cables within +-6 mm of it must sit in the rear blind sector
    zc = info['scan_z']
    lx = P['LIDAR_FRONT_X'] - 30.5
    slab = box(-400, 400, -300, 300, zc - 6, zc + 6)
    fov = []
    items = new + [(f'cable:{k}', union(*cable_solids(c, 0.0))) for k, c in cables.items()]
    for name, s in items:
        if not bb_overlap(s, slab):
            continue
        sec = s.intersect(slab)
        if volume(sec) < 0.1:
            continue
        bbx = sec.val().BoundingBox()
        bearings = [abs(math.degrees(math.atan2(y, x - lx))) for x in (bbx.xmin, bbx.xmax) for y in (bbx.ymin, bbx.ymax)]
        fov.append((name, round(min(bearings), 1), 'inside blind sector' if min(bearings) >= 135 else 'IN VIEW'))
    # clearances worth reporting
    cl = dict(canopy_over_jetson_fan_mm=round(Z_CANOPY - Z_SINK_TOP, 2),
              camera_plug_in_pod_notch_side_gap_mm=round(min(CAM_JACK[0] - 7.0 - kit.CAM_PLUG_NOTCH['x'][0],
                                                              kit.CAM_PLUG_NOTCH['x'][1] - (CAM_JACK[0] + 7.0)), 2),
              camera_plug_above_notch_floor_mm=round(RJ45_Z - 5.0 - kit.CAM_PLUG_NOTCH['z0'], 2))
    return rows, cable_hits, fov, cl


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


def wiring_table(cables):
    rows = []
    for k, c in cables.items():
        L = c['length_mm']
        rows.append(dict(cable=k, spec=c['spec'], from_=c['ends'][0], to=c['ends'][1], d_mm=c['d'],
                         routed_mm=round(L), cut_mm=int(math.ceil((L * 1.1 + 20) / 10.0) * 10)))
    return rows


if __name__ == '__main__':
    kb, new_parts, new_comps, cables, stand, n_hex = build()
    rows, cable_hits, fov, cl = checks(kb, new_parts, new_comps, cables)
    res = export(new_parts, new_comps, stand)
    wt = wiring_table(cables)
    rep = dict(z=dict(drive_top=Z_DRIVE_TOP, brain_top=Z_BRAIN_TOP, sink_top=Z_SINK_TOP, canopy_underside=Z_CANOPY),
               canopy_posts=CANOPY_POSTS, antennas=ANTENNAS, grille_holes=n_hex, clearances=cl,
               interference=rows, cable_interference=cable_hits, lidar_plane=fov, parts=res, wiring=wt,
               cables={k: dict(d=c['d'], pts=[[round(v, 2) for v in p] for p in c['path']]) for k, c in cables.items()})
    with open(os.path.join(OUT, 'extras_report.json'), 'w') as f:
        json.dump(rep, f, indent=1, default=str)
    print(json.dumps({k: rep[k] for k in ('clearances', 'interference', 'cable_interference', 'lidar_plane')}, indent=1))
    for k, v in res.items():
        print(f'{k:16s} bed {v["bed_xyz"]}  {v["volume_cm3"]:6.1f} cm3  ~{v["mass_g_solid_petgcf"]:.0f} g solid  fits250={v["fits_250_bed"]} solids={v["solids"]}')
    for r in wt:
        print(f"{r['cable']:15s} {r['routed_mm']:5d} mm routed, cut {r['cut_mm']} mm  {r['spec']}")
