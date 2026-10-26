"""Electrical checks on the ATLAS-PWR-1 netlist (atlas_power_parts.json), in place of an ERC: the schematic
is KiCad 9 format and the build container has KiCad 7.

    python3 boards/power/netcheck.py            # prints every check, exits 1 on any error

Structural checks
  1  every IC/module input or power pin is connected (no floating inputs; NC pins must be no_connect/passive)
  2  no single-pin nets (except the declared test-only nets)
  3  every IC supply pin has a capacitor to GND on its net
  4  isolation: the BMS-side nets (switched B- domain) form their own galvanic island; only the PC817 LED/transistor
     gap joins them to board GND (rev A review P-M1)
  5  supply domains: no conductive path (wire, fuse, diode, < 1 kOhm, FET/BJT channel, regulator) from the laptop's
     HUB_VBUS domain into a board supply, or back
  6  dev-kit J12 rules (C_jetson_mech.md section 5): pins 1, 2, 4, 24, 37, 39, 40 open; signal pins touch only
     resistors; board outputs toward the Jetson behind a series resistor of 1k to 10k (1k: the dev kit level-shifts
     these pins with TXB-type translators that hold a pin through about 4k, review M1); pull resistors >= 50k
 14  ground splits: CHG_GND (charger side, review B1) joins GND only through the CC/CV module (IN- to OUT-, its
     current shunt); COMM_GND, SRVIN_GND and VUSB_GND (FSESC signal grounds, review M6) each reach GND through
     exactly one 2.2-4.7 Ohm resistor and touch nothing but their connector pin
Operating-point checks (a small piecewise-linear DC solver: resistors, diodes with forward drop and reverse
breakdown, BJTs and MOSFETs that switch on when driven, optocouplers, the TL431, ESD clamp diodes on IC pins),
run for every scenario in SCENARIOS (normal run, 30 V spike on the pack bus, 30 V on the charge input,
everything pulsed, board off with the Jetson/laptop/ESC powered, laptop unplugged, ESC unpowered, dev kit off with
the ESC and the laptop on):
  7  every IC/module pin within its absolute maximum rating (table PIN_LIMITS, sources in the comments)
  8  MOSFET |VGS| and VDS, BJT VCE within rating
  9  resistor power <= 50 % of rating in the nominal scenarios; the precharge resistor's pulse energy separately
 10  capacitor voltage <= rating (electrolytics <= 80 % in the nominal scenarios)
 11  no TVS or zener conducts in a nominal scenario (except the charger-present zener, which is meant to)
 12  LED current <= 20 mA
 13  back-power: current into an unpowered IC through its pin clamp diodes <= 0.5 mA (warning above 0.05 mA).
     The four 1k-fed dev-kit inputs (BACKPOWER_1K) are allowed up to 3 mA as a warning: TXB0108-class translators
     list partial power-down (Ioff), so the real current is likely far lower (unverified for the Orin Nano carrier)
"""
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = json.load(open(os.path.join(HERE, 'atlas_power_parts.json')))
PARTS = {p['ref']: p for p in DATA['parts']}

errors, warnings, notes = [], [], []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def pin_net(p, name):
    for num, nm in p['pinnames'].items():
        if nm == name:
            return p['pads'].get(num)
    raise KeyError(f"{p['ref']} has no pin {name}")


def nets_of(p):
    return sorted(set(v for v in p['pads'].values() if v))


