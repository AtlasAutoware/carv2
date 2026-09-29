"""ATLAS-DRV-1, the drive board: battery protection, main switch, USB-C charging, ESC, servo
and lidar supplies, USB debug hub, and the socket for the brain board.

Single source of truth for the schematic and the PCB. Run tools/build.py drive.
Values carry a short reason where the datasheet asks for a design choice.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
sys.path.insert(0, os.path.join(HERE, '..', 'stack'))
from eda import Design, P_IN, PAS  # noqa: E402
from chips import *  # noqa: E402,F401,F403
import stack  # noqa: E402

d = Design('atlas_drive', 'ATLAS-DRV-1 drive board', rev='0.1')
TI = 'Texas Instruments'
MUR_10U50 = 'GRM32ER71H106KA12L'      # 10 uF 50 V X7R 1210 (TPSM63610 datasheet table 7-2)

# =============================================================================== A. pack
d.block('A_PACK', 'Pack connection', [
    'Pack power leads: 10 AWG soldered into B+ and B- (SolderWire 6 mm2 pads).',
    'Sense lead: 7-pin JST-XH side entry. B0 is the bottom of cell 1, B4 the top of cell 4.',
    'B- is the cell stack bottom (BATN). Board ground (GND) is PACK-, after the BMS FETs.',
])
PAD6 = 'Connector_Wire:SolderWire-6sqmm_1x01_D3.5mm_OD7mm'
d.chip('J', conn('PAD_BAT+', 1, PAD6, desc='pack + lead, 10 AWG'), {'1': 'BATP'}, value='B+', in_bom='no')
d.chip('J', conn('PAD_BAT-', 1, PAD6, desc='pack - lead, 10 AWG'), {'1': 'BATN'}, value='B-', in_bom='no')
d.chip('J', conn('PACK_SENSE', 7, 'Connector_JST:JST_XH_S7B-XH-A_1x07_P2.50mm_Horizontal', mpn='S7B-XH-A(LF)(SN)',
                  mfr='JST', desc='pack sense lead: B0..B4, NTC, NTC return',
                  names=['B0', 'B1', 'B2', 'B3', 'B4', 'NTC', 'NTC_RTN']),
       {'B0': 'CELL0', 'B1': 'CELL1', 'B2': 'CELL2', 'B3': 'CELL3', 'B4': 'CELL4', 'NTC': 'BMS_TS', 'NTC_RTN': 'BATN'})
d.D('D', 'SMBJ20A', 'BATN', 'BATP', 'Diode_SMD:D_SMB', kind='Z', mpn='SMBJ20A', mfr='Littelfuse',
    desc='TVS across the pack terminals, 20 V standoff, 32.4 V clamp')

# =============================================================================== B. BMS
d.block('B_BMS', 'Battery protection: BQ7791508, 4S, low-side FETs', [
    'BQ7791508: OV 4.20 V, UV 3.00 V, OCD1 70 mV / 1.4 s, OCD2 140 mV / 0.7 s, SCD 300 mV / 0.4 ms, OCC 60 mV.',
    'Sense 0.5 mOhm: OCD1 140 A, OCD2 280 A, SCD 600 A, OCC 120 A. VESC input limit (90 A) stays under OCD1.',
    '4S: CCFG to AVDD; VC5 shorted to VC4 at the pins (datasheet 11). Internal balancing: 33 Ohm / 1 uF per input (RINI, CINI).',
    'DSG FETs source on the shunt side, CHG FETs source on PACK- (GND), drains common (FET_MID).',
    'CTRC/CTRD tied to VSS = drivers always enabled. PRES held high through a divider (recommended max 16 V).',
])
U = d.chip('U', BQ77915, {'VDD': 'BMS_VDD', 'AVDD': 'BMS_AVDD', 'VC5': 'BMS_VC4', 'VC4': 'BMS_VC4', 'VC3': 'BMS_VC3',
                           'VC2': 'BMS_VC2', 'VC1': 'BMS_VC1', 'VC0': 'BMS_VC0', 'SRP': 'BMS_SRP', 'SRN': 'BMS_SRN',
                           'TS': 'BMS_TS', 'VTB': 'BMS_VTB', 'DSG': 'BMS_DSG', 'CHG': 'BMS_CHG', 'LD': 'BMS_LD',
                           'LPWR': None, 'CBI': 'BATN', 'OCDP': 'BMS_OCDP', 'CCFG': 'BMS_AVDD', 'CBO': None,
                           'PRES': 'BMS_PRES', 'CTRC': 'BATN', 'CTRD': 'BATN', 'VSS': 'BATN'})
for i in range(5):
    d.R('R', '33', f'CELL{i}', f'BMS_VC{i}', size='0805', desc='cell input filter, 33 Ohm 0805 (balancing current ~50 mA)')
for i in range(1, 5):
    d.C('C', '1u 16V', f'BMS_VC{i}', f'BMS_VC{i - 1}', size='0603', desc='cell input filter 1 uF X7R')
d.R('R', '1k', 'CELL4', 'BMS_VDD', desc='VDD filter (RVDD)')
d.C('C', '1u 25V', 'BMS_VDD', 'BATN', size='0603', desc='VDD filter (CVDD)')
d.C('C', '1u 6.3V', 'BMS_AVDD', 'BATN', desc='AVDD')
d.R('R', '10k', 'BMS_VTB', 'BMS_TS', desc='thermistor pull-up to VTB, 1%')
d.R('R', '750k', 'BMS_OCDP', 'BATN', desc='OCDP: OCD1 1.42 s / OCD2 0.70 s (table 9-3)')
d.R('R', '470k', 'BMS_LD', 'GND', desc='load removal detect')
d.R('R', '470k', 'CELL4', 'BMS_PRES', desc='PRES divider top: 11.4 V at 16.8 V')
d.R('R', '1M', 'BMS_PRES', 'BATN', desc='PRES divider bottom')
d.R('R', '100', 'BMS_KS1', 'BMS_SRP', desc='sense filter RS')
d.R('R', '100', 'BMS_KS2', 'BMS_SRN', desc='sense filter RS')
d.C('C', '100n', 'BMS_SRP', 'BMS_SRN', desc='sense filter CS')
d.chip('R', SHUNT4, {'I1': 'BATN', 'I2': 'BMS_RSN', 'S1': 'BMS_KS1', 'S2': 'BMS_KS2'}, value='0.5m',
       mpn='BVR-Z-R0005-1.0', mfr='Isabellenhuette', desc='BMS sense 0.5 mOhm 4-terminal 4026')
d.R('R', '4.53k', 'BMS_DSG', 'DSG_G', desc='DSG gate resistor (RDSG)')
d.R('R', '1M', 'DSG_G', 'BMS_RSN', desc='DSG gate-source (RGS_DSG)')
d.R('R', '1k', 'BMS_CHG', 'CHG_G', desc='CHG gate resistor (RCHG)')
d.R('R', '1M', 'CHG_G', 'GND', desc='CHG gate-source (RGS_CHG)')
for i in range(4):
    d.chip('Q', NFET_Q5B, {'G': 'DSG_G', 'D': 'FET_MID', 'S': 'BMS_RSN'}, desc='BMS discharge FET')
    d.chip('Q', NFET_Q5B, {'G': 'CHG_G', 'D': 'FET_MID', 'S': 'GND'}, desc='BMS charge FET')

# =============================================================================== C. main switch
d.block('C_SWITCH', 'Main switch: TPS48111 + 4 FETs, MCU-sequenced precharge', [
    'EN from the power latch. The MCU turns on INP_G (precharge through 10 Ohm), checks VM, then INP (main FETs).',
    'RSNS 0.2 mOhm. SCP: RISCP 4.02k -> 350 A in 1.2 us. OCP: RIWRN 39.2k, RSET 100 -> 150 A for 10 ms (CTMR 680 nF).',
    'IMON: gain 0.9 x 5.1k / 100 = 46 -> 150 A reads 1.38 V on PA5. Auto-retry after 15 s.',
    'CBST 2.2 uF (4 x 118 nC gate charge). Remote temperature: MMBT3904 at the FETs on DIODE.',
])
d.chip('U', TPS48111, {'VS': 'BATP', 'CS+': 'SW_CSP', 'CS-': 'SW_KS2', 'ISCP': 'SW_ISCP', 'EN/UVLO': 'SW_EN',
                        'INP_G': 'SW_INPG', 'INP': 'SW_INP', 'FLT_T': 'SW_FLT_N', 'FLT_I': 'SW_FLT_N', 'IMON': 'SW_IMON',
                        'IWRN': 'SW_IWRN', 'TMR': 'SW_TMR', 'DIODE': 'SW_DIODE', 'BST': 'SW_BST', 'PU': 'SW_GATE',
                        'PD': 'SW_GATE', 'SRC': 'VM', 'G': 'PRE_G0', 'GND': 'GND'})
d.chip('R', SHUNT4, {'I1': 'BATP', 'I2': 'SW_IN', 'S1': 'SW_KS1', 'S2': 'SW_KS2'}, value='0.2m',
       mpn='BVR-Z-R0002-1.0', mfr='Isabellenhuette', desc='main switch sense 0.2 mOhm 4-terminal 4026')
d.R('R', '100', 'SW_KS1', 'SW_CSP', desc='RSET 100 Ohm 1%')
d.R('R', '4.02k', 'SW_KS1', 'SW_ISCP', desc='RISCP: short circuit 350 A (eq. 11)')
d.R('R', '39.2k', 'SW_IWRN', 'GND', desc='RIWRN: overcurrent 150 A (eq. 6)')
d.C('C', '680n', 'SW_TMR', 'GND', desc='CTMR: 10 ms overcurrent delay, 15 s retry')
d.R('R', '5.1k', 'SW_IMON', 'GND', desc='RIMON: 46 V/V')
d.C('C', '2.2u 25V', 'SW_BST', 'VM', size='0805', desc='bootstrap cap BST-SRC')
d.R('R', '10k', 'LATCH_Q', 'SW_EN', desc='EN from the latch')
d.R('R', '100k', 'SW_EN', 'GND', desc='EN pull-down')
d.R('R', '100k', 'SW_INP', 'GND', desc='INP off by default')
d.R('R', '100k', 'SW_INPG', 'GND', desc='INP_G off by default')
d.R('R', '1k', 'MAIN_ON', 'SW_INP', desc='from PA6')
d.R('R', '1k', 'PRECHG_ON', 'SW_INPG', desc='from PA7')
d.C('C', '100n 50V', 'BATP', 'GND', desc='VS decoupling')
d.chip('Q', NPN_SOT23, {'B': 'SW_DIODE', 'C': 'SW_DIODE', 'E': 'GND'}, desc='remote temperature diode at the main FETs')
d.R('R', '1k', 'SW_IMON', 'IMON_MCU', desc='IMON to PA5; limits clamp current')
d.C('C', '100n', 'IMON_MCU', 'GND', desc='IMON filter')
d.R('R', '1k', '+3V3', 'SW_FLT_LED', desc='fault LED')
d.LED('D', 'RED', 'SW_FLT_LED', 'SW_FLT_N')
for i in range(4):
    d.R('R', '2.2', 'SW_GATE', f'SW_G{i}', desc='gate resistor per FET (current sharing)')
    d.chip('Q', NFET_Q5B, {'G': f'SW_G{i}', 'D': 'SW_IN', 'S': 'VM'}, desc='main switch FET')
d.R('R', '470', 'PRE_G0', 'PRE_G', desc='precharge gate Rg (datasheet 220-470 Ohm)')
d.chip('Q', NFET_Q5B, {'G': 'PRE_G', 'D': 'PRE_D', 'S': 'VM'}, desc='precharge FET')
for _ in range(2):
    d.R('R', '22', 'SW_IN', 'PRE_D', size='2512', mpn='CRCW251222R0FKEGHP', mfr='Vishay',
        desc='precharge resistor, 2 x 22 Ohm pulse-proof 2512 in parallel (11 Ohm, tau 16 ms): each takes 0.15 J per '
             'switch-on, under its single-pulse rating (sim/precharge.py; one 10 Ohm 2512 was over it)')
d.D('D', 'SMCJ20A', 'GND', 'VM', 'Diode_SMD:D_SMC', kind='Z', mpn='SMCJ20A', mfr='Littelfuse',
    desc='motor bus TVS 1500 W: regen with the BMS open')

# =============================================================================== D. power latch and logic supplies
d.block('D_POWER', 'Power button latch and logic supplies', [
    'TPS70933 makes 3V3_AON from B+ (1 uA). SN74LVC1G74 is the on/off latch: button -> PRE, MCU KILL -> CLR.',
    'A reset or crash of the MCU does not turn the car off; only KILL (PB12 high) or pulling the pack does.',
    'LATCH_Q enables the TPS48111 and the DRV8323R buck (nSHDN). Buck: VIN from B+, 5.0 V (54.9k / 10k, 0.765 V FB).',
    'TLV75533P makes +3V3 from +5V. The button also pulls the charger QON low (exits ship mode).',
])
d.chip('U', TPS709, {'IN': 'BATP', 'EN': 'BATP', 'OUT': '3V3_AON', 'NC': None, 'GND': 'GND'})
d.C('C', '1u 50V', 'BATP', 'GND', size='0603', desc='LDO input')
d.C('C', '2.2u', '3V3_AON', 'GND', size='0603', desc='LDO output')
d.chip('U', LVC1G74, {'VCC': '3V3_AON', 'CLK': 'GND', 'D': 'GND', '~{PRE}': 'BTN_N', '~{CLR}': 'LATCH_CLR_N',
                       'Q': 'LATCH_Q', '~{Q}': None, 'GND': 'GND'})
d.C('C', '100n', '3V3_AON', 'GND', desc='latch decoupling')
d.R('R', '100k', '3V3_AON', 'BTN_N', desc='button pull-up')
d.C('C', '10n', 'BTN_N', 'GND', desc='button debounce')
d.R('R', '100k', '3V3_AON', 'LATCH_CLR_N', desc='CLR pull-up')
d.C('C', '1u', 'LATCH_CLR_N', 'GND', size='0603', desc='power-on clear: latch starts off when the pack is connected')
d.chip('Q', NMOS_SOT23, {'G': 'KILL_G', 'D': 'LATCH_CLR_N', 'S': 'GND'}, desc='MCU kill: clears the latch')
d.R('R', '1k', 'KILL', 'KILL_G', desc='from PB12')
d.R('R', '100k', 'KILL_G', 'GND', desc='kill off while the MCU is in reset')
d.stock('SW', 'Switch:SW_Push', 'POWER', 'Button_Switch_SMD:SW_Push_1P1T_NO_CK_KMR2', {'1': 'BTN_N', '2': 'GND'},
        mpn='KMR211NG LFS', mfr='C&K', desc='on-board power button')
d.chip('J', conn('BTN_EXT', 2, 'Connector_JST:JST_PH_S2B-PH-K_1x02_P2.00mm_Horizontal', mpn='S2B-PH-K-S(LF)(SN)', mfr='JST',
                  desc='remote power button (parallel to SW1)'), {'1': 'BTN_N', '2': 'GND'})
d.chip('U', LVC1G34, {'VCC': '+3V3', 'A': 'BTN_N', 'Y': 'BTN_SENSE', 'GND': 'GND', 'NC': None})
d.C('C', '100n', '+3V3', 'GND', desc='button buffer decoupling')
d.D('D', 'BAT54WS', 'CHG_QON_N', 'BTN_N', 'Diode_SMD:D_SOD-323', kind='S', mpn='BAT54WS', mfr='Nexperia',
    desc='button also pulls charger QON low (ship-mode exit)')
d.R('R', '10k', 'LATCH_Q', 'BUCK_EN', desc='buck enable from the latch')
# DRV8323R buck part (pins on U30 in the ESC sheet): VIN, nSHDN, SW, CB, FB
d.R('R', '10', 'BATP', 'BUCK_VIN', size='0603', desc='buck input filter')
d.C('C', '4.7u 50V', 'BUCK_VIN', 'GND', size='1206', desc='buck input (CVIN)')
d.C('C', '100n 50V', 'BUCK_VIN', 'GND', desc='buck input HF')
d.C('C', '100n 16V', 'BUCK_CB', 'BUCK_SW', desc='buck bootstrap (CBOOT)')
d.D('D', 'PMEG6010CEH', 'GND', 'BUCK_SW', 'Diode_SMD:D_SOD-123F', kind='S', mpn='PMEG6010CEH', mfr='Nexperia',
    desc='buck catch diode 60 V 1 A (DSW)')
d.L('L', '22u', 'BUCK_SW', '+5V', 'Inductor_SMD:L_Bourns-SRN4018', mpn='SRN4018-220M', mfr='Bourns',
    desc='buck inductor 22 uH (0.7 MHz, 16.8 V -> 5 V, 0.35 A)')
d.C('C', '22u 10V', '+5V', 'GND', size='0805', desc='buck output')
d.C('C', '22u 10V', '+5V', 'GND', size='0805', desc='buck output')
d.R('R', '54.9k', '+5V', 'BUCK_FB', desc='FB top: 0.765 x (1 + 54.9/10) = 4.96 V')
d.R('R', '10k', 'BUCK_FB', 'GND', desc='FB bottom')
d.chip('U', TLV755, {'IN': '+5V', 'EN': '+5V', 'OUT': '+3V3', 'NC': None, 'GND': 'GND'})
d.C('C', '1u', '+5V', 'GND', size='0603', desc='LDO in')
d.C('C', '10u 10V', '+3V3', 'GND', size='0805', desc='LDO out / 3.3 V bulk')
d.R('R', '1k', '+3V3', 'PWR_LED', desc='power LED')
d.LED('D', 'GREEN', 'PWR_LED', 'GND')

# =============================================================================== E. ESC
d.block('E_ESC', 'ESC power stage: DRV8323RS + 12 x CSD18510Q5B + 3 shunts', [
    'VESC-6 class, Trampa HD60 pin map (firmware/vesc/hw_atlas_drv1). 6x PWM from TIM1: PA8-10 high, PB13-15 low.',
    'Two FETs per switch, 2.2 Ohm gate resistor each. Shunts 0.2 mOhm, CSA gain 40 V/V: +-206 A.',
    'Phase and bus sense 39k / 2.2k (as VESC). PC13 switches 10 nF phase filters in (HW_HAS_PHASE_FILTERS).',
    'DC link: 4 x 330 uF 35 V hybrid polymer (12.8 mm tall: clears the brain board NVMe) + 12 x 10 uF 1210 ceramics.',
    'E-stop: DRV ENABLE = PB5 AND the E-stop loop (74LVC1G08), so an open loop stops the gates with no firmware.',
])
d.chip('U', DRV8323RS, {
    'VM': 'VM', 'VDRAIN': 'VM', 'VCP': 'DRV_VCP', 'CPH': 'DRV_CPH', 'CPL': 'DRV_CPL', 'DVDD': 'DRV_DVDD', 'VREF': '+3V3',
    'INHA': 'PWM_AH', 'INLA': 'PWM_AL', 'INHB': 'PWM_BH', 'INLB': 'PWM_BL', 'INHC': 'PWM_CH', 'INLC': 'PWM_CL',
    'ENABLE': 'DRV_EN', 'CAL': 'DRV_CAL', 'nSCS': 'DRV_CS_N', 'SCLK': 'DRV_SCK', 'SDI': 'DRV_MOSI', 'SDO': 'DRV_MISO',
    'nFAULT': 'DRV_FAULT_N', 'SOA': 'CSA_A', 'SOB': 'CSA_B', 'SOC': 'CSA_C',
    'VIN': 'BUCK_VIN', 'nSHDN': 'BUCK_EN', 'CB': 'BUCK_CB', 'SW': 'BUCK_SW', 'FB': 'BUCK_FB',
    'GHA': 'GHA', 'SHA': 'PHA', 'GLA': 'GLA', 'SPA': 'SPA', 'SNA': 'SNA',
    'GHB': 'GHB', 'SHB': 'PHB', 'GLB': 'GLB', 'SPB': 'SPB', 'SNB': 'SNB',
    'GHC': 'GHC', 'SHC': 'PHC', 'GLC': 'GLC', 'SPC': 'SPC', 'SNC': 'SNC', 'NC': None, 'GND': 'GND'})
d.C('C', '100n 50V', 'VM', 'GND', desc='CVM1')
d.C('C', '10u 50V', 'VM', 'GND', size='1210', mpn=MUR_10U50, desc='CVM2')
d.C('C', '1u 25V', 'DRV_VCP', 'VM', size='0603', desc='CVCP')
d.C('C', '47n 50V', 'DRV_CPH', 'DRV_CPL', size='0603', desc='CSW charge pump flying cap')
d.C('C', '1u 6.3V', 'DRV_DVDD', 'GND', desc='CDVDD')
d.C('C', '100n', '+3V3', 'GND', desc='CVREF')
d.R('R', '10k', '+3V3', 'DRV_FAULT_N', desc='nFAULT pull-up')
d.R('R', '10k', '+3V3', 'DRV_MISO', desc='SDO pull-up')
d.R('R', '10k', '+3V3', 'DRV_CS_N', desc='nSCS idle high during MCU reset')
d.R('R', '100k', 'DRV_EN', 'GND', desc='gate drive off by default')
for k, ph in enumerate('ABC'):
    n = 54 + k * 12
    # current sense output filters to the ADC
    d.R('R', '100', f'CSA_{ph}', f'CURR_{ph}', desc='CSA output filter')
    d.C('C', '1n', f'CURR_{ph}', 'GND', desc='CSA output filter')
    # phase voltage divider and switched filter
    d.R('R', '39k', f'PH{ph}', f'SENS_{ph}', desc='phase sense divider top (VESC 39k / 2.2k)')
    d.R('R', '2.2k', f'SENS_{ph}', 'GND', desc='phase sense divider bottom')
    d.C('C', '10n', f'SENS_{ph}', f'PHF_{ph}', desc='phase filter cap, switched by PC13')
    d.chip('Q', NMOS_SOT23, {'G': 'PHASE_FILT', 'D': f'PHF_{ph}', 'S': 'GND'}, desc='phase filter switch')
    # gate resistors and FETs, two per switch
    for j in range(2):
        d.R('R', '2.2', f'GH{ph}', f'GH{ph}{j}', desc='high-side gate resistor')
        d.R('R', '2.2', f'GL{ph}', f'GL{ph}{j}', desc='low-side gate resistor')
        d.chip('Q', NFET_Q5B, {'G': f'GH{ph}{j}', 'D': 'VM', 'S': f'PH{ph}'}, side='B',
               desc=f'phase {ph} high-side FET')
        d.chip('Q', NFET_Q5B, {'G': f'GL{ph}{j}', 'D': f'PH{ph}', 'S': f'PH{ph}_LS'}, side='B',
               desc=f'phase {ph} low-side FET')
    d.chip('R', SHUNT4, {'I1': f'PH{ph}_LS', 'I2': 'GND', 'S1': f'SP{ph}', 'S2': f'SN{ph}'}, value='0.2m', side='B',
           mpn='BVR-Z-R0002-1.0', mfr='Isabellenhuette', desc=f'phase {ph} low-side shunt 0.2 mOhm')
    for j in range(4):
        d.C('C', '10u 50V', 'VM', 'GND', size='1210', mpn=MUR_10U50, desc='DC link ceramic at the half-bridge')
    PADM = 'atlas:WirePad_SMD_9x7mm_10Vias'
    d.chip('J', conn(f'PAD_MOTOR_{ph}', 1, PADM, desc=f'motor phase {ph}, 12 AWG pigtail'), {'1': f'PH{ph}'},
           value=f'MOTOR {ph}', in_bom='no')
for i in range(4):
    d.CP('C', '330u 35V', 'VM', 'GND', 'Capacitor_SMD:CP_Elec_10x10', mpn='EEH-ZU1V331P', mfr='Panasonic',
         desc='DC link bulk, hybrid polymer 330 uF 35 V, 10 x 12.8 mm, 11 mOhm, 4.8 A rms (100 kHz, 125 C)')
d.R('R', '39k', 'VM', 'VIN_SENSE', desc='bus voltage divider (VIN_R1)')
d.R('R', '2.2k', 'VIN_SENSE', 'GND', desc='bus voltage divider (VIN_R2)')
d.C('C', '10n', 'VIN_SENSE', 'GND', desc='bus sense filter')
d.stock('TH', 'Device:Thermistor_NTC', '10k B3380', 'Resistor_SMD:R_0402_1005Metric', {'1': '+3V3', '2': 'TEMP_PCB'}, side='B',
        mpn='NCP15XH103F03RC', mfr='Murata', desc='FET temperature, 10k B25/50 3380 (VESC NTC_TEMP)')
d.R('R', '10k', 'TEMP_PCB', 'GND', desc='NTC divider')
d.C('C', '100n', 'TEMP_PCB', 'GND', desc='NTC filter')
# E-stop
d.chip('U', LVC1G08, {'VCC': '+3V3', 'A': 'GATE_EN_MCU', 'B': 'ESTOP_OK', 'Y': 'DRV_EN', 'GND': 'GND'})
d.C('C', '100n', '+3V3', 'GND', desc='AND gate decoupling')
d.chip('J', conn('ESTOP', 2, 'Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical', mpn='B2B-PH-K-S(LF)(SN)', mfr='JST',
                   desc='E-stop loop, normally closed'), {'1': 'ESTOP_SRC', '2': 'ESTOP_IN'})
d.R('R', '1k', '+3V3', 'ESTOP_SRC', desc='loop source current limit')
d.R('R', '100', 'ESTOP_IN', 'ESTOP_OK', desc='loop filter')
d.R('R', '10k', 'ESTOP_OK', 'GND', desc='open loop reads low = stop')
d.C('C', '100n', 'ESTOP_OK', 'GND', desc='loop filter')
d.D('D', 'PESD5V0S1BA', 'GND', 'ESTOP_IN', 'Diode_SMD:D_SOD-323', kind='TVS', mpn='PESD5V0S1BA', mfr='Nexperia',
    desc='ESD on the external loop')

# =============================================================================== F. MCU
d.block('F_MCU', 'STM32F405 running VESC firmware, IMU, CAN, hall sensors, servo signal', [
    'Pin map = Trampa HD60 (hw_hd60) except: IMU SDA moved PB2 -> PC11 so BOOT1 stays low for the ROM bootloader,',
    'power hold replaced by KILL on PB12 (latch), and new I/O: PA4 brain power, PA5 IMON, PA6 MAIN_ON, PA7 PRECHG_ON,',
    'PC10 E-stop sense, PC14 power-button request to the Jetson, PC15 Jetson halted. See firmware/vesc/hw_atlas_drv1.h.',
    'USART3 (PB10/PB11) to the Jetson at 115200 like car 1. USB to hub port 2 for VESC Tool. SWD on a 1.27 mm 2x5.',
    'Hall lead order assumed ROAR standard: GND, TEMP, C, B, A, +5V (confirm on the motor, MEASURE_FIRST #11).',
])
d.chip('U', STM32F405, {
    'VBAT': '+3V3', 'VDD': '+3V3', 'VDDA': 'VDDA', 'VCAP_1': 'VCAP1', 'VCAP_2': 'VCAP2', 'VSS': 'GND', 'VSSA': 'GND',
    'NRST': 'STK_MCU_NRST', 'BOOT0': 'STK_MCU_BOOT0', 'PH0-OSC_IN': 'OSC_IN', 'PH1-OSC_OUT': 'OSC_OUT',
    'PA0': 'SENS_A', 'PA1': 'SENS_B', 'PA2': 'SENS_C', 'PA3': 'TEMP_PCB', 'PA4': 'MCU_POWER_EN', 'PA5': 'IMON_MCU',
    'PA6': 'MAIN_ON', 'PA7': 'PRECHG_ON', 'PA8': 'PWM_AH', 'PA9': 'PWM_BH', 'PA10': 'PWM_CH', 'PA11': 'USB_MCU_DN',
    'PA12': 'USB_MCU_DP', 'PA13': 'SWDIO', 'PA14': 'SWCLK', 'PA15': 'IMU_SCL',
    'PC0': 'CURR_A', 'PC1': 'CURR_B', 'PC2': 'CURR_C', 'PC3': 'VIN_SENSE', 'PC4': 'TEMP_MOTOR', 'PC5': 'BTN_SENSE',
    'PC6': 'HALL1', 'PC7': 'HALL2', 'PC8': 'HALL3', 'PC9': 'DRV_CS_N', 'PC10': 'ESTOP_OK', 'PC11': 'IMU_SDA',
    'PC12': 'DRV_MOSI', 'PC13': 'PHASE_FILT', 'PC14': 'MCU_PWR_BTN_N', 'PC15': 'STK_OS_HALTED', 'PD2': 'DRV_CAL',
    'PB0': 'LED_G', 'PB1': 'LED_R', 'PB2': 'BOOT1', 'PB3': 'DRV_MISO', 'PB4': 'DRV_SCK', 'PB5': 'GATE_EN_MCU',
    'PB6': 'SERVO_PWM', 'PB7': 'DRV_FAULT_N', 'PB8': 'CAN_RX', 'PB9': 'CAN_TX', 'PB10': 'VESC_TX', 'PB11': 'VESC_RX',
    'PB12': 'KILL', 'PB13': 'PWM_AL', 'PB14': 'PWM_BL', 'PB15': 'PWM_CL'})
for i in range(4):
    d.C('C', '100n', '+3V3', 'GND', desc='VDD decoupling, one per VDD pin')
d.C('C', '4.7u', '+3V3', 'GND', size='0603', desc='VDD bulk')
d.FB('FB', '600R@100MHz', '+3V3', 'VDDA', size='0603', mpn='BLM18KG601SN1D', mfr='Murata', desc='VDDA filter')
d.C('C', '1u', 'VDDA', 'GND', size='0603', desc='VDDA')
d.C('C', '10n', 'VDDA', 'GND', desc='VDDA HF')
d.C('C', '2.2u', 'VCAP1', 'GND', size='0603', desc='VCAP_1 (low ESR)')
d.C('C', '2.2u', 'VCAP2', 'GND', size='0603', desc='VCAP_2 (low ESR)')
d.C('C', '100n', 'STK_MCU_NRST', 'GND', desc='NRST cap')
d.R('R', '10k', 'STK_MCU_BOOT0', 'GND', desc='BOOT0 low: boot from flash')
d.R('R', '10k', 'BOOT1', 'GND', desc='PB2/BOOT1 low: ROM bootloader works when BOOT0 is driven high')
d.stock('Y', 'Device:Crystal_GND24', '8MHz', 'Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm',
        {'1': 'OSC_IN', '3': 'OSC_OUT', '2': 'GND', '4': 'GND'}, desc='8 MHz crystal, 3225, CL 12 pF, 20 ppm')
d.C('C', '18p', 'OSC_IN', 'GND', desc='crystal load C0G')
d.C('C', '18p', 'OSC_OUT', 'GND', desc='crystal load C0G')
d.chip('J', conn('SWD', 10, 'Connector_PinHeader_1.27mm:PinHeader_2x05_P1.27mm_Vertical_SMD', mpn='FTSH-105-01-L-DV-K',
                   mfr='Samtec', desc='Cortex debug 10-pin (ST-Link)',
                   names=['VTREF', 'SWDIO', 'GND', 'SWCLK', 'GND', 'SWO', 'KEY', 'NC', 'GNDDET', 'NRST']),
       {'VTREF': '+3V3', 'SWDIO': 'SWDIO', 'GND': 'GND', 'SWCLK': 'SWCLK', 'SWO': None, 'KEY': None, 'NC': None,
        'GNDDET': 'GND', 'NRST': 'STK_MCU_NRST'})
d.R('R', '1k', 'LED_G', 'LED_G_A', desc='status LED')
d.LED('D', 'GREEN', 'LED_G_A', 'GND')
d.R('R', '1k', 'LED_R', 'LED_R_A', desc='status LED')
d.LED('D', 'RED', 'LED_R_A', 'GND')
# UART and control lines to the brain board
d.R('R', '100', 'VESC_TX', 'STK_VESC_M2J', desc='USART3 TX to the Jetson')
d.R('R', '100', 'STK_VESC_J2M', 'VESC_RX', desc='USART3 RX from the Jetson')
d.R('R', '100k', '+3V3', 'VESC_RX', desc='RX idles high while the Jetson is off')
d.R('R', '100', 'MCU_POWER_EN', 'STK_POWER_EN', desc='brain board power enable')
d.R('R', '100k', 'STK_POWER_EN', '+3V3', desc='brain board stays on while the MCU is in reset or being flashed')
d.R('R625', '10k', 'GATE_EN_MCU', 'GND', desc='gate driver held off while the MCU is in reset or its ROM bootloader')
d.R('R', '100', 'MCU_PWR_BTN_N', 'STK_PWR_BTN_N', desc='power-button request to the Jetson')
d.R('R', '100k', '+3V3', 'STK_PWR_BTN_N', desc='idle high')
d.R('R', '10k', '+3V3', 'STK_OS_HALTED', desc='reads high (halted) while the brain board is off')
# IMU on bit-banged I2C
d.chip('U', LSM6DS3, {'VDDIO': '+3V3', 'VDD': '+3V3', 'SCL': 'IMU_SCL', 'SDA': 'IMU_SDA', 'SDO/SA0': 'GND',
                        'CS': '+3V3', 'INT1': None, 'INT2': None, 'SDX': 'GND', 'SCX': 'GND', 'NC': None, 'GND': 'GND'})
d.C('C', '100n', '+3V3', 'GND', desc='IMU VDD')
d.C('C', '1u', '+3V3', 'GND', size='0603', desc='IMU bulk')
d.R('R', '4.7k', '+3V3', 'IMU_SCL', desc='I2C pull-up')
d.R('R', '4.7k', '+3V3', 'IMU_SDA', desc='I2C pull-up')
# CAN
d.chip('U', SN65HVD230, {'VCC': '+3V3', 'D': 'CAN_TX', 'R': 'CAN_RX', 'Rs': 'GND', 'CANH': 'CANH', 'CANL': 'CANL',
                           'Vref': None, 'GND': 'GND'})
d.C('C', '100n', '+3V3', 'GND', desc='CAN transceiver')
d.R('R', '120', 'CANH', 'CAN_TERM', desc='CAN termination (close the TERM jumper at the end of the bus)')
d.chip('JP', SJ2, {'1': 'CAN_TERM', '2': 'CANL'}, value='TERM', desc='CAN terminator jumper', in_bom='no')
d.stock('D', 'Device:D_TVS_Dual_AAC', 'NUP2105L', 'Package_TO_SOT_SMD:SOT-23', {'1': 'CANH', '2': 'CANL', '3': 'GND'},
        mpn='NUP2105LT1G', mfr='onsemi', desc='CAN bus ESD')
d.chip('J', conn('CAN', 4, 'Connector_JST:JST_GH_BM04B-GHS-TBT_1x04-1MP_P1.25mm_Vertical', mpn='BM04B-GHS-TBT(LF)(SN)(N)',
                   mfr='JST', desc='CAN port', names=['5V', 'CANH', 'CANL', 'GND']),
       {'5V': '+5V', 'CANH': 'CANH', 'CANL': 'CANL', 'GND': 'GND'})
# hall sensors and motor temperature
d.chip('J', conn('HALL', 6, 'Connector_JST:JST_ZH_B6B-ZR_1x06_P1.50mm_Vertical', mpn='B6B-ZR(LF)(SN)', mfr='JST',
                   desc='motor sensor lead', names=['GND', 'TEMP', 'HC', 'HB', 'HA', '5V']),
       {'GND': 'GND', 'TEMP': 'TEMP_MOTOR_J', 'HC': 'HALL3_J', 'HB': 'HALL2_J', 'HA': 'HALL1_J', '5V': '+5V'})
for i, h in enumerate(('1', '2', '3')):
    d.R('R', '4.7k', '+5V', f'HALL{h}_J', desc='hall pull-up (open collector sensors)')
    d.R('R', '1k', f'HALL{h}_J', f'HALL{h}', desc='hall filter (PC6-8 are 5 V tolerant)')
    d.C('C', '1n', f'HALL{h}', 'GND', desc='hall filter')
d.R('R', '10k', '+3V3', 'TEMP_MOTOR', desc='motor NTC pull-up (NTC_RES_MOTOR)')
d.R('R', '100', 'TEMP_MOTOR_J', 'TEMP_MOTOR', desc='motor NTC series')
d.C('C', '100n', 'TEMP_MOTOR', 'GND', desc='motor NTC filter')
# servo signal
d.chip('U', AHCT1G125, {'VCC': '+5V', 'A': 'SERVO_PWM', '~{OE}': 'GND', 'Y': 'SERVO_BUF', 'GND': 'GND'})
d.C('C', '100n', '+5V', 'GND', desc='servo buffer')
d.R('R', '220', 'SERVO_BUF', 'SERVO_SIG', desc='servo signal series')

# =============================================================================== G. charging
d.block('G_CHARGE', 'USB-C: TPS25751D PD sink + BQ25798 charger', [
    'TPS25751D in SafeMode (ADCIN1 = LDO_3V3, ADCIN2 = GND): loads its patch and configuration from the M24512 at 0x50',
    'on I2Cc, negotiates up to 20 V and programs the BQ25798 (0x6B) on the same bus. Target port on the Jetson I2C.',
    'BQ25798: PROG 17.4k = 4S, 1.5 MHz, 1 uH. TS fixed at 25 C (5.23k / 30.1k || 10k). ILIM_HIZ 39k / 100k = 3.25 A.',
    'SYS output is VSYS (NVDC path): the brain board and the lidar run from it, from USB power when it is plugged in.',
    'EEPROM image: TI Application Customization Tool (TPS25751). Header J702 can program it off-line.',
])
d.chip('J', USBC16, {'VBUS': 'VBUS_C', 'CC1': 'USB_CC1', 'CC2': 'USB_CC2', 'D+': 'USBC_DP', 'D-': 'USBC_DN',
                       'SBU1': None, 'SBU2': None, 'GND': 'GND', 'SHIELD': 'GND'})
d.chip('D', ESD4, {'IO1': 'USBC_DP', 'IO2': 'USBC_DN', 'IO3': None, 'IO4': None, 'GND': 'GND'},
       desc='USB-C data ESD (flow-through, 0.5 pF)')
d.D('D', 'SMF24A', 'GND', 'VBUS_C', 'Diode_SMD:D_SOD-123F', kind='Z', mpn='SMF24A', mfr='Littelfuse',
    desc='VBUS TVS, 24 V standoff (20 V PD)')
d.C('C', '4.7u 25V', 'VBUS_C', 'GND', size='0805', desc='CVBUS')
d.C('C', '390p', 'USB_CC1', 'GND', desc='CC cap (200-480 pF)')
d.C('C', '390p', 'USB_CC2', 'GND', desc='CC cap (200-480 pF)')
d.chip('U', TPS25751D, {
    'VBUS_IN': 'VBUS_C', 'VBUS': 'VBUS_C', 'PP5V': '+5V', 'VIN_3V3': '+3V3', 'LDO_3V3': 'PD_LDO3V3', 'LDO_1V5': 'PD_LDO1V5',
    'CC1': 'USB_CC1', 'CC2': 'USB_CC2', 'ADCIN1': 'PD_LDO3V3', 'ADCIN2': 'GND',
    'I2Cc_SDA': 'CHG_SDA', 'I2Cc_SCL': 'CHG_SCL', '~{I2Cc_IRQ}': 'CHG_INT_N',
    'I2Ct_SDA': 'STK_I2C_SDA', 'I2Ct_SCL': 'STK_I2C_SCL', '~{I2Ct_IRQ}': 'PD_IRQ_N',
    'PPHV': 'PPHV', 'GPIO0': 'GND', 'GPIO1': 'GND', 'GPIO2': 'GND', 'GPIO3': 'GND', 'GPIO4': 'GND', 'GPIO5': 'GND',
    'GPIO6': 'GND', 'GPIO7': 'GND', 'GPIO11': None, 'DRAIN': 'PD_DRAIN', 'GND': 'GND'})
d.C('C', '10u 10V', '+3V3', 'GND', size='0805', desc='CVIN_3V3')
d.C('C', '10u 10V', 'PD_LDO3V3', 'GND', size='0805', desc='CLDO_3V3')
d.C('C', '4.7u 10V', 'PD_LDO1V5', 'GND', size='0603', desc='CLDO_1V5')
d.C('C', '10u 10V', '+5V', 'GND', size='0805', desc='PP5V (sink-only board: never sourced)')
d.C('C', '22u 25V', 'PPHV', 'GND', size='1206', desc='CPPHV (47-100 uF with the charger input caps)')
d.C('C', '22u 25V', 'PPHV', 'GND', size='1206', desc='CPPHV')
d.R('R', '10k', 'PD_LDO3V3', 'CHG_SDA', desc='I2Cc pull-up to LDO_3V3')
d.R('R', '10k', 'PD_LDO3V3', 'CHG_SCL', desc='I2Cc pull-up to LDO_3V3')
d.R('R', '10k', 'PD_LDO3V3', 'CHG_INT_N', desc='charger INT pull-up')
d.R('R', '10k', '+3V3', 'PD_IRQ_N', desc='I2Ct IRQ pull-up (not used)')
d.chip('U', EEPROM_SO8, {'VCC': 'PD_LDO3V3', 'E0': 'GND', 'E1': 'GND', 'E2': 'GND', '~{WC}': 'GND', 'SDA': 'CHG_SDA',
                           'SCL': 'CHG_SCL', 'VSS': 'GND'})
d.C('C', '100n', 'PD_LDO3V3', 'GND', desc='EEPROM')
d.chip('J', conn('EEPROM_PROG', 4, 'Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical', desc='EEPROM programming header (DNP)',
                   names=['3V3', 'SDA', 'SCL', 'GND']), {'3V3': 'PD_LDO3V3', 'SDA': 'CHG_SDA', 'SCL': 'CHG_SCL', 'GND': 'GND'},
       dnp=True)
d.chip('U', BQ25798, {
    'VBUS': 'PPHV', 'PMID': 'CHG_PMID', 'REGN': 'CHG_REGN', 'VAC1': 'PPHV', 'VAC2': 'PPHV',
    'SCL': 'CHG_SCL', 'SDA': 'CHG_SDA', '~{INT}': 'CHG_INT_N', 'STAT': 'CHG_STAT_N', '~{CE}': 'GND', '~{QON}': 'CHG_QON_N',
    'TS': 'CHG_TS', 'ILIM_HIZ': 'CHG_ILIM', 'PROG': 'CHG_PROG', 'D+': None, 'D-': None, 'ACDRV1': 'GND', 'ACDRV2': 'GND',
    'SW1': 'CHG_SW1', 'BTST1': 'CHG_BT1', 'SW2': 'CHG_SW2', 'BTST2': 'CHG_BT2', 'SYS': 'VSYS', 'BAT': 'BATP',
    'BATP': 'CHG_BATP', 'SDRV': None, 'GND': 'GND'})
d.C('C', '100n 50V', 'PPHV', 'GND', desc='VBUS HF')
d.C('C', '10u 25V', 'PPHV', 'GND', size='0805', desc='VBUS')
d.C('C', '10u 25V', 'PPHV', 'GND', size='0805', desc='VBUS')
d.C('C', '100n 50V', 'CHG_PMID', 'GND', desc='PMID HF')
for i in range(3):
    d.C('C', '10u 25V', 'CHG_PMID', 'GND', size='0805', desc='PMID (3 x 10 uF)')
d.C('C', '4.7u 10V', 'CHG_REGN', 'GND', size='0603', desc='REGN')
d.C('C', '47n 16V', 'CHG_BT1', 'CHG_SW1', desc='BTST1')
d.C('C', '47n 16V', 'CHG_BT2', 'CHG_SW2', desc='BTST2')
d.L('L', '1u', 'CHG_SW1', 'CHG_SW2', 'Inductor_SMD:L_Coilcraft_XAL5030-XXX', mpn='XAL5030-102MEB', mfr='Coilcraft',
    desc='charger inductor 1.0 uH (1.5 MHz), Isat > 6 A')
d.C('C', '100n 50V', 'VSYS', 'GND', desc='SYS HF')
for i in range(5):
    d.C('C', '10u 25V', 'VSYS', 'GND', size='0805', desc='SYS (5 x 10 uF)')
d.C('C', '10u 25V', 'BATP', 'GND', size='0805', desc='BAT')
d.C('C', '10u 25V', 'BATP', 'GND', size='0805', desc='BAT')
d.R('R', '100', 'BATP', 'CHG_BATP', desc='BATP sense series 100 Ohm')
d.R('R', '5.23k', 'CHG_REGN', 'CHG_TS', desc='TS RT1')
d.R('R', '30.1k', 'CHG_TS', 'GND', desc='TS RT2')
d.R('R', '10k', 'CHG_TS', 'GND', desc='TS: fixed 25 C in place of a thermistor (pack NTC goes to the BMS)')
d.R('R', '39k', 'CHG_REGN', 'CHG_ILIM', desc='ILIM_HIZ top: 1 V + 0.8 x 3.25 A = 3.6 V')
d.R('R', '100k', 'CHG_ILIM', 'GND', desc='ILIM_HIZ bottom')
d.R('R', '17.4k', 'CHG_PROG', 'GND', desc='PROG: 4S, 1.5 MHz (table 7-1)')
d.R('R', '2.2k', 'CHG_REGN', 'CHG_LED_A', desc='charge LED from REGN (works with the car off)')
d.LED('D', 'AMBER', 'CHG_LED_A', 'CHG_STAT_N')
d.R('R', '10k', 'CHG_STAT_N', 'STK_CHG_STAT', desc='charge status to the Jetson (brain input is 5.5 V tolerant)')

# =============================================================================== H. USB debug
d.block('H_USB', 'One-cable debugging: USB2514B hub, CP2102N console, flash-mode switch', [
    'Normal: USB-C -> hub. Port 1 Jetson USB0 (L4T USB networking), port 2 STM32 (VESC Tool), port 3 CP2102N (console).',
    'FLASH switch: two TS3USB30E connect USB-C straight to Jetson USB0 (NVIDIA asks for a direct link in recovery).',
    'Hub straps: CFG_SEL = 00 (self-powered, straps on), NON_REM = 11 (ports 1-3 fixed). RBIAS 12.0k 1%.',
    'VBUS_DET: VBUS can be 20 V after PD, so a 10k + 3.3 V low-current zener clamps it.',
])
d.chip('U', TS3USB30E, {'VCC': '+3V3', 'D+': 'USBC_DP', 'D-': 'USBC_DN', 'S': 'FLASH_SEL', '~{OE}': 'GND',
                          'D1+': 'HUB_UP_DP', 'D1-': 'HUB_UP_DN', 'D2+': 'FLASH_DP', 'D2-': 'FLASH_DN', 'GND': 'GND'})
d.chip('U', TS3USB30E, {'VCC': '+3V3', 'D+': 'STK_USB0_DP', 'D-': 'STK_USB0_DN', 'S': 'FLASH_SEL', '~{OE}': 'GND',
                          'D1+': 'HUB_DN1_DP', 'D1-': 'HUB_DN1_DN', 'D2+': 'FLASH_DP', 'D2-': 'FLASH_DN', 'GND': 'GND'})
d.C('C', '100n', '+3V3', 'GND', desc='mux')
d.C('C', '100n', '+3V3', 'GND', desc='mux')
d.stock('SW', 'Switch:SW_SPDT', 'FLASH', 'Button_Switch_SMD:SW_SPDT_PCM12', {'1': '+3V3', '2': 'FLASH_SEL', '3': 'GND'},
        mpn='PCM12SMTR', mfr='C&K', desc='USB mode: normal (hub) / flash (direct to Jetson)')
d.R('R', '100k', 'FLASH_SEL', 'GND', desc='defined level while the slider moves')
d.chip('U', USB2514B, {
    'VDD33': '+3V3', 'VDDA33': '+3V3', 'USBDM_UP': 'HUB_UP_DN', 'USBDP_UP': 'HUB_UP_DP', 'VBUS_DET': 'HUB_VBUS_DET',
    'RESET_N': 'HUB_RST_N', 'XTALIN': 'HUB_XI', 'XTALOUT': 'HUB_XO', 'RBIAS': 'HUB_RBIAS', 'CRFILT': 'HUB_CRFILT',
    'PLLFILT': 'HUB_PLLFILT', 'TEST': 'GND', 'SCL/CFG_SEL0': 'HUB_CFG0', 'HS_IND/CFG_SEL1': 'HUB_CFG1',
    'SDA/NON_REM1': 'HUB_NONREM1', 'SUSP_IND/NON_REM0': 'HUB_NONREM0',
    'DM_DN1': 'HUB_DN1_DN', 'DP_DN1': 'HUB_DN1_DP', 'DM_DN2': 'USB_MCU_DN', 'DP_DN2': 'USB_MCU_DP',
    'DM_DN3': 'USB_CP_DN', 'DP_DN3': 'USB_CP_DP', 'DM_DN4': None, 'DP_DN4': None,
    'PRTPWR1': None, 'PRTPWR2': None, 'PRTPWR3': None, 'PRTPWR4': None,
    'OCS_N1': None, 'OCS_N2': None, 'OCS_N3': None, 'OCS_N4': None, 'VSS': 'GND'})
for i in range(4):
    d.C('C', '100n', '+3V3', 'GND', desc='hub VDDA33 / VDD33')
d.C('C', '4.7u', '+3V3', 'GND', size='0603', desc='hub bulk')
d.C('C', '100n', 'HUB_CRFILT', 'GND', desc='CRFILT (max 0.1 uF)')
d.C('C', '100n', 'HUB_PLLFILT', 'GND', desc='PLLFILT (max 0.1 uF)')
d.R('R', '12.0k', 'HUB_RBIAS', 'GND', desc='RBIAS 12.0k 1%')
d.stock('Y', 'Device:Crystal_GND24', '24MHz', 'Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm',
        {'1': 'HUB_XI', '3': 'HUB_XO', '2': 'GND', '4': 'GND'}, desc='24 MHz crystal, 3225, CL 12 pF')
d.C('C', '18p', 'HUB_XI', 'GND', desc='crystal load C0G')
d.C('C', '18p', 'HUB_XO', 'GND', desc='crystal load C0G')
d.R('R', '10k', '+3V3', 'HUB_RST_N', desc='reset RC')
d.C('C', '1u', 'HUB_RST_N', 'GND', size='0603', desc='reset RC (10 ms)')
d.R('R', '10k', 'HUB_CFG0', 'GND', desc='CFG_SEL0 = 0')
d.R('R', '470', 'HUB_CFG1', 'HUB_LED_A', desc='HS indicator LED; also straps CFG_SEL1 = 0')
d.LED('D', 'BLUE', 'HUB_LED_A', 'GND')
d.R('R', '47k', '+3V3', 'HUB_NONREM1', desc='NON_REM1 = 1')
d.R('R', '47k', '+3V3', 'HUB_NONREM0', desc='NON_REM0 = 1 (and LOCAL_PWR = self-powered)')
d.R('R', '10k', 'VBUS_C', 'HUB_VBUS_DET', desc='VBUS_DET from USB-C VBUS (5-20 V)')
d.D('D', 'MMSZ4684', 'GND', 'HUB_VBUS_DET', 'Diode_SMD:D_SOD-123', kind='Z', mpn='MMSZ4684T1G', mfr='onsemi',
    desc='3.3 V low-current zener clamp')
d.R('R', '100k', 'HUB_VBUS_DET', 'GND', desc='VBUS_DET low when unplugged')
d.chip('U', CP2102N, {
    'VDD': '+3V3', 'VIO': '+3V3', 'VREGIN': '+3V3', 'D+': 'USB_CP_DP', 'D-': 'USB_CP_DN', 'VBUS': 'CP_VBUS', '~{RST}': 'CP_RST_N',
    'TXD': 'CP_TXD', 'RXD': 'STK_CON_J2M', '~{RTS}': None, '~{CTS}': None, '~{DTR}': None, '~{DSR}': None, '~{DCD}': None,
    '~{RI}': None, 'GPIO.0/TXT': 'CP_TXLED', 'GPIO.1/RXT': 'CP_RXLED', 'GPIO.2': None, 'GPIO.3': None,
    '~{SUSPEND}': None, 'SUSPEND': None, 'NC': None, 'GND': 'GND'})
d.C('C', '100n', '+3V3', 'GND', desc='CP2102N VDD')
d.C('C', '4.7u', '+3V3', 'GND', size='0603', desc='CP2102N VDD bulk')
d.C('C', '100n', '+3V3', 'GND', desc='CP2102N VIO / VREGIN')
d.R('R', '1k', '+3V3', 'CP_RST_N', desc='RSTb pull-up (datasheet)')
d.R('R', '10k', '+3V3', 'CP_VBUS', desc='always attached behind the hub')
d.R('R', '100', 'CP_TXD', 'STK_CON_M2J', desc='console TX to the Jetson')
d.R('R', '1k', '+3V3', 'CP_TXLED_A', desc='TX LED')
d.LED('D', 'GREEN', 'CP_TXLED_A', 'CP_TXLED', size='0402')
d.R('R', '1k', '+3V3', 'CP_RXLED_A', desc='RX LED')
d.LED('D', 'YELLOW', 'CP_RXLED_A', 'CP_RXLED', size='0402')

# =============================================================================== I. outputs
d.block('I_OUT', 'Servo 7.5 V (TPSM63610), lidar eFuse (TPS26600), fan', [
    'TPSM63610 from VM: RFBT 100k / RFBB 15.4k = 7.49 V, RT 15.8k = 1 MHz, EN divider 100k / 16.2k = on above 9 V.',
    'Output 4 x 47 uF 16 V + 220 uF polymer for servo stall pulses (8 A, 10 A peak).',
    'TPS26600 from VSYS: ILIM 12k = 1 A, dVdT 22 nF, UVLO 10 V. SHDN from the Jetson (LIDAR_EN), off by default.',
])
d.chip('U', TPSM63610, {'VIN': 'VM', 'EN': 'SRV_EN', 'SYNC/MODE': 'GND', 'SPSP': 'SRV_VCC', 'RT': 'SRV_RT',
                          'VLDOIN': 'SERVO_V', 'VCC': 'SRV_VCC', 'NC': None, 'VOUT': 'SERVO_V', 'FB': 'SRV_FB',
                          'PG': 'SRV_PG', 'RBOOT': 'SRV_RBOOT', 'CBOOT': 'SRV_CBOOT', 'SW': None,
                          'AGND': 'GND', 'PGND': 'GND'})
for i in range(3):
    d.C('C', '10u 50V', 'VM', 'GND', size='1210', mpn=MUR_10U50, desc='TPSM63610 input')
d.C('C', '100n 50V', 'VM', 'GND', desc='TPSM63610 input HF')
d.R('R', '100k', 'VM', 'SRV_EN', desc='EN divider top: on above 9.1 V (1.263 V EN)')
d.R('R', '16.2k', 'SRV_EN', 'GND', desc='EN divider bottom')
d.R('R', '15.8k', 'SRV_RT', 'GND', desc='RT: 1 MHz (eq. 5)')
d.R('R', '100k', 'SERVO_V', 'SRV_FB', desc='RFBT')
d.R('R', '15.4k', 'SRV_FB', 'GND', desc='RFBB: 7.49 V')
d.R('R', '100', 'SRV_RBOOT', 'SRV_CBOOT', desc='RBOOT: EMI / efficiency balance (datasheet)')
d.C('C', '1u 25V', 'SERVO_V', 'GND', size='0603', desc='VLDOIN')
d.R('R', '100k', '+3V3', 'SRV_PG', desc='PG pull-up')
for i in range(4):
    d.C('C', '47u 16V', 'SERVO_V', 'GND', size='1210', mpn='GRM32EC81C476ME15L', mfr='Murata',
        desc='servo output 47 uF 16 V X6S')
d.CP('C', '220u 16V', 'SERVO_V', 'GND', 'Capacitor_SMD:CP_Elec_8x10', mpn='16SVPF220M', mfr='Panasonic',
     desc='servo bulk, polymer')
d.chip('J', conn('SERVO', 3, 'Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical', desc='steering servo S / + / -',
                   names=['SIG', 'V+', 'GND']), {'SIG': 'SERVO_SIG', 'V+': 'SERVO_V', 'GND': 'GND'})
d.chip('U', TPS26600, {'IN': 'VSYS', 'UVLO': 'LID_UVLO', 'OVP': 'GND', 'MODE': None, '~{SHDN}': 'STK_LIDAR_EN',
                         'dVdT': 'LID_DVDT', 'ILIM': 'LID_ILIM', 'IMON': None, 'OUT': 'LIDAR_V', '~{FLT}': 'LID_FLT_N',
                         'NC': None, 'GND': 'GND', 'RTN': 'GND'})
d.C('C', '1u 50V', 'VSYS', 'GND', size='0805', desc='eFuse input')
d.R('R', '732k', 'VSYS', 'LID_UVLO', desc='UVLO top: on above 10 V')
d.R('R', '100k', 'LID_UVLO', 'GND', desc='UVLO bottom')
d.C('C', '22n', 'LID_DVDT', 'GND', desc='dVdT: 5 V/ms output ramp')
d.R('R', '12k', 'LID_ILIM', 'GND', desc='ILIM: 1.0 A')
d.R('R', '100k', 'STK_LIDAR_EN', 'GND', desc='lidar off unless the Jetson enables it')
d.R('R', '100k', '+3V3', 'LID_FLT_N', desc='fault pull-up (test point)')
d.C('C', '1u 50V', 'LIDAR_V', 'GND', size='0805', desc='eFuse output')
d.D('D', 'SMBJ20A', 'GND', 'LIDAR_V', 'Diode_SMD:D_SMB', kind='Z', mpn='SMBJ20A', mfr='Littelfuse', desc='lidar output TVS')
d.chip('J', conn('LIDAR_PWR', 2, 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_PT-1,5-2-3.5-H_1x02_P3.50mm_Horizontal',
                   mpn='1984617', mfr='Phoenix Contact', desc='lidar power (donor M12 cable)', names=['+', '-']),
       {'+': 'LIDAR_V', '-': 'GND'})
d.chip('J', conn('FAN', 4, 'Connector:FanPinHeader_1x04_P2.54mm_Vertical', desc='side-pod fan, 5 V, full speed',
                   names=['GND', '+5V', 'TACH', 'PWM']), {'GND': 'GND', '+5V': '+5V', 'TACH': None, 'PWM': None})

# =============================================================================== J. stack and sense
d.block('J_STACK', 'Brain board socket, battery monitor, board ID', [
    'Pin map from boards/stack/stack.py (shared with the brain board). Odd pins on the car-left row, pin 1 at the rear.',
    'INA228 at 0x40 on the Jetson I2C: pack current on the BMS shunt (0.5 mOhm), pack voltage on B+.',
    'The Jetson I2C is pulled up on the module; the 10k here keep it defined while the brain board is off.',
])
dn = stack.drive_nets()
d.chip('J', conn('STACK_2x20', 40, 'Connector_PinSocket_2.54mm:PinSocket_2x20_P2.54mm_Vertical', mpn='SSQ-120-03-G-D',
                   mfr='Samtec', desc='2x20 2.54 mm socket to the brain board (stack gap 20 mm, see stack.py)',
                   names=[f'P{i}' for i in range(1, 41)]), {f'P{i}': dn[i] for i in range(1, 41)})
d.R('R', '10k', '+3V3', 'STK_I2C_SCL', desc='I2C pull-up (brain off)')
d.R('R', '10k', '+3V3', 'STK_I2C_SDA', desc='I2C pull-up (brain off)')
for i, n in enumerate(('STK_SPARE1', 'STK_SPARE2', 'STK_CAN_TX', 'STK_CAN_RX')):
    d.TP('TP', n)
d.chip('U', INA228, {'VS': '+3V3', 'IN+': 'INA_INP', 'IN-': 'INA_INN', 'VBUS': 'INA_VBUS', 'A0': 'GND', 'A1': 'GND',
                       'SCL': 'STK_I2C_SCL', 'SDA': 'STK_I2C_SDA', '~{ALERT}': None, 'GND': 'GND'})
d.C('C', '100n', '+3V3', 'GND', desc='INA228')
d.R('R', '10', 'BMS_KS2', 'INA_INP', desc='shunt filter (IN+ on the pack side: discharge reads positive)')
d.R('R', '10', 'BMS_KS1', 'INA_INN', desc='shunt filter')
d.C('C', '100n', 'INA_INP', 'INA_INN', desc='shunt filter')
d.R('R', '1k', 'BATP', 'INA_VBUS', desc='bus sense series')
d.C('C', '10n 50V', 'INA_VBUS', 'GND', desc='bus sense filter')
d.chip('U', EEPROM_2K, {'VCC': '+3V3', 'SDA': 'STK_I2C_SDA', 'SCL': 'STK_I2C_SCL', 'WP': 'GND', 'VSS': 'GND'})
d.C('C', '100n', '+3V3', 'GND', desc='ID EEPROM')
for i, n in enumerate(('GND', 'GND', 'BATP', 'VM', 'VSYS', '+5V', '+3V3', '3V3_AON', 'SERVO_V', 'LIDAR_V', 'SRV_PG', 'LID_FLT_N',
                       'CURR_A', 'SENS_A')):
    d.TP('TP', n)
MH = 'MountingHole:MountingHole_3.2mm_M3_Pad_Via'
for i in range(8):
    d.stock('H', 'Mechanical:MountingHole_Pad', 'M3', MH, {'1': 'GND'}, desc='M3 mounting hole', in_bom='no')

if __name__ == '__main__':
    bad = d.check()
    print(len(d.parts), 'parts', len(d.nets()), 'nets')
    for net, nodes in bad:
        print('single-pin net', net, nodes)
