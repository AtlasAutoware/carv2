"""Atlas car v2 printed kit for the Traxxas Slash 4x4 (6822 chassis), rev B.

    python3 kit.py            build every part, run the fit checks, export STEP/STL, render

Frame (same as the car-1 mount set): +x forward, +y car left, +z up. Origin at the deck
centre, deck top at z = 0. Every chassis number below comes from the car-1/new-car keep-out
model in atlasstuff/power_board_v2/case/mounts_src/newcar/board_layout_newcar.py and is an
ESTIMATE unless marked; docs/MEASURE_FIRST.md lists what to measure before printing.
Environment variables of the same name override any number in P (e.g. UNDER_CLEARANCE=42,
POWER_L=130, BMS_MOUNT=flat, DEVKIT_HOLES='[[7,10.5],[93,10.5],[7,68.5],[93,68.5]]').

Rev B (2026-10-24, NOTES_REVB.md): the rev A drive and brain boards are gone. In their place:
  - ATLAS-PWR-1, a 2-layer through-hole power board (up to 150 x 84 mm) on 7 mm deck standoffs;
  - the NVIDIA Orin Nano dev-kit carrier on a printed tray (devkit_tray) that stands on the power
    board's holes with 25 mm standoffs;
  - the Flipsky FSESC in a printed cradle (esc_cradle) in the ESC bay beside the motor, cooled by the
    right side pod's fan;
  - the JBD BMS with the pack, standing on edge in a printed holder (bms_fence) on the pack lid.
"""
import os, sys, json, math, itertools
import cadquery as cq
from shapely.geometry import box as sbox, Point, Polygon
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
for d in ('stl', 'step', 'renders'):
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
    # power board ATLAS-PWR-1 (scratchpad PHASE2.md, fixed facts): board-local X 0..L forward, Y 0..84 toward
    # car left; car (x, y) = (X + POWER_X0, Y + POWER_Y0). L is the agent-D layout's final length.
    POWER_L=130.0, POWER_W=84.0, POWER_X0=-32.0, POWER_Y0=-68.0, POWER_Z=7.0, PCB_T=1.6,
    POWER_LOW_H=23.0,              # part height limit under the dev-kit tray (board-local X 20..120)
    POWER_TALL_H=35.0,             # limit in the rear strip (X 0..20) and the front strip (X > 120)
    STACK_H=25.0,                  # power PCB top to the tray's underside: M3 x 25 standoffs
    TRAY_T=3.0,
    # NVIDIA Jetson Orin Nano dev-kit carrier: 100.00 x 79.00 mm, PCB 1.57 mm, top parts 16.70 max, bottom
    # 4.30 max (carrier spec Fig. 4-1). Dev-kit-local X 0..100 along car +x from its rear edge, Y 0..79 toward
    # car left; the I/O edge (DC jack, RJ45, 4 x USB-A, USB-C) is Y = 79, facing the pack.
    DEVKIT=(-12.0, 88.0, -63.0, 16.0), DEVKIT_PCB_T=1.57,
    # UNMEASURED (MEASURE_FIRST item 17). NVIDIA does not publish the hole positions as text; they are in the
    # login-only carrier design files and dev-kit STEP model. Placeholder: an 86 x 58 mm rectangle centred on
    # the board, the pattern recalled (not verified) for the older Jetson Nano / Xavier NX dev-kit carriers.
    DEVKIT_HOLES=((7.0, 10.5), (93.0, 10.5), (7.0, 68.5), (93.0, 68.5)),
    DEVKIT_PILOT_D=2.2,            # M2.5 thread-forming screw into the boss (2.6 for M3)
    DEVKIT_BOSS_D=6.0,
    DEVKIT_BOSS_H=7.0,             # tray top to carrier underside: DEVKIT_BOTTOM_H + 1 mm
    DEVKIT_BOTTOM_H=6.0,           # NVMe + Wi-Fi card + screws under the carrier (measure, item 19)
    DEVKIT_IO_H=16.7,
    # I/O connectors along the Y = 79 edge: (name, X0, X1, height, depth into the board). ESTIMATES (item 20)
    DEVKIT_IO=(('dc_jack', 2.0, 11.0, 11.0, 14.0), ('displayport', 13.0, 31.0, 13.0, 16.0),
               ('usb_a_1', 34.0, 49.0, 16.0, 17.5), ('usb_a_2', 52.0, 67.0, 16.0, 17.5),
               ('rj45', 69.0, 85.0, 13.5, 21.0), ('usb_c', 88.0, 97.0, 3.5, 7.5)),
    DEVKIT_J12=(6.0, 57.0, 1.0, 6.0),       # 2 x 20 header, dev-kit-local X0, X1, Y0, Y1 (ESTIMATE, item 20)
    DEVKIT_J14=(62.0, 92.5, 0.0, 6.0),      # 1 x 12 right-angle header, pins out of the Y = 0 edge (ESTIMATE)
    JETSON_XY=(10.0, 88.0, 8.0, 56.0),      # module + heatsink + fan footprint, dev-kit-local (ESTIMATE, item 18)
    JETSON_SINK_H=32.0,                     # carrier top to fan top (measure, item 18)
    CANOPY_GAP=8.0,                         # minimum fan top to canopy underside (checked)
    # ESC bay beside the motor and the FSESC in its cradle
    ESC_BAY=(-113.0, -35.0, -68.0, -6.0, 35.0),
    ESC_CASE=(71.0, 43.0, 22.7),   # PLACEHOLDER, UNMEASURED: Mini FSESC 6.7 Pro bare 67 x 39 x 18.7 + 2 mm a side (item 21)
    ESC_C=(-74.0, -34.0),          # case centre in plan, long axis along x, motor end toward the rear
    # phase + hall opening in the deck. C proposed x -94..-82, but that sits over the rear-right splice plate
    # (x -95..-65) and the joint bolt at (-90, -60); this one is between the rear post slot (ends -115.7) and the
    # cross rib (x -99..-96), right under the ESC's motor end
    PHASE_OPENING=(-112.0, -101.0, -70.0, -46.0),
    ESC_OUT_Y=66.0,                # board-local Y of the ESC output XT60PW on the rear edge (X = 0), agent D
    # JBD 4S 100 A BMS (PHASE2 decision 2): 160 x 105 x 10 mm. 'edge' = standing on its long edge in bms_fence on
    # the pack lid's outboard edge; 'flat' = lying on a tray on the lid (only for a BMS that fits the 138 x 51 lid)
    BMS=(160.0, 105.0, 10.0), BMS_MOUNT='edge',
    # right side pod: 40 mm fan (x range), and the windows through both pod walls for the plugs and the button at
    # the power board's Y = 0 edge: (name, car x centre, width, z0, z1). Agent D reports the real positions.
    FAN_X=(-94.0, -54.0),
    POD_WINDOWS=(('charge_usbc', 68.0, 16.0, 10.0, 25.0), ('debug_usbc', 88.0, 16.0, 10.0, 25.0),
                 ('button', -20.0, 12.0, 11.0, 23.0)),
    # sensors
    LIDAR_FRONT_X=238.0, PLINTH_T=6.0,
    CAM_LENS_D=31.0, CAM_LENS_L=30.5, CAM_M12_L=48.0, CAM_PITCH=0.0,   # Kowa LM4NCL 3.5 mm: 31 x 30.5 mm, 60 g (machinevisiondirect.com)
    CAM_HOLE_PITCH=(20.0, 20.0),   # ESTIMATE: 4 corner M3 holes on the Triton bottom, confirm on the camera
    USB_ETH=(50.0, 22.0, 15.0),    # lidar USB-Ethernet dongle body L x W x H (ESTIMATE; ZimaSpace RTL8153, 180 mm cable)
    # FET switch: agent D's layout (boards/power/layout.py, 24 Oct) puts the 40 x 15 x 3 mm heatsink bar, live at BAT+, on
    # the three IRFB7430 tabs at board-local X 10.54..50.54, Y 62.92..65.92, with the FET bodies just south of it. Live
    # metal reaches about 20 mm above the board (TO-220 tab tops with about 3 mm of lead; ESTIMATE). (X0, X1, Y0, Y1, h)
    FET_BAR=(10.54, 50.54, 57.4, 65.92, 20.0),
    # insulating shield: 3 mm cast acrylic hung under the tray where the tray's CF rails pass over the bar. FET_SHIELD=0
    # leaves it out. Parts under it must stay at FET_SHIELD_MAX_H or below (1 mm under the shield).
    FET_SHIELD=1, FET_SHIELD_XY=(20.0, 54.0, 49.0, 72.0), FET_SHIELD_SCREWS=((22.5, 51.0), (25.5, 58.0)),
    FET_SHIELD_MAX_H=21.0,
    # laser-cut sheet parts (school CO2 laser: acrylic, plywood, MDF up to about 6 mm). DXF and SVG profiles always go to
    # out/laser/. SHEET_PARTS picks which printed parts the model replaces with the sheet versions for the checks:
    # 'none', 'all', or a comma list of tray, bms, canopy, splices. SHEET_T is the MEASURED sheet thickness.
    SHEET_T=3.0, SHEET_PARTS='none',
    TAB_L=10.0, SLOT_CLEAR_W=0.1, SLOT_CLEAR_L=0.2,   # tab/slot rule: slot = (SHEET_T + 0.1) x (TAB_L + 0.2), drawn kerf-neutral
    LASER_HOLE_M3=3.2, LASER_HOLE_M25=2.7,
    CANOPY_POST_H=48.0,            # tray top to the canopy posts' tops: printed pillars, or M3 hex standoffs 40 + 8 mm
    CANOPY_SKIRT_H=10.0,           # sheet canopy: skirt depth under the top plate
)
for k, v in list(P.items()):
    if k in os.environ:
        raw = os.environ[k]
        if isinstance(v, str):
            P[k] = raw
        elif isinstance(v, (tuple, list)):
            P[k] = tuple(json.loads(raw))
        else:
            P[k] = type(v)(json.loads(raw))