def parse_value(v):
    m = re.match(r'^\s*([0-9.]+)\s*([pnumkKM]?)', v)
    if not m:
        return None
    mult = {'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'm': 1e-3, 'k': 1e3, 'K': 1e3, 'M': 1e6, '': 1.0}[m.group(2)]
    return float(m.group(1)) * mult


def kind(p):
    r = p['ref']
    return re.match(r'^[A-Z]+', r).group(0)


NETS = {}
for p in PARTS.values():
    for num, n in p['pads'].items():
        if n:
            NETS.setdefault(n, []).append((p['ref'], num))

# ============================================================================ 1-3 structural
TEST_ONLY = {'J12_GPIO09', 'J12_GPIO12', 'FAN_TACH', 'PICO_RUN', 'J12_CTS', 'J12_SDA', 'J12_SCL', 'I2C0_SDA',
             'I2C0_SCL'}
NC_OK = {('MOD', '3V3_EN'): 'Pico 3V3_EN has a 100k pull-up to VSYS on the module',
         ('MOD', 'RUN'): 'Pico RUN has an internal pull-up; brought to a test pad'}


def check_structure():
    n_in = 0
    for p in PARTS.values():
        k = kind(p)
        if k not in ('U', 'MOD', 'Q'):
            continue
        for num, typ in p['pintypes'].items():
            net = p['pads'].get(num)
            nm = p['pinnames'][num]
            if net is None and typ in ('input', 'power_in'):
                if (k, nm) in NC_OK:
                    continue
                err(f"[1] {p['ref']} {p['value']} pin {num} {nm} ({typ}) is not connected")
            n_in += 1
    print(f'[1] checked {n_in} IC/module/transistor pins for floating inputs')
    single = [(n, v) for n, v in NETS.items() if len(v) < 2]
    for n, v in single:
        if n not in TEST_ONLY:
            err(f'[2] single-pin net {n}: {v}')
    # test-only nets: a pin plus a test pad, or a DNP part
    print(f'[2] {len(NETS)} nets, {len(single)} with one pin (allowed: {sorted(set(n for n, _ in single) & TEST_ONLY)})')
    caps = {}
    for p in PARTS.values():
        if kind(p) == 'C' and not p['dnp']:
            a, b = p['pads'].get('1'), p['pads'].get('2')
            for x, y in ((a, b), (b, a)):
                if y == 'GND' or (x and x.startswith('BMS') and y == 'BMS_GND'):
                    caps.setdefault(x, []).append(p['ref'])
    nsup = 0
    for p in PARTS.values():
        if kind(p) != 'U':
            continue
        for num, typ in p['pintypes'].items():
            net = p['pads'].get(num)
            if typ == 'power_in' and net and net != 'GND':
                nsup += 1
                if not caps.get(net):
                    err(f"[3] {p['ref']} supply pin {p['pinnames'][num]} on {net} has no capacitor to GND")
    print(f'[3] {nsup} IC supply pins have a capacitor to GND on their net' if not any('[3]' in e for e in errors)
          else '[3] decoupling problems listed')


# ============================================================================ 4 isolation, 5 supply domains
class UF:
    def __init__(self):
        self.p = {}

    def f(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def u(self, a, b):
        self.p[self.f(a)] = self.f(b)


def check_isolation():
    uf = UF()
    for p in PARTS.values():
        if p['value'] == 'PC817':
            groups = [[pin_net(p, 'A'), pin_net(p, 'K')], [pin_net(p, 'C'), pin_net(p, 'E')]]
        else:
            groups = [nets_of(p)]
        for g in groups:
            g = [n for n in g if n]
            for n in g:
                uf.f(n)
            for a, b in zip(g, g[1:]):
                uf.u(a, b)
    island = sorted(n for n in NETS if uf.f(n) == uf.f('BMS_GND'))
    if uf.f('BMS_GND') == uf.f('GND'):
        err('[4] the BMS-side domain is galvanically joined to board GND')
    else:
        print(f'[4] BMS-side island (isolated from GND by U201/U202 only): {island}')
    bridges = [p['ref'] for p in PARTS.values() if p['value'] == 'PC817'
               and uf.f(pin_net(p, 'A')) != uf.f(pin_net(p, 'C'))]
    print(f'[4] optocouplers that bridge two domains: {bridges}')


BOARD_SUPPLIES = {'BAT', 'VM', 'VSYS_SW', 'V5_IN', '+5V', '+3V3', 'PICO_VSYS', 'VDEV_F', 'VDEV', 'SERVO_V', 'LIDAR_V',
                  'LID_SW', 'CAM_VIN', 'CHG_IN', 'CHG_OUT', 'CHG_RB'}
HUB_SUPPLIES = {'HUB_VBUS', 'CON_3V3'}


def conductive_edges():
    """(net_a, net_b, ref) pairs joined by a low-impedance path (either direction, conservative)."""
    e = []
    for p in PARTS.values():
        if p['dnp']:
            continue
        k, v = kind(p), p['value']
        pads = p['pads']
        if k == 'R':
            r = parse_value(v)
            if r is not None and r < 1000:
                e.append((pads['1'], pads['2'], p['ref']))
        elif k in ('F', 'D') and v.upper() not in ('RED', 'GREEN'):
            e.append((pads['1'], pads['2'], p['ref']))
        elif k == 'Q':
            names = {nm: pads.get(num) for num, nm in p['pinnames'].items()}
            if 'D' in names:
                e.append((names['D'], names['S'], p['ref']))
            else:
                e.append((names['C'], names['E'], p['ref']))
        elif k in ('U', 'MOD'):
            names = {nm: pads.get(num) for num, nm in p['pinnames'].items()}
            for a, b in (('VIN', 'VOUT'), ('IN+', 'OUT+'), ('VDD', 'VUSB')):
                if names.get(a) and names.get(b):
                    e.append((names[a], names[b], p['ref']))
    return [(a, b, r) for a, b, r in e if a and b and 'GND' not in (a, b)]


def check_domains():
    edges = conductive_edges()
    adj = {}
    for a, b, r in edges:
        adj.setdefault(a, []).append((b, r))
        adj.setdefault(b, []).append((a, r))

    def reach(start):
        seen, stack, path = {start}, [start], {start: []}
        while stack:
            x = stack.pop()
            for y, r in adj.get(x, []):
                if y not in seen:
                    seen.add(y)
                    path[y] = path[x] + [r]
                    stack.append(y)
        return seen, path
    bad = False
    for s in HUB_SUPPLIES:
        seen, path = reach(s)
        hit = seen & BOARD_SUPPLIES
        for h in sorted(hit):
            err(f'[5] laptop domain {s} reaches board supply {h} through {path[h]}')
            bad = True
    if not bad:
        seen, _ = reach('HUB_VBUS')
        print(f'[5] laptop VBUS domain is closed: {sorted(seen)}; no path to {sorted(BOARD_SUPPLIES)[:6]}...')


def check_j12():
    j = next(p for p in PARTS.values() if p['value'] == 'J12_RIBBON')
    num_net = {int(n): v for n, v in j['pads'].items()}
    for n in (1, 2, 4, 24, 37, 39, 40):
        if num_net.get(n):
            err(f'[6] J12 pin {n} must stay open, is on {num_net[n]}')
    outputs = {10: 'UART1_RXD', 32: 'GPIO07', 33: 'GPIO13'}
    for n, net in sorted(num_net.items()):
        if not net or net == 'GND' or n == 17:
            continue
        others = [(r, num) for r, num in NETS[net] if r != j['ref']]
        for r, num in others:
            k = kind(PARTS[r])
            if k not in ('R', 'TP'):
                err(f'[6] J12 pin {n} ({net}) touches {r} directly; only resistors allowed')
        rs = [PARTS[r] for r, _ in others if kind(PARTS[r]) == 'R' and not PARTS[r]['dnp']]
        if n in outputs:
            # 1k minimum: the dev kit's TXB-type translators hold a pin through about 4k, so 10k never toggled
            # them (review M1); 1k bounds back-power into an unpowered dev kit to about 2.8 mA (see [13])
            series = [parse_value(p['value']) for p in rs if 'GND' not in nets_of(p)]
            if not series or min(series) < 1e3 or max(series) > 1.5e3:
                err(f'[6] J12 pin {n} is a board output toward the Jetson without a 1k series resistor')
        for p in rs:
            other = [x for x in nets_of(p) if x != net][0]
            if other in ('GND', '+3V3', '+5V') and parse_value(p['value']) < 50e3:
                err(f"[6] J12 pin {n}: pull resistor {p['ref']} {p['value']} is under 50k")
    print('[6] J12: open pins, series resistors and pull values checked')


def check_ground_splits():
    """[14] CHG_GND meets GND only inside the CC/CV module; each FSESC signal ground reaches GND through one
    2.2-4.7 Ohm resistor."""
    cc = next(p for p in PARTS.values() if p['value'] == 'CCCV_BUCK_XL4015')
    if pin_net(cc, 'IN-') != 'CHG_GND' or pin_net(cc, 'OUT-') != 'GND':
        err(f"[14] {cc['ref']} must have IN- on CHG_GND and OUT- on GND (its current shunt is between them)")
    for p in PARTS.values():
        ns = nets_of(p)
        if 'CHG_GND' in ns and 'GND' in ns and p['ref'] != cc['ref']:
            err(f"[14] {p['ref']} {p['value']} touches both CHG_GND and GND: the charge current would bypass the shunt")
    want = {('ADA5807_HUSB238', 'GND'), ('P6KE24A', None), ('10u 50V', None)}
    on = sorted({p['ref'] for r, _ in NETS.get('CHG_GND', []) for p in [PARTS[r]]})
    for val, pin in want:
        hit = [p for p in PARTS.values() if p['value'] == val and 'CHG_IN' in nets_of(p)]
        if not hit or any('CHG_GND' not in nets_of(p) for p in hit):
            err(f'[14] {val} on CHG_IN must return to CHG_GND')
    for q in (p for p in PARTS.values() if p['value'] == '2N3904' and ({'CHG_C', 'CHG_PRESENT_N'} & set(nets_of(p)))):
        if pin_net(q, 'E') != 'CHG_GND':
            err(f"[14] charger-present/enable transistor {q['ref']} must have its emitter on CHG_GND")
    print(f"[14] CHG_GND joins GND only through {cc['ref']} (IN- to OUT-); on CHG_GND: {on}")
    for net in ('COMM_GND', 'SRVIN_GND', 'VUSB_GND'):
        users = [PARTS[r] for r, _ in NETS.get(net, [])]
        rs = [p for p in users if kind(p) == 'R']
        others = [p['ref'] for p in users if kind(p) not in ('R', 'J')]
        ok = (len(rs) == 1 and nets_of(rs[0]) == sorted([net, 'GND']) and 2.2 <= parse_value(rs[0]['value']) <= 4.7
              and not others)
        if not ok:
            err(f'[14] {net} must reach GND through exactly one 2.2-4.7 Ohm resistor and touch only its connector')
        else:
            print(f"[14] {net}: {', '.join(p['ref'] for p in users if kind(p) == 'J')} -> {rs[0]['ref']} "
                  f"{rs[0]['value']} Ohm -> GND")


# ============================================================================ DC operating point
VF = {'RED': 1.8, 'GREEN': 2.0, '1N5817': 0.3, 'BAT85': 0.3, 'Si': 0.65}
# reverse breakdown (V) and dynamic resistance (Ohm) of the TVS/zeners: VBR nominal, (VC - VBR) / IPP
VBR = {'1.5KE20A': (20.0, 0.14), '1.5KE22A': (22.0, 0.16), 'P6KE20A': (20.0, 0.35), 'P6KE22A': (22.0, 0.44),
       'P6KE24A': (24.0, 0.62), '1N5247B': (17.0, 30.0)}
PFETS = {'IRF9Z34NPBF', 'IRF4905PBF'}
RON = {'IRFB7430PBF': 0.002, 'IRF4905PBF': 0.02}      # others 0.1 Ohm (IRF9Z34N at -10 V; 2N7000 is a signal switch)
TVS_INTENDED = {'1N5247B'}          # the charger-present zener conducts by design


class Circuit:
    def __init__(self, fixed, switches_closed=()):
        self.fixed = dict(fixed)
        self.el = []                       # (type, data)
        self.switches_closed = set(switches_closed)

    def add(self, typ, **kw):
        self.el.append([typ, kw])


ESD_RAIL = {}          # (ref) -> supply net of that IC's pin clamps


def build(fixed, closed=(), ptc_tripped=False):
    c = Circuit(fixed, closed)
    for p in PARTS.values():
        if p['dnp']:
            continue
        k, v, pads = kind(p), p['value'], p['pads']
        names = {nm: pads.get(num) for num, nm in p['pinnames'].items()}
        if k == 'R':
            c.add('R', a=pads['1'], b=pads['2'], r=parse_value(v), ref=p['ref'])
        elif k == 'TH':
            c.add('R', a=pads['1'], b=pads['2'], r=10e3, ref=p['ref'])
        elif k == 'F':
            c.add('R', a=pads['1'], b=pads['2'], r=0.01 if v.startswith('5A') else 0.5, ref=p['ref'])
        elif k == 'SW':
            if p['ref'] in closed:
                c.add('R', a=pads['1'], b=pads['2'], r=0.1, ref=p['ref'])
        elif k == 'D':
            an, ca = pads['2'], pads['1']
            if v.upper() in ('RED', 'GREEN'):
                c.add('D', a=an, k=ca, vf=VF[v.upper()], rd=20.0, vbr=None, ref=p['ref'], led=True)
            elif v in VBR:
                c.add('D', a=an, k=ca, vf=0.8, rd=0.2, vbr=VBR[v][0], rbr=VBR[v][1], ref=p['ref'], name=v)
            else:
                c.add('D', a=an, k=ca, vf=VF.get(v, 0.65), rd=0.2, vbr=None, ref=p['ref'])
        elif k == 'Q':
            if 'B' in names:
                c.add('BJT', b=names['B'], c=names['C'], e=names['E'], pnp=p['value'] == '2N3906', ref=p['ref'])
            else:
                c.add('FET', g=names['G'], d=names['D'], s=names['S'], pch=p['value'] in PFETS, ref=p['ref'],
                      ron=RON.get(p['value'], 0.1))
        elif k == 'U' and v == 'PC817':
            c.add('OPTO', a=names['A'], k=names['K'], c=names['C'], e=names['E'], ref=p['ref'])
        elif k == 'U' and v == 'TL431':
            c.add('TL431', ref_=names['REF'], k=names['K'], a=names['A'], ref=p['ref'])
        elif k == 'U' and v == '74HCT08':
            for g in '1234':
                if names.get(g + 'Y'):
                    c.add('AND', a=names[g + 'A'], b=names[g + 'B'], y=names[g + 'Y'], vcc=names['VCC'],
                          ref=f"{p['ref']}.{g}Y")
        elif k == 'U' and v == 'MIC5014':
            c.add('GDRV', i=names['IN'], vp=names['V+'], g=names['GATE'], s=names['SOURCE'], ref=p['ref'])
    # outside the board: the E-stop loop (closed unless the scenario opens it), the Pololu ON/OFF inputs
    # (about 20k to GND each: Pololu's input diagram shows 10k + 10k), the CC/CV buck output (sources, cannot sink)
    if 'ESTOP_OPEN' not in closed:
        c.add('R', a='ESTOP_SRC', b='ESTOP_IN', r=0.1, ref='ext.estop_loop')
    c.add('R', a='LATCH_ON', b='GND', r=20e3, ref='ext.pololu_on')
    c.add('R', a='LATCH_OFF_M', b='GND', r=20e3, ref='ext.pololu_off')
    if 'CHG_SRC' in fixed:
        c.add('D', a='CHG_SRC', k='CHG_OUT', vf=0.01, rd=0.05, vbr=None, ref='ext.buck_out')
        c.add('R', a='CHG_OUT', b='GND', r=10e3, ref='ext.buck_fb')
    # inside the CC/CV module: its current shunt between IN- (CHG_GND) and OUT- (GND), about 0.05 Ohm (review B1)
    cc = next(p for p in PARTS.values() if p['value'] == 'CCCV_BUCK_XL4015')
    c.add('R', a=pin_net(cc, 'IN-'), b=pin_net(cc, 'OUT-'), r=0.05, ref='ext.cccv_shunt')
    # ESD clamp diodes of IC pins toward their supply (and from GND), used for clamp and back-power checks
    for ref, rail, pins in ESD:
        p = PARTS[ref]
        for nm in pins:
            n = pin_net(p, nm)
            if n:
                c.add('D', a=n, k=rail, vf=0.5, rd=50.0, vbr=None, ref=f'{ref}.{nm}>esd', esd=(ref, nm, rail))
                c.add('D', a='GND', k=n, vf=0.5, rd=50.0, vbr=None, ref=f'{ref}.{nm}<esd', esd=(ref, nm, 'GND'))
    for net, rail in EXT_ESD:
        c.add('D', a=net, k=rail, vf=0.5, rd=50.0, vbr=None, ref=f'ext.{net}>esd', esd=('ext', net, rail))
    c.add('R', a='VM', b='GND', r=1e3, ref='ext.esc_bleed')
    for net, src, r in EXT_PULL:
        c.add('R', a=net, b=src, r=r, ref=f'ext.{net}')
    return c


PICO_IO = ['GP0', 'GP1', 'GP2', 'GP3', 'GP4', 'GP5', 'GP6', 'GP7', 'GP8', 'GP9', 'GP10', 'GP11', 'GP12', 'GP13', 'GP14',
           'GP15', 'GP16', 'GP17', 'GP18', 'GP19', 'GP20', 'GP21', 'GP22', 'GP26_ADC0', 'GP27_ADC1', 'GP28_ADC2']
_pico = next(p['ref'] for p in PARTS.values() if p['value'] == 'RPi_Pico')
_mcp = next(p['ref'] for p in PARTS.values() if p['value'] == 'MCP2221A')
_hct = next(p['ref'] for p in PARTS.values() if p['value'] == '74HCT08')
ESD = [(_pico, '+3V3', PICO_IO), (_mcp, 'CON_3V3', ['URx', 'UTx', '~{RST}']),
       (_hct, '+5V', ['1A', '1B', '2A', '2B', '3A', '3B'])]
# outside the board: the pins of the FSESC, the Jetson and the JBD our nets drive into
EXT_ESD = [('COMM_RX', 'ESC_3V3'), ('COMM_ADC2', 'ESC_3V3'), ('J12_RXD', 'J12_3V3'), ('J12_ESTOP_OK', 'J12_3V3'),
           ('J12_CHG_STAT_N', 'J12_3V3'), ('J14_CON_RXD', 'J12_3V3'), ('BMS_RXD', 'BMS_VDD')]
# carrier pull-ups on J14 (assumed 10k; SLEEP/WAKE* is a 5 V signal, the reset and recovery lines 1.8 V)
EXT_PULL = [('J14_PWR_KEY_N', 'J14_5V', 10e3), ('J14_RESET_N', 'J14_1V8', 10e3), ('J14_RECOVERY_N', 'J14_1V8', 10e3)]


def solve(c, iters=200):
    nodes = sorted({n for typ, kw in c.el for k2, n in kw.items() if isinstance(n, str) and k2 in
                    ('a', 'b', 'k', 'c', 'e', 'g', 'd', 's', 'ref_', 'y', 'vcc', 'i', 'vp')} - set(c.fixed) - {'GND'})
    idx = {n: i for i, n in enumerate(nodes)}
    state = {}
    V = {n: 0.0 for n in nodes}
    V.update(c.fixed)

    def v(n):
        return V.get(n, 0.0)
    for it in range(iters):
        N = len(nodes)
        G = np.zeros((N, N))
        I = np.zeros(N)
        for i in range(N):
            G[i, i] += 1e-9

        def cond(a, b, g, vs=0.0):
            # current a->b = g * (Va - Vb - vs)
            for x, sgn in ((a, 1), (b, -1)):
                if x in idx:
                    G[idx[x], idx[x]] += g
                    I[idx[x]] += sgn * g * vs
            if a in idx and b in idx:
                G[idx[a], idx[b]] -= g
                G[idx[b], idx[a]] -= g
            if a in idx and b not in idx:
                I[idx[a]] += g * v(b)
            if b in idx and a not in idx:
                I[idx[b]] += g * v(a)
        for typ, kw in c.el:
            r = kw['ref']
            if typ == 'R':
                if kw['a'] in idx or kw['b'] in idx:
                    cond(kw['a'], kw['b'], 1.0 / kw['r'])
            elif typ == 'D':
                st = state.get(r, 'off')
                if st == 'fwd':
                    cond(kw['a'], kw['k'], 1.0 / kw['rd'], kw['vf'])
                elif st == 'rev':
                    cond(kw['k'], kw['a'], 1.0 / kw['rbr'], kw['vbr'])
            elif typ == 'BJT':
                bn, cn, en = kw['b'], kw['c'], kw['e']
                if kw['pnp']:
                    if state.get(r + 'be') == 'on':
                        cond(en, bn, 1 / 100.0, 0.65)
                    if state.get(r + 'ce') == 'on':
                        cond(en, cn, 1 / 10.0)
                else:
                    if state.get(r + 'be') == 'on':
                        cond(bn, en, 1 / 100.0, 0.65)
                    if state.get(r + 'ce') == 'on':
                        cond(cn, en, 1 / 10.0)
            elif typ == 'FET':
                if state.get(r) == 'on':
                    cond(kw['d'], kw['s'], 1 / kw['ron'])
            elif typ == 'OPTO':
                if state.get(r + 'led') == 'on':
                    cond(kw['a'], kw['k'], 1 / 20.0, 1.2)
                if state.get(r + 'ce') == 'on':
                    cond(kw['c'], kw['e'], 1 / 200.0)
            elif typ == 'TL431':
                if state.get(r) == 'on':
                    cond(kw['k'], kw['a'], 1 / 100.0, 2.0)
            elif typ == 'AND':
                # 50 Ohm output to VCC when both inputs are above VIH (2.0 V) and VCC is up, else to GND
                cond(kw['y'], kw['vcc'] if state.get(r) == 'hi' else 'GND', 1 / 50.0)
            elif typ == 'GDRV':
                # MIC5014 asserted: gate = SOURCE + 15 V (clamp) through 1k (charge pump); else gate pulled to GND
                if state.get(r) == 'on':
                    cond(kw['g'], kw['s'], 1 / 1000.0, 15.0)
                else:
                    cond(kw['g'], 'GND', 1 / 10e3)
        sol = np.linalg.solve(G, I) if nodes else []
        for n, i in idx.items():
            V[n] = float(sol[i])
        new = {}
        for typ, kw in c.el:
            r = kw['ref']
            if typ == 'D':
                vd = v(kw['a']) - v(kw['k'])
                st = state.get(r, 'off')
                if st == 'fwd':
                    new[r] = 'fwd' if (vd - kw['vf']) / kw['rd'] > -1e-7 else 'off'
                elif st == 'rev':
                    new[r] = 'rev' if (-vd - kw['vbr']) / kw['rbr'] > -1e-7 else 'off'
                else:
                    new[r] = 'fwd' if vd > kw['vf'] + 1e-4 else ('rev' if kw['vbr'] and -vd > kw['vbr'] + 1e-4 else 'off')
            elif typ == 'BJT':
                vbe = (v(kw['e']) - v(kw['b'])) if kw['pnp'] else (v(kw['b']) - v(kw['e']))
                st = state.get(r + 'be', 'off')
                on = vbe > 0.65 - (1e-6 if st == 'on' else -1e-4)
                new[r + 'be'] = 'on' if on else 'off'
                new[r + 'ce'] = 'on' if on else 'off'
            elif typ == 'FET':
                vgs = v(kw['g']) - v(kw['s'])
                new[r] = 'on' if ((-vgs) if kw['pch'] else vgs) > 3.0 else 'off'
            elif typ == 'OPTO':
                vd = v(kw['a']) - v(kw['k'])
                st = state.get(r + 'led', 'off')
                on = vd > 1.2 - (1e-6 if st == 'on' else -1e-4)
                new[r + 'led'] = 'on' if on else 'off'
                new[r + 'ce'] = 'on' if on and (vd - 1.2) / 20.0 > 0.3e-3 else 'off'
            elif typ == 'TL431':
                new[r] = 'on' if v(kw['ref_']) - v(kw['a']) > 2.495 else 'off'
            elif typ == 'AND':
                new[r] = 'hi' if (v(kw['vcc']) > 4.5 and v(kw['a']) > 2.0 and v(kw['b']) > 2.0) else 'lo'
            elif typ == 'GDRV':
                new[r] = 'on' if (v(kw['vp']) > 3.0 and v(kw['i']) - 0 > 2.0) else 'off'
        if new == state:
            return V, state, it
        state = new
    return V, state, -1


def dcur(kw, V, state):
    """current through a diode element, anode -> cathode"""
    st = state.get(kw['ref'], 'off')
    vd = V.get(kw['a'], 0) - V.get(kw['k'], 0)
    if st == 'fwd':
        return (vd - kw['vf']) / kw['rd']
    if st == 'rev':
        return -(-vd - kw['vbr']) / kw['rbr']
    return 0.0


# --------------------------------------------------------------------------- scenarios
PICO_RUN = {'BMS_TX': 3.3, 'PRECHARGE_EN': 0.0, 'MAIN_EN': 3.3, 'LIDAR_EN': 3.3, 'JETSON_PWR_KEY': 0.0,
            'JETSON_RESET': 0.0, 'LATCH_OFF': 0.0, 'VESC_KILL': 3.3, 'FAN_PWM': 3.3, 'LED_STATUS': 3.3,
            'LED_FAULT': 0.0, 'ESTOP_OK_TO_JETSON': 3.3, 'CHG_STAT_N_TO_JETSON': 3.3, 'DEVKIT_PWR': 3.3}
PICO_PULSE = dict(PICO_RUN, PRECHARGE_EN=3.3, JETSON_PWR_KEY=3.3, JETSON_RESET=3.3, LATCH_OFF=3.3, BMS_TX=0.0,
                  LED_FAULT=3.3, FAN_PWM=0.0)


def world(bat=16.8, on=True, laptop=True, jetson=True, esc=True, charger=True, chg_in=21.0, pico=None):
    f = {'GND': 0.0, 'BAT': bat, 'BMS_GND': 0.0, 'BMS_VDD': 5.0, 'BMS_TXD': 5.0}
    if on:
        f.update({'VSYS_SW': bat, '+5V': 5.0, '+3V3': 3.3, 'SERVO_V': 8.4})
        f.update(pico if pico is not None else PICO_RUN)
    else:
        f.update({'VSYS_SW': 0.0, '+5V': 0.0, '+3V3': 0.0, 'PICO_VSYS': 0.0, 'SERVO_V': 0.0})
    if laptop:
        f.update({'HUB_VBUS': 5.25, 'CON_3V3': 3.3})
    else:
        f.update({'HUB_VBUS': 0.0, 'CON_3V3': 0.0})
    if jetson:
        f.update({'J12_3V3': 3.3, 'J12_TXD': 3.3, 'J12_JETSON_UP': 3.3, 'J12_LIDAR_REQ': 3.3, 'J14_CON_TXD': 3.3,
                  'J14_5V': 5.0, 'J14_1V8': 1.8})
    else:
        f.update({'J12_3V3': 0.0, 'J14_5V': 0.0, 'J14_1V8': 0.0})
    if esc:
        f.update({'ESC_3V3': 3.3, 'COMM_TX': 3.3, 'SERVO_IN_J': 3.3})
    else:
        f.update({'ESC_3V3': 0.0})
    if charger:
        f.update({'CHG_IN': chg_in, 'CHG_SRC': min(16.8, chg_in)})
    else:
        f.update({'CHG_IN': 0.0})
    return f


SCENARIOS = [
    ('run, pack 16.8 V, charger, laptop, Jetson, ESC on', world(), set(), True),
    ('run, pack 12.0 V (low end)', world(bat=12.0, charger=False), set(), True),
    ('every Pico output pulsed, both buttons held', world(pico=PICO_PULSE), {'SW401', 'SW801'}, True),
    ('30 V spike on the pack bus while running', world(bat=30.0), set(), False),
    ('30 V spike on the pack bus, outputs pulsed', world(bat=30.0, pico=PICO_PULSE), {'SW401'}, False),
    ('30 V on the charge input', world(chg_in=30.0), set(), False),
    ('board off (pack in), button held', world(on=False, laptop=False, jetson=False, esc=False, charger=False),
     {'SW401'}, True),
    ('board off; Jetson, laptop, ESC (USB) and charger powered on their own', world(on=False), set(), True),
    ('board on, laptop unplugged', world(laptop=False), set(), True),
    ('board on, E-stop open: main switch drops, ESC unpowered, firmware drops VESC_KILL',
     dict(world(esc=False), VESC_KILL=0.0), {'ESTOP_OPEN'}, True),
    ('E-stop open while the Pico still drives MAIN_EN and PRECHARGE_EN high', world(pico=PICO_PULSE),
     {'ESTOP_OPEN'}, True),
    # review M1: the dev kit off (DEVKIT_PWR low, its 3.3 V down) while the FSESC and the laptop stay on; the
    # firmware drives ESTOP_OK_TO_JETSON and CHG_STAT_N_TO_JETSON low while the Jetson's 3.3 V is low
    ('board on, dev kit off; ESC and laptop on', world(jetson=False, pico=dict(
        PICO_RUN, DEVKIT_PWR=0.0, ESTOP_OK_TO_JETSON=0.0, CHG_STAT_N_TO_JETSON=0.0)), set(), True),
    ('as above, firmware still driving the two Jetson outputs high (worst case)', world(jetson=False, pico=dict(
        PICO_RUN, DEVKIT_PWR=0.0)), set(), True),
]
# dev-kit inputs fed through 1k (review M1): back-power into an unpowered dev kit is a warning up to 3 mA
BACKPOWER_1K = {'J12_RXD', 'J12_ESTOP_OK', 'J12_CHG_STAT_N', 'J14_CON_RXD'}

# --------------------------------------------------------------------------- limits
# (part value, pin name): (max V relative to GND or to the named net, reference net or None). Sources:
# MIC5014 DS20006767A abs max (V+ 60 V, operating 30 V; IN and SOURCE -20 V..V+; GATE 50 V); TI SN74HCT08 (VCC 7 V,
# inputs VCC + 0.5 V); RP2040 (pins IOVDD + 0.5 V = 3.8 V, VSYS 5.5 V); MCP2221A (VDD 6.0 V, pins VDD + 0.3 V);
# MCP1700 (VIN 6.5 V); RECOM R-78E (Vin 28 V); TI TL431 (VKA 37 V); Pololu 2813 (40 V abs), S18V20F12 (32 V abs);
# XL4015 class module (36 V); CH334F hub (VBUS 5.5 V).
PIN_LIMITS = {
    ('MIC5014', 'V+'): (60.0, None), ('MIC5014', 'IN'): (0.0, 'V+'), ('MIC5014', 'SOURCE'): (0.0, 'V+'),
    ('MIC5014', 'GATE'): (50.0, None),
    ('74HCT08', 'VCC'): (7.0, None),
    ('MCP2221A', 'VDD'): (6.0, None), ('MCP1700-3302E/TO', 'VIN'): (6.5, None),
    ('R-78E5.0-1.0', 'VIN'): (28.0, None), ('TL431', 'K'): (37.0, None),
    ('POLOLU_2813', 'VIN'): (40.0, None), ('POLOLU_2813', 'ON'): (0.0, 'VIN'), ('POLOLU_2813', 'OFF'): (0.0, 'VIN'),
    ('POLOLU_S18V20F12', 'VIN'): (32.0, None), ('CCCV_BUCK_XL4015', 'IN+'): (36.0, None),
    ('ADA5997_CH334F_HUB', 'UP_VBUS'): (5.5, None), ('RPi_Pico', 'VSYS'): (5.5, None),
}
NOMINAL_ONLY = {('MIC5014', 'V+'): 30.0}
for nm in ['1A', '1B', '2A', '2B', '3A', '3B', '4A', '4B']:
    PIN_LIMITS[('74HCT08', nm)] = (0.5, 'VCC')
for nm in PICO_IO:
    PIN_LIMITS[('RPi_Pico', nm)] = (0.5, '3V3')
for nm in ['URx', 'UTx', '~{RST}', 'D+', 'D-']:
    PIN_LIMITS[('MCP2221A', nm)] = (0.3, 'VDD')
VGS_MAX = {'IRFB7430PBF': 20.0, 'IRF9Z34NPBF': 20.0, 'IRF4905PBF': 20.0, '2N7000': 20.0}
VDS_MAX = {'IRFB7430PBF': 40.0, 'IRF9Z34NPBF': 55.0, 'IRF4905PBF': 55.0, '2N7000': 60.0}
VCE_MAX = {'2N3904': 40.0, '2N3906': 40.0, 'PC817': 35.0}


def r_rating(p):
    t = (p['value'] + ' ' + p['fields'].get('MPN', '') + ' ' + p['fields'].get('Description', ''))
    if '5W' in p['value'] or '5 W' in t:
        return 5.0
    if '1/4 W' in t:
        return 0.25
    m = re.search(r'(?<![/0-9.])([0-9]*\.?[0-9]+) W', t)
    return float(m.group(1)) if m else 0.25


def c_rating(p):
    m = re.search(r'([0-9.]+)V', p['value'])
    return float(m.group(1)) if m else 50.0


def keep(worst, key, val, lim, title):
    if key not in worst or val > worst[key][0]:
        worst[key] = (val, lim, title)


def run_scenarios():
    worst = {}
    for title, fixed, closed, nominal in SCENARIOS:
        c = build(fixed, closed)
        V, state, it = solve(c)
        tag = f'"{title}"'
        if it < 0:
            err(f'[op] {tag}: the operating point did not converge')
            continue

        def v(n):
            return V.get(n, 0.0) if n else 0.0
        # 7 IC/module pins
        for p in PARTS.values():
            if kind(p) not in ('U', 'MOD'):
                continue
            names = {nm: pads for nm, pads in ((nm, p['pads'].get(num)) for num, nm in p['pinnames'].items())}
            for (val, pin), (lim, refpin) in PIN_LIMITS.items():
                if p['value'] != val or not names.get(pin):
                    continue
                vp = v(names[pin])
                limit = lim + (v(names[refpin]) if refpin else 0.0)
                if refpin and v(names[refpin]) < 0.5 and pin not in ('IN', 'SOURCE', 'ON', 'OFF'):
                    continue          # unpowered IC: handled by the back-power check
                if nominal and (val, pin) in NOMINAL_ONLY:
                    limit = min(limit, NOMINAL_ONLY[(val, pin)])
                keep(worst, (p['ref'], pin), vp, limit, title)
                if vp > limit + 0.01:
                    err(f"[7] {tag}: {p['ref']} {val} {pin} = {vp:.2f} V > limit {limit:.2f} V")
        # 8 transistors
        for typ, kw in c.el:
            if typ == 'FET':
                p = PARTS[kw['ref']]
                vgs, vds = v(kw['g']) - v(kw['s']), v(kw['d']) - v(kw['s'])
                if abs(vgs) > VGS_MAX[p['value']]:
                    err(f"[8] {tag}: {kw['ref']} |VGS| = {abs(vgs):.1f} V > {VGS_MAX[p['value']]}")
                if abs(vds) > VDS_MAX[p['value']]:
                    err(f"[8] {tag}: {kw['ref']} |VDS| = {abs(vds):.1f} V > {VDS_MAX[p['value']]}")
                keep(worst, (kw['ref'], 'VGS'), abs(vgs), VGS_MAX[p['value']], title)
            elif typ in ('BJT', 'OPTO'):
                p = PARTS[kw['ref']]
                vce = abs(v(kw['c']) - v(kw['e']))
                lim = VCE_MAX.get(p['value'], 40.0)
                if vce > lim:
                    err(f"[8] {tag}: {kw['ref']} VCE = {vce:.1f} V > {lim}")
                if typ == 'BJT':
                    vbe_rev = (v(kw['b']) - v(kw['e'])) if kw['pnp'] else (v(kw['e']) - v(kw['b']))
                    if vbe_rev > 5.0:
                        err(f"[8] {tag}: {kw['ref']} reverse VBE = {vbe_rev:.1f} V > 5 V")
        # 9 resistor power, 12 LED current
        for typ, kw in c.el:
            if typ == 'R' and kw['ref'] in PARTS:
                p = PARTS[kw['ref']]
                if kind(p) != 'R':
                    continue
                pw = (v(kw['a']) - v(kw['b'])) ** 2 / kw['r']
                rat = r_rating(p)
                if p['ref'] == next(r for r, q in PARTS.items() if q['value'] == '10 5W'):
                    continue
                if nominal and pw > 0.5 * rat:
                    err(f"[9] {tag}: {kw['ref']} {p['value']} dissipates {pw * 1000:.0f} mW > 50 % of {rat} W")
                keep(worst, (kw['ref'], 'P'), pw, rat, title)
            if typ == 'D' and kw.get('led'):
                i = dcur(kw, V, state)
                if i > 0.020:
                    err(f"[12] {tag}: {kw['ref']} LED current {i * 1000:.1f} mA > 20 mA")
        # 10 capacitors
        for p in PARTS.values():
            if kind(p) != 'C' or p['dnp']:
                continue
            vc = abs(v(p['pads']['1']) - v(p['pads']['2']))
            rat = c_rating(p)
            lim = rat * (0.8 if nominal and p['footprint'].startswith('Capacitor_THT:CP') else 1.0)
            if vc > lim:
                err(f"[10] {tag}: {p['ref']} {p['value']} sees {vc:.1f} V > {lim:.1f} V")
        # 11 TVS / zener conduction in nominal scenarios
        for typ, kw in c.el:
            if typ == 'D' and kw.get('vbr') and state.get(kw['ref']) == 'rev':
                i = -dcur(kw, V, state)
                if nominal and kw['name'] not in TVS_INTENDED:
                    err(f"[11] {tag}: {kw['ref']} {kw['name']} conducts {i * 1000:.1f} mA in normal operation")
                elif not nominal and kw['name'] not in TVS_INTENDED:
                    notes.append(f"{title}: {kw['ref']} {kw['name']} clamps {v(kw['k']) - v(kw['a']):.1f} V, {i:.2f} A")
        # 13 back-power through pin clamps
        for typ, kw in c.el:
            if typ == 'D' and kw.get('esd'):
                i = dcur(kw, V, state)
                ref, nm, rail = kw['esd']
                if ref == 'ext' and nm in BACKPOWER_1K and i <= 3e-3:
                    if i > 0.05e-3:
                        warn(f'[13] {tag}: {i * 1000:.2f} mA into the dev kit {nm} (1k series, TXB-type input with '
                             f'Ioff: likely far less)')
                elif i > 0.5e-3:
                    err(f'[13] {tag}: {i * 1000:.2f} mA into {ref} {nm} through its clamp to {rail}')
                elif i > 0.05e-3:
                    warn(f'[13] {tag}: {i * 1000:.2f} mA into {ref} {nm} through its clamp to {rail}')
        on = sorted(k for k, s in state.items() if s == 'on' and not k.endswith('be'))
        print(f'[op] {title}: converged in {it} iterations; on: {", ".join(x.replace("ce", "").replace("led", " LED") for x in on)}')
        print('      ' + '  '.join(f'{n}={V[n]:.2f}' for n in ('VM', 'SW_GATE', 'MIC_IN', 'PRE_G', 'ESTOP_OK', 'V5_IN',
                                                            'VDEV', 'LATCH_ON', 'BAT_SENSE', 'VM_SENSE', 'CHG_OUT',
                                                            'CHG_PRESENT_N', 'BUTTON_N', 'SERVO_SIG')
                                 if n in V))
    return worst


def precharge_pulse():
    r = next(p for p in PARTS.values() if p['value'] == '10 5W')
    for c_esc, v in ((2e-3, 16.8), (6e-3, 16.8)):
        e = 0.5 * c_esc * v * v
        print(f"[9] precharge {r['ref']}: {c_esc * 1e3:.0f} mF at {v} V -> {e:.2f} J per start, tau "
              f"{10.5 * c_esc * 1e3:.0f} ms; cement 5 W parts take 10 x rated power for 5 s (250 J): OK")


def main():
    print(f"{DATA['name']}: {len(PARTS)} parts, {len(NETS)} nets\n")
    check_structure()
    check_isolation()
    check_domains()
    check_j12()
    check_ground_splits()
    precharge_pulse()
    worst = run_scenarios()
    print('\nworst cases (value, limit, scenario):')
    for key in sorted(worst):
        val, lim, sc = worst[key]
        if key[1] == 'P':
            if val > 0.01:
                print(f"   {key[0]:6s} power   {val * 1000:7.1f} mW of {lim} W  {PARTS[key[0]]['value']:>6s} ({sc})")
        elif key[1] == 'VGS':
            print(f'   {key[0]:6s} |VGS|   {val:7.2f} V of {lim} V    ({sc})')
        else:
            print(f'   {key[0]:6s} {key[1]:8s} {val:7.2f} V, limit {lim:.2f} V ({sc})')
    if notes:
        print('\nclamping in the spike scenarios:')
        for n in notes:
            print('   ' + n)
    print(f'\n{len(errors)} errors, {len(warnings)} warnings')
    for w in warnings:
        print('WARNING', w)
    for e in errors:
        print('ERROR', e)
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
