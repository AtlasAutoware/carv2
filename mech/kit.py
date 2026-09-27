"""Atlas car v2 printed kit for the Traxxas Slash 4x4 (6822 chassis).

    python3 kit.py            build every part, run the fit checks, export STEP/STL, render

Frame (same as the car-1 mount set): +x forward, +y car left, +z up. Origin at the deck
centre, deck top at z = 0. Every chassis number below comes from the car-1/new-car keep-out
model in atlasstuff/power_board_v2/case/mounts_src/newcar/board_layout_newcar.py and is an
ESTIMATE unless marked; docs/MEASURE_FIRST.md lists what to measure before printing.
Environment variables of the same name override any number in P (e.g. UNDER_CLEARANCE=42).
"""
import os, sys, json, math, itertools
import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
for d in ('stl', 'step', 'renders', 'dxf'):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)

# ----------------------------------------------------------------------------- parameters
P = dict(
    # chassis interface (estimates carried over from the car-1 plate, see MEASURE_FIRST.md)
    UNDER_CLEARANCE=45.0,          # old plate underside (z -3.175) to chassis side-wall top
    TUB_DEPTH=24.0,
    FRONT_TOWER_X=168.3, REAR_TOWER_X=-141.7, TOWER_T=4.0, TOWER_W=120.0,
    TOWER_TOP_BELOW_OLD_PLATE=16.0,
    POST_D=7.0, POST_TOP=25.0,
    FRONT_POST=(180.36, 38.62), REAR_POST=(-127.68, 41.12),
    WHEELBASE=324.0, TRACK=296.0, TYRE_D=110.0, TYRE_W=42.0, TYRE_TOP_ABOVE_RIM=14.0, BUMP=30.0, LOCK_DEG=30.0,
    BATT_BAY=(-75.0, 65.0, 15.0, 62.0),
    GEARBOX=(-160.0, -110.0, -25.0, 25.0, 22.0), MOTOR_X=-125.0, MOTOR_D=36.0, MOTOR_Y=(-85.0, -25.0), MOTOR_AXIS_ABOVE_RIM=5.0,
    SHAFT=(-110.0, 128.0, -8.0, 8.0, -8.0), SERVO=(128.0, 150.0, -53.0, 3.0, 25.0), LINKAGE=(140.0, 185.0, -40.0, 40.0, 12.0),
    SHOCK_Y=42.0, SHOCK_CAP_D=20.0,
    # deck
    DECK_T=5.0, X_NOSE=238.0, X_TAIL=-226.0, HALF_W=88.75, NOSE_HALF_W=60.0, TAPER_X=120.0,
    RIB_DEPTH=10.0, RIB_T=3.0, JOINTS=(-80.0, 82.0), SPLICE_T=3.0, SPLICE_L=30.0,
    POST_SLOT=24.0,
    # pack: 12 x Molicel P28A 18650 (18.6 max dia x 65.2 max, 46 g; 18650batterystore.com)
    CELL_D=18.6, CELL_L=65.2, CELL_PITCH=20.0, HOLDER_T=5.0, HOLDER_POCKET=3.5,
    PACK_X0=-62.0, PACK_Y0=17.0,
    # boards (design package in ../boards)
    DRIVE=(-60.0, 80.0, -74.0, 16.0), DRIVE_Z=7.0, PCB_T=1.6, STACK_H=20.0, SPREADER_T=4.76,
    SPREADER=(-35.0, 25.0, -72.0, -24.0),   # 60 x 48 mm under the ESC power stage (drive-local X 25-85, Y 2-50)
    BRAIN=(-40.0, 80.0, -74.0, 16.0), JETSON_SINK_H=32.0,
    # sensors
    LIDAR_FRONT_X=238.0, PLINTH_T=6.0,
    CAM_LENS_D=31.0, CAM_LENS_L=30.5, CAM_M12_L=48.0, CAM_PITCH=0.0,   # Kowa LM4NCL 3.5 mm: 31 x 30.5 mm, 60 g (machinevisiondirect.com)
    CAM_HOLE_PITCH=(20.0, 20.0),   # ESTIMATE: 4 corner M3 holes on the Triton bottom, confirm on the camera
)
for k, v in list(P.items()):
    if k in os.environ:
        P[k] = type(v)(json.loads(os.environ[k])) if not isinstance(v, (tuple, list)) else tuple(json.loads(os.environ[k]))

OLD_PLATE_UNDERSIDE = -3.175
Z_RIM = OLD_PLATE_UNDERSIDE - P['UNDER_CLEARANCE']          # -48.175
Z_FLOOR = Z_RIM - P['TUB_DEPTH']                           # -72.175
TOWER_TOP = OLD_PLATE_UNDERSIDE - P['TOWER_TOP_BELOW_OLD_PLATE']   # -19.175
FRONT_AXLE = P['FRONT_TOWER_X'] + 10.0
REAR_AXLE = FRONT_AXLE - P['WHEELBASE']
DT = P['DECK_T']
M3_INSERT, M3_CLEAR, M3_HEAD = 4.0, 3.4, 6.2

# ----------------------------------------------------------------------------- helpers

def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane('XY').box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def cylz(x, y, z0, z1, d):
    return cq.Workplane('XY').add(cq.Solid.makeCylinder(d / 2, z1 - z0, cq.Vector(x, y, z0), cq.Vector(0, 0, 1)))


def cyl(p, d, length, direction):
    return cq.Workplane('XY').add(cq.Solid.makeCylinder(d / 2, length, cq.Vector(*p), cq.Vector(*direction)))


def cone(p, d0, d1, h):
    return cq.Workplane('XY').add(cq.Solid.makeCone(d0 / 2, d1 / 2, h, cq.Vector(*p), cq.Vector(0, 0, 1)))


def extrude_poly(pts, z0, z1):
    return cq.Workplane('XY').polyline(pts).close().extrude(z1 - z0).translate((0, 0, z0))


def union(*objs):
    objs = [o for o in objs if o is not None]
    r = objs[0]
    for o in objs[1:]:
        r = r.union(o)
    return r


def volume(w):
    return sum(s.Volume() for s in w.vals() if hasattr(s, 'Volume'))


def n_solids(w):
    return len(w.val().Solids()) if hasattr(w.val(), 'Solids') else 1


def half_w(x):
    """Deck half-width: full width to TAPER_X, straight taper to the nose."""
    if x <= P['TAPER_X']:
        return P['HALF_W']
    t = (x - P['TAPER_X']) / (P['X_NOSE'] - P['TAPER_X'])
    return P['HALF_W'] + t * (P['NOSE_HALF_W'] - P['HALF_W'])


# ----------------------------------------------------------------------------- chassis keep-outs

