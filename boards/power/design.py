"""ATLAS-PWR-1 rev B, the power board: pack input, main switch with precharge and E-stop gate, power
latch, servo/dev-kit/lidar/camera feeds, USB-C PD charging, one-cable debugging (USB hub + console),
the Raspberry Pi Pico supervisor and the cables to the Jetson dev kit and the Flipsky FSESC.

Single source of truth for the schematic and the PCB: python3 boards/tools/build_sch.py power.
Every IC, transistor, diode, electrolytic, connector and power part is through-hole or a module on 2.54 mm
headers or wire pads. Resistors and small ceramic capacitors are 1206 chips on the bottom side (hand-solder
pads, soldered with an iron): the 130 mm length limit leaves no room for them as through-hole parts (BRIEF rule 2
fallback, NOTES.md). The two 10 Ohm power resistors stay through-hole. Values carry a short reason.
Sourcing fields: MPN, Manufacturer, Price (USD, qty 1, 2026-10-24), Source (where the price was read),
Verified (yes = read on the cited page on 2026-10-24; est. = typical catalogue price, not checked;
no = part or price unconfirmed). README.md has the parts table and the cost per block.
The GPIO map is boards/power/PINMAP.md (single source of truth); the nets below follow it.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
sys.path.insert(0, HERE)
from eda import Design  # noqa: E402
from chips import conn  # noqa: E402
from chips_power import (MIC5014, HCT08, MCP2221A, MCP1700, R78E, TL431, PC817, IRFB7430, IRF9Z34N, IRF4905,  # noqa: E402
                         NPN, PNP, N7000, PICO, HUB5997, HUSB238, POLOLU2813, S18V20F12, CCCV, HEATSINK)

d = Design('atlas_power', 'ATLAS-PWR-1 power board', rev='B', date='2026-10-24')

# ----------------------------------------------------------------------------- footprints
R1206 = 'Resistor_SMD:R_1206_3216Metric_Pad1.30x1.75mm_HandSolder'     # 1/4 W thick film, bottom side
C1206 = 'Capacitor_SMD:C_1206_3216Metric_Pad1.33x1.80mm_HandSolder'    # X7R 50 V, bottom side
RH = 'Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal'    # 0.6 W metal film, lying
R5W = 'Resistor_THT:R_Axial_Power_L25.0mm_W9.0mm_P27.94mm'              # 5 W cement, lying (9.5 mm tall)
CP8 = 'Capacitor_THT:CP_Radial_D8.0mm_P3.50mm'
CP10 = 'Capacitor_THT:CP_Radial_D10.0mm_P5.00mm'
CP125 = 'Capacitor_THT:CP_Radial_D12.5mm_P5.00mm'
DO201V = 'Diode_THT:D_DO-201AD_P5.08mm_Vertical_KathodeUp'
DO15 = 'Diode_THT:D_DO-15_P3.81mm_Vertical_KathodeUp'                   # standing, about 11 mm tall
DO41 = 'Diode_THT:D_DO-41_SOD81_P3.81mm_Vertical_KathodeUp'
DO35 = 'Diode_THT:D_DO-35_SOD27_P2.54mm_Vertical_KathodeUp'
LED3 = 'LED_THT:LED_D3.0mm'
PTC = 'atlas:Fuse_Bourns_MF-R_P5.08mm'
W10 = 'atlas:WirePad_THT_10AWG_D3.5mm_OD7.5mm'
W16 = 'Connector_Wire:SolderWire-1.5sqmm_1x01_D1.7mm_OD3.9mm'
W18 = 'Connector_Wire:SolderWire-1sqmm_1x01_D1.4mm_OD3.9mm'
H1 = 'Connector_PinHeader_2.54mm:PinHeader_1x{:02d}_P2.54mm_Vertical'
TP_LOOP = 'TestPoint:TestPoint_Keystone_5000-5004_Miniature'
TP_PAD = 'TestPoint:TestPoint_THTPad_1.5x1.5mm_Drill0.7mm'
DK, MO, NW = 'https://www.digikey.com', 'https://www.mouser.com', 'https://www.newark.com'
FC = 'https://www.findchips.com/search/'


def src(price, url, verified):
    """sourcing fields: price in USD at qty 1 (Newark CA$ converted at 0.73), the page it was read on, verified"""
    return dict(Price=f'{price:.2f}', Source=url, Verified=verified)


R_SRC = src(0.10, FC + 'RC1206FR-0710KL', 'yes')    # Mouser $0.10 at qty 1 (any value of the series)
C100N = dict(mpn='Samsung CL31B104KBCNNNC (100 nF 50 V X7R 1206)', mfr='Samsung',
             **src(0.14, FC + 'CL31B104KBCNNNC', 'yes'))
C1U = dict(mpn='TDK C3216X7R1H105K160AB (1 uF 50 V X7R 1206)', mfr='TDK', **src(0.65, FC + 'C3216X7R1H105K160AB', 'yes'))


P_NPN = src(0.28, FC + '2N3904BU', 'yes')            # Mouser
P_PNP = src(0.26, FC + '2N3906', 'yes')              # Mouser 2N3906BU
P_TP = src(0.27, FC + '36-5000-ND', 'yes')           # Digi-Key Keystone 5000
P_LED_R = src(0.12, FC + 'LTL-4221N', 'yes')         # TME
P_LED_G = src(0.10, FC + 'LTL-4231N', 'yes')         # TME
P_H3 = src(0.13, FC + '61300311121', 'yes')          # Mouser, Wurth 1x3 2.54 mm
P_H4 = src(0.19, FC + '61300411121', 'yes')          # Mouser, Wurth 1x4 2.54 mm
P_4905 = src(2.71, FC + 'IRF4905PBF', 'yes')       # Mouser
P_TVS22 = src(0.45, FC + 'P6KE22A', 'yes')           # Newark (Taiwan Semiconductor) Can$0.619
C10N = dict(mpn='KEMET C1206C103K5RACTU (10 nF 50 V X7R 1206)', mfr='KEMET', **src(0.10, FC + 'C1206C103K5RACTU', 'yes'))
USBA = 'Connector_USB:USB_A_Wuerth_614004134726_Horizontal'   # WR-COM type A, upright (on its edge), THT
MINI = 'Fuse:Fuseholder_Blade_Mini_Keystone_3568'
P_MINI = src(1.48, FC + '3568', 'yes')               # Mouser: Keystone 3568 $1.15 + Littelfuse 0297005.WXNV $0.33


def yageo(value):
    """Yageo RC1206FR-07 part number for a resistor value: 10k -> RC1206FR-0710KL, 4.7k -> 4K7, 470 -> 470R"""
    v = value.replace('.0k', 'k')
    for suf, letter in (('k', 'K'), ('M', 'M')):
        if v.endswith(suf):
            num = v[:-1]
            return 'RC1206FR-07' + (num.replace('.', letter) if '.' in num else num + letter) + 'L'
    return 'RC1206FR-07' + (value.replace('.', 'R') if '.' in value else value + 'R') + 'L'


def R(ref, value, a, b, desc, fp=R1206, mpn=None, **kw):
    """1206 on the bottom unless a through-hole footprint is given"""
    f = dict(R_SRC)
    f.update(kw)
    smd = fp == R1206
    if smd:
        f.setdefault('mfr', 'Yageo')
    return d.R(ref, value, a, b, size=fp, mpn=mpn or (yageo(value) if smd else ''), desc=desc,
               side='B' if smd else 'F', **f)


def C(ref, value, a, b, desc, **kw):
    """1206 ceramic on the bottom"""
    return d.C(ref, value, a, b, size=C1206, desc=desc, side='B', **kw)


C1210 = 'Capacitor_SMD:C_1210_3225Metric_Pad1.33x2.70mm_HandSolder'
C10U = dict(mpn='Murata GRM32ER71H106KA12L (10 uF 50 V X7R 1210)', mfr='Murata',
            **src(0.86, FC + 'GRM32ER71H106KA12L', 'yes'))


def C10(a, b, desc):
    """10 uF 50 V X7R 1210 on the bottom (in place of small electrolytics; about 4 uF left at 17 V bias)"""
    return d.C('C', '10u 50V', a, b, size=C1210, desc=desc, side='B', **C10U)


def TPL(net):
    return d.stock('TP', 'Connector:TestPoint', net, TP_LOOP, {'1': net}, mpn='Keystone 5000 (red) / 5001 (black)',
                   mfr='Keystone', desc='test loop', **P_TP)


def TPP(net):
    return d.TP('TP', net, fp=TP_PAD)


# =============================================================================== A. pack input
d.block('A_PACK', 'Pack input: 10 AWG pads, bulk capacitance, TVS', [
    'Pack lead: 10 AWG pigtail soldered into J101/J102 with an XT90 male on its end. The pack carries the',
    'XT90-S female: the anti-spark resistor sits in the female half (probots and myfpvstore listings; one',
    'esk8.news teardown says male, so check with a meter: the half with a few ohms between two contacts of one',
    'pole goes on the pack). Also on the pack: 125 A MIDI fuse at B+, JBD BMS in B-. P- after the BMS is board GND.',
    'No XT90PW board-mount: its drawing could not be read and Amass rates it 30 A (UL) / 60 A for 1 min.',
    'Bulk at the pads (review P-M3): 3 x 680 uF 35 V low-ESR, 2 mF, so a main-switch trip or a BMS cut',
    'cannot ring the pack bus up. 1.5KE20A: 17.1 V standoff (above the 16.8 V CV setpoint), 27.7 V clamp.',
    'Top copper is BAT around the pads and FET drains; the bottom under it is GND (low-inductance loop).',
])
d.chip('J', conn('PAD_BAT+', 1, W10, desc='pack + lead, 10 AWG'), {'1': 'BAT'}, value='BAT+', in_bom='no')
d.chip('J', conn('PAD_BAT-', 1, W10, desc='pack - lead (P- after the BMS), 10 AWG'), {'1': 'GND'}, value='BAT-',
       in_bom='no')
for _ in range(3):
    d.CP('C', '680u 35V', 'BAT', 'GND', CP125, mpn='EEU-FR1V681', mfr='Panasonic',
         desc='pack bulk 680 uF 35 V low-ESR, 12.5 x 20 mm (21 mm tall)',
         **src(1.05, FC + 'EEU-FR1V681', 'yes'))
C('C', '1u 50V', 'BAT', 'GND', desc='HF decoupling at the pads', **C1U)
d.D('D', '1.5KE20A', 'GND', 'BAT', DO201V, kind='Z', mpn='1.5KE20A', mfr='Yageo / Littelfuse',
    desc='pack TVS 1500 W, VRWM 17.1 V, VBR 19.0-21.0 V, VC 27.7 V', **src(0.42, FC + '1.5KE20A', 'yes'))
TPL('BAT')
TPL('GND')

# =============================================================================== B. BMS link
d.block('B_BMS', 'BMS link: opto-isolated UART to the JBD smart BMS', [
    'JBD UART port (Overkill/JBD manual D.1.2): 1 VDD, 2 TX, 3 RX, 4 GND; on the BMS it is a 4-pin JST-PA 2.0.',
    'An off-board adapter lead maps it to J201 (JST-XH 4). The BMS side switches B-, so its GND must never',
    'meet board GND (esphome-jbd-bms warning; rev A review P-M1): two PC817s are the only link.',
    'BMS side powered from the port VDD (3.3-5 V expected; measure before plugging). 9600 baud.',
    'Pico TX low -> U202 LED on -> BMS RX low. BMS TX low -> U201 LED on -> Pico RX low (both non-inverting).',
    'Keep 2 mm between the BMS_* copper and everything else; no pour crosses the U201/U202 gap.',
])
d.chip('J', conn('BMS_UART', 4, 'Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical', mpn='B4B-XH-A(LF)(SN)',
                  mfr='JST', desc='to the JBD UART port through the adapter lead (BMS-side domain, isolated)',
                  names=['VDD', 'TX', 'RX', 'GND']),
       {'VDD': 'BMS_VDD', 'TX': 'BMS_TXD', 'RX': 'BMS_RXD', 'GND': 'BMS_GND'}, **src(0.11, FC + 'B4B-XH-A', 'yes'))
d.chip('U', PC817, {'A': 'BMS_OPT1_A', 'K': 'BMS_TXD', 'C': 'BMS_RX', 'E': 'GND'},
       desc='BMS TX -> Pico GP1 (UART0 RX)', **src(0.42, FC + 'PC817X2NSZ9F', 'yes'))
R('R', '1k', 'BMS_VDD', 'BMS_OPT1_A', 'U201 LED: 1.9 mA at 3.3 V, 3.5 mA at 5 V (BMS TX sinks it)')
R('R', '4.7k', '+3V3', 'BMS_RX', 'Pico RX pull-up; idle high')
d.chip('U', PC817, {'A': 'BMS_OPT2_A', 'K': 'BMS_TX', 'C': 'BMS_RXD', 'E': 'BMS_GND'},
       desc='Pico GP0 (UART0 TX) -> BMS RX', **src(0.42, FC + 'PC817X2NSZ9F', 'yes'))
R('R', '470', '+3V3', 'BMS_OPT2_A', 'U202 LED: 4 mA from the Pico pin (sinks); CTR >= 50 % gives >= 2 mA')
R('R', '4.7k', 'BMS_VDD', 'BMS_RXD', 'BMS RX pull-up to the port VDD; idle high; 0.7-1.1 mA when low')
C('C', '100n', 'BMS_VDD', 'BMS_GND', desc='BMS-side decoupling (stays in the BMS domain)', **C100N)

# =============================================================================== C. main switch
d.block('C_SWITCH', 'Main switch: 3 x IRFB7430 high side, MIC5014, precharge, E-stop AND', [
    'MIC5014 (DS20006767A): V+ 2.75-30 V (60 V abs, gate off above 35 V), IN TTL 0.8/2.0 V, ~1 uA, gate clamped',
    '13-17 V above SOURCE. V+ straight from BAT (SOURCE = VM must not exceed V+), 10 uF + 100 nF at pins 1/4.',
    'Turn-on: 1 nF in 90 us at 12 V; 3 x 300 nC -> about 5 ms (VM already precharged). Turn-off: 1 nF in 6 us;',
    'estimate 0.1-0.4 ms for 0.9-1.2 uC incl. Miller: about 0.04 J per FET at 90 A, inside the SOA. BENCH CHECK.',
    '10 Ohm per gate (sharing, damping), 2.2M G-S keeps the FETs off with the MIC5014 out of its socket (100k',
    'loaded its charge pump, review m1).',
    'Precharge: IRF9Z34N + MF-R050 + 10 Ohm 5 W into VM; tau 20 ms for 2 mF, 0.28 J per start. The MF-R050',
    'trips (1 A, seconds) if precharge is left on into a shorted bus (28 W in the resistor otherwise).',
    'Review M3: the FSESC and the Castle BEC load VM during precharge (110 mA is the limit at 12 V). If the bench',
    'test fails: move the BEC lead to J410 (VSYS_SW) and/or fit 4.7 Ohm 5 W (Yageo SQP500JB-4R7, same body) as',
    'R313; at 4.7 Ohm the peak is 3.6 A for about 10 ms (check that the MF-R050 does not trip).',
    'E-stop in hardware: 74HCT08 at 5 V: MIC_IN = MAIN_EN AND ESTOP_OK; precharge = PRECHARGE_EN AND ESTOP_OK.',
    'Pico enables have 100k pull-downs, so a Pico reset opens the switch. VM TVS 1.5KE22A (18.8 V standoff).',
])
for i in range(1, 4):
    d.chip('Q', IRFB7430, {'G': f'SW_G{i}', 'D': 'BAT', 'S': 'VM'}, desc='main switch FET (tab = BAT+)',
           **src(3.69, FC + 'IRFB7430PBF', 'yes'))
for i in range(1, 4):
    R('R', '10', 'SW_GATE', f'SW_G{i}', 'gate resistor per FET: current sharing, damps the 3-FET gate loop')
R('R', '2.2M', 'SW_GATE', 'VM', 'gate-source pull-down: FETs off with the MIC5014 removed; light load on its pump')
d.chip('U', MIC5014, {'V+': 'BAT', 'IN': 'MIC_IN', 'GND': 'GND', 'GATE': 'SW_GATE', 'SOURCE': 'VM', 'NC': None},
       desc='high-side driver (socketed)', **src(3.54, FC + 'MIC5014YN', 'yes'))
C10('BAT', 'GND', 'MIC5014 V+ bypass 10 uF (datasheet), under the socket')
C('C', '100n', 'BAT', 'GND', desc='MIC5014 V+ HF bypass, at pins 1/4', **C100N)
R('R', '1k', 'AND_MAIN', 'MIC_IN', 'from the 74HCT08 (5 V) to IN')
R('R', '100k', 'MIC_IN', 'GND', 'IN low while the 5 V rail is off (car off)')
d.chip('U', HCT08, {'VCC': '+5V', 'GND': 'GND', '1A': 'MAIN_EN', '1B': 'ESTOP_OK', '1Y': 'AND_MAIN',
                    '2A': 'PRECHARGE_EN', '2B': 'ESTOP_OK', '2Y': 'AND_PRE', '3A': 'SERVO_IN', '3B': '+5V',
                    '3Y': 'SERVO_BUF', '4A': 'GND', '4B': 'GND', '4Y': None},
       desc='E-stop AND gates and the servo-signal buffer (socketed)', **src(0.92, FC + 'SN74HCT08N', 'yes'))
C('C', '100n', '+5V', 'GND', desc='74HCT08 decoupling', **C100N)
R('R', '100k', 'MAIN_EN', 'GND', 'MAIN_EN low while the Pico is in reset')
R('R', '100k', 'PRECHARGE_EN', 'GND', 'PRECHARGE_EN low while the Pico is in reset')
d.chip('Q', IRF9Z34N, {'G': 'PRE_G', 'S': 'BAT', 'D': 'PRE_D'}, desc='precharge P-FET (tab = PRE_D, not on the heatsink)',
       **src(1.08, FC + 'IRF9Z34NPBF', 'yes'))
R('R', '10k', 'BAT', 'PRE_G', 'G-S pull-up: off by default')
R('R', '10k', 'PRE_G', 'PRE_C', 'gate divider: VGS -8.4 V at 16.8 V, -15 V on a 30 V spike (+-20 V rating)')
d.chip('Q', NPN, {'B': 'PRE_B', 'C': 'PRE_C', 'E': 'GND'}, desc='precharge level shifter', **P_NPN)
R('R', '4.7k', 'AND_PRE', 'PRE_B', 'base drive 0.9 mA from 5 V')
R('R', '100k', 'PRE_B', 'GND', 'base pull-down')
d.stock('F', 'Device:Polyfuse', 'MF-R050', PTC, {'1': 'PRE_D', '2': 'PRE_F'}, mpn='MF-R050', mfr='Bourns',
        desc='0.5 A hold / 1 A trip, 60 V: backstop if precharge stays on into a short', **src(0.47, FC + 'MF-R050', 'yes'))
d.R('R', '10 5W', 'PRE_F', 'VM', size=R5W, mpn='SQP500JB-10R', mfr='Yageo',
    desc='precharge resistor 10 Ohm 5 W cement, 22 x 9.5 x 9 mm, lying flat; 1.7 A peak, 0.28 J per start',
    **src(0.52, FC + 'SQP500JB-10R', 'yes'))
d.D('D', '1.5KE22A', 'GND', 'VM', DO201V, kind='Z', mpn='1.5KE22A', mfr='Diotec',
    desc='motor bus TVS 1500 W, VRWM 18.8 V: regen with the BMS open', **src(0.29, FC + '1.5KE22A', 'yes'))
d.stock('TH', 'Device:Thermistor_NTC', '10k B3977', 'Capacitor_THT:C_Disc_D3.0mm_W2.0mm_P2.50mm',
        {'1': 'NTC_NODE', '2': 'GND'}, mpn='NTCLE100E3103JB0', mfr='Vishay',
        desc='FET temperature: bent against the heatsink bar with Kapton between (the bar is BAT+)',
        **src(0.53, FC + 'NTCLE100E3103JB0', 'yes'))
R('R', '10k', '+3V3', 'NTC_NODE', 'NTC divider top: 1.65 V at 25 C, 0.3 V at 90 C')
C('C', '100n', 'FET_NTC', 'GND', desc='NTC filter at the Pico pin', **C100N)
d.chip('HS', HEATSINK, {}, **src(1.50, 'https://sendcutsend.com', 'no'))
R('R', '4.7k', 'VM', 'VM_LED_A', 'VM-live LED: 3 mA at 16.8 V, 60 mW (1206 is 1/4 W)')
R('R', '10k', 'NTC_NODE', 'FET_NTC', 'series into GP28: limits the current if the NTC chafes through to the BAT+ bar')
d.stock('D', 'Device:LED', 'RED', LED3, {'1': 'GND', '2': 'VM_LED_A'}, mpn='Lite-On LTL-4221N (3 mm red)',
        mfr='Lite-On', desc='VM live (motor bus energised)', **P_LED_R)
TPL('VM')
TPP('SW_GATE')

# =============================================================================== D. latch and rails
d.block('D_RAILS', 'Latch and rails: Pololu #2813, R-78E 5 V, Castle BEC, dev-kit feed, lidar, camera 12 V', [
    'Button (on board or remote) pulls the Pololu ON input high through 33k from BAT (2.0 V at 12 V, 3.9 V max)',
    'and, through Q401, pulls BUTTON_N low for the Pico. The Pico ends power with a LATCH_OFF pulse.',
    'R-78E5.0-1.0 (8-28 V in) behind 4.7 Ohm + P6KE20A, so a 30 V spike on VSYS_SW reaches it as <= 22 V.',
    'Pico VSYS through a 1N5817 (Pico datasheet 4.5): the Pico USB cable cannot back-feed the 5 V rail.',
    'Dev kit: 5 A mini blade fuse -> P6KE22A -> over-voltage cut-off (IRF4905, TL431 trips at 18.7 V, releases 17.85 V)',
    '-> 18 AWG pads; the carrier is rated 9-20 V. The cut-off guards the dev kit against regen with the BMS open;',
    'the same P-FET lets the Pico power-cycle a hung Jetson (GP22 DEVKIT_PWR low = off).',
    'Lidar: IRF9Z34N high side, 10k/10k gate divider, 100 nF soft start, MF-R075, P6KE22A, Phoenix 2-pin.',
    'Camera: MF-R075 -> P6KE22A -> wire pads -> Pololu S18V20F12 (off board) -> camera lead.',
    'Servo: Castle BEC 2.0 from VM (J401), or from VSYS_SW (J410) if its start-up load stops the precharge (M3).',
])
d.chip('MOD', POLOLU2813, {'VIN': 'BAT', 'GND': 'GND', 'VOUT': 'VSYS_SW', 'ON': 'LATCH_ON', 'OFF': 'LATCH_OFF_M'},
       desc='push-on latch, mounted on the tray, wired: 18 AWG VIN/VOUT/GND, 24 AWG ON/OFF',
       **src(8.95, 'https://www.pololu.com/product/2813', 'yes'))
d.stock('SW', 'Switch:SW_Push', 'POWER', 'Button_Switch_THT:SW_Tactile_SPST_Angled_PTS645Vx58-2LFS',
        {'1': 'BTN_HI', '2': 'LATCH_ON'}, mpn='PTS645VL58-2 LFS', mfr='C&K',
        desc='power button, 6 mm right-angle tactile at the Y=0 edge, pressed through the pod window',
        **src(0.30, FC + 'PTS645VL582LFS', 'yes'))
R('R', '33k', 'BAT', 'BTN_HI', 'button source: 0.4 mA when pressed; a shorted remote lead draws 0.5 mA')
R('R', '10k', 'LATCH_ON', 'GND', 'ON low when released; with the ON input (about 20k) gives 2.0-3.9 V pressed')
C('C', '100n', 'LATCH_ON', 'GND', desc='debounce and ESD on the remote button line', **C100N)
d.chip('Q', NPN, {'B': 'BTN_B', 'C': 'BUTTON_N', 'E': 'GND'}, desc='button sense for the Pico (open collector)',
       **P_NPN)
R('R', '22k', 'LATCH_ON', 'BTN_B', 'base drive 60 uA at 2.0 V')
R('R', '100k', 'BTN_B', 'GND', 'base pull-down')
R('R', '10k', '+3V3', 'BUTTON_N', 'BUTTON_N pull-up (active low)')
R('R', '1k', 'LATCH_OFF', 'LATCH_OFF_M', 'GP9 to the Pololu OFF input (> 1 V pulse)')
R('R', '100k', 'LATCH_OFF_M', 'GND', 'OFF stays low while the Pico is off or in reset')
# 5 V
R('R', '4.7', 'VSYS_SW', 'V5_IN', 'R-78E input filter: 0.5 V drop at 0.1 A (review m9: keeps a sagging pack above the '
  'R-78E 8 V minimum); with D401 limits a 30 V spike (about 2 A into D401)', fp=RH,
  mpn='Vishay MBB02070C4708FCT00 (0.6 W metal film)', mfr='Vishay', **src(0.26, FC + 'MBB02070C4708FCT00', 'yes'))
d.D('D', 'P6KE20A', 'GND', 'V5_IN', DO15, kind='Z', mpn='P6KE20A', mfr='Littelfuse',
    desc='clamp for the R-78E input (28 V max): conducts above 19 V', **src(0.54, FC + 'P6KE20A', 'yes'))
C10('V5_IN', 'GND', 'R-78E input')
d.chip('U', R78E, {'VIN': 'V5_IN', 'VOUT': '+5V', 'GND': 'GND'}, desc='5 V rail: Pico, hub-free logic, fan, 74HCT08',
       **src(4.47, FC + 'R-78E5.0-1.0', 'yes'))
C10('+5V', 'GND', 'R-78E output')
d.D('D', '1N5817', '+5V', 'PICO_VSYS', DO41, kind='S', mpn='1N5817RLG', mfr='onsemi',
    desc='5 V to the Pico VSYS (OR-ing with its own VBUS diode)', **src(0.67, FC + '1N5817RLG', 'yes'))
R('R', '2.2k', '+5V', 'LED5_A', '5 V LED, 1.3 mA')
d.stock('D', 'Device:LED', 'GREEN', LED3, {'1': 'GND', '2': 'LED5_A'}, mpn='Lite-On LTL-4231N (3 mm green)',
        mfr='Lite-On', desc='5 V on', **P_LED_G)
# servo: Castle BEC 2.0 on VM, output plugs into J406, servo into J408
d.chip('J', conn('PAD_BEC_IN+', 1, W16, desc='Castle BEC input + (16 AWG red lead), default: on VM'), {'1': 'VM'},
       value='BEC+', in_bom='no')
d.chip('J', conn('PAD_BEC_IN-', 1, W16, desc='Castle BEC input - (16 AWG black lead)'), {'1': 'GND'}, value='BEC-',
       in_bom='no')
d.chip('J', conn('BEC_OUT', 3, H1.format(3), desc='Castle BEC output plug (servo style); signal pin unused',
                  names=['NC', 'V+', 'GND']), {'NC': None, 'V+': 'SERVO_V', 'GND': 'GND'},
       mpn='Wurth 61300311121', mfr='Wurth', **P_H3)
d.chip('J', conn('PAD_SERVO_V', 1, W16, desc='alternative: BEC output + soldered'), {'1': 'SERVO_V'}, value='SRV+',
       in_bom='no')
d.chip('J', conn('PAD_SERVO_GND', 1, W16, desc='alternative: BEC output - soldered'), {'1': 'GND'}, value='SRV-',
       in_bom='no')
d.CP('C', '1000u 16V', 'SERVO_V', 'GND', CP10, mpn='EEU-FR1C102', mfr='Panasonic',
     desc='servo rail bulk 1000 uF 16 V low-ESR, 10 x 16 mm, at the servo header (stall pulses)',
     **src(0.80, FC + 'EEU-FR1C102', 'yes'))
d.chip('J', conn('SERVO', 3, H1.format(3), desc='steering servo S / + / - (front edge)', names=['SIG', 'V+', 'GND']),
       {'SIG': 'SERVO_SIG', 'V+': 'SERVO_V', 'GND': 'GND'}, mpn='Wurth 61300311121', mfr='Wurth', **P_H3)
R('R', '220', 'SERVO_BUF', 'SERVO_SIG', 'servo signal series (5 V from the 74HCT08 buffer)')
# dev kit DC feed with over-voltage cut-off
d.stock('F', 'Device:Fuse', '5A mini', MINI, {'1': 'VSYS_SW', '2': 'VDEV_F'}, mpn='Keystone 3568 + Littelfuse 0297005.WXNV',
        mfr='Keystone / Littelfuse', desc='dev-kit feed fuse: mini blade (ATM) holder with a 5 A fuse', **P_MINI)
d.D('D', 'P6KE22A', 'GND', 'VDEV_F', DO15, kind='Z', mpn='P6KE22A', mfr='Taiwan Semiconductor',
    desc='dev-kit feed TVS 600 W, VRWM 18.8 V (above the pack TVS band, review m4)', **P_TVS22)
d.chip('Q', IRF4905, {'G': 'OV_G', 'S': 'VDEV_F', 'D': 'VDEV'}, desc='dev-kit over-voltage cut-off (review M2)',
       **P_4905)
R('R', '10k', 'VDEV_F', 'OV_G', 'G-S pull-up')
R('R', '6.8k', 'OV_G', 'OV_C', 'gate divider: VGS -7.1 V at 12 V, -10 V at 16.8 V, -17.9 V at 30 V')
d.chip('Q', NPN, {'B': 'DEV_B', 'C': 'OV_C', 'E': 'GND'}, desc='dev-kit power enable (on unless GP22 is driven low)',
       **P_NPN)
R('R', '4.7k', 'DEVKIT_PWR', 'DEV_B', 'base drive from GP22')
R('R', '100k', 'DEV_B', 'GND', 'base pull-down')
R('R', '10k', '+3V3', 'DEVKIT_PWR', 'pull-up: about 2.7 V against the Pico reset pull-down, so the dev kit stays on')
d.chip('U', TL431, {'REF': 'OV_REF', 'K': 'OV_K', 'A': 'GND'}, desc='over-voltage comparator for the dev-kit feed',
       **src(0.14, FC + 'TL431ACLPR', 'yes'))
R('R', '100k', 'VDEV_F', 'OV_REF', 'OV divider top (1 %)')
R('R', '15.0k', 'OV_REF', 'GND', 'OV divider bottom: trips at about 18.7 V (2.495 V REF)')
R('R', '1.2M', 'OV_G', 'OV_REF', 'hysteresis: releases at about 17.85 V (above the 16.8 V charge voltage)')
d.chip('Q', PNP, {'B': 'OV_B', 'E': 'VDEV_F', 'C': 'OV_G'}, desc='pulls the gate to the source on over-voltage',
       **P_PNP)
R('R', '10k', 'VDEV_F', 'OV_B', 'PNP B-E pull-up')
R('R', '4.7k', 'OV_B', 'OV_K', 'TL431 cathode current 3.4 mA at 18.7 V, 5.9 mA at 30 V (>= 1 mA needed)')
d.CP('C', '220u 35V', 'VDEV', 'GND', CP8, mpn='Panasonic EEU-FR1V221', mfr='Panasonic',
     desc='dev-kit lead bulk at the pads', **src(0.73, FC + 'EEU-FR1V221', 'yes'))
d.chip('J', conn('PAD_DEVKIT+', 1, W18, desc='dev-kit DC lead + (18 AWG, 5.5 x 2.5 mm plug)'), {'1': 'VDEV'},
       value='DEV+', in_bom='no')
d.chip('J', conn('PAD_DEVKIT-', 1, W18, desc='dev-kit DC lead -'), {'1': 'GND'}, value='DEV-', in_bom='no')
# lidar switch
d.chip('Q', IRF9Z34N, {'G': 'LID_G', 'S': 'VSYS_SW', 'D': 'LID_SW'}, desc='lidar high-side switch',
       **src(1.08, FC + 'IRF9Z34NPBF', 'yes'))
R('R', '10k', 'VSYS_SW', 'LID_G', 'G-S pull-up: lidar off by default')
C('C', '100n', 'VSYS_SW', 'LID_G', desc='gate capacitor: about 0.5 ms soft start', **C100N)
C('C', '100n', 'VDEV_F', 'OV_G', desc='gate-source capacitor: soft start into the dev kit (review m5)', **C100N)
R('R', '10k', 'LID_G', 'LID_C', 'gate divider: VGS -8.4 V at 16.8 V, -15 V at 30 V')
d.chip('Q', NPN, {'B': 'LID_B', 'C': 'LID_C', 'E': 'GND'}, desc='lidar enable', **P_NPN)
R('R', '4.7k', 'LIDAR_EN', 'LID_B', 'base drive from GP6')
R('R', '100k', 'LID_B', 'GND', 'base pull-down: lidar off while the Pico is dead (fixes rev A P-m1 by construction)')
d.stock('F', 'Device:Polyfuse', 'MF-R075', PTC, {'1': 'LID_SW', '2': 'LIDAR_V'}, mpn='MF-R075', mfr='Bourns',
        desc='lidar polyfuse 0.75 A hold, 60 V (TiM561 about 0.33 A)', **src(0.25, FC + 'MF-R075', 'yes'))
d.D('D', 'P6KE22A', 'GND', 'LIDAR_V', DO15, kind='Z', mpn='P6KE22A', mfr='Taiwan Semiconductor',
    desc='lidar output TVS (P6KE22A: above the pack TVS band, review m4)', **P_TVS22)
d.chip('J', conn('LIDAR_PWR', 2, 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_PT-1,5-2-3.5-H_1x02_P3.50mm_Horizontal',
                  mpn='1984617', mfr='Phoenix Contact', desc='lidar power (donor M12 cable)', names=['+', '-']),
       {'+': 'LIDAR_V', '-': 'GND'}, **src(0.59, FC + '1984617', 'yes'))
d.chip('J', conn('PAD_BEC_IN+ALT', 1, W16, desc='alternative BEC input + on VSYS_SW (review M3): solder the red lead '
                  'here instead of BEC+ only if the BEC start-up stops the precharge; then the latch carries the servo'),
       {'1': 'VSYS_SW'}, value='BEC+ALT', in_bom='no')
# camera 12 V
d.stock('F', 'Device:Polyfuse', 'MF-R075', PTC, {'1': 'VSYS_SW', '2': 'CAM_VIN'}, mpn='MF-R075', mfr='Bourns',
        desc='camera feed polyfuse (1 A class; the camera takes about 0.25 A at the regulator input)',
        **src(0.25, FC + 'MF-R075', 'yes'))
d.D('D', 'P6KE22A', 'GND', 'CAM_VIN', DO15, kind='Z', mpn='P6KE22A', mfr='Taiwan Semiconductor',
    desc='camera regulator input TVS (S18V20F12 32 V absolute; review m18), fitted', **P_TVS22)
d.chip('MOD', S18V20F12, {'VIN': 'CAM_VIN', 'GND': 'GND'},
       desc='camera 12 V regulator, off board on the tray: input wired here (22 AWG), 12 V output straight to the '
            'Triton VAUX lead (M8 pin 1 red +12 V, pin 5 black GND)',
       **src(29.95, 'https://www.pololu.com/product/2577', 'yes'))
TPL('VSYS_SW')
TPL('+5V')
TPL('SERVO_V')

# =============================================================================== E. charging
d.block('E_CHARGE', 'USB-C charging: PD trigger 20 V, CC/CV buck 16.8 V / 2.5 A, reverse block, fuse', [
    'Adafruit 5807 (HUSB238) and the CC/CV buck (XL4015 class) sit off the board in the side pod at the charge',
    'window (130 mm board limit), wired to pads. On the 5807 cut the 5V jumper (all open = 20 V) and the 1A',
    'jumper (both current jumpers open = 3 A).',
    'Charge ground (review B1): the common XL4015 CC/CV module measures current with a shunt between IN- and',
    'OUT-. So the charger side has its own net CHG_GND (PD trigger GND, CC/CV IN-, D501, C501, the charger-present',
    'detector) and CC/CV OUT- is its only tie to GND: the charge current returns through the shunt and CC works. A',
    'module with high-side sensing (IN- and OUT- joined inside) works on the same pads. Bench check in README.',
    'Reverse block: Q501 IRF4905 with its body diode toward the pack, turned fully on only while CHG_IN > ~17.5 V',
    '(1N5247B 17 V zener + Q502), so a 5/9/12/15 V PD fallback never enables it. No diode drop at the end of',
    'charge, so the buck CV is set to 16.80 V (4.20 V/cell), not 17.1 V (PHASE2 assumed a diode).',
    'Q503 gives the Pico CHG_PRESENT_N (open collector, no back-power into an unpowered Pico).',
    '5 A mini blade fuse into BAT. The pack-side current goes through the XT90 and the BMS common port.',
])
d.chip('MOD', HUSB238, {'VOUT': 'CHG_IN', 'GND': 'CHG_GND'},
       desc='USB-C PD trigger set to 20 V (jumpers), off board in the pod; its terminal holes wired here (20 AWG)',
       **src(5.95, 'https://www.adafruit.com/product/5807', 'yes'))
d.D('D', 'P6KE24A', 'CHG_GND', 'CHG_IN', DO15, kind='Z', mpn='P6KE24A', mfr='Littelfuse',
    desc='charge input TVS, VRWM 20.5 V (PD 20 V + 5 %)', **src(0.54, FC + 'P6KE24A', 'yes'))
C10('CHG_IN', 'CHG_GND', 'charge input, <= 10 uF so PD attach inrush stays small')
d.chip('MOD', CCCV, {'IN+': 'CHG_IN', 'IN-': 'CHG_GND', 'OUT+': 'CHG_OUT', 'OUT-': 'GND'},
       desc='CC/CV buck, set 16.80 V / 2.5 A with a meter before wiring OUT+ (README)', **src(8.00, '-', 'no'))
d.chip('Q', IRF4905, {'G': 'CHG_G', 'S': 'CHG_RB', 'D': 'CHG_OUT'},
       desc='reverse block: body diode CHG_OUT -> pack; channel on only with 20 V present (review M2)', **P_4905)
R('R', '10k', 'CHG_RB', 'CHG_G', 'G-S pull-up: off (body diode only) without a charger')
C('C', '100n', 'CHG_RB', 'CHG_G', desc='gate-source capacitor: about 0.4 ms soft start (review m5)', **C100N)
R('R', '6.8k', 'CHG_G', 'CHG_C', 'gate divider: VGS -10 V at 16.8 V, -7.1 V at 12 V')
d.chip('Q', NPN, {'B': 'CHG_B1', 'C': 'CHG_C', 'E': 'CHG_GND'}, desc='reverse-block enable', **P_NPN)
d.D('D', '1N5247B', 'CHG_Z', 'CHG_IN', DO35, kind='Z', mpn='1N5247BTR', mfr='onsemi',
    desc='17 V zener: 20 V present detector (on above 16.8-18.5 V)', **src(0.17, FC + '1N5247BTR', 'yes'))
R('R', '47k', 'CHG_Z', 'CHG_B1', 'base drive')
R('R', '47k', 'CHG_B1', 'CHG_GND', 'base pull-down')
d.chip('Q', NPN, {'B': 'CHG_B2', 'C': 'CHG_PRESENT_N', 'E': 'CHG_GND'}, desc='charger present to the Pico (GP15)',
       **P_NPN)
R('R', '47k', 'CHG_Z', 'CHG_B2', 'base drive')
R('R', '47k', 'CHG_B2', 'CHG_GND', 'base pull-down')
R('R', '10k', '+3V3', 'CHG_PRESENT_N', 'pull-up: high = no charger')
d.stock('F', 'Device:Fuse', '5A mini', MINI, {'1': 'CHG_RB', '2': 'BAT'}, mpn='Keystone 3568 + Littelfuse 0297005.WXNV',
        mfr='Keystone / Littelfuse', desc='charge path fuse: mini blade (ATM) holder with a 5 A fuse', **P_MINI)
TPP('CHG_IN')
TPP('CHG_GND')

# =============================================================================== F. debug hub
d.block('F_DEBUG', 'One-cable debugging: laptop USB-C -> CH334F hub -> dev kit, FSESC, MCP2221A console', [
    'Adafruit 5997 CH334F 4-port hub on 8.5 mm sockets at the Y=0 edge; its own USB-C (upstream) faces the pod',
    'window and is the laptop port. High speed, bus powered from the laptop. Its VBUS goes to every port',
    'and to nothing else: HUB_VBUS never meets +5V, so the car cannot back-power the laptop and the laptop',
    'cannot power the car. GND is common. Port 1 -> J601 USB-A receptacle -> one USB-A to C cable -> dev-kit',
    'USB-C (192.168.55.1; for flashing NVIDIA documents a direct cable: laptop straight into the dev kit is the',
    'fallback). Port 3 -> J602 -> 4449 -> the FSESC micro-USB cable, its ground through 3.3 Ohm (M6).',
    'Port 2 -> MCP2221A (PDIP-14, under the hub) at 3.3 V from an MCP1700 on HUB_VBUS -> 10k -> J14 3/4.',
    'Port 4 -> J603 spare (e.g. move the Pico USB here). The upstream header pads (D+/D-) are left open.',
    'Route each D+/D- pair as a coupled pair over unbroken GND, short (USB 2.0 HS; 90 Ohm is not reachable on',
    '1.6 mm 2-layer, keep runs under 40 mm).',
])
_hub = {'UP_VBUS': 'HUB_VBUS', 'UP_D+': None, 'UP_D-': None, 'UP_GND': 'GND'}
for _p in range(1, 5):
    _hub.update({f'P{_p}_VBUS': 'HUB_VBUS', f'P{_p}_D+': f'P{_p}_DP', f'P{_p}_D-': f'P{_p}_DM', f'P{_p}_GND': 'GND'})
d.chip('MOD', HUB5997, _hub,
       desc='USB hub module on 2 x Sullins PPTC081LFBN-RC + 1 x PPTC041LFBN-RC female sockets (8.5 mm), so the '
            'MCP2221A fits under it; its own USB-C is the laptop port. $4.95 module (adafruit.com) + $3.30 sockets '
            '(findchips, broker price)', **src(8.25, 'https://www.adafruit.com/product/5997', 'yes'))
d.chip('J', conn('DEVKIT_USB', 5, USBA, desc='hub port 1: USB-A receptacle for one USB-A to USB-C cable to the dev '
                  "kit's device port (review M7)", names=['VBUS', 'D-', 'D+', 'GND', 'SHIELD']),
       {'VBUS': 'HUB_VBUS', 'D-': 'P1_DM', 'D+': 'P1_DP', 'GND': 'GND', 'SHIELD': 'GND'}, mpn='Wurth 614004134726',
       mfr='Wurth', **src(3.87, FC + '614004134726', 'yes'))
d.chip('J', conn('VESC_USB', 4, H1.format(4), desc='hub port 3 to the FSESC micro-USB (VESC Tool, full speed); '
                  'Adafruit 4449 lead: red, white, green, black. Its GND goes through 3.3 Ohm (review M6)',
                  names=['VBUS', 'D-', 'D+', 'GND']),
       {'VBUS': 'HUB_VBUS', 'D-': 'P3_DM', 'D+': 'P3_DP', 'GND': 'VUSB_GND'}, mpn='Wurth 61300411121', mfr='Wurth', **P_H4)
d.chip('J', conn('HUB_PORT4', 4, H1.format(4), desc='hub port 4, spare (e.g. the Pico USB for flashing); Adafruit 4449 lead',
                  names=['VBUS', 'D-', 'D+', 'GND']),
       {'VBUS': 'HUB_VBUS', 'D-': 'P4_DM', 'D+': 'P4_DP', 'GND': 'GND'}, mpn='Wurth 61300411121', mfr='Wurth', **P_H4)
d.chip('U', MCP2221A, {'VDD': 'CON_3V3', 'VUSB': 'CON_3V3', 'D+': 'P2_DP', 'D-': 'P2_DM', '~{RST}': 'CON_RST',
                       'UTx': 'CON_TX', 'URx': 'CON_RX', 'GP0': None, 'GP1': None, 'GP2': None, 'GP3': None,
                       'SDA': None, 'SCL': None, 'VSS': 'GND'},
       desc='console USB-UART on hub port 2 (CDC, no driver needed), socketed, under the hub', **src(3.20, FC + 'MCP2221A-I%2FP', 'yes'))
C('C', '100n', 'CON_3V3', 'GND', desc='MCP2221A VDD', **C100N)
C('C', '100n', 'CON_3V3', 'GND', desc='MCP2221A VUSB (tied to VDD for 3.3 V operation)', **C100N)
R('R', '10k', 'CON_3V3', 'CON_RST', 'RST pull-up (datasheet: 1-10k to VDD)')
d.chip('U', MCP1700, {'VIN': 'HUB_VBUS', 'VOUT': 'CON_3V3', 'GND': 'GND'}, desc='3.3 V for the console from HUB_VBUS',
       **src(0.50, FC + 'MCP1700-3302E%2FTO', 'yes'))
C('C', '1u', 'HUB_VBUS', 'GND', desc='LDO input (keeps total VBUS capacitance under 10 uF)', **C1U)
C('C', '1u', 'CON_3V3', 'GND', desc='LDO output', **C1U)
R('R', '1k', 'CON_TX', 'J14_CON_RXD', 'console TX -> J14 pin 3: 1k so a TXB-type level shifter on the dev kit still '
  'toggles (review M1)')
R('R', '10k', 'J14_CON_TXD', 'CON_RX', 'J14 pin 4 -> console RX: same, the other way')
R('R', '2.2', 'VUSB_GND', 'GND', 'FSESC USB ground: keeps motor current out of the USB cable ground (review M6); 2.2 '
  'Ohm (not 3.3) because the FSESC may draw its USB VBUS current back through it (0.2 V at 100 mA); a failed ESC- '
  'joint burns it open like a fuse')

# =============================================================================== G. supervisor
d.block('G_SUPER', 'Supervisor: Raspberry Pi Pico in sockets (GPIO map: PINMAP.md)', [
    'Pico VSYS from +5V through the 1N5817; its 3V3(OUT) is the board +3V3 (about 300 mA available).',
    'Its micro-USB goes to a dev-kit USB-A (USB CDC link), or to hub port 4 (J603) for flashing from the laptop.',
    'ADC dividers 100k / 18k: 16.8 V -> 2.56 V, 20 V -> 3.05 V, 30 V -> 4.6 V through 15k (65 uA into the clamp).',
    'BAT_SENSE is taken from VSYS_SW (equals the pack when on) so no divider drains the pack while the car is off.',
    'Status LEDs from GP17 / GP18 through 470 Ohm (2.8 mA, within the default 4 mA drive).',
])
_pico = {'GP0': 'BMS_TX', 'GP1': 'BMS_RX', 'GP2': 'PRECHARGE_EN', 'GP3': 'MAIN_EN', 'GP4': 'I2C0_SDA',
         'GP5': 'I2C0_SCL', 'GP6': 'LIDAR_EN', 'GP7': 'JETSON_PWR_KEY', 'GP8': 'JETSON_RESET', 'GP9': 'LATCH_OFF',
         'GP10': 'ESTOP_OK', 'GP11': 'JETSON_UP', 'GP12': 'JETSON_3V3_SENSE', 'GP13': 'BUTTON_N',
         'GP14': 'VESC_KILL', 'GP15': 'CHG_PRESENT_N', 'GP16': 'FAN_PWM', 'GP17': 'LED_STATUS', 'GP18': 'LED_FAULT',
         'GP19': 'ESTOP_OK_TO_JETSON', 'GP20': 'CHG_STAT_N_TO_JETSON', 'GP21': 'LIDAR_REQ', 'GP22': 'DEVKIT_PWR',
         'RUN': 'PICO_RUN', 'GP26_ADC0': 'VM_SENSE', 'GP27_ADC1': 'BAT_SENSE', 'AGND': 'GND',
         'GP28_ADC2': 'FET_NTC', 'ADC_VREF': None, '3V3': '+3V3', '3V3_EN': None, 'VSYS': 'PICO_VSYS', 'VBUS': None,
         'GND': 'GND'}
d.chip('MOD', PICO, _pico, desc='supervisor MCU module in 2 x 1x20 female sockets (Sullins PPTC201LFBN-RC, 8.5 mm, '
                                 '$1.05 each); the 74HCT08 and two PC817s sit under it',
       **src(4.00 + 2 * 1.05, FC + 'SC0915', 'yes'))
C('C', '100n', '+3V3', 'GND', desc='3V3 decoupling at the Pico', **C100N)
C10('PICO_VSYS', 'GND', 'Pico VSYS bulk')
R('R', '100k', 'VM', 'VM_SENSE', 'VM divider top')
R('R', '18k', 'VM_SENSE', 'GND', 'VM divider bottom: 0.1525')
C('C', '100n', 'VM_SENSE', 'GND', desc='VM sense filter (1.5 ms)', **C100N)
R('R', '100k', 'VSYS_SW', 'BAT_SENSE', 'pack divider top (from VSYS_SW: no drain when off)')
R('R', '18k', 'BAT_SENSE', 'GND', 'pack divider bottom: 0.1525')
C('C', '100n', 'BAT_SENSE', 'GND', desc='pack sense filter', **C100N)
R('R', '470', 'LED_STATUS', 'LEDS_A', 'status LED')
d.stock('D', 'Device:LED', 'GREEN', LED3, {'1': 'GND', '2': 'LEDS_A'}, mpn='Lite-On LTL-4231N (3 mm green)',
        mfr='Lite-On', desc='LED_STATUS', **P_LED_G)
R('R', '470', 'LED_FAULT', 'LEDF_A', 'fault LED')
d.stock('D', 'Device:LED', 'RED', LED3, {'1': 'GND', '2': 'LEDF_A'}, mpn='Lite-On LTL-4221N (3 mm red)',
        mfr='Lite-On', desc='LED_FAULT', **P_LED_R)
TPL('+3V3')
TPP('PICO_RUN')

# =============================================================================== H. Jetson ribbon and J14
d.block('H_JETSON', 'Jetson dev kit: J12 40-pin ribbon (2x20 box header) and J14 button-header harness', [
    'J12 per C_jetson_mech.md section 5: pins 1, 2, 4, 24, 37, 39, 40 not connected (a ribbon turned round maps',
    'pin n to 41-n: nothing then shorts the dev-kit 5 V). Board outputs toward the Jetson are behind 1k: the dev',
    'kit level-shifts these pins (TXB-type, holds a pin through about 4k), so 10k would not toggle them (review M1).',
    'UART1 (pins 8 TX, 10 RX) passes to the FSESC COMM header, crossed (10k toward the FSESC, 1k toward the Jetson);',
    'the VESC 3.3 V pin is not used.',
    'I2C1 (pins 3/5, bus 7, 2.2k pull-ups on the dev kit) to the Pico GP4/GP5 through 330 Ohm (DNP), no pull-ups.',
    'J14: PC817s across 12/11 (power key, 150-200 ms) and 8/7 (reset, 100 ms); recovery button 10/9;',
    'console 3/4/7. Pins 1, 2, 5, 6 open (auto power-on stays enabled). Key the 1x12 housing with a printed clip.',
])
_J12 = {1: None, 2: None, 3: 'J12_SDA', 4: None, 5: 'J12_SCL', 6: 'GND', 7: 'J12_GPIO09', 8: 'J12_TXD', 9: 'GND',
        10: 'J12_RXD', 14: 'GND', 15: 'J12_GPIO12', 17: 'J12_3V3', 20: 'GND', 25: 'GND', 29: 'J12_LIDAR_REQ',
        30: 'GND', 31: 'J12_JETSON_UP', 32: 'J12_CHG_STAT_N', 33: 'J12_ESTOP_OK', 34: 'GND', 36: 'J12_CTS'}
_J12N = ['3V3', '5V', 'I2C1_SDA', '5V', 'I2C1_SCL', 'GND', 'GPIO09', 'UART1_TXD', 'GND', 'UART1_RXD', 'UART1_RTS',
         'I2S0_SCLK', 'SPI1_SCK', 'GND', 'GPIO12', 'SPI1_CS1', '3V3', 'SPI1_CS0', 'SPI0_MOSI', 'GND', 'SPI0_MISO',
         'SPI1_MISO', 'SPI0_SCK', 'SPI0_CS0', 'GND', 'SPI0_CS1', 'I2C0_SDA', 'I2C0_SCL', 'GPIO01', 'GND', 'GPIO11',
         'GPIO07', 'GPIO13', 'GND', 'I2S0_FS', 'UART1_CTS', 'SPI1_MOSI', 'I2S0_DIN', 'GND', 'I2S0_DOUT']
d.chip('J', conn('J12_RIBBON', 40, 'Connector_IDC:IDC-Header_2x20_P2.54mm_Vertical', mpn='Wurth 61204021621',
                  mfr='Wurth', desc='2x20 shrouded box header for the 40-wire IDC ribbon to dev-kit J12',
                  names=[f'{i + 1}_{n}' for i, n in enumerate(_J12N)]),
       {f'{i}_{_J12N[i - 1]}': _J12.get(i) for i in range(1, 41)}, **src(1.21, FC + '61204021621', 'yes'))
R('R', '330', 'J12_SDA', 'I2C0_SDA', 'I2C series, spare link: DNP (an unpowered Pico would clamp dev-kit bus 7)', dnp=True)
R('R', '330', 'J12_SCL', 'I2C0_SCL', 'I2C series, spare link: DNP', dnp=True)
R('R', '10k', 'J12_TXD', 'COMM_RX', 'Jetson UART1 TX -> FSESC RX; limits back-power into an unpowered ESC')
R('R', '1k', 'COMM_TX', 'J12_RXD', 'FSESC TX -> Jetson UART1 RX: 1k so a TXB-type level shifter toggles (review M1)')
R('R', '1k', 'J12_CTS', 'GND', 'DNP: ties UART1 CTS low; fit only if vesc_driver keeps hardware flow control (B_esc.md)', dnp=True)
R('R', '10k', 'J12_3V3', 'JETSON_3V3_SENSE', '3.3 V sense series (never tied to the board 3.3 V)')
R('R', '100k', 'JETSON_3V3_SENSE', 'GND', '3.3 V sense: 3.0 V at the Pico')
R('R', '100k', 'J12_JETSON_UP', 'GND', 'JETSON_UP pull-down: reads 0 while the module is off')
R('R', '10k', 'J12_JETSON_UP', 'JETSON_UP', 'series into GP11: 0.3 mA at most into an unpowered Pico')
R('R', '100k', 'J12_LIDAR_REQ', 'GND', 'LIDAR_REQ pull-down')
R('R', '10k', 'J12_LIDAR_REQ', 'LIDAR_REQ', 'series into GP21: 0.3 mA at most into an unpowered Pico')
R('R', '1k', 'ESTOP_OK_TO_JETSON', 'J12_ESTOP_OK', 'board output toward the Jetson, 1k (TXB-type input, review M1)')
R('R', '1k', 'CHG_STAT_N_TO_JETSON', 'J12_CHG_STAT_N', 'board output toward the Jetson, 1k (TXB-type input, review M1)')
TPP('J12_GPIO09')
TPP('J12_GPIO12')
_J14N = ['PC_LED-', 'PC_LED+', 'UART2_RXD', 'UART2_TXD', 'AC_OK', 'APO_DIS', 'GND', 'SYS_RESET*', 'GND',
         'FORCE_RECOVERY*', 'GND', 'SLEEP/WAKE*']
_J14 = {1: None, 2: None, 3: 'J14_CON_RXD', 4: 'J14_CON_TXD', 5: None, 6: None, 7: 'GND', 8: 'J14_RESET_N',
        9: 'GND', 10: 'J14_RECOVERY_N', 11: 'GND', 12: 'J14_PWR_KEY_N'}
d.chip('J', conn('J14_HARNESS', 12, H1.format(12), desc='1x12 header for the Dupont lead to dev-kit J14',
                  names=[f'{i + 1}_{n}' for i, n in enumerate(_J14N)]),
       {f'{i}_{_J14N[i - 1]}': _J14[i] for i in range(1, 13)}, mpn='Wurth 61301211121', mfr='Wurth',
       **src(0.54, FC + '61301211121', 'yes'))
d.chip('U', PC817, {'A': 'PWRKEY_A', 'K': 'GND', 'C': 'J14_PWR_KEY_N', 'E': 'GND'},
       desc='Jetson power key (J14 12 to 11)', **src(0.42, FC + 'PC817X2NSZ9F', 'yes'))
R('R', '470', 'JETSON_PWR_KEY', 'PWRKEY_A', 'LED 2.8 mA from GP7')
d.chip('U', PC817, {'A': 'RESET_A', 'K': 'GND', 'C': 'J14_RESET_N', 'E': 'GND'},
       desc='Jetson hard reset (J14 8 to 7)', **src(0.42, FC + 'PC817X2NSZ9F', 'yes'))
R('R', '470', 'JETSON_RESET', 'RESET_A', 'LED 2.8 mA from GP8')
d.stock('SW', 'Switch:SW_Push', 'RECOVERY', 'Button_Switch_THT:SW_PUSH_6mm_H5mm', {'1': 'J14_RECOVERY_N', '2': 'GND'},
        mpn='PTS645SL50-2 LFS', mfr='C&K', desc='Jetson force-recovery (hold, then reset or apply power)',
        **src(0.25, FC + 'PTS645SL50-2LFS', 'yes'))

# =============================================================================== I. ESC interface
d.block('I_ESC', 'ESC interface: VM pads, COMM header, servo-signal input', [
    'FSESC (Mini 6.7 Pro) power: 12 AWG (or an XT60 pigtail) soldered into J901/J902 at the X=0 edge, the ESC-',
    'pad beside the pack BAT- return. The FSESC has no enable input; the main switch is its E-stop.',
    'COMM 7-pin JST-PH: 1 3V3 (not used), 2 GND, 3 TX, 4 RX, 5 ADC1 (not used), 6 ADC2, 7 PPM (not used).',
    'PIN ORDER UNVERIFIED: read the FSESC silkscreen before crimping; the crimps can be re-ordered in the housing.',
    'ADC2 = VESC_KILL through 1k (VESC kill switch "ADC2 low", 1.65 V threshold; 0 V = kill). 100k pull-down.',
    'SERVO_IN: the FSESC servo/PPM output (3.3 V) -> 10k -> 74HCT08 buffer (5 V) -> 220 Ohm -> servo header.',
    'Review M6: the FSESC signal grounds (COMM pin 2, the servo lead, its USB) run beside its ESC- lead, which drops',
    'about 90 mV at 90 A. Each goes to GND through 3.3 Ohm: 20-30 mA of loop current instead of amps, and the',
    'resistor opens like a fuse if the ESC- joint fails. Run ESC+ and ESC- as one strain-relieved pair.',
])
d.chip('J', conn('PAD_ESC+', 1, W10, desc='ESC + (VM), 10-12 AWG'), {'1': 'VM'}, value='ESC+', in_bom='no')
d.chip('J', conn('PAD_ESC-', 1, W10, desc='ESC - (GND), 10-12 AWG'), {'1': 'GND'}, value='ESC-', in_bom='no')
d.chip('J', conn('FSESC_COMM', 7, 'Connector_JST:JST_PH_B7B-PH-K_1x07_P2.00mm_Vertical', mpn='B7B-PH-K-S(LF)(SN)',
                  mfr='JST', desc='FSESC COMM (pin order unverified)',
                  names=['3V3', 'GND', 'TX', 'RX', 'ADC1', 'ADC2', 'PPM']),
       {'3V3': None, 'GND': 'COMM_GND', 'TX': 'COMM_TX', 'RX': 'COMM_RX', 'ADC1': None, 'ADC2': 'COMM_ADC2', 'PPM': None},
       **src(0.33, FC + 'B7B-PH-K-S', 'yes'))
R('R', '1k', 'VESC_KILL', 'COMM_ADC2', 'kill line series (B_esc.md)')
R('R', '100k', 'VESC_KILL', 'GND', 'kill asserted (0 V) while the Pico is in reset')
d.chip('J', conn('SERVO_IN', 3, H1.format(3), desc='servo signal from the FSESC servo/PPM port (S / + / -; + unused)',
                  names=['SIG', '5V', 'GND']), {'SIG': 'SERVO_IN_J', '5V': None, 'GND': 'SRVIN_GND'},
       mpn='Wurth 61300311121', mfr='Wurth', **P_H3)
R('R', '10k', 'SERVO_IN_J', 'SERVO_IN', 'input series: 0.3 mA at most into the unpowered 74HCT08 when the ESC runs on USB')
R('R', '100k', 'SERVO_IN', 'GND', 'defined low while the ESC is off')
R('R', '3.3', 'COMM_GND', 'GND', 'FSESC COMM ground through 3.3 Ohm (review M6)')
R('R', '3.3', 'SRVIN_GND', 'GND', 'servo-signal lead ground through 3.3 Ohm (review M6)')

# =============================================================================== J. E-stop, fan, holes
d.block('J_MISC', 'E-stop loop, fan, mounting holes, board ID', [
    'E-stop: 3.3 V -> 1k -> normally-closed loop (JST-PH 2) -> 100 Ohm -> ESTOP_OK, 10k + 10 nF to GND (0.1 ms;',
    'review m3: a slow edge into the non-Schmitt 74HCT08 could chatter the main switch).',
    'Closed = 3.0 V (HCT VIH 2.0 V, Pico VIH 2.0 V); open or unplugged = 0 V = stop. BAT85 clamps on the lead.',
    'Fan 4-pin 5 V: PWM from GP16 through a 2N7000 (open drain); with the Pico off the fan runs at full speed.',
    'Mounting: 6 x M3 at (4,4), (4,80), (75,4), (75,80), (L-4,4), (L-4,80), 7 mm keep-out, not plated.',
    'Board ID: silkscreen "ATLAS-PWR-1 rev B" and a serial box (layout.py).',
])
d.chip('J', conn('ESTOP', 2, 'Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical', mpn='B2B-PH-K-S(LF)(SN)', mfr='JST',
                  desc='E-stop loop, normally closed (jumper lead if no button)'), {'1': 'ESTOP_SRC', '2': 'ESTOP_IN'},
       **src(0.12, FC + 'B2B-PH-K-S', 'yes'))
R('R', '1k', '+3V3', 'ESTOP_SRC', 'loop source, 3 mA into a shorted lead')
R('R', '100', 'ESTOP_IN', 'ESTOP_OK', 'loop filter')
R('R', '10k', 'ESTOP_OK', 'GND', 'open loop reads low = stop')
C('C', '10n', 'ESTOP_OK', 'GND', desc='loop filter (0.1 ms)', **C10N)
d.D('D', 'BAT85', 'GND', 'ESTOP_IN', DO35, kind='S', mpn='BAT85S-TAP', mfr='Vishay', desc='lead clamp to GND',
    **src(0.43, FC + 'BAT85', 'yes'))
d.D('D', 'BAT85', 'ESTOP_IN', '+3V3', DO35, kind='S', mpn='BAT85S-TAP', mfr='Vishay', desc='lead clamp to 3.3 V',
    **src(0.43, FC + 'BAT85', 'yes'))
d.chip('J', conn('BTN_REMOTE', 2, 'Connector_JST:JST_PH_S2B-PH-K_1x02_P2.00mm_Horizontal', mpn='S2B-PH-K-S(LF)(SN)',
                  mfr='JST', desc='remote power button (parallel to SW401), side entry at the front edge'),
       {'1': 'BTN_HI', '2': 'LATCH_ON'}, **src(0.12, FC + 'S2B-PH-K-S', 'yes'))
d.chip('J', conn('FAN', 4, 'Connector:FanPinHeader_1x04_P2.54mm_Vertical', mpn='Molex 47053-1000', mfr='Molex',
                  desc='side-pod fan, 5 V PWM (Noctua NF-A4x10 5V PWM)', names=['GND', '+5V', 'TACH', 'PWM']),
       {'GND': 'GND', '+5V': '+5V', 'TACH': 'FAN_TACH', 'PWM': 'FAN_PWM_N'}, **src(0.56, FC + '0470531000', 'yes'))
d.chip('Q', N7000, {'G': 'FAN_G', 'D': 'FAN_PWM_N', 'S': 'GND'}, desc='fan PWM pull-down', **src(0.50, FC + '2N7000', 'yes'))
R('R', '100', 'FAN_PWM', 'FAN_G', 'gate series')
R('R', '100k', 'FAN_G', 'GND', 'gate pull-down: fan full speed with the Pico off')
TPP('FAN_TACH')
TPL('GND')
MH = 'atlas:MountingHole_3.2mm_M3_Keepout7mm'
for _ in range(6):
    d.stock('H', 'Mechanical:MountingHole', 'M3', MH, {}, desc='M3 mounting hole, 7 mm keep-out', in_bom='no')

# test-only nets: a single pin plus a test point is intended
d.nc_nets.update({'J12_GPIO09', 'J12_GPIO12', 'FAN_TACH', 'PICO_RUN'})

if __name__ == '__main__':
    bad = d.check()
    print(len(d.parts), 'parts', len(d.nets()), 'nets')
    for net, nodes in bad:
        print('single-pin net', net, nodes)
