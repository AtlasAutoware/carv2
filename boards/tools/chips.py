"""Pin tables for every IC and connector on the two boards (box symbols).

Each pin table was checked against the part's datasheet pin-function table or the stock KiCad
symbol of the same part. Numbers in a list are pads that share one pin (stacked in the symbol).
"""
from eda import Chip, P_IN, P_OUT, BIDI, PAS, PWR_IN, PWR_OUT, OC, TRI, NC

L, R, T, B = 'L', 'R', 'T', 'B'

# ------------------------------------------------------------------ MCU and motor driver
STM32F405 = Chip('STM32F405RGT6', [
    ('1', 'VBAT', PWR_IN, T), (['19', '32', '48', '64'], 'VDD', PWR_IN, T), ('13', 'VDDA', PWR_IN, T),
    ('31', 'VCAP_1', PAS, T), ('47', 'VCAP_2', PAS, T),
    (['18', '63'], 'VSS', PWR_IN, B), ('12', 'VSSA', PWR_IN, B),
    ('7', 'NRST', P_IN, L), ('60', 'BOOT0', P_IN, L), ('5', 'PH0-OSC_IN', P_IN, L), ('6', 'PH1-OSC_OUT', P_OUT, L),
    ('14', 'PA0', BIDI, L), ('15', 'PA1', BIDI, L), ('16', 'PA2', BIDI, L), ('17', 'PA3', BIDI, L),
    ('20', 'PA4', BIDI, L), ('21', 'PA5', BIDI, L), ('22', 'PA6', BIDI, L), ('23', 'PA7', BIDI, L),
    ('41', 'PA8', BIDI, L), ('42', 'PA9', BIDI, L), ('43', 'PA10', BIDI, L), ('44', 'PA11', BIDI, L),
    ('45', 'PA12', BIDI, L), ('46', 'PA13', BIDI, L), ('49', 'PA14', BIDI, L), ('50', 'PA15', BIDI, L),
    ('8', 'PC0', BIDI, L), ('9', 'PC1', BIDI, L), ('10', 'PC2', BIDI, L), ('11', 'PC3', BIDI, L),
    ('26', 'PB0', BIDI, R), ('27', 'PB1', BIDI, R), ('28', 'PB2', BIDI, R), ('55', 'PB3', BIDI, R),
    ('56', 'PB4', BIDI, R), ('57', 'PB5', BIDI, R), ('58', 'PB6', BIDI, R), ('59', 'PB7', BIDI, R),
    ('61', 'PB8', BIDI, R), ('62', 'PB9', BIDI, R), ('29', 'PB10', BIDI, R), ('30', 'PB11', BIDI, R),
    ('33', 'PB12', BIDI, R), ('34', 'PB13', BIDI, R), ('35', 'PB14', BIDI, R), ('36', 'PB15', BIDI, R),
    ('24', 'PC4', BIDI, R), ('25', 'PC5', BIDI, R), ('37', 'PC6', BIDI, R), ('38', 'PC7', BIDI, R),
    ('39', 'PC8', BIDI, R), ('40', 'PC9', BIDI, R), ('51', 'PC10', BIDI, R), ('52', 'PC11', BIDI, R),
    ('53', 'PC12', BIDI, R), ('2', 'PC13', BIDI, R), ('3', 'PC14', BIDI, R), ('4', 'PC15', BIDI, R),
    ('54', 'PD2', BIDI, R),
], 'Package_QFP:LQFP-64_10x10mm_P0.5mm', desc='ARM Cortex-M4 MCU, 1 MB flash (runs VESC firmware)',
    mpn='STM32F405RGT6', mfr='STMicroelectronics', width=22.86)

