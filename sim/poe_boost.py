"""Camera PoE supply: the LM5155 boost power stage on the brain board, 12-16.8 V in, 52 V out.

    python3 poe_boost.py         (needs ngspice; writes out/poe_boost.png and out/poe_boost.json)

Checks the parts around the controller, not the controller itself: for each operating point the switch
runs at the steady-state duty cycle (found by bisection so the output settles at 52 V), and the result
is the inductor current (peak against the XAL7070's 4.2 A saturation current and against the LM5155's
cycle-by-cycle limit, 100 mV across 25 mOhm less the slope compensation), the 52 V ripple and the
losses. The loop itself (RCOMP 15.8k, CCOMP 10n, CHF 330p) follows TI's LM5155 design procedure and is
not simulated here: the controller's internal gains are not published in the datasheet.

Parts: 47 uH Coilcraft XAL7070-473 (84 mOhm DCR), CSD19538Q3A switch (Rds(on) taken as 60 mOhm hot),
Vishay SS2H10 Schottky (about 0.7 V at 1 A), 3 x 2.2 uF 100 V X7R (about 0.9 uF each at 52 V) and 22 uF
100 V aluminium (Panasonic EEE-FK2A220P, ESR taken as 0.5 Ohm) on the output, 300 kHz.
"""
import json
import os
import subprocess

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
F = 300e3
L, DCR = 47e-6, 0.084
RDS, RS = 0.060, 0.025
VOUT = 52.0
I_LIM_PEAK = (0.100 - 0.040) / RS      # 100 mV limit less the internal 40 mV slope at full duty: conservative


def run(vin, pout, duty, tag, tstop=4e-3):
    rload = VOUT ** 2 / pout
    net = f"""* LM5155 boost power stage, {vin} V in, {pout} W out, D = {duty:.4f}
Vin in 0 DC {vin}
Rdcr in l1 {DCR}
L1 l1 sw {L} IC=0
Vil sw swm 0
S1 swm rs g 0 SW1
Rs rs 0 {RS}
D1 swm out DSCH
Cc out 0 2.7u IC={VOUT * 0.95}
Ce out ce {22e-6} IC={VOUT * 0.95}
Rce ce 0 0.5
Rl out 0 {rload}
Vg g 0 PULSE(0 5 0 5n 5n {duty / F - 10e-9} {1 / F})
.model SW1 SW(Ron={RDS} Roff=1Meg Vt=2.5 Vh=0.1)
.model DSCH D(Is=2e-6 N=1.2 Rs=0.08 Cjo=100p BV=100)
.tran 20n {tstop} 0 20n uic
.control
run
wrdata {os.path.join(OUT, f'boost_{tag}.txt')} v(out) i(Vil)
.endc
.end
"""
    p = os.path.join(OUT, f'boost_{tag}.cir')
    open(p, 'w').write(net)
    subprocess.run(['ngspice', '-b', p], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, check=True)
    d = np.loadtxt(os.path.join(OUT, f'boost_{tag}.txt'))
    return d[:, 0], d[:, 1], d[:, 3]


def settle(vin, pout, tag):
    lo, hi = 0.5, 0.85
    for _ in range(9):
        dmid = (lo + hi) / 2
        t, vo, il = run(vin, pout, dmid, tag, tstop=2.5e-3)
        v_end = float(np.mean(vo[t > t[-1] - 0.3e-3]))
        if v_end < VOUT:
            lo = dmid
        else:
            hi = dmid
    t, vo, il = run(vin, pout, (lo + hi) / 2, tag, tstop=4e-3)
    sel = t > t[-1] - 20 / F
    tu = np.linspace(t[sel][0], t[-1], 40000)
    ilu = np.interp(tu, t[sel], il[sel])
    vou = np.interp(tu, t[sel], vo[sel])
    duty = (lo + hi) / 2
    iin = float(np.mean(ilu))
    pin = vin * iin
    res = dict(vin=vin, pout_w=pout, duty=round(duty, 3), vout=round(float(np.mean(vou)), 2),
               ripple_mv_pp=round(float(np.ptp(vou)) * 1e3, 1), il_avg=round(iin, 3), il_peak=round(float(ilu.max()), 3),
               il_valley=round(float(ilu.min()), 3), isat_margin=round(4.2 / float(ilu.max()), 2),
               limit_margin=round(I_LIM_PEAK / float(ilu.max()), 2),
               efficiency_conduction_only=round(pout / pin, 3))
    return res, (tu, ilu, vou)


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    pts = [(12.0, 5.0), (14.4, 5.0), (16.8, 5.0), (12.0, 15.0), (14.4, 15.0)]
    out = []
    fig, ax = plt.subplots(1, 2, figsize=(14, 4.8))
    for i, (vin, pw) in enumerate(pts):
        r, (tu, ilu, vou) = settle(vin, pw, f'{i}')
        out.append(r)
        print(json.dumps(r))
        if (vin, pw) in ((12.0, 15.0), (14.4, 5.0)):
            us = (tu - tu[0]) * 1e6
            ax[0].plot(us, ilu, label=f'{vin} V in, {pw} W out')
            ax[1].plot(us, vou, label=f'{vin} V in, {pw} W out')
    ax[0].axhline(4.2, color='r', ls='--', lw=1, label='inductor saturation (30 % drop)')
    ax[0].axhline(I_LIM_PEAK, color='orange', ls=':', lw=1, label='controller current limit (conservative)')
    ax[0].set(xlabel='us', ylabel='inductor current (A)', title='boost inductor current', xlim=(0, 20))
    ax[1].set(xlabel='us', ylabel='52 V rail (V)', title='output ripple', xlim=(0, 20))
    for a in ax:
        a.grid(alpha=0.3); a.legend(fontsize=8)
    plt.tight_layout(); plt.savefig(os.path.join(OUT, 'poe_boost.png'), dpi=130); plt.close()
    json.dump(out, open(os.path.join(OUT, 'poe_boost.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
