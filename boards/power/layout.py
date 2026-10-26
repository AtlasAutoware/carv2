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
       |FAN                                             hub (MCP2221A under)  J602 recovery F402 C404 servo |
  Y 0  +H------- J12 2x20 box header (ribbon) ---------- H ---- hub USB-C -- USB-A -- power button LEDs H+
       X 0 (rear: ESC bay)                                                               X 130 (front)

High-current path (copper(), not left to the router):
  BAT+ pad -> top BAT pour (north of the FET pin row; GND under it on the bottom, so the bulk caps sit in a tight
  BAT/GND loop) -> FET drains; FET sources -> top VM pour south of the row -> ESC+ pad at the rear edge.
  Return: ESC- pad -> GND corner (both layers) -> BAT- pad, 12 mm apart. The whole bottom under the power
  section is GND (return path under the VM pour). Gate traces leave each G pin on the bottom.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))

NAME = 'atlas_power'
L_BOARD = 130.0
SIZE = (L_BOARD, 84.0)
PAGE_ORIGIN = (30.0, 30.0)
COPPER_LAYERS = 4
# (E2b) four layers since 2026-10-26: two 2-layer routings left 21 and 37 signal connections open in the logic half
# (J802 pinned 4.6 mm west of the Pico walls it) and the ground round the Pico had no path to the pack
# (LAYOUT_NOTES.md).
# F.Cu 2 oz: THT parts, the BAT/VM/GND power pours, the hand routes. In1.Cu 1 oz: solid GND plane (cut out under the
# BMS domain). In2.Cu 1 oz: signals and the +3V3/+5V/PICO_VSYS runs. B.Cu 2 oz: bottom chips, the bottom GND pours.
LAYER_TYPES = {'In1': 'power', 'In2': 'signal'}
# physical stack (build_pcb.py writes it into the board's setup): copper and dielectric thickness in mm, 1.6 mm
# nominal (the fab sets the real dielectrics), HASL lead-free
STACKUP = {'copper': {'F': 0.070, 'In1': 0.035, 'In2': 0.035, 'B': 0.070},
           'dielectric': [('prepreg', 0.2), ('core', 0.97), ('prepreg', 0.2)], 'mask': 0.01, 'finish': 'HAL lead-free'}
# the BMS domain (BMS-side pins of U201/U202, R201, R204, C201, J201) plus its 2 mm isolation band: no plane, no
# track, no fill on the inner layers there (the same boxes keep the auto placer's bottom chips out, NO_AUTO)
BMS_DOMAIN = [(76.0, 58.0, 85.0, 84.0), (76.0, 76.6, 92.5, 84.0)]
FULL_CONNECT = ['J408']          # pads joined to every GND fill and the plane without thermal spokes (DEV-, 5 A)
CORNER_R = 2.0

HOLES = {'H1001': (4.0, 4.0), 'H1002': (4.0, 80.0), 'H1003': (75.0, 4.0), 'H1004': (75.0, 80.0),
         'H1005': (L_BOARD - 4.0, 4.0), 'H1006': (L_BOARD - 4.0, 80.0)}
AUTO_MARGIN = 0.2                # 0.4 mm between auto-placed courtyards
KEEP_AUTO = True                 # (E2) routed: auto-placed parts stay where the last run put them
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

# Net classes (agent E, layout): signals 0.3 mm with 0.25 mm clearance and 0.8/0.4 mm vias (PCBWay standard
# 2-layer); 5 V at 1.0 mm; VSYS_SW, the charge path and BAT's routed feeds (Pololu latch VIN, MIC5014 supply)
# at 2.0 mm. BAT, VM and GND carry their high current in the pours of copper(), never in routed tracks.
DEFAULT_CLASS = {'width': 0.3, 'clearance': 0.25, 'via': 0.8, 'drill': 0.4}
NETCLASSES = {
    'Supply': {'width': 2.0, 'clearance': 0.3, 'via': 1.2, 'drill': 0.6, 'nets': [
        'VSYS_SW', 'VDEV_F', 'VDEV', 'LID_SW', 'LIDAR_V', 'CHG_IN', 'CHG_OUT', 'CHG_RB', 'CAM_VIN', 'BAT',
        'CHG_GND']},                 # (D) CHG_GND carries the 2.5 A charge return to the CC/CV OUT- pad
    'Servo': {'width': 2.5, 'clearance': 0.3, 'via': 1.2, 'drill': 0.6, 'nets': ['SERVO_V']},
    'Pulse': {'width': 1.0, 'clearance': 0.3, 'via': 1.0, 'drill': 0.5, 'nets': ['PRE_D', 'PRE_F', 'V5_IN', 'VM']},
    'Rail5': {'width': 1.0, 'clearance': 0.25, 'via': 1.0, 'drill': 0.5, 'nets': ['+5V']},
    # (E) HUB_VBUS (the laptop's USB 5 V into the hub, under 1 A) at 0.6 mm: a 1 mm track cannot reach the middle
    # pin of U602 (TO-92, 0.22 mm between pads) and the routers do not neck down at a pin
    'Power': {'width': 0.6, 'clearance': 0.25, 'via': 0.8, 'drill': 0.4, 'nets': [
        '+3V3', 'PICO_VSYS', 'CON_3V3', 'SW_GATE', 'SW_G1', 'SW_G2', 'SW_G3', 'HUB_VBUS']},
    # USB 2.0 pairs: route coupled, short, over unbroken GND (90 Ohm is not reachable on 1.6 mm 2-layer)
    'USB': {'width': 0.4, 'clearance': 0.25, 'via': 0.8, 'drill': 0.4, 'nets': [
        'P1_DP', 'P1_DM', 'P2_DP', 'P2_DM', 'P3_DP', 'P3_DM', 'P4_DP', 'P4_DM']},
    # BMS-side domain: 0.3 mm inside it (J201's pads are 0.8 mm apart), 2 mm to everything else (DRU below;
    # the router gets the same 2 mm as a Specctra class_class rule, DSN_CLASS_CLEARANCE)
    'BMS': {'width': 0.3, 'clearance': 0.3, 'via': 0.8, 'drill': 0.4, 'nets': [
        'BMS_VDD', 'BMS_TXD', 'BMS_RXD', 'BMS_GND', 'BMS_OPT1_A']},
}
# the router's copy of the BMS isolation rule (tools/dsn_patch.py writes Specctra class_class rules)
DSN_CLASS_CLEARANCE = {'BMS': 2.05}
# board-wide floors for DRC (build_pcb.py), from PCBWay's capabilities page (Oct 2026): 2 oz outer copper,
# normal process, 7/8 mil track/space; standard service annular ring 0.15 mm; component holes 16 mil apart;
# line to board edge 0.25 mm. The brief's own floors are tighter (0.25 mm track and space, 0.3 mm drill).
BOARD_RULES = {'min_clearance': 0.2, 'min_track_width': 0.25, 'min_via_diameter': 0.8, 'min_via_annular_width': 0.15,
               'min_through_hole_diameter': 0.3, 'min_hole_clearance': 0.25, 'min_hole_to_hole': 0.4,
               'min_copper_edge_clearance': 0.3}