def chassis():
    S = {}
    S['tub'] = box(-150, 150, -50, 50, Z_FLOOR, Z_RIM).cut(box(-147, 147, -47, 47, Z_FLOOR + 3, Z_RIM + 1))
    g = P['GEARBOX']; S['gearbox'] = box(g[0], g[1], g[2], g[3], Z_FLOOR, Z_RIM + g[4])
    y0, y1 = P['MOTOR_Y']
    S['motor'] = cyl((P['MOTOR_X'], y0, Z_RIM + P['MOTOR_AXIS_ABOVE_RIM']), P['MOTOR_D'], y1 - y0, (0, 1, 0))
    s = P['SHAFT']; S['centre_shaft'] = box(s[0], s[1], s[2], s[3], Z_FLOOR + 3, Z_RIM + s[4])
    s = P['SERVO']; S['steering_servo'] = box(s[0], s[1], s[2], s[3], Z_FLOOR + 3, Z_RIM + s[4])
    s = P['LINKAGE']; S['steering_linkage'] = box(s[0], s[1], s[2], s[3], Z_FLOOR, Z_RIM + s[4])
    for name, tx, (px, py) in (('front', P['FRONT_TOWER_X'], P['FRONT_POST']), ('rear', P['REAR_TOWER_X'], P['REAR_POST'])):
        S[f'{name}_tower'] = box(tx - P['TOWER_T'] / 2, tx + P['TOWER_T'] / 2, -P['TOWER_W'] / 2, P['TOWER_W'] / 2, Z_FLOOR, TOWER_TOP)
        for sy in (1, -1):
            S[f'{name}_shock_{"L" if sy > 0 else "R"}'] = cylz(tx, sy * P['SHOCK_Y'], TOWER_TOP - 70, TOWER_TOP - 2, P['SHOCK_CAP_D'])
            S[f'{name}_post_{"L" if sy > 0 else "R"}'] = cylz(px, sy * py, TOWER_TOP, P['POST_TOP'], P['POST_D'])
    # tyres: swept over bump (0 and +BUMP) and, at the front, steering lock (-LOCK..+LOCK)
    r = P['TYRE_D'] / 2
    yc = P['TRACK'] / 2 - P['TYRE_W'] / 2
    zc = Z_RIM + P['TYRE_TOP_ABOVE_RIM'] - r
    for name, ax, steer in (('front', FRONT_AXLE, True), ('rear', REAR_AXLE, False)):
        for sy in (1, -1):
            env = None
            for bump in (0.0, P['BUMP'] / 2, P['BUMP']):
                for a in ((-P['LOCK_DEG'], -P['LOCK_DEG'] / 2, 0.0, P['LOCK_DEG'] / 2, P['LOCK_DEG']) if steer else (0.0,)):
                    t = cyl((ax, sy * yc - P['TYRE_W'] / 2, zc + bump), P['TYRE_D'], P['TYRE_W'], (0, 1, 0))
                    t = t.rotate((ax, sy * yc, 0), (ax, sy * yc, 1), a)
                    env = t if env is None else env.union(t)
            S[f'{name}_tyre_{"L" if sy > 0 else "R"}'] = env
    return S


# ----------------------------------------------------------------------------- component envelopes

def tim561():
    """SICK TiM561-2050101: 60 wide x 61 deep, 58.45 to the hood base, 85.75 to the hood top,
    scan plane 62.46 above the bottom face, 2 x M3 bottom threads 51 apart 16.79 from the rear
    face (SICK datasheet 1071419). Swivel unit and plug sizes are estimates (TIM561_MOUNT.md)."""
    xf = P['LIDAR_FRONT_X']; xr = xf - 61.0; z0 = P['PLINTH_T']
    body = box(xr, xf, -30, 30, z0, z0 + 58.45).edges('|Z').fillet(4)
    hood = cone((xr + 30.5, 0, z0 + 58.45), 58, 42, 85.75 - 58.45)
    swivel = box(xr - 17.37, xr, -20, 20, z0, z0 + 18)
    plugs = union(*[cyl((xr - 17.37, sy * 10, z0 + 9), 15, 45, (-1, 0, 0)) for sy in (1, -1)])
    return dict(lidar=union(body, hood), lidar_connectors=union(swivel, plugs)), z0 + 62.46, z0 + 85.75


def triton(cam_bottom_z, x_mount_face):
    """LUCID Triton TRI023S-CC: 29 x 29 x 45 mm without connectors and lens mount, 67 g,
    C-mount (edmundoptics.com/p/41817). Lens and M12 plug lengths are parameters."""
    x0 = x_mount_face - 45.0
    body = box(x0, x_mount_face, -14.5, 14.5, cam_bottom_z, cam_bottom_z + 29)
    lens = cyl((x_mount_face, 0, cam_bottom_z + 14.5), P['CAM_LENS_D'], P['CAM_LENS_L'], (1, 0, 0))
    plug = cyl((x0, 6, cam_bottom_z + 14.5), 16, P['CAM_M12_L'], (-1, 0, 0))
    return dict(camera=union(body, lens), camera_plug=plug)


def boards():
    """Envelopes of the two boards and their tall parts, from the placed PCBs (../boards: drive-local
    (X, Y) sits at car (X - 60, Y - 74), brain-local at car (X - 40, Y - 74))."""
    x0, x1, y0, y1 = P['DRIVE']; z = P['DRIVE_Z']; t = P['PCB_T']
    B = {}
    B['drive_pcb'] = box(x0, x1, y0, y1, z, z + t)
    B['drive_fets_bottom'] = box(-30, 20, -70, -26, z - 1.2, z)
    B['drive_standoffs_7mm'] = union(*[cylz(x, y, 0, z, 5.5) for (x, y) in DRIVE_HOLES])
    B['esc_heatsink'] = spreader()                                      # 3/16 in 6061, SendCutSend, 1 mm pad above
    # DC-link bulk caps C525-C528: Panasonic EEH-ZU1V331P, case G12, 10 mm x 12.8 mm (the 470 uF 35 V part is
    # 16.8 mm tall and would hit the brain board's NVMe SSD)
    B['drive_bulk_caps'] = union(*[cylz(-36.1 + 12.8 * i, -20.1, z + t, z + t + 12.8, 10) for i in range(4)])
    B['drive_top_parts'] = box(x0 + 2, x1 - 2, y0 + 2, y1 - 2, z + t, z + t + 3.0)
    B['usb_c_and_button'] = box(-62, -52, -25, -3, z + t, z + t + 4)
    zb = z + t + P['STACK_H']
    bx0, bx1, by0, by1 = P['BRAIN']
    B['brain_pcb'] = box(bx0, bx1, by0, by1, zb, zb + t)
    B['brain_standoffs_20mm'] = union(*[cylz(x, y, z + t, zb, 5.5) for (x, y) in BRAIN_HOLES])
    B['nvme_2280'] = box(-29.2, 51.2, -43.1, -20.8, zb - 4.8, zb)                # under the brain board
    B['jetson_module_and_sink'] = box(-11.9, 58.0, -66.5, -21.2, zb + t, zb + t + P['JETSON_SINK_H'])
    B['rj45_poe_camera'] = box(-39.4, -21.6, -73.9, -51.9, zb + t, zb + t + 13.5)  # Antmicro's RJ45, now PoE source
    B['rj45_lidar'] = box(53.2, 69.6, -6.0, 15.8, zb + t, zb + t + 13.5)          # J1301 behind the LAN7800
    B['stack_header'] = box(0.0, 51.0, -13.5, -9.5, z + t, zb)                     # SSQ socket + TSW pins, 20 mm
    B['fan_40mm'] = box(FAN_X[0], FAN_X[1], -88.4, -78.4, 2.0, 42.0)
    return B


