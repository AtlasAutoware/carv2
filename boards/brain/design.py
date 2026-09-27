"""ATLAS-BRN-1, the brain board: Antmicro's open Jetson Orin Nano/NX baseboard with the parts the car
does not need taken out and these four sheets added.

The Antmicro sheets stay Antmicro's (boards/brain/vendor/antmicro, Apache-2.0); fork.py removes
what the car does not use and hangs these sheets from Antmicro's root sheet. Every net here is a
global label, so the names below that also exist in the Antmicro sheets (+3V3, POE_OUTPUT,
UART1_TXD and so on) are the same nets.

Refs start at 1001 so they never collide with Antmicro's (all below 400).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
sys.path.insert(0, os.path.join(HERE, '..', 'stack'))
from eda import Design  # noqa: E402
from chips import (NTS0102, NFET_SOT523, PFET_SOT23, NFET_100V, TPS259474, LM5155, TPS23861, LAN7800,  # noqa: E402
                   RJ45_MAG, conn)
import stack  # noqa: E402

d = Design('atlas_brain', 'ATLAS-BRN-1 brain board', rev='0.1', ref_base=900)
TI = 'Texas Instruments'
MUR = 'Murata'

# =============================================================================== A. stack
d.block('BA_STACK', 'Drive board connector, power button, level shifting', [
    'Pin map from boards/stack/stack.py (shared with the drive board). The header sits on the bottom side.',
    'Mating post about 14 mm below the insulator for the 20 mm gap into the SSQ-120-03 socket (3.7-6.4 mm insertion).',
    'Power button: STK_PWR_BTN_N low turns on the P-FET, which drives PWR_SOFT (Antmicro Q7: a button press,',
    'powers the module on) and pulls SLEEP/WAKE* low through Q1004 (the OS sees a power-key event and shuts down).',
    'STK_OS_HALTED: open drain, low while POWER_EN is high (module on). The drive board pulls it up.',
    'STM32 reset: the Jetson sets the expander bit MCU_RST_REQ (old CSIA_PEN), Q1003 pulls NRST low (open drain,',
    'so the STM32 can still reset itself). BOOT0, LIDAR_EN are expander outputs; ESTOP_OK, CHG_STAT inputs.',
    'UART1 (1.8 V on the module) to the STM32 at 3.3 V through an NTS0102 powered from the drive board 3.3 V.',
])
bn = stack.brain_nets()
d.chip('J', conn('STACK_2x20', 40, 'Connector_PinHeader_2.54mm:PinHeader_2x20_P2.54mm_Vertical',
                  mpn='TSW-120-xx-G-D (post length for the 20 mm stack, see notes)', mfr='Samtec',
                  desc='2x20 2.54 mm header into the drive board socket, bottom side',
                  names=[f'P{i}' for i in range(1, 41)]),
       {f'P{i}': bn[i] for i in range(1, 41)}, side='B')
d.chip('Q', PFET_SOT23, {'G': 'STK_PWR_BTN_N', 'S': '3V3_STDB', 'D': 'PWR_SOFT'},
       desc='power button from the drive board: drives PWR_SOFT high (the drive board pulls the gate up)')
d.chip('Q', NFET_SOT523, {'G': 'POWER_EN', 'D': 'STK_OS_HALTED', 'S': 'GND'},
       desc='OS_HALTED: pulled low while the module is powered (drive board pull-up)')
d.chip('Q', NFET_SOT523, {'G': 'MCU_RST_REQ', 'D': 'STK_MCU_NRST', 'S': 'GND'},
       desc='STM32 reset, open drain')
d.chip('Q', NFET_SOT523, {'G': 'PWR_SOFT', 'D': 'SLEEP_WAKE_N', 'S': 'GND'},
       desc='power-key event on module SLEEP/WAKE* while the button request is held')
d.R('R', '100k', 'MCU_RST_REQ', 'GND', desc='reset FET off while the expander pins are inputs')
d.R('R', '100k', '+3V3', 'STK_CHG_STAT',
    desc='charge status pull-up (weak: the drive board has 10k in series with the charger STAT pin)')
d.R('R', '33', 'CAN_TX', 'STK_CAN_TX', desc='CAN TX to the drive board (3.3 V CMOS on the module)')
d.R('R', '33', 'STK_CAN_RX', 'CAN_RX', desc='CAN RX from the drive board')
d.chip('U', NTS0102, {'VCCA': '+1V8', 'VCCB': 'STK_3V3_DRV', 'OE': '+1V8', 'A1': 'UART1_TXD', 'B1': 'STK_VESC_J2M',
                      'A2': 'UART1_RXD', 'B2': 'STK_VESC_M2J', 'GND': 'GND'},
       desc='UART1 1.8 V <-> 3.3 V (drive board side powered by the drive board)')
d.C('C', '100n', '+1V8', 'GND', desc='NTS0102 VCCA')
d.C('C', '100n', 'STK_3V3_DRV', 'GND', desc='NTS0102 VCCB')
MH = 'MountingHole:MountingHole_3.2mm_M3_Pad_Via'
for i in range(2):     # strip corners, over drive H1006 / H1004 (the other two supports are Antmicro's H4 / H3)
    d.stock('H', 'Mechanical:MountingHole_Pad', 'M3', MH, {'1': 'GND'}, desc='M3 mounting hole', in_bom='no')

# =============================================================================== B. input eFuse
d.block('BB_EFUSE', 'Board input: eFuse from the drive board VSYS', [
    'TPS259474A: on when the drive board raises STK_POWER_EN (it also holds a 100k pull-down there).',
    'Output is Antmicro net POE_OUTPUT: Antmicro ideal diode Q16/Q14 -> VCC_IN -> soft start Q18 -> VCC.',
    'ILIM 665 Ohm = 5.0 A (RILM = 3334 / ILIM). Worst case load about 3.3 A at 12 V (module 25 W, NVMe, camera).',
    'OVLO 150k / 10k: off above 19.2 V (pack maximum 16.8 V). dV/dt 2.2 nF: about 0.9 V/ms.',
    'Circuit breaker timer 4.7 nF: about 3.9 ms at 1.2 x ILIM before it trips, then auto-retry.',
])
d.chip('U', TPS259474, {'IN': 'STK_VSYS', 'EN/UVLO': 'STK_POWER_EN', 'OVLO': 'EF_OVLO', 'ILIM': 'EF_ILIM',
                        'DVDT': 'EF_DVDT', 'ITIMER': 'EF_ITIMER', 'OUT': 'POE_OUTPUT', 'PG': None, 'PGTH': None,
                        'GND': 'GND'})
d.R('R', '150k', 'STK_VSYS', 'EF_OVLO', desc='OVLO divider top, 1%')
d.R('R', '10k', 'EF_OVLO', 'GND', desc='OVLO divider bottom, 1%')
d.R('R', '665', 'EF_ILIM', 'GND', desc='current limit 5.0 A, 1%')
d.C('C', '2.2n', 'EF_DVDT', 'GND', desc='output slew rate')
d.C('C', '4.7n', 'EF_ITIMER', 'GND', desc='circuit breaker timer')
for i in range(2):
    d.C('C', '10u 25V', 'STK_VSYS', 'GND', size='1206', mpn='GRM31CR71E106KA12L', mfr=MUR, desc='eFuse input 10 uF 25 V X7R')
d.C('C', '100n 50V', 'STK_VSYS', 'GND', desc='eFuse input')
for i in range(2):
    d.C('C', '22u 25V', 'POE_OUTPUT', 'GND', size='1210', mpn='GRM32ER71E226KE15L', mfr=MUR,
        desc='board input bulk 22 uF 25 V X7R (replaces Antmicro C84/C85, which were 16 V parts)')
d.C('C', '100n 50V', 'POE_OUTPUT', 'GND', desc='board input')

# =============================================================================== C. PoE
d.block('BC_POE', 'Camera PoE: 52 V boost (LM5155) and 802.3at PSE (TPS23861, port 1 on the camera jack)', [
    'Boost 12-16.8 V -> 52 V, 300 kHz (RT 73.2k), 47 uH XAL7070 (Isat 4.2 A), RS 25 mOhm, RSL 634 Ohm (82 % slope).',
    'Current limit about 2.2 A at 12 V in (15 W out with margin); the camera (802.3af) draws about 4 W.',
    'Loop: crossover about 5 kHz (RHP zero 32 kHz at 15 W), RCOMP 15.8k, CCOMP 10n (zero 1 kHz), CHF 330p.',
    'UVLO 56k / 10k: starts at 9.9 V. PGOOD holds the PSE in reset until 52 V is up (TPS23861 VPWR before RESET).',
    'TPS23861 as shipped: auto mode, I2C 0x28 with A3 open (Jetson I2C1). SDAI and SDAO tied. INT to the expander.',
    'Port 1 (Alternative A): VPWR on the 1-2 centre tap, switched return on the 3-6 centre tap of J6.',
    'Ports 2-4 unused: SEN and DRAIN to GND, GATE open (datasheet 8.2.2). Unused camera pairs 4-5, 7-8: Bob Smith.',
])
d.chip('U', LM5155, {'BIAS': 'POE_OUTPUT', 'VCC': 'BST_VCC', 'UVLO/SYNC': 'BST_UVLO', 'FB': 'BST_FB',
                     'COMP': 'BST_COMP', 'SS': 'BST_SS', 'RT': 'BST_RT', 'GATE': 'BST_GATE', 'CS': 'BST_CS',
                     'PGOOD': 'PSE_RESET_N', 'PGND': 'GND', 'AGND': 'GND', 'EP': 'GND'})
d.L('L', '47u', 'POE_OUTPUT', 'BST_SW', 'Inductor_SMD:L_Coilcraft_XAL7070-XXX', mpn='XAL7070-473MEC', mfr='Coilcraft',
    desc='boost inductor 47 uH, Isat 4.2 A (30 %), DCR 84 mOhm')
d.chip('Q', NFET_100V, {'G': 'BST_GATE', 'D': 'BST_SW', 'S': 'BST_RS'}, desc='boost switch')
d.R('R', '0.025', 'BST_RS', 'GND', size='1206', desc='boost current sense 25 mOhm 1% 0.5 W')
d.R('R', '634', 'BST_RS', 'BST_CS', desc='slope compensation RSL, 1%')
d.C('C', '100p', 'BST_CS', 'GND', desc='CS filter, C0G')
d.D('D', 'SS2H10', 'BST_SW', 'POE_52V', 'Diode_SMD:D_SMB', kind='S', mpn='SS2H10-E3/52T', mfr='Vishay',
    desc='boost rectifier, Schottky 100 V 2 A')
for i in range(3):
    d.C('C', '2.2u 100V', 'POE_52V', 'GND', size='1210', mpn='GRM32ER72A225KA35L', mfr=MUR, desc='52 V output, X7R')
d.CP('C', '22u 100V', 'POE_52V', 'GND', 'Capacitor_SMD:CP_Elec_8x10.5', mpn='EEE-FK2A220P', mfr='Panasonic',
     desc='52 V bulk (TI asks for bulk on the PSE supply), aluminium 100 V')
for i in range(2):
    d.C('C', '10u 25V', 'POE_OUTPUT', 'GND', size='1206', mpn='GRM31CR71E106KA12L', mfr=MUR, desc='boost input')
d.C('C', '100n 50V', 'POE_OUTPUT', 'GND', desc='BIAS pin')
d.C('C', '2.2u 16V', 'BST_VCC', 'GND', size='0603', desc='VCC regulator (1-4.7 uF)')
d.R('R', '73.2k', 'BST_RT', 'GND', desc='RT: 2.21e10 / 300 kHz - 955, 1%')
d.R('R', '510k', 'POE_52V', 'BST_FB', size='0603', desc='FB top: 52 V with VREF 1.0 V, 1%')
d.R('R', '10k', 'BST_FB', 'GND', desc='FB bottom, 1%')
d.R('R', '56k', 'POE_OUTPUT', 'BST_UVLO', desc='UVLO top: on at 9.9 V, 1%')
d.R('R', '10k', 'BST_UVLO', 'GND', desc='UVLO bottom, 1%')
d.C('C', '47n', 'BST_SS', 'GND', desc='soft start about 3.6 ms')
d.R('R', '15.8k', 'BST_COMP', 'BST_COMPZ', desc='RCOMP, 1%')
d.C('C', '10n', 'BST_COMPZ', 'GND', desc='CCOMP')
d.C('C', '330p', 'BST_COMP', 'GND', desc='CHF, C0G')
d.D('D', 'SMBJ58A', 'GND', 'POE_52V', 'Diode_SMD:D_SMB', kind='TVS', mpn='SMBJ58A', mfr='Littelfuse',
    desc='52 V system TVS: 58 V standoff, 93.6 V clamp')
# PSE
d.chip('U', TPS23861, {'VDD': '+3V3', 'VPWR': 'POE_52V', 'RESET': 'PSE_RESET_N', 'SCL': 'I2C1_SCL', 'SDAI': 'I2C1_SDA',
                       'SDAO': 'I2C1_SDA', 'INT': 'PSE_INT_N', 'A3': None, 'SHTDWN': None, 'AIN': None, 'AOUT': None,
                       'N/C': None, 'GATE1': 'PSE_G1', 'DRAIN1': 'PSE_D1', 'SEN1': 'PSE_S1', 'KSENSA': 'GND',
                       'GATE2': None, 'DRAIN2': 'GND', 'SEN2': 'GND', 'GATE3': None, 'DRAIN3': 'GND', 'SEN3': 'GND',
                       'KSENSB': 'GND', 'GATE4': None, 'DRAIN4': 'GND', 'SEN4': 'GND', 'DGND': 'GND', 'AGND': 'GND'})
d.C('C', '100n 50V', '+3V3', 'GND', desc='TPS23861 VDD (50 V X7R per datasheet)')
d.C('C', '100n 100V', 'POE_52V', 'GND', size='0805', mpn='GRM21BR72A104KAC4L', mfr=MUR, desc='TPS23861 VPWR, at pin 28')
d.C('C', '10n', 'PSE_RESET_N', 'GND', desc='RESET filter')
d.R('R', '10k', '+3V3', 'PSE_INT_N', desc='INT pull-up (open drain, read by the I/O expander)')
d.chip('Q', NFET_100V, {'G': 'PSE_G1', 'D': 'POE_PAIR_36', 'S': 'PSE_RS1'}, desc='port 1 switch (low side)')
for i in range(2):
    d.R('R', '0.51', 'PSE_RS1', 'GND', size='0805', desc='port 1 sense, two in parallel = 0.255 Ohm, 1% 0.25 W')
d.R('R', '22.1', 'PSE_RS1', 'PSE_S1', size='0603', desc='RSEN1, 1%')
d.R('R', '47', 'POE_PAIR_36', 'PSE_D1', size='0603', desc='RDRN1, 5%')
d.C('C', '100n 100V', 'POE_52V', 'POE_PAIR_36', size='0805', mpn='GRM21BR72A104KAC4L', mfr=MUR, desc='CP1, port bypass')
d.D('D', 'SMBJ58A', 'POE_PAIR_36', 'POE_52V', 'Diode_SMD:D_SMB', kind='TVS', mpn='SMBJ58A', mfr='Littelfuse',
    desc='DP1A port TVS')
d.R('R', '0', 'POE_52V', 'POE_PAIR_12', size='1206', desc='port 1 positive to the 1-2 centre tap (fuse site, 0R fitted)')
d.R('R', '75', 'POE_PAIR_78', 'BS_CAM', size='0603', desc='Bob Smith, camera jack pair 4-5')
d.R('R', '75', 'POE_PAIR_910', 'BS_CAM', size='0603', desc='Bob Smith, camera jack pair 7-8')
d.C('C', '1n 2kV', 'BS_CAM', 'GND', size='1206', mpn='GRM31BR73D102KW01L', mfr=MUR, desc='Bob Smith, 2 kV')

# =============================================================================== D. lidar Ethernet
d.block('BD_LAN', 'Lidar Ethernet: LAN7800 on Jetson USB2, second RJ45', [
    'The SICK TiM561 talks 100BASE-TX. The LAN7800 hangs off the module USB2 pair (the Antmicro USB-C/DP port',
    'that the car does not use). Driver: lan78xx, in the stock L4T kernel.',
    'No EEPROM: the driver sets the MAC address. VBUS_DET tied to 3.3 V (always attached). TEST to GND.',
    'Internal 1.2 V switcher: 3.3 uH + 10 uF. Internal 2.5 V LDO feeds the PHY. Voltage-mode PHY: the jack PHY-side',
    'centre taps only get the 10 nF cap. Cable-side centre taps: Bob Smith (75 Ohm, 1 nF 2 kV).',
    'Crystal 25 MHz, 18 pF load: 27 pF caps (2 x (18 - 4.5 pF stray)).',
])
d.chip('U', LAN7800, {
    'VDD_SW_IN': '+3V3', 'VDD33_REG_IN': '+3V3', 'VDD33A': '+3V3', 'VDDVARIO': '+3V3', 'VDD25_REG_OUT': 'LAN_2V5',
    'VDD25A': 'LAN_2V5', 'VDD12_SW_OUT': 'LAN_SW', 'VDD12_SW_FB': 'LAN_1V2', 'VDD12CORE': 'LAN_1V2', 'VDD12A': 'LAN_1V2',
    'USB2_DP': 'USB2_D_P', 'USB2_DM': 'USB2_D_N', 'USB3_TXDP': None, 'USB3_TXDM': None, 'USB3_RXDP': None,
    'USB3_RXDM': None, 'USBRBIAS': 'LAN_RBIAS', 'VBUS_DET': '+3V3', 'RESET_N': 'LAN_RST_N', 'TEST': 'GND',
    'XI': 'LAN_XI', 'XO': 'LAN_XO', 'PME_MODE': 'LAN_PME_MODE', 'PME_N': None, 'SUSPEND_N': None, 'EECS': None,
    'EEDI': 'LAN_EEDI', 'EEDO/LED0': 'LAN_LED0', 'EECLK/LED1': 'LAN_LED1', 'LED3': None,
    'TR0P': 'LAN_TR0P', 'TR0N': 'LAN_TR0N', 'TR1P': 'LAN_TR1P', 'TR1N': 'LAN_TR1N', 'TR2P': 'LAN_TR2P',
    'TR2N': 'LAN_TR2N', 'TR3P': 'LAN_TR3P', 'TR3N': 'LAN_TR3N', 'REF_REXT': 'LAN_REXT', 'REF_FILT': 'LAN_RFILT',
    'VSS': 'GND'})
d.L('L', '3.3u', 'LAN_SW', 'LAN_1V2', 'Inductor_SMD:L_1008_2520Metric', mpn='LQM2HPN3R3MG0L', mfr=MUR,
    desc='1.2 V switcher inductor, 1.2 A, 0.125 Ohm')
d.C('C', '10u 10V', 'LAN_1V2', 'GND', size='0603', desc='1.2 V switcher output')
for i in range(5):
    d.C('C', '100n', 'LAN_1V2', 'GND', desc='VDD12 pins 21, 25, 30, 42, 44')
d.C('C', '1u', 'LAN_2V5', 'GND', desc='2.5 V LDO output')
for i in range(4):
    d.C('C', '100n', 'LAN_2V5', 'GND', desc='VDD25A pins 3, 6, 9, 12')
d.C('C', '10u 10V', '+3V3', 'GND', size='0603', desc='LAN7800 3.3 V bulk')
for i in range(5):
    d.C('C', '100n', '+3V3', 'GND', desc='3.3 V pins 14, 20, 36, 38, 39, 46')
d.R('R', '12.0k', 'LAN_RBIAS', 'GND', desc='USBRBIAS, 1%')
d.R('R', '2.00k', 'LAN_REXT', 'GND', desc='PHY reference, 1%')
d.C('C', '1u', 'LAN_RFILT', 'GND', desc='PHY reference filter')
d.R('R', '10k', '+3V3', 'LAN_RST_N', desc='reset pull-up')
d.C('C', '100n', 'LAN_RST_N', 'GND', desc='power-on reset delay')
d.R('R', '10k', 'LAN_PME_MODE', 'GND', desc='PME mode input, unused')
d.R('R', '10k', 'LAN_EEDI', 'GND', desc='no EEPROM: EEDI reads 0')
d.stock('Y', 'Device:Crystal_GND24', '25MHz', 'Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm',
        {'1': 'LAN_XI', '3': 'LAN_XO', '2': 'GND', '4': 'GND'}, mpn='ABM8-25.000MHZ-B2-T', mfr='Abracon',
        desc='25 MHz crystal, 18 pF, 20 ppm')
d.C('C', '27p', 'LAN_XI', 'GND', desc='crystal load, C0G')
d.C('C', '27p', 'LAN_XO', 'GND', desc='crystal load, C0G')
d.chip('J', RJ45_MAG, {'P1': 'LAN_TR0P', 'P2': 'LAN_TR0N', 'P3': 'LAN_TR1P', 'P6': 'LAN_TR1N', 'P7': 'LAN_TR2P',
                       'P8': 'LAN_TR2N', 'P9': 'LAN_TR3P', 'P10': 'LAN_TR3N', 'P4': 'LAN_CT', 'P5': 'LAN_CT',
                       'VC1': 'LAN_VC1', 'VC2': 'LAN_VC2', 'VC3': 'LAN_VC3', 'VC4': 'LAN_VC4',
                       'LED_GRN+': '+3V3', 'LED_GRN-': 'LAN_LEDG', 'LED_YEL+': '+3V3', 'LED_YEL-': 'LAN_LEDY',
                       'SHIELD': 'LAN_SHLD'}, value='LIDAR')
d.C('C', '10n', 'LAN_CT', 'GND', size='0603', desc='PHY-side centre taps (as on the camera jack)')
for i in range(1, 5):
    d.R('R', '75', f'LAN_VC{i}', 'BS_LID', size='0603', desc='Bob Smith termination')
d.C('C', '1n 2kV', 'BS_LID', 'GND', size='1206', mpn='GRM31BR73D102KW01L', mfr=MUR, desc='Bob Smith, 2 kV')
d.R('R', '200', 'LAN_LEDG', 'LAN_LED0', desc='link LED')
d.R('R', '200', 'LAN_LEDY', 'LAN_LED1', desc='activity LED')
d.R('R', '200', 'LAN_SHLD', 'GND', desc='shield to ground (as on the camera jack)')
d.C('C', '100n', 'LAN_SHLD', 'GND', desc='shield to ground')

if __name__ == '__main__':
    print(len(d.parts), 'parts', len(d.nets()), 'nets')
    for net, nodes in d.check():
        print('single-pin net', net, nodes)