RAILS = ['GND', '+3V3', '+5V', 'VM', 'BAT', 'VSYS_SW', 'HUB_VBUS']
try:
    TO92 = sorted(p['ref'] for p in json.load(open(os.path.join(HERE, NAME + '_parts.json')))['parts']
                  if p['footprint'].endswith('TO-92_Inline'))
except (OSError, ValueError):
    TO92 = []
DRU = ('(version 1)\n'
       '(rule "BMS-side domain 2 mm from everything else" (constraint clearance (min 2.0mm))'
       ' (condition "A.NetClass == \'BMS\' && B.NetClass != \'BMS\'"))\n'
       # KiCad's TO-92 land pattern: 0.22 mm between pads at 1.27 mm pitch, 0.15 mm ring (PCBWay 2 oz: 8 mil space,
       # 0.15 mm ring on the standard service). Only between the pads of one of these parts.
       # (intersectsCourtyard: KiCad 7 has no memberOfFootprint; KiCad 8+ have both)
       # GND fills on both sides: a THT pad whose thermal relief keeps one spoke (a track takes the others) is
       # still joined, and the other side's fill joins it too
       + '(rule "one thermal spoke is enough (fills on both layers)" (constraint min_resolved_spokes 1)'
         ' (condition "A.Type == \'Pad\' && B.Type == \'Zone\'"))\n'
       + ''.join(f'(rule "TO-92 land pattern {r}" (constraint clearance (min 0.2mm))'
                 f' (condition "A.Type == \'Pad\' && B.Type == \'Pad\' && A.intersectsCourtyard(\'{r}\')'
                 f' && B.intersectsCourtyard(\'{r}\')"))\n' for r in TO92))