OLD_PLATE_UNDERSIDE = -3.175
Z_RIM = OLD_PLATE_UNDERSIDE - P['UNDER_CLEARANCE']          # -48.175
Z_FLOOR = Z_RIM - P['TUB_DEPTH']                           # -72.175
TOWER_TOP = OLD_PLATE_UNDERSIDE - P['TOWER_TOP_BELOW_OLD_PLATE']   # -19.175
FRONT_AXLE = P['FRONT_TOWER_X'] + 10.0
REAR_AXLE = FRONT_AXLE - P['WHEELBASE']
DT = P['DECK_T']
M3_INSERT, M3_CLEAR, M3_HEAD = 4.0, 3.4, 6.2
M3_CSK = 6.72                    # ISO 10642 M3 countersunk head diameter

# ----------------------------------------------------------------------------- the rev B stack, derived
POWER = (P['POWER_X0'], P['POWER_X0'] + P['POWER_L'], P['POWER_Y0'], P['POWER_Y0'] + P['POWER_W'])
Z_POWER_TOP = P['POWER_Z'] + P['PCB_T']                     # 8.6
Z_TRAY0 = Z_POWER_TOP + P['STACK_H']                        # 33.6, tray underside
_sp = str(P['SHEET_PARTS']).strip().lower()
SHEET = {'tray', 'bms', 'canopy', 'splices'} if _sp == 'all' else ({w.strip() for w in _sp.split(',')} - {'', 'none'})
Z_TRAY1 = Z_TRAY0 + (P['SHEET_T'] if 'tray' in SHEET else P['TRAY_T'])   # 36.6, tray top
Z_DEVKIT0 = Z_TRAY1 + P['DEVKIT_BOSS_H']                    # 43.6, carrier underside
Z_DEVKIT1 = Z_DEVKIT0 + P['DEVKIT_PCB_T']                   # 45.17, carrier top
Z_SINK_TOP = Z_DEVKIT1 + P['JETSON_SINK_H']                 # 77.17, fan top
# every canopy post (printed pillar or bought standoff stack) ends CANOPY_POST_H above the tray top; the printed canopy
# has 1 mm pads under its posts, the laser one sits directly on them
Z_POST_TOP = Z_TRAY1 + P['CANOPY_POST_H']                   # 84.6
Z_CANOPY = Z_POST_TOP + (0.0 if 'canopy' in SHEET else 1.0) # 85.6, canopy underside (8.4 over the fan)


def pw(X, Y):
    """power-board-local (X, Y) -> car (x, y)"""
    return (X + POWER[0], Y + POWER[2])


def dk(X, Y):
    """dev-kit-local (X, Y) -> car (x, y)"""
    return (X + P['DEVKIT'][0], Y + P['DEVKIT'][2])


_PL, _PW = P['POWER_L'], P['POWER_W']
POWER_HOLES_LOCAL = [(4.0, 4.0), (4.0, 80.0), (75.0, 4.0), (75.0, 80.0), (_PL - 4.0, 4.0), (_PL - 4.0, 80.0)]
POWER_HOLES = [pw(*h) for h in POWER_HOLES_LOCAL]          # 7 mm deck standoffs below, 25 mm tray standoffs above
POWER_HOLE_KEEPOUT = 7.0
DEVKIT_HOLES_CAR = [dk(*h) for h in P['DEVKIT_HOLES']]
TRAY_RAIL = 8.0                  # width of the tray's rails and edge arms
ARM_BAND = 9.0                   # strip along the board's Y = 0 and Y = 84 edges under the tray arms (low parts only)
LOW_X = (20.0, 120.0)            # board-local X of the dev kit's shadow (PHASE2 height map)


def half_w(x):
    """Deck half-width: full width to TAPER_X, straight taper to the nose."""
    if x <= P['TAPER_X']:
        return P['HALF_W']
    t = (x - P['TAPER_X']) / (P['X_NOSE'] - P['TAPER_X'])
    return P['HALF_W'] + t * (P['NOSE_HALF_W'] - P['HALF_W'])


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


def csk_hole(x, y, z_top, depth):
    """M3 countersunk clearance hole from z_top down through `depth` mm"""
    h = cylz(x, y, z_top - depth - 1, z_top + 1, M3_CLEAR)
    k = (M3_CSK + 0.3 - M3_CLEAR) / 2
    return h.union(cone((x, y, z_top - k), M3_CLEAR, M3_CSK + 0.3, k + 0.01))


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


LIDAR_PLUG_END_X = P['LIDAR_FRONT_X'] - 61.0 - 17.37 - 45.0        # 114.63, where the M12 cables leave the plugs


def triton(cam_bottom_z, x_mount_face):
    """LUCID Triton TRI023S-CC: 29 x 29 x 45 mm without connectors and lens mount, 67 g,
    C-mount (edmundoptics.com/p/41817). Lens and M12 plug lengths are parameters. Rev B adds the
    8-pin M8 GPIO plug (LUCID GPIO-M8 cable, right angle 'Up' for Triton) that now powers the camera."""
    x0 = x_mount_face - 45.0
    body = box(x0, x_mount_face, -14.5, 14.5, cam_bottom_z, cam_bottom_z + 29)
    lens = cyl((x_mount_face, 0, cam_bottom_z + 14.5), P['CAM_LENS_D'], P['CAM_LENS_L'], (1, 0, 0))
    plug = cyl((x0, 6, cam_bottom_z + 14.5), 16, P['CAM_M12_L'], (-1, 0, 0))
    # M8 right-angle plug envelope at the rear face, beside the M12 (size ESTIMATE: 10 mm body, 16 mm out, cable up)
    m8 = box(x0 - 16.0, x0, -13.0, -3.0, cam_bottom_z + 4.0, cam_bottom_z + 30.0)
    return dict(camera=union(body, lens), camera_plug=plug, camera_m8_plug=m8)


def power_zones():
    """The power board's height map as board-local rectangles (name, X0, X1, Y0, Y1, max height). PHASE2: at most
    POWER_LOW_H under the tray (X 20..120), POWER_TALL_H in the rear strip (X 0..20) and the front strip (X > 120).
    The tray's edge arms run over the Y 0..9 and Y 75..84 bands of both strips to reach the corner standoffs, so those
    bands are low too, and so is Y 0..5 under the tray (its right rail)."""
    L, W = P['POWER_L'], P['POWER_W']
    lo, hi = P['POWER_LOW_H'], P['POWER_TALL_H']
    a, b = LOW_X[0], min(LOW_X[1], L)
    Z = [('low', a, b, 0.0, W, lo),
         ('tall_rear', 0.0, a, ARM_BAND, W - ARM_BAND, hi),
         ('low_rear_arm_r', 0.0, a, 0.0, ARM_BAND, lo), ('low_rear_arm_l', 0.0, a, W - ARM_BAND, W, lo)]
    if L > b:
        Z += [('tall_front', b, L, ARM_BAND, W - ARM_BAND, hi),
              ('low_front_arm_r', b, L, 0.0, ARM_BAND, lo), ('low_front_arm_l', b, L, W - ARM_BAND, W, lo)]
    if P['FET_SHIELD']:              # under the acrylic shield: 1 mm below it (cut out of the zones it overlaps)
        a, b, c, d = P['FET_SHIELD_XY']
        Z.append(('low_shield', a, b, c, d, P['FET_SHIELD_MAX_H']))
    return Z


def servo_notch_local():
    """PHASE2: if the board reaches past the deck's servo slot, an 8 mm deep notch at car x 98.5..103.5 on Y = 0"""
    x0, x1 = SERVO_SLOT[0] - POWER[0], SERVO_SLOT[1] - POWER[0]
    return (x0, x1, 0.0, 8.0) if P['POWER_L'] > x0 else None


def _power_keepouts(z0, z1):
    ko = [cylz(x, y, z0 - 1, z1 + 1, POWER_HOLE_KEEPOUT) for (x, y) in POWER_HOLES]
    n = servo_notch_local()
    if n:
        a, b = pw(n[0], n[2]), pw(n[1], n[3])
        ko.append(box(a[0], b[0], a[1] - 1, b[1], z0 - 1, z1 + 1))
    return ko


def devkit_io_boxes():
    """the carrier's I/O connectors on its Y = 79 edge (car y = DEVKIT y1), each with its jack face"""
    out = {}
    y_edge = P['DEVKIT'][3]
    for (name, X0, X1, h, depth) in P['DEVKIT_IO']:
        x0, _ = dk(X0, 0); x1, _ = dk(X1, 0)
        out[name] = dict(box=box(x0, x1, y_edge - depth, y_edge + DEVKIT_IO_OVERHANG, Z_DEVKIT1, Z_DEVKIT1 + h),
                         x=(x0 + x1) / 2, face_y=y_edge + DEVKIT_IO_OVERHANG, h=h)
    return out


