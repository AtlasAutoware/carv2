"""ESC DC-link ripple: which capacitors carry the inverter's switching current, and how much.

    python3 dclink.py            (needs ngspice on the PATH; writes out/dclink_*.png and out/dclink.json)

A switched model of the three half-bridges (ideal switches, sine-triangle PWM like the VESC's FOC output
stage) drives a star-connected motor model (R, L and a sinusoidal back-EMF per phase). The DC link is
what the drive board has: the bulk hybrid-polymer capacitors on the VM pour, the 1210 ceramics next to
the FETs, the board inductance between them, and the pack with its leads. The result is the RMS
current in each capacitor, the voltage ripple on the motor bus and the battery current.

Assumptions (the motor is not characterised yet): 20 uH and 10 mOhm per phase, 400 Hz electrical,
current in phase with the back-EMF (FOC with Id = 0). Capacitor data: Panasonic EEH-ZU1V331P
(330 uF 35 V, 11 mOhm, 4.8 A rms at 100 kHz and 125 C), Murata GRM32ER71H106KA12L (10 uF 50 V X7R
1210, about 6 uF left at 14 V). Pack: 4S3P Molicel P28A, about 24 mOhm, 10 AWG leads about 150 nH.
"""
import json
import math
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)

VDC = 14.4                 # nominal pack
FSW = 30e3                 # VESC FOC switching frequency (default 30 kHz)
FE = 400.0                 # electrical frequency
R_PH, L_PH = 0.010, 20e-6  # per phase (assumed)
N_BULK, C_BULK, ESR_BULK, ESL_BULK, IRIP_BULK = 4, 330e-6, 0.011, 3e-9, 4.8
N_CER, C_CER, ESR_CER, ESL_CER = 12, 6e-6, 0.003, 0.5e-9
L_BOARD = 5e-9             # ceramics (at the FETs) to the bulk caps
R_PACK, L_PACK = 0.024, 150e-9


def netlist(ipk, m=0.8):
    # back-EMF amplitude for the requested peak current with Id = 0 (current in phase with the EMF)
    w = 2 * math.pi * FE
    vph = m * VDC / 2
    x = w * L_PH
    e = math.sqrt(max(vph ** 2 - (ipk * x) ** 2, 1e-6)) - ipk * R_PH
    delta = math.atan2(ipk * x, e + ipk * R_PH)          # voltage leads the EMF by delta
    lines = [f'* DC link ripple, {ipk} A peak phase current, m = {m}',
             f'Vpack pk 0 DC {VDC}',
             f'Rpack pk p1 {R_PACK}', f'Lpack p1 vb {L_PACK}',
             # bulk caps on the VM pour
             f'Lbrd vb vm {L_BOARD}']
    for i in range(N_BULK):
        lines += [f'Vbm{i} vb b{i}a 0', f'Cb{i} b{i}a b{i}b {C_BULK} IC={VDC}', f'Rb{i} b{i}b b{i}c {ESR_BULK}',
                  f'Lb{i} b{i}c 0 {ESL_BULK}']
    lines += [f'Vcm vm c0a 0', f'Cc c0a c0b {N_CER * C_CER} IC={VDC}', f'Rc c0b c0c {ESR_CER / N_CER}',
              f'Lc c0c 0 {ESL_CER / N_CER}']
    # carrier and PWM (smooth comparators keep the solver happy)
    lines.append(f'Vtri tri 0 PULSE(-1 1 0 {0.5 / FSW} {0.5 / FSW} 1e-9 {1 / FSW})')
    for k, ph in enumerate('abc'):
        ang = -2 * math.pi * k / 3
        lines += [f'Bref{ph} ref{ph} 0 V = {m} * sin({w} * time + {ang + delta})',
                  f'Bs{ph} s{ph} 0 V = 0.5 * (1 + tanh(2000 * (v(ref{ph}) - v(tri))))',
                  # half-bridge output: VM times the switch state
                  f'Bout{ph} o{ph} 0 V = v(vm) * v(s{ph})',
                  f'Vim{ph} o{ph} m{ph} 0',
                  f'Rph{ph} m{ph} r{ph} {R_PH}', f'Lph{ph} r{ph} e{ph} {L_PH}',
                  f'Bemf{ph} e{ph} n V = {e} * sin({w} * time + {ang})',
                  # the bridge draws the phase current from VM while the high side is on
                  f'Bdraw{ph} vm 0 I = v(s{ph}) * i(Vim{ph})']
    lines += ['Rn n 0 1e6',
              '.options method=gear reltol=1e-3 abstol=1e-6 vntol=1e-5 itl4=100',
              f'.tran 50n {12.5e-3} 0 50n uic',
              '.control', 'run',
              'wrdata ' + os.path.join(OUT, f'dclink_{ipk}.txt') + ' i(Vpack) ' +
              ' '.join(f'i(Vbm{i})' for i in range(N_BULK)) + ' i(Vcm) v(vm) i(Vima) i(Vimb) i(Vimc)',
              '.endc', '.end']
    return '\n'.join(lines), e, delta


