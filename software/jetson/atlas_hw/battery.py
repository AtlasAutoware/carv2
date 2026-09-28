"""Pack voltage, current and an estimated state of charge from the drive board's INA228.

One process owns the estimate: `atlas battery-daemon` (atlas-battery.service). It writes the live
state to /run/atlas/battery.json every READ_PERIOD seconds, which the CLI and the ROS 2 node read,
and saves the estimate to /var/lib/atlas/battery.json so the next start-up can continue from it.
Nothing else resets the INA228's accumulators.

How the estimate works
  - At start-up, from the pack voltage. The Jetson already draws current by then, so the voltage
    is corrected by I x R_PACK before the lookup in OCV_TABLE.
  - After that, coulomb counting from the INA228 CHARGE register (0.5 mOhm BMS shunt).
  - The saved estimate is kept at start-up if it is within SAVED_TRUST of the voltage estimate.
    Otherwise the voltage wins: the pack was charged or used while the car was off, and the INA228
    has no power then (it runs from the drive board's 3.3 V).

OCV_TABLE and R_PACK are placeholders, not Molicel P28A data: a generic rest-voltage curve for
NMC 18650 cells and a rough guess at the pack resistance. Replace both with measurements
(ATLAS_PACK_R and /etc/atlas/ocv.json) before trusting the percentage below about 20 %.
"""
import json
import os
import time

from . import board

LIVE_PATH = '/run/atlas/battery.json'
STATE_PATH = '/var/lib/atlas/battery.json'
READ_PERIOD = 2.0
SAVE_PERIOD = 60.0
SAVED_TRUST = 0.15

# per-cell rest voltage -> state of charge; generic NMC shape, see the module docstring
OCV_TABLE = [
    (3.30, 0.00), (3.50, 0.03), (3.60, 0.07), (3.66, 0.10), (3.70, 0.15), (3.73, 0.20),
    (3.77, 0.30), (3.80, 0.40), (3.84, 0.50), (3.88, 0.60), (3.94, 0.70), (4.00, 0.80),
    (4.07, 0.90), (4.14, 0.97), (4.20, 1.00),
]
R_PACK = float(os.environ.get('ATLAS_PACK_R', '0.05'))    # ohm, guess: 4 cells in series / 3 in parallel + BMS FETs + wiring


def load_ocv_table(path='/etc/atlas/ocv.json'):
    """A measured table as [[cell_volts, soc_0_to_1], ...] replaces the generic one."""
    try:
        with open(path) as f:
            table = sorted((float(v), float(s)) for v, s in json.load(f))
        if len(table) >= 2:
            return table
    except (OSError, ValueError, TypeError):
        pass
    return OCV_TABLE


def soc_from_cell_voltage(v, table=OCV_TABLE):
    if v <= table[0][0]:
        return table[0][1]
    for (v0, s0), (v1, s1) in zip(table, table[1:]):
        if v <= v1:
            return s0 + (s1 - s0) * (v - v0) / (v1 - v0)
    return table[-1][1]


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f)
    os.replace(tmp, path)


def read_live(path=LIVE_PATH, max_age=10.0):
    """The daemon's latest state, or None if it is not running (or the file is stale)."""
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if time.time() - data.get('time', 0) > max_age:
        return None
    return data


class Estimator:
    def __init__(self, ina, capacity_ah=board.PACK_CAPACITY_AH, cells=board.PACK_CELLS_SERIES,
                 r_pack=R_PACK, state_path=STATE_PATH, table=None):
        self.ina = ina
        self.capacity_c = capacity_ah * 3600.0
        self.cells = cells
        self.r_pack = r_pack
        self.state_path = state_path
        self.table = table or OCV_TABLE
        self.soc0 = None
        self.q0 = None
        self.source = None

    def start(self):
        self.ina.configure(reset_accumulators=True)
        time.sleep(0.2)                         # first averaged conversion
        r = self.ina.read_all()
        v_rest = (r['voltage'] + r['current'] * self.r_pack) / self.cells
        soc_v = soc_from_cell_voltage(v_rest, self.table)
        saved = None
        try:
            with open(self.state_path) as f:
                saved = float(json.load(f)['soc'])
        except (OSError, ValueError, KeyError, TypeError):
            pass
        if saved is not None and abs(saved - soc_v) <= SAVED_TRUST:
            self.soc0, self.source = saved, 'saved'
        else:
            self.soc0, self.source = soc_v, 'voltage'
        self.q0 = r['charge_c']
        return self.soc0

    def read(self):
        r = self.ina.read_all()
        soc = self.soc0 - (r['charge_c'] - self.q0) / self.capacity_c
        r['soc'] = min(1.0, max(0.0, soc))
        r['cell_v'] = r['voltage'] / self.cells
        r['cell_v_rest'] = (r['voltage'] + r['current'] * self.r_pack) / self.cells
        r['soc_source'] = self.source
        r['time'] = time.time()
        return r

    def save(self, soc):
        _write_json(self.state_path, {'soc': soc, 'time': time.time()})


def run_daemon(ina, shutdown_cell_v=None, hold_s=30.0, is_charging=lambda: False, log=print):
    """Loop forever: live file every READ_PERIOD, saved estimate every SAVE_PERIOD.

    shutdown_cell_v: if the I x R corrected cell voltage stays below this for hold_s (and the pack
    is not charging), power the Jetson off cleanly before the BMS cuts it at 3.0 V per cell.
    """
    import signal
    est = Estimator(ina, table=load_ocv_table())
    est.start()
    log(f'battery: start {est.soc0 * 100:.0f} % (from {est.source})')
    stop = []
    signal.signal(signal.SIGTERM, lambda *a: stop.append(1))
    last_save = time.monotonic()
    low_since = None
    r = None
    while not stop:
        try:
            r = est.read()
            _write_json(LIVE_PATH, r)
        except OSError as e:
            log(f'battery: read failed: {e}')
            time.sleep(READ_PERIOD)
            continue
        now = time.monotonic()
        if now - last_save > SAVE_PERIOD:
            est.save(r['soc'])
            last_save = now
        if shutdown_cell_v and r['cell_v_rest'] < shutdown_cell_v and not is_charging():
            low_since = low_since or now
            if now - low_since > hold_s:
                log(f'battery: {r["cell_v_rest"]:.2f} V per cell for {hold_s:.0f} s, powering off')
                est.save(r['soc'])
                os.system('systemctl poweroff')
                return
        else:
            low_since = None
        time.sleep(READ_PERIOD)
    if r:
        est.save(r['soc'])
