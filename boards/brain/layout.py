"""ATLAS-BRN-1 placement and copper for the Atlas parts (tools/placer.py -> tools/fork_pcb.py).

Board-local mm, top view: X forward from the rear edge, Y toward the car's left from the I/O edge
(Antmicro's connector edge). Antmicro's board is X 0-120, Y 0-60; the new strip is Y 60-90.

  Y 90 +--------------------------------------------------------------------------------------+
       | H1001 (6,84)                                    LIDAR RJ45 (opens to car-left)  H1002  |
       | 52 V bulk   eFuse    NTS0102      level/FETs      LAN7800 + 25 MHz                   |
  Y 60 | POE_OUTPUT pour ==== stack header J1001 (bottom), X 41-90 ============                |
       | boost (LM5155)  |  Jetson Orin module on the SO-DIMM (Antmicro)          | M.2 E      |
       | PSE (TPS23861)  |                                                         |            |
       | camera RJ45 J6  |                                                         |            |
  Y 0  +--------------------------------------------------------------------------------------+
       X 0 (rear)                                                                        X 120

Antmicro's own parts are obstacles here (out/atlas_brain_obstacles.json, written by fork_pcb.py --geom).
"""
import json
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'stack'))
import stack  # noqa: E402

NAME = 'atlas_brain'
SIZE = (120.0, 90.0)
COPPER_LAYERS = 8
AUTO_MARGIN = 0.25
IC_RING = 0.6
RAILS = ['GND', '+3V3', '+1V8', 'POE_OUTPUT', 'STK_VSYS', 'POE_52V', 'LAN_1V2', 'LAN_2V5', '3V3_STDB']

# Antmicro parts that stay: nothing new goes on top of them (both sides for through-hole parts)
NO_AUTO = []
_obs = os.path.join(HERE, 'out', NAME + '_obstacles.json')
if os.path.exists(_obs):
    for o in json.load(open(_obs)):
        x0, y0, x1, y1 = o['crt']
        sides = ('F', 'B') if o['pth'] else (o['side'],)
        for s in sides:
            NO_AUTO.append((s, x0, y0, x1, y1))
        for h in o['holes']:
            (cx, cy), r = h['c'], h['r'] + 0.3
            for s in ('F', 'B'):
                NO_AUTO.append((s, cx - r, cy - r, cx + r, cy + r))
# Antmicro copper that stays on the outer layers (after fork_pcb.py trims the stubs): tracks and power
# pours block their own side, vias both sides
_cu = os.path.join(HERE, 'out', NAME + '_copper_obstacles.json')
if os.path.exists(_cu):
    _c = json.load(open(_cu))
    for t in _c['tracks']:
        (ax, ay), (bx, by), w = t['a'], t['b'], t['w'] / 2 + 0.15
        NO_AUTO.append((t['layer'], min(ax, bx) - w, min(ay, by) - w, max(ax, bx) + w, max(ay, by) + w))
    for v in _c['vias']:
        r = v['r'] + 0.15
        for s_ in ('F', 'B'):
            NO_AUTO.append((s_, v['x'] - r, v['y'] - r, v['x'] + r, v['y'] + r))
    for z in _c['zones']:
        x0, y0, x1, y1 = z['bb']
        NO_AUTO.append((z['layer'], x0, y0, x1, y1))
NO_AUTO += [
    ('F', 0.0, 0.0, 120.0, 0.6), ('B', 0.0, 0.0, 120.0, 0.6),       # board edges
    ('F', 0.0, 89.4, 120.0, 90.0), ('B', 0.0, 89.4, 120.0, 90.0),
    ('F', 0.0, 57.9, 120.0, 60.4), ('B', 0.0, 57.9, 120.0, 60.4),   # Antmicro's routing along the old edge
]

# parts the automatic placer must put on a given side
SIDE = {}

_placed = []


def placed_refs():
    return list(_placed)