def pack_cells():
    cells = []
    for i in range(6):
        for j in range(2):
            x = P['PACK_X0'] + 2 + P['CELL_PITCH'] * (i + 0.5)
            y = P['PACK_Y0'] + 2 + P['CELL_PITCH'] * (j + 0.5)
            cells.append(cylz(x, y, PACK_CELL_Z0, PACK_CELL_Z0 + P['CELL_L'], P['CELL_D']))
    return union(*cells)


# ----------------------------------------------------------------------------- pack geometry
PACK_IN_X = 6 * P['CELL_PITCH'] + 1.0          # 121: holders + 0.5 clearance a side
PACK_IN_Y = 2 * P['CELL_PITCH'] + 1.0          # 41
PACK_WALL = 1.6
PACK_TOP = 3.0                                  # flange top (flange sits on the deck top)
PACK_LID_T = 3.0
# stack inside the box, bottom up: floor 2, fish paper + strip 0.6, holder (lip 1.5 under the cell), cell, holder, strip + paper 0.6, foam 1.0
PACK_FLOOR = 2.0
PACK_INNER_H = 0.6 + (P['HOLDER_T'] - P['HOLDER_POCKET']) * 2 + P['CELL_L'] + 0.6 + 1.0
PACK_BOTTOM = PACK_TOP - PACK_INNER_H - PACK_FLOOR
PACK_CELL_Z0 = PACK_BOTTOM + PACK_FLOOR + 0.6 + (P['HOLDER_T'] - P['HOLDER_POCKET'])
PX0 = P['PACK_X0']; PX1 = PX0 + PACK_IN_X + 2 * PACK_WALL
PY0 = P['PACK_Y0']; PY1 = PY0 + PACK_IN_Y + 2 * PACK_WALL
PACK_SCREWS = [(PX0 - 3.5, PY0 + 6), (PX0 - 3.5, PY1 - 6), (PX1 + 3.5, PY0 + 6), (PX1 + 3.5, PY1 - 6), (-30, PY1 + 3.5), (30, PY1 + 3.5)]


# ----------------------------------------------------------------------------- deck
# drive board holes that go to the deck (H1001, H1002, H1003, H1004, H1007, H1008 in boards/drive/layout.py;
# drive-local (X, Y) -> car (X - 60, Y - 74)), 7 mm standoffs into deck inserts
_DH = {'H1001': (6.0, 6.0), 'H1002': (135.06, 5.06), 'H1003': (6.0, 84.0), 'H1004': (134.0, 84.0),
       'H1007': (6.0, 45.0), 'H1008': (134.0, 45.0)}
DRIVE_HOLES = [(x + P['DRIVE'][0], y + P['DRIVE'][2]) for (x, y) in _DH.values()]
# brain board corners (brain-local (10.06, 5.06), (115.06, 5.06), (6, 84), (114, 84)) on 20 mm standoffs over
# drive holes H1005, H1002, H1006, H1004
BRAIN_HOLES = [(x + P['BRAIN'][0], y + P['BRAIN'][2]) for (x, y) in ((10.06, 5.06), (115.06, 5.06), (6.0, 84.0), (114.0, 84.0))]
# heat spreader: four tapped M3 holes, screwed to the deck from below (outside the deck vents), and a
# notch under drive hole H1005 for the nut of the brain board's 20 mm standoff there
SPREADER_HOLES = [(-32.0, -60.0), (-32.0, -36.0), (22.0, -60.0), (22.0, -36.0)]
H1005_CAR = (30.06 + P['DRIVE'][0], 5.06 + P['DRIVE'][2])
SPREADER_NOTCH_R = 4.0
M3_TAP = 2.5


def spreader():
    x0, x1, y0, y1 = P['SPREADER']
    s = box(x0, x1, y0, y1, 0.0, P['SPREADER_T'])
    s = s.cut(cylz(H1005_CAR[0], H1005_CAR[1], -1, P['SPREADER_T'] + 1, 2 * SPREADER_NOTCH_R))
    for (x, y) in SPREADER_HOLES:
        s = s.cut(cylz(x, y, -1, P['SPREADER_T'] + 1, M3_TAP))
    return s


def spreader_dxf(path):
    """Flat pattern for SendCutSend: outline with the notch, 4 x 2.5 mm holes to be tapped M3."""
    import ezdxf
    from shapely.geometry import box as sbox, Point
    x0, x1, y0, y1 = P['SPREADER']
    g = sbox(x0, y0, x1, y1).difference(Point(*H1005_CAR).buffer(SPREADER_NOTCH_R, 64))
    doc = ezdxf.new('R2010', setup=True)
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()
    ox, oy = x0, y0                                     # part origin at its lower-left corner
    msp.add_lwpolyline([(x - ox, y - oy) for x, y in g.exterior.coords], close=True)
    for (x, y) in SPREADER_HOLES:
        msp.add_circle((x - ox, y - oy), M3_TAP / 2)
    doc.saveas(path)
PLINTH_BOLTS = [(P['LIDAR_FRONT_X'] - 32, 24), (P['LIDAR_FRONT_X'] - 32, -24), (P['LIDAR_FRONT_X'] - 6, 24), (P['LIDAR_FRONT_X'] - 6, -24)]
ARCH_X = (136.0, 150.0)
ARCH_Y = 42.0
ARCH_BOLTS = [(x, sy * ARCH_Y) for x in (ARCH_X[0] - 5, ARCH_X[1] + 5) for sy in (1, -1)]
POD = dict(x0=-105.0, x1=120.0, y_in=76.0, y_out=94.0, h=50.0, t=2.4)
# 40 mm side-pod fan (right pod), x range in the car frame. It sat at x -46..-6 until 2026-09-28, right
# outboard of the camera's RJ45 jack (brain board J6, car x -39.4..-21.6), where the camera plug has to
# go: the jack opens toward the car's right side, 2 mm from the pod wall. Moved forward, it is also
# centred on the ESC power stage (car x -30..20) instead of behind it.
FAN_X = (-16.0, 24.0)
# the camera plug passes through the right pod here: a slot open at the top, through both walls
CAM_PLUG_NOTCH = dict(x=(-40.5, -20.5), z0=27.0)
POD_TIE_SLOTS_X = (4.0, 70.0)       # zip-tie slot pairs on the right pod's top for the camera cable
SERVO_SLOT = (98.5, 103.5, -52.0, -28.0)    # deck slot for the steering servo lead (x0, x1, y0, y1)
POD_BOLTS = {1: [(-88, 72.5), (10, 72.5), (105, 72.5)], -1: [(-88, -72.5), (105, -72.5)]}
WING = dict(strut_x=(-214.0, -200.0), strut_y=55.0, z=88.0, chord=(-228.0, -183.0), span=95.0)
WING_BOLTS = [(x, sy * WING['strut_y']) for x in (WING['strut_x'][0] - 5, WING['strut_x'][1] + 5) for sy in (1, -1)]
SPLICE_Y = [(-74.0, -2.0), (2.0, 74.0)]          # bays between the edge ribs and the centre rib
JOINT_BOLTS = [(jx + sx * P['SPLICE_L'] / 3, y) for jx in P['JOINTS'] for sx in (-1, 1) for y in (-60.0, -40.0, -20.0, 20.0, 40.0, 60.0)]