DEVKIT_IO_OVERHANG = 1.0         # jacks stand 1 mm proud of the carrier edge (estimate)


def devkit_plug_boxes(io):
    """mating plugs on the I/O edge, with the point where each cable leaves (estimates: RJ45 plug 21 mm + boot
    11 mm; USB-A overmold 16 x 8 x 28; USB-C overmold 12 x 7 x 25; DC right-angle plug 12 x 12 x 20, cable down)"""
    out = {}
    def put(name, port, w, hgt, length, zc, exit_dz=0.0):
        x = io[port]['x']; y0 = io[port]['face_y']
        b = box(x - w / 2, x + w / 2, y0, y0 + length, zc - hgt / 2, zc + hgt / 2)
        out[name] = dict(box=b, end=(x, y0 + length, zc + exit_dz), x=x)
    z1 = Z_DEVKIT1
    put('dc_plug', 'dc_jack', 12.0, 12.0, 20.0, z1 + 5.5)
    put('usb_a_lidar', 'usb_a_1', 16.0, 8.0, 28.0, z1 + 4.0)
    put('usb_a_pico', 'usb_a_2', 16.0, 8.0, 28.0, z1 + 4.0)
    put('rj45_camera', 'rj45', 14.0, 10.0, 32.0, z1 + 6.5)
    put('usb_c_hub', 'usb_c', 12.0, 7.0, 25.0, z1 + 1.8)
    # the DC plug's cable leaves downward at its far end
    e = out['dc_plug']['end']; out['dc_plug']['end'] = (e[0], e[1] - 6.0, e[2] - 6.0)
    return out


def boards():
    """Envelopes of the rev B electronics: the power board with its height map, the dev-kit carrier and what is on
    and under it, the plugs on its I/O edge, the FSESC, the fan, the battery assembly (BMS, MIDI fuse, XT90-S) and
    the lidar's USB-Ethernet dongle."""
    x0, x1, y0, y1 = POWER; z = P['POWER_Z']; t = P['PCB_T']; zt = Z_POWER_TOP
    B = {}
    pcb = box(x0, x1, y0, y1, z, zt)
    n = servo_notch_local()
    if n:
        a, b = pw(n[0], n[2]), pw(n[1], n[3])
        pcb = pcb.cut(box(a[0], b[0], a[1] - 1, b[1], z - 1, zt + 1))
    for (hx, hy) in POWER_HOLES:
        pcb = pcb.cut(cylz(hx, hy, z - 1, zt + 1, 3.2))
    B['power_pcb'] = pcb
    B['power_standoffs_7mm'] = union(*[cylz(x, y, 0, z, 5.5) for (x, y) in POWER_HOLES])
    low, tall = [], []
    sh = None
    if P['FET_SHIELD']:
        a, b = pw(P['FET_SHIELD_XY'][0], P['FET_SHIELD_XY'][2]), pw(P['FET_SHIELD_XY'][1], P['FET_SHIELD_XY'][3])
        sh = box(a[0], b[0], a[1], b[1], zt - 1, zt + 50)
    for (name, X0, X1, Y0, Y1, h) in power_zones():
        a, b = pw(X0, Y0), pw(X1, Y1)
        blk = box(a[0], b[0], a[1], b[1], zt, zt + h)
        for k in _power_keepouts(zt, zt + h):
            blk = blk.cut(k)
        if sh is not None and name != 'low_shield' and bb_overlap(blk, sh):
            blk = blk.cut(sh)
        (low if name.startswith('low') else tall).append(blk)
    B['power_parts_low'] = union(*low)
    B['power_parts_tall'] = union(*tall)
    B['tray_standoffs_25mm'] = union(*[cylz(x, y, zt, Z_TRAY0, 5.5) for (x, y) in POWER_HOLES])
    fb = P['FET_BAR']
    a, b = pw(fb[0], fb[2]), pw(fb[1], fb[3])
    B['fet_bar'] = box(a[0], b[0], a[1], b[1], zt, zt + fb[4])     # heatsink bar + FET tabs, live at BAT+
    if bought_posts():               # canopy posts that are bought M3 hex standoff stacks (40 + 8 mm)
        B['canopy_standoffs'] = union(*[cylz(x, y, Z_TRAY1, Z_POST_TOP, 6.35) for (x, y) in bought_posts()])
    # mating plugs at the board's edges: ESC XT60 on the rear edge (cable to the ESC), pack XT90-S on the pack edge
    ey = pw(0, P['ESC_OUT_Y'])[1]
    B['esc_out_plug'] = box(x0 - 16.0, x0, ey - 8.0, ey + 8.0, zt, zt + 9.0)
    xx = pw(8.0, 0)[0]
    B['xt90s_pack'] = box(xx - 10.5, xx + 10.5, y1, y1 + 30.0, zt, zt + 17.0)
    # the dev-kit carrier
    dx0, dx1, dy0, dy1 = P['DEVKIT']
    dpcb = box(dx0, dx1, dy0, dy1, Z_DEVKIT0, Z_DEVKIT1)
    for (hx, hy) in DEVKIT_HOLES_CAR:
        dpcb = dpcb.cut(cylz(hx, hy, Z_DEVKIT0 - 1, Z_DEVKIT1 + 1, 2.7))
    B['devkit_pcb'] = dpcb
    bot = box(dx0, dx1, dy0, dy1, Z_DEVKIT0 - P['DEVKIT_BOTTOM_H'], Z_DEVKIT0)
    for (hx, hy) in DEVKIT_HOLES_CAR:                       # no parts within 5 mm of a mounting hole
        bot = bot.cut(cylz(hx, hy, Z_DEVKIT0 - P['DEVKIT_BOTTOM_H'] - 1, Z_DEVKIT0 + 1, 10.0))
    B['devkit_bottom_parts'] = bot
    jx0, jx1, jy0, jy1 = P['JETSON_XY']
    a, b = dk(jx0, jy0), dk(jx1, jy1)
    B['jetson_module_and_sink'] = box(a[0], b[0], a[1], b[1], Z_DEVKIT1, Z_SINK_TOP)
    io = devkit_io_boxes()
    B['devkit_io'] = union(*[v['box'] for v in io.values()])
    plugs = devkit_plug_boxes(io)
    B['devkit_plugs'] = union(*[v['box'] for v in plugs.values()])
    j12, j14 = P['DEVKIT_J12'], P['DEVKIT_J14']
    a, b = dk(j12[0], j12[2]), dk(j12[1], j12[3])
    hdr = box(a[0], b[0], a[1], b[1], Z_DEVKIT1, Z_DEVKIT1 + 8.5)
    a2, b2 = dk(j14[0], j14[2]), dk(j14[1], j14[3])
    hdr = hdr.union(box(a2[0], b2[0], a2[1], b2[1], Z_DEVKIT1, Z_DEVKIT1 + 2.6))
    B['devkit_headers'] = hdr
    # the ribbon's IDC socket on J12 and the J14 Dupont housing on the right-angle pins (out past the edge)
    idc = box(a[0] - 2.5, b[0] + 2.5, (a[1] + b[1]) / 2 - 4.5, (a[1] + b[1]) / 2 + 4.5, Z_DEVKIT1 + 8.5, Z_DEVKIT1 + 17.5)
    dup = box(a2[0], b2[0], dy0 - 9.0, dy0, Z_DEVKIT1 + 0.2, Z_DEVKIT1 + 2.8 + 0.2)
    B['devkit_header_plugs'] = idc.union(dup)
    # the FSESC in the ESC bay, on the cradle's 3 mm base
    L_, W_, H_ = P['ESC_CASE']; cx, cy = P['ESC_C']
    B['esc_case'] = box(cx - L_ / 2, cx + L_ / 2, cy - W_ / 2, cy + W_ / 2, CRADLE_T, CRADLE_T + H_)
    B['fan_40mm'] = box(FAN_X[0], FAN_X[1], -88.4, -78.4, 2.0, 42.0)
    # battery assembly on the pack lid
    B['bms'] = bms_solid()
    B['midi_fuse'] = box(*MIDI_FUSE_XY, PACK_TOP + PACK_LID_T, PACK_TOP + PACK_LID_T + MIDI_FUSE_H)
    # lidar USB-Ethernet dongle, zip-tied upright to the rear face of the camera arch's left leg, jack down
    B['usb_eth_adapter'] = box(*USB_ETH_BOX)
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
Z_LID_TOP = PACK_TOP + PACK_LID_T               # 6.0
LID_XY = (PX0 - 7, PX1 + 7, PY0, PY1 + 7)       # the lid in plan

# battery assembly on the lid (rev B): MIDI 125 A fuse holder in B+ (size ESTIMATE, unverified: 60 x 30 x 26 mm)
MIDI_FUSE_XY = (6.0, 66.0, 22.0, 52.0)
MIDI_FUSE_H = 26.0
# lidar dongle, standing upright against the rear face of the camera arch's left leg (x 136, y 36..48 is the leg),
# jack at the bottom (z 40) facing down, its USB lead leaving the top: (x0, x1, y0, y1, z0, z1)
USB_ETH_BOX = (136.0 - P['USB_ETH'][2], 136.0, 36.0 - P['USB_ETH'][1], 36.0, 40.0, 40.0 + P['USB_ETH'][0])