def rms(x):
    return float(np.sqrt(np.mean(np.square(x - np.mean(x)))))


def run(ipk):
    net, e, delta = netlist(ipk)
    p = os.path.join(OUT, f'dclink_{ipk}.cir')
    open(p, 'w').write(net)
    subprocess.run(['ngspice', '-b', p], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, check=True)
    d = np.loadtxt(os.path.join(OUT, f'dclink_{ipk}.txt'))
    t = d[:, 0]
    cols = d[:, 1::2]                     # wrdata writes time, value pairs
    ipack = -cols[:, 0]
    ibulk = cols[:, 1:1 + N_BULK]
    icer = cols[:, 1 + N_BULK]
    vm = cols[:, 2 + N_BULK]
    iph = cols[:, 3 + N_BULK:6 + N_BULK]
    sel = t > t[-1] - 2 / FE              # the last two electrical periods
    # resample on a uniform grid for honest RMS values
    tu = np.linspace(t[sel][0], t[-1], 200000)
    u = lambda y: np.interp(tu, t[sel], y[sel])
    res = dict(i_phase_peak=ipk, emf_peak=round(e, 2),
               i_phase_rms=round(float(np.sqrt(np.mean(u(iph[:, 0]) ** 2))), 1),
               i_battery_avg=round(float(np.mean(u(ipack))), 1),
               i_battery_ripple_rms=round(rms(u(ipack)), 1),
               i_bulk_rms_each=[round(rms(u(ibulk[:, i])), 2) for i in range(N_BULK)],
               i_ceramics_rms_total=round(rms(u(icer)), 2),
               v_bus_ripple_pp=round(float(np.ptp(u(vm))), 3),
               bulk_rating_a=IRIP_BULK)
    return res, (t, ipack, ibulk, icer, vm, iph)


def plot(all_res, waves):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    t, ipack, ibulk, icer, vm, iph = waves
    sel = t > t[-1] - 1 / FE
    fig, ax = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    tm = (t[sel] - t[sel][0]) * 1e3
    for k, ph in enumerate('ABC'):
        ax[0].plot(tm, iph[sel, k], lw=0.8, label=f'phase {ph}')
    ax[0].set_ylabel('phase current (A)'); ax[0].legend(loc='upper right'); ax[0].grid(alpha=0.3)
    ax[1].plot(tm, ibulk[sel, 0], lw=0.5, label='one bulk capacitor')
    ax[1].plot(tm, icer[sel], lw=0.5, label='all 12 ceramics', alpha=0.7)
    ax[1].plot(tm, ipack[sel], lw=0.8, label='battery')
    ax[1].set_ylabel('current (A)'); ax[1].legend(loc='upper right'); ax[1].grid(alpha=0.3)
    ax[2].plot(tm, vm[sel], lw=0.6, color='k')
    ax[2].set_ylabel('motor bus VM (V)'); ax[2].set_xlabel('time (ms), one electrical period'); ax[2].grid(alpha=0.3)
    r = all_res[-1]
    fig.suptitle(f'ESC DC link at {r["i_phase_peak"]} A peak phase current: each bulk capacitor carries '
                 f'{max(r["i_bulk_rms_each"]):.1f} A rms (rated {IRIP_BULK} A)')
    plt.tight_layout(); plt.savefig(os.path.join(OUT, 'dclink_waveforms.png'), dpi=130); plt.close()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ip = [r['i_phase_peak'] for r in all_res]
    ax.plot(ip, [max(r['i_bulk_rms_each']) for r in all_res], 'o-', label='per bulk capacitor')
    ax.plot(ip, [r['i_ceramics_rms_total'] for r in all_res], 's-', label='12 ceramics together')
    ax.plot(ip, [r['i_battery_ripple_rms'] for r in all_res], '^-', label='battery leads (AC part)')
    ax.axhline(IRIP_BULK, color='r', ls='--', lw=1, label=f'bulk rating {IRIP_BULK} A (100 kHz, 125 C)')
    ax.set_xlabel('peak phase current (A)'); ax.set_ylabel('RMS ripple current (A)'); ax.grid(alpha=0.3); ax.legend()
    ax.set_title('Where the inverter ripple current goes')
    plt.tight_layout(); plt.savefig(os.path.join(OUT, 'dclink_sweep.png'), dpi=130); plt.close()


if __name__ == '__main__':
    pts = [int(a) for a in sys.argv[1:]] or [30, 50, 70, 100]
    allr = []
    w = None
    for ipk in pts:
        r, w = run(ipk)
        allr.append(r)
        print(json.dumps(r))
    plot(allr, w)
    json.dump(dict(assumptions=dict(vdc=VDC, fsw=FSW, fe=FE, r_ph=R_PH, l_ph=L_PH, n_bulk=N_BULK, c_bulk=C_BULK,
                                    esr_bulk=ESR_BULK, n_cer=N_CER, c_cer_eff=C_CER, r_pack=R_PACK, l_pack=L_PACK),
                   results=allr), open(os.path.join(OUT, 'dclink.json'), 'w'), indent=1)