def deck_outline_pts():
    xs = [P['X_TAIL'], P['TAPER_X'], P['X_NOSE']]
    right = [(x, -half_w(x)) for x in xs]
    left = [(x, half_w(x)) for x in reversed(xs)]
    return right + left


def deck_full():
    d = extrude_poly(deck_outline_pts(), -DT, 0).edges('|Z').fillet(10)
    # ribs underneath (kept inboard of the tyre sweep and the pack)
    ribs = [box(-88, 118, sy * 76 - 1.5, sy * 76 + 1.5, -DT - P['RIB_DEPTH'], -DT) for sy in (1, -1)]
    ribs.append(box(-100, 125, -1.5, 1.5, -DT - P['RIB_DEPTH'], -DT))
    ribs.append(box(104, 107, -76, 76, -DT - P['RIB_DEPTH'], -DT))
    ribs.append(box(-99, -96, -76, 76, -DT - P['RIB_DEPTH'], -DT))
    # tower saddles: 15.6 x 40 blocks, 22 below the old plate underside, slot over the tower top
    saddles = []
    for tx in (P['FRONT_TOWER_X'], P['REAR_TOWER_X']):
        b = box(tx - 7.8, tx + 7.8, -20, 20, OLD_PLATE_UNDERSIDE - 22, -DT)
        b = b.cut(box(tx - P['TOWER_T'] / 2 - 0.3, tx + P['TOWER_T'] / 2 + 0.3, -21, 21, OLD_PLATE_UNDERSIDE - 23, TOWER_TOP))
        saddles.append(b)
    d = union(d, *ribs, *saddles)
    # the ribs must not pass through the pack
    d = d.cut(box(PX0 - 0.5, PX1 + 0.5, PY0 - 0.5, PY1 + 0.5, -60, -DT + 0.01))
    # the splice plates sit in the rib bays across each joint: clear the ribs there
    for jx in P['JOINTS']:
        for (y0, y1) in SPLICE_Y:
            d = d.cut(box(jx - P['SPLICE_L'] / 2 - 0.3, jx + P['SPLICE_L'] / 2 + 0.3, y0 - 0.3, y1 + 0.3, -DT - 30, -DT))
    # vents under the ESC heat spreader (which sits directly on the deck)
    for y in (-64.25, -50.75, -37.25):
        d = d.cut(box(-28, 18, y - 4, y + 4, -DT - 1, 0.01))
    # pack window, post slots, cable passes
    d = d.cut(box(PX0 - 0.4, PX1 + 0.4, PY0 - 0.4, PY1 + 0.4, -DT - 20, 1))
    for (px, py) in (P['FRONT_POST'], P['REAR_POST']):
        for sy in (1, -1):
            s = P['POST_SLOT']
            d = d.cut(box(px - s / 2, px + s / 2, sy * py - s / 2, sy * py + s / 2, -60, 1))
    d = d.cut(box(-58, -46, -64, -40, -60, 1))     # motor phases + hall lead, under the drive board's rear edge
    # servo lead: a 5 x 24 mm slot just ahead of the front splice plates (x 67-97) and behind the cross rib
    # (x 104-107). Until 2026-09-28 it was x 86-98, over the right front splice plate and around the joint
    # bolt at (92, -40), so the plate blocked it and the bolt had no deck around it.
    d = d.cut(box(SERVO_SLOT[0], SERVO_SLOT[1], SERVO_SLOT[2], SERVO_SLOT[3], -60, 1))
    d = d.cut(box(100, 112, 36, 50, -60, 1))        # lidar / camera cable drop to the right-hand keeper (spare)
    # holes: inserts (4.0) or clearance (3.4)
    holes = []
    holes += [(x, y, M3_INSERT, 0) for (x, y) in DRIVE_HOLES]
    holes += [(x, y, M3_CLEAR, 0) for (x, y) in SPREADER_HOLES]       # M3 x 8 up into the spreader's tapped holes
    holes += [(x, y, M3_CLEAR, 0) for (x, y) in PLINTH_BOLTS]
    holes += [(x, y, M3_INSERT, 0) for (x, y) in ARCH_BOLTS + PACK_SCREWS + WING_BOLTS]
    holes += [(x, y, M3_INSERT, 0) for s in POD_BOLTS.values() for (x, y) in s]
    holes += [(x, y, M3_CLEAR, 0) for (x, y) in JOINT_BOLTS]
    for (x, y, dia, ztop) in holes:
        d = d.cut(cylz(x, y, -DT - 0.5, ztop + 0.5, dia))
    # zip-tie slots along both edges
    for x in (-180, -60, 40, 110):
        for sy in (1, -1):
            d = d.cut(box(x - 2, x + 2, sy * 84 - 3, sy * 84 + 3, -DT - 1, 1))
    return d


def split_deck(d):
    """Three prints (each fits a 250 x 250 bed), butt-jointed at JOINTS and bolted to 3 mm splice
    plates underneath. The deck prints top face down, so its top has no features at all."""
    j0, j1 = P['JOINTS']
    big = 1000
    rear = d.intersect(box(-big, j0, -big, big, -big, big))
    mid = d.intersect(box(j0, j1, -big, big, -big, big))
    front = d.intersect(box(j1, big, -big, big, -big, big))
    return rear, mid, front


def splice_plate(jx, y0, y1):
    p = box(jx - P['SPLICE_L'] / 2, jx + P['SPLICE_L'] / 2, y0, y1, -DT - P['SPLICE_T'], -DT).edges('|Z').fillet(3)
    for (x, y) in JOINT_BOLTS:
        if abs(x - jx) < P['SPLICE_L'] and y0 < y < y1:
            p = p.cut(cylz(x, y, -DT - P['SPLICE_T'] - 1, -DT + 1, M3_CLEAR))
    return p


# ----------------------------------------------------------------------------- lidar plinth + bumper

