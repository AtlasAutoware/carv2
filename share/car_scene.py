"""Whole-car scene for the renders: the printed kit and the parts that finish it (mech/kit.py, mech/extras.py),
both boards (their KiCad 3D models), every cable, and stand-ins for everything bought.

    python3 share/car_scene.py          writes share/scene/*.stl and share/scene/scene.json (about 1 minute)
    share/render_car.sh                 renders them with Blender Cycles (render_car.py)

The stand-ins are NOT models of the real parts. They are drawn from the sizes this design already uses: the
Traxxas Slash 4x4 from kit.py's chassis keep-out numbers (all estimates, docs/MEASURE_FIRST.md), the SICK TiM561
and LUCID Triton from their datasheet envelopes in kit.py, the Jetson module with the dev kit's heatsink and fan
from its 69.6 x 45 mm module and kit.py's 32 mm height. Suspension geometry, wheel spokes, tread, fins and fan
blades are drawn to look right, not measured.

Units are mm in the car frame of kit.py (+x forward, +y left, +z up, deck top at z 0).
"""
import json
import math
import os
import sys

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'mech'))
import kit  # noqa: E402
import extras  # noqa: E402
from kit import P, box, cylz, cyl, union  # noqa: E402

SCENE = os.path.join(HERE, 'scene')
os.makedirs(SCENE, exist_ok=True)

OBJ = []            # (name, shape, material, group)


def add(name, shape, mat, group):
    OBJ.append((name, shape, mat, group))


def comp(*shapes):
    """compound without boolean union (fine for rendering, much faster)"""
    sol = []
    for s in shapes:
        if s is None:
            continue
        v = s.vals() if hasattr(s, 'vals') else [s]
        for x in v:
            sol.extend(x.Solids() if hasattr(x, 'Solids') else [x])
    return cq.Workplane('XY').add(cq.Compound.makeCompound(sol))


def cyl_between(p0, p1, d):
    L = math.dist(p0, p1)
    v = tuple((p1[i] - p0[i]) / L for i in range(3))
    return cq.Workplane('XY').add(cq.Solid.makeCylinder(d / 2, L, cq.Vector(*p0), cq.Vector(*v)))


def rot_y_axis(shape, center, deg):
    return shape.rotate(center, (center[0], center[1] + 1, center[2]), deg)


# ----------------------------------------------------------------------------- chassis stand-in (Slash 4x4)
Z_RIM, Z_FLOOR, TOWER_TOP = kit.Z_RIM, kit.Z_FLOOR, kit.TOWER_TOP
R_TYRE = P['TYRE_D'] / 2
Y_TYRE = P['TRACK'] / 2 - P['TYRE_W'] / 2                  # tyre centre plane
Z_AXLE = Z_RIM + P['TYRE_TOP_ABOVE_RIM'] - R_TYRE           # -89.175
Z_GROUND = Z_AXLE - R_TYRE                                  # -144.175
AXLES = {'front': kit.FRONT_AXLE, 'rear': kit.REAR_AXLE}


def wheel_parts(xc, sy):
    """rim, tyre carcass and lugs for one corner, placed. Built about the origin with the axle along y."""
    W = P['TYRE_W']
    yc = sy * Y_TYRE
    # carcass: revolve a profile drawn in the XY plane (x = radius, y = axial) about the y axis
    r_in, r_out = 35.0, R_TYRE - 3.0
    pts = [(r_in, -W / 2 + 3), (r_out - 7, -W / 2 + 1), (r_out - 1.5, -W / 2 + 4), (r_out, -W / 2 + 9),
           (r_out, W / 2 - 9), (r_out - 1.5, W / 2 - 4), (r_out - 7, W / 2 - 1), (r_in, W / 2 - 3)]
    carcass = cq.Workplane('XY').polyline(pts).close().revolve(360, (0, 0, 0), (0, 1, 0))
    lugs = []
    n = 26
    for yoff, phase in ((-10.0, 0.0), (10.0, 0.5)):
        for i in range(n):
            a = 360.0 * (i + phase) / n
            lug = box(-4.2, 4.2, -7.5, 7.5, r_out - 0.6, R_TYRE)
            lugs.append(lug.translate((0, yoff, 0)).rotate((0, 0, 0), (0, 1, 0), a))
    for i in range(n):                                          # shoulder blocks on the sidewall edge
        a = 360.0 * (i + 0.25) / n
        for s in (-1, 1):
            sb = box(-3.0, 3.0, s * (W / 2 - 3.0) - 2.0, s * (W / 2 - 3.0) + 2.0, r_out - 5.0, r_out + 1.0)
            lugs.append(sb.rotate((0, 0, 0), (0, 1, 0), a))
    # rim: barrel, outer lip, 6 split spokes, hub with a wheel nut
    rim_r = r_in + 1.0
    barrel = cq.Workplane('XZ').circle(rim_r).circle(rim_r - 2.5).extrude(W - 6).translate((0, W / 2 - 3, 0))
    lip = cq.Workplane('XZ').circle(rim_r + 2.2).circle(rim_r - 2.5).extrude(3).translate((0, W / 2, 0))
    face_y = W / 2 - 4.0
    spokes = []
    for i in range(6):
        for d in (-7.0, 7.0):
            a = 60.0 * i + d
            s = box(8.0, rim_r - 1.0, -2.5, 2.5, -2.2, 2.2).translate((0, face_y, 0))
            spokes.append(s.rotate((0, 0, 0), (0, 1, 0), a))
    hub = cq.Workplane('XZ').circle(12.0).extrude(10).translate((0, face_y + 2.5, 0))
    nut = cq.Workplane('XZ').polygon(6, 10.0).extrude(6).translate((0, face_y + 8.5, 0))
    if sy < 0:
        mirror = lambda s: s.mirror('XZ')                     # noqa: E731
        carcass, lugs = mirror(carcass), [mirror(l) for l in lugs]
        barrel, lip, spokes, hub, nut = mirror(barrel), mirror(lip), [mirror(s) for s in spokes], mirror(hub), mirror(nut)
    place = lambda s: s.translate((xc, yc, Z_AXLE))           # noqa: E731
    return (place(carcass), [place(l) for l in lugs], place(comp(barrel, lip, *spokes, hub)), place(nut))