def place_all(B):
    def pl(ref, x, y, rot=0, side='F'):
        B.place(ref, x, y, rot, side)
        _placed.append(ref)

    def ctr(ref, x, y, rot=0, side='F'):
        B.centre(ref, x, y, rot, side)
        _placed.append(ref)

    def fc(ref, x, y, pads, direction, side='F'):
        B.face(ref, x, y, pads, direction, side)
        _placed.append(ref)

    def fn(ref, x, y, net, direction, side='F'):
        """orient a part so that its pads on `net` point in `direction`"""
        pads = [n for n, v in B.parts[ref]['pads'].items() if v == net]
        if not pads:
            raise KeyError(f'{ref} has no pad on {net}')
        fc(ref, x, y, pads, direction, side)

    # ------------------------------------------------ stack header (bottom): pad 1 at pin 1 of stack.py
    x1, y1 = stack.pin_xy_brain(1)
    x2, y2 = stack.pin_xy_brain(2)
    x3, y3 = stack.pin_xy_brain(3)
    best = None
    for rot in (0, 90, 180, 270):
        B.anchor_pad('J1001', '1', x1, y1, rot, 'B')
        p2, p3 = B.pad_xy('J1001', '2'), B.pad_xy('J1001', '3')
        err = abs(p2[0] - x2) + abs(p2[1] - y2) + abs(p3[0] - x3) + abs(p3[1] - y3)
        if best is None or err < best[0]:
            best = (err, rot)
    if best[0] > 0.01:
        raise SystemExit(f'stack header pins do not line up ({best[0]:.3f} mm off)')
    B.anchor_pad('J1001', '1', x1, y1, best[1], 'B')
    _placed.append('J1001')
    pl('H1001', 6.0, 84.0)
    pl('H1002', 114.0, 84.0)

    # ------------------------------------------------ stack helpers (top, over the header, and bottom by Q7)
    pl('U1001', 52.0, 68.0, 90)            # UART1 translator between the module pins and header pins 15/16
    pl('Q1002', 65.4, 68.0, 0)             # OS_HALTED from POWER_EN, next to header pin 22
    pl('Q1003', 70.0, 68.0, 0)             # STM32 reset, next to header pin 24
    pl('R1002', 74.4, 68.0, 90)            # CHG_STAT pull-up at pin 27
    pl('R1003', 80.8, 68.0, 90)            # CAN series resistors at pins 33/34
    pl('R1004', 83.2, 68.0, 90)
    pl('Q1001', 34.5, 63.0, 0, 'B')        # power button P-FET under the strip, near Antmicro Q7
    pl('Q1004', 30.5, 63.0, 0, 'B')        # SLEEP/WAKE* pull-down

    # ------------------------------------------------ input eFuse (top, left of the VSYS header pins)
    # Turned so its two long pads run left-right: IN (pin 5) leaves to the right into the VSYS pour,
    # OUT (pin 6) to the left into the POE_OUTPUT pour; input caps sit in the one, output caps in the other.
    pl('U1101', 36.0, 67.5, 90)
    fn('C1103', 43.5, 67.3, 'STK_VSYS', 'left')           # above the header's VSYS pins (their pads reach Y 64.6)
    fn('C1104', 43.5, 69.7, 'STK_VSYS', 'left')
    fn('C1105', 38.9, 67.25, 'STK_VSYS', 'left')
    fn('C1106', 31.0, 63.2, 'POE_OUTPUT', 'right')
    fn('C1107', 25.4, 63.2, 'POE_OUTPUT', 'right')
    fn('C1108', 33.0, 66.3, 'POE_OUTPUT', 'right')

    # ------------------------------------------------ 52 V boost (top, strip rear end, above the POE_OUTPUT pour)
    #   inductor pad 1 sits on the pour; its pad 2, the FET drain and the diode anode make the switch node
    pl('L1201', 13.5, 70.0, 90)            # 47 uH
    pl('D1201', 21.6, 72.6, 180)           # anode (left) on the switch node, cathode right
    pl('Q1201', 13.5, 76.3, 270)           # drain down to the switch node, sources and gate up
    pl('R1201', 14.2, 80.9, 90)            # 25 mOhm sense above the sources, GND end up
    pl('U1201', 9.0, 77.5, 180)            # LM5155: GATE/PGND/CS face the FET, the small parts go left
    pl('C1209', 10.0, 74.925, 180)         # its VCC cap right under the VCC pin, in the corner the inductor,
                                           # the FET and the controller leave (their courtyards fit it exactly)
    # the controller's small parts where the automatic placer put them before the VCC cap moved in (the
    # board is routed around them)
    pl('C1206', 7.25, 72.75, 90)
    pl('C1207', 4.0, 75.5, 90)
    pl('C1210', 2.0, 81.25, 90)
    pl('C1211', 16.25, 84.75, 90)
    pl('C1212', 16.5, 81.5, 90)
    pl('C1215', 2.25, 72.0, 0)
    pl('R1203', 4.5, 79.25, 0)
    pl('R1204', 11.0, 85.25, 90)
    pl('R1205', 2.0, 79.0, 0)
    pl('R1206', 4.5, 71.5, 90)
    pl('R1207', 1.5, 75.25, 90)
    pl('R1208', 14.25, 84.25, 0)
    for i, ref in enumerate(('C1202', 'C1203', 'C1204')):
        pl(ref, 22.0, 76.8 + 3.5 * i, 0)   # 2.2 uF 100 V above the diode cathode
    pl('C1205', 30.6, 84.5, 0)             # 22 uF 100 V can
    pl('D1202', 29.0, 76.0, 0)             # 52 V system TVS

    # ------------------------------------------------ PSE (top, behind the camera jack J6)
    pl('D1203', 5.0, 24.4, 0)              # port TVS DP1A by the jack's centre-tap pins
    pl('Q1202', 4.0, 28.9, 0)              # port 1 switch
    pl('U1202', 14.0, 31.5, 90)            # TPS23861
    # the jack-side parts sit right above the jack: 0R into the 1-2 centre tap (pin 11), Bob Smith
    # termination of the unused 4-5 / 7-8 centre taps (pins 13, 14)
    fn('R1214', 10.1, 24.5, 'POE_PAIR_12', 'down')
    fn('R1215', 13.6, 23.52, 'POE_PAIR_78', 'down')
    fn('R1216', 15.4, 23.52, 'POE_PAIR_910', 'down')
    fn('C1217', 14.6, 26.26, 'BS_CAM', 'left')

    # ------------------------------------------------ lidar Ethernet (top, front of the strip)
    ctr('J1301', 101.4, 78.9, 180)         # opens to the car-left edge, clear of H1002
    # LAN7800 turned so its MDI pins (1-12) face the jack and its USB 2 pins face the module. Every part
    # of the block is placed by hand around it: each side keeps a 1.1-1.3 mm strip next to the pin row
    # for the fan-out, and the MDI side keeps the corridor to the jack free on the top side.
    pl('U1301', 84.0, 76.5, 180)
    lan = {
        # north, pins 13-24: the 1.2 V switcher (pin 13) and the caps of pins 14, 20, 21, 23;
        # LED0/LED1/EEDI leave between C1316 and C1312
        'C1317': (81.2, 82.6, 90, 'F'), 'C1302': (82.25, 82.6, 90, 'F'), 'C1316': (83.3, 82.6, 90, 'F'),
        'C1312': (85.6, 82.9, 90, 'F'), 'L1301': (88.9, 83.4, 0, 'F'), 'C1301': (89.6, 86.0, 0, 'F'),
        'C1306': (86.9, 86.0, 0, 'F'), 'R1305': (84.3, 82.6, 90, 'B'),
        'R1311': (91.9, 83.3, 180, 'F'), 'R1310': (91.9, 84.4, 180, 'F'),
        # south, pins 37-48: bias and reference parts, the 2.5 V LDO cap (pin 45); XI/XO drop to the
        # crystal on the bottom between C1313 and C1305 (the stack header's CAN resistors sit above it)
        'R1301': (80.95, 70.4, 270, 'F'), 'C1313': (82.0, 70.4, 270, 'F'), 'C1305': (84.05, 70.4, 270, 'F'),
        'C1307': (85.1, 70.4, 270, 'F'), 'C1314': (86.15, 70.4, 270, 'F'), 'R1302': (87.2, 70.4, 270, 'F'),
        'C1318': (88.25, 70.4, 270, 'F'),
        'Y1301': (83.2, 70.4, 0, 'B'), 'C1320': (80.0, 69.55, 180, 'B'), 'C1321': (86.4, 71.25, 0, 'B'),
        'R1304': (86.4, 69.6, 0, 'B'),
        # west, pins 25-36: 1.2 V pins 25 and 30, reset, 3.3 V pin 36; the USB 2 pair leaves between C1303
        # and C1304
        'C1303': (78.4, 80.1, 180, 'F'), 'C1304': (78.4, 76.75, 180, 'F'), 'C1319': (78.4, 75.35, 180, 'F'),
        'R1303': (78.4, 74.25, 0, 'F'), 'C1315': (78.4, 73.15, 180, 'F'),
        # east: the VDD25A caps (pins 3, 6, 9, 12) on the bottom, under the 2.5 V via column (copper())
        'C1308': (89.6, 74.75, 0, 'B'), 'C1309': (89.6, 76.25, 0, 'B'), 'C1310': (89.6, 77.75, 0, 'B'),
        'C1311': (89.6, 79.25, 0, 'B'),
        # jack side: shield cap and two Bob Smith resistors out of the MDI corridor (bottom, under the jack)
        'C1324': (92.2, 78.6, 90, 'F'), 'R1309': (98.0, 74.25, 0, 'B'), 'R1308': (101.4, 74.25, 0, 'B'),
        'C1322': (103.0, 66.25, 0, 'F'), 'C1323': (113.75, 75.25, 90, 'F'), 'R1306': (111.25, 75.0, 90, 'F'),
        'R1307': (112.0, 79.0, 0, 'F'), 'R1312': (111.0, 72.0, 90, 'F'),
    }
    for ref, (x, y, rot, side) in lan.items():
        pl(ref, x, y, rot, side)