def lidar_plinth():
    xf = P['LIDAR_FRONT_X']; xr = xf - 70.0; t = P['PLINTH_T']
    p = box(xr, xf, -32, 32, 0, t).edges('|Z').fillet(4)
    # 1 mm locating pocket for the housing, open at the rear for the swivel unit
    p = p.cut(box(xf - 61.25, xf + 0.25, -30.25, 30.25, t - 1.0, t + 1))
    # lidar bottom screws, from below: M3 x 6 heads in 6.2 counterbores, 2.0 mm of thread engaged
    lx = xf - 61.0 + 16.79
    for sy in (1, -1):
        p = p.cut(cylz(lx, sy * 25.5, -1, t + 1, M3_CLEAR)).cut(cylz(lx, sy * 25.5, -1, t - 3.0 - 0.8, M3_HEAD))
    # inserts for the four bolts that come up through the bumper flange and the deck
    for (x, y) in PLINTH_BOLTS:
        p = p.cut(cylz(x, y, -1, t - 1.0, M3_INSERT))
    # weight relief under the lidar
    p = p.cut(box(xf - 50, xf - 12, -14, 14, -1, t - 2.0))
    return p


def bumper():
    xf = P['LIDAR_FRONT_X']
    flange = box(xf - 38, xf, -40, 40, -DT - 5, -DT)
    for (x, y) in PLINTH_BOLTS:
        flange = flange.cut(cylz(x, y, -30, 1, M3_CLEAR)).cut(cylz(x, y, -30, -DT - 3.0, M3_HEAD + 0.4))
    zb, zt = -30.0, 44.0
    face = (cq.Workplane('XY').moveTo(xf + 14, -62).threePointArc((xf + 24, 0), (xf + 14, 62))
            .lineTo(xf + 6, 62).threePointArc((xf + 16, 0), (xf + 6, -62)).close()
            .extrude(zt - zb).translate((0, 0, zb)))
    arms = []
    for sy in (1, -1):
        pts = [(xf - 6, sy * 34), (xf + 2, sy * 34), (xf + 14, sy * 58), (xf + 8, sy * 62), (xf - 6, sy * 42)]
        arms.append(extrude_poly(pts, zb, -DT))
    web = box(xf - 4, xf + 12, -40, 40, zb, zb + 8)
    b = union(flange, face, *arms, web)
    # lightening windows in the face
    for y in (-38, -13, 13, 38):
        b = b.cut(box(xf + 2, xf + 30, y - 7, y + 7, zb + 16, zt - 12))
    return b


# ----------------------------------------------------------------------------- camera arch + cradle
ARCH_TOP = None


def camera_arch(lidar_top):
    global ARCH_TOP
    z_bar0 = lidar_top + 4.0
    z_bar1 = z_bar0 + 8.0
    ARCH_TOP = z_bar1
    x0, x1 = ARCH_X
    legs = []
    for sy in (1, -1):
        foot = box(x0 - 10, x1 + 10, sy * ARCH_Y - 9, sy * ARCH_Y + 9, 0, 4).edges('|Z').fillet(3)
        leg = box(x0, x1, sy * ARCH_Y - 6, sy * ARCH_Y + 6, 0, z_bar1)
        gus = extrude_poly([(x0 - 9, sy * ARCH_Y - 3), (x0, sy * ARCH_Y - 3), (x0, sy * ARCH_Y + 3), (x0 - 9, sy * ARCH_Y + 3)], 4, 4.01)
        legs += [foot, leg]
        # triangular gussets front and back of each leg (in the xz plane)
        for sx, xe in ((-1, x0), (1, x1)):
            g = (cq.Workplane('XZ').polyline([(xe, 4), (xe + sx * 9, 4), (xe, 34)]).close()
                 .extrude(6).translate((0, sy * ARCH_Y + 3, 0)))
            legs.append(g)
    bar = box(x0, x1, -ARCH_Y - 6, ARCH_Y + 6, z_bar0, z_bar1)
    tongue = box(x0, P['LIDAR_FRONT_X'] - 32, -17, 17, z_bar0, z_bar1)
    a = union(*legs, bar, tongue)
    for (x, y) in ARCH_BOLTS:
        a = a.cut(cylz(x, y, -1, 5, M3_CLEAR))
    # cradle screws: two M3 inserts in the tongue
    for x in (P['LIDAR_FRONT_X'] - 58, P['LIDAR_FRONT_X'] - 42):
        a = a.cut(cylz(x, 0, z_bar1 - 6, z_bar1 + 1, M3_INSERT))
    # cable clip hole on the bar (zip tie)
    a = a.cut(box(x0 + 3, x1 - 3, -3, 3, z_bar0 - 1, z_bar1 + 1))
    return a


def camera_cradle(pitch_deg=None):
    """Plate the Triton bolts to (4 corner M3, slotted +-1.5 because the hole pitch is an
    estimate), itself bolted to the arch tongue. pitch_deg < 0 tips the camera down."""
    pitch = P['CAM_PITCH'] if pitch_deg is None else pitch_deg
    x_face = P['LIDAR_FRONT_X'] - P['CAM_LENS_L']        # C-mount face so the lens ends at the nose
    x0 = x_face - 45.0
    zb = ARCH_TOP
    base_h = 4.0 + 44.0 * math.tan(math.radians(abs(pitch)))
    c = box(x0 + 1, x_face - 1, -17, 17, zb, zb + 4.0 + base_h)
    # tilt: cut the top as a plane through the pivot at the front, then camera sits on it
    if abs(pitch) > 0.01:
        cutter = box(x0 - 20, x_face + 20, -30, 30, 0, 60).translate((0, 0, zb + 4.0))
        cutter = cutter.rotate((x_face - 1, 0, zb + 4.0), (x_face - 1, 1, zb + 4.0), -pitch)
        c = c.cut(cutter)
    else:
        c = box(x0 + 1, x_face - 1, -17, 17, zb, zb + 4.0)
    for x in (P['LIDAR_FRONT_X'] - 58, P['LIDAR_FRONT_X'] - 42):
        c = c.cut(cylz(x, 0, zb - 1, zb + 20, M3_CLEAR))
    px, py = P['CAM_HOLE_PITCH']
    cx = x_face - 22.5
    for sx in (1, -1):
        for sy in (1, -1):
            slot = box(cx + sx * px / 2 - 1.7 - 1.5, cx + sx * px / 2 + 1.7 + 1.5, sy * py / 2 - 1.7, sy * py / 2 + 1.7, zb - 1, zb + 30)
            c = c.cut(slot)
    return c


# ----------------------------------------------------------------------------- side pods

