"""Pin tables for the ATLAS-PWR-1 parts that boards/tools/chips.py does not have (box symbols).

Every table was checked against the source named next to it. Through-hole packages only; the
modules sit on 2.54 mm headers (Pico, hub, PD trigger) or are wired to labelled pads (Pololu
modules, CC/CV buck), because their hole positions could not be read from the vendor drawings.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
from eda import Chip, P_IN, P_OUT, BIDI, PAS, PWR_IN, PWR_OUT, NC  # noqa: E402

L, R, T, B = 'L', 'R', 'T', 'B'

# ------------------------------------------------------------------ ICs
# Microchip DS20006767A table 3-1: 1 V+, 2 Input, 3 Source, 4 Ground, 5 Gate, 6-8 not connected.
MIC5014 = Chip('MIC5014', [
    ('1', 'V+', PWR_IN, T), ('2', 'IN', P_IN, L), ('4', 'GND', PWR_IN, B),
    ('5', 'GATE', P_OUT, R), ('3', 'SOURCE', PAS, R), (['6', '7', '8'], 'NC', NC, R),
], 'Package_DIP:DIP-8_W7.62mm_Socket', desc='high-side MOSFET driver with charge pump, 2.75-30 V, 15 V gate clamp',
    mpn='MIC5014YN', mfr='Microchip', width=12.7)

# TI SN74HCT08 / KiCad 74xx:74LS08 (same 7408 pinout): gates 1-2>3, 4-5>6, 9-10>8, 12-13>11, GND 7, VCC 14.
HCT08 = Chip('74HCT08', [
    ('14', 'VCC', PWR_IN, T),
    ('1', '1A', P_IN, L), ('2', '1B', P_IN, L), ('4', '2A', P_IN, L), ('5', '2B', P_IN, L),
    ('9', '3A', P_IN, L), ('10', '3B', P_IN, L), ('12', '4A', P_IN, L), ('13', '4B', P_IN, L),
    ('3', '1Y', P_OUT, R), ('6', '2Y', P_OUT, R), ('8', '3Y', P_OUT, R), ('11', '4Y', P_OUT, R),
    ('7', 'GND', PWR_IN, B),
], 'Package_DIP:DIP-14_W7.62mm_Socket', desc='quad 2-input AND, TTL-level inputs (3.3 V logic in, 5 V out)',
    mpn='SN74HCT08N', mfr='Texas Instruments', width=12.7)

# Microchip MCP2221A data sheet DS20005565D, 14-pin PDIP: 1 VDD, 2 GP0, 3 GP1, 4 RST, 5 URx, 6 UTx, 7 GP2,
# 8 GP3, 9 SDA, 10 SCL, 11 VUSB, 12 D-, 13 D+, 14 VSS (also KiCad Interface_USB:MCP2221AxP).
MCP2221A = Chip('MCP2221A', [
    ('1', 'VDD', PWR_IN, T), ('11', 'VUSB', PAS, T),
    ('13', 'D+', BIDI, L), ('12', 'D-', BIDI, L), ('4', '~{RST}', P_IN, L),
    ('6', 'UTx', P_OUT, R), ('5', 'URx', P_IN, R), ('2', 'GP0', BIDI, R), ('3', 'GP1', BIDI, R),
    ('7', 'GP2', BIDI, R), ('8', 'GP3', BIDI, R), ('9', 'SDA', BIDI, R), ('10', 'SCL', BIDI, R),
    ('14', 'VSS', PWR_IN, B),
], 'Package_DIP:DIP-14_W7.62mm_Socket', desc='USB 2.0 full-speed to UART bridge (CDC), 3.3 V operation (VUSB tied to VDD)',
    mpn='MCP2221A-I/P', mfr='Microchip', width=15.24)

# KiCad Regulator_Linear:MCP1700x-330xxTO (from Microchip DS20001826): TO-92 1 GND, 2 VIN, 3 VOUT.
MCP1700 = Chip('MCP1700-3302E/TO', [('2', 'VIN', PWR_IN, L), ('3', 'VOUT', PWR_OUT, R), ('1', 'GND', PWR_IN, B)],
               'Package_TO_SOT_THT:TO-92_Inline', desc='3.3 V 250 mA LDO, 6 V max input, TO-92',
               mpn='MCP1700-3302E/TO', mfr='Microchip', width=10.16)

# KiCad Regulator_Switching:R-78E5.0-1.0 (RECOM R-78Exx-1.0 datasheet): 1 +Vin, 2 GND, 3 +Vout; 7805 pinout.
R78E = Chip('R-78E5.0-1.0', [('1', 'VIN', PWR_IN, L), ('3', 'VOUT', PWR_OUT, R), ('2', 'GND', PWR_IN, B)],
            'Converter_DCDC:Converter_DCDC_RECOM_R-78E-0.5_THT', desc='5 V 1 A switching regulator, 8-28 V in, SIP-3',
            mpn='R-78E5.0-1.0', mfr='RECOM', width=10.16)

# TI TL431 LP (TO-92) / KiCad Reference_Voltage:TL431LP: 1 REF, 2 ANODE, 3 CATHODE.
TL431 = Chip('TL431', [('1', 'REF', P_IN, L), ('3', 'K', PAS, T), ('2', 'A', PAS, B)],
             'Package_TO_SOT_THT:TO-92_Inline', desc='2.495 V shunt reference (dev-kit over-voltage cut-off)',
             mpn='TL431ACLPRE3', mfr='Texas Instruments', width=7.62)

# Sharp PC817 / KiCad Isolator:PC817: 1 anode, 2 cathode, 3 emitter, 4 collector.
PC817 = Chip('PC817', [('1', 'A', PAS, L), ('2', 'K', PAS, L), ('4', 'C', PAS, R), ('3', 'E', PAS, R)],
             'Package_DIP:DIP-4_W7.62mm', desc='optocoupler, 5 kV isolation, DIP-4',
             mpn='PC817X2NSZ9F', mfr='Sharp', width=10.16)

# ------------------------------------------------------------------ discretes (TO-220 G-D-S, TO-92 E-B-C / S-G-D)
# Infineon IRFB7430PBF and IRF9Z34NPBF data sheets, TO-220AB: 1 gate, 2 drain (and tab), 3 source.
IRFB7430 = Chip('IRFB7430PBF', [('1', 'G', P_IN, L), ('2', 'D', PAS, T), ('3', 'S', PAS, B)],
                'Package_TO_SOT_THT:TO-220-3_Vertical', ref='Q',
                desc='N-FET 40 V 1.3 mOhm max (10 V), Qg 300 nC, TO-220 (tab = drain)', mpn='IRFB7430PBF',
                mfr='Infineon', width=7.62)
IRF9Z34N = Chip('IRF9Z34NPBF', [('1', 'G', P_IN, L), ('3', 'S', PAS, T), ('2', 'D', PAS, B)],
                'Package_TO_SOT_THT:TO-220-3_Vertical', ref='Q',
                desc='P-FET -55 V 100 mOhm, VGS +-20 V, TO-220 (tab = drain)', mpn='IRF9Z34NPBF', mfr='Infineon',
                width=7.62)
# Infineon IRF4905PBF: TO-220AB, pin 1 G, 2 D, 3 S (same as the IRF9Z34N), -55 V, 20 mOhm at -10 V, +-20 V gate
IRF4905 = Chip('IRF4905PBF', [('1', 'G', P_IN, L), ('3', 'S', PAS, T), ('2', 'D', PAS, B)],
               'Package_TO_SOT_THT:TO-220-3_Vertical', ref='Q',
               desc='P-FET -55 V 20 mOhm, VGS +-20 V, TO-220 (tab = drain)', mpn='IRF4905PBF', mfr='Infineon',
               width=7.62)
# onsemi 2N3904BU / 2N3906BU (KiCad Transistor_BJT:2N3904, 2N3906): TO-92 1 E, 2 B, 3 C.
NPN = Chip('2N3904', [('2', 'B', P_IN, L), ('3', 'C', PAS, T), ('1', 'E', PAS, B)], 'Package_TO_SOT_THT:TO-92_Inline',
           ref='Q', desc='NPN 40 V 200 mA, TO-92', mpn='2N3904BU', mfr='onsemi', width=7.62)
PNP = Chip('2N3906', [('2', 'B', P_IN, L), ('1', 'E', PAS, T), ('3', 'C', PAS, B)], 'Package_TO_SOT_THT:TO-92_Inline',
           ref='Q', desc='PNP 40 V 200 mA, TO-92', mpn='2N3906BU', mfr='onsemi', width=7.62)
# onsemi 2N7000 (KiCad Transistor_FET:2N7000): TO-92 1 S, 2 G, 3 D.
N7000 = Chip('2N7000', [('2', 'G', P_IN, L), ('3', 'D', PAS, T), ('1', 'S', PAS, B)], 'Package_TO_SOT_THT:TO-92_Inline',
             ref='Q', desc='N-MOSFET 60 V 200 mA logic level, TO-92', mpn='2N7000-G', mfr='Microchip', width=7.62)

# ------------------------------------------------------------------ modules
# Raspberry Pi Pico: 2 x 20 castellated pins at 2.54 mm, rows 17.78 mm apart, 51 x 21 mm (Pico datasheet;
# pin order cross-checked with github.com/ncarandini/KiCad-RP-Pico). Pins 1-20 down the left side from the
# USB end, 21-40 back up the right side.
_PICO = {1: 'GP0', 2: 'GP1', 3: 'GND', 4: 'GP2', 5: 'GP3', 6: 'GP4', 7: 'GP5', 8: 'GND', 9: 'GP6', 10: 'GP7',
         11: 'GP8', 12: 'GP9', 13: 'GND', 14: 'GP10', 15: 'GP11', 16: 'GP12', 17: 'GP13', 18: 'GND', 19: 'GP14',
         20: 'GP15', 21: 'GP16', 22: 'GP17', 23: 'GND', 24: 'GP18', 25: 'GP19', 26: 'GP20', 27: 'GP21', 28: 'GND',
         29: 'GP22', 30: 'RUN', 31: 'GP26_ADC0', 32: 'GP27_ADC1', 33: 'AGND', 34: 'GP28_ADC2', 35: 'ADC_VREF',
         36: '3V3', 37: '3V3_EN', 38: 'GND', 39: 'VSYS', 40: 'VBUS'}


def _pico_pins():
    pins = []
    gnd = [str(n) for n, nm in _PICO.items() if nm == 'GND']
    for n, nm in _PICO.items():
        if nm == 'GND':
            continue
        typ = {'3V3': PWR_OUT, 'VSYS': PWR_IN, 'VBUS': PAS, 'AGND': PWR_IN, 'RUN': P_IN, '3V3_EN': P_IN,
               'ADC_VREF': PAS}.get(nm, BIDI)
        pins.append((str(n), nm, typ, L if n <= 20 else R))
    pins.append((gnd, 'GND', PWR_IN, B))
    return pins


PICO = Chip('RPi_Pico', _pico_pins(), 'atlas:RaspberryPi_Pico_Socketed_2x20_P17.78mm', ref='MOD',
            desc='Raspberry Pi Pico (RP2040) in two 1x20 female sockets', mpn='SC0915', mfr='Raspberry Pi', width=25.4)

# Adafruit 5997 CH334F 4-port hub: pad positions from adafruit/Adafruit-CH334F-Breakout-PCB (Eagle board).
# Footprint pad numbers: 1-4 upstream (VBUS, D+, D-, GND), then ports 1..4, four pads each in the same order.
_hub = [(['1'], 'UP_VBUS', PAS, L), ('2', 'UP_D+', BIDI, L), ('3', 'UP_D-', BIDI, L), ('4', 'UP_GND', PAS, L)]
for _p in range(4):
    _b = 5 + 4 * _p
    _hub += [(str(_b), f'P{_p + 1}_VBUS', PAS, R), (str(_b + 1), f'P{_p + 1}_D+', BIDI, R),
             (str(_b + 2), f'P{_p + 1}_D-', BIDI, R), (str(_b + 3), f'P{_p + 1}_GND', PAS, R)]
HUB5997 = Chip('ADA5997_CH334F_HUB', _hub, 'atlas:Adafruit_5997_CH334F_Hub_Headers', ref='MOD',
               desc='USB 2.0 high-speed 4-port hub breakout (CH334F), bus powered, VBUS passed to all ports',
               mpn='5997', mfr='Adafruit', width=20.32)

# Adafruit 5807 HUSB238 PD trigger: off the board (in the side pod at the charge window, next to the CC/CV buck),
# its VOUT / GND terminal-block holes wired to two labelled pads (20 AWG, 3 A).
HUSB238 = Chip('ADA5807_HUSB238', [('1', 'VOUT', PWR_OUT, R), ('2', 'GND', PAS, B)], 'atlas:WireLand_PD_Trigger',
               ref='MOD', desc='USB-C PD sink trigger (HUSB238), jumpers set to 20 V / 3 A; off board in the pod, wired',
               mpn='5807', mfr='Adafruit', width=10.16)

# Pololu #2813: wired to labelled pads (pin positions on the module could not be read from Pololu's drawing).
POLOLU2813 = Chip('POLOLU_2813', [
    ('1', 'VIN', PWR_IN, L), ('3', 'GND', PWR_IN, B), ('2', 'VOUT', PWR_OUT, R), ('4', 'ON', P_IN, L),
    ('5', 'OFF', P_IN, L),
], 'atlas:WireLand_Pololu_2813', ref='MOD',
    desc='Big Pushbutton Power Switch HP: 4.5-40 V, 6 A cont., ON/OFF pulse inputs; off board (tray), wired with 18 AWG',
    mpn='2813', mfr='Pololu', width=15.24)

# Pololu S18V20F12 and the CC/CV buck: off-board modules wired to labelled pads. The camera regulator's input
# comes from the board; its 12 V output goes straight to the camera lead (no return to the board).
S18V20F12 = Chip('POLOLU_S18V20F12', [('1', 'VIN', PWR_IN, L), ('2', 'GND', PWR_IN, B)],
                 'atlas:WireLand_Pololu_S18V20F12', ref='MOD',
                 desc='12 V step-up/step-down regulator (camera), 3-30 V in; off board on the tray, input wired to these pads, '
                      'output to the camera M8 lead', mpn='2577 (S18V20F12)', mfr='Pololu', width=10.16)
CCCV = Chip('CCCV_BUCK_XL4015', [
    ('1', 'IN+', PWR_IN, L), ('2', 'IN-', PWR_IN, B), ('3', 'OUT+', PWR_OUT, R), ('4', 'OUT-', PWR_IN, B),
], 'atlas:WireLand_CCCV_Buck', ref='MOD',
    desc='CC/CV buck module, XL4015 class 5 A; set CV 16.80 V, CC 2.5 A; mounted off the board, wired to these pads',
    mpn='XL4015 CC/CV 5 A module (generic)', mfr='generic', width=15.24)

HEATSINK = Chip('HEATSINK_BAR', [], 'atlas:Heatsink_Bar_3xTO220_40x15x3mm', ref='HS',
                desc='aluminium bar 40 x 15 x 3 mm bolted to the three main FET tabs (M3); live at BAT+, insulate it',
                mpn='6061 bar 40 x 15 x 3 mm, 3 x 3.2 mm holes at 13.0 mm', mfr='SendCutSend or stock bar', width=10.16)
