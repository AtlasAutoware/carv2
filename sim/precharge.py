"""Main-switch precharge: how hard the precharge resistor works when the car is switched on.

    python3 precharge.py         (needs ngspice; writes out/precharge.png and out/precharge.json)

The STM32 turns on the TPS48111's precharge gate first. The ESC capacitors charge from the pack through
the precharge resistor; once the motor bus is up the main FETs close. The whole capacitor energy,
C V^2 / 2, is spent in the resistor whatever its value, and it arrives as one pulse of a few ms.
A resistor survives such a pulse only up to its single-pulse rating. The check compares the energy the
resistor has taken by each moment with the energy of a rectangular pulse of that length it is rated
for (Vishay CRCW2512-HP single-pulse diagram: about 100 W for 1 ms, 20 W for 10 ms, 2 W for 100 ms;
a standard 2512 thick-film part manages about half: IRC PWC data, 10 W for 10 ms).

Cases: the first design (one 10 Ohm 2512) and the fix (two 22 Ohm CRCW2512-HP in parallel).
"""
import json
import math
import os
import subprocess

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)

V_PACK = 16.8                          # full pack: the worst case
R_PACK, L_PACK = 0.024, 150e-9
C_BUS = 4 * 330e-6 + 12 * 6e-6 + 30e-6  # bulk + ceramics (DC-biased) + servo module and driver input caps
ESR_BUS = 0.011 / 4
T_ON = 1e-3                            # precharge gate on
T_MAIN = 0.100                         # the MCU closes the main FETs about 100 ms later (bus above 95 %)
SERVO_I = 0.3                          # the servo supply starts above 9 V and charges its output caps


def pulse_limit(t, hp=True):
    """rated single rectangular pulse power for a 2512 part (W) at duration t (s)"""
    t_ms = np.maximum(t * 1e3, 1e-3)
    p = np.where(t_ms <= 10, 100 * t_ms ** -0.7, 20 * (t_ms / 10) ** -1.0)
    return p if hp else p / 2


def run(name, r_each, n):
    r = r_each / n
    net = f"""* precharge {name}
Vpk pk 0 DC {V_PACK}
Rpk pk p1 {R_PACK}
Lpk p1 swin {L_PACK}
* precharge path: resistor(s), then the precharge FET (a switch that closes at T_ON)
Vir swin r1 0
Rpre r1 pd {r}
Spre pd vm gp 0 SWMOD
Vgp gp 0 PULSE(0 5 {T_ON} 1u 1u 1 2)
* main FETs, 4 x 0.79 mOhm, close at T_MAIN
Vim swin m1 0
Smain m1 vm gm 0 SWMAIN
Vgm gm 0 PULSE(0 5 {T_MAIN} 1u 1u 1 2)
Cbus vm c1 {C_BUS} IC=0
Rbus c1 0 {ESR_BUS}
Bservo vm 0 I = {SERVO_I} * 0.5 * (1 + tanh(20 * (v(vm) - 9)))
.model SWMOD SW(Ron=1m Roff=10Meg Vt=2.5 Vh=0.1)
.model SWMAIN SW(Ron=0.2m Roff=10Meg Vt=2.5 Vh=0.1)
.tran 2u 0.12 0 5u uic
.control
run
wrdata {os.path.join(OUT, f'precharge_{name}.txt')} v(vm) i(Vir) i(Vim)
.endc
.end
"""
    p = os.path.join(OUT, f'precharge_{name}.cir')
    open(p, 'w').write(net)
    subprocess.run(['ngspice', '-b', p], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, check=True)
    d = np.loadtxt(os.path.join(OUT, f'precharge_{name}.txt'))
    t, vm, ir, im = d[:, 0], d[:, 1], d[:, 3], d[:, 5]
    pr = ir ** 2 * r / n                                   # power in each resistor
    e = np.concatenate([[0], np.cumsum(0.5 * (pr[1:] + pr[:-1]) * np.diff(t))])
    on = t > T_ON
    dt = t[on] - T_ON
    margin_hp = float(np.min(pulse_limit(dt[1:]) * dt[1:] / np.maximum(e[on][1:], 1e-12)))
    margin_std = float(np.min(pulse_limit(dt[1:], hp=False) * dt[1:] / np.maximum(e[on][1:], 1e-12)))
    k95 = np.argmax(vm > 0.95 * V_PACK)
    res = dict(case=name, r_total=round(r, 2), resistors=n, c_bus_mF=round(C_BUS * 1e3, 2),
               tau_ms=round(r * C_BUS * 1e3, 1), t95_ms=round((t[k95] - T_ON) * 1e3, 1),
               i_peak=round(float(ir.max()), 2), p_peak_each_w=round(float(pr.max()), 1),
               energy_each_j=round(float(e[t < T_MAIN][-1]), 3),
               v_bus_at_main_close=round(float(np.interp(T_MAIN, t, vm)), 2),
               i_main_close_peak=round(float(np.max(np.abs(im[t > T_MAIN]))), 1),
               pulse_margin_crcw_hp=round(margin_hp, 2), pulse_margin_std_2512=round(margin_std, 2))
    return res, (t, vm, ir, pr, e)


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    cases = [('first design: 1 x 10 Ohm', 10.0, 1), ('fix: 2 x 22 Ohm CRCW2512-HP', 22.0, 2)]
    out = []
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.8))
    for (label, r_each, n), col in zip(cases, ('tab:red', 'tab:green')):
        res, (t, vm, ir, pr, e) = run(label.split(':')[0].replace(' ', '_'), r_each, n)
        res['label'] = label
        out.append(res)
        ms = (t - T_ON) * 1e3
        ax[0].plot(ms, vm, color=col, label=label)
        ax[1].plot(ms, pr, color=col, label=label + ' (per resistor)')
        ax[2].plot(ms[ms > 0], e[ms > 0] * 1e3, color=col, label=label + ' (per resistor)')
        print(json.dumps(res))
    tt = np.logspace(-4, -1, 200)
    ax[2].plot(tt * 1e3, pulse_limit(tt) * tt * 1e3, 'k--', lw=1, label='CRCW2512-HP single-pulse rating')
    ax[2].plot(tt * 1e3, pulse_limit(tt, hp=False) * tt * 1e3, 'k:', lw=1, label='standard 2512 thick film')
    ax[0].axvline((T_MAIN - T_ON) * 1e3, color='gray', lw=0.8, ls='--'); ax[0].text((T_MAIN - T_ON) * 1e3, 1, ' main FETs on', color='gray')
    ax[0].set(xlabel='ms after switch-on', ylabel='motor bus VM (V)', xlim=(-5, 110), title='bus voltage')
    ax[1].set(xlabel='ms after switch-on', ylabel='W', xlim=(-1, 60), title='power in each precharge resistor')
    ax[2].set(xlabel='pulse length (ms)', ylabel='energy (mJ)', xscale='log', xlim=(0.1, 100), title='energy taken vs pulse rating')
    for a in ax:
        a.grid(alpha=0.3); a.legend(fontsize=7)
    plt.tight_layout(); plt.savefig(os.path.join(OUT, 'precharge.png'), dpi=130); plt.close()
    json.dump(out, open(os.path.join(OUT, 'precharge.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