DRV8323RS = Chip('DRV8323RS', [
    ('6', 'VM', PWR_IN, T), ('7', 'VDRAIN', P_IN, T), ('5', 'VCP', PAS, T), ('4', 'CPH', PAS, T), ('3', 'CPL', PAS, T),
    ('36', 'DVDD', PWR_OUT, T), ('26', 'VREF', PWR_IN, T),
    ('37', 'INHA', P_IN, L), ('38', 'INLA', P_IN, L), ('39', 'INHB', P_IN, L), ('40', 'INLB', P_IN, L),
    ('41', 'INHC', P_IN, L), ('42', 'INLC', P_IN, L), ('33', 'ENABLE', P_IN, L), ('34', 'CAL', P_IN, L),
    ('32', 'nSCS', P_IN, L), ('31', 'SCLK', P_IN, L), ('30', 'SDI', P_IN, L), ('29', 'SDO', OC, L),
    ('28', 'nFAULT', OC, L), ('25', 'SOA', P_OUT, L), ('24', 'SOB', P_OUT, L), ('23', 'SOC', P_OUT, L),
    ('47', 'VIN', PWR_IN, L), ('48', 'nSHDN', P_IN, L), ('44', 'CB', PAS, L), ('45', 'SW', P_OUT, L), ('1', 'FB', P_IN, L),
    ('8', 'GHA', P_OUT, R), ('9', 'SHA', PAS, R), ('10', 'GLA', P_OUT, R), ('11', 'SPA', P_IN, R), ('12', 'SNA', P_IN, R),
    ('17', 'GHB', P_OUT, R), ('16', 'SHB', PAS, R), ('15', 'GLB', P_OUT, R), ('14', 'SPB', P_IN, R), ('13', 'SNB', P_IN, R),
    ('18', 'GHC', P_OUT, R), ('19', 'SHC', PAS, R), ('20', 'GLC', P_OUT, R), ('21', 'SPC', P_IN, R), ('22', 'SNC', P_IN, R),
    ('46', 'NC', NC, R),
    (['2', '27', '35', '43', '49'], 'GND', PWR_IN, B),
], 'Package_DFN_QFN:Texas_RGZ0048A_VQFN-48-1EP_7x7mm_P0.5mm_EP5.15x5.15mm_ThermalVias',
    desc='3-phase smart gate driver, 3 CSAs, 600 mA buck (SPI)', mpn='DRV8323RSRGZR', mfr='Texas Instruments', width=30.48)
# pad 2 PGND, 27 DGND, 35 AGND, 43 BGND, 49 thermal pad: one ground here, joined on the plane under the IC

NFET_Q5B = Chip('CSD18510Q5B', [('4', 'G', P_IN, L), ('5', 'D', PAS, T), (['1', '2', '3'], 'S', PAS, B)],
                'Package_TO_SOT_SMD:TDSON-8-1', ref='Q', desc='N-FET 40 V 0.79 mOhm (10 V) SON 5x6',
                mpn='CSD18510Q5B', mfr='Texas Instruments', width=7.62)

NMOS_SOT23 = Chip('2N7002K', [('1', 'G', P_IN, L), ('3', 'D', PAS, T), ('2', 'S', PAS, B)],
                  'Package_TO_SOT_SMD:SOT-23', ref='Q', desc='N-MOSFET 60 V 300 mA logic level, SOT-23',
                  mpn='2N7002K', mfr='onsemi / Nexperia', width=7.62)

SHUNT4 = Chip('R_SHUNT_4T', [('1', 'I1', PAS, L), ('4', 'I2', PAS, R), ('2', 'S1', PAS, B), ('3', 'S2', PAS, B)],
              'Resistor_SMD:R_Shunt_Isabellenhuette_BVR4026', ref='R', desc='4-terminal current shunt 4026',
              width=10.16)

# ------------------------------------------------------------------ battery protection and main switch
BQ77915 = Chip('BQ7791508', [
    ('1', 'VDD', PWR_IN, T), ('2', 'AVDD', PWR_OUT, T),
    ('3', 'VC5', P_IN, L), ('4', 'VC4', P_IN, L), ('5', 'VC3', P_IN, L), ('6', 'VC2', P_IN, L), ('7', 'VC1', P_IN, L),
    ('8', 'VC0', P_IN, L), ('10', 'SRP', P_IN, L), ('11', 'SRN', P_IN, L), ('18', 'TS', P_IN, L), ('19', 'VTB', P_OUT, L),
    ('12', 'DSG', P_OUT, R), ('13', 'CHG', P_OUT, R), ('14', 'LD', P_IN, R), ('15', 'LPWR', P_OUT, R),
    ('16', 'CBI', P_IN, R), ('17', 'OCDP', P_IN, R), ('20', 'CCFG', P_IN, R), ('21', 'CBO', P_OUT, R),
    ('22', 'PRES', P_IN, R), ('23', 'CTRC', P_IN, R), ('24', 'CTRD', P_IN, R),
    ('9', 'VSS', PWR_IN, B),
], 'Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm', desc='3-5S Li-ion protector, balancing, no MCU (OV 4.20 V, UV 3.0 V)',
    mpn='BQ7791508PWR', mfr='Texas Instruments', width=20.32)

TPS48111 = Chip('TPS48111-Q1', [
    ('20', 'VS', PWR_IN, T), ('18', 'CS+', P_IN, T), ('17', 'CS-', P_IN, T), ('19', 'ISCP', P_IN, T),
    ('1', 'EN/UVLO', P_IN, L), ('2', 'INP_G', P_IN, L), ('3', 'INP', P_IN, L), ('4', 'FLT_T', OC, L), ('5', 'FLT_I', OC, L),
    ('7', 'IMON', P_OUT, L), ('8', 'IWRN', PAS, L), ('9', 'TMR', PAS, L), ('10', 'DIODE', PAS, L),
    ('12', 'BST', PAS, R), ('15', 'PU', P_OUT, R), ('14', 'PD', PAS, R), ('13', 'SRC', PAS, R), ('11', 'G', P_OUT, R),
    ('6', 'GND', PWR_IN, B),
], 'atlas:TI_DGX0019A_VSSOP-19_3x5.1mm_P0.5mm', desc='100 V smart high-side driver with precharge driver, 1.2 us SCP',
    mpn='TPS48111QDGXRQ1', mfr='Texas Instruments', width=20.32)

