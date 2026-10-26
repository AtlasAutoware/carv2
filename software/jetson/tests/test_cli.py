"""The `atlas` command against a fake Pico on a pty (no daemon running: it talks to the port)."""
import json
import os
import threading

import pytest

from atlas_hw import cli, vesc


@pytest.fixture
def car(pico, run_dir, world):
    pico.start()
    return pico


def test_status(car, capsys):
    cli.main(['status'])
    out = capsys.readouterr().out
    assert 'supervisor   RUN (test)' in out
    assert 'battery      15.62 V, +1.50 A, BMS 60 %, cells 3.900 3.900 3.910 3.910 V' in out
    assert 'E-stop closed' in out and 'J12 inputs   ESTOP_OK 1, CHG_STAT_N 1' in out


def test_status_json_from_the_daemon_file(car, run_dir, capsys):
    import time
    (run_dir / 'supervisor.json').write_text(json.dumps(dict(car.state, state='LOCKOUT', time=time.time())))
    cli.main(['status', '--json'])
    assert json.loads(capsys.readouterr().out)['state'] == 'LOCKOUT'
    assert 'status' not in car.cmds()                        # did not need to ask the Pico


def test_lidar(car, capsys):
    cli.main(['lidar', 'off'])
    assert car.state['lidar'] is False
    assert 'lidar power off' in capsys.readouterr().out
    cli.main(['lidar'])
    assert 'lidar power off' in capsys.readouterr().out


def test_battery_without_daemon(car, capsys):
    cli.main(['battery'])
    out = capsys.readouterr().out
    assert '15.62 V (bms)' in out and '+1.50 A' in out and 'atlas-battery.service is not running' in out


def test_supervisor_commands(car, capsys):
    cli.main(['supervisor', 'shutdown'])
    cli.main(['supervisor', 'fan', '40'])
    cli.main(['supervisor', 'fan', 'auto'])
    cli.main(['supervisor', 'hb-timeout', '0'])
    cli.main(['supervisor', 'bms-fets', 'charge-off'])
    sent = {m['cmd']: m for m in car.received}
    assert sent['fan']['auto'] is True
    assert sent['hb_timeout']['s'] == 0
    assert sent['bms_fets']['charge'] is False and sent['bms_fets']['discharge'] is True


def test_discharge_off_needs_yes(car):
    with pytest.raises(SystemExit, match='--yes'):
        cli.main(['supervisor', 'bms-fets', 'off'])
    assert 'bms_fets' not in car.cmds()
    cli.main(['supervisor', 'bms-fets', 'off', '--yes'])
    m = [m for m in car.received if m['cmd'] == 'bms_fets'][0]
    assert m['discharge'] is False and m['force'] is True


def test_supervisor_send_prints_the_reply(car, capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(['supervisor', 'send', '{"cmd": "nope"}'])
    assert e.value.code == 1 and 'unknown command' in capsys.readouterr().out
    import argparse
    with pytest.raises(SystemExit, match='unknown command'):         # the other commands stop on err
        cli._request(argparse.Namespace(tty=None), {'cmd': 'nope'})


def test_repl_needs_yes(car):
    with pytest.raises(SystemExit, match='--yes'):
        cli.main(['supervisor', 'repl'])
    cli.main(['supervisor', 'repl', '--yes'])
    assert car.cmds()[-1] == 'repl'


def test_hw_init_sets_lidar_from_config(car, monkeypatch, capsys):
    monkeypatch.setenv('ATLAS_LIDAR_AT_BOOT', '0')
    cli.main(['hw-init', '--wait', '0'])
    assert car.state['lidar'] is False
    assert 'lidar off (ATLAS_LIDAR_AT_BOOT)' in capsys.readouterr().out


def test_halt_hook(car, world, capsys):
    world.chips['/dev/gpiochip0'][106]['value'] = 1
    cli.main(['halt-hook', 'reboot'])
    assert car.received[-1] == {'cmd': 'halt', 'verb': 'reboot'}
    assert world.chips['/dev/gpiochip0'][106]['value'] == 0   # JETSON_UP dropped
    assert 'HALT acknowledged, JETSON_UP low' in capsys.readouterr().out


def test_halt_hook_without_a_pico(run_dir, world, monkeypatch, capsys):
    monkeypatch.setenv('ATLAS_SUPERVISOR_TTY', '/dev/does-not-exist')
    cli.main(['halt-hook', 'poweroff'])                       # never fails the shutdown
    assert 'HALT not sent' in capsys.readouterr().out


def test_vesc_probe(monkeypatch, capsys):
    master, slave = os.openpty()
    monkeypatch.setenv('ATLAS_VESC_TTY', os.ttyname(slave))

    def esc():
        os.read(master, 64)
        os.write(master, vesc.packet(bytes([0, 6, 6]) + b'60_MK6\0' + bytes(12)))
    threading.Thread(target=esc, daemon=True).start()
    try:
        cli.main(['vesc', '--probe'])
    finally:
        os.close(master)
        os.close(slave)
    assert 'firmware    6.06, hardware 60_MK6' in capsys.readouterr().out


def test_rev_a_commands_are_gone():
    for old in ('pd', 'usb-role', 'stm32', 'id'):
        with pytest.raises(SystemExit):
            cli.main([old])
