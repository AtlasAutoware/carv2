"""What the Atlas fork changes in Antmicro's Jetson Orin baseboard (github.com/antmicro/
jetson-orin-baseboard, commit 34f0e7f, Apache-2.0). fork.py applies this to the schematic and
tools/fork_pcb.py to the board.
"""
ANTMICRO_COMMIT = '34f0e7f'
ANTMICRO_PROJECT = 'jetson-orin-baseboard'
PROJECT = 'atlas_brain'

# Whole sheets the car has no use for: CSI camera FFCs, HDMI, the USB-C debug/DisplayPort port and
# the USB 3 USB-C port. The camera is GigE (PoE on the Antmicro RJ45), USB0 goes to the drive
# board's USB-C through the stack header, USB2 feeds the lidar Ethernet bridge.
REMOVE_SHEETS = ['CSI', 'HDMI', 'USB Debug, DP', 'USB3']

# Parts removed from the sheets that stay (the rest of each sheet is untouched).
REMOVE_REFS = {
    # Ethernet: the PoE powered-device front end (TPS2372 + 48 V to 12 V module). The board is
    # powered from the stack header now and the same RJ45 SOURCES PoE to the camera instead.
    'ethernet.kicad_sch': ['C52', 'C76', 'C79', 'C80', 'C81', 'C82', 'C84', 'C85', 'D12', 'D13', 'D14', 'D15', 'FB2',
                           'FB3', 'Q17', 'R123', 'R129', 'R142', 'R145', 'R146', 'R148', 'R149', 'R150', 'R153', 'R154',
                           'R155', 'R156', 'R157', 'R185', 'R196', 'R198', 'R199', 'R229', 'R241', 'R243', 'U22',
                           'U23', 'U39'],
    # Supply: the Nano-Fit DC input and its ideal diode, and the two 0R links from the USB-C PD
    # controller (on the removed debug sheet). The PoE-input ideal diode Q16/Q14 now carries the
    # stack header input.
    'supply.kicad_sch': ['D28', 'J12', 'Q13', 'Q15', 'R250', 'R252', 'R253', 'R254'],
    # Peripherals: the Samtec ERF8 expansion socket, the Tag-Connect for the PD controller's flash,
    # and the series parts / ESD / decoupling that only served them.
    'peripherals.kicad_sch': ['C105', 'C106', 'C107', 'C108', 'C109', 'C110', 'C111', 'C112', 'C113', 'C114', 'C115',
                              'D16', 'D17', 'D19', 'D21', 'D39', 'D40', 'D41', 'D42', 'D43', 'D44', 'D45', 'D46', 'D47',
                              'D48', 'D49', 'D50', 'D63', 'J9', 'J11', 'R26', 'R53', 'R54', 'R55', 'R62', 'R63', 'R64',
                              'R100', 'R101', 'R102', 'R112', 'R120', 'R121', 'R134', 'R141', 'R204', 'R233', 'R234',
                              'R235', 'R247', 'R248', 'R335', 'R336'],
    # SoM: 0R options that routed camera sync / GPIOs to the removed CSI and expansion connectors.
    'som.kicad_sch': ['R2', 'R3', 'R4', 'R5', 'R11', 'R12'],
    # M.2: wake-select option that only went to the expansion socket.
    'm-2.kicad_sch': ['R15'],
    # Root: the two rear/side SMT spacers. H6 would stand on a drive board bulk capacitor (brain (7.5, 52.5)
    # is drive (27.5, 52.5)); H5 is not a support point in the stack.
    'jetson-orin-baseboard.kicad_sch': ['H5', 'H6'],
}

# Fitted parts turned into do-not-populate: the corner spacers H3/H4 stay as plain holes. The brain board
# stands on 20 mm M3 standoffs from the drive board at all four corners (stack.py STACK_GAP).
DNP_REFS = {'jetson-orin-baseboard.kicad_sch': ['H3', 'H4']}

