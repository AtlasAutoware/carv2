"""The battery estimate, fed from the supervisor's status frames (rev B: JBD BMS through the Pico)."""
import json

import pytest

from atlas_hw import battery


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def status(v=15.36, i=0.0, ok=True, chg=False, **bms):
    b = {'ok': ok, 'v': v, 'i': i, 'soc': 55, 'cells': [v / 4] * 4, 'temps': [24.0], 'rem_ah': 4.6,
         'full_ah': 8.4, 'prot': 0}
    b.update(bms)
    return {'t': 'status', 'bat': round(v + 0.05, 2), 'chg': chg, 'bms': b if ok else {'ok': False}}


def test_ocv_lookup():
    assert battery.soc_from_cell_voltage(3.84) == pytest.approx(0.5)
    assert battery.soc_from_cell_voltage(3.82) == pytest.approx(0.45)
    assert battery.soc_from_cell_voltage(2.9) == 0.0
    assert battery.soc_from_cell_voltage(4.3) == 1.0


def test_pack_source_integrates_bms_current():
    clock = Clock()
    src = battery.PackSource(clock)
    r = src.reading(status(i=2.0))
    assert r['source'] == 'bms' and r['charge_c'] == 0.0 and r['cells'] == [3.84] * 4
    clock.t += 1.0
    r = src.reading(status(i=4.0))
    assert r['charge_c'] == pytest.approx(3.0)              # trapezoid: (2 + 4) / 2 x 1 s
    clock.t += 30.0                                         # link was down: not integrated
    assert src.reading(status(i=4.0))['charge_c'] == pytest.approx(3.0)


def test_pack_source_falls_back_to_the_pico_divider():
    src = battery.PackSource(Clock())
    r = src.reading(status(ok=False))
    assert r['source'] == 'pico_adc' and r['voltage'] == pytest.approx(15.41) and not r['current_known']
    assert src.reading({'t': 'status'}) is None


def test_estimator_voltage_start_then_coulombs(tmp_path):
    clock = Clock()
    src = battery.PackSource(clock)
    est = battery.Estimator(r_pack=0.0, state_path=str(tmp_path / 's.json'))
    r = src.reading(status(v=15.36, i=8.4 * 3600 * 0.1 / 100.0))     # 10 % of 8.4 Ah over 100 s
    assert est.start(r) == pytest.approx(0.5, abs=0.01) and est.source == 'voltage'
    for _ in range(100):
        clock.t += 1.0
        r = src.reading(status(v=15.36, i=8.4 * 3600 * 0.1 / 100.0))
    assert est.read(r)['soc'] == pytest.approx(0.4, abs=0.01)


def test_estimator_trusts_close_saved_state(tmp_path):
    path = tmp_path / 's.json'
    r = battery.PackSource(Clock()).reading(status(v=15.36))
    path.write_text(json.dumps({'soc': 0.55}))
    est = battery.Estimator(r_pack=0.0, state_path=str(path))
    assert est.start(r) == pytest.approx(0.55) and est.source == 'saved'
    path.write_text(json.dumps({'soc': 0.95}))              # charged with the car off
    est = battery.Estimator(r_pack=0.0, state_path=str(path))
    assert est.start(r) == pytest.approx(0.5, abs=0.01) and est.source == 'voltage'


def test_monitor_writes_live_file_and_shuts_down_on_low_cells(run_dir):
    clock = Clock()
    calls = []
    mon = battery.BatteryMonitor(shutdown_cell_v=3.30, hold_s=30.0, log=lambda *a: None,
                                 poweroff=lambda: calls.append(1), clock=clock,
                                 estimator=battery.Estimator(r_pack=0.0), source=battery.PackSource(clock))
    mon.on_status(status(v=15.36))
    live = battery.read_live()
    assert live['soc'] == pytest.approx(0.5, abs=0.01) and live['bms_soc'] == 55
    for _ in range(40):                                     # 3.20 V per cell, but charging
        clock.t += 1.0
        mon.on_status(status(v=12.8, chg=True))
    assert calls == []
    for _ in range(29):
        clock.t += 1.0
        mon.on_status(status(v=12.8))
    assert calls == []
    for _ in range(3):
        clock.t += 1.0
        mon.on_status(status(v=12.8))
    assert calls == [1]                                     # once
    mon.stop()
    assert json.loads((run_dir / 'state.json').read_text())['soc'] >= 0