# ----------------------------------------------------------------------------- deck
PLINTH_BOLTS = [(P['LIDAR_FRONT_X'] - 32, 24), (P['LIDAR_FRONT_X'] - 32, -24), (P['LIDAR_FRONT_X'] - 6, 24), (P['LIDAR_FRONT_X'] - 6, -24)]
ARCH_X = (136.0, 150.0)
ARCH_Y = 42.0
ARCH_BOLTS = [(x, sy * ARCH_Y) for x in (ARCH_X[0] - 5, ARCH_X[1] + 5) for sy in (1, -1)]
POD = dict(x0=-105.0, x1=120.0, y_in=76.0, y_out=94.0, h=50.0, t=2.4)
# 40 mm side-pod fan (right pod), x range in the car frame. Rev B: it moved back from x -16..24 to x -94..-54 so it
# blows across the FSESC in the ESC bay (case centre x -74). The pod bolt at (-88, -72.5) sits inboard of the window,
# on the flange, with its head below the window's lower 2.7 mm (kit_report.json pod_bolt_head_in_fan_window_mm).
FAN_X = tuple(P['FAN_X'])
# Rev A's camera-plug slot (CAM_PLUG_NOTCH) and the camera-cable tie slots on the right pod are gone: the camera
# cable now leaves the dev kit's RJ45 over the pack lid.
# servo lead: a 5 mm slot just ahead of the front splice plates (x 67-97) and behind the cross rib (x 104-107). Rev B
# extends it outboard to y -67 so it lines up with the power board's servo notch (car x 98.5..103.5 on its Y = 0 edge,
# y -68..-60); the old y -52..-28 part now lies under the board and is harmless.
SERVO_SLOT = (98.5, 103.5, -67.0, -28.0)
POD_BOLTS = {1: [(-88, 72.5), (10, 72.5), (105, 72.5)], -1: [(-88, -72.5), (105, -72.5)]}
WING = dict(strut_x=(-214.0, -200.0), strut_y=55.0, z=88.0, chord=(-228.0, -183.0), span=95.0)
WING_BOLTS = [(x, sy * WING['strut_y']) for x in (WING['strut_x'][0] - 5, WING['strut_x'][1] + 5) for sy in (1, -1)]
SPLICE_Y = [(-74.0, -2.0), (2.0, 74.0)]          # bays between the edge ribs and the centre rib
JOINT_BOLTS = [(jx + sx * P['SPLICE_L'] / 3, y) for jx in P['JOINTS'] for sx in (-1, 1) for y in (-60.0, -40.0, -20.0, 20.0, 40.0, 60.0)]
# ESC cradle: two tabs share the rear joint's outboard bolts (M3 x 16 through cradle, deck and splice plate), two go
# into new deck inserts on the inboard side
CRADLE_T = 3.0
ESC_CRADLE_JOINT = [(-90.0, -60.0), (-70.0, -60.0)]
ESC_CRADLE_INSERTS = [(-104.0, -8.0), (-48.0, -8.0)]
# canopy leg in zone B (front-left corner of the canopy): a printed post whose foot shares the front joint's two
# left bolts at (92, 40) and (92, 60) (M3 x 16 through foot, deck and splice plate), so it needs no new inserts
CANOPY_LEG_XY = (92.0, 44.0)
CANOPY_LEG_JOINT = [(92.0, 40.0), (92.0, 60.0)]


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
    # pack window, post slots, cable passes
    d = d.cut(box(PX0 - 0.4, PX1 + 0.4, PY0 - 0.4, PY1 + 0.4, -DT - 20, 1))
    for (px, py) in (P['FRONT_POST'], P['REAR_POST']):
        for sy in (1, -1):
            s = P['POST_SLOT']
            d = d.cut(box(px - s / 2, px + s / 2, sy * py - s / 2, sy * py + s / 2, -60, 1))
    po = P['PHASE_OPENING']
    d = d.cut(box(po[0], po[1], po[2], po[3], -60, 1))   # motor phases + hall lead, under the ESC's motor end
    d = d.cut(box(SERVO_SLOT[0], SERVO_SLOT[1], SERVO_SLOT[2], SERVO_SLOT[3], -60, 1))
    d = d.cut(box(100, 112, 36, 50, -60, 1))        # lidar / camera cable drop to the right-hand keeper (spare)
    # holes: inserts (4.0) or clearance (3.4)
    holes = []
    holes += [(x, y, M3_INSERT, 0) for (x, y) in POWER_HOLES]
    holes += [(x, y, M3_INSERT, 0) for (x, y) in ESC_CRADLE_INSERTS]
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
        # fan window on the inner wall, fan behind it (40 mm fan, blows inboard across the FSESC)
        f0, f1 = FAN_X
        pod = pod.cut(box(f0 + 1, f1 - 1, yi - 1, yi + t + 1, 2, 40))
        for (fx, fz) in ((f0 + 4, 5), (f1 - 4, 5), (f0 + 4, 37), (f1 - 4, 37)):     # 32 mm hole pitch
            pod = pod.cut(cyl((fx, yi - 1, fz), 3.4, t + 12, (0, 1, 0)))
        # windows through both walls for the charge USB-C, the debug USB-C and the power button at the power board's
        # Y = 0 edge (a plug's overmold passes through the pod to the board edge 8 mm inboard of the pod)
        for (name, xc, w, z0, z1) in P['POD_WINDOWS']:
            pod = pod.cut(box(xc - w / 2, xc + w / 2, yi - 1, yo + 1, z0, z1))
    if sy < 0:
        pod = pod.mirror('XZ')
    return pod


# ----------------------------------------------------------------------------- rev B: dev-kit tray

def _front_post():
    """(x, kind) of the canopy's front posts. Wanted 8 mm ahead of the carrier; when the board's front standoffs are
    closer than 9 mm to that (boards of about 126 to 141 mm), the post stands on the standoff itself: a bought M3 hex
    standoff stack whose bottom male thread clamps the tray instead of the countersunk screw ('coaxial')."""
    want = P['DEVKIT'][1] + 8.0
    sx = POWER[1] - 4.0
    if abs(want - sx) < 9.0 and sx > P['DEVKIT'][1] + 4.0:
        return sx, 'coaxial'
    return min(want, max(POWER[1], P['DEVKIT'][1] + 13.0) - 5.0), 'pillar'


def tray_x1():
    """the tray's front end: the board's front edge, or 13 mm past the carrier if the board is shorter than that and
    the front posts are printed pillars (the tray's arms then overhang the board's front edge, above its front-edge
    plugs)"""
    return POWER[1] if _front_post()[1] == 'coaxial' else max(POWER[1], P['DEVKIT'][1] + 13.0)


def canopy_posts():
    """[(x, y, kind)]: the canopy's posts on the tray, outside the carrier. kind 'pillar' = printed on the tray,
    'standoff' = bought M3 hex standoffs (all four on a laser-cut tray), 'coaxial' = bought, on a tray standoff"""
    xr = P['DEVKIT'][0] - 6.0
    xf, kf = _front_post()
    yr, yl = POWER[2] + 4.0, POWER[3] - 4.0
    kr = 'standoff' if 'tray' in SHEET else 'pillar'
    if 'tray' in SHEET and kf == 'pillar':
        kf = 'standoff'
    return [(xr, yr, kr), (xr, yl, kr), (xf, yr, kf), (xf, yl, kf)]


def tray_pillars():
    """canopy post positions (x, y) car"""
    return [(x, y) for (x, y, _) in canopy_posts()]


def printed_pillars():
    return [(x, y) for (x, y, k) in canopy_posts() if k == 'pillar']


def bought_posts():
    return [(x, y) for (x, y, k) in canopy_posts() if k != 'pillar']


TRAY_PILLAR_D = 10.0


def tray_rects():
    """the tray's rails and edge arms in plan, car (x0, x1, y0, y1): a perimeter over the dev kit's shadow (board-local
    X 20..120), a cross rail at the X 75 standoffs, rails through the carrier's hole lines, and edge arms out to the
    corner standoffs. Shared by the printed tray and the laser-cut one."""
    x0, _, y0, y1 = POWER
    x1 = tray_x1()
    r = TRAY_RAIL
    mx0 = pw(LOW_X[0], 0)[0]
    mx1 = pw(min(LOW_X[1], P['POWER_L']), 0)[0]
    R = [(mx0, mx1, y0, y0 + r), (mx0, mx1, y1 - r, y1), (mx0, mx0 + r, y0, y1), (mx1 - r, mx1, y0, y1),
         (x0, mx0 + 0.01, y0, y0 + r), (x0, mx0 + 0.01, y1 - r, y1)]
    if x1 > mx1:
        R += [(mx1 - 0.01, x1, y0, y0 + r), (mx1 - 0.01, x1, y1 - r, y1)]
    cx = pw(75.0, 0)[0]
    R.append((cx - r / 2, cx + r / 2, y0, y1))
    for (hx, hy) in DEVKIT_HOLES_CAR:
        R.append((mx0, mx1, max(y0, hy - r / 2), min(y1, hy + r / 2)))
        R.append((max(mx0, hx - r / 2), min(mx1, hx + r / 2), y0, y1))
    return R


def fet_shield_screws_car():
    return [pw(X, Y) for (X, Y) in P['FET_SHIELD_SCREWS']] if P['FET_SHIELD'] else []


