"""pins.py against the board.

boards/power/PINMAP.md is the single source of truth; boards/power/design.py wires the Pico from
it. Each is compared with pins.py when it exists. The map of Oct 24 (the rev B build brief) is
kept as a record, with the two pins the board design changed since.
"""
import ast
import os
import re

import pytest

import pins

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
PINMAP = os.path.join(REPO, 'boards', 'power', 'PINMAP.md')
DESIGN = os.path.join(REPO, 'boards', 'power', 'design.py')

OCT24_MAP = {
    0: 'BMS_TX', 1: 'BMS_RX', 2: 'PRECHARGE_EN', 3: 'MAIN_EN', 4: 'I2C0_SDA', 5: 'I2C0_SCL',
    6: 'LIDAR_EN', 7: 'JETSON_PWR_KEY', 8: 'JETSON_RESET', 9: 'LATCH_OFF', 10: 'ESTOP_OK',
    11: 'JETSON_UP', 12: 'JETSON_3V3_SENSE', 13: 'BUTTON_N', 14: 'VESC_KILL', 15: 'CHG_PRESENT',
    16: 'FAN_PWM', 17: 'LED_STATUS', 18: 'LED_FAULT', 19: 'ESTOP_OK_TO_JETSON',
    20: 'CHG_STAT_N_TO_JETSON', 21: 'LIDAR_REQ', 22: 'VM_OK', 26: 'VM_SENSE', 27: 'BAT_SENSE',
    28: 'FET_NTC',
}
CHANGED_SINCE = {15: 'CHG_PRESENT_N', 22: 'DEVKIT_PWR'}     # boards/power/design.py, Oct 24 draft


def pinmap_md():
    """{GP: net} from the markdown table rows that start with a GP number."""
    out = {}
    with open(PINMAP) as f:
        for line in f:
            cells = [c.strip().strip('`*') for c in line.strip().strip('|').split('|')]
            if len(cells) >= 3 and re.fullmatch(r'(GP)?\d+', cells[0]):
                gp = int(cells[0].replace('GP', ''))
                net = next((c for c in cells[1:] if re.fullmatch(r'[A-Z][A-Z0-9_]+', c)), None)
                if net:
                    out[gp] = net
    return out


def design_pico_nets():
    """{GP: net} from the `_pico = {...}` pin dictionary in design.py."""
    with open(DESIGN) as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', None) == '_pico' for t in node.targets):
            pins_ = ast.literal_eval(node.value)
            out = {}
            for pin, net in pins_.items():
                m = re.fullmatch(r'GP(\d+)(_ADC\d)?', pin)
                if m and net:
                    out[int(m.group(1))] = net
            return out
    return {}


def test_matches_the_oct24_map_apart_from_the_recorded_changes():
    for gp, net in OCT24_MAP.items():
        net = CHANGED_SINCE.get(gp, net)
        assert getattr(pins, net) == gp, net


@pytest.mark.skipif(not os.path.exists(DESIGN), reason='boards/power/design.py not written yet')
def test_matches_the_board_design():
    nets = design_pico_nets()
    assert nets, 'no _pico pin dictionary in design.py'
    for gp, net in nets.items():
        assert hasattr(pins, net), f'design.py has {net} on GP{gp}; pins.py has no {net}'
        assert getattr(pins, net) == gp, f'{net}: design.py GP{gp}, pins.py GP{getattr(pins, net)}'


@pytest.mark.skipif(not os.path.exists(PINMAP), reason='boards/power/PINMAP.md not written yet')
def test_matches_boards_power_pinmap():
    table = pinmap_md()
    assert table, 'no GP rows found in PINMAP.md'
    for gp, net in table.items():
        assert hasattr(pins, net), f'PINMAP.md has {net} on GP{gp}; pins.py has no {net}'
        assert getattr(pins, net) == gp, f'{net}: PINMAP.md GP{gp}, pins.py GP{getattr(pins, net)}'


def test_every_pin_used_once():
    used = [gp for _, gp, _ in pins.OUTPUTS] + [gp for _, gp, _ in pins.INPUTS]
    used += [gp for _, gp in pins.ADCS] + list(pins.HIGH_Z) + [pins.FAN_PWM, pins.BMS_TX, pins.BMS_RX]
    assert len(used) == len(set(used))
    assert set(gp for _, gp in pins.ADCS) <= {26, 27, 28}


def test_safe_levels():
    safe = {name: level for name, _, level in pins.OUTPUTS}
    for name in ('MAIN_EN', 'PRECHARGE_EN', 'VESC_KILL', 'LIDAR_EN', 'JETSON_PWR_KEY', 'JETSON_RESET',
                 'LATCH_OFF'):
        assert safe[name] == 0, name