def coilover(top, bottom, body_d=16.0, spring_d=19.0):
    """shock: body from the top mount, rod to the bottom mount, a coil spring over the body"""
    L = math.dist(top, bottom)
    v = tuple((bottom[i] - top[i]) / L for i in range(3))
    at = lambda s: tuple(top[i] + v[i] * s for i in range(3))  # noqa: E731
    body = cyl_between(at(4), at(0.62 * L), body_d)
    cap = cyl_between(at(0), at(6), body_d + 2)
    rod = cyl_between(at(0.62 * L), at(L - 4), 5.0)
    eye_t = cyl_between(at(-3), at(5), 8.0)
    eye_b = cyl_between(at(L - 6), at(L + 2), 8.0)
    # spring: a helix swept with a circle
    turns, pitch = 7, (0.62 * L - 10) / 7
    helix = cq.Wire.makeHelix(pitch, pitch * turns, spring_d / 2 - 1.2)
    spring = (cq.Workplane('XY').add(cq.Solid.makeSphere(0.1)))
    try:
        path = cq.Workplane('XY').add(helix)
        prof = cq.Workplane('XZ').center(spring_d / 2 - 1.2, 0).circle(1.2)
        spring = prof.sweep(path, isFrenet=True)
        # helix is along +z from the origin: orient it along the shock, starting 8 mm below the top
        z = cq.Vector(0, 0, 1)
        d = cq.Vector(*v)
        ax = z.cross(d)
        ang = math.degrees(math.acos(max(-1, min(1, z.dot(d)))))
        if ax.Length > 1e-9:
            spring = spring.rotate((0, 0, 0), ax.toTuple(), ang)
        spring = spring.translate(at(8))
    except Exception:
        spring = cyl_between(at(8), at(0.62 * L), spring_d)
    return comp(body, cap, eye_t), comp(rod, eye_b), spring