def side_pod(sy):
    x0, x1, yi, yo, h, t = POD['x0'], POD['x1'], POD['y_in'], POD['y_out'], POD['h'], POD['t']
    prof = [(yi, 0), (yo, 0), (yo, h - 10), (yo - 5, h - 3), (yi + 4, h), (yi, h)]
    inner = [(yi + t, -1), (yo - t, -1), (yo - t, h - 10 - 1), (yo - 5 - 1, h - 3 - t), (yi + 4, h - t), (yi + t, h - t)]
    outer_s = cq.Workplane('YZ').polyline(prof).close().extrude(x1 - x0).translate((x0, 0, 0))
    inner_s = cq.Workplane('YZ').polyline(inner).close().extrude(x1 - x0 - 2 * t).translate((x0 + t, 0, 0))
    pod = outer_s.cut(inner_s)
    # rounded nose and tail in plan
    pod = pod.edges('|Z').fillet(6)
    # bolting flange on the inboard side
    if sy > 0:
        fl = box(x0 + 4, x1 - 4, yi - 7, yi + 0.01, 0, 3)
    else:
        fl = union(box(x0 + 4, -64, yi - 7, yi + 0.01, 0, 3), box(84, x1 - 4, yi - 7, yi + 0.01, 0, 3))
    pod = pod.union(fl)
    for (x, y) in [(x, abs(y)) for (x, y) in POD_BOLTS[1 if sy > 0 else -1]]:
        pod = pod.cut(cylz(x, y, -1, 4, M3_CLEAR))
    # vents on the outer face
    for i in range(7):
        xv = x0 + 30 + i * 22
        pod = pod.cut(box(xv, xv + 12, yo - 5, yo + 1, 10, h - 20))
    if sy < 0:
        # fan window on the inner wall, fan behind it (40 mm fan, blows inboard over the ESC heatsink)
        f0, f1 = FAN_X
        pod = pod.cut(box(f0 + 1, f1 - 1, yi - 1, yi + t + 1, 2, 40))
        for (fx, fz) in ((f0 + 4, 5), (f1 - 4, 5), (f0 + 4, 37), (f1 - 4, 37)):     # 32 mm hole pitch
            pod = pod.cut(cyl((fx, yi - 1, fz), 3.4, t + 12, (0, 1, 0)))
        # the camera's RJ45 plug and its boot run straight out through the pod (the jack opens 2 mm from
        # the inner wall): a slot open at the top, through both walls
        n0, n1 = CAM_PLUG_NOTCH['x']
        pod = pod.cut(box(n0, n1, yi - 1, yo + 1, CAM_PLUG_NOTCH['z0'], h + 5))
        # zip-tie slots in pairs across the top, to hold the camera cable along the pod
        for xs in POD_TIE_SLOTS_X:
            for ys in (yi + 5.5, yo - 5.0):
                pod = pod.cut(box(xs - 2.75, xs + 2.75, ys - 1.1, ys + 1.1, h - 8, h + 5))
    if sy < 0:
        pod = pod.mirror('XZ')
    return pod


# ----------------------------------------------------------------------------- rear wing

def wing_struts():
    s = []
    for sy in (1, -1):
        foot = box(WING['strut_x'][0] - 10, WING['strut_x'][1] + 10, sy * WING['strut_y'] - 7, sy * WING['strut_y'] + 7, 0, 4).edges('|Z').fillet(3)
        post = box(WING['strut_x'][0], WING['strut_x'][1], sy * WING['strut_y'] - 4, sy * WING['strut_y'] + 4, 0, WING['z'])
        tab = box(WING['chord'][0] + 6, WING['chord'][1] - 6, sy * WING['strut_y'] - 4, sy * WING['strut_y'] + 4, WING['z'] - 8, WING['z'])
        st = union(foot, post, tab)
        for (x, y) in [b for b in WING_BOLTS if (b[1] > 0) == (sy > 0)]:
            st = st.cut(cylz(x, y, -1, 5, M3_CLEAR))
        for x in (WING['chord'][0] + 10, WING['chord'][1] - 10):
            st = st.cut(cylz(x, sy * WING['strut_y'], WING['z'] - 9, WING['z'] + 1, M3_CLEAR))
        s.append(st)
    return s


def wing_blade():
    c0, c1 = WING['chord']; span = WING['span']; z = WING['z']
    blade = box(c0, c1, -span, span, z, z + 5).edges('|Y').fillet(2.4)
    ends = [box(c0 - 4, c1 + 6, sy * span - (3 if sy > 0 else 0), sy * span + (0 if sy > 0 else 3), z - 34, z + 12).edges('|Y').fillet(6) for sy in (1, -1)]
    b = union(blade, *ends)
    for sy in (1, -1):
        for x in (c0 + 10, c1 - 10):
            b = b.cut(cylz(x, sy * WING['strut_y'], z - 1, z + 6, M3_INSERT))
    return b


# ----------------------------------------------------------------------------- pack parts

def pack_box():
    ob = box(PX0, PX1, PY0, PY1, PACK_BOTTOM, PACK_TOP).edges('|Z').fillet(3)
    ib = box(PX0 + PACK_WALL, PX1 - PACK_WALL, PY0 + PACK_WALL, PY1 - PACK_WALL, PACK_BOTTOM + PACK_FLOOR, PACK_TOP + 1)
    b = ob.cut(ib)
    # flange on three sides (the right side stays clear for the drive board bosses)
    fl = union(box(PX0 - 7, PX0 + 0.01, PY0, PY1, 0, PACK_TOP), box(PX1 - 0.01, PX1 + 7, PY0, PY1, 0, PACK_TOP),
               box(PX0 - 7, PX1 + 7, PY1 - 0.01, PY1 + 7, 0, PACK_TOP))
    b = b.union(fl)
    for (x, y) in PACK_SCREWS:
        b = b.cut(cylz(x, y, -1, PACK_TOP + 1, M3_CLEAR))
    # grooves for the two bottom balance taps (B1, B3) on the inside of the right wall
    for x in (PX0 + 30, PX1 - 30):
        b = b.cut(box(x - 1.5, x + 1.5, PY0 + PACK_WALL - 1.0, PY0 + PACK_WALL + 0.01, PACK_BOTTOM + PACK_FLOOR, PACK_TOP + 1))
    # drain / inspection holes in the floor
    for i in range(3):
        b = b.cut(cylz(PX0 + 25 + 40 * i, (PY0 + PY1) / 2, PACK_BOTTOM - 1, PACK_BOTTOM + PACK_FLOOR + 1, 6))
    return b


def pack_lid():
    l = union(box(PX0 - 7, PX1 + 7, PY0, PY1 + 7, PACK_TOP, PACK_TOP + PACK_LID_T).edges('|Z').fillet(3))
    for (x, y) in PACK_SCREWS:
        l = l.cut(cylz(x, y, PACK_TOP - 1, PACK_TOP + 5, M3_CLEAR))
    # lead exits at the right edge: pack+ (front end, G4), sense lead (middle), pack- (rear end, G1)
    for (x, w) in ((PX1 - 14, 10), (0.0, 7), (PX0 + 14, 10)):
        l = l.cut(box(x - w / 2, x + w / 2, PY0 - 1, PY0 + 9, PACK_TOP - 1, PACK_TOP + PACK_LID_T + 1))
    # pressure ribs onto the foam pad over the top strips
    for i in range(1, 6):
        x = PX0 + 2 + P['CELL_PITCH'] * i
        l = l.union(box(x - 1, x + 1, PY0 + PACK_WALL + 2, PY1 - PACK_WALL - 2, PACK_TOP - 0.8, PACK_TOP))
    return l