def copper(B, C):
    """pours for the power paths that the router should not have to guess"""
    from shapely.geometry import box
    from shapely.ops import unary_union
    W, H = SIZE
    # eFuse long pads: pad-wide necks out of the pad row into the two pours (pours cannot reach in)
    C.track([(36.8, 67.25), (38.6, 67.25)], 0.3, 'F', 'STK_VSYS')
    C.track([(35.2, 67.75), (33.5, 67.75), (33.5, 65.3)], 0.3, 'F', 'POE_OUTPUT')
    # STK_VSYS: header pins 1-6 to the eFuse input, top and bottom
    C.zone('P:VSYS_F', 'STK_VSYS', 'F', box(38.4, 60.6, 48.1, 71.2), priority=5, clearance=0.25,
           min_width=0.25, connect='full')
    C.zone('P:VSYS_B', 'STK_VSYS', 'B', box(40.2, 60.6, 48.1, 64.9), priority=5, clearance=0.25,
           min_width=0.25, connect='full')
    # POE_OUTPUT: eFuse output along the old board edge to the boost inductor, and down onto Antmicro's
    # POE_OUTPUT pour on the bottom (ideal diode Q16/Q14 to the module supply)
    lx, ly = B.pad_xy('L1201', '1')
    poe = unary_union([box(3.4, 60.6, 34.0, 65.6), box(lx - 2.2, 60.6, lx + 2.2, ly + 1.2)])
    C.zone('P:POE_OUT_F', 'POE_OUTPUT', 'F', poe, priority=5, clearance=0.25, min_width=0.25, connect='full')
    for x in (4.2, 5.2, 6.2, 7.2):
        for y in (61.4, 62.4):
            C.via(x, y, 'POE_OUTPUT', 0.3, 0.6)
    C.zone('P:POE_OUT_B', 'POE_OUTPUT', 'B', box(0.8, 57.5, 12.0, 64.0), priority=5, clearance=0.25,
           min_width=0.25, connect='full')
    # LAN7800 VDD25A pins (3, 6, 9, 12) sit between the MDI pairs: straight out to a via each, their
    # 100 nF caps right under the via column on the bottom
    for pin in ('3', '6', '9', '12'):
        px, py = B.pad_xy('U1301', pin)
        C.track([(px, py), (88.55, py)], 0.2, 'F', 'LAN_2V5')
        C.via(88.55, py, 'LAN_2V5', 0.2, 0.45, check=False)
    # boost switch node: inductor pad 2, FET drain, diode anode and the necks between them. Not their
    # convex hull: that takes in the corner left of the FET, where the VCC cap and its track are
    qb = C.pad_box('Q1201', '5', 0.3).bounds
    lb = C.pad_box('L1201', '2', 0.3).bounds
    db = C.pad_box('D1201', '2', 0.3).bounds
    sw = unary_union([box(*qb), box(*lb), box(*db),
                      box(qb[0], lb[3] - 0.1, qb[2], qb[1] + 0.1),
                      box(lb[2] - 0.1, max(lb[1], db[1]), db[0] + 0.1, min(lb[3], db[3]))])
    C.zone('P:BST_SW_F', 'BST_SW', 'F', sw, priority=6, clearance=0.4, min_width=0.25, connect='full')
    # GND planes in the strip on every inner layer, overlapping Antmicro's planes by 1.5 mm so they join.
    # In1/2/4/6 are Antmicro's plane layers (not routed); In3/In5 carry signals, so there it is a fill.
    inner = box(0.3, 58.5, W - 0.3, H - 0.3)
    for lay in ('In1', 'In2', 'In4', 'In6'):
        C.zone(f'P:GND_{lay}_STRIP', 'GND', lay, inner, priority=9, clearance=0.2, min_width=0.2, connect='tht')
    for lay in ('In3', 'In5'):
        C.zone(f'F:GND_{lay}_STRIP', 'GND', lay, inner, priority=9, clearance=0.2, min_width=0.2, connect='tht',
               dsn=False)
    # GND on both outer layers over the strip (fills after routing)
    strip = box(0.3, 60.3, W - 0.3, H - 0.3)
    C.zone('F:GND_F_STRIP', 'GND', 'F', strip, priority=0, clearance=0.25, min_width=0.2, connect='thermal', dsn=False)
    C.zone('F:GND_B_STRIP', 'GND', 'B', strip, priority=0, clearance=0.25, min_width=0.2, connect='thermal', dsn=False)