def chassis():
    S = {}
    # tub: a moulded tray with rounded ends and a raised centre spine, side guards along the outside
    # chassis plate: the kit's keep-out tub is only 100 mm wide, but the battery bay (kit BATT_BAY, y 15-62) and
    # the motor (y -85 to -25) sit outside it, so the stand-in is a wide floor plate with low walls
    tub_outer = box(-170, 170, -64, 66, Z_FLOOR, Z_FLOOR + 9).edges('|Z').fillet(16)
    tub_inner = box(-167, 167, -61, 63, Z_FLOOR + 2.5, Z_FLOOR + 10).edges('|Z').fillet(13)
    add('chassis_tub', tub_outer.cut(tub_inner), 'plastic_black', 'chassis')
    # bulkheads and diff housings at each axle
    for name, ax in AXLES.items():
        s = 1 if name == 'front' else -1
        bulk = box(ax - 24, ax + 18, -34, 34, Z_AXLE - 20, Z_AXLE + 22).edges('|X').fillet(6)
        diff = cyl((ax, -30, Z_AXLE), 40, 60, (0, 1, 0))
        add(f'{name}_bulkhead', comp(bulk, diff), 'plastic_black', 'chassis')
    # shock towers: shaped plates with the tower top from kit.py, wider at the top
    for name, tx in (('front', P['FRONT_TOWER_X']), ('rear', P['REAR_TOWER_X'])):
        T = P['TOWER_T']
        prof = [(-30, Z_AXLE + 10), (30, Z_AXLE + 10), (66, TOWER_TOP - 6), (60, TOWER_TOP), (-60, TOWER_TOP), (-66, TOWER_TOP - 6)]
        plate = cq.Workplane('YZ').polyline(prof).close().extrude(T).translate((tx - T / 2, 0, 0))
        for yy in (-48, -24, 0, 24, 48):
            plate = plate.cut(cyl((tx - 5, yy, TOWER_TOP - 18), 9 if yy else 12, 10, (1, 0, 0)))
        add(f'{name}_tower', plate, 'plastic_black', 'chassis')
        # body posts (kit.py positions), with the kit's post washers and body clips on top
        px, py = P['FRONT_POST'] if name == 'front' else P['REAR_POST']
        posts = [cylz(px, s * py, TOWER_TOP - 4, P['POST_TOP'], P['POST_D']) for s in (1, -1)]
        add(f'{name}_body_posts', comp(*posts), 'plastic_black', 'chassis')
        clips = [cq.Workplane('XY').circle(6.2).circle(5.2).extrude(1.2).translate((px, s * py, 5.0)) for s in (1, -1)]
        add(f'{name}_body_clips', comp(*clips), 'steel', 'chassis')
    # suspension, hubs, driveshafts, wheels
    for name, ax in AXLES.items():
        tx = P['FRONT_TOWER_X'] if name == 'front' else P['REAR_TOWER_X']
        for sy in (1, -1):
            y_in, y_hub = sy * 34.0, sy * (Y_TYRE - 22.0)
            arm = []
            for dx in (-16, 16):
                arm.append(cyl_between((ax + dx, y_in, Z_AXLE - 12), (ax + dx * 0.25, y_hub, Z_AXLE - 14), 9.0))
            arm.append(cyl_between((ax - 16, y_in, Z_AXLE - 12), (ax + 16, y_in, Z_AXLE - 12), 8.0))
            plate = box(ax - 10, ax + 10, min(y_in, y_hub), max(y_in, y_hub), Z_AXLE - 16, Z_AXLE - 11)
            upper = cyl_between((tx + (6 if name == 'front' else -6), sy * 24, TOWER_TOP - 26), (ax, y_hub, Z_AXLE + 18), 6.0)
            add(f'{name}_arms_{"L" if sy > 0 else "R"}', comp(*arm, plate, upper), 'plastic_black', 'chassis')
            carrier = box(ax - 12, ax + 12, y_hub - 7 * sy - 5, y_hub - 7 * sy + 5, Z_AXLE - 20, Z_AXLE + 22).edges('|Y').fillet(4)
            carrier = carrier.union(cyl((ax, y_hub - 12 * sy, Z_AXLE), 20, 12 * sy if sy > 0 else 12, (0, sy, 0)))
            add(f'{name}_hub_{"L" if sy > 0 else "R"}', carrier, 'plastic_dark', 'chassis')
            shaft = cyl_between((ax, sy * 26, Z_AXLE), (ax, y_hub, Z_AXLE), 7.0)
            boot = cyl_between((ax, sy * 26, Z_AXLE), (ax, sy * 44, Z_AXLE), 14.0)
            add(f'{name}_driveshaft_{"L" if sy > 0 else "R"}', comp(shaft), 'steel', 'chassis')
            add(f'{name}_diff_boot_{"L" if sy > 0 else "R"}', comp(boot), 'rubber', 'chassis')
            # coil-over: tower outer mount to the outer end of the lower arm
            top = (tx + (4 if name == 'front' else -4), sy * 60.0, TOWER_TOP - 8)
            bot = (ax - 6 * (1 if name == 'front' else -1), sy * (Y_TYRE - 34.0), Z_AXLE - 9)
            body, rod, spring = coilover(top, bot)
            add(f'{name}_shock_body_{"L" if sy > 0 else "R"}', body, 'alu_dark', 'chassis')
            add(f'{name}_shock_rod_{"L" if sy > 0 else "R"}', rod, 'chrome', 'chassis')
            add(f'{name}_shock_spring_{"L" if sy > 0 else "R"}', spring, 'spring_steel', 'chassis')
            carcass, lugs, rim, nut = wheel_parts(ax, sy)
            add(f'{name}_tyre_{"L" if sy > 0 else "R"}', comp(carcass, *lugs), 'rubber', 'chassis')
            add(f'{name}_rim_{"L" if sy > 0 else "R"}', rim, 'rim', 'chassis')
            add(f'{name}_wheelnut_{"L" if sy > 0 else "R"}', nut, 'alu_dark', 'chassis')
    # steering: servo, servo saver, links
    s = P['SERVO']
    servo = box(s[0] + 1, s[1] - 1, -44, -4, Z_FLOOR + 6, Z_RIM + s[4] - 10).edges('|Z').fillet(1.5)
    tabs = box(s[0] + 1, s[1] - 1, -50, 2, Z_RIM + s[4] - 20, Z_RIM + s[4] - 17)
    add('steering_servo', comp(servo, tabs), 'plastic_black', 'chassis')
    saver = cylz(s[0] + 11, -12, Z_RIM + s[4] - 10, Z_RIM + s[4] - 3, 20)
    add('servo_saver', saver, 'plastic_dark', 'chassis')
    fx = kit.FRONT_AXLE
    links = [cyl_between((s[0] + 11, -12 + 8, Z_RIM + s[4] - 6), (fx - 12, sy * (Y_TYRE - 28), Z_AXLE + 4), 4.0) for sy in (1, -1)]
    add('steering_links', comp(*links), 'steel', 'chassis')
    # drivetrain: centre shaft, transmission, motor (Puller Pro 540 stand-in: 36 mm can) with its end bell
    add('centre_shaft', cyl_between((-110, 0, Z_FLOOR + 10), (AXLES['front'] - 24, 0, Z_AXLE + 4), 6.0), 'steel', 'chassis')
    g = P['GEARBOX']
    trans = box(g[0], g[1], g[2], g[3], Z_FLOOR + 3, Z_RIM + g[4]).edges('|Y').fillet(6)
    add('transmission', trans, 'plastic_black', 'chassis')
    spur = cq.Workplane('XZ').circle(30).extrude(8).translate((P['MOTOR_X'] + 8, -18, Z_RIM - 5))
    add('spur_cover', spur, 'plastic_dark', 'chassis')
    y0, y1 = P['MOTOR_Y']
    mz = Z_RIM + P['MOTOR_AXIS_ABOVE_RIM']
    can = cyl((P['MOTOR_X'], y0 + 6, mz), P['MOTOR_D'], y1 - y0 - 6, (0, 1, 0))
    for i in range(10):                                            # cooling grooves on the can
        can = can.cut(cyl((P['MOTOR_X'], y0 + 14 + 4.2 * i, mz), P['MOTOR_D'] + 2, 1.2, (0, 1, 0)).cut(
            cyl((P['MOTOR_X'], y0 + 13 + 4.2 * i, mz), P['MOTOR_D'] - 1.0, 4, (0, 1, 0))))
    add('motor_can', can, 'motor_can', 'chassis')
    bell = cyl((P['MOTOR_X'], y0, mz), P['MOTOR_D'] - 1, 6.5, (0, 1, 0))
    tabs = [box(P['MOTOR_X'] + 9 * math.cos(math.radians(90 + 120 * i)) - 2, P['MOTOR_X'] + 9 * math.cos(math.radians(90 + 120 * i)) + 2,
                y0 - 4, y0, mz + 9 * math.sin(math.radians(90 + 120 * i)) - 1, mz + 9 * math.sin(math.radians(90 + 120 * i)) + 1)
            for i in range(3)]
    add('motor_endbell', comp(bell, *tabs), 'alu', 'chassis')
    mount = box(P['MOTOR_X'] - 24, P['MOTOR_X'] + 24, y1 - 2, y1 + 2, Z_FLOOR + 3, mz + 22)
    add('motor_mount', mount, 'alu_dark', 'chassis')
    # rear bumper
    rb = box(-212, -196, -62, 62, Z_AXLE - 6, Z_AXLE + 14).edges('|X').fillet(5)
    rb = rb.union(box(-198, -165, -30, 30, Z_AXLE - 2, Z_AXLE + 8))
    add('rear_chassis_bumper', rb, 'plastic_black', 'chassis')