def devkit_tray():
    """Printed frame that carries the dev-kit carrier. It stands on the power board's six holes with M3 x 25
    standoffs (countersunk M3 x 8 from the top, heads flush) and holds the carrier on four 6 mm bosses at the
    carrier's own holes (DEVKIT_HOLES, M2.5 thread-forming screws). Rails as in tray_rects(). Four pillars on the
    arms carry the canopy. Everything else is open, for air and for the parts under it; all of it sits over the low
    (23 mm) zones of the power board's height map. Two more countersunk holes take the acrylic FET shield's screws."""
    x0, _, y0, y1 = POWER
    x1 = tray_x1()
    z0 = Z_TRAY0
    z1 = Z_TRAY0 + P['TRAY_T']
    m = [box(a, b, c, d, z0, z1) for (a, b, c, d) in tray_rects()]
    pads = [cylz(x, y, z0, z1, 10.0) for (x, y) in POWER_HOLES]
    pads += [cylz(x, y, z0, z1, 12.0) for (x, y) in DEVKIT_HOLES_CAR]
    bosses = [cylz(x, y, z1 - 0.01, z1 + P['DEVKIT_BOSS_H'], P['DEVKIT_BOSS_D']) for (x, y) in DEVKIT_HOLES_CAR]
    pillars = [cylz(x, y, z1 - 0.01, Z_POST_TOP, TRAY_PILLAR_D) for (x, y) in printed_pillars()]
    t = union(*m, *pads, *bosses, *pillars)
    # keep the tray inside the board outline (pads at the corner holes would overhang)
    t = t.intersect(box(x0, x1, y0, y1, z0 - 1, Z_CANOPY + 1))
    for (x, y) in POWER_HOLES + fet_shield_screws_car():
        t = t.cut(csk_hole(x, y, z1, P['TRAY_T']))
    for (x, y) in DEVKIT_HOLES_CAR:
        t = t.cut(cylz(x, y, z0 - 1, z1 + P['DEVKIT_BOSS_H'] + 1, P['DEVKIT_PILOT_D']))
    for (x, y) in printed_pillars():
        t = t.cut(cylz(x, y, Z_POST_TOP - 6.0, Z_POST_TOP + 1.0, M3_INSERT))     # M3 insert at the top for the canopy
    return t


# ----------------------------------------------------------------------------- rev B: ESC cradle

def esc_cradle():
    """Printed cradle for the cased FSESC in the ESC bay: a 3 mm base frame with a large window, low corner
    locators, two zip-tie straps over the case (slots and a groove underneath), four tabs to the deck. The rear-right
    corner is cut away over the phase opening so the motor leads drop straight down from the ESC's motor end."""
    L_, W_, H_ = P['ESC_CASE']; cx, cy = P['ESC_C']
    ex0, ex1, ey0, ey1 = cx - L_ / 2, cx + L_ / 2, cy - W_ / 2, cy + W_ / 2
    t = CRADLE_T
    base = box(ex0 - 2, ex1 + 2, ey0 - 5, ey1 + 5, 0, t)
    base = base.cut(box(ex0 + 8, ex1 - 8, ey0 + 8, ey1 - 8, -1, t + 1))
    tabs = [cylz(x, y, 0, t, 9.0) for (x, y) in ESC_CRADLE_JOINT + ESC_CRADLE_INSERTS]
    c = union(base, *tabs)
    # locators, 6 mm tall, 0.3 mm off the case: two on each long side, one on each end (inboard half)
    loc_h = 6.0
    for xs in (ex0 + 10, ex1 - 16):
        c = c.union(box(xs, xs + 6, ey0 - 2.7, ey0 - 0.3, t - 0.01, t + loc_h))
        c = c.union(box(xs, xs + 6, ey1 + 0.3, ey1 + 2.7, t - 0.01, t + loc_h))
    for xe in ((ex0 - 2.0, ex0 - 0.3), (ex1 + 0.3, ex1 + 2.0)):
        c = c.union(box(xe[0], xe[1], ey1 - 14, ey1 - 2, t - 0.01, t + loc_h))
    # zip-tie straps: slots beside both long sides and a 1.4 mm groove across the underside
    for xs in (cx - L_ / 4, cx + L_ / 4):
        for ys in ((ey0 - 3.9, ey0 - 1.7), (ey1 + 1.7, ey1 + 3.9)):
            c = c.cut(box(xs - 2.6, xs + 2.6, ys[0], ys[1], -1, t + 1))
        c = c.cut(box(xs - 2.6, xs + 2.6, ey0 - 4.0, ey1 + 4.0, -1, 1.4))
    # the phase opening: clear the cradle over it (1 mm margin)
    po = P['PHASE_OPENING']
    c = c.cut(box(po[0] - 1, po[1] + 1, po[2] - 1, po[3] + 1, -1, t + loc_h + 1))
    for (x, y) in ESC_CRADLE_JOINT + ESC_CRADLE_INSERTS:
        c = c.cut(cylz(x, y, -1, t + 1, M3_CLEAR))
    return c


# ----------------------------------------------------------------------------- rev B: the BMS on the pack lid

def bms_place():
    """the BMS box (x0, x1, y0, y1, z0, z1) for the chosen mount"""
    Lb, Wb, Tb = P['BMS']
    if P['BMS_MOUNT'] == 'flat':
        cy = (LID_XY[2] + LID_XY[3]) / 2
        return (-Lb / 2, Lb / 2, cy - Wb / 2, cy + Wb / 2, Z_LID_TOP + 2.0, Z_LID_TOP + 2.0 + Tb)
    # on its long edge along x, against the outboard (left) edge of the lid, inboard of the left pod (y 76)
    yo = POD['y_in'] - 5.0                  # 71: outboard face
    if 'bms' in SHEET:                      # the laser holder's base needs 2.5 mm outboard of its wall (closed slots)
        yo -= 2.5
    bt = P['SHEET_T'] if 'bms' in SHEET else 3.0            # holder base thickness
    return (-Lb / 2, Lb / 2, yo - Tb, yo, Z_LID_TOP + bt, Z_LID_TOP + bt + Wb)


def bms_solid():
    return box(*bms_place())


def bms_fence():
    """Holder for the JBD BMS. 'edge': a 3 mm base on the lid's outboard edge with a 12 mm channel the BMS stands in
    and two 60 mm uprights on its outboard face (zip ties round BMS and upright). It shares the lid's two outboard
    screws (+-30, 64.7), countersunk M3 x 10 through base and lid into the deck inserts. 'flat': a 2 mm tray with a
    rim on the lid, on the same two screws."""
    bx0, bx1, by0, by1, bz0, bz1 = bms_place()
    c = 0.3
    if P['BMS_MOUNT'] == 'flat':
        tr = box(bx0 - 2.4, bx1 + 2.4, by0 - 2.4, by1 + 2.4, Z_LID_TOP, Z_LID_TOP + 2.0)
        rim = box(bx0 - 2.4, bx1 + 2.4, by0 - 2.4, by1 + 2.4, Z_LID_TOP + 1.99, bz0 + 4.0).cut(
            box(bx0 - c, bx1 + c, by0 - c, by1 + c, Z_LID_TOP, bz0 + 5.0))
        f = tr.union(rim)
        for (x, y) in PACK_SCREWS[4:]:
            f = f.cut(csk_hole(x, y, Z_LID_TOP + 2.0, 2.0))
        return f
    w = 2.4
    yi, yo = by0 - c - w, by1 + c + w                 # outer faces of the channel walls
    base = box(bx0 - 2.0, bx1 + 2.0, yi, yo, Z_LID_TOP, Z_LID_TOP + 3.0)
    walls = [box(bx0 - 2.0, bx1 + 2.0, yi, by0 - c, Z_LID_TOP + 2.99, Z_LID_TOP + 15.0),
             box(bx0 - 2.0, bx1 + 2.0, by1 + c, yo, Z_LID_TOP + 2.99, Z_LID_TOP + 15.0)]
    ups = []
    for xu in (-50.0, 50.0):
        u = box(xu - 6.0, xu + 6.0, by1 + c, POD['y_in'] - 0.6, Z_LID_TOP + 2.99, Z_LID_TOP + 63.0)
        # two notches in the outer edge locate the zip ties
        for zn in (Z_LID_TOP + 30.0, Z_LID_TOP + 55.0):
            u = u.cut(box(xu - 7.0, xu + 7.0, POD['y_in'] - 1.6, POD['y_in'], zn - 2.0, zn + 2.0))
        ups.append(u)
    f = union(base, *walls, *ups)
    for (x, y) in PACK_SCREWS[4:]:
        f = f.cut(csk_hole(x, y, Z_LID_TOP + 3.0, 3.0))
    return f


def pack_box_bms_check():
    """Could the BMS go inside a taller pack box instead? The box cannot grow down (bay floor) and the BMS is larger
    than the box's inside in plan."""
    Lb, Wb, Tb = P['BMS']
    floor_gap = PACK_BOTTOM - Z_FLOOR
    return dict(bay_floor_gap_mm=round(floor_gap, 2), box_inside_mm=[PACK_IN_X, PACK_IN_Y],
                bms_mm=[Lb, Wb, Tb], bms_fits_inside_box_plan=bool(max(Lb, Wb) <= PACK_IN_X and min(Lb, Wb) <= PACK_IN_Y),
                box_can_grow_down_12mm=bool(floor_gap >= 12.0))


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