LVC1G74 = Chip('SN74LVC1G74', [('8', 'VCC', PWR_IN, T), ('1', 'CLK', P_IN, L), ('2', 'D', P_IN, L),
                               ('7', '~{PRE}', P_IN, L), ('6', '~{CLR}', P_IN, L), ('5', 'Q', P_OUT, R),
                               ('3', '~{Q}', P_OUT, R), ('4', 'GND', PWR_IN, B)],
               'Package_SO:VSSOP-8_2.3x2mm_P0.5mm', desc='D flip-flop with preset and clear (power latch)',
               mpn='SN74LVC1G74DCUR', mfr='Texas Instruments', width=12.7)

TPS709 = Chip('TPS70933', [('1', 'IN', PWR_IN, L), ('3', 'EN', P_IN, L), ('5', 'OUT', PWR_OUT, R), ('4', 'NC', NC, R),
                           ('2', 'GND', PWR_IN, B)],
              'Package_TO_SOT_SMD:SOT-23-5', desc='30 V 150 mA LDO, 1 uA quiescent (always-on 3.3 V)',
              mpn='TPS70933DBVR', mfr='Texas Instruments', width=10.16)

TLV755 = Chip('TLV75533P', [('6', 'IN', PWR_IN, L), ('4', 'EN', P_IN, L), ('1', 'OUT', PWR_OUT, R),
                            (['2', '5'], 'NC', NC, R), (['3', '7'], 'GND', PWR_IN, B)],
              'Package_SON:WSON-6-1EP_2x2mm_P0.65mm_EP1x1.6mm', desc='500 mA LDO 3.3 V, WSON-6 with thermal pad',
              mpn='TLV75533PDRVR', mfr='Texas Instruments', width=10.16)

# ------------------------------------------------------------------ charging
BQ25798 = Chip('BQ25798', [
    (['2', '3'], 'VBUS', PWR_IN, T), ('29', 'PMID', PAS, T), ('5', 'REGN', PWR_OUT, T), ('9', 'VAC1', P_IN, T), ('8', 'VAC2', P_IN, T),
    ('14', 'SCL', P_IN, L), ('15', 'SDA', BIDI, L), ('21', '~{INT}', OC, L), ('1', 'STAT', OC, L), ('13', '~{CE}', P_IN, L),
    ('12', '~{QON}', P_IN, L), ('16', 'TS', P_IN, L), ('17', 'ILIM_HIZ', P_IN, L), ('20', 'PROG', P_IN, L),
    ('6', 'D+', BIDI, L), ('7', 'D-', BIDI, L), ('11', 'ACDRV1', PAS, L), ('10', 'ACDRV2', PAS, L),
    ('28', 'SW1', P_OUT, R), ('4', 'BTST1', PAS, R), ('26', 'SW2', P_OUT, R), ('19', 'BTST2', PAS, R),
    ('25', 'SYS', PWR_OUT, R), (['22', '23'], 'BAT', PAS, R), ('18', 'BATP', P_IN, R), ('24', 'SDRV', P_OUT, R),
    ('27', 'GND', PWR_IN, B),
], 'Package_DFN_QFN:Texas_RQM0029A_VQFN-29_4x4mm_P0.4mm', desc='1-4S 5 A buck-boost charger, NVDC power path',
    mpn='BQ25798RQMR', mfr='Texas Instruments', width=22.86)

TPS25751D = Chip('TPS25751D', [
    ('23', 'VBUS_IN', PWR_IN, T), ('32', 'VBUS', PWR_OUT, T), ('34', 'PP5V', PWR_IN, T), ('38', 'VIN_3V3', PWR_IN, T),
    ('1', 'LDO_3V3', PWR_OUT, T), ('4', 'LDO_1V5', PWR_OUT, T),
    ('28', 'CC1', BIDI, L), ('29', 'CC2', BIDI, L), ('2', 'ADCIN1', P_IN, L), ('3', 'ADCIN2', P_IN, L),
    ('16', 'I2Cc_SDA', BIDI, L), ('17', 'I2Cc_SCL', OC, L), ('18', '~{I2Cc_IRQ}', P_IN, L),
    ('8', 'I2Ct_SDA', BIDI, L), ('9', 'I2Ct_SCL', P_IN, L), ('10', '~{I2Ct_IRQ}', OC, L),
    ('20', 'PPHV', PWR_OUT, R), ('5', 'GPIO0', P_IN, R), ('6', 'GPIO1', P_IN, R), ('7', 'GPIO2', P_IN, R),
    ('19', 'GPIO3', P_IN, R), ('26', 'GPIO4', P_IN, R), ('27', 'GPIO5', P_IN, R), ('37', 'GPIO6', P_IN, R),
    ('36', 'GPIO7', P_IN, R), ('13', 'GPIO11', P_OUT, R), (['15', '30', '40'], 'DRAIN', PAS, R),
    (['11', '12', '14', '31', '39'], 'GND', PWR_IN, B),
], 'atlas:Texas_REF0038A_WQFN-38-2EP_6x4mm_P0.4_Gap0.19', desc='USB-C PD controller with 5 A sink switch, drives the charger',
    mpn='TPS25751DREFR', mfr='Texas Instruments', width=25.4)