def _router_keepouts(C):
    """same trick as the drive board: the autorouter must not run foreign tracks through the pours"""
    from shapely.geometry import Polygon
    for z in list(C.zones):
        if z['name'].startswith('P:') and z['layer'] in ('F', 'B'):
            for i, rings in enumerate(z['rings']):
                g = Polygon(rings[0], rings[1:]).buffer(-0.6, 8)
                pieces = [g] if g.geom_type == 'Polygon' else list(getattr(g, 'geoms', []))
                for j, piece in enumerate(pieces):
                    if piece.area > 1.0:
                        C.keepout(f"D:{z['name'][2:]}_{i}_{j}", [z['layer']], piece, tracks=True, vias=z['net'] != 'GND')


_copper_zones = copper


def copper(B, C):      # noqa: F811
    _copper_zones(B, C)
    _router_keepouts(C)


PLANE_LAYERS = ('In1', 'In2', 'In4', 'In6')


def dsn_prep(b, pcbnew):
    """before the Specctra export (tools/dsn_export.py): Antmicro's plane layers become power layers the
    router does not use, and every Antmicro pour on the routing layers gets the inset keepout the Atlas
    pours have (so new tracks stay out of them; new vias may still pass through the GND ones)."""
    from pcbnew import FromMM as MM
    lay = {'In1': pcbnew.In1_Cu, 'In2': pcbnew.In2_Cu, 'In4': pcbnew.In4_Cu, 'In6': pcbnew.In6_Cu}
    for n in PLANE_LAYERS:
        b.SetLayerType(lay[n], pcbnew.LT_POWER)
    routing = [pcbnew.F_Cu, pcbnew.In3_Cu, pcbnew.In5_Cu, pcbnew.B_Cu]
    dropped = kept = 0
    keep = []
    for z in list(b.Zones()):
        if z.GetIsRuleArea() or z.GetZoneName().startswith(('P:', 'F:', 'D:')):
            continue
        on = [l for l in routing if z.IsOnLayer(l)]
        if not on:
            continue
        gnd = z.GetNetname() in ('GND', '')
        for l in on:
            poly = pcbnew.SHAPE_POLY_SET(z.Outline())
            strat = getattr(pcbnew, 'CORNER_STRATEGY_ROUND_ALL_CORNERS', getattr(pcbnew, 'ROUND_ALL_CORNERS', None))
            poly.Inflate(-MM(0.6), strat, MM(0.05))
            for i in range(poly.OutlineCount()):
                ra = pcbnew.ZONE(b)
                ra.SetIsRuleArea(True)
                ra.SetDoNotAllowTracks(True)
                ra.SetDoNotAllowVias(not gnd)       # new vias may pierce a GND pour, not a power pour
                ra.SetDoNotAllowPads(False)
                ra.SetDoNotAllowFootprints(False)
                ls = pcbnew.LSET()
                ls.AddLayer(l)
                ra.SetLayerSet(ls)
                ra.SetZoneName('D:am_' + z.GetNetname())
                ra.Outline().AddOutline(poly.Outline(i))     # the zone keeps its own copy of the outline
                b.Add(ra)
                keep.append(ra)
                kept += 1
    print('dsn prep: keepouts over Antmicro pours on the routing layers:', kept)
    return keep