def canopy_leg():
    """Printed post from the deck in zone B to the canopy's front-left corner: a 12 mm column on a 14 x 30 mm foot
    that takes the front joint's two left bolts (M3 x 16), an M3 insert at the top for the canopy screw."""
    x, y = CANOPY_LEG_XY
    ya, yb = min(b[1] for b in CANOPY_LEG_JOINT) - 5.0, max(b[1] for b in CANOPY_LEG_JOINT) + 3.5
    foot = box(x - 7, x + 7, ya, yb, 0, 4).edges('|Z').fillet(3)
    col = cylz(x, y, 3.99, Z_POST_TOP, 12.0)
    gus = [box(x - 1.5, x + 1.5, ya + 1, yb - 1, 3.99, 16.0), box(x - 6.5, x + 6.5, y - 1.5, y + 1.5, 3.99, 16.0)]
    g = union(foot, col, *gus)
    for (ix, iy) in CANOPY_LEG_JOINT:
        g = g.cut(cylz(ix, iy, -1, 20, M3_CLEAR)).cut(cylz(ix, iy, 4.0, 20, M3_HEAD + 0.6))
    g = g.cut(cylz(x, y, Z_POST_TOP - 6.0, Z_POST_TOP + 1.0, M3_INSERT))
    return g


# ----------------------------------------------------------------------------- laser-cut sheet parts
# Each sheet part is a 2D profile (shapely, mm) cut from SHEET_T sheet, drawn kerf-neutral (nominal sizes; the laser's
# kerf of about 0.1-0.2 mm adds clearance to every hole and slot and takes it off every outline and tab). M3 holes are
# 3.2 mm. Tab/slot rule: tabs TAB_L long and SHEET_T deep; slots (SHEET_T + SLOT_CLEAR_W) x (TAB_L + SLOT_CLEAR_L);
# at least two tabs per edge, at most 40 mm apart, the end ones 8 mm in from the corners. Holes that must take a
# countersunk head are cut at 3.2 mm and countersunk by hand (a laser cannot).
LASER_DIR = os.path.join(OUT, 'laser')


class Sheet:
    """a laser-cut part: `poly` (outline with any non-circular holes), `circles` [(x, y, d)], `engrave`
    [(text, x, y, height)] in its own 2D frame; `place` maps the extruded profile into the car"""

    def __init__(self, name, poly, circles=(), engrave=(), material='', qty=1, place=None, note=''):
        self.name, self.poly, self.circles, self.engrave = name, poly, list(circles), list(engrave)
        self.material, self.qty, self.place, self.note = material, qty, place, note

    def cut_poly(self):
        if not self.circles:
            return self.poly
        return self.poly.difference(unary_union([Point(x, y).buffer(d / 2, 24) for (x, y, d) in self.circles]))

    def solid(self):
        s = poly_solid(self.cut_poly(), P['SHEET_T'])
        return self.place(s) if self.place else s


def _clean_ring(coords):
    """drop repeated and near-repeated points (shapely unions leave zero-length edges OCC cannot make faces from)"""
    pts = []
    for p in coords[:-1]:
        if not pts or math.dist(p, pts[-1]) > 1e-3:
            pts.append(p)
    if len(pts) > 1 and math.dist(pts[0], pts[-1]) <= 1e-3:
        pts.pop()
    return pts


def poly_solid(poly, t):
    poly = poly.simplify(0.002)
    polys = [poly] if poly.geom_type == 'Polygon' else list(poly.geoms)
    out = None
    for pg in polys:
        sol = cq.Workplane('XY').polyline(_clean_ring(list(pg.exterior.coords))).close().extrude(t)
        hs = [cq.Workplane('XY').polyline(_clean_ring(list(r.coords))).close().extrude(t + 2).translate((0, 0, -1)) for r in pg.interiors]
        if hs:
            sol = sol.cut(union(*hs))
        out = sol if out is None else out.union(sol)
    return out


def at_z(z0):
    """a horizontal sheet whose 2D frame is car (x, y), bottom face at z0"""
    return lambda s: s.translate((0, 0, z0))


def in_xz(y_lo):
    """a vertical sheet whose 2D frame is car (x, z), occupying y_lo..y_lo + SHEET_T"""
    return lambda s: s.rotate((0, 0, 0), (1, 0, 0), 90).translate((0, y_lo + P['SHEET_T'], 0))


def in_yz(x_lo):
    """a vertical sheet whose 2D frame is car (y, z), occupying x_lo..x_lo + SHEET_T"""
    return lambda s: s.rotate((0, 0, 0), (1, 0, 0), 90).rotate((0, 0, 0), (0, 0, 1), 90).translate((x_lo, 0, 0))