EEPROM_SO8 = Chip('M24512', [('8', 'VCC', PWR_IN, T), ('1', 'E0', P_IN, L), ('2', 'E1', P_IN, L), ('3', 'E2', P_IN, L),
                             ('7', '~{WC}', P_IN, L), ('5', 'SDA', BIDI, R), ('6', 'SCL', P_IN, R), ('4', 'VSS', PWR_IN, B)],
                  'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm', desc='512 kbit I2C EEPROM (TPS25751 configuration)',
                  mpn='M24512-RMN6TP', mfr='STMicroelectronics', width=12.7)

EEPROM_2K = Chip('24AA02', [('5', 'VCC', PWR_IN, T), ('3', 'SDA', BIDI, R), ('1', 'SCL', P_IN, R), ('4', 'WP', P_IN, L),
                            ('2', 'VSS', PWR_IN, B)],
                 'Package_TO_SOT_SMD:SOT-23-5', desc='2 kbit I2C EEPROM, board ID (address 0x50)',
                 mpn='24AA02T-I/OT', mfr='Microchip', width=10.16)

USBC16 = Chip('USB_C_16P', [
    (['A4', 'A9', 'B4', 'B9'], 'VBUS', PAS, L), ('A5', 'CC1', BIDI, L), ('B5', 'CC2', BIDI, L),
    (['A6', 'B6'], 'D+', BIDI, R), (['A7', 'B7'], 'D-', BIDI, R), ('A8', 'SBU1', BIDI, R), ('B8', 'SBU2', BIDI, R),
    (['A1', 'A12', 'B1', 'B12'], 'GND', PAS, B), ('SH', 'SHIELD', PAS, B),
], 'Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal', ref='J',
    desc='USB-C receptacle, USB 2.0, 5 A VBUS', mpn='USB4105-GF-A', mfr='GCT', width=15.24)

# ------------------------------------------------------------------ USB debug
USB2514B = Chip('USB2514B', [
    (['15', '23'], 'VDD33', PWR_IN, T), (['5', '10', '29', '36'], 'VDDA33', PWR_IN, T),
    ('30', 'USBDM_UP', BIDI, L), ('31', 'USBDP_UP', BIDI, L), ('27', 'VBUS_DET', P_IN, L), ('26', 'RESET_N', P_IN, L),
    ('33', 'XTALIN', P_IN, L), ('32', 'XTALOUT', P_OUT, L), ('35', 'RBIAS', PAS, L), ('14', 'CRFILT', PAS, L),
    ('34', 'PLLFILT', PAS, L), ('11', 'TEST', P_IN, L), ('24', 'SCL/CFG_SEL0', BIDI, L), ('25', 'HS_IND/CFG_SEL1', BIDI, L),
    ('22', 'SDA/NON_REM1', BIDI, L), ('28', 'SUSP_IND/NON_REM0', BIDI, L),
    ('1', 'DM_DN1', BIDI, R), ('2', 'DP_DN1', BIDI, R), ('3', 'DM_DN2', BIDI, R), ('4', 'DP_DN2', BIDI, R),
    ('6', 'DM_DN3', BIDI, R), ('7', 'DP_DN3', BIDI, R), ('8', 'DM_DN4', BIDI, R), ('9', 'DP_DN4', BIDI, R),
    ('12', 'PRTPWR1', P_OUT, R), ('16', 'PRTPWR2', P_OUT, R), ('18', 'PRTPWR3', P_OUT, R), ('20', 'PRTPWR4', P_OUT, R),
    ('13', 'OCS_N1', P_IN, R), ('17', 'OCS_N2', P_IN, R), ('19', 'OCS_N3', P_IN, R), ('21', 'OCS_N4', P_IN, R),
    ('37', 'VSS', PWR_IN, B),
], 'Package_DFN_QFN:QFN-36-1EP_6x6mm_P0.5mm_EP3.7x3.7mm', desc='USB 2.0 4-port hub',
    mpn='USB2514B-I/M2', mfr='Microchip', width=27.94)