def cell_holder():
    """One of two identical 2 x 6 holders (top and bottom of the block)."""
    x0 = PX0 + PACK_WALL + 0.5; y0 = PY0 + PACK_WALL + 0.5
    h = box(x0, x0 + 6 * P['CELL_PITCH'], y0, y0 + 2 * P['CELL_PITCH'], 0, P['HOLDER_T']).edges('|Z').fillet(2)
    for i in range(6):
        for j in range(2):
            cx = x0 + P['CELL_PITCH'] * (i + 0.5); cy = y0 + P['CELL_PITCH'] * (j + 0.5)
            h = h.cut(cylz(cx, cy, P['HOLDER_T'] - P['HOLDER_POCKET'], P['HOLDER_T'] + 1, P['CELL_D'] + 0.35))
            h = h.cut(cylz(cx, cy, -1, P['HOLDER_T'] + 1, 14.0))
    return h


def post_washer():
    w = box(-15, 15, -15, 15, 0, 3).edges('|Z').fillet(4)
    return w.cut(cylz(0, 0, -1, 4, P['POST_D'] + 0.6))


def fit_coupon(deck, which):
    tx = P['FRONT_TOWER_X'] if which == 'front' else P['REAR_TOWER_X']
    px = P['FRONT_POST'][0] if which == 'front' else P['REAR_POST'][0]
    x0, x1 = min(tx, px) - 22, max(tx, px) + 22
    return deck.intersect(box(x0, x1, -66, 66, -60, 20))


# ----------------------------------------------------------------------------- build + checks

def build():
    S = chassis()
    L, scan_z, lidar_top = tim561()
    B = boards()
    arch = camera_arch(lidar_top)
    cam = triton(ARCH_TOP + 4.0, P['LIDAR_FRONT_X'] - P['CAM_LENS_L'])
    deck = deck_full()
    rear, mid, front = split_deck(deck)
    parts = dict(
        deck_rear=rear, deck_mid=mid, deck_front=front,
        splice_rear_right=splice_plate(P['JOINTS'][0], *SPLICE_Y[0]), splice_rear_left=splice_plate(P['JOINTS'][0], *SPLICE_Y[1]),
        splice_front_right=splice_plate(P['JOINTS'][1], *SPLICE_Y[0]), splice_front_left=splice_plate(P['JOINTS'][1], *SPLICE_Y[1]),
        lidar_plinth=lidar_plinth(), bumper=bumper(), camera_arch=arch, camera_cradle=camera_cradle(),
        side_pod_left=side_pod(1), side_pod_right=side_pod(-1),
        wing_strut_left=wing_struts()[0], wing_strut_right=wing_struts()[1], wing_blade=wing_blade(),
        pack_box=pack_box(), pack_lid=pack_lid(),
    )
    comps = dict(L)
    comps.update(cam)
    comps.update(B)
    comps['cells_4s3p'] = pack_cells()
    holder_b = cell_holder().translate((0, 0, PACK_BOTTOM + PACK_FLOOR + 0.6))
    holder_t = cell_holder().mirror('XY').translate((0, 0, PACK_CELL_Z0 + P['CELL_L'] + (P['HOLDER_T'] - P['HOLDER_POCKET'])))
    parts['cell_holder_bottom'] = holder_b
    parts['cell_holder_top'] = holder_t
    extras = dict(post_washer=post_washer(), fit_coupon_front=fit_coupon(deck, 'front'), fit_coupon_rear=fit_coupon(deck, 'rear'),
                  camera_cradle_down5=camera_cradle(-5.0), camera_cradle_down10=camera_cradle(-10.0))
    return S, comps, parts, extras, dict(scan_z=scan_z, lidar_top=lidar_top, arch_top=ARCH_TOP)


def bb_overlap(a, b, pad=0.0):
    A = a.val().BoundingBox(); Bb = b.val().BoundingBox()
    return not (A.xmax < Bb.xmin - pad or Bb.xmax < A.xmin - pad or A.ymax < Bb.ymin - pad or Bb.ymax < A.ymin - pad
                or A.zmax < Bb.zmin - pad or Bb.zmax < A.zmin - pad)


def inter(a, b):
    if not bb_overlap(a, b):
        return 0.0
    try:
        return volume(a.intersect(b))
    except Exception as e:
        return float('nan')


def checks(S, comps, parts, info):
    rows = []
    # expected contacts that are not interference (cells in holders, pack in its bay, towers in slots)
    skip = {('pack_box', 'tub'), ('cell_holder_bottom', 'tub'), ('cell_holder_top', 'tub'), ('cells_4s3p', 'tub'),
}
    allp = list(parts.items())
    for (na, a), (nb, b) in itertools.combinations(allp, 2):
        v = inter(a, b)
        if v > 0.5:
            rows.append((na, nb, round(v, 1)))
    for na, a in allp:
        for nb, b in list(comps.items()) + list(S.items()):
            if (na, nb) in skip:
                continue
            v = inter(a, b)
            if v > 0.5:
                rows.append((na, nb, round(v, 1)))
    for na, a in comps.items():
        for nb, b in S.items():
            if (na, nb) in skip:
                continue
            v = inter(a, b)
            if v > 0.5:
                rows.append((na, nb, round(v, 1)))
    # the bought parts against each other: tall parts between the two boards, the sensors and their plugs.
    # 'drive_top_parts' is a 3 mm blanket over the whole drive board, so the parts standing on the drive
    # board are expected inside it; a sensor and its own plug touch by design.
    on_drive = {'drive_bulk_caps', 'usb_c_and_button', 'stack_header', 'brain_standoffs_20mm', 'drive_standoffs_7mm', 'drive_pcb'}
    touch = {frozenset(p) for p in (('lidar', 'lidar_connectors'), ('camera', 'camera_plug'), ('drive_pcb', 'drive_fets_bottom'),
                                     ('drive_pcb', 'drive_standoffs_7mm'), ('brain_pcb', 'brain_standoffs_20mm'))}
    for (na, a), (nb, b) in itertools.combinations(sorted(comps.items()), 2):
        pair = frozenset((na, nb))
        if pair in touch or ('drive_top_parts' in pair and (pair - {'drive_top_parts'}) <= on_drive):
            continue
        v = inter(a, b)
        if v > 0.5:
            rows.append((na, nb, round(v, 1)))
    # the one tight vertical fit in the stack: the NVMe SSD under the brain board over the drive board's bulk caps
    nv, bc = comps['nvme_2280'].val().BoundingBox(), comps['drive_bulk_caps'].val().BoundingBox()
    info['nvme_over_bulk_caps_mm'] = round(nv.zmin - bc.zmax, 2)
    # pack footprint inside the battery bay
    bx0, bx1, by0, by1 = P['BATT_BAY']
    pack_in_bay = (PX0 >= bx0 and PX1 <= bx1 and PY0 >= by0 and PY1 <= by1)
    # lidar scan plane: what is within +-6 mm of it and inside the 270 degree field of view
    zc = info['scan_z']
    lx = P['LIDAR_FRONT_X'] - 30.5
    slab = box(-400, 400, -300, 300, zc - 6, zc + 6)
    fov_hits = []
    for name, s in list(parts.items()) + [(k, v) for k, v in comps.items() if not k.startswith('lidar')]:
        if not bb_overlap(s, slab):
            continue
        try:
            sec = s.intersect(slab)
            if volume(sec) < 0.1:
                continue
            bbx = sec.val().BoundingBox()
            # worst-case bearing of the section's corners from the lidar axis (0 = dead ahead)
            bearings = [abs(math.degrees(math.atan2(y, x - lx))) for x in (bbx.xmin, bbx.xmax) for y in (bbx.ymin, bbx.ymax)]
            fov_hits.append((name, round(min(bearings), 1), 'inside blind sector' if min(bearings) >= 135 else 'IN VIEW'))
        except Exception:
            pass
    return rows, pack_in_bay, fov_hits