def tab_centres(a, b, pitch=40.0, end=8.0):
    """tab centres along an edge from a to b"""
    L = P['TAB_L']
    span = (b - a) - 2 * end - L
    n = max(2, int(span // pitch) + 2) if span > 0 else 1
    if n == 1:
        return [(a + b) / 2]
    return [a + end + L / 2 + i * span / (n - 1) for i in range(n)]


def slot(c, band0, along_x=True):
    """slot for a tab centred at c along an edge whose sheet band starts at band0 (a SHEET_T wide band)"""
    w, l = P['SHEET_T'] + P['SLOT_CLEAR_W'], P['TAB_L'] + P['SLOT_CLEAR_L']
    m = band0 + P['SHEET_T'] / 2
    return sbox(c - l / 2, m - w / 2, c + l / 2, m + w / 2) if along_x else sbox(m - w / 2, c - l / 2, m + w / 2, c + l / 2)


def tabs_on(edge_v, a, b, up=True):
    """tabs (SHEET_T deep) on a horizontal edge at v = edge_v of a vertical plate, between u = a and b"""
    t = P['SHEET_T']
    return [sbox(c - P['TAB_L'] / 2, edge_v if up else edge_v - t, c + P['TAB_L'] / 2, edge_v + t if up else edge_v)
            for c in tab_centres(a, b)]


def sheet_devkit_tray():
    """the dev-kit tray as one 3 mm sheet: the printed tray's frame, flat, with pads at every hole. The carrier stands on
    four DEVKIT_BOSS_H spacers (printed devkit_spacers, glued on, M2.5 thread-forming screws from the top; or three
    stacked laser_spacer_disc each, which makes 9 mm). The canopy posts are M3 hex standoffs (CANOPY_POST_H)."""
    x0, _, y0, y1 = POWER
    rects = [sbox(a, c, b, d) for (a, b, c, d) in tray_rects()]
    pads = [Point(p).buffer(5.0, 24) for p in POWER_HOLES] + [Point(p).buffer(6.0, 24) for p in DEVKIT_HOLES_CAR]
    pads += [Point(p).buffer(4.5, 24) for p in tray_pillars()]      # 9 mm: stays out of the rear and front 35 mm strips
    poly = unary_union(rects + pads).intersection(sbox(x0, y0, tray_x1(), y1))
    hm3 = P['LASER_HOLE_M3']
    circles = [(x, y, hm3) for (x, y) in POWER_HOLES + fet_shield_screws_car()]
    circles += [(x, y, hm3) for (x, y) in tray_pillars() if min(math.dist((x, y), h) for h in POWER_HOLES) > 1.0]
    circles += [(x, y, P['LASER_HOLE_M25']) for (x, y) in DEVKIT_HOLES_CAR]
    return Sheet('laser_devkit_tray', poly, circles, [], '3 mm laser-grade birch plywood (or 3 mm cast acrylic)', 1,
                 at_z(Z_TRAY0), 'countersink the six standoff holes and the two shield-screw holes by hand (90 deg, 6.7 mm)')


def devkit_spacers():
    """printed spacers for the sheet tray: 8 mm round, DEVKIT_BOSS_H tall, M2.5 pilot, glued to the sheet"""
    return union(*[cylz(x, y, Z_TRAY1, Z_TRAY1 + P['DEVKIT_BOSS_H'], 8.0).cut(
        cylz(x, y, Z_TRAY1 - 1, Z_TRAY1 + P['DEVKIT_BOSS_H'] + 1, P['DEVKIT_PILOT_D'])) for (x, y) in DEVKIT_HOLES_CAR])


def sheet_spacer_disc():
    return Sheet('laser_spacer_disc', Point(0, 0).buffer(4.0, 48), [(0.0, 0.0, P['LASER_HOLE_M25'])], [],
                 '3 mm cast acrylic or birch plywood', 12, None,
                 'alternative to the printed spacers: 3 per carrier hole = 9 mm, so set DEVKIT_BOSS_H=9 (carrier 2 mm higher)')


def sheet_fet_shield():
    """3 mm acrylic plate hung under the tray, between the BAT+ heatsink bar and the tray's CF rails"""
    X0, X1, Y0, Y1 = P['FET_SHIELD_XY']
    a, b = pw(X0, Y0), pw(X1, Y1)
    poly = sbox(a[0], a[1], b[0], b[1]).buffer(-2.0).buffer(2.0, 12)
    circles = [(x, y, P['LASER_HOLE_M3']) for (x, y) in fet_shield_screws_car()]
    eng = [('BAT+ BELOW', (a[0] + b[0]) / 2 + 3.0, (a[1] + b[1]) / 2 + 4.0, 3.0)]
    return Sheet('laser_fet_shield', poly, circles, eng, '3 mm cast acrylic (PMMA) only', 1, at_z(Z_TRAY0 - P['SHEET_T']),
                 '2 x M3 x 10 nylon countersunk screws from the tray top, nylon nuts under the shield')


def sheet_bms():
    """the BMS holder as three 3 mm sheets: a base on the lid with two rows of slots, an inboard channel wall and an
    outboard wall whose two ears are the uprights; tabs into the base, glue. Same lid screws as the printed holder."""
    bx0, bx1, by0, by1, bz0, bz1 = bms_place()
    t, c = P['SHEET_T'], 0.3
    yi, yo = by0 - c - t, by1 + c + t
    xa, xb = bx0 - 2.0, bx1 + 2.0
    zb = Z_LID_TOP + t                                           # base top
    cs = tab_centres(xa, xb)
    base = sbox(xa, yi - 2.5, xb, yo + 2.5).difference(unary_union([slot(cc, yi) for cc in cs] + [slot(cc, yo - t) for cc in cs]))
    base_c = [(x, y, P['LASER_HOLE_M3']) for (x, y) in PACK_SCREWS[4:]]
    S = {'laser_bms_base': Sheet('laser_bms_base', base, base_c, [('FRONT >', xb - 20, (yi + yo) / 2, 3.0)],
                                 '3 mm birch plywood or cast acrylic', 1, at_z(Z_LID_TOP),
                                 'countersink the two lid-screw holes by hand; the BMS edge sits over them')}
    wall_h = 12.0
    w_in = unary_union([sbox(xa, zb, xb, zb + wall_h)] + tabs_on(zb, xa, xb, up=False))
    S['laser_bms_wall_in'] = Sheet('laser_bms_wall_in', w_in, [], [], '3 mm birch plywood or cast acrylic', 1, in_xz(yi))
    ears = []
    for xu in (-50.0, 50.0):
        e = sbox(xu - 6.0, zb, xu + 6.0, Z_LID_TOP + 63.0)
        for zn in (Z_LID_TOP + 30.0, Z_LID_TOP + 55.0):         # zip-tie notches on both sides of each ear
            e = e.difference(sbox(xu - 7.0, zn - 2.0, xu - 4.6, zn + 2.0)).difference(sbox(xu + 4.6, zn - 2.0, xu + 7.0, zn + 2.0))
        ears.append(e)
    w_out = unary_union([sbox(xa, zb, xb, zb + wall_h)] + ears + tabs_on(zb, xa, xb, up=False))
    S['laser_bms_wall_out'] = Sheet('laser_bms_wall_out', w_out, [], [], '3 mm birch plywood or cast acrylic', 1, in_xz(yo - t))
    return S


def sheet_splices():
    """one profile for the four splice plates (the left and right plates are the same part turned over)"""
    out = {}
    for (name, jx, (y0, y1)) in (('splice_rear_right', P['JOINTS'][0], SPLICE_Y[0]), ('splice_rear_left', P['JOINTS'][0], SPLICE_Y[1]),
                                 ('splice_front_right', P['JOINTS'][1], SPLICE_Y[0]), ('splice_front_left', P['JOINTS'][1], SPLICE_Y[1])):
        poly = sbox(jx - P['SPLICE_L'] / 2, y0, jx + P['SPLICE_L'] / 2, y1).buffer(-3.0).buffer(3.0, 12)
        circles = [(x, y, P['LASER_HOLE_M3']) for (x, y) in JOINT_BOLTS if abs(x - jx) < P['SPLICE_L'] and y0 < y < y1]
        out[name] = Sheet('laser_splice', poly, circles, [], '3 mm laser-grade birch plywood (not acrylic, not MDF)', 4,
                          at_z(-DT - P['SHEET_T']))
    return out


def kit_sheets():
    """every laser-cut part kit.py knows (the canopy box is in extras.py)"""
    S = {'laser_devkit_tray': sheet_devkit_tray(), 'laser_spacer_disc': sheet_spacer_disc()}
    if P['FET_SHIELD']:
        S['laser_fet_shield'] = sheet_fet_shield()
    if P['BMS_MOUNT'] == 'edge':
        S.update(sheet_bms())
    sp = sheet_splices()
    S['laser_splice'] = sp['splice_rear_right']
    return S, sp


def _rings(poly):
    polys = [poly] if poly.geom_type == 'Polygon' else list(poly.geoms)
    for pg in polys:
        yield list(pg.exterior.coords)
        for r in pg.interiors:
            yield list(r.coords)


def export_laser(sheets):
    """DXF (layers CUT and ENGRAVE, mm) and SVG (red hairline = cut, black text = engrave) for each sheet part, each in
    its own frame moved to start at (0, 0). Returns the part list for the report."""
    import ezdxf
    os.makedirs(LASER_DIR, exist_ok=True)
    info = []
    for name, sh in sheets.items():
        minx, miny, maxx, maxy = sh.poly.bounds
        W, H = maxx - minx, maxy - miny
        doc = ezdxf.new('R2010')
        doc.units = ezdxf.units.MM
        doc.layers.add('CUT', color=1)
        doc.layers.add('ENGRAVE', color=5)
        msp = doc.modelspace()
        paths = []
        for ring in _rings(sh.poly):
            pts = [(x - minx, y - miny) for (x, y) in ring[:-1]]
            msp.add_lwpolyline(pts, close=True, dxfattribs={'layer': 'CUT'})
            paths.append('M ' + ' L '.join(f'{x:.3f} {H - y:.3f}' for (x, y) in pts) + ' Z')
        circ = []
        for (x, y, d) in sh.circles:
            msp.add_circle((x - minx, y - miny), d / 2, dxfattribs={'layer': 'CUT'})
            circ.append(f'<circle cx="{x - minx:.3f}" cy="{H - (y - miny):.3f}" r="{d / 2:.3f}" fill="none" stroke="#ff0000" stroke-width="0.1"/>')
        txt = []
        for (text, x, y, h) in sh.engrave:
            msp.add_text(text, height=h, dxfattribs={'layer': 'ENGRAVE'}).set_placement((x - minx, y - miny), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
            txt.append(f'<text x="{x - minx:.3f}" y="{H - (y - miny):.3f}" font-family="DejaVu Sans" font-size="{h:.2f}" '
                       f'text-anchor="middle" dominant-baseline="middle" fill="#000000">{text}</text>')
        doc.saveas(os.path.join(LASER_DIR, f'{name}.dxf'))
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.3f}mm" height="{H:.3f}mm" viewBox="0 0 {W:.3f} {H:.3f}">\n'
               f'<path d="{" ".join(paths)}" fill="none" stroke="#ff0000" stroke-width="0.1"/>\n' + '\n'.join(circ + txt) + '\n</svg>\n')
        with open(os.path.join(LASER_DIR, f'{name}.svg'), 'w') as f:
            f.write(svg)
        info.append(dict(name=name, material=sh.material, sheet_t=P['SHEET_T'], size_mm=[round(W, 1), round(H, 1)], qty=sh.qty,
                         holes=len(sh.circles), note=sh.note))
    return info


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
        devkit_tray=devkit_tray(), esc_cradle=esc_cradle(), bms_fence=bms_fence(), canopy_leg=canopy_leg(),
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
    # laser-cut parts: the FET shield is always fitted; SHEET_PARTS swaps printed parts for their sheet versions
    sheets, splices = kit_sheets()
    if P['FET_SHIELD']:
        parts['laser_fet_shield'] = sheets['laser_fet_shield'].solid()
    if 'tray' in SHEET:
        del parts['devkit_tray']
        parts['laser_devkit_tray'] = sheets['laser_devkit_tray'].solid()
        parts['devkit_spacers'] = devkit_spacers()
    if 'bms' in SHEET and P['BMS_MOUNT'] == 'edge':
        del parts['bms_fence']
        for k in ('laser_bms_base', 'laser_bms_wall_in', 'laser_bms_wall_out'):
            parts[k] = sheets[k].solid()
    if 'splices' in SHEET:
        for k, sh in splices.items():
            parts[k] = sh.solid()                                # same names, so the checks and joints are unchanged
    return S, comps, parts, extras, dict(scan_z=scan_z, lidar_top=lidar_top, arch_top=ARCH_TOP, sheets=sheets)


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


# bought parts that touch by design: a part and what it is soldered, plugged or bolted to
TOUCH = {frozenset(p) for p in (
    ('lidar', 'lidar_connectors'), ('camera', 'camera_plug'), ('camera', 'camera_m8_plug'),
    ('power_pcb', 'power_standoffs_7mm'), ('power_pcb', 'tray_standoffs_25mm'),
    ('power_pcb', 'power_parts_low'), ('power_pcb', 'power_parts_tall'),
    ('devkit_pcb', 'devkit_bottom_parts'), ('devkit_pcb', 'jetson_module_and_sink'), ('devkit_pcb', 'devkit_io'),
    ('devkit_pcb', 'devkit_headers'), ('devkit_io', 'devkit_plugs'), ('devkit_headers', 'devkit_header_plugs'),
    ('devkit_pcb', 'devkit_header_plugs'), ('fet_bar', 'power_parts_low'), ('fet_bar', 'power_parts_tall'),
    ('fet_bar', 'power_pcb'))}


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
    # the bought parts against each other: the height-map blocks, the dev kit and what is on and under it, the plugs,
    # the ESC, the battery assembly, the sensors
    for (na, a), (nb, b) in itertools.combinations(sorted(comps.items()), 2):
        if frozenset((na, nb)) in TOUCH:
            continue
        v = inter(a, b)
        if v > 0.5:
            rows.append((na, nb, round(v, 1)))
    # the vertical fits in the stack
    info['devkit_bottom_over_tray_mm'] = round(Z_DEVKIT0 - P['DEVKIT_BOTTOM_H'] - Z_TRAY1, 2)
    info['tray_over_power_low_parts_mm'] = round(Z_TRAY0 - (Z_POWER_TOP + P['POWER_LOW_H']), 2)
    info['devkit_bottom_over_power_parts_mm'] = round(Z_DEVKIT0 - P['DEVKIT_BOTTOM_H'] - (Z_POWER_TOP + P['POWER_LOW_H']), 2)
    # front of the power board against the lidar's M12 plugs (their cables leave the plugs at x 114.63)
    info['lidar_plug_ends_ahead_of_power_board_mm'] = round(LIDAR_PLUG_END_X - POWER[1], 2)
    # ESC: air around the case, and the right pod's rear bolt in front of the fan window
    L_, W_, H_ = P['ESC_CASE']; cx, cy = P['ESC_C']
    info['esc_case_xyz'] = [round(cx - L_ / 2, 1), round(cx + L_ / 2, 1), round(cy - W_ / 2, 1), round(cy + W_ / 2, 1), CRADLE_T, round(CRADLE_T + H_, 1)]
    info['esc_case_to_pod_inner_wall_mm'] = round((cy - W_ / 2) + POD['y_in'], 2)
    info['esc_case_top_under_bay_limit_mm'] = round(P['ESC_BAY'][4] - (CRADLE_T + H_), 2)
    bolt = [b for b in POD_BOLTS[-1] if FAN_X[0] < b[0] < FAN_X[1]]
    info['pod_bolt_head_in_fan_window_mm'] = [dict(bolt=b, head_top_z=round(3.0 + 1.65, 2), window_bottom_z=2.0,
                                                   blocks_mm=round(3.0 + 1.65 - 2.0, 2)) for b in bolt]
    info['pack_box_bms_check'] = pack_box_bms_check()
    info['bms_box'] = [round(v, 1) for v in bms_place()]
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


PRINT_ORIENT = dict(deck_front=((1, 0, 0), 180), deck_mid=((1, 0, 0), 180), deck_rear=((1, 0, 0), 180), bumper=(None, 0), lidar_plinth=(None, 0),
                    camera_arch=(None, 0), camera_cradle=(None, 0), side_pod_left=((1, 0, 0), 180), side_pod_right=((1, 0, 0), 180),
                    wing_strut_left=((1, 0, 0), 90), wing_strut_right=((1, 0, 0), -90), wing_blade=((1, 0, 0), 180),
                    pack_box=((1, 0, 0), 180), pack_lid=((1, 0, 0), 180), cell_holder_bottom=(None, 0), cell_holder_top=((1, 0, 0), 180),
                    devkit_tray=(None, 0), esc_cradle=(None, 0), bms_fence=(None, 0), canopy_leg=(None, 0), devkit_spacers=(None, 0))


def export(parts, comps, S, extras):
    import cadquery as cq
    res = {}
    for name, p in extras.items():
        q = p.rotate((0, 0, 0), (1, 0, 0), 180) if name.startswith('fit_coupon') else p   # top face down, like the deck
        bb = q.val().BoundingBox()
        q = q.translate((-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))
        cq.exporters.export(p, os.path.join(OUT, 'step', f'{name}.step'))
        cq.exporters.export(q, os.path.join(OUT, 'stl', f'{name}.stl'), tolerance=0.05, angularTolerance=0.15)
    for name, p in parts.items():
        if name.startswith('laser_') or (name.startswith('splice_') and 'splices' in SHEET):
            cq.exporters.export(p, os.path.join(OUT, 'step', f'{name}.step'))      # cut, not printed: DXF/SVG in out/laser
            continue
        ax, ang = PRINT_ORIENT.get(name, (None, 0))
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
    render(items, os.path.join(OUT, 'renders', 'kit_iso.png'), views=[(24, -58), (24, 122)], title='Atlas car v2 rev B kit: printed parts (dark), boards, ESC, BMS and pack (blue), sensors (orange)')
    render(items + chassis_items, os.path.join(OUT, 'renders', 'kit_on_chassis.png'), views=[(18, -60)], title='on the Slash 4x4 keep-out model (green, estimated)')
    render(items, os.path.join(OUT, 'renders', 'kit_top.png'), views=[(89.9, -90)], title='top view, nose to the right', zoom=1.25)
    render(items + chassis_items, os.path.join(OUT, 'renders', 'kit_side.png'), views=[(0, -90)], title='right side view', zoom=1.25)
    render([(p, grey) for k, p in parts.items() if k.startswith(('pack', 'cell', 'bms'))] + [(comps['cells_4s3p'], blue), (comps['bms'], blue), (comps['midi_fuse'], blue)],
           os.path.join(OUT, 'renders', 'pack.png'), views=[(25, -60)], title='4S3P pack: box, holders, lid, 12 cells; the JBD BMS on edge in its holder, MIDI fuse')
    stack = ('devkit_tray', 'esc_cradle')
    stack_c = ('power_pcb', 'power_standoffs_7mm', 'tray_standoffs_25mm', 'power_parts_low', 'power_parts_tall', 'devkit_pcb',
               'devkit_bottom_parts', 'jetson_module_and_sink', 'devkit_io', 'devkit_plugs', 'devkit_headers', 'devkit_header_plugs',
               'esc_case', 'fan_40mm', 'esc_out_plug', 'xt90s_pack')
    render([(parts[k], grey) for k in stack] + [(comps[k], blue) for k in stack_c],
           os.path.join(OUT, 'renders', 'stack_revb.png'), views=[(24, -58), (24, 122)],
           title='rev B stack: power board height map, dev-kit tray and carrier, ESC in its cradle')


if __name__ == '__main__':
    S, comps, parts, extras, info = build()
    rows, pack_in_bay, fov = checks(S, comps, parts, info)
    res = export(parts, comps, S, extras)
    laser = export_laser(info['sheets'])
    renders(parts, comps, S)
    keys = ('devkit_bottom_over_tray_mm', 'tray_over_power_low_parts_mm', 'devkit_bottom_over_power_parts_mm',
            'lidar_plug_ends_ahead_of_power_board_mm', 'esc_case_xyz', 'esc_case_to_pod_inner_wall_mm',
            'esc_case_top_under_bay_limit_mm', 'pod_bolt_head_in_fan_window_mm', 'pack_box_bms_check', 'bms_box')
    rep = dict(params=P, z_rim=Z_RIM, tower_top=TOWER_TOP, scan_plane_z=round(info['scan_z'], 2), lidar_top_z=round(info['lidar_top'], 2),
               camera_axis_z=round(info['arch_top'] + 4 + 14.5, 2), pack_box_z=[round(PACK_BOTTOM, 2), PACK_TOP], pack_in_bay=pack_in_bay,
               stack_z=dict(power_top=Z_POWER_TOP, tray=[Z_TRAY0, Z_TRAY1], devkit=[round(Z_DEVKIT0, 2), round(Z_DEVKIT1, 2)],
                            sink_top=round(Z_SINK_TOP, 2), canopy_underside=round(Z_CANOPY, 2)),
               power_board=dict(outline_car=POWER, holes_car=POWER_HOLES, holes_local=POWER_HOLES_LOCAL,
                                servo_notch_local=servo_notch_local(), zones_local=power_zones()),
               devkit_holes_car=DEVKIT_HOLES_CAR, canopy_posts=canopy_posts(), sheet_parts_in_checks=sorted(SHEET),
               canopy_over_fan_mm=round(Z_CANOPY - Z_SINK_TOP, 2), canopy_gap_ok=bool(Z_CANOPY - Z_SINK_TOP >= P['CANOPY_GAP']),
               fet_shield=dict(on=bool(P['FET_SHIELD']), shield_z=[round(Z_TRAY0 - P['SHEET_T'], 2), Z_TRAY0],
                               live_metal_top_z=round(Z_POWER_TOP + P['FET_BAR'][4], 2),
                               gap_bar_to_shield_mm=round(Z_TRAY0 - P['SHEET_T'] - Z_POWER_TOP - P['FET_BAR'][4], 2)),
               **{k: info[k] for k in keys}, interference=rows, lidar_plane=fov, parts=res, laser=laser)
    with open(os.path.join(OUT, 'kit_report.json'), 'w') as f:
        json.dump(rep, f, indent=1, default=str)
    print(json.dumps({k: rep[k] for k in ('scan_plane_z', 'lidar_top_z', 'camera_axis_z', 'pack_box_z', 'pack_in_bay', 'stack_z',
                                         'sheet_parts_in_checks', 'fet_shield') + keys + ('interference', 'lidar_plane')}, indent=1, default=str))
    for l in laser:
        print(f"laser {l['name']:22s} {l['size_mm']} mm x{l['qty']}  {l['material']}")
    for k, v in res.items():
        print(f'{k:22s} bed {v["bed_xyz"]}  {v["volume_cm3"]:7.1f} cm3  ~{v["mass_g_solid_petgcf"]:.0f} g solid  fits250={v["fits_250_bed"]}  solids={v["solids"]}')