CP2102N = Chip('CP2102N-QFN24', [
    ('6', 'VDD', PWR_IN, T), ('5', 'VIO', PWR_IN, T), ('7', 'VREGIN', PWR_IN, T),
    ('3', 'D+', BIDI, L), ('4', 'D-', BIDI, L), ('8', 'VBUS', P_IN, L), ('9', '~{RST}', P_IN, L),
    ('21', 'TXD', P_OUT, R), ('20', 'RXD', P_IN, R), ('19', '~{RTS}', P_OUT, R), ('18', '~{CTS}', P_IN, R),
    ('23', '~{DTR}', P_OUT, R), ('22', '~{DSR}', P_IN, R), ('24', '~{DCD}', P_IN, R), ('1', '~{RI}', P_IN, R),
    ('14', 'GPIO.0/TXT', BIDI, R), ('13', 'GPIO.1/RXT', BIDI, R), ('12', 'GPIO.2', BIDI, R), ('11', 'GPIO.3', BIDI, R),
    ('15', '~{SUSPEND}', P_OUT, R), ('17', 'SUSPEND', P_OUT, R), (['10', '16'], 'NC', NC, R),
    (['2', '25'], 'GND', PWR_IN, B),
], 'Package_DFN_QFN:QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm', desc='USB to UART bridge (Jetson serial console)',
    mpn='CP2102N-A02-GQFN24', mfr='Silicon Labs', width=20.32)

TS3USB30E = Chip('TS3USB30E', [('10', 'VCC', PWR_IN, T), ('4', 'D+', BIDI, L), ('6', 'D-', BIDI, L), ('1', 'S', P_IN, L),
                               ('9', '~{OE}', P_IN, L), ('2', 'D1+', BIDI, R), ('8', 'D1-', BIDI, R), ('3', 'D2+', BIDI, R),
                               ('7', 'D2-', BIDI, R), ('5', 'GND', PWR_IN, B)],
                 'Package_SO:MSOP-10_3x3mm_P0.5mm', desc='USB 2.0 1:2 mux, 1.1 GHz',
                 mpn='TS3USB30EDGSR', mfr='Texas Instruments', width=12.7)

USBLC6 = Chip('USBLC6-2SC6', [('1', 'IO1', PAS, L), ('3', 'IO2', PAS, L), ('6', 'IO1', PAS, R), ('4', 'IO2', PAS, R),
                              ('5', 'VBUS', PAS, T), ('2', 'GND', PAS, B)],
              'Package_TO_SOT_SMD:SOT-23-6', ref='D', desc='USB 2.0 ESD protection', mpn='USBLC6-2SC6', mfr='STMicroelectronics', width=10.16)
# note: pins 1/6 and 3/4 are the same line pass-through; keep them as separate pins so the router sees both pads

# ------------------------------------------------------------------ outputs and sensing
TPSM63610 = Chip('TPSM63610', [
    (['1', '18'], 'VIN', PWR_IN, T), ('17', 'EN', P_IN, L), ('15', 'SYNC/MODE', P_IN, L), ('14', 'SPSP', P_IN, L),
    ('12', 'RT', PAS, L), ('5', 'VLDOIN', PWR_IN, L), ('6', 'VCC', PWR_OUT, L), ('16', 'NC', NC, L),
    (['9', '10'], 'VOUT', PWR_OUT, R), ('8', 'FB', P_IN, R), ('13', 'PG', OC, R), ('2', 'RBOOT', PAS, R), ('3', 'CBOOT', PAS, R),
    ('4', 'SW', P_OUT, R),
    (['7', '11', '21', '22'], 'AGND', PWR_IN, B), (['19', '20'], 'PGND', PWR_IN, B),
], 'atlas:TI_RDF0022A_B3QFN-22_6.5x7.5mm', desc='36 V 8 A buck module with integrated inductor',
    mpn='TPSM63610RDFR', mfr='Texas Instruments', width=20.32)

TPS26600 = Chip('TPS26600', [
    (['1', '2'], 'IN', PWR_IN, T), ('3', 'UVLO', P_IN, L), ('5', 'OVP', P_IN, L), ('6', 'MODE', P_IN, L),
    ('7', '~{SHDN}', P_IN, L), ('12', 'dVdT', PAS, L), ('11', 'ILIM', PAS, L), ('10', 'IMON', P_OUT, L),
    (['15', '16'], 'OUT', PWR_OUT, R), ('14', '~{FLT}', OC, R), (['4', '13'], 'NC', NC, R),
    ('9', 'GND', PWR_IN, B), (['8', '17'], 'RTN', PWR_IN, B),
], 'Package_SO:HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm', desc='60 V 2.2 A eFuse (lidar supply, 1 A limit)',
    mpn='TPS26600PWPR', mfr='Texas Instruments', width=17.78)