# areas the automatic placer must leave empty: (side, x0, y0, x1, y1)
NO_AUTO = [
    ('F', 0.0, 36.0, 74.0, 84.0),        # power section (top): pours, FETs, heatsink, bulk caps
    ('B', 0.0, 36.0, 60.0, 84.0),        # power section (bottom): unbroken GND under BAT and VM
    ('B', 76.0, 58.0, 85.0, 84.0),       # (E) BMS domain under U201/U202 plus its 2 mm isolation band
    ('B', 76.0, 76.6, 92.5, 84.0),       # (E) BMS domain at J201 plus 2 mm
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
    c('TP1002', 77.2, 25.4)                                # (E) GND test point beside TP402 (+5V), out of the BMS gap
    c('TP302', 76.3, 61.6)                                 # (E) SW_GATE test point beside the MIC5014, outside the BMS band
    c(find(value='10n', nets=['ESTOP_OK']), 102.75, 40.25, 0, 'B')   # (E) where the auto placer had it before
    c(find(value='100', nets=['ESTOP_IN']), 101.75, 82.0, 0, 'B')      # (E) E-stop series 100 Ohm: first free bottom spot
    c(find(value='10k', nets=['ESTOP_OK', 'GND']), 102.75, 37.05, 0, 'B')   # (D) loop pull-down beside C1001
    pin(find(value='IRF9Z34NPBF', nets=['PRE_D']), '1', 58.0, 59.5)
    pin(find(value='MF-R050'), '1', 61.0, 55.6, 270)       # PRE_D (top) -> PRE_F (bottom end)
    pin(find(value='10 5W'), '1', 54.5, 45.5, 180)         # precharge resistor lying on the VM pour, VM end west
    pin(find(value='1.5KE22A'), '1', 34.0, 53.4)           # VM TVS on the VM pour; anode pad drops into bottom GND
    pin(find(value='BEC+'), '1', 22.0, 42.0)               # Castle BEC input, on the VM pour
    pin(find(value='BEC-'), '1', 12.0, 50.2)               # in the GND corner
    c(find(pre='TP', nets=['VM']), 26.0, 52.0)              # (E) 0.6 mm down: room for the FET bar warning
    c(find(value='MIC5014'), 68.5, 70.0)
    # (E2) MIC5014 IN pull-down beside pin 2, north of the heatsink-NTC track that leaves under the DIP between pins 2/3
    c(find(value='100k', nets=['MIC_IN', 'GND']), 62.0, 72.9, 90, 'B')
    # (E2) the VM_SENSE divider's top resistor on the VM link north of F501 (VM itself, a 0.3 mm class, cannot pass
    # between the J802 and Pico pins; VM_SENSE, a signal, can)
    c(find(value='100k', nets=['VM', 'VM_SENSE']), 70.0, 56.0, 270, 'B')
    # (E2) the power button's 33k from BAT beside F501's BAT pin (it was at the button, which took a thin BAT track
    # across the middle of the board; BTN_HI, a signal, now makes that run)
    c(find(value='33k', nets=['BAT', 'BTN_HI']), 76.5, 49.8, 0, 'B')
    # (E2) the dev-kit cut-off's VDEV_F-to-OV_G resistor between F401 and Q402, beside R412 and Q402's gate (it sat
    # in the 2.5 mm gap west of F401 that the signals from the MIC5014 side, MIC_IN and NTC_NODE, have to use)
    c(find(value='10k', nets=['VDEV_F', 'OV_G']), 85.7, 54.4, 270, 'B')
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
    # (D, review M7) hub port 1: USB-A receptacle standing on its edge, opening toward the Y = 0 edge (face 0.5 mm
    # inboard), between the hub and the power button
    pin(find(value='DEVKIT_USB'), '1', 102.8, 12.83, 90)
    pin(find(value='VESC_USB'), '1', 109.3, 19.85)         # (D) hub port 3 (FSESC lead): 1x4 beside the USB-A, pin 1 north
    pin(find(value='HUB_PORT4'), '1', 77.4, 21.4)          # hub port 4 (left column); port 2 = MCP2221A under the hub
    pin(find(value='POWER'), '1', 115.0, 5.6, 180)         # right-angle: plunger out of the Y=0 edge

    # ------------------------------------------------------------ charge, latch, 5 V (X 14..74, Y 14..36)
    c(find(value='ADA5807_HUSB238'), 21.0, 22.0)           # PD trigger wire pads (module in the pod)
    c(find(value='P6KE24A'), 21.0, 31.2, 90)
    c(find(value='CCCV_BUCK_XL4015'), 28.6, 25.0)
    c(find(value='1N5247B'), 34.0, 31.6, 90)
    c(find(value='2N3904', nets=['CHG_C']), 38.4, 32.6)
    c(find(value='2N3904', nets=['CHG_PRESENT_N']), 41.0, 18.6)
    c(find(value='IRF4905PBF', nets=['CHG_OUT']), 40.0, 25.5)
    # (E2) Q501's 100 nF gate-source capacitor beside its gate pin (the auto placer had put it 28 mm away, by F501)
    c(find(value='100n', nets=['CHG_RB', 'CHG_G']), 33.6, 22.5, 90, 'B')
    c(find(value='5A mini', nets=['CHG_RB']), 70.0, 46.7, 90)   # into the BAT pour at its north end
    c(find(pre='TP', nets=['CHG_IN']), 34.2, 18.6)
    c(find(value='POLOLU_2813'), 50.0, 25.0)
    c(find(value='2N3904', nets=['BUTTON_N']), 57.2, 32.6)
    c(find(value='R-78E5.0-1.0'), 62.5, 18.2)
    c(find(value='4.7', nets=['V5_IN']), 63.0, 25.6)
    c(find(value='P6KE20A', nets=['V5_IN']), 71.6, 19.0, 90)
    c(find(value='1N5817'), 70.2, 26.6, 90)
    c(find(value='GREEN', nets=['LED5_A']), 69.6, 33.4)
    c(find(pre='TP', nets=['+5V']), 73.9, 24.6)
    c(find(pre='TP', nets=['VSYS_SW']), 62.05, 29.14)      # (D) moved 3.5 mm south for the BEC+ALT pad
    pin(find(value='BEC+ALT'), '1', 63.6, 34.45)           # (D, review M3) alternative BEC input on VSYS_SW

    # ------------------------------------------------------------ middle right: J14, BMS, dev-kit feed
    pin(find(value='J14_HARNESS'), '1', 93.0, 62.4)        # 1x12 along -Y, west of the Pico
    c(find(value='RECOVERY'), 102.87, 25.8)                # (D) north of the USB-A, under the Pico's south edge
    pin(find(value='BMS_UART'), '1', 81.5, 81.0)           # JST-XH 4 at the pack edge
    c(find(value='PC817', nets=['BMS_RX']), 83.5, 72.8)
    c(find(value='PC817', nets=['BMS_TX']), 83.5, 66.4, 180)   # (E) turned: both optos' BMS sides face west
    # (E) BMS-side chips explicit, under the optos between their pin rows, so the whole BMS domain is one
    # island west of X 84.5 and under J201, 2 mm from every board-side pin (U201 3/4, U202 1/2 at X 87.3)
    c(find(value='1k', nets=['BMS_VDD', 'BMS_OPT1_A']), 82.6, 73.0, 90, 'B')
    c(find(value='4.7k', nets=['BMS_VDD', 'BMS_RXD']), 82.6, 67.0, 90, 'B')
    c(find(value='100n', nets=['BMS_VDD', 'BMS_GND']), 82.6, 62.0, 90, 'B')   # 2 mm from F401
    c(find(value='470', nets=['+3V3', 'BMS_OPT2_A']), 88.5, 62.25, 0, 'B')   # (E) R203 2 mm east of the BMS_VDD track
    pin(find(value='DEV+'), '1', 92.0, 74.0)
    pin(find(value='DEV-'), '1', 93.28, 68.2)               # (E2) 1.28 mm east: room for the 2 mm VDEV track to DEV+ west of it
    #     (and its courtyard just clear of the Pico's)
    c(find(value='5A mini', nets=['VDEV_F']), 80.6, 51.0, 90)
    c(find(value='IRF4905PBF', nets=['VDEV']), 87.5, 56.4, 90)
    c(find(value='P6KE22A', nets=['VDEV_F']), 87.5, 46.0, 90)
    c(find(value='220u 35V'), 80.5, 36.2)
    c(find(value='2N3904', nets=['OV_C']), 75.0, 29.5)     # DEVKIT_PWR switch
    c(find(value='2N3906'), 87.6, 39.2)
    c(find(value='TL431'), 87.6, 34.2)

    # ------------------------------------------------------------ Pico in sockets, parts under it
    c(find(value='RPi_Pico'), 106.5, 57.0)                 # USB end at the pack edge (cable to a dev-kit USB-A)
    pin(find(value='74HCT08'), '1', 102.7, 78.8)           # under the Pico
    pin(find(value='PC817', nets=['J14_PWR_KEY_N']), '1', 102.7, 58.4)
    pin(find(value='PC817', nets=['J14_RESET_N']), '1', 102.7, 51.6)
    # (D) status / fault LEDs at the Y = 0 edge beside the power button (their old spot is now the USB-A and J602)
    c(find(value='GREEN', nets=['LEDS_A']), 119.75, 8.06, 90)
    c(find(value='RED', nets=['LEDF_A']), 119.75, 2.82, 90)
    c(find(pre='TP', nets=['+3V3']), 120.6, 74.4)
    c(find(pre='TP', nets=['PICO_RUN']), 113.77, 27.7)           # (D) beside F402 and D405, south of the Pico
    c(find(value='10k', nets=['FET_NTC']), 112.85, 66.0, 90, 'B')   # NTC series 10k at GP28, between U302 and the Pico pins
    c(find(value='10k', nets=['+3V3', 'NTC_NODE']), 112.85, 60.6, 90, 'B')   # (D) NTC divider top, same channel
    c(find(value='100n', nets=['FET_NTC']), 112.85, 71.2, 90, 'B')
    # (E2b) the J12 ribbon's series resistors whose far side is a Pico pin, next to that pin (bottom, under or beside
    # the Pico): the long runs are now the J12_* nets from the header pins (how far their routing got: LAYOUT_NOTES.md).
    # R803/R804 (to the FSESC COMM header) and the pull-downs R805, R808, R810 stay at the ribbon header.
    for v_, nets_, x_, y_, r_ in (('330', ['J12_SDA', 'I2C0_SDA'], 100.25, 67.75, 90),
                                  ('330', ['J12_SCL', 'I2C0_SCL'], 100.25, 62.5, 90),
                                  ('10k', ['J12_JETSON_UP', 'JETSON_UP'], 100.25, 50.0, 90),
                                  ('10k', ['J12_3V3', 'JETSON_3V3_SENSE'], 106.75, 40.5, 90),
                                  ('100k', ['JETSON_3V3_SENSE', 'GND'], 109.5, 34.5, 90),
                                  ('1k', ['ESTOP_OK_TO_JETSON', 'J12_ESTOP_OK'], 112.75, 48.25, 90),
                                  ('1k', ['CHG_STAT_N_TO_JETSON', 'J12_CHG_STAT_N'], 127.75, 45.0, 90),
                                  ('10k', ['J12_LIDAR_REQ', 'LIDAR_REQ'], 112.75, 53.5, 90)):
        c(find(value=v_, nets=nets_), x_, y_, r_, 'B')

    # ------------------------------------------------------------ front edge (X = L)
    pin(find(value='SERVO'), '1', L_BOARD - 2.4, 19.6)
    c(find(value='1000u 16V'), 119.6, 16.4)
    pin(find(value='LIDAR_PWR'), '1', 125.0, 25.0, 90)     # wire entry toward the front edge
    c(find(value='IRF9Z34NPBF', nets=['LID_SW']), 120.5, 37.5, 90)
    c(find(value='2N3904', nets=['LID_C']), 126.5, 34.2, 90)
    c(find(value='MF-R075', nets=['LIDAR_V']), 116.66, 24.05)  # (D) between C404 and the Pico, beside the lidar plug
    c(find(value='P6KE22A', nets=['LIDAR_V']), 110.07, 25.71, 90)
    c(find(value='MF-R075', nets=['CAM_VIN']), 120.5, 47.5, 90)
    c(find(value='P6KE22A', nets=['CAM_VIN']), 125.75, 71.96, 90)   # (D, review m18) camera input TVS
    c(find(value='POLOLU_S18V20F12'), 126.8, 45.6)
    c(find(value='ESTOP'), 127.0, 55.0, 90)
    c(find(value='BAT85', nets=['+3V3']), 122.0, 54.5, 90)
    c(find(value='BAT85', nets=['GND']), 119.3, 54.5, 90)
    c(find(value='BTN_REMOTE'), 125.3, 64.0, 90)
    c(find(pre='TP', nets=['SERVO_V']), 44.0, 14.1)         # (E2) on the servo supply run (was at X 120.6 Y 70, 50 mm from it)

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
    for ref in FULL_CONNECT:
        fp = b.FindFootprintByReference(ref)
        if fp is not None:
            for pd in fp.Pads():
                pd.SetZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    marks(B)


# ----------------------------------------------------------------------------- markings (agent E, inside KiCad)
FIDUCIAL_NEAR = [[(15.75, 14.25), (10.0, 4.5), (9.75, 77.5)], [(127.0, 10.0), (121.0, 4.5), (114.0, 12.0)], [(121.0, 79.5)]]   # three, non-collinear
TEXTS = [  # (text, [(near X, near Y), ...], height mm, layer 'F'/'B', bold)
    ('FET bar is at pack voltage', [(21.6, 56.9), (30.5, 56.9)], 1.0, 'F', True),     # across the FET row from the bar
    ('ATLAS-PWR-1 rev B  2026-10-26', [(34.0, 38.0)], 1.2, 'F', True),
    ('Atlas Autoware   S/N ____', [(30.0, 44.0)], 1.2, 'B', False),       # the top has no free strip for it
    ('ATLAS-PWR-1 rev B  2026-10-26', [(30.0, 50.0)], 1.5, 'B', True),
    ('bottom: 1206/1210 chips, solder these first', [(30.0, 47.0)], 1.0, 'B', False),
]
WIRE_SIGNS = {'BAT+': '+', 'BAT-': '-', 'ESC+': '+', 'ESC-': '-', 'BEC+': '+', 'BEC-': '-', 'DEV+': '+', 'DEV-': '-',
              'SRV+': '+', 'SRV-': '-', 'BEC+ALT': '+'}


def marks(B):
    """Fiducials, board name/rev/date, the FET bar warning, + and - beside the power wire pads, a pin-1 dot
    beside every polarised top-side part. Each goes to the free spot nearest its target: clear of every pad
    (0.25 mm), of the silkscreen already there and of the board edge."""
    import pcbnew
    from pcbnew import FromMM as MM, ToMM
    b = B.b
    W, H = SIZE
    OX, OY = PAGE_ORIGIN

    def rect_of(bb, grow=0.0):     # page BOX2I -> board-local (x0, y0, x1, y1)
        x0, y1 = ToMM(bb.GetLeft()) - OX, H - (ToMM(bb.GetTop()) - OY)
        x1, y0 = ToMM(bb.GetRight()) - OX, H - (ToMM(bb.GetBottom()) - OY)
        return (x0 - grow, y0 - grow, x1 + grow, y1 + grow)

    pads = {'F': [], 'B': []}
    silk = {'F': [], 'B': []}         # rectangles (texts, small filled shapes)
    strokes = {'F': [], 'B': []}      # silk strokes: (x0, y0, x1, y1, half width)
    crt = {'F': [], 'B': []}

    def loc(v):
        return B.back(v)

    def add_strokes(it, side):
        w = ToMM(it.GetWidth()) / 2
        st = it.GetShape()
        pts = []
        if st == pcbnew.SHAPE_T_SEGMENT:
            pts = [loc(it.GetStart()), loc(it.GetEnd())]
        elif st == pcbnew.SHAPE_T_RECT:
            (x0, y0), (x1, y1) = loc(it.GetStart()), loc(it.GetEnd())
            pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
        elif st == pcbnew.SHAPE_T_CIRCLE:
            cx, cy = loc(it.GetCenter())
            r = ToMM(it.GetRadius())
            pts = [(cx + r * math.cos(k * math.pi / 16), cy + r * math.sin(k * math.pi / 16)) for k in range(33)]
            if it.IsFilled():
                silk[side].append((cx - r - w, cy - r - w, cx + r + w, cy + r + w))
        elif st == pcbnew.SHAPE_T_ARC:
            cx, cy = loc(it.GetCenter())
            (sx, sy), (mx, my), (ex, ey) = loc(it.GetStart()), loc(it.GetArcMid()), loc(it.GetEnd())
            r = math.hypot(sx - cx, sy - cy)
            a0, am, a1 = (math.atan2(q - cy, p_ - cx) for p_, q in ((sx, sy), (mx, my), (ex, ey)))
            # go from a0 to a1 through am
            span = (a1 - a0) % (2 * math.pi)
            if (am - a0) % (2 * math.pi) > span:
                span -= 2 * math.pi
            pts = [(cx + r * math.cos(a0 + span * k / 16), cy + r * math.sin(a0 + span * k / 16)) for k in range(17)]
        else:                            # polygons, curves: their bounding box
            silk[side].append(rect_of(it.GetBoundingBox(), 0.15))
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            strokes[side].append((x0, y0, x1, y1, w))

    for fp in b.GetFootprints():
        side = 'B' if fp.IsFlipped() else 'F'
        for pd in fp.Pads():
            r = rect_of(pd.GetBoundingBox(), 0.25)
            for sd in ('F', 'B'):
                if pd.IsOnLayer(pcbnew.F_Mask if sd == 'F' else pcbnew.B_Mask) or pd.GetDrillSize().x > 0:
                    pads[sd].append(r)
        for it in fp.GraphicalItems():
            if it.GetLayer() not in (pcbnew.F_SilkS, pcbnew.B_SilkS):
                continue
            sd = 'F' if it.GetLayer() == pcbnew.F_SilkS else 'B'
            if it.Type() in (pcbnew.PCB_TEXT_T, getattr(pcbnew, 'PCB_FP_TEXT_T', -1)):
                silk[sd].append(rect_of(it.GetBoundingBox(), 0.15))
            else:
                add_strokes(it, sd)
        for t in (fp.Reference(), fp.Value()):
            if t.IsVisible() and t.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
                silk['F' if t.GetLayer() == pcbnew.F_SilkS else 'B'].append(rect_of(t.GetBoundingBox(), 0.15))
        try:
            fp.BuildCourtyardCaches()
            c = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd)
            for i in range(c.OutlineCount()):
                crt[side].append(rect_of(c.Outline(i).BBox(), 0.0))
        except Exception:
            pass

    def seg_rect(sx0, sy0, sx1, sy1, r):
        """distance from a segment to an axis-aligned rectangle (0 when they meet)"""
        x0, y0, x1, y1 = r
        if (x0 <= sx0 <= x1 and y0 <= sy0 <= y1) or (x0 <= sx1 <= x1 and y0 <= sy1 <= y1):
            return 0.0

        def pd(px, py):
            dx, dy = sx1 - sx0, sy1 - sy0
            L2 = dx * dx + dy * dy
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - sx0) * dx + (py - sy0) * dy) / L2))
            return math.hypot(px - (sx0 + t * dx), py - (sy0 + t * dy))

        def cross(ax, ay, bx, by, cx_, cy_, dx_, dy_):
            def o(px, py, qx, qy, rx, ry):
                return (qx - px) * (ry - py) - (qy - py) * (rx - px)
            return (o(ax, ay, bx, by, cx_, cy_) * o(ax, ay, bx, by, dx_, dy_) < 0 and
                    o(cx_, cy_, dx_, dy_, ax, ay) * o(cx_, cy_, dx_, dy_, bx, by) < 0)
        edges = [(x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)]
        if any(cross(sx0, sy0, sx1, sy1, *e) for e in edges):
            return 0.0
        d = min(pd(x0, y0), pd(x1, y0), pd(x1, y1), pd(x0, y1))
        for px, py in ((sx0, sy0), (sx1, sy1)):
            nx, ny = min(max(px, x0), x1), min(max(py, y0), y1)
            d = min(d, math.hypot(px - nx, py - ny))
        return d

    holes = [(x, y, 3.6) for x, y in HOLES.values()]
    # solder mask openings from the copper file (review m20): silkscreen there would be clipped, so keep off them
    openings = {'F': [], 'B': []}
    try:
        for m in json.load(open(os.path.join(HERE, 'out', NAME + '_copper.json'))).get('masks', []):
            openings[m['layer']].append(m['rings'])
    except (OSError, ValueError):
        pass

    def inside(px, py, ring):
        c = False
        for (ax, ay), (bx, by) in zip(ring, ring[1:] + ring[:1]):
            if (ay > py) != (by > py) and px < ax + (py - ay) * (bx - ax) / (by - ay):
                c = not c
        return c

    def on_opening(r, side, grow=0.3):
        x0, y0, x1, y1 = r[0] - grow, r[1] - grow, r[2] + grow, r[3] + grow
        pts = [(x0 + (x1 - x0) * i / 6, y0 + (y1 - y0) * j / 3) for i in range(7) for j in range(4)]
        for rings in openings[side]:
            for px, py in pts:
                if inside(px, py, rings[0]) and not any(inside(px, py, h) for h in rings[1:]):
                    return True
        return False

    def hit(r, rs):
        return any(r[0] < o[2] and r[2] > o[0] and r[1] < o[3] and r[3] > o[1] for o in rs)

    def free(r, side, edge=0.6, courtyards=False):
        if r[0] < edge or r[1] < edge or r[2] > W - edge or r[3] > H - edge:
            return False
        for hx, hy, hr in holes:
            nx, ny = min(max(hx, r[0]), r[2]), min(max(hy, r[1]), r[3])
            if (nx - hx) ** 2 + (ny - hy) ** 2 < hr ** 2:
                return False
        if hit(r, pads[side]) or hit(r, silk[side]) or on_opening(r, side):
            return False
        if any(seg_rect(x0, y0, x1, y1, r) < w + 0.15 for x0, y0, x1, y1, w in strokes[side]
               if not (max(x0, x1) + w + 0.2 < r[0] or min(x0, x1) - w - 0.2 > r[2] or
                       max(y0, y1) + w + 0.2 < r[1] or min(y0, y1) - w - 0.2 > r[3])):
            return False
        return not (courtyards and hit(r, crt[side]))

    def spiral(x, y, step=0.25, reach=12.0):
        yield x, y
        k = 1
        while k * step <= reach:
            for i in range(-k, k + 1):
                for j in (-k, k):
                    yield x + i * step, y + j * step
                    yield x + j * step, y + i * step
            k += 1

    # fiducials: 1 mm copper dot, 2 mm mask opening; keep 1.5 mm round them free of pads and part bodies
    n_fid = 0
    for i, targets in enumerate(FIDUCIAL_NEAR):
        for x, y in (q for tx, ty in targets for q in spiral(tx, ty, reach=6.0)):
            r = (x - 2.0, y - 2.0, x + 2.0, y + 2.0)
            if free(r, 'F', edge=1.0, courtyards=True):
                fp = B.load_fp('Fiducial:Fiducial_1mm_Mask2mm')
                fp.SetReference(f'FID{i + 1}')
                fp.SetValue('Fiducial')
                fp.SetAttributes(pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM)
                fp.Reference().SetVisible(False)
                fp.Value().SetVisible(False)
                b.Add(fp)
                fp.SetPosition(B.P(x, y))
                pads['F'].append(r)
                crt['F'].append(r)
                n_fid += 1
                break
        else:
            if os.environ.get('MARKS_DEBUG'):
                x, y = targets[0]
                r = (x - 2.0, y - 2.0, x + 2.0, y + 2.0)
                print('   debug fiducial', targets[0], 'pads', [o for o in pads['F'] if hit(r, [o])][:3],
                      'silk', [o for o in silk['F'] if hit(r, [o])][:3], 'crt', [o for o in crt['F'] if hit(r, [o])][:3],
                      'strokes', [q for q in strokes['F'] if seg_rect(q[0], q[1], q[2], q[3], r) < q[4] + 0.15][:3],
                      'opening', on_opening(r, 'F'))

    def add_text(s, targets, size, side, bold=False, reach=12.0, own=None):
        """the first free spot near the first target that has one; text stays off part bodies (courtyards,
        except the courtyard of `own`, the part it labels)"""
        t = pcbnew.PCB_TEXT(b)
        t.SetText(s)
        t.SetLayer(pcbnew.F_SilkS if side == 'F' else pcbnew.B_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
        t.SetTextThickness(MM(max(0.15, size * (0.2 if bold else 0.15))))
        if side == 'B':
            t.SetMirrored(True)
        skip = []
        if own is not None:
            c = own.GetCourtyard(pcbnew.B_CrtYd if own.IsFlipped() else pcbnew.F_CrtYd)
            skip = [rect_of(c.Outline(i).BBox(), 0.0) for i in range(c.OutlineCount())]
        saved = crt[side]
        crt[side] = [r for r in saved if r not in skip]
        try:
            for tx, ty in targets:
                for x, y in spiral(tx, ty, step=0.25 if reach <= 8 else 0.5, reach=reach):
                    t.SetPosition(B.P(x, y))
                    r = rect_of(t.GetBoundingBox(), 0.1)
                    if free(r, side, edge=0.5, courtyards=True):
                        b.Add(t)
                        silk[side].append(r)
                        return (round(x, 2), round(y, 2))
        finally:
            crt[side] = saved
        if os.environ.get('MARKS_DEBUG'):
            tx, ty = targets[0]
            t.SetPosition(B.P(tx, ty))
            r = rect_of(t.GetBoundingBox(), 0.1)
            why = [o for o in pads[side] if r[0] < o[2] and r[2] > o[0] and r[1] < o[3] and r[3] > o[1]][:2]
            why += [('crt', o) for o in crt[side] if r[0] < o[2] and r[2] > o[0] and r[1] < o[3] and r[3] > o[1]][:3]
            why += [('silk', o) for o in silk[side] if r[0] < o[2] and r[2] > o[0] and r[1] < o[3] and r[3] > o[1]][:2]
            print('   debug', repr(s), 'rect', [round(v, 2) for v in r], 'blocked by', why[:6])
        print('marks: no room for', repr(s))
        return None

    placed = []
    for s_, tg, size, side, bold in TEXTS:
        placed.append((s_, add_text(s_, tg, size, side, bold, reach=3.0) or
                       add_text(s_, tg[:1], size, side, bold, reach=40.0)))
    # + / - beside the power wire pads, drawn as silk strokes (2.4 mm, 0.4 mm wide): the nearest free side of the pad
    def sign_at(sign, x, y, size=2.4, w=0.4):
        segs = [((x - size / 2, y), (x + size / 2, y))]
        if sign == '+':
            segs.append(((x, y - size / 2), (x, y + size / 2)))
        for a_, c_ in segs:
            g = pcbnew.PCB_SHAPE(b)
            g.SetShape(pcbnew.SHAPE_T_SEGMENT)
            g.SetStart(B.P(*a_))
            g.SetEnd(B.P(*c_))
            g.SetWidth(MM(w))
            g.SetLayer(pcbnew.F_SilkS)
            b.Add(g)

    for ref, fp in B.fps.items():
        sign = WIRE_SIGNS.get(B.parts[ref]['value'])
        if not sign or fp.IsFlipped():
            continue
        pd = max(fp.Pads(), key=lambda q: q.GetBoundingBox().GetWidth())
        px, py = B.back(pd.GetPosition())
        own = [rect_of(r_, 0.0) for r_ in []]
        c = fp.GetCourtyard(pcbnew.F_CrtYd)
        own = [rect_of(c.Outline(i).BBox(), 0.0) for i in range(c.OutlineCount())]
        others = [r_ for r_ in crt['F'] if r_ not in own]
        done = None
        for size in (2.4, 1.6):                 # the smaller one where the wire pads sit close together
            for k in (0.6 + size / 2, 1.0 + size / 2, 1.4 + size / 2, 1.9 + size / 2):
                rad = ToMM(pd.GetBoundingBox().GetWidth()) / 2 + k
                for ang in range(0, 360, 30):
                    x = px + rad * math.cos(math.radians(ang))
                    y = py + rad * math.sin(math.radians(ang))
                    h = size / 2 + 0.25
                    r = (x - h, y - h, x + h, y + h)
                    saved = crt['F']
                    crt['F'] = others
                    ok = free(r, 'F', edge=0.5, courtyards=True)
                    crt['F'] = saved
                    if ok:
                        sign_at(sign, x, y, size=size, w=0.4 if size > 2 else 0.3)
                        silk['F'].append(r)
                        done = (round(x, 2), round(y, 2), size)
                        break
                if done:
                    break
            if done:
                break
        if not done and os.environ.get('MARKS_DEBUG'):
            rad = ToMM(pd.GetBoundingBox().GetWidth()) / 2 + 0.6 + 0.8
            for ang in range(0, 360, 30):
                x = px + rad * math.cos(math.radians(ang))
                y = py + rad * math.sin(math.radians(ang))
                r = (x - 1.05, y - 1.05, x + 1.05, y + 1.05)
                why = [('pad', o) for o in pads['F'] if hit(r, [o])][:1] + [('silk', o) for o in silk['F'] if hit(r, [o])][:1]
                why += [('crt', o) for o in others if hit(r, [o])][:1] + (['opening'] if on_opening(r, 'F') else [])
                why += [('stroke', q[:4]) for q in strokes['F'] if seg_rect(q[0], q[1], q[2], q[3], r) < q[4] + 0.15][:1]
                print('   debug sign', ref, ang, [round(v, 1) for v in r], why)
        if not done:
            # (E2) no room beside the pad (its own reference sits there, the neighbours are close): the reference
            # text itself becomes the pad's name with its sign ("SRV+", "DEV+"), and the reference goes to the fab layer
            ref_t, val_t = fp.Reference(), fp.Value()
            if ref_t.IsVisible() and ref_t.GetLayer() == pcbnew.F_SilkS:
                val_t.SetLayer(pcbnew.F_SilkS)
                val_t.SetPosition(ref_t.GetPosition())
                val_t.SetTextSize(ref_t.GetTextSize())
                val_t.SetTextThickness(max(ref_t.GetTextThickness(), MM(0.2)))
                val_t.SetVisible(True)
                ref_t.SetLayer(pcbnew.F_Fab)
                done = ('value text', B.parts[ref]['value'])
                print('marks: the sign of %s is its value text %r in place of the reference' % (ref, B.parts[ref]['value']))
            else:
                print('marks: no room for the sign of', ref)
        placed.append((ref + sign, done))
    # pin-1 dot (0.7 mm, filled) beside pad 1 of every polarised top-side part
    n_dot = 0
    for ref, fp in B.fps.items():
        if fp.IsFlipped() or not ref.startswith(('U', 'Q', 'D', 'J', 'MOD', 'C')):
            continue
        p1 = [q for q in fp.Pads() if q.GetNumber() == '1']
        if len(fp.Pads()) < 2 or not p1 or ref.startswith('MOD4') or ref.startswith('MOD5'):
            continue
        if ref.startswith('C') and not B.parts[ref]['footprint'].startswith('Capacitor_THT:CP_'):
            continue
        if B.parts[ref]['value'] in WIRE_SIGNS:
            continue
        p1 = max(p1, key=lambda q: q.GetBoundingBox().GetWidth())
        px, py = B.back(p1.GetPosition())
        cx, cy = B.back(fp.GetPosition())
        others = [B.back(q.GetPosition()) for q in fp.Pads() if q.GetNumber() not in ('1', '')]
        if others:
            ox = sum(o[0] for o in others) / len(others)
            oy = sum(o[1] for o in others) / len(others)
        else:
            ox, oy = cx, cy
        bb = rect_of(p1.GetBoundingBox(), 0.0)
        hw, hh = (bb[2] - bb[0]) / 2, (bb[3] - bb[1]) / 2
        dx, dy = px - ox, py - oy
        cands = []
        for k in (0.75, 1.1, 1.5, 2.0):
            for ang in range(0, 360, 45):
                cands.append((px + (hw + k) * math.cos(math.radians(ang)), py + (hh + k) * math.sin(math.radians(ang))))
        cands.sort(key=lambda q: (q[0] - px) ** 2 + (q[1] - py) ** 2 - 0.3 * ((q[0] - px) * dx + (q[1] - py) * dy) /
                   (math.hypot(dx, dy) or 1.0))
        if abs(dx) >= abs(dy):
            sx = 1 if dx >= 0 else -1
            cands += [(px + sx * (hw + 0.75), py), (px, py + hh + 0.75), (px, py - hh - 0.75)]
        else:
            sy = 1 if dy >= 0 else -1
            cands += [(px, py + sy * (hh + 0.75)), (px + hw + 0.75, py), (px - hw - 0.75, py)]
        cands += [(px - hw - 0.75, py), (px + hw + 0.75, py), (px, py - hh - 0.75), (px, py + hh + 0.75),
                  (px + hw + 0.6, py + hh + 0.6), (px - hw - 0.6, py + hh + 0.6),
                  (px + hw + 0.6, py - hh - 0.6), (px - hw - 0.6, py - hh - 0.6)]
        for x, y in cands:
            r = (x - 0.45, y - 0.45, x + 0.45, y + 0.45)
            if free(r, 'F', edge=0.5):
                c = pcbnew.PCB_SHAPE(b)
                c.SetShape(pcbnew.SHAPE_T_CIRCLE)
                c.SetCenter(B.P(x, y))
                c.SetEnd(B.P(x + 0.2, y))
                c.SetWidth(MM(0.3))
                c.SetFilled(True)
                c.SetLayer(pcbnew.F_SilkS)
                b.Add(c)
                silk['F'].append(r)
                n_dot += 1
                break
        else:
            print('marks: no room for the pin-1 dot of', ref)
    print('marks: %d fiducials, %d pin-1 dots; texts at %s' % (n_fid, n_dot, placed))


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
    # (E) the main VM pour reaches down to Y 36.5 between X 13.9 and 54 (nothing on the top there), so the corner
    # where the motor current turns west into the ESC+ strip is 11 mm wide instead of 8 mm (pour_resistance.py)
    vm = unary_union([box(13.9, 39.6, 56.6, 59.5), box(13.9, 36.5, 54.0, 39.6), box(0.0, 36.0, 13.9, 47.6)])
    gnd = box(0.0, 48.6, 13.4, 84.0)
    zone('P:BAT_F', 'BAT', 'F', bat, prio=13, connect='full')
    zone('P:VM_F', 'VM', 'F', vm, prio=12, connect='full')
    zone('P:GND_PWR_F', 'GND', 'F', gnd, prio=12, connect='full')
    # bottom: GND under the whole power section (bulk-cap loop, return path under the VM pour)
    zone('P:GND_PWR_B', 'GND', 'B', box(0.0, 36.0, 66.0, 84.0), prio=12, connect='full')
    # stitching: GND corner top <-> bottom
    n_gnd = C.via_grid('GND', box(1.0, 69.5, 12.4, 75.5).union(box(9.5, 57.0, 12.4, 62.0)), 2.0, 0.5, 1.0)
    # mounting holes: no copper within 3.5 mm (CF-filled printed parts can conduct), kept after routing
    cu_layers = ['F', 'In1', 'In2', 'B'] if COPPER_LAYERS == 4 else ['F', 'B']
    for i, (x, y) in enumerate(HOLES.values()):
        C.keepout(f'K:hole{i + 1}', cu_layers, Point(x, y).buffer(3.5, 32), tracks=True, vias=True, zones=True,
                  dsn_only=False)
    if COPPER_LAYERS == 4:
        # (E2b) In1: one solid GND plane under the whole board except the BMS domain and its 2 mm band, which stays
        # an island on its own ground (BMS_GND); every through-hole GND pin joins the plane, J408 (DEV-, the dev
        # kit's 5 A return) solid (FULL_CONNECT, set in finish()), surface GND pads by a via each (pad_vias.py)
        bms = unary_union([box(*b_) for b_ in BMS_DOMAIN])
        zone('P:GND_In1', 'GND', 'In1', box(0.0, 0.0, SIZE[0], SIZE[1]).difference(bms), prio=0, connect='tht')
        for i, g_ in enumerate([bms] if bms.geom_type == 'Polygon' else list(bms.geoms)):
            C.keepout(f'K:bms_in{i + 1}', ['In1', 'In2'], g_.intersection(edge), tracks=True, vias=False, zones=True,
                      dsn_only=False)
    # autorouter: foreign tracks stay out of the top power pours (0.6 mm inside their outline)
    for z in list(C.zones):
        if z['name'].startswith('P:') and z['layer'] == 'F':
            for i, rings in enumerate(z['rings']):
                g = Polygon(rings[0], rings[1:]).buffer(-0.6, 8)
                for j, piece in enumerate([g] if g.geom_type == 'Polygon' else list(getattr(g, 'geoms', []))):
                    if piece.area > 1.0:
                        C.keepout(f"D:{z['name'][2:]}_{i}_{j}", [z['layer']], piece, tracks=True, vias=False)
    # (E2) two more router guides (gone with the other 'D:' areas once routing is done): the bottom GND plane under
    # the bulk caps, the FETs and the VM pour stays whole for the routers (the gate drive and the MIC5014 links that
    # must cross it are routed first, by hand); and no top track under J601's metal shell, which sits on the mask
    C.keepout('D:GND_PWR_B_0_0', ['B'], box(0.0, 36.0, 58.0, 84.0).intersection(edge).difference(keep_holes),
              tracks=True, vias=False)
    C.keepout('D:J601_shell_0_0', ['F'], box(99.25, 0.3, 106.35, 19.8), tracks=True, vias=True)
    # (E, review m20) solder mask open over the main current paths of the BAT and VM pours, so they can be tinned
    # or strapped with copper wire: 1 mm inside the pour, 1.5 mm from every pad of another net, off the part bodies
    # (their outlines are silkscreen; the heatsink bar rests there) and off the strips kept for markings
    others = {'BAT': [], 'VM': []}
    for ref, (x_, y_, d_, side_) in B.pos.items():
        for n_, c_, bb_, drill_ in B.pads(ref):
            pnet = B.parts[ref]['pads'].get(n_) or ''
            if side_ == 'F' or drill_ > 0:
                for net_ in others:
                    if pnet != net_:
                        others[net_].append(box(*bb_).buffer(1.5, 8))
    bar = [B.crt(r) for r, p in B.parts.items() if p['value'] == 'HEATSINK_BAR']
    # kept masked for the silkscreen: the strip under the FET row (FET bar warning), the strip below the VM pour
    # (board name), and a square east of each BAT/VM wire pad for its + sign
    keep = [box(0.0, 55.0, 60.0, 59.6), box(13.9, 36.0, 54.0, 39.9)]
    for ref, p in B.parts.items():
        if p['footprint'].startswith(('atlas:WirePad', 'Connector_Wire:')) and set(p['pads'].values()) & {'BAT', 'VM'}:
            bb_ = max((bb for n_, c_, bb, d_ in B.pads(ref)), key=lambda q: q[2] - q[0])
            cx_, cy_, r_ = (bb_[0] + bb_[2]) / 2, (bb_[1] + bb_[3]) / 2, (bb_[2] - bb_[0]) / 2
            bodies_ = [box(*B.crt(o)) for o in B.pos if o != ref and B.pos[o][3] == 'F']
            for sq in (box(cx_ + r_ + 0.2, cy_ - 2.0, cx_ + r_ + 3.8, cy_ + 2.0),
                       box(cx_ - r_ - 3.8, cy_ - 2.0, cx_ - r_ - 0.2, cy_ + 2.0),
                       box(cx_ - 2.0, cy_ + r_ + 0.2, cx_ + 2.0, cy_ + r_ + 3.8),
                       box(cx_ - 2.0, cy_ - r_ - 3.8, cx_ + 2.0, cy_ - r_ - 0.2)):
                if edge.contains(sq) and not any(sq.intersects(o) for o in bodies_):
                    keep.append(sq)              # the first side of the pad clear of other parts
                    break
    bodies = [box(*B.crt(r, 0.3)) for r in B.pos if B.pos[r][3] == 'F' and not B.is_hole(r) and
              not B.parts[r]['footprint'].startswith(('atlas:WirePad', 'Connector_Wire:'))]
    no_open = unary_union([box(b_[0] - 0.5, b_[1] - 0.5, b_[2] + 0.5, b_[3] + 0.5) for b_ in bar] + keep + bodies)
    for net_, region in (('VM', vm), ('BAT', bat)):
        g = region.intersection(edge).difference(keep_holes).buffer(-1.0, join_style=2)
        g = g.difference(unary_union(others[net_])).difference(no_open)
        C.mask('M:' + net_, 'F', g.buffer(-0.2, join_style=2).buffer(0.2, join_style=2))
    # GND fills on both layers after routing
    C.zone('F:GND_F', 'GND', 'F', edge.difference(keep_holes), priority=1, connect='tht', dsn=False)
    C.zone('F:GND_B', 'GND', 'B', edge.difference(keep_holes), priority=1, connect='tht', dsn=False)
    print('stitching vias: GND', n_gnd)
