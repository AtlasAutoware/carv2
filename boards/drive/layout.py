"""ATLAS-DRV-1 placement, copper and outline. Board-local mm, top view: X runs forward from the
rear edge, Y runs toward the car's left side from the right edge. Used by tools/build_pcb.py.

Floorplan, top view (B = on the bottom side):

  Y 90 +----------------------------------------------------------------------------------+
       | H1003  charger   H1006  B+  B-  BMS shunt  | pack sense |   USB hub, console   H1004|
       | USB-C  PD sink    main shunt, TPS48111   BMS FETs (DSG over CHG)                   |
       |        EEPROM    main switch FETs          ====== stack socket J1001 =====  flash  |
  Y 62 | button          4 x 330 uF on the VM pour          Jetson mux                 CAN   |
       | latch (B)  TVS  ------ VM band: vias down to the VM bar under the columns ---      |
  Y 45 | H1007      bottom: 12 x 10 uF straight across VM bar -> GND strip (B)     MCU  H1008|
       | motor leads      wire pads C      wire pads B      wire pads A           lidar     |
       | (corridor)       [ power stage on the bottom, on the heat spreader ]             |
       | hall            column C          column B          column A            servo buck|
       | E-stop           gate driver DRV8323RS + its buck at the board edge          servo  |
  Y 0  | H1001 fan    H1005                                                         H1002  |
       +----------------------------------------------------------------------------------+
       X 0 (rear)                                                                  X 140

Power stage columns (bottom), each from the top: VM bar, 2 high-side FETs (tabs up on the VM bar,
sources down), phase bar with the wire-pad vias, 2 low-side FETs (tabs up on the phase bar),
low-side source bar, 0.2 mOhm shunt, GND. The commutation loop closes through the 10 uF ceramics on
the bottom just above the VM bar and back down the In4 GND plane, one thin prepreg above the bottom copper.

Six layers, 2 oz each: F, In1 GND plane, In2 signals (plus the VSYS corridor and GND under the power stage),
In3 signals, In4 GND plane, B. Four layers were tried first; the autorouter could not get the gate
driver's 18 logic and sense lines past the power stage to the MCU.
The DRV8323 phase outputs are assigned right/centre/left = A/B/C so that its gate routes do not cross.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'stack'))
import stack  # noqa: E402

NAME = 'atlas_drive'
SIZE = (140.0, 90.0)
PAGE_ORIGIN = (30.0, 30.0)
COPPER_LAYERS = 6
LAYER_TYPES = {'In1': 'power', 'In2': 'mixed', 'In3': 'mixed', 'In4': 'power'}   # In1, In4 solid GND; In2, In3 signals
CORNER_R = 2.0

# mounting holes (board-local): four to the deck, two brain-board supports, two mid-edge (see mech/kit.py)
# H1005/H1002 sit under the brain board's corner spacers (Antmicro H4/H3 at brain (10.06, 5.06) and
# (115.06, 5.06), brain X = drive X - 20), H1006/H1004 under the brain's strip holes.
HOLES = {'H1001': (6.0, 6.0), 'H1002': (135.06, 5.06), 'H1003': (6.0, 84.0), 'H1004': (134.0, 84.0),
         'H1005': (30.06, 5.06), 'H1006': (26.0, 84.0), 'H1007': (6.0, 45.0), 'H1008': (134.0, 45.0)}
AUTO_MARGIN = 0.25    # auto-placed parts keep 0.5 mm between courtyards: room for a track
KEEP_AUTO = True      # the board is routed: auto-placed parts stay where the last run put them (tools/placer.py)
IC_RING = 0.6         # and 0.6 mm from the courtyard of any IC with 20+ pads (fan-out)

# power stage: phase -> column centre X. Phase A right, C left (see the docstring).
COLS = {'C': 37.5, 'B': 54.0, 'A': 70.5}
HS_Y, LS_Y, SH_Y = 41.0, 30.0, 19.0          # FET and shunt centres (Y)
PAD_Y = 35.5                                  # wire pad centre = middle of the phase bar
CAP_Y = 51.0                                  # bottom ceramics (VM pad at 49.5, GND pad at 52.5)
ESC = {  # phase: hs outer, hs inner, ls outer, ls inner, shunt, wire pad, 4 ceramics, gate R hs_o, hs_i, ls_o, ls_i
    'A': ('Q502', 'Q504', 'Q503', 'Q505', 'R512', 'J501', ('C509', 'C510', 'C511', 'C512'), ('R508', 'R510', 'R509', 'R511')),
    'B': ('Q507', 'Q509', 'Q508', 'Q510', 'R520', 'J502', ('C515', 'C516', 'C517', 'C518'), ('R516', 'R518', 'R517', 'R519')),
    'C': ('Q512', 'Q514', 'Q513', 'Q515', 'R528', 'J503', ('C521', 'C522', 'C523', 'C524'), ('R524', 'R526', 'R525', 'R527')),
}


def gate_vias(cx):
    """(hs outer, hs inner, ls outer, ls inner) gate via positions of a column."""
    return (cx - 6.9, 38.1), (cx, 42.0), (cx - 6.9, 27.1), (cx, 31.0)


def sense_vias(cx):
    """shunt Kelvin vias (SP at the phase end, SN at the GND end), right of the shunt"""
    return (cx + 4.6, SH_Y + 4.0), (cx + 4.6, SH_Y - 4.0)


# main switch and BMS rows
MAIN_Y = 65.2          # main switch FETs, sources (VM) down
DSG_Y, CHG_Y = 79.0, 71.5
BMS_X = (66.5, 72.5, 78.5, 84.5)
MAIN_X = (24.5, 30.5, 36.5, 42.5)


# net classes for the autorouter (widths in mm). High currents never rely on these: they run in the
# zones and pre-routed tracks of copper(); these are the widths for everything that still needs routing.
# Trace widths the autorouter uses. The heavy currents run in the pours (copper() below), so these only
# have to carry local supply current. Freerouting does not neck down at a pin, so a width has to fit
# between the neighbouring pads with 0.2 mm to spare on each side: 0.2 mm does that for the 0.35 mm pads
# at 0.5 mm pitch (MSOP, LGA, LQFP); the 0.2 mm pads at 0.4 mm pitch on the charger and the PD
# controller leave room for 0.15 mm only, so their signal nets are 'Fine'. So are the gate driver's
# logic nets (SPI, PWM inputs, current-sense outputs): its left edge has seven of them side by side at
# 0.5 mm pitch that all have to leave the same way, and at 0.15 mm neighbouring escapes can run
# diagonally next to each other. Their power pins are pre-routed in copper(). GND has no class: its pins
# drop straight into the planes.
NETCLASSES = {
    'Fine': {'width': 0.15, 'clearance': 0.2, 'nets': [
        'CHG_STAT_N', 'CHG_BT1', 'CHG_REGN', 'CHG_QON_N', 'CHG_SCL', 'CHG_SDA', 'CHG_TS', 'CHG_ILIM', 'CHG_BATP',
        'CHG_BT2', 'CHG_PROG', 'CHG_INT_N', 'PD_LDO3V3', 'PD_LDO1V5', 'STK_I2C_SDA', 'STK_I2C_SCL', 'PD_IRQ_N',
        'PD_DRAIN', 'USB_CC1', 'USB_CC2',
        'DRV_FAULT_N', 'DRV_MISO', 'DRV_MOSI', 'DRV_SCK', 'DRV_CS_N', 'DRV_EN', 'DRV_CAL',
        'PWM_AH', 'PWM_AL', 'PWM_BH', 'PWM_BL', 'PWM_CH', 'PWM_CL', 'CSA_A', 'CSA_B', 'CSA_C']},
    'Power': {'width': 0.2, 'clearance': 0.2, 'nets': [
        '+3V3', '+5V', '3V3_AON', 'BUCK_VIN', 'DRV_VCP', 'DRV_DVDD', 'SRV_VCC',
        'VDDA', 'VM', 'BATP', 'BATN', 'VSYS', 'CHG_PMID', 'SW_IN', 'PRE_D', 'FET_MID', 'BMS_RSN', 'CHG_SW1', 'CHG_SW2']},
    'Supply': {'width': 0.4, 'clearance': 0.2, 'via': 0.8, 'drill': 0.4, 'nets': [
        'PPHV', 'VBUS_C', 'LIDAR_V', 'SERVO_V', 'BUCK_SW']},
    # USB 2.0 high-speed pairs, routed coupled (tools/mazeroute.py --pairs): 0.15 mm tracks with a
    # 0.15 mm gap, 0.2 mm to everything else (the other classes' clearance). The class clearance is
    # 0.14, a hair under the gap, so nanometre rounding of the pair geometry does not trip DRC. Check
    # the width against JLCPCB's impedance calculator for the stack-up actually ordered (90 Ohm
    # differential) before ordering.
    'USB': {'width': 0.15, 'clearance': 0.14, 'via': 0.5, 'drill': 0.25, 'nets': [
        'USBC_DP', 'USBC_DN', 'HUB_UP_DP', 'HUB_UP_DN', 'FLASH_DP', 'FLASH_DN', 'HUB_DN1_DP', 'HUB_DN1_DN',
        'STK_USB0_DP', 'STK_USB0_DN']},
    'Gate': {'width': 0.25, 'clearance': 0.2, 'nets': [
        'GHA', 'GLA', 'GHB', 'GLB', 'GHC', 'GLC', 'GHA0', 'GHA1', 'GLA0', 'GLA1', 'GHB0', 'GHB1', 'GLB0', 'GLB1',
        'GHC0', 'GHC1', 'GLC0', 'GLC1', 'PHA', 'PHB', 'PHC', 'SPA', 'SNA', 'SPB', 'SNB', 'SPC', 'SNC', 'SW_GATE',
        'SW_G0', 'SW_G1', 'SW_G2', 'SW_G3', 'PRE_G0', 'PRE_G', 'DSG_G', 'CHG_G', 'BMS_DSG', 'BMS_CHG']},
}

# custom DRC rules (written to atlas_drive.kicad_dru). Pad gaps inside these footprints are 0.15 mm by
# their land patterns; JLCPCB's minimum for 2 oz outer copper is 0.15 mm.
FINE_PITCH = ['U1001', 'U402', 'U602', 'U801', 'U802', 'U501', 'U701']
DRU = '(version 1)\n' + ''.join(
    f'(rule "land pattern {r}" (constraint clearance (min 0.15mm)) '
    f'(condition "A.memberOfFootprint(\'{r}\') && B.memberOfFootprint(\'{r}\')"))\n' for r in FINE_PITCH) + \
    '(rule "USB-C shell pegs (GCT land pattern)" (constraint hole_clearance (min 0.15mm)) ' \
    '(condition "A.memberOfFootprint(\'J701\') || B.memberOfFootprint(\'J701\')"))\n' \
    '(rule "stack header GND pins on the inner fills: one spoke is enough, the planes and outer fills connect them too" ' \
    '(layer inner) (constraint min_resolved_spokes 1) (condition "A.memberOfFootprint(\'J1001\')"))\n'

RAILS = ['GND', '+3V3', '+5V', 'VM', 'BATP', 'VSYS', '3V3_AON', 'BATN', 'PD_LDO3V3', 'CHG_REGN', 'SERVO_V']

# areas the automatic placer must leave empty: (side, x0, y0, x1, y1)
NO_AUTO = [
    ('B', 28.0, 1.5, 82.0, 57.5),       # power stage, VM bar, ceramics, GND strip (the DRV corner is explicit)
    ('F', 29.0, 31.0, 80.0, 40.5),      # motor lead pads and their solder fillets
    ('F', 0.0, 28.0, 29.0, 42.0),       # motor lead corridor from the rear edge
    ('F', 14.0, 42.5, 80.0, 62.8),      # VM pour: bulk caps, VM band
    ('F', 21.0, 61.0, 52.0, 72.0),      # main switch FETs and SW_IN
    ('F', 60.0, 64.0, 89.0, 90.0),      # BMS FETs, BMS shunt
    ('F', 28.0, 80.0, 64.0, 90.0),      # pack leads
    ('B', 30.0, 81.0, 51.0, 90.0),      # pack leads (bottom side of the through-hole pads)
]

# escape vias defined in copper(): keep bottom parts off them
for _x in BMS_X:
    NO_AUTO.append(('B', _x - 1.91 - 0.8, 83.7 - 0.8, _x - 1.91 + 0.8, 83.7 + 0.8))
    NO_AUTO.append(('B', _x + 1.91 - 0.8, 66.35 - 0.8, _x + 1.91 + 0.8, 66.35 + 0.8))
for _x in MAIN_X + (48.5,):
    NO_AUTO.append(('B', _x + 1.91 - 0.7, 60.95 - 0.5, _x + 1.91 + 0.7, 60.95 + 0.7))
NO_AUTO.append(('B', 63.3, 65.2, 88.0, 67.4))           # CHG FET GND via row
NO_AUTO.append(('F', 17.8, 77.7, 21.8, 79.8))           # charger BAT pour and its vias
NO_AUTO.append(('B', 17.8, 77.7, 21.8, 79.8))
NO_AUTO.append(('F', 17.5, 87.6, 21.8, 89.4))           # VSYS vias to the In2 VSYS region
NO_AUTO.append(('B', 17.5, 87.6, 21.8, 89.4))
NO_AUTO.append(('B', 17.8, 76.0, 40.2, 80.1))           # BATP pour on the bottom (pack + to the charger)
NO_AUTO.append(('B', 17.8, 73.4, 31.2, 76.4))
NO_AUTO.append(('B', 40.6, 76.2, 51.7, 89.9))           # BATN pour on the bottom
NO_AUTO.append(('F', 22.5, 74.4, 24.3, 78.3))           # GND vias of the BAT caps C727/C728
NO_AUTO.append(('F', 115.5, 17.6, 117.3, 20.1))         # VM feed vias of the servo buck
NO_AUTO.append(('F', 112.7, 7.8, 134.0, 13.3))          # servo output copper: module to the header
NO_AUTO.append(('F', 130.0, 10.7, 134.0, 29.5))
NO_AUTO.append(('F', 132.8, 15.3, 138.4, 17.7))
NO_AUTO.append(('B', 14.0, 42.8, 16.1, 46.8))           # D302 GND island vias
NO_AUTO.append(('F', 116.8, 21.7, 128.2, 24.8))         # servo buck input-cap GND and its vias
NO_AUTO.append(('F', 112.7, 3.0, 127.2, 6.7))           # servo buck output-cap GND and its vias
NO_AUTO.append(('B', 115.5, 17.6, 117.3, 20.1))
# gate driver fan-out: logic vias left of it, PWM vias under it, phase A's gate bundle up its right edge,
# and the gate/sense runs from its top edge into the columns
NO_AUTO.append(('F', 39.5, 0.4, 59.5, 14.9))
NO_AUTO.append(('F', 33.0, 0.4, 39.9, 14.0))           # column C GND via grid and the buck output caps; column A grid
NO_AUTO.append(('F', 67.6, 7.0, 73.4, 14.0))
NO_AUTO.append(('F', 59.5, 0.4, 66.5, 14.2))
NO_AUTO.append(('F', 57.9, 11.6, 62.0, 15.0))
NO_AUTO.append(('F', 40.5, 14.2, 78.0, 24.5))

# parts the automatic placer must put on a given side: the small passives of the switch controller
# and the BMS sit on the bottom under their ICs (the top there is power copper)
SIDE = {r: 'F' for r in ['R304', 'R305', 'R306', 'R307', 'R308', 'R309', 'R310', 'R311', 'R312', 'R313', 'C301',
                         'C304', 'D301']}
SIDE.update({r: 'B' for r in ['R302', 'R303', 'C302', 'C303',
                         'R201', 'R202', 'R203', 'R204', 'R205', 'C201', 'C202', 'C203', 'C204', 'R206', 'C205',
                         'C206', 'R207', 'R208', 'R209', 'R210', 'R211', 'R212', 'R213', 'C207', 'R215', 'R216',
                         'R217', 'R218']})

_placed = []


def placed_refs():
    return list(_placed)


def place_all(B):
    def pl(ref, x, y, rot=0, side='F'):
        B.place(ref, x, y, rot, side)
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

    # ================================================================ power stage (bottom)
    for ph, (hso, hsi, lso, lsi, sh, pad, caps, gr) in ESC.items():
        cx = COLS[ph]
        fc(hso, cx - 3.3, HS_Y, ['1', '2', '3'], 'down', 'B')    # sources down onto the phase bar
        fc(hsi, cx + 3.3, HS_Y, ['1', '2', '3'], 'down', 'B')
        fc(lso, cx - 3.3, LS_Y, ['1', '2', '3'], 'down', 'B')    # drain tabs up on the phase bar
        fc(lsi, cx + 3.3, LS_Y, ['1', '2', '3'], 'down', 'B')
        fc(sh, cx, SH_Y, ['1'], 'up', 'B')                         # current pad 1 (low-side sources) up
        pl(pad, cx, PAD_Y, 0, 'F')
        for i, c in enumerate(caps):                               # VM pad down on the VM bar
            fn(c, cx - 5.1 + 3.4 * i, CAP_Y, 'VM', 'down', 'B')
        (ho, hi, lo, li) = gate_vias(cx)
        rhso, rhsi, rlso, rlsi = gr
        fn(rhso, ho[0], ho[1] + 2.0, f'GH{ph}0', 'down')           # gate resistors on top next to their vias
        fn(rhsi, hi[0] + 1.6, hi[1], f'GH{ph}1', 'left')
        # column B's sits 0.55 mm closer to its via: the driver's C-phase gate pair fans out past its
        # bottom-left corner, between phase B's pair and GLC
        fn(rlso, lo[0], lo[1] - (1.45 if ph == 'B' else 2.0), f'GL{ph}0', 'up')
        fn(rlsi, li[0], li[1] - 1.8, f'GL{ph}1', 'up')
    fn('TH501', 77.6, 33.0, 'TEMP_PCB', 'down', 'B')               # FET NTC on the bottom beside column A's phase bar
    # phase-voltage dividers (39k tops) on the bottom in the gaps between the columns, touching the phase
    # bars; copper() runs the divided signals down the gaps to vias above the driver row
    # phase A's divider bottom and filter cap on the bottom beside SENS_A's via under the MCU's corner:
    # on top, the auto placer boxed them in west of PA0-PA2 (VDDA's via, the SENS_B loop and the In3
    # hall/kill lanes left no way out for PHF_A or SENS_A's via). PHF_A then runs up the bottom under the
    # MCU's west pins to its switch.
    fn('R507', 87.9, 16.3, 'SENS_A', 'right', 'B')
    fn('C508', 88.0, 19.2, 'SENS_A', 'down', 'B')
    fn('R522', 44.5, 35.5, 'PHC', 'left', 'B')
    fn('R514', 47.0, 35.5, 'PHB', 'right', 'B')
    fn('R506', 63.8, 35.5, 'PHA', 'right', 'B')

    # ================================================================ gate driver (top, board edge)
    # Turned 180 degrees so each group of pins faces where it goes: gate and sense pins of phases C and B
    # along the top edge (C left, B right) and of phase A on the right edge fan straight up into their
    # columns; the logic pins (left edge, PWM inputs on the bottom-left) drop through vias to In2 and run
    # to the MCU under the driver; VM, the charge pump and the buck FB sit on the right edge below phase A.
    # The EP's thermal vias land in column B's GND end on the bottom.
    pl('U501', 54.0, 11.0, 180)
    fn('C503', 60.6, 10.1, 'VM', 'up')                             # VCP to VM: VM pad level with the VM pins
    fn('C504', 60.8, 7.05, 'DRV_CPH', 'up')                        # charge pump flying cap below it
    fn('C501', 63.7, 11.0, 'VM', 'left')                           # VM decoupling where the VM feed arrives
    fn('C502', 63.8, 7.9, 'VM', 'up')
    # buck: its pins (CB SW VIN nSHDN) sit bottom-right, next to the PWM inputs, while B+, the enable and
    # the inductor side all lie to the left. CB/SW cap under the pins; SW, VIN and nSHDN drop through vias
    # and run left on the bottom (below the driver's GND pour, see copper()), so the PWM inputs keep the
    # space under the driver for their vias. VIN caps stay at the VIN pin, FB divider right beside them.
    fn('C409', 54.8, 6.0, 'BUCK_CB', 'left')
    fn('C408', 57.6, 4.4, 'BUCK_VIN', 'up')                        # VIN 100 nF at the pin
    fn('C407', 59.6, 3.0, 'BUCK_VIN', 'up')                        # VIN 4.7 uF
    fn('R408', 62.4, 3.6, 'BUCK_FB', 'left')                       # FB divider
    fn('R407', 62.4, 1.6, 'BUCK_FB', 'left')
    fn('R406', 48.8, 1.5, 'BUCK_VIN', 'right')                     # 10 ohm from B+, where B+ arrives
    fn('D402', 46.0, 4.6, 'BUCK_SW', 'left')                       # catch diode
    fn('L401', 40.4, 4.4, 'BUCK_SW', 'right')
    fn('C410', 35.6, 3.2, '+5V', 'right')                          # +5V output at the inductor
    fn('C411', 35.7, 6.6, '+5V', 'right')
    pl('U404', 75.6, 3.0, 0)                                       # 3.3 V LDO where +5V meets the MCU side
    fn('C505', 48.4, 7.9, 'DRV_DVDD', 'right')                     # DVDD at the bottom of the left edge
    fn('C506', 48.85, 13.25, '+3V3', 'right')                      # VREF straight left of its pin
    pl('TP1008', 62.1, 17.6, 0, 'B')                               # VM test pad on the bottom VM feed
    for i, (ref, net) in enumerate((('R505', 'CSA_A'), ('R513', 'CSA_B'), ('R521', 'CSA_C'))):
        fn(ref, 81.2, 7.3 + 1.2 * i, net, 'left')                  # current-sense series R at the MCU end
    for i, (ref, net) in enumerate((('R501', 'DRV_FAULT_N'), ('R502', 'DRV_MISO'), ('R503', 'DRV_CS_N'))):
        fn(ref, 78.7, 7.3 + 1.2 * i, net, 'left')                  # fault and SPI pull-ups
    # ================================================================ DC link (top)
    for i, ref in enumerate(('C525', 'C526', 'C527', 'C528')):
        fn(ref, 23.9 + 12.8 * i, 53.9, 'VM', 'left')               # GND pads over the bottom GND strip
    fn('D302', 20.5, 44.8, 'VM', 'right')                          # VM TVS, GND pad over free bottom copper

    # ================================================================ main switch (top)
    for i, ref in enumerate(('Q302', 'Q303', 'Q304', 'Q305')):
        fc(ref, MAIN_X[i], MAIN_Y, ['1', '2', '3'], 'down')        # sources down to VM, tabs up to SW_IN
    fc('Q306', 48.5, MAIN_Y, ['1', '2', '3'], 'down')              # precharge FET
    fn('R319', 48.5, 70.8, 'SW_IN', 'left')                        # precharge resistors 2512: SW_IN left, PRE_D over Q306's tab,
    fn('R320', 48.5, 70.8, 'SW_IN', 'left', 'B')                   # the second one right under the first, on the bottom
    fn('R301', 33.5, 74.5, 'BATP', 'up')                           # main shunt: B+ end up toward J101
    pl('J101', 34.5, 85.5, 0)                                      # B+ lead
    pl('U301', 42.0, 75.8, 180)                                    # TPS48111: sense/gate/VS pins face the shunt (Kelvin traces run under its body)
    pl('Q301', 39.5, 66.8, 0, 'B')                                 # temperature sense transistor under the FET tabs
    for i, ref in enumerate(('R314', 'R315', 'R316', 'R317')):     # gate resistors on the bottom under the gate pins
        fn(ref, MAIN_X[i] + 1.91, 59.6, f'SW_G{i}', 'up', 'B')
    fn('R318', 50.41, 59.6, 'PRE_G', 'up', 'B')
    fn('D101', 40.5, 79.0, 'BATP', 'left', 'B')                    # pack TVS between the two lead pads (bottom)

    # ================================================================ BMS (top; U1001 bottom)
    pl('J102', 46.5, 85.5, 0)                                      # B- lead
    fn('R214', 57.9, 85.5, 'BATN', 'left')                         # BMS shunt, B- end toward J102
    for i, ref in enumerate(('Q201', 'Q203', 'Q205', 'Q207')):
        fc(ref, BMS_X[i], DSG_Y, ['1', '2', '3'], 'up')            # DSG: sources up (shunt side), tabs down
    for i, ref in enumerate(('Q202', 'Q204', 'Q206', 'Q208')):
        fc(ref, BMS_X[i], CHG_Y, ['1', '2', '3'], 'down')          # CHG: tabs up (common drain), sources down to GND
    pl('U201', 57.5, 76.0, 90)                                     # BQ7791508
    pl('U1001', 57.9, 79.5, 0, 'B')                                # INA228 under the BMS shunt sense pads
    pl('J103', 106.5, 80.0, 180)                                   # pack sense, opening toward the left edge

    # ================================================================ USB-C and PD sink (rear left)
    pl('SW401', 2.9, 51.7, 90)                                     # power button at the rear edge
    pl('J401', 6.5, 59.5, 270)                                     # external button lead, opening at the rear edge
    pl('J701', 3.2, 67.5, 270)                                     # USB-C, opening at the rear edge
    pl('D701', 9.8, 67.5, 90)                                      # USB ESD next to D+/D-
    pl('C702', 9.1, 64.1, 0)                                       # CC1 (0.2 mm left of the old spot: CC2 passes
    pl('C703', 9.1, 62.9, 0)                                       # CC2  between C703 and the PD pins)
    pl('U701', 12.8, 61.8, 90)                                     # TPS25751D, VBUS/PPHV pads up
    fn('C701', 10.3, 71.3, 'VBUS_C', 'down')                       # VBUS input cap at the connector
    fn('D702', 9.6, 69.0, 'VBUS_C', 'up', 'B')                     # VBUS TVS (bottom)
    fn('C708', 17.0, 64.0, 'PPHV', 'up')                           # PPHV output caps, PPHV pads level with the PPHV
    fn('C709', 19.6, 64.0, 'PPHV', 'up')                           # pin; the I2C lines pass between their pads
    fn('C705', 11.0, 56.3, 'PD_LDO3V3', 'up')                      # LDO caps under the LDO pins
    fn('C706', 13.3, 56.7, 'PD_LDO1V5', 'up')
    fn('C704', 9.2, 60.5, '+3V3', 'right', 'B')                   # VIN_3V3 and PP5V caps (bottom, under the pins)
    fn('C707', 9.2, 57.7, '+5V', 'right', 'B')                     # (0.5 mm lower: room for the VIN_3V3 via)
    pl('U702', 19.5, 57.5, 0, 'B')                                 # config EEPROM (bottom)
    pl('J702', 11.8, 23.5, 0)                                      # EEPROM programming header (DNP), rear strip

    # ================================================================ charger (rear left): BQ25798 per TI's layout guide
    # PMID, GND and SYS fan straight out of the power-pin row on top with the 0.1 uF + 10 uF parts right
    # at the pins; SW1/SW2 drop through vias under the IC to the inductor directly below on the bottom.
    CX, CY = 15.5, 77.2
    pl('U703', CX, CY, 0)                                          # power row (PMID SW1 GND SW2 SYS) on top
    fn('L701', CX, CY, 'CHG_SW1', 'left', 'B')                     # inductor under the IC
    fn('C714', 14.35, 80.3, 'CHG_PMID', 'left')                    # PMID 100 nF | GND
    fn('C721', 16.95, 80.4, 'VSYS', 'right')                       # GND | SYS 100 nF (the SYS neck passes under it)
    for i, (cp, cs) in enumerate((('C715', 'C722'), ('C716', 'C723'), ('C717', 'C724'))):
        fn(cp, 14.25, 82.2 + 2.2 * i, 'CHG_PMID', 'left')          # PMID 10 uF | GND
        fn(cs, 17.75, 82.2 + 2.2 * i, 'VSYS', 'right')             # GND | SYS 10 uF
    fn('C725', 21.3, 80.95, 'VSYS', 'left')
    fn('C726', 20.8, 81.6, 'VSYS', 'left', 'B')
    fn('C711', 12.05, 78.5, 'PPHV', 'right')                       # VBUS 100 nF at pins 2-3 (BTST1 passes under it)
    fn('C718', 11.45, 76.6, 'CHG_REGN', 'right')                   # REGN at pin 5
    fn('C712', 10.0, 80.05, 'PPHV', 'down')                        # VBUS 10 uF
    fn('C713', 10.7, 83.6, 'PPHV', 'down')
    fn('C727', 21.2, 77.4, 'BATP', 'left', 'B')                    # BAT 10 uF (bottom, on the BATP pour to J101)
    fn('C728', 21.2, 75.2, 'BATP', 'left', 'B')
    fn('C719', 10.6, 79.0, 'CHG_BT1', 'right', 'B')                # bootstrap caps (bottom, beside the inductor)
    fn('C720', 19.6, 72.6, 'CHG_BT2', 'up', 'B')

    # ================================================================ power button latch (rear strip, bottom)
    pl('U401', 12.0, 50.0, 0, 'B')                                 # always-on LDO
    pl('U402', 17.0, 50.0, 0, 'B')                                 # latch flip-flop
    pl('U403', 17.0, 45.0, 0, 'B')                                 # button sense buffer
    pl('Q401', 12.0, 45.0, 0, 'B')                                 # MCU kill
    pl('D403', 11.0, 40.0, 0, 'B')                                 # power LED

    # ================================================================ rear edge connectors
    pl('J603', 3.2, 20.5, 90)                                      # hall sensor lead
    pl('J504', 3.4, 13.5, 90)                                      # E-stop loop
    pl('J903', 11.7, 4.5, 0)                                       # fan (fan sits outboard of the right edge)

    # ================================================================ MCU (top)
    pl('U601', 93.0, 24.0, 0)
    pl('Y601', 84.3, 27.5, 90)
    pl('J601', 105.5, 33.5, 0)                                     # SWD
    pl('U602', 106.0, 19.0, 0)                                     # IMU
    pl('D601', 104.5, 10.5, 0)
    pl('D602', 108.0, 10.5, 0)

    # ================================================================ stack socket (top)
    x1, y1 = stack.pin_xy_drive(1)
    best = None
    for rot in (0, 90, 180, 270):
        B.anchor_pad('J1001', '1', x1, y1, rot, 'F')
        p2, p3 = B.pad_xy('J1001', '2'), B.pad_xy('J1001', '3')
        e2, e3 = stack.pin_xy_drive(2), stack.pin_xy_drive(3)
        err = abs(p2[0] - e2[0]) + abs(p2[1] - e2[1]) + abs(p3[0] - e3[0]) + abs(p3[1] - e3[1])
        if best is None or err < best[0]:
            best = (err, rot)
    B.anchor_pad('J1001', '1', x1, y1, best[1], 'F')
    _placed.append('J1001')

    # ================================================================ USB hub cluster (top, front left)
    pl('U802', 72.0, 55.0, 0)                                      # Jetson-side mux, under the socket's USB0 pins
    pl('U801', 103.0, 71.0, 0)                                     # USB-C-side mux
    pl('U803', 116.0, 71.0, 0)                                     # USB2514B
    pl('Y801', 116.0, 78.5, 0)
    pl('U804', 127.5, 70.0, 0)                                     # CP2102N
    pl('SW801', 137.0, 70.0, 90)                                   # flash switch at the front edge
    pl('D801', 122.0, 78.0, 0)
    pl('D803', 125.0, 78.0, 0)
    pl('D804', 128.0, 78.0, 0)
    pl('D802', 97.0, 68.5, 0)
    pl('U1002', 99.0, 57.0, 0)                                     # board ID EEPROM next to the socket I2C pins

    # ================================================================ outputs (top, front)
    # servo buck: VIN caps across the top (VM pour), VOUT caps along the bottom (SERVO_V pour) which runs
    # right, around the H1002 pad and up to the servo pin and the 220 uF can
    pl('U901', 122.0, 14.5, 0)                                     # TPSM63610
    for i, ref in enumerate(('C901', 'C902', 'C903')):
        fn(ref, 118.9 + 3.4 * i, 21.1, 'VM', 'down')
    fn('C904', 127.2, 17.6, 'VM', 'down')
    fn('R906', 117.55, 15.95, 'SRV_RBOOT', 'up')                   # bootstrap resistor between pins 2 and 3
    for i, ref in enumerate(('C906', 'C907', 'C908')):
        fn(ref, 118.4 + 3.4 * i, 7.2, 'SERVO_V', 'up')
    fn('C909', 114.9, 9.0, 'SERVO_V', 'up')
    fn('C910', 127.5, 28.2, 'SERVO_V', 'right')
    pl('J901', 137.2, 19.0, 0)                                     # servo, pins along the front edge
    pl('U604', 134.6, 25.4, 0)
    pl('U902', 122.0, 38.0, 0)                                     # lidar eFuse
    pl('J902', 136.0, 35.5, 90)                                    # lidar power terminal, entry at the front edge
    fn('D901', 128.5, 38.0, 'LIDAR_V', 'up')
    pl('U603', 124.0, 53.0, 0)                                     # CAN transceiver
    pl('J602', 136.8, 54.0, 90)                                    # CAN port
    pl('D603', 130.0, 58.5, 0)
    pl('JP601', 129.5, 51.2, 0)

    # ================================================================ holes and test points
    for ref, (x, y) in HOLES.items():
        pl(ref, x, y, 0)


# ----------------------------------------------------------------------------- copper
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


# ----------------------------------------------------------------------------- copper (computed in placer.py)
def copper(B, C):
    """Zones, via arrays and the pre-routed escapes. Zone names: 'P:' power copper that exists while
    autorouting (the router sees it as planes/obstacles), 'F:' fills added after routing."""
    from shapely.geometry import box, Polygon, Point, LineString
    from shapely.ops import unary_union
    W, H = SIZE
    edge = box(0.3, 0.3, W - 0.3, H - 0.3)
    made = []                       # (net, layer, geom) of zones already defined, for mutual clearance

    def obst(net, layer, grow):
        g = []
        for pnet, bb, d, side, ref, n in C.pads_all():
            if pnet == net and pnet:
                continue
            if d > 0 or side == layer:
                g.append(box(bb[0] - grow, bb[1] - grow, bb[2] + grow, bb[3] + grow))
        for v in C.vias:
            if v['net'] != net:
                g.append(Point(v['x'], v['y']).buffer(v['dia'] / 2 + grow, 16))
        for t in C.tracks:
            if t['net'] != net and t['layer'] == layer:
                g.append(LineString(t['pts']).buffer(t['width'] / 2 + grow, 8))
        for znet, zl, zg in made:
            if znet != net and zl == layer:
                g.append(zg.buffer(grow, 8))
        return unary_union(g)

    def zone(name, net, layer, region, prio=10, grow=0.25, keep=None, raw=False, **kw):
        # raw: inner planes keep their plain outline; KiCad's fill makes the antipads, and the
        # autorouter only needs the outline to know where the plane is
        g = region.intersection(edge) if raw else region.intersection(edge).difference(obst(net, layer, grow))
        if keep is not None:
            g = g.difference(keep)
        g = g.buffer(-0.12, 8).buffer(0.12, 8)          # drop slivers
        polys = [g] if g.geom_type == 'Polygon' else [p for p in getattr(g, 'geoms', [])]
        polys = [p for p in polys if p.area > 0.5]
        for i, p in enumerate(polys):
            C.zone(f'{name}' + (f'_{i}' if len(polys) > 1 else ''), net, layer, p, priority=prio, **kw)
            made.append((net, layer, p))
        return polys

    def T(pts, net, layer='B', w=0.3):
        C.track(pts, w, layer, net)

    def V(x, y, net, drill=0.3, dia=0.6):
        if not C.via(x, y, net, drill, dia):
            raise RuntimeError(f'escape via {net} at ({x}, {y}) blocked')

    # ---------------------------------------------------------------- escapes: ESC gates and shunt Kelvin lines
    for ph, (hso, hsi, lso, lsi, sh, pad, caps, gr) in ESC.items():
        cx = COLS[ph]
        (ho, hi, lo, li) = gate_vias(cx)
        T([(cx - 5.2, HS_Y - 2.9), ho], f'GH{ph}0')
        V(*ho, f'GH{ph}0')
        T([(cx + 1.4, HS_Y - 2.9), (cx, HS_Y - 2.9), hi], f'GH{ph}1')
        V(*hi, f'GH{ph}1')
        T([(cx - 5.2, LS_Y - 2.9), lo], f'GL{ph}0')
        V(*lo, f'GL{ph}0')
        T([(cx + 1.4, LS_Y - 2.9), (cx, LS_Y - 2.9), li], f'GL{ph}1')
        V(*li, f'GL{ph}1')
        sp, sn = sense_vias(cx)
        T([(cx + 3.2, SH_Y + 4.03), sp], f'SP{ph}')
        V(*sp, f'SP{ph}')
        T([(cx + 3.2, SH_Y - 4.03), sn], f'SN{ph}')
        V(*sn, f'SN{ph}')
    # ---------------------------------------------------------------- DRV8323 VM feed
    # The driver's VM pins face right, boxed in by the charge pump below and phase A's gate fan-out
    # above, so VM arrives from underneath: down the bottom-side gap between columns B and A from the
    # VM bar, then up through a via beside the VM decoupling. The bottom GND pour steps around it.
    T([(62.1, 40.3), (62.1, 11.0)], 'VM', 'B', 0.4)
    V(62.1, 11.0, 'VM', 0.3, 0.6)
    # divided phase voltages: stubs into the phase bars, then down the column gaps on the bottom to vias
    # just above the driver row, where In2 takes them to the MCU
    def padc(ref, net):
        return [c for n, c, bb, d in B.pads(ref) if B.parts[ref]['pads'].get(n) == net][0]
    for ref, ph, bar_x in (('R522', 'PHC', 43.1), ('R514', 'PHB', 48.4), ('R506', 'PHA', 64.9)):
        x, y = padc(ref, ph)
        T([(x, y), (bar_x, y)], ph, 'B', 0.3)
    for ref, net, lane in (('R522', 'SENS_C', 44.6), ('R514', 'SENS_B', 46.1), ('R506', 'SENS_A', 62.95)):
        x, y = padc(ref, net)
        T([(x, y), (x, y - 0.8), (lane, y - 1.2), (lane, 12.4)], net, 'B', 0.2)
        V(lane, 12.4, net)
    # buck (see place_all): SW, VIN and nSHDN leave the driver's bottom-right pins through vias and run
    # left on the bottom under the PWM-input vias, SW highest, nSHDN along the edge
    sw_c = padc('C409', 'BUCK_SW')
    T([sw_c, (55.4, 4.9)], 'BUCK_SW', 'F', 0.4)
    V(55.4, 4.9, 'BUCK_SW')
    T([(55.4, 4.9), (55.4, 2.3), (44.6, 2.3)], 'BUCK_SW', 'B', 0.4)
    V(44.6, 2.3, 'BUCK_SW')
    sw_d = padc('D402', 'BUCK_SW')
    sw_l = padc('L401', 'BUCK_SW')
    T([(44.6, 2.3), (sw_d[0], sw_d[1])], 'BUCK_SW', 'F', 0.4)
    T([(sw_d[0], sw_d[1]), (sw_l[0], sw_d[1])], 'BUCK_SW', 'F', 0.4)
    vin = B.pad_xy('U501', '47')
    c408 = padc('C408', 'BUCK_VIN')
    c407 = padc('C407', 'BUCK_VIN')
    r406 = padc('R406', 'BUCK_VIN')
    T([vin, (vin[0], 5.9)], 'BUCK_VIN', 'F', 0.25)
    V(vin[0], 5.9, 'BUCK_VIN')
    T([(vin[0], 5.9), c408, c407], 'BUCK_VIN', 'F', 0.25)
    T([(vin[0], 5.9), (vin[0], 1.55), (51.2, 1.55)], 'BUCK_VIN', 'B', 0.25)
    V(51.2, 1.55, 'BUCK_VIN')
    T([(51.2, 1.55), r406], 'BUCK_VIN', 'F', 0.25)
    en = B.pad_xy('U501', '48')
    T([en, (en[0] + 0.25, 6.2)], 'BUCK_EN', 'F', 0.2)
    V(en[0] + 0.25, 6.2, 'BUCK_EN')
    T([(en[0] + 0.25, 6.2), (en[0] + 0.25, 0.85), (40.0, 0.85)], 'BUCK_EN', 'B', 0.2)
    ga = padc('D402', 'GND')
    T([ga, (ga[0], 3.25)], 'GND', 'F', 0.4)                     # via below the diode: the space above
    V(ga[0], 3.25, 'GND')                                       # is the logic escapes' way under the driver
    # ---------------------------------------------------------------- escapes: gate driver logic pins
    # Seven logic pins side by side on the driver's left edge and six PWM inputs along its bottom edge
    # all have to reach the MCU, up and to the right. Each row leaves through a ladder of 0.5 mm vias
    # stepping away from the pins. Every via sits 0.1 mm off its own pin line, so the next pin's
    # 0.15 mm track passes it 0.6 mm away (0.28 mm clear); from the vias the inner layers take them
    # under the driver. VREF's capacitor sits straight left of its pin, clear of the ladder.
    def upad(net):
        return B.pad_xy('U501', [n for n, v in B.parts['U501']['pads'].items() if v == net][0])
    for k, net in enumerate(('DRV_FAULT_N', 'DRV_MISO', 'DRV_MOSI', 'DRV_SCK', 'DRV_CS_N', 'DRV_EN', 'DRV_CAL')):
        px, py = upad(net)
        vx, vy = px - 1.2125 - 0.6 * k, py + 0.1
        T([(px, py), (vx + 0.1, py), (vx, vy)], net, 'F', 0.15)
        V(vx, vy, net, 0.25, 0.5)
    for k, net in enumerate(('PWM_AH', 'PWM_AL', 'PWM_BH', 'PWM_BL', 'PWM_CH', 'PWM_CL')):
        px, py = upad(net)
        vx, vy = px - 0.1, py - 0.9625 - 0.6 * k
        T([(px, py), (px, vy + 0.1), (vx, vy)], net, 'F', 0.15)
        V(vx, vy, net, 0.25, 0.5)
    T([upad('+3V3'), padc('C506', '+3V3')], '+3V3', 'F', 0.25)
    gv = padc('C506', 'GND')
    T([gv, (47.3, gv[1])], 'GND', 'F', 0.25)
    V(47.3, gv[1], 'GND')
    gd = padc('C505', 'GND')                                    # DVDD cap: GND down onto the diode's GND pad
    T([gd, (gd[0], ga[1])], 'GND', 'F', 0.25)
    # ---------------------------------------------------------------- escapes: main switch gates (top pin -> via -> bottom resistor)
    for i, ref in enumerate(('Q302', 'Q303', 'Q304', 'Q305', 'Q306')):
        xg = (MAIN_X + (48.5,))[i] + 1.91
        net = f'SW_G{i}' if i < 4 else 'PRE_G'
        T([(xg, 62.3), (xg, 60.95)], net, 'F')
        V(xg, 60.95, net)
        T([(xg, 60.95), (xg, 60.3)], net, 'B')
    # ---------------------------------------------------------------- second precharge resistor (bottom): a via into each pour
    V(44.3, 70.8, 'SW_IN', 0.3, 0.6)
    T([(44.3, 70.8), (45.5, 70.8)], 'SW_IN', 'B', 0.6)
    V(51.6, 68.6, 'PRE_D', 0.3, 0.6)
    T([(51.6, 68.6), (51.5, 69.6)], 'PRE_D', 'B', 0.6)

    # ---------------------------------------------------------------- escapes: BMS gates
    for x in BMS_X:
        T([(x - 1.91, 81.9), (x - 1.91, 83.7)], 'DSG_G', 'F')       # DSG gate up into a notch in the BMS_RSN pour
        V(x - 1.91, 83.7, 'DSG_G')
        T([(x + 1.91, 68.6), (x + 1.91, 66.35)], 'CHG_G', 'F')      # CHG gate down into a notch in the CHG GND pour
        V(x + 1.91, 66.35, 'CHG_G')

    # ---------------------------------------------------------------- charger: SW1/SW2 through vias under the IC to the inductor below
    for y in (77.75, 76.95, 76.15):
        C.via(14.75, y, 'CHG_SW1', 0.3, 0.55, check=False)
        C.via(16.25, y, 'CHG_SW2', 0.3, 0.55, check=False)

    # ---------------------------------------------------------------- via arrays
    n_vm = C.via_grid('VM', box(31.0, 44.85, 77.0, 48.2), 1.2, 0.4, 0.8)           # VM pour (top) -> VM bar (bottom)
    # column GND ends -> planes, in each shunt's shadow. The grids start at Y 7.4, like the bottom GND pour:
    # under that the driver's logic and the buck lines run on In2 and the bottom; column B has none: the driver sits there, its thermal vias do
    # the job and the bottom GND pour carries the rest sideways to the grids of columns A and C.
    n_gc = C.via_grid('GND', box(COLS['C'] - 3.7, 7.4, COLS['C'] + 2.0, SH_Y - 5.4), 1.25, 0.4, 0.8)
    n_gc += C.via_grid('GND', box(COLS['A'] - 2.5, 7.4, COLS['A'] + 2.5, SH_Y - 5.4), 1.25, 0.4, 0.8)
    # GND strip above the ceramics; around the Jetson-side USB switch (U802) only the row next to the
    # ceramics, so its three USB pairs have a way out to the socket and to the hub side
    n_gs = C.via_grid('GND', box(30.8, 53.9, 78.2, 57.9).difference(box(68.5, 55.0, 78.3, 57.9)), 1.3, 0.4, 0.8)
    n_ch = C.via_grid('GND', box(63.4, 65.5, 88.0, 67.25), 1.2, 0.4, 0.8)          # CHG FET sources -> planes
    islands = []
    for ref in ('C525', 'C526', 'C527', 'C528'):                                   # bulk-cap GND islands in the VM pour
        g = C.pad_box(ref, '2')
        x0, y0, x1, y1 = g.bounds
        isl = box(x0 - 0.35, y0 - 0.35, x1 + 0.35, 59.0)
        islands.append(isl)
        C.via_grid('GND', box(x0, y1 + 0.35, x1, 58.9), 1.2, 0.4, 0.8)
    g = C.pad_box('D302', '2')
    x0, y0, x1, y1 = g.bounds
    islands.append(box(x0 - 1.6, y0 - 0.35, x1 + 0.35, y1 + 0.35))
    for y in (y0 + 0.4, (y0 + y1) / 2, y1 - 0.4):
        C.via(x0 - 0.8, y, 'GND', 0.4, 0.8)
    for x, y in ((15.0, 81.1), (16.0, 81.1), (15.2, 83.3), (16.0, 83.3), (15.2, 85.5), (16.0, 85.5), (15.6, 87.7)):
        C.via(x, y, 'GND', 0.3, 0.55)                                              # charger GND bus
    for x in (18.55, 19.35, 20.15, 20.95):                                         # BAT pins -> bottom BATP pour
        for y in (78.55, 79.35):                                                   # (8 x 0.3 mm for up to 5 A)
            V(x, y, 'BATP')
    for x in (18.1, 19.1, 20.1, 21.1):                                             # SYS bus -> In2 VSYS region
        V(x, 88.45, 'VSYS', 0.4, 0.8)
    for ref in ('C727', 'C728'):                                                   # BAT caps' GND: via beside the pad,
        x0, y0, x1, y1 = C.pad_box(ref, '2').bounds                                # the BATP pour closes around both
        yc = (y0 + y1) / 2
        V(x1 + 0.75, yc, 'GND')
        T([((x0 + x1) / 2, yc), (x1 + 0.75, yc)], 'GND', 'B', 0.6)

    # ---------------------------------------------------------------- top power copper
    esc_ks = [box(29.1, 68.9, 31.3, 73.2), box(29.1, 76.6, 31.3, 80.3)]           # main shunt Kelvin pad exits
    zone('P:VM_F', 'VM', 'F', Polygon([(14.5, 43.2), (80.5, 43.2), (80.5, 50.4), (68.9, 50.4), (68.9, 59.0),
                                       (59.3, 59.0), (59.3, 62.65), (21.3, 62.65), (21.3, 61.3), (16.0, 61.3),
                                       (16.0, 57.8), (14.5, 57.8)]), keep=unary_union(islands).buffer(0.25))
    for i, isl in enumerate(islands):
        zone(f'P:GND_ISL{i}', 'GND', 'F', isl, prio=11)
    zone('P:SW_IN_F', 'SW_IN', 'F', Polygon([(21.3, 63.3), (45.8, 63.3), (45.8, 68.95), (46.6, 68.95), (46.6, 72.8),
                                             (24.5, 72.8), (24.5, 69.0), (21.3, 69.0)]), keep=esc_ks[0])
    zone('P:PRE_D_F', 'PRE_D', 'F', Polygon([(46.1, 63.6), (52.3, 63.6), (52.3, 72.6), (50.6, 72.6), (50.6, 68.95),
                                             (46.1, 68.95)]))
    zone('P:BATP_F', 'BATP', 'F', box(30.0, 76.9, 39.6, 89.7), keep=esc_ks[1])
    zone('P:BATN_F', 'BATN', 'F', box(42.0, 81.3, 55.6, 89.7), keep=box(52.2, 80.8, 55.6, 83.2))
    zone('P:BMS_RSN_F', 'BMS_RSN', 'F', box(60.3, 81.1, 88.2, 89.7), keep=box(60.2, 80.6, 63.6, 83.2))
    zone('P:FET_MID_F', 'FET_MID', 'F', box(63.9, 69.9, 87.1, 80.6))
    zone('P:GND_CHG_F', 'GND', 'F', box(63.3, 65.2, 88.0, 69.5))
    # ---------------------------------------------------------------- 0.4 mm-pitch pins: the power pins by hand
    # The charger (BQ25798 VQFN-HR) and the PD controller (TPS25751D WQFN) have 0.2 mm pads 0.2 mm apart.
    # Pours cannot reach into that row (their slivers vanish) and the router's power widths do not fit, so
    # the power and ground pins leave on pad-wide necks drawn here; the router takes the signals ('Fine').
    # charger, top row: PMID -> C714, GND -> the GND bus, SYS under C721's GND pad -> C721 / SYS pour
    T([(14.6, 78.95), (14.6, 79.5), (14.25, 79.85), (13.87, 80.3)], 'CHG_PMID', 'F', 0.2)
    T([(15.5, 78.95), (15.5, 80.3)], 'GND', 'F', 0.2)
    T([(16.4, 78.95), (16.4, 79.745), (17.43, 79.745), (17.43, 80.4)], 'VSYS', 'F', 0.2)
    # left column: VBUS 2+3 -> C711; VAC2 (8) and VAC1 (9, an L-shaped corner pad) joined by a stub whose
    # left end the router picks up; REGN -> C718; BTST1 under C711 to a via and C719 on the bottom
    T([(12.53, 78.2), (13.6, 78.2)], 'PPHV', 'F', 0.4)
    T([(12.6, 79.45), (12.53, 78.6)], 'PPHV', 'F', 0.4)                       # VBUS in from a via above C711
    V(12.6, 79.45, 'PPHV', 0.4, 0.8)
    T([(13.1, 75.8), (13.7, 75.8)], 'PPHV', 'F', 0.4)
    T([(12.6, 75.3), (13.1, 75.8)], 'PPHV', 'F', 0.25)                        # VAC1/VAC2 only sense: small via
    V(12.6, 75.3, 'PPHV', 0.3, 0.6)
    T([(12.6, 75.3), (12.6, 79.45)], 'PPHV', 'In2', 0.25)                     # ... tied to VBUS on In2
    T([(13.6, 77.2), (12.95, 77.2), (12.5, 76.75)], 'CHG_REGN', 'F', 0.2)
    T([(13.6, 77.6), (11.2, 77.6)], 'CHG_BT1', 'F', 0.2)
    V(11.2, 77.6, 'CHG_BT1')
    T([(11.2, 77.6), (11.1, 78.0), (11.1, 79.0)], 'CHG_BT1', 'B', 0.2)
    # bottom row: CE (13) to GND pin 27 straight through between the SW pours; ACDRV2/ACDRV1 (10, 11) to a via
    T([(15.5, 78.95), (15.5, 76.1), (15.7, 75.9), (15.7, 75.3)], 'GND', 'F', 0.2)
    T([(14.5, 75.3), (14.5, 74.6), (14.9, 74.6), (14.9, 75.3)], 'GND', 'F', 0.2)
    T([(14.7, 74.6), (14.7, 74.0)], 'GND', 'F', 0.2)
    V(14.7, 74.0, 'GND')
    # PD controller: GND pins into the GND thermal pad (39), DRAIN pins into the DRAIN pad (40). Pins 31 and
    # 36 sit 0.175 mm from the big VBUS / PP5V pads, so their necks start at the pad end and are 0.15 mm.
    T([(11.15, 62.2), (11.7, 62.2), (11.9, 62.0)], 'GND', 'F', 0.15)                   # 31
    T([(11.15, 60.15), (11.8, 60.15)], 'GND', 'F', 0.15)                                # 36
    T([(10.875, 59.8), (11.8, 59.8)], 'GND', 'F', 0.2)                                  # 37
    for x in (12.6, 13.4, 13.8):                                                       # 3, 5, 6
        T([(x, 58.875), (x, 59.7)], 'GND', 'F', 0.2)
    T([(14.725, 59.4), (14.3, 59.4), (13.95, 59.65)], 'GND', 'F', 0.2)                 # 7
    for y in (61.0, 61.4):                                                             # 11, 12
        T([(14.725, y), (13.95, y)], 'GND', 'F', 0.2)
    T([(14.725, 62.2), (14.3, 62.2), (13.95, 62.0)], 'GND', 'F', 0.2)                  # 14
    T([(14.725, 62.6), (14.3, 62.6), (13.95, 62.8)], 'PD_DRAIN', 'F', 0.2)             # 15
    T([(10.875, 62.6), (11.3, 62.6), (11.65, 62.8)], 'PD_DRAIN', 'F', 0.2)             # 30
    T([(10.875, 64.2), (9.6, 64.2)], 'GND', 'F', 0.2)                                  # 26 -> C702 GND
    T([(10.875, 63.8), (10.45, 63.8), (10.45, 64.2)], 'GND', 'F', 0.2)                 # 27
    T([(14.725, 64.2), (15.4, 64.2), (15.7, 64.4)], 'GND', 'F', 0.2)                   # 19 -> via
    V(15.7, 64.4, 'GND')
    T([(10.875, 59.4), (10.0, 59.05)], '+3V3', 'F', 0.2)                               # 38 VIN_3V3 -> via -> C704
    V(10.0, 59.05, '+3V3')
    T([(10.0, 59.05), (10.0, 60.0)], '+3V3', 'B', 0.3)
    T([(11.8, 58.875), (11.8, 58.3), (12.2, 58.3), (12.2, 58.875)], 'PD_LDO3V3', 'F', 0.2)    # 1+2 -> C705
    T([(11.8, 58.3), (11.3, 57.5)], 'PD_LDO3V3', 'F', 0.25)
    T([(13.0, 58.875), (13.0, 57.6)], 'PD_LDO1V5', 'F', 0.2)                           # 4 -> C706
    T([(13.5, 65.15), (19.6, 65.15)], 'PPHV', 'F', 0.4)                                # PPHV pad -> C708, C709
    # charger: PMID left, GND up the middle, SYS right, SW1/SW2 into the vias under the IC
    zone('P:CHG_GND_F', 'GND', 'F', unary_union([box(14.9, 79.8, 16.1, 81.3),
                                                  box(14.7, 81.0, 17.3, 88.3)]), prio=12, grow=0.2)
    zone('P:PMID_F', 'CHG_PMID', 'F', unary_union([box(13.3, 79.8, 14.7, 80.7),
                                                    box(12.8, 80.2, 13.85, 87.4)]), prio=12, grow=0.2)
    zone('P:SYS_F', 'VSYS', 'F', unary_union([box(16.3, 79.8, 17.9, 80.8),
                                               box(17.6, 80.2, 19.3, 88.6), box(19.3, 80.0, 20.9, 81.9),
                                               box(17.6, 87.6, 21.7, 89.2)]), prio=12, grow=0.2)
    zone('P:SW1_F', 'CHG_SW1', 'F', box(14.4, 75.85, 15.15, 78.45), prio=12, grow=0.2)
    zone('P:SW2_F', 'CHG_SW2', 'F', box(15.85, 75.85, 16.6, 78.45), prio=12, grow=0.2)
    zone('P:BATL_F', 'BATP', 'F', unary_union([box(17.1, 77.9, 18.2, 78.55), box(18.0, 78.0, 21.6, 79.75)]),
         prio=12, grow=0.2)

    # ---------------------------------------------------------------- bottom power copper
    zone('P:VM_B', 'VM', 'B', box(30.7, 39.5, 77.3, 50.5))
    for ph in ESC:
        cx = COLS[ph]
        zone(f'P:PH{ph}_B', f'PH{ph}', 'B', box(cx - 5.8, 28.4, cx + 5.8, 38.7))
        zone(f'P:PH{ph}_LS_B', f'PH{ph}_LS', 'B', box(cx - 5.8, SH_Y + 2.3, cx + 5.8, 27.9))
    zone('P:GND_COLS_B', 'GND', 'B', box(30.5, 7.0, 78.5, SH_Y - 2.3))    # below Y 7 the bottom is a routing channel
    zone('P:GND_STRIP_B', 'GND', 'B', box(30.5, 51.4, 78.5, 58.0))
    zone('P:BATP_B', 'BATP', 'B', Polygon([(18.0, 73.6), (31.0, 73.6), (31.0, 76.2), (40.0, 76.2), (40.0, 89.7),
                                           (30.5, 89.7), (30.5, 79.9), (18.0, 79.9)]))
    zone('P:BATN_B', 'BATN', 'B', box(40.8, 76.4, 51.5, 89.7))
    zone('P:SW1_B', 'CHG_SW1', 'B', box(13.25, 75.8, 15.1, 78.2), prio=12, grow=0.2)
    zone('P:SW2_B', 'CHG_SW2', 'B', box(15.9, 75.8, 17.74, 78.2), prio=12, grow=0.2)


    # ---------------------------------------------------------------- servo buck copper
    for num in ('19', '20', '21', '22'):                                           # GND vias in the module's exposed pads
        x0, y0, x1, y1 = C.pad_box('U901', num).bounds
        for x in (x0 + 0.9, x1 - 0.9):
            C.via(x, (y0 + y1) / 2, 'GND', 0.3, 0.55, check=False)
    n_si = C.via_grid('GND', box(117.0, 23.5, 128.0, 24.5), 1.2, 0.4, 0.8)         # input caps' GND
    n_so = C.via_grid('GND', box(112.9, 3.3, 127.0, 4.9), 1.2, 0.4, 0.8)           # output caps' GND
    print('servo buck GND vias: input', n_si, 'output', n_so)
    for y in (18.3, 19.3):
        V(116.4, y, 'VM', 0.4, 0.8)                                                # VM feed arrives from the bottom
    C.track([(77.0, 46.6), (104.0, 46.6), (113.5, 37.1), (113.5, 20.0), (116.4, 18.8)], 2.0, 'B', 'VM')
    zone('P:VM_SRV_F', 'VM', 'F', box(115.8, 16.25, 128.0, 20.1), prio=12)
    zone('P:GND_SRVI_F', 'GND', 'F', box(117.0, 21.95, 128.0, 24.6), prio=12)
    zone('P:SRV_F', 'SERVO_V', 'F', unary_union([box(112.9, 8.0, 126.9, 12.2), box(126.9, 10.9, 133.8, 13.1),
                                                   box(130.2, 10.9, 133.8, 29.3), box(133.0, 15.5, 138.2, 17.5)]),
         prio=12, connect='full')
    zone('P:GND_SRVO_F', 'GND', 'F', box(112.9, 3.2, 127.0, 6.5), prio=12)

    # ---------------------------------------------------------------- inner layers
    # In1 and In4: solid GND (In4 sits right above the bottom-side power stage: the commutation loop
    # returns there). In2: GND under the power stage (more copper for the 70 A return), a VSYS corridor
    # from the charger to the stack header, and signals elsewhere. In3: signals. In2 and In3 are filled
    # with GND after routing.
    # 4.5 mm on 2 oz is plenty for the 5 A the charger can deliver; kept narrow so In2 stays free for the
    # charger and PD signals on its left and above it
    vsys = unary_union([box(17.5, 86.8, 24.5, 89.5), box(20.0, 59.5, 24.5, 89.5), box(20.0, 59.5, 67.8, 63.2)])
    zone('P:GND_In1', 'GND', 'In1', edge, prio=0, connect='tht', raw=True)
    zone('P:GND_In4', 'GND', 'In4', edge, prio=0, connect='tht', raw=True)
    zone('P:VSYS_In2', 'VSYS', 'In2', vsys, prio=2, raw=True)
    # In2 GND under the power stage from the shunt GND ends (Y 14) up past the ceramics. Below Y 13.5 In2
    # stays a signal layer so the gate driver's pins can escape to the MCU, and so does a 7 mm band east
    # of column B (X 58-82, Y 13.5-20.5), the way from the gate driver's corner to the MCU; the GND
    # fill after routing takes whatever the tracks leave of it.
    zone('P:GND_In2', 'GND', 'In2', box(28.0, 13.5, 82.0, 58.5).difference(box(58.0, 13.0, 82.5, 20.5)),
         prio=1, connect='tht', raw=True)

    # ---------------------------------------------------------------- autorouter keepouts
    # The autorouter treats every pour as a plane other nets may cross. Each pour on a routing layer
    # gets a keepout 0.6 mm inside its outline: foreign traces stay out of the copper, and a trace of
    # the pour's own net can still end in the 0.6 mm rim and join it.
    for z in list(C.zones):
        if z['name'].startswith('P:') and z['layer'] in ('F', 'B', 'In2', 'In3'):
            for i, rings in enumerate(z['rings']):
                g = Polygon(rings[0], rings[1:]).buffer(-0.6, 8)
                for j, piece in enumerate([g] if g.geom_type == 'Polygon' else list(getattr(g, 'geoms', []))):
                    if piece.area > 1.0:
                        # a signal via through a GND pour costs a small hole; through a power pour it can cut it
                        C.keepout(f"D:{z['name'][2:]}_{i}_{j}", [z['layer']], piece, tracks=True,
                                  vias=z['net'] != 'GND')

    # ---------------------------------------------------------------- fills after routing
    C.zone('F:GND_F', 'GND', 'F', edge, priority=1, connect='tht', dsn=False)
    C.zone('F:GND_B', 'GND', 'B', edge, priority=1, connect='tht', dsn=False)
    C.zone('F:GND_In2', 'GND', 'In2', edge, priority=0, connect='tht', dsn=False)
    C.zone('F:GND_In3', 'GND', 'In3', edge, priority=0, connect='tht', dsn=False)
    print('via arrays: VM', n_vm, 'GND cols', n_gc, 'GND strip', n_gs, 'CHG GND', n_ch)