# ----------------------------------------------------------------------------- sensors
def tim561():
    """SICK TiM561 envelope from kit.tim561 (datasheet sizes; the connector unit is an estimate)"""
    xf = P['LIDAR_FRONT_X']
    xr = xf - 61.0
    z0 = P['PLINTH_T']
    xc = xr + 30.5
    base = box(xr, xf, -30, 30, z0, z0 + 58.45).edges('|Z').fillet(4)
    base = base.edges('>Z').chamfer(1.5)
    add('lidar_body', base, 'sensor_grey', 'sensors')
    window = cylz(xc, 0, z0 + 58.45, z0 + 67.5, 56)
    add('lidar_window', window, 'optics_black', 'sensors')
    hood = cq.Workplane('XY').add(cq.Solid.makeCone(28, 22, 85.75 - 67.5, cq.Vector(xc, 0, z0 + 67.5), cq.Vector(0, 0, 1)))
    add('lidar_hood', hood, 'sensor_dark', 'sensors')
    unit = box(xr - 17.37, xr, -20, 20, z0, z0 + 18).edges('|X').fillet(2)
    add('lidar_connector_unit', unit, 'sensor_dark', 'sensors')
    for sy, nm in ((1, 'eth'), (-1, 'pwr')):
        yz = (sy * 10.0, z0 + 9.0)
        nutc = cyl((xr - 17.37, yz[0], yz[1]), 16, 12, (-1, 0, 0))
        for i in range(12):
            a = math.radians(30 * i)
            nutc = nutc.cut(cyl((xr - 17.37, yz[0] + 8.2 * math.cos(a), yz[1] + 8.2 * math.sin(a)), 1.4, 13, (-1, 0, 0)))
        bodyp = cq.Workplane('XY').add(cq.Solid.makeCone(7.2, 4.0, 33.0, cq.Vector(xr - 29.37, yz[0], yz[1]), cq.Vector(-1, 0, 0)))
        add(f'lidar_plug_nut_{nm}', nutc, 'nickel', 'sensors')
        add(f'lidar_plug_body_{nm}', bodyp, 'cable_black', 'sensors')