INA228 = Chip('INA228', [('6', 'VS', PWR_IN, T), ('10', 'IN+', P_IN, L), ('9', 'IN-', P_IN, L), ('8', 'VBUS', P_IN, L),
                         ('2', 'A0', P_IN, L), ('1', 'A1', P_IN, L), ('5', 'SCL', P_IN, R), ('4', 'SDA', BIDI, R),
                         ('3', '~{ALERT}', OC, R), ('7', 'GND', PWR_IN, B)],
                 'Package_SO:MSOP-10_3x3mm_P0.5mm', desc='85 V 20-bit power/energy/charge monitor, I2C',
                 mpn='INA228AIDGSR', mfr='Texas Instruments', width=12.7)

LSM6DS3 = Chip('LSM6DS3TR-C', [(['5'], 'VDDIO', PWR_IN, T), ('8', 'VDD', PWR_IN, T), ('13', 'SCL', P_IN, L),
                               ('14', 'SDA', BIDI, L), ('1', 'SDO/SA0', P_IN, L), ('12', 'CS', P_IN, L),
                               ('4', 'INT1', P_OUT, R), ('9', 'INT2', P_OUT, R), ('2', 'SDX', P_IN, R), ('3', 'SCX', P_IN, R),
                               (['10', '11'], 'NC', NC, R), (['6', '7'], 'GND', PWR_IN, B)],
                  'Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y', desc='6-axis IMU (VESC lsm6ds3 driver, WHO_AM_I 0x6A)',
                  mpn='LSM6DS3TR-C', mfr='STMicroelectronics', width=15.24)

SN65HVD230 = Chip('SN65HVD230', [('3', 'VCC', PWR_IN, T), ('1', 'D', P_IN, L), ('4', 'R', P_OUT, L), ('8', 'Rs', P_IN, L),
                                 ('7', 'CANH', BIDI, R), ('6', 'CANL', BIDI, R), ('5', 'Vref', P_OUT, R), ('2', 'GND', PWR_IN, B)],
                     'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm', desc='3.3 V CAN transceiver',
                     mpn='SN65HVD230DR', mfr='Texas Instruments', width=12.7)


def logic5(name, a_name, a_num, b=None, y_type=P_OUT, mpn='', desc=''):
    pins = [('5', 'VCC', PWR_IN, T), (a_num, a_name, P_IN, L), ('4', 'Y', y_type, R), ('3', 'GND', PWR_IN, B)]
    if b:
        pins.append((b[1], b[0], P_IN, L))
    else:
        pins.append(('1', 'NC', NC, L))
    return Chip(name, pins, 'Package_TO_SOT_SMD:SOT-353_SC-70-5', desc=desc, mpn=mpn, mfr='Texas Instruments', width=10.16)


LVC1G08 = logic5('74LVC1G08', 'A', '1', ('B', '2'), mpn='SN74LVC1G08DCKR', desc='single 2-input AND (E-stop gate enable)')
AHCT1G125 = Chip('74AHCT1G125', [('5', 'VCC', PWR_IN, T), ('2', 'A', P_IN, L), ('1', '~{OE}', P_IN, L), ('4', 'Y', TRI, R),
                                 ('3', 'GND', PWR_IN, B)], 'Package_TO_SOT_SMD:SOT-353_SC-70-5',
                 desc='buffer with TTL input, 5 V output (servo signal)', mpn='SN74AHCT1G125DCKR', mfr='Texas Instruments', width=10.16)
LVC1G34 = logic5('74LVC1G34', 'A', '2', mpn='SN74LVC1G34DCKR', desc='single buffer, 5.5 V tolerant input')
LVC1G07 = logic5('74LVC1G07', 'A', '2', y_type=OC, mpn='SN74LVC1G07DCKR', desc='single buffer, open-drain output')


def conn(name, n, fp, mpn='', mfr='', desc='', ref='J', names=None, types=None):
    names = names or [str(i) for i in range(1, n + 1)]
    types = types or [PAS] * n
    pins = [(str(i + 1), names[i], types[i], L) for i in range(n)]
    return Chip(name, pins, fp, ref=ref, desc=desc, mpn=mpn, mfr=mfr, width=10.16)


NPN_SOT23 = Chip('MMBT3904', [('1', 'B', P_IN, L), ('3', 'C', PAS, T), ('2', 'E', PAS, B)], 'Package_TO_SOT_SMD:SOT-23',
                 ref='Q', desc='NPN 40 V, SOT-23 (used as a temperature diode)', mpn='MMBT3904LT1G', mfr='onsemi', width=7.62)

SJ2 = Chip('SolderJumper_2', [('1', '1', PAS, L), ('2', '2', PAS, R)], 'Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm',
           ref='JP', desc='solder jumper, open', width=5.08)

