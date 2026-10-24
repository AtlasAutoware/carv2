"""ATLAS-PWR-1 rev B placement, copper and outline. Board-local mm, top view: X runs forward from the rear
edge, Y toward the car's left from the right (pod) edge; car (x, y) = (X - 32, Y - 68) (PHASE2.md).
Used by tools/placer.py (placement and copper JSON) and tools/build_pcb.py (inside KiCad).

130 x 84 mm (the mech kit's limit: at 150 the front edge and standoff sit in the lidar plug envelope).
Top side: every through-hole part and module. Bottom side: the 1206/1210 chips, placed by the auto placer under
through-hole bodies (SMD_UNDER_THT: on the bottom a through-hole part blocks only its pads).
The Pico and the hub stand on 8.5 mm sockets (HOLLOW): the 74HCT08 and two PC817s sit under the Pico,
the MCP2221A and its LDO under the hub. Parts under a module must be 9 mm tall or less.

Floorplan, top view (out/placement.png, out/placement_pours.png):

  Y 84 +-----------------------------------------------------------------------------------------------+
       |H  BAT+   [C101  C102  C103 on the BAT pour]  MIC5014 H  BMS XH-4     |  Pico USB    H|
       |BAT- (GND corner)   === bar (BAT+) ===          precharge  PC817 x2  DEV+-|  Pico on     |
       |ESC-      Q301   Q302   Q303 (tabs north)  Q304 F301      dev-kit fuse   J14|  sockets,    | front:
       |BEC-  VM pour: R313 lying, D301, BEC+         charge fuse  OV cut-off     |  HCT08 and   | servo, lidar,
       |ESC+                                          VM LED       220u           |  2 x PC817   | camera pads,
       |COMM SERVO_IN BEC_OUT SRV+-  PD pads CC/CV pads Q501 latch pads R-78E      |  under it    | E-stop, remote
       |FAN                                                          hub (MCP2221A under) ports  button LEDs |
  Y 0  +H------- J12 2x20 box header (ribbon) ---------- H ---- hub USB-C ---------- power button ----H+
       X 0 (rear: ESC bay)                                                               X 130 (front)

High-current path (copper(), not left to the router):
  BAT+ pad -> top BAT pour (north of the FET pin row; GND under it on the bottom, so the bulk caps sit in a tight
  BAT/GND loop) -> FET drains; FET sources -> top VM pour south of the row -> ESC+ pad at the rear edge.
  Return: ESC- pad -> GND corner (both layers) -> BAT- pad, 12 mm apart. The whole bottom under the power
  section is GND (return path under the VM pour). Gate traces leave each G pin on the bottom.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

NAME = 'atlas_power'
L_BOARD = 130.0
SIZE = (L_BOARD, 84.0)
PAGE_ORIGIN = (30.0, 30.0)
COPPER_LAYERS = 2
LAYER_TYPES = {}                 # two layers, no inner planes
CORNER_R = 2.0

HOLES = {'H1001': (4.0, 4.0), 'H1002': (4.0, 80.0), 'H1003': (75.0, 4.0), 'H1004': (75.0, 80.0),
         'H1005': (L_BOARD - 4.0, 4.0), 'H1006': (L_BOARD - 4.0, 80.0)}
AUTO_MARGIN = 0.2                # 0.4 mm between auto-placed courtyards
KEEP_AUTO = False
IC_RING = 0.4
SMD_UNDER_THT = True             # bottom chips may sit under through-hole bodies, clear of their pads
PAD_CLEAR = 0.5
HOLLOW = ('MOD701', 'MOD601')    # Pico and hub on 8.5 mm sockets: parts up to 9 mm tall go under them
try:                             # the auto placer puts each part on the side design.py gave it
    SIDE = {p['ref']: p['side'] for p in json.load(open(os.path.join(HERE, NAME + '_parts.json')))['parts']}
except (OSError, ValueError):
    SIDE = {}

# height map (mech kit.py power_zones): <= 23 mm in X 20..120 and in the Y 0..9 / 75..84 bands of the end strips;
# <= 35 mm in X 0..20 and X 120..130 for Y 9..75. Nothing on this board is taller than 23 mm (680 uF caps 21 mm).

NETCLASSES = {
    'Supply': {'width': 2.0, 'clearance': 0.3, 'via': 1.2, 'drill': 0.6, 'nets': [
        'VSYS_SW', 'VDEV_F', 'VDEV', 'LID_SW', 'LIDAR_V', 'CHG_IN', 'CHG_OUT', 'CHG_RB', 'CAM_VIN']},
    'Servo': {'width': 2.5, 'clearance': 0.3, 'via': 1.2, 'drill': 0.6, 'nets': ['SERVO_V']},
    'Pulse': {'width': 1.0, 'clearance': 0.3, 'via': 1.0, 'drill': 0.5, 'nets': ['PRE_D', 'PRE_F', 'V5_IN', 'BAT', 'VM']},
    'Power': {'width': 0.6, 'clearance': 0.3, 'via': 0.8, 'drill': 0.4, 'nets': [
        '+5V', '+3V3', 'PICO_VSYS', 'HUB_VBUS', 'CON_3V3', 'SW_GATE', 'SW_G1', 'SW_G2', 'SW_G3']},
    # USB 2.0 pairs: route coupled, short, over unbroken GND (90 Ohm is not reachable on 1.6 mm 2-layer)
    'USB': {'width': 0.4, 'clearance': 0.25, 'via': 0.8, 'drill': 0.4, 'nets': [
        'P1_DP', 'P1_DM', 'P2_DP', 'P2_DM', 'P3_DP', 'P3_DM', 'P4_DP', 'P4_DM']},
    'BMS': {'width': 0.3, 'clearance': 1.0, 'nets': ['BMS_VDD', 'BMS_TXD', 'BMS_RXD', 'BMS_GND', 'BMS_OPT1_A']},
}
RAILS = ['GND', '+3V3', '+5V', 'VM', 'BAT', 'VSYS_SW', 'HUB_VBUS']
DRU = ('(version 1)\n'
       '(rule "BMS-side domain 2 mm from everything else" (constraint clearance (min 2.0mm))'
       ' (condition "A.NetClass == \'BMS\' && B.NetClass != \'BMS\'"))\n')

# areas the automatic placer must leave empty: (side, x0, y0, x1, y1)
NO_AUTO = [
    ('F', 0.0, 36.0, 74.0, 84.0),        # power section (top): pours, FETs, heatsink, bulk caps
    ('B', 0.0, 36.0, 60.0, 84.0),        # power section (bottom): unbroken GND under BAT and VM
]

_placed = []


def placed_refs():
    return list(_placed)


def place_all(B):
    parts = B.parts

    def find(**kw):
        """the one part whose value matches kw['value'] (if given) and whose pads touch every net in kw['nets']"""
        want = set(kw.get('nets', ()))
        hits = [r for r, p in parts.items() if want <= set(p['pads'].values())
                and ('value' not in kw or p['value'] == kw['value'])
                and ('pre' not in kw or r.startswith(kw['pre']))
                and ('side' not in kw or p['side'] == kw['side'])]
        if len(hits) != 1:
            raise KeyError(f'{kw}: {hits}')
        return hits[0]

    def c(ref, x, y, rot=0, side='F'):
        """courtyard centre at (x, y)"""
        B.centre(ref, x, y, rot, side)
        _placed.append(ref)

    def pin(ref, num, x, y, rot=0, side='F'):
        """pad `num` at (x, y)"""
        B.anchor_pad(ref, num, x, y, rot, side)
        _placed.append(ref)

    # ------------------------------------------------------------ power section (rear left, Y 36..84)
    pin(find(value='BAT+'), '1', 19.5, 79.6)
    pin(find(value='BAT-'), '1', 6.25, 65.6)
    pin(find(value='ESC-'), '1', 5.0, 54.0)
    pin(find(value='ESC+'), '1', 5.0, 42.0)
    fets = sorted(r for r, p in parts.items() if p['value'] == 'IRFB7430PBF')
    for i, r in enumerate(fets):
        pin(r, '1', 15.0 + 13.0 * i, 59.5)                 # pins G D S along +X, tab north (toward the bar)
    c(find(value='HEATSINK_BAR'), 30.54, 64.42)                # front face 0.15 mm off the tab backs (closed by the bolts)
    caps = sorted(r for r, p in parts.items() if p['value'] == '680u 35V')
    for i, r in enumerate(caps):
        pin(r, '1', 28.0 + 13.0 * i, 76.0)                 # + pad on the BAT pour, - pad drops into bottom GND
    pin(find(value='1.5KE20A'), '1', 16.5, 72.6, 180)      # pack TVS: cathode on BAT, anode in the GND corner
    c(find(value='10k B3977'), 38.0, 67.9)                 # NTC bent against the bar
    c(find(pre='TP', nets=['BAT']), 22.0, 68.4)
    c('TP102', 2.6, 59.75)
    pin(find(value='IRF9Z34NPBF', nets=['PRE_D']), '1', 58.0, 59.5)
    pin(find(value='MF-R050'), '1', 61.0, 55.6, 270)       # PRE_D (top) -> PRE_F (bottom end)
    pin(find(value='10 5W'), '1', 54.5, 45.5, 180)         # precharge resistor lying on the VM pour, VM end west
    pin(find(value='1.5KE22A'), '1', 34.0, 53.4)           # VM TVS on the VM pour; anode pad drops into bottom GND
    pin(find(value='BEC+'), '1', 22.0, 42.0)               # Castle BEC input, on the VM pour
    pin(find(value='BEC-'), '1', 12.0, 50.2)               # in the GND corner
    c(find(pre='TP', nets=['VM']), 26.0, 52.6)
    c(find(value='MIC5014'), 68.5, 70.0)
    for i, r in enumerate(sorted(r for r, p in parts.items() if p['value'] == '10' and 'SW_GATE' in p['pads'].values())):
        c(r, 15.0 + 13.0 * i, 63.6, 270, 'B')              # bottom, north of each G pin, SW_GATE runs east at Y 66
    c(find(value='1u 50V', nets=['BAT']), 30.5, 71.6, 0, 'B')   # under C101: HF bypass across its pins
    c(find(value='2N3904', nets=['PRE_C']), 60.0, 40.2)
    c(find(value='RED', nets=['VM_LED_A']), 60.5, 45.0)

    # ------------------------------------------------------------ rear edge (X = 0): fan, ESC COMM, BEC
    pin(find(value='FAN'), '1', 3.6, 9.6, 90)
    pin(find(value='FSESC_COMM'), '1', 2.7, 21.6, 90)
    pin(find(value='SERVO_IN'), '1', 9.2, 34.5)
    pin(find(value='BEC_OUT'), '1', 9.2, 25.2)
    pin(find(value='SRV+'), '1', 14.6, 33.0)
    pin(find(value='SRV-'), '1', 14.6, 26.8)
    c(find(value='2N7000'), 10.6, 14.6)
    c(find(pre='TP', nets=['FAN_TACH']), 14.0, 20.4)

    # ------------------------------------------------------------ Y = 0 edge: J12 ribbon, hub, button
    pin(find(value='J12_RIBBON'), '1', 17.0, 6.0, 90)      # 2x20 box header, rows along X
    c(find(value='ADA5997_CH334F_HUB'), 88.5, 15.0, 180)   # its USB-C at the board edge = laptop port
    c(find(value='MCP2221A'), 88.5, 16.0, 180)             # under the hub, D+/D- (pins 13/12) beside hub port 2
    c(find(value='MCP1700-3302E/TO'), 88.5, 3.6)          # under the hub
    pin(find(value='DEVKIT_USB'), '1', 100.6, 13.4)        # hub port 1 (right column, low)
    pin(find(value='VESC_USB'), '1', 104.5, 13.4)          # hub port 3 (right column, high)
    pin(find(value='HUB_PORT4'), '1', 77.4, 21.4)          # hub port 4 (left column); port 2 = MCP2221A under the hub
    pin(find(value='POWER'), '1', 115.0, 5.6, 180)         # right-angle: plunger out of the Y=0 edge

    # ------------------------------------------------------------ charge, latch, 5 V (X 14..74, Y 14..36)
    c(find(value='ADA5807_HUSB238'), 21.0, 22.0)           # PD trigger wire pads (module in the pod)
    c(find(value='P6KE24A'), 21.0, 31.2, 90)
    c(find(value='CCCV_BUCK_XL4015'), 28.6, 25.0)
    c(find(value='1N5247B'), 34.0, 31.6, 90)
    c(find(value='2N3904', nets=['CHG_C']), 38.4, 32.6)
    c(find(value='2N3904', nets=['CHG_PRESENT_N']), 41.0, 18.6)
    c(find(value='IRF9Z34NPBF', nets=['CHG_OUT']), 40.0, 25.5)
    c(find(value='5A mini', nets=['CHG_RB']), 70.0, 46.7, 90)   # into the BAT pour at its north end
    c(find(pre='TP', nets=['CHG_IN']), 34.2, 18.6)
    c(find(value='POLOLU_2813'), 50.0, 25.0)
    c(find(value='2N3904', nets=['BUTTON_N']), 57.2, 32.6)
    c(find(value='R-78E5.0-1.0'), 62.5, 18.2)
    c(find(value='10', nets=['V5_IN']), 63.0, 25.6)
    c(find(value='P6KE20A', nets=['V5_IN']), 71.6, 19.0, 90)
    c(find(value='1N5817'), 70.2, 26.6, 90)
    c(find(value='GREEN', nets=['LED5_A']), 69.6, 33.4)
    c(find(pre='TP', nets=['+5V']), 73.9, 24.6)
    c(find(pre='TP', nets=['VSYS_SW']), 62.4, 32.6)

    # ------------------------------------------------------------ middle right: J14, BMS, dev-kit feed
    pin(find(value='J14_HARNESS'), '1', 93.0, 62.4)        # 1x12 along -Y, west of the Pico
    c(find(value='RECOVERY'), 102.3, 19.8)
    pin(find(value='BMS_UART'), '1', 81.5, 81.0)           # JST-XH 4 at the pack edge
    c(find(value='PC817', nets=['BMS_RX']), 83.5, 72.8)
    c(find(value='PC817', nets=['BMS_TX']), 83.5, 66.4)
    pin(find(value='DEV+'), '1', 92.0, 74.0)
    pin(find(value='DEV-'), '1', 92.0, 68.2)
    c(find(value='5A mini', nets=['VDEV_F']), 80.6, 51.0, 90)
    c(find(value='IRF9Z34NPBF', nets=['VDEV']), 87.5, 56.4, 90)
    c(find(value='P6KE20A', nets=['VDEV_F']), 87.5, 46.0, 90)
    c(find(value='220u 35V'), 80.5, 36.2)
    c(find(value='2N3904', nets=['OV_C']), 75.0, 29.5)     # DEVKIT_PWR switch
    c(find(value='2N3906'), 87.6, 39.2)
    c(find(value='TL431'), 87.6, 34.2)

    # ------------------------------------------------------------ Pico in sockets, parts under it
    c(find(value='RPi_Pico'), 106.5, 57.0)                 # USB end at the pack edge (cable to a dev-kit USB-A)
    pin(find(value='74HCT08'), '1', 102.7, 78.8)           # under the Pico
    pin(find(value='PC817', nets=['J14_PWR_KEY_N']), '1', 102.7, 58.4)
    pin(find(value='PC817', nets=['J14_RESET_N']), '1', 102.7, 51.6)
    c(find(value='GREEN', nets=['LEDS_A']), 109.9, 18.3)   # status / fault LEDs, visible beside the Pico
    c(find(value='RED', nets=['LEDF_A']), 109.9, 23.1)
    c(find(pre='TP', nets=['+3V3']), 120.6, 74.4)
    c(find(pre='TP', nets=['PICO_RUN']), 107.2, 28.4)
    c(find(value='10k', nets=['FET_NTC']), 112.85, 66.0, 90, 'B')   # NTC divider at GP28, between U302 and the Pico pins
    c(find(value='100n', nets=['FET_NTC']), 112.85, 71.2, 90, 'B')

    # ------------------------------------------------------------ front edge (X = L)
    pin(find(value='SERVO'), '1', L_BOARD - 2.4, 19.6)
    c(find(value='1000u 16V'), 119.6, 16.4)
    pin(find(value='LIDAR_PWR'), '1', 125.0, 25.0, 90)     # wire entry toward the front edge
    c(find(value='IRF9Z34NPBF', nets=['LID_SW']), 120.5, 37.5, 90)
    c(find(value='2N3904', nets=['LID_C']), 126.5, 34.2, 90)
    c(find(value='MF-R075', nets=['LIDAR_V']), 101.65, 27.6)
    c(find(value='P6KE20A', nets=['LIDAR_V']), 115.0, 27.4)
    c(find(value='MF-R075', nets=['CAM_VIN']), 120.5, 47.5, 90)
    c(find(value='POLOLU_S18V20F12'), 126.8, 45.6)
    c(find(value='ESTOP'), 127.0, 55.0, 90)
    c(find(value='BAT85', nets=['+3V3']), 122.0, 54.5, 90)
    c(find(value='BAT85', nets=['GND']), 119.3, 54.5, 90)
    c(find(value='BTN_REMOTE'), 125.3, 64.0, 90)
    c(find(pre='TP', nets=['SERVO_V']), 120.6, 70.0)

    # ------------------------------------------------------------ holes
    for ref, (x, y) in HOLES.items():
        B.place(ref, x, y, 0, 'F')
        _placed.append(ref)


# ----------------------------------------------------------------------------- outline (inside KiCad)
def outline_pts():
    W, H = SIZE
    return [(0, 0), (W, 0), (W, H), (0, H)]


def finish(B):
    import pcbnew
    from pcbnew import FromMM as MM
    b = B.b
    W, H = SIZE
    r = CORNER_R

    def seg(a, c):
        s = pcbnew.PCB_SHAPE(b)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(B.P(*a))
        s.SetEnd(B.P(*c))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(MM(0.1))
        b.Add(s)

    def arc(a, m, c):
        s = pcbnew.PCB_SHAPE(b)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(B.P(*a), B.P(*m), B.P(*c))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(MM(0.1))
        b.Add(s)
    k = r - r / 2 ** 0.5
    seg((r, 0), (W - r, 0))
    seg((W, r), (W, H - r))
    seg((W - r, H), (r, H))
    seg((0, H - r), (0, r))
    arc((0, r), (k, k), (r, 0))
    arc((W - r, 0), (W - k, k), (W, r))
    arc((W, H - r), (W - k, H - k), (W - r, H))
    arc((r, H), (k, H - k), (0, H - r))

    def text(s, x, y, size=1.5, layer=None):
        t = pcbnew.PCB_TEXT(b)
        t.SetText(s)
        t.SetPosition(B.P(x, y))
        t.SetLayer(layer if layer is not None else pcbnew.F_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
        t.SetTextThickness(MM(0.2 if size < 2 else 0.3))
        b.Add(t)
    text('ATLAS-PWR-1 rev B', 45.0, 15.6, 1.6)
    text('Atlas Autoware 2026-10   S/N ____', 45.0, 18.2, 1.0)
    text('BAT+ AND HEATSINK ARE LIVE', 30.5, 67.9, 1.0)
    text('ATLAS-PWR-1 rev B  bottom: 1206 chips', 65.0, 42.0, 1.6, pcbnew.B_SilkS)


# ----------------------------------------------------------------------------- copper (computed in placer.py)
def copper(B, C):
    """High-current pours and stitching. 'P:' zones exist while routing (the router treats them as copper),
    'F:' zones are the GND fills added afterwards."""
    from shapely.geometry import Polygon, Point, box
    from shapely.ops import unary_union
    edge = Polygon(outline_pts()).buffer(-0.3, join_style=2)
    keep_holes = unary_union([Point(x, y).buffer(3.5, 32) for x, y in HOLES.values()])

    def zone(name, net, layer, region, prio=10, **kw):
        g = region.intersection(edge).difference(keep_holes)
        polys = [g] if g.geom_type == 'Polygon' else [p for p in getattr(g, 'geoms', []) if p.area > 1.0]
        for i, p in enumerate(polys):
            C.zone(name + (f'_{i}' if len(polys) > 1 else ''), net, layer, p, priority=prio, **kw)
        return polys

    # main FET pin row at Y 59.5: BAT pour from the north grabs the drains, VM from the south the sources
    # (pads are 1.9 x 2.0 mm at 2.54 mm: each pour reaches its own pins over their outer edge, none fits between)
    bat = unary_union([box(13.5, 59.5, 66.0, 84.0), box(56.0, 59.5, 74.5, 64.0), box(64.5, 48.0, 74.5, 64.0)])
    vm = unary_union([box(13.9, 39.6, 56.6, 59.5), box(0.0, 36.0, 13.9, 47.6)])
    gnd = box(0.0, 48.6, 13.4, 84.0)
    zone('P:BAT_F', 'BAT', 'F', bat, prio=13, connect='full')
    zone('P:VM_F', 'VM', 'F', vm, prio=12, connect='full')
    zone('P:GND_PWR_F', 'GND', 'F', gnd, prio=12, connect='full')
    # bottom: GND under the whole power section (bulk-cap loop, return path under the VM pour)
    zone('P:GND_PWR_B', 'GND', 'B', box(0.0, 36.0, 66.0, 84.0), prio=12, connect='full')
    # stitching: GND corner top <-> bottom
    n_gnd = C.via_grid('GND', box(1.0, 69.5, 12.4, 75.5).union(box(9.5, 57.0, 12.4, 62.0)), 2.0, 0.5, 1.0)
    # mounting holes: no copper within 3.5 mm (CF-filled printed parts can conduct), kept after routing
    for i, (x, y) in enumerate(HOLES.values()):
        C.keepout(f'K:hole{i + 1}', ['F', 'B'], Point(x, y).buffer(3.5, 32), tracks=True, vias=True, zones=True,
                  dsn_only=False)
    # autorouter: foreign tracks stay out of the top power pours (0.6 mm inside their outline)
    for z in list(C.zones):
        if z['name'].startswith('P:') and z['layer'] == 'F':
            for i, rings in enumerate(z['rings']):
                g = Polygon(rings[0], rings[1:]).buffer(-0.6, 8)
                for j, piece in enumerate([g] if g.geom_type == 'Polygon' else list(getattr(g, 'geoms', []))):
                    if piece.area > 1.0:
                        C.keepout(f"D:{z['name'][2:]}_{i}_{j}", [z['layer']], piece, tracks=True, vias=False)
    # GND fills on both layers after routing
    C.zone('F:GND_F', 'GND', 'F', edge.difference(keep_holes), priority=1, connect='tht', dsn=False)
    C.zone('F:GND_B', 'GND', 'B', edge.difference(keep_holes), priority=1, connect='tht', dsn=False)
    print('stitching vias: GND', n_gnd)