def triton():
    """LUCID Triton TRI023S-CC: 29 x 29 x 45 mm body, C-mount, Kowa LM4NCL lens (31 x 30.5 mm), M12 plug at the back"""
    x_face = P['LIDAR_FRONT_X'] - P['CAM_LENS_L']
    x0 = x_face - 45.0
    zb = kit.ARCH_TOP + 4.0
    zc = zb + 14.5
    body = box(x0, x_face - 3, -14.5, 14.5, zb, zb + 29).edges('|X').fillet(2.0)
    front = box(x_face - 3, x_face, -14.5, 14.5, zb, zb + 29).edges('|X').fillet(2.0)
    add('camera_body', body, 'anodized_dark', 'sensors')
    add('camera_front', front, 'anodized_dark', 'sensors')
    ring = cyl((x_face, 0, zc), 27.0, 2.5, (1, 0, 0))
    add('camera_mount_ring', ring, 'alu', 'sensors')
    L = P['CAM_LENS_L']
    lens = cyl((x_face + 2.5, 0, zc), P['CAM_LENS_D'], L - 2.5, (1, 0, 0))
    knurl = []
    for xo, w in ((6.0, 7.0), (17.0, 6.0)):
        for i in range(36):
            a = math.radians(10 * i)
            knurl.append(cyl((x_face + 2.5 + xo, 15.7 * math.cos(a), zc + 15.7 * math.sin(a)), 1.0, w, (1, 0, 0)))
    lens = lens.cut(cyl((x_face + L - 1.5, 0, zc), P['CAM_LENS_D'] - 6, 2.0, (1, 0, 0)))
    add('lens_barrel', lens, 'lens_black', 'sensors')
    add('lens_knurl', comp(*knurl), 'lens_black', 'sensors')
    add('lens_ring', cyl((x_face + L - 4, 0, zc), P['CAM_LENS_D'] + 0.4, 1.2, (1, 0, 0)), 'alu', 'sensors')
    add('lens_glass', cq.Workplane('XY').add(cq.Solid.makeSphere(40, cq.Vector(x_face + L - 1.5 - 39.2, 0, zc), angleDegrees1=-90, angleDegrees2=90))
        .intersect(cyl((x_face + L - 4, 0, zc), P['CAM_LENS_D'] - 6, 3, (1, 0, 0))), 'glass', 'sensors')
    # M12 X-coded plug on the back (kit.camera_plug), then the cable (extras.cable_defs)
    pz, py = zc, 6.0
    nut = cyl((x0, py, pz), 16.0, 12.0, (-1, 0, 0))
    bodyp = cq.Workplane('XY').add(cq.Solid.makeCone(7.4, 4.2, 36.0, cq.Vector(x0 - 12, py, pz), cq.Vector(-1, 0, 0)))
    add('camera_plug_nut', nut, 'nickel', 'sensors')
    add('camera_plug_body', bodyp, 'cable_green', 'sensors')
    m8 = cyl((x0, -7.0, pz - 6), 8.0, 4.0, (-1, 0, 0))
    add('camera_m8', m8, 'nickel', 'sensors')


# ----------------------------------------------------------------------------- stack stand-ins
def standoffs(points, z0, z1, name, group):
    s = [cq.Workplane('XY').polygon(6, 5.5 / math.cos(math.radians(30))).extrude(z1 - z0).translate((x, y, z0)) for (x, y) in points]
    add(name, comp(*s), 'brass', group)


