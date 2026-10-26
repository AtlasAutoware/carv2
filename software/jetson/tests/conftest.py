import os
import sys

import pytest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, '..'))
sys.path.insert(0, HERE)


@pytest.fixture
def world(monkeypatch):
    """Fake libgpiod 1.x (the version JetPack 6 ships) with the four J12 lines."""
    from fakes_revb import GpioWorld, gpiod_v1
    w = GpioWorld()
    monkeypatch.setitem(sys.modules, 'gpiod', gpiod_v1(w))
    return w


@pytest.fixture
def world_v2(monkeypatch):
    from fakes_revb import GpioWorld, gpiod_v2
    w = GpioWorld()
    m, line = gpiod_v2(w)
    monkeypatch.setitem(sys.modules, 'gpiod', m)
    monkeypatch.setitem(sys.modules, 'gpiod.line', line)
    return w


@pytest.fixture
def pico(monkeypatch):
    from fakes_revb import FakePico
    p = FakePico()
    monkeypatch.setenv('ATLAS_SUPERVISOR_TTY', p.slave_path)
    yield p
    p.close()


@pytest.fixture
def run_dir(tmp_path, monkeypatch):
    """/run/atlas and /var/lib/atlas in a temporary folder (the socket in a short one: AF_UNIX
    paths are limited to 108 bytes)."""
    import shutil
    import tempfile
    from atlas_hw import battery, supervisor
    sock_dir = tempfile.mkdtemp(prefix='atl')
    monkeypatch.setattr(supervisor, 'SOCKET_PATH', os.path.join(sock_dir, 's.sock'))
    monkeypatch.setattr(supervisor, 'LIVE_PATH', str(tmp_path / 'supervisor.json'))
    monkeypatch.setattr(battery, 'LIVE_PATH', str(tmp_path / 'battery.json'))
    monkeypatch.setattr(battery, 'STATE_PATH', str(tmp_path / 'state.json'))
    yield tmp_path
    shutil.rmtree(sock_dir, ignore_errors=True)
