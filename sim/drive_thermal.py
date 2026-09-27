"""Drive board temperature at sustained high load: a 2-D thermal model of the board and its heat spreader.

    python3 drive_thermal.py [peak phase current A, default 70]   (writes out/drive_thermal.png, .json)

The board is a 140 x 90 mm plate whose in-plane conduction comes from its four 2 oz copper layers
(90 % copper where the power pours are, 50 % elsewhere) and FR4, cooled on both faces by the side-pod
fan's air (h = 25 W/m2K, a moderate 1-2 m/s flow). Under the power stage a 60 x 48 x 4.76 mm aluminium
spreader touches the tops of the twelve ESC FETs through a 1 mm, 6 W/mK pad; the package top of a
SON 5x6 FET is a poor heat path (about 20 C/W assumed), so most heat leaves through the drain tabs into
the copper. The losses come from the operating point of sim/dclink.py (sine PWM, m = 0.8, 30 kHz,
cos(phi) 0.79) and the datasheets:
  ESC FET conduction: switch RMS current^2 x 1.2 mOhm (CSD18510Q5B, 0.79 mOhm typ at 25 C, x1.5 hot),
      high side I_pk^2 (1/8 + m cos(phi) / (3 pi)), low side I_pk^2 (1/8 - m cos(phi) / (3 pi)), two FETs share.
  ESC switching: V_bus x average |I| x 56 ns x f_sw per phase (2 x 28 nC Qgd per switch at 1 A gate drive),
      split between the high- and low-side FETs, plus 100 ns of body-diode dead time per edge.
  Battery path at the battery current of that point: 4 + 4 BMS FETs, 4 main-switch FETs, 0.5 and 0.2 mOhm shunts.
  Everything else: gate driver 0.5 W, MCU 0.25 W, servo module 0.8 W (1 A average servo current), hub and
      console 0.4 W, charger power path 0.1 W.
It is an estimate to find hot spots and margins, not a substitute for a thermocouple on the bench.
"""
import json
import math
import os
import sys

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(HERE, '..', 'boards', 'tools'))

W, H, D = 140.0, 90.0, 0.5            # board and grid (mm)
T_AMB = float(os.environ.get('T_AMB', 35.0))     # air inside the body on a hot day
H_CONV = float(os.environ.get('H_CONV', 25.0))   # W/m2K per face (8 = still air, no fan)
K_CU, T_CU, K_FR4 = 390.0, 70e-6, 0.3
M, COSPHI, FSW, VBUS = 0.8, 0.79, 30e3, 14.4
RDS_HOT = 1.2e-3


def load_parts():
    pl = json.load(open(os.path.join(HERE, '..', 'boards', 'drive', 'out', 'atlas_drive_placement.json')))
    parts = {p['ref']: p for p in json.load(open(os.path.join(HERE, '..', 'boards', 'drive', 'atlas_drive_parts.json')))['parts']}
    return pl, parts


def losses(ipk, ibat):
    k = M * COSPHI / (3 * math.pi)
    hs = ipk ** 2 * (1 / 8 + k) * RDS_HOT / 2 / 2        # per FET: switch current squared / 2 FETs, / 2 for the share
    ls = ipk ** 2 * (1 / 8 - k) * RDS_HOT / 2 / 2
    # (switch RMS^2 x R_switch where R_switch = R_FET / 2 and each FET carries half: I_FET^2 R_FET = I_sw^2 R_FET / 4)
    iavg = 2 / math.pi * ipk
    sw = VBUS * iavg * 56e-9 * FSW                      # per phase
    dt = 0.8 * iavg * 2 * 100e-9 * FSW                  # per phase, body diode in the dead time
    fet_hs = hs + sw / 4
    fet_ls = ls + sw / 4 + dt / 2
    batt_fet = (ibat / 4) ** 2 * RDS_HOT
    return dict(fet_hs=fet_hs, fet_ls=fet_ls, batt_fet=batt_fet, shunt_esc=0.2e-3 * ipk ** 2 * (1 / 8 - k),
                shunt_bms=0.5e-3 * ibat ** 2, shunt_main=0.2e-3 * ibat ** 2)