def jetson():
    """Orin Nano module on its SO-DIMM with the dev kit's heatsink and fan (stand-in, kit.py envelope)"""
    x0, x1, y0, y1 = extras.JETSON_BOX
    zt = extras.Z_BRAIN_TOP
    sock = box(x0 - 4, x1 + 4, y1 - 9, y1 + 5, zt, zt + 5.5)
    add('sodimm_socket', sock, 'plastic_black', 'brain')
    pcb = box(x0, x1, y0, y1, zt + 4.5, zt + 5.7)
    add('module_pcb', pcb, 'pcb_dark', 'brain')
    plate = box(x0 + 2, x1 - 2, y0 + 1, y1 - 1, zt + 5.7, zt + 10.0).edges('|Z').fillet(1.5)
    fins = [box(x0 + 3 + 2.2 * i, x0 + 4.2 + 2.2 * i, y0 + 1.5, y1 - 1.5, zt + 10.0, zt + 23.0) for i in range(int((x1 - x0 - 6) / 2.2))]
    add('jetson_heatsink', comp(plate, *fins), 'anodized_dark', 'brain')
    fx, fy = extras.FAN_C
    shroud = box(x0 + 8, x1 - 8, y0 + 2, y1 - 2, zt + 23.0, extras.Z_SINK_TOP).edges('|Z').fillet(3)
    shroud = shroud.cut(cylz(fx, fy, zt + 23.5, extras.Z_SINK_TOP + 1, 38.0))
    add('jetson_fan_frame', shroud, 'plastic_black', 'brain')
    blades = []
    for i in range(7):
        b = box(4.0, 18.5, -3.2, 3.2, 0, 1.2).rotate((0, 0, 0), (1, 0, 0), 25).rotate((0, 0, 0), (0, 0, 1), 360 / 7 * i)
        blades.append(b.translate((fx, fy, extras.Z_SINK_TOP - 5.0)))
    hub = cylz(fx, fy, extras.Z_SINK_TOP - 7.0, extras.Z_SINK_TOP - 2.5, 14.0)
    add('jetson_fan_rotor', comp(hub, *blades), 'plastic_black', 'brain')
    # the M.2 Wi-Fi card under the module and the NVMe under the brain board
    add('wifi_card', box(16.0, 46.0, -52.0, -30.0, zt + 1.2, zt + 2.2), 'pcb_dark', 'brain')
    add('nvme_card', box(-29.2, 51.2, -43.1, -20.8, extras.Z_BRAIN_BOT - 2.3, extras.Z_BRAIN_BOT - 1.5), 'pcb_black', 'brain')
    add('nvme_label', box(-20.0, 30.0, -41.0, -23.0, extras.Z_BRAIN_BOT - 2.6, extras.Z_BRAIN_BOT - 2.3), 'label_white', 'brain')


def rj45_jack(x0, x1, y0, y1, open_sign, name):
    zt = extras.Z_BRAIN_TOP
    j = box(x0, x1, y0, y1, zt, zt + 13.5)
    yf = y0 if open_sign < 0 else y1
    mouth = box((x0 + x1) / 2 - 6.0, (x0 + x1) / 2 + 6.0, yf - 16 if open_sign > 0 else yf - 0.1, yf + 0.1 if open_sign > 0 else yf + 16,
                zt + 2.0, zt + 10.8)
    add(name, j.cut(mouth), 'nickel', 'brain')
    leds = [box(x, x + 2.5, yf - 0.4 if open_sign > 0 else yf - 0.1, yf + 0.1 if open_sign > 0 else yf + 0.4, zt + 11.2, zt + 12.6)
            for x in ((x0 + 1.2), (x1 - 3.7))]
    add(name + '_leds', comp(*leds), 'led_green', 'brain')


def rj45_plug(jack_x, jack_y, sign, boot_mat, name):
    z = extras.RJ45_Z
    ya, yb = sorted((jack_y, jack_y + sign * 21.0))
    yc, yd = sorted((jack_y + sign * 21.0, jack_y + sign * 32.0))
    body = box(jack_x - 6.0, jack_x + 6.0, ya, yb, z - 4.0, z + 4.0)
    boot = box(jack_x - 6.8, jack_x + 6.8, yc, yd, z - 4.8, z + 4.8).edges('|Y').fillet(2)
    add(name + '_body', body, 'clear_plastic', 'brain')
    add(name + '_boot', boot, boot_mat, 'brain')