ESD4 = Chip('TPD4E05U06', [(['1', '10'], 'IO1', PAS, L), (['2', '9'], 'IO2', PAS, L), (['4', '7'], 'IO3', PAS, R),
                           (['5', '6'], 'IO4', PAS, R), (['3', '8'], 'GND', PAS, B)],
            'Package_SON:USON-10_2.5x1.0mm_P0.5mm', ref='D', desc='4-channel ESD, 0.5 pF, flow-through (USB)',
            mpn='TPD4E05U06DQAR', mfr='Texas Instruments', width=10.16)


# ------------------------------------------------------------------ brain board additions
# Parts that also appear on the Antmicro baseboard use Antmicro's footprints, which the PCB fork
# copies from the board itself (fork_pcb.py), so the pads are identical to the ones already there.
AM = 'antmicro-footprints:'

TPS259474 = Chip('TPS259474', [('5', 'IN', PWR_IN, L), ('1', 'EN/UVLO', P_IN, L), ('2', 'OVLO', P_IN, L),
                               ('9', 'ILIM', PAS, L), ('7', 'DVDT', PAS, L), ('10', 'ITIMER', PAS, L),
                               ('6', 'OUT', PWR_OUT, R), ('3', 'PG', OC, R), ('4', 'PGTH', P_IN, R),
                               ('8', 'GND', PWR_IN, B)],
                 AM + 'VQFN-HR-10_2x2mm', desc='2.7-23 V 5.5 A eFuse, adjustable OVLO, circuit breaker, auto-retry',
                 mpn='TPS259474ARPWR', mfr='Texas Instruments', width=15.24)

NTS0102 = Chip('NTS0102', [('3', 'VCCA', PWR_IN, T), ('7', 'VCCB', PWR_IN, T), ('6', 'OE', P_IN, L),
                           ('5', 'A1', BIDI, L), ('4', 'A2', BIDI, L), ('8', 'B1', BIDI, R), ('1', 'B2', BIDI, R),
                           ('2', 'GND', PWR_IN, B)],
               AM + 'XSON-8_1x1.95mm_P0.5mm', desc='2-bit auto-direction level translator (same part as the debug UART)',
               mpn='NTS0102GT', mfr='NXP', width=12.7)

NFET_SOT523 = Chip('PJE138K', [('1', 'G', P_IN, L), ('3', 'D', PAS, T), ('2', 'S', PAS, B)], AM + 'SOT-523',
                   ref='Q', desc='N-MOSFET 50 V, SOT-523 (Antmicro standard part)', mpn='PJE138K_R1_00001', mfr='PANJIT',
                   width=7.62)
PFET_SOT23 = Chip('SSM3J332R', [('1', 'G', P_IN, L), ('2', 'S', PAS, T), ('3', 'D', PAS, B)], AM + 'SOT-23-3',
                  ref='Q', desc='P-MOSFET -30 V, SOT-23 (Antmicro standard part)', mpn='SSM3J332R,LF', mfr='Toshiba',
                  width=7.62)
NFET_100V = Chip('CSD19538Q3A', [('4', 'G', P_IN, L), ('5', 'D', PAS, T), (['1', '2', '3'], 'S', PAS, B)],
                 'Package_SON:VSON-8_3.3x3.3mm_P0.65mm_NexFET', ref='Q',
                 desc='N-MOSFET 100 V, 49 mOhm at 10 V (58 at 6 V), Qg 4.3 nC, SON 3.3 x 3.3',
                 mpn='CSD19538Q3A', mfr='Texas Instruments', width=7.62)

LM5155 = Chip('LM5155', [('1', 'BIAS', PWR_IN, T), ('2', 'VCC', PWR_OUT, T), ('12', 'UVLO/SYNC', P_IN, L),
                         ('8', 'FB', P_IN, L), ('6', 'COMP', PAS, L), ('9', 'SS', PAS, L), ('10', 'RT', PAS, L),
                         ('3', 'GATE', P_OUT, R), ('5', 'CS', P_IN, R), ('11', 'PGOOD', OC, R),
                         ('4', 'PGND', PWR_IN, B), ('7', 'AGND', PWR_IN, B), ('13', 'EP', PWR_IN, B)],
              'Package_SON:WSON-12-1EP_3x2mm_P0.5mm_EP1x2.65', desc='boost controller, 3.5-45 V, 100 mV current limit',
              mpn='LM5155DSSR', mfr='Texas Instruments', width=17.78)