def export(parts, comps, S, extras):
    import cadquery as cq
    res = {}
    for name, p in extras.items():
        q = p.rotate((0, 0, 0), (1, 0, 0), 180) if name.startswith('fit_coupon') else p   # top face down, like the deck
        bb = q.val().BoundingBox()
        q = q.translate((-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))
        cq.exporters.export(p, os.path.join(OUT, 'step', f'{name}.step'))
        cq.exporters.export(q, os.path.join(OUT, 'stl', f'{name}.stl'), tolerance=0.05, angularTolerance=0.15)
    orient = dict(deck_front=((1, 0, 0), 180), deck_mid=((1, 0, 0), 180), deck_rear=((1, 0, 0), 180), bumper=(None, 0), lidar_plinth=(None, 0),
                  camera_arch=(None, 0), camera_cradle=(None, 0), side_pod_left=((1, 0, 0), 180), side_pod_right=((1, 0, 0), 180),
                  wing_strut_left=((1, 0, 0), 90), wing_strut_right=((1, 0, 0), -90), wing_blade=((1, 0, 0), 180),
                  pack_box=((1, 0, 0), 180), pack_lid=((1, 0, 0), 180), cell_holder_bottom=(None, 0), cell_holder_top=((1, 0, 0), 180))
    for name, p in parts.items():
        ax, ang = orient.get(name, (None, 0))
        q = p
        if ax:
            q = q.rotate((0, 0, 0), ax, ang)
        bb = q.val().BoundingBox()
        q = q.translate((-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))
        cq.exporters.export(p, os.path.join(OUT, 'step', f'{name}.step'))
        cq.exporters.export(q, os.path.join(OUT, 'stl', f'{name}.stl'), tolerance=0.05, angularTolerance=0.15)
        bb = q.val().BoundingBox()
        v = volume(p) / 1000.0
        res[name] = dict(bed_xyz=[round(bb.xlen, 1), round(bb.ylen, 1), round(bb.zlen, 1)], volume_cm3=round(v, 1),
                         mass_g_solid_petgcf=round(v * 1.30, 0), fits_250_bed=bool(bb.xlen <= 250 and bb.ylen <= 250 and bb.zlen <= 250),
                         solids=n_solids(p))
    # assembly STEP: parts + components (+ chassis keep-outs in a separate file)
    asm = cq.Assembly(name='atlas_car_v2')
    for name, p in parts.items():
        asm.add(p, name=name, color=cq.Color(0.15, 0.15, 0.17))
    for name, p in comps.items():
        asm.add(p, name=name, color=cq.Color(0.2, 0.45, 0.9))
    asm.save(os.path.join(OUT, 'step', 'assembly_kit_and_components.step'))
    ch = cq.Assembly(name='slash4x4_keepouts')
    for name, p in S.items():
        ch.add(p, name=name, color=cq.Color(0.3, 0.7, 0.3))
    ch.save(os.path.join(OUT, 'step', 'chassis_keepouts_estimate.step'))
    return res


def renders(parts, comps, S):
    sys.path.insert(0, HERE)
    from render import render
    grey = (0.22, 0.22, 0.25); blue = (0.25, 0.5, 0.95); green = (0.45, 0.75, 0.45); orange = (0.95, 0.55, 0.2)
    items = [(p, grey) for p in parts.values()] + [(c, orange if k.startswith(('lidar', 'camera')) else blue) for k, c in comps.items()]
    chassis_items = [(S[k], green) for k in ('tub', 'gearbox', 'motor', 'steering_servo', 'front_tower', 'rear_tower',
                                             'front_tyre_L', 'front_tyre_R', 'rear_tyre_L', 'rear_tyre_R')]
    render(items, os.path.join(OUT, 'renders', 'kit_iso.png'), views=[(24, -58), (24, 122)], title='Atlas car v2 kit: printed parts (dark), boards and pack (blue), sensors (orange)')
    render(items + chassis_items, os.path.join(OUT, 'renders', 'kit_on_chassis.png'), views=[(18, -60)], title='on the Slash 4x4 keep-out model (green, estimated)')
    render(items, os.path.join(OUT, 'renders', 'kit_top.png'), views=[(89.9, -90)], title='top view, nose to the right', zoom=1.25)
    render(items + chassis_items, os.path.join(OUT, 'renders', 'kit_side.png'), views=[(0, -90)], title='right side view', zoom=1.25)
    render([(p, grey) for k, p in parts.items() if k.startswith(('pack', 'cell'))] + [(comps['cells_4s3p'], blue)],
           os.path.join(OUT, 'renders', 'pack.png'), views=[(25, -60)], title='4S3P pack: box, holders, lid, 12 cells')


if __name__ == '__main__':
    S, comps, parts, extras, info = build()
    rows, pack_in_bay, fov = checks(S, comps, parts, info)
    res = export(parts, comps, S, extras)
    spreader_dxf(os.path.join(OUT, 'dxf', 'heat_spreader.dxf'))
    renders(parts, comps, S)
    rep = dict(params=P, z_rim=Z_RIM, tower_top=TOWER_TOP, scan_plane_z=round(info['scan_z'], 2), lidar_top_z=round(info['lidar_top'], 2),
               camera_axis_z=round(info['arch_top'] + 4 + 14.5, 2), pack_box_z=[round(PACK_BOTTOM, 2), PACK_TOP], pack_in_bay=pack_in_bay,
               nvme_over_bulk_caps_mm=info['nvme_over_bulk_caps_mm'], interference=rows, lidar_plane=fov, parts=res)
    with open(os.path.join(OUT, 'kit_report.json'), 'w') as f:
        json.dump(rep, f, indent=1, default=str)
    print(json.dumps({k: rep[k] for k in ('scan_plane_z', 'lidar_top_z', 'camera_axis_z', 'pack_box_z', 'pack_in_bay', 'nvme_over_bulk_caps_mm', 'interference', 'lidar_plane')}, indent=1))
    for k, v in res.items():
        print(f'{k:22s} bed {v["bed_xyz"]}  {v["volume_cm3"]:7.1f} cm3  ~{v["mass_g_solid_petgcf"]:.0f} g solid  fits250={v["fits_250_bed"]}  solids={v["solids"]}')