def stack_header():
    # drive board socket (Samtec SSQ, 8.5 mm) and the brain board header's insulator and pins
    add('stack_socket', box(0.0, 51.0, -13.5, -8.5, extras.Z_DRIVE_TOP, extras.Z_DRIVE_TOP + 8.5), 'plastic_black', 'drive')
    add('stack_header_body', box(0.0, 51.0, -13.5, -8.5, extras.Z_BRAIN_BOT - 2.5, extras.Z_BRAIN_BOT), 'plastic_black', 'brain')
    pins = [box(1.0 + 2.54 * i - 0.32, 1.0 + 2.54 * i + 0.32, yy - 0.32, yy + 0.32, extras.Z_DRIVE_TOP + 8.5, extras.Z_BRAIN_BOT - 2.5)
            for i in range(20) for yy in (-12.2, -9.8)]
    add('stack_header_pins', comp(*pins), 'gold', 'brain')


def side_fan():
    """Noctua NF-A4x10 5V PWM (the BOM's fan): 40 x 40 x 10, beige frame, brown blades"""
    f0, f1 = kit.FAN_X
    xc, zc = (f0 + f1) / 2, 22.0
    y0, y1 = -88.4, -78.4
    frame = box(f0, f1, y0, y1, zc - 20, zc + 20).edges('|Y').fillet(3)
    frame = frame.cut(cyl((xc, y0 - 1, zc), 38.0, 12.0, (0, 1, 0)))
    for dx in (-16, 16):
        for dz in (-16, 16):
            frame = frame.cut(cyl((xc + dx, y0 - 1, zc + dz), 3.4, 12.0, (0, 1, 0)))
    add('side_fan_frame', frame, 'noctua_beige', 'deck')
    hub = cyl((xc, y0 + 1, zc), 16.0, 8.0, (0, 1, 0))
    blades = []
    for i in range(9):
        b = box(-1.5, 1.5, y0 + 2.0, y1 - 2.0, 8.0, 18.5).rotate((0, (y0 + y1) / 2, 0), (0, (y0 + y1) / 2 + 1, 0), 0)
        b = b.rotate((0, (y0 + y1) / 2, 0), (0, (y0 + y1) / 2, 1), 22)   # blade pitch
        b = b.rotate((0, 0, 0), (0, 1, 0), 40 * i).translate((xc, 0, zc))
        blades.append(b)
    add('side_fan_rotor', comp(hub, *blades), 'noctua_brown', 'deck')


ANTENNA_TILT = 25.0          # degrees back from vertical, as fitted


def antenna_hinge():
    """Both knuckles sit on one line parallel to y: x of the jacks, 12 mm above the canopy top."""
    return dict(x=extras.ANTENNAS[0][0], z=extras.Z_CANOPY + extras.CANOPY_T + 12.0, tilt=ANTENNA_TILT)


def antennas_detail(tilt=ANTENNA_TILT):
    parts = []
    nuts = []
    for (x, y) in extras.ANTENNAS:
        z0 = extras.Z_CANOPY + extras.CANOPY_T
        nuts.append(cq.Workplane('XY').polygon(6, 8.0 / math.cos(math.radians(30))).extrude(2.0).translate((x, y, z0)))
        nuts.append(cylz(x, y, z0 + 2.0, z0 + 9.0, 6.4))
        piv = (x, y, z0 + 12.0)
        base = cylz(x, y, z0 + 8.0, z0 + 16.0, 10.0)
        knuckle = cyl((x, y - 5.0, z0 + 13.0), 10.0, 10.0, (0, 1, 0))
        whip = cq.Workplane('XY').add(cq.Solid.makeCone(4.6, 3.6, extras.ANTENNA_L - 18.0, cq.Vector(x, y, z0 + 16.0), cq.Vector(0, 0, 1)))
        tip = cq.Workplane('XY').add(cq.Solid.makeSphere(3.6, cq.Vector(x, y, z0 + extras.ANTENNA_L - 2.0)))
        a = comp(base, whip, tip)
        a = a.rotate(piv, (piv[0], piv[1] + 1, piv[2]), -tilt)
        parts.append(comp(a, knuckle))
    add('antenna_jacks_top', comp(*nuts), 'gold', 'canopy')
    add('antennas', comp(*parts), 'rubber_matte', 'canopy')


# ----------------------------------------------------------------------------- build the whole scene
MATERIAL_OF_PART = {'cells_4s3p': 'cell_wrap'}