def main():
    ipk = float(sys.argv[1]) if len(sys.argv) > 1 else 70.0
    dcl = json.load(open(os.path.join(OUT, 'dclink.json'))) if os.path.exists(os.path.join(OUT, 'dclink.json')) else None
    ibat = None
    if dcl:
        for r in dcl['results']:
            if abs(r['i_phase_peak'] - ipk) < 1e-6:
                ibat = r['i_battery_avg']
    if ibat is None:
        ibat = 0.47 * ipk                                   # the dclink.py ratio at m = 0.8
    Lo = losses(ipk, ibat)
    pl, parts = load_parts()
    nx, ny = int(W / D), int(H / D)
    P = np.zeros((ny, nx))
    src = []

    def add(ref, watts, size=(5.0, 6.0)):
        x, y = pl[ref]['x'], pl[ref]['y']
        rot = pl[ref]['rot'] % 180
        sx, sy = (size[1], size[0]) if rot == 90 else size
        i0, i1 = int((x - sx / 2) / D), int((x + sx / 2) / D)
        j0, j1 = int((y - sy / 2) / D), int((y + sy / 2) / D)
        n = max(1, (i1 - i0) * (j1 - j0))
        P[j0:j1, i0:i1] += watts / n
        src.append((ref, watts, x, y))

    val = lambda r: parts[r].get('value')
    esc_hs = [r for r in pl if val(r) == 'CSD18510Q5B' and pl[r]['side'] == 'B' and abs(pl[r]['y'] - 41.0) < 0.1]
    esc_ls = [r for r in pl if val(r) == 'CSD18510Q5B' and pl[r]['side'] == 'B' and abs(pl[r]['y'] - 30.0) < 0.1]
    for r in esc_hs:
        add(r, Lo['fet_hs'])
    for r in esc_ls:
        add(r, Lo['fet_ls'])
    for r in [r for r in pl if val(r) == 'CSD18510Q5B' and pl[r]['side'] == 'F' and r != 'Q306']:
        add(r, Lo['batt_fet'])
    for r in ('R512', 'R520', 'R528'):
        add(r, Lo['shunt_esc'], (6.4, 10.2))
    add('R214', Lo['shunt_bms'], (6.4, 10.2)); add('R301', Lo['shunt_main'], (6.4, 10.2))
    add('U501', 0.5, (7, 7)); add('U601', 0.25, (10, 10)); add('U901', 0.8, (12, 10))
    add('U803', 0.3, (6, 6)); add('U703', 0.1, (4, 4))
    total = float(P.sum())

    # conductances
    xs = (np.arange(nx) + 0.5) * D
    ys = (np.arange(ny) + 0.5) * D
    X, Y = np.meshgrid(xs, ys)
    power = (X > 28) & (X < 82) & (Y > 2) & (Y < 62)
    cov = np.where(power, 0.9, 0.5)
    gs = cov * 4 * T_CU * K_CU + 1.6e-3 * K_FR4           # W/K per square
    area = (D * 1e-3) ** 2
    g_air = 2 * H_CONV * area
    spreader = (X > 25) & (X < 85) & (Y > 2) & (Y < 50)
    fet_cells = np.zeros_like(P, dtype=bool)
    for r in esc_hs + esc_ls:
        x, y = pl[r]['x'], pl[r]['y']
        fet_cells |= (np.abs(X - x) < 3.0) & (np.abs(Y - y) < 2.5)
    g_fet_per = 1.0 / (20.0 + 1e-3 / (6.0 * 30e-6)) / (fet_cells.sum() / 12)   # per cell: package top + pad
    g_gap = 0.026 / 2.24e-3 * area                                               # air gap elsewhere
    gc = np.where(spreader, np.where(fet_cells, g_fet_per, g_gap), 0.0)
    g_al = 167.0 * 4.76e-3
    g_sp_air = H_CONV * area * 0.6                                               # underside partly on the deck

    nb = nx * ny
    idx = lambda j, i: j * nx + i
    sidx = -np.ones((ny, nx), dtype=int)
    sidx[spreader] = nb + np.arange(spreader.sum())
    N = nb + int(spreader.sum())
    rows, cols, vals = [], [], []
    diag = np.zeros(N)
    rhs = np.zeros(N)
    for j in range(ny):
        for i in range(nx):
            a = idx(j, i)
            for dj, di in ((0, 1), (1, 0)):
                jj, ii = j + dj, i + di
                if jj < ny and ii < nx:
                    b = idx(jj, ii)
                    g = 2 * gs[j, i] * gs[jj, ii] / (gs[j, i] + gs[jj, ii])
                    rows += [a, b]; cols += [b, a]; vals += [-g, -g]
                    diag[a] += g; diag[b] += g
                    if spreader[j, i] and spreader[jj, ii]:
                        sa, sb = sidx[j, i], sidx[jj, ii]
                        rows += [sa, sb]; cols += [sb, sa]; vals += [-g_al, -g_al]
                        diag[sa] += g_al; diag[sb] += g_al
            diag[a] += g_air
            rhs[a] += P[j, i] + g_air * T_AMB
            if spreader[j, i]:
                s = sidx[j, i]
                rows += [a, s]; cols += [s, a]; vals += [-gc[j, i], -gc[j, i]]
                diag[a] += gc[j, i]; diag[s] += gc[j, i] + g_sp_air
                rhs[s] += g_sp_air * T_AMB
    A = sp.coo_matrix((vals, (rows, cols)), shape=(N, N)).tocsr() + sp.diags(diag)
    T = spla.spsolve(A.tocsc(), rhs)
    Tb = T[:nb].reshape(ny, nx)
    Ts = np.full((ny, nx), np.nan)
    Ts[spreader] = T[nb:]

    def tmax(ref, size=(5.0, 6.0)):
        x, y = pl[ref]['x'], pl[ref]['y']
        m = (np.abs(X - x) < size[0] / 2) & (np.abs(Y - y) < size[1] / 2)
        return float(Tb[m].max())

    res = dict(peak_phase_current=ipk, battery_current=ibat, ambient_c=T_AMB, total_loss_w=round(total, 2),
               losses_w={k: round(v, 3) for k, v in Lo.items()},
               board_max_c=round(float(Tb.max()), 1), board_mean_c=round(float(Tb.mean()), 1),
               spreader_mean_c=round(float(np.nanmean(Ts)), 1),
               hottest_esc_fet_c=round(max(tmax(r) for r in esc_hs + esc_ls), 1),
               esc_fet_junction_c=round(max(tmax(r) for r in esc_hs + esc_ls) + 0.8 * Lo['fet_hs'], 1),
               bms_fet_c=round(max(tmax(r) for r in pl if val(r) == 'CSD18510Q5B' and r.startswith('Q2')), 1),
               bulk_caps_c=round(max(tmax(r, (10, 10)) for r in ('C525', 'C526', 'C527', 'C528')), 1),
               mcu_c=round(tmax('U601', (10, 10)), 1), servo_module_c=round(tmax('U901', (12, 10)), 1))
    print(json.dumps(res, indent=1))
    tag = f'{int(ipk)}A' + ('' if H_CONV == 25.0 else f'_h{int(H_CONV)}')
    res['h_w_m2k'] = H_CONV
    json.dump(res, open(os.path.join(OUT, f'drive_thermal_{tag}.json'), 'w'), indent=1)

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(12, 8))
    im = ax.imshow(Tb, origin='lower', extent=(0, W, 0, H), cmap='inferno', vmin=T_AMB)
    cb = plt.colorbar(im, ax=ax, shrink=0.8); cb.set_label('C')
    for ref, wt, x, y in src:
        if wt >= 0.2:
            ax.text(x, y, ref, color='cyan', fontsize=7, ha='center', va='center')
    ax.add_patch(plt.Rectangle((25, 2), 60, 48, fill=False, ec='white', ls='--', lw=0.8))
    ax.text(26, 3, 'heat spreader (under the board)', color='white', fontsize=8)
    ax.set_xlabel('mm (rear edge at 0)'); ax.set_ylabel('mm')
    ax.set_title(f'ATLAS-DRV-1 at {ipk:.0f} A peak phase current ({ibat:.0f} A from the pack), {T_AMB:.0f} C air, '
                 f'{"fan" if H_CONV >= 20 else "no fan"}: '
                 f'{total:.1f} W of losses, hottest FET about {res["esc_fet_junction_c"]:.0f} C')
    plt.tight_layout(); plt.savefig(os.path.join(OUT, f'drive_thermal_{tag}.png'), dpi=140); plt.close()


if __name__ == '__main__':
    main()