TPS23861 = Chip('TPS23861', [
    ('1', 'VDD', PWR_IN, T), ('28', 'VPWR', PWR_IN, T),
    ('2', 'RESET', P_IN, L), ('3', 'SCL', P_IN, L), ('4', 'SDAI', P_IN, L), ('5', 'SDAO', OC, L), ('6', 'INT', OC, L),
    ('23', 'A3', P_IN, L), ('24', 'SHTDWN', P_IN, L), ('25', 'AIN', P_IN, L), ('26', 'AOUT', OC, L), ('27', 'N/C', NC, L),
    ('17', 'GATE1', P_OUT, R), ('16', 'DRAIN1', P_IN, R), ('15', 'SEN1', P_IN, R), ('18', 'KSENSA', P_IN, R),
    ('21', 'GATE2', P_OUT, R), ('20', 'DRAIN2', P_IN, R), ('19', 'SEN2', P_IN, R),
    ('10', 'GATE3', P_OUT, R), ('9', 'DRAIN3', P_IN, R), ('8', 'SEN3', P_IN, R), ('11', 'KSENSB', P_IN, R),
    ('14', 'GATE4', P_OUT, R), ('13', 'DRAIN4', P_IN, R), ('12', 'SEN4', P_IN, R),
    ('7', 'DGND', PWR_IN, B), ('22', 'AGND', PWR_IN, B),
], 'Package_SO:TSSOP-28_4.4x9.7mm_P0.65mm', desc='IEEE 802.3at quad-port PSE controller, auto mode as shipped',
    mpn='TPS23861PWR', mfr='Texas Instruments', width=20.32)

LAN7800 = Chip('LAN7800', [
    (['14'], 'VDD_SW_IN', PWR_IN, T), ('46', 'VDD33_REG_IN', PWR_IN, T), ('38', 'VDD33A', PWR_IN, T),
    (['20', '36', '39'], 'VDDVARIO', PWR_IN, T), ('45', 'VDD25_REG_OUT', PWR_OUT, T),
    (['3', '6', '9', '12'], 'VDD25A', PWR_IN, T), ('13', 'VDD12_SW_OUT', PWR_OUT, T), ('15', 'VDD12_SW_FB', P_IN, T),
    (['21', '42'], 'VDD12CORE', PWR_IN, T), (['25', '30', '44'], 'VDD12A', PWR_IN, T),
    ('26', 'USB2_DP', BIDI, L), ('27', 'USB2_DM', BIDI, L), ('28', 'USB3_TXDP', P_OUT, L), ('29', 'USB3_TXDM', P_OUT, L),
    ('31', 'USB3_RXDP', P_IN, L), ('32', 'USB3_RXDM', P_IN, L), ('37', 'USBRBIAS', PAS, L), ('23', 'VBUS_DET', P_IN, L),
    ('35', 'RESET_N', P_IN, L), ('34', 'TEST', P_IN, L), ('40', 'XI', P_IN, L), ('41', 'XO', P_OUT, L),
    ('43', 'PME_MODE', P_IN, L), ('22', 'PME_N', OC, L), ('24', 'SUSPEND_N', P_OUT, L),
    ('16', 'EECS', P_OUT, L), ('17', 'EEDI', P_IN, L), ('18', 'EEDO/LED0', P_OUT, L), ('19', 'EECLK/LED1', P_OUT, L),
    ('33', 'LED3', P_OUT, L),
    ('1', 'TR0P', BIDI, R), ('2', 'TR0N', BIDI, R), ('4', 'TR1P', BIDI, R), ('5', 'TR1N', BIDI, R),
    ('7', 'TR2P', BIDI, R), ('8', 'TR2N', BIDI, R), ('10', 'TR3P', BIDI, R), ('11', 'TR3N', BIDI, R),
    ('47', 'REF_REXT', PAS, R), ('48', 'REF_FILT', PAS, R),
    ('49', 'VSS', PWR_IN, B),
], 'Package_DFN_QFN:QFN-48-1EP_7x7mm_P0.5mm_EP5.3x5.3mm_ThermalVias',
    desc='USB 3.1 Gen 1 / USB 2.0 to 10/100/1000 Ethernet bridge with PHY', mpn='LAN7800-I/Y9X', mfr='Microchip',
    width=30.48)

RJ45_MAG = Chip('RJ45_PoE_MagJack', [
    ('1', 'P1', PAS, L), ('2', 'P2', PAS, L), ('3', 'P3', PAS, L), ('6', 'P6', PAS, L), ('7', 'P7', PAS, L),
    ('8', 'P8', PAS, L), ('9', 'P9', PAS, L), ('10', 'P10', PAS, L), ('4', 'P4', PAS, L), ('5', 'P5', PAS, L),
    ('11', 'VC1', PAS, R), ('12', 'VC2', PAS, R), ('13', 'VC3', PAS, R), ('14', 'VC4', PAS, R),
    ('15', 'LED_GRN+', PAS, R), ('16', 'LED_GRN-', PAS, R), ('17', 'LED_YEL+', PAS, R), ('18', 'LED_YEL-', PAS, R),
    (['19', '20'], 'SHIELD', PAS, B),
], AM + 'RJ45_X-2337992-8_Horizontal', ref='J', desc='RJ45 with magnetics and PoE centre taps (same jack as the camera port)',
    mpn='5-2337992-8', mfr='TE Connectivity', width=20.32)