# Global labels renamed: the PCAL6408A expander (U34, SYS I2C) pins that drove the removed camera
# and USB-C power switches now carry the drive board signals.
RENAME_GLOBAL = {
    'peripherals.kicad_sch': {
        'CSIA_PEN': 'MCU_RST_REQ',          # P0 out: STM32 reset through an open-drain FET
        'CSIB_PEN': 'STK_MCU_BOOT0',        # P1 out
        'USBC1_PEN': 'STK_LIDAR_EN',        # P2 out
        'DISABLE_POE_DCDC': 'STK_ESTOP_OK', # P3 in
        'CSIA_FLG': 'STK_CHG_STAT',         # P4 in
        'CSIB_FLG': 'STK_SPARE1',           # P5
        'USBC1_FLG': 'STK_SPARE2',          # P6
        'USBC0_FLG': 'PSE_INT_N',           # P7 in: PoE controller interrupt
    },
    'ethernet.kicad_sch': {'DISABLE_POE_DCDC': None},   # label left dangling by the removed optocoupler: delete
}

# Local labels turned into global labels so the new sheets can reach them.
LOCAL_TO_GLOBAL = {
    'som.kicad_sch': {'SLEEP{slash}~{WAKE}': 'SLEEP_WAKE_N'},
    'ethernet.kicad_sch': {'PAIR_12': 'POE_PAIR_12', 'PAIR_36': 'POE_PAIR_36', 'PAIR_78': 'POE_PAIR_78',
                           'PAIR_910': 'POE_PAIR_910'},
}

# Net classes for the new nets (Antmicro's classes are kept as they are).
NETCLASS_PATTERNS = [
    ('Atlas_MDI', 'LAN_TR*'),
    ('85Ohm-diff_USB_2.0', 'USB2_D_*'),
    ('85Ohm-diff_USB_2.0', 'USB0_D_*'),
    ('PoE', 'POE_52V'),
    ('PoE', 'POE_PAIR_*'),
    ('PoE', 'PSE_D1'),
    ('PoE', 'BST_SW'),
    ('Atlas_Power', 'STK_VSYS'),
    ('Atlas_Power', 'POE_OUTPUT'),
    ('Atlas_Power', 'BST_RS'),
    ('Atlas_Power', 'PSE_RS1'),
]
# Atlas_Power: the heavy currents run in pours (layout.copper()); the class width only has to get into
# the power pins of the SON and VQFN parts (0.3 mm pads at 0.5 mm pitch), since the router cannot neck down.
NEW_CLASSES = [
    {'name': 'Atlas_Power', 'clearance': 0.2, 'track_width': 0.25, 'via_diameter': 0.6, 'via_drill': 0.3,
     'diff_pair_width': 0.2, 'diff_pair_gap': 0.25},
    {'name': 'Atlas_MDI', 'clearance': 0.2, 'track_width': 0.15, 'via_diameter': 0.45, 'via_drill': 0.2,
     'diff_pair_width': 0.2, 'diff_pair_gap': 0.25},
]
# Antmicro's DRC file asks 0.2 mm between tracks of different MDI pairs (rule mdi_clearance) while their
# MDI class says 0.125 mm, and the autorouter only reads the class. The lidar pairs get their own class
# at 0.2 mm (Antmicro's own camera pairs are routed and stay in theirs). Changes to Antmicro classes go in
# CLASS_PATCH.
CLASS_PATCH = {}
# 52 V PoE nets: 0.2 mm to everything, for the class and for Antmicro's PoE-to-Default DRC rule (0.5 mm
# in their file, written for the powered-device input). IPC-2221B asks 0.13 mm for 51-100 V under solder
# mask; TI's own TSSOP land pattern for the TPS23861 leaves 0.2 mm between its 57 V DRAIN pin and its
# neighbours, so anything larger makes the PSE's pins unroutable.
POE_CLEARANCE = 0.2

# Antmicro's 1345 vias are 0.45 mm pads with 0.1 mm drills, too small to drill through a 1.6 mm, 8-layer
# board at a standard fab (JLCPCB's floor is 0.15 mm, 0.2 mm is routine). The fork opens every via to
# 0.2 mm; the 0.45 mm pad still leaves a 0.125 mm ring and Antmicro's copper clearances are untouched.
VIA_DRILL = 0.2

# Parts whose own land pattern puts PoE / Atlas_Power pads closer than those classes' clearance (TI's
# TSSOP and SON pinouts, 0.14-0.25 mm pad gaps): DRC checks pad-to-pad inside them at 0.12 mm instead.
LAND_PATTERN_REFS = ['Q1001', 'Q1201', 'Q1202', 'U1101', 'U1201', 'U1202', 'U1301']