def build():
    kb, new_parts, new_comps, cables, stand, _ = extras.build()
    S, comps, parts, ex, info = kb
    # the printed kit (PETG-CF)
    groups = {'deck_rear': 'deck', 'deck_mid': 'deck', 'deck_front': 'deck', 'side_pod_left': 'deck', 'side_pod_right': 'deck',
              'wing_strut_left': 'deck', 'wing_strut_right': 'deck', 'wing_blade': 'deck', 'bumper': 'deck', 'lidar_plinth': 'deck',
              'camera_arch': 'deck', 'camera_cradle': 'deck', 'pack_box': 'pack', 'pack_lid': 'pack', 'cell_holder_bottom': 'pack',
              'cell_holder_top': 'pack'}
    for name, p in parts.items():
        if name.startswith('splice'):
            groups[name] = 'deck'
        add(name, p, 'petg_cf', groups.get(name, 'deck'))
    add('stack_canopy', new_parts['stack_canopy'], 'petg_cf', 'canopy')
    washers = [ex['post_washer'].translate((x, s * y, 0.0)) for (x, y) in (P['FRONT_POST'], P['REAR_POST']) for s in (1, -1)]
    add('post_washers', comp(*washers), 'petg_cf', 'deck')
    # bought parts kept from kit.py's envelopes
    add('heat_spreader', comps['esc_heatsink'], 'alu', 'drive')
    standoffs(kit.DRIVE_HOLES, 0.0, P['DRIVE_Z'], 'standoffs_7mm', 'drive')
    standoffs(kit.BRAIN_HOLES, extras.Z_DRIVE_TOP, extras.Z_BRAIN_BOT, 'standoffs_20mm', 'brain')
    standoffs(extras.CANOPY_POSTS, extras.Z_BRAIN_TOP, extras.Z_CANOPY, 'standoffs_40mm', 'canopy')
    screws = [cylz(x, y, extras.Z_CANOPY + extras.CANOPY_T, extras.Z_CANOPY + extras.CANOPY_T + 1.7, 5.7) for (x, y) in extras.CANOPY_POSTS]
    add('canopy_screws', comp(*screws), 'steel_black', 'canopy')
    add('cells', comps['cells_4s3p'], 'cell_wrap', 'pack')
    tim561()
    triton()
    jetson()
    rj45_jack(-39.4, -21.6, -73.9, -51.9, -1, 'rj45_camera_jack')
    rj45_jack(53.2, 69.6, -6.0, 15.8, +1, 'rj45_lidar_jack')
    rj45_plug(extras.CAM_JACK[0], extras.CAM_JACK[1], -1, 'cable_green', 'rj45_camera_plug')
    rj45_plug(extras.LID_JACK[0], extras.LID_JACK[1], +1, 'cable_grey', 'rj45_lidar_plug')
    stack_header()
    side_fan()
    antennas_detail()
    chassis()
    return cables, stand


CABLE_MATERIAL = {'camera': 'cable_green', 'lidar_ethernet': 'cable_grey', 'lidar_power': 'cable_grey',
                  'motor_A': 'wire_black', 'motor_B': 'wire_black', 'motor_C': 'wire_black', 'hall': 'wire_grey',
                  'servo': 'wire_black', 'pack_plus': 'wire_red', 'pack_minus': 'wire_black', 'pack_sense': 'wire_white',
                  'side_fan': 'wire_black', 'wifi_1': 'cable_black', 'wifi_2': 'cable_black'}
CABLE_GROUP = {'camera': 'cable_cam', 'lidar_ethernet': 'cable', 'lidar_power': 'cable', 'wifi_1': 'cable_canopy', 'wifi_2': 'cable_canopy'}


def export():
    cables, stand = build()
    man = {'objects': [], 'cables': [], 'boards': {}, 'units': 'mm'}
    for name, shape, mat, group in OBJ:
        path = os.path.join(SCENE, name + '.stl')
        cq.exporters.export(shape, path, tolerance=0.08, angularTolerance=0.12)
        man['objects'].append(dict(name=name, file=name + '.stl', material=mat, group=group))
    for k, c in cables.items():
        man['cables'].append(dict(name=k, d=c['d'], material=CABLE_MATERIAL.get(k, 'wire_black'),
                                  group=CABLE_GROUP.get(k, 'cable'), pts=[[round(v, 3) for v in p] for p in c['path']]))
    cq.exporters.export(stand, os.path.join(SCENE, 'bench_stand.stl'), tolerance=0.08, angularTolerance=0.12)
    man['stand'] = dict(file='bench_stand.stl', material='pla_grey')
    man['boards'] = {'drive': dict(glb='boards/drive/out/render/atlas_drive.glb', at=[P['DRIVE'][0], P['DRIVE'][2], P['DRIVE_Z']]),
                     'brain': dict(glb='boards/brain/out/render/atlas_brain.glb', at=[P['BRAIN'][0], P['BRAIN'][2], extras.Z_BRAIN_BOT])}
    man['ground_z'] = Z_GROUND
    man['focus'] = [10.0, 0.0, -40.0]
    man['antenna_hinge'] = antenna_hinge()
    json.dump(man, open(os.path.join(SCENE, 'scene.json'), 'w'), indent=1)
    print(len(man['objects']), 'objects,', len(man['cables']), 'cables ->', SCENE)


if __name__ == '__main__':
    export()
