import sys

import pytest

from atlas_hw import gpio


@pytest.mark.parametrize('fixture', ['world', 'world_v2'])
def test_request_outputs_and_inputs(fixture, request):
    w = request.getfixturevalue(fixture)
    with gpio.Lines(outputs={'JETSON_UP': 1, 'LIDAR_REQ': 0}, inputs=('ESTOP_OK', 'CHG_STAT_N')) as g:
        chip = w.chips['/dev/gpiochip0']
        assert chip[106]['value'] == 1 and chip[106]['dir'] == 'out' and chip[106]['owner'] == 'atlas'
        assert chip[105]['value'] == 0
        assert g.get('ESTOP_OK') == 1 and g.get('CHG_STAT_N') == 1
        g.set('JETSON_UP', 0)
        assert chip[106]['value'] == 0
        with pytest.raises(ValueError):
            g.set('ESTOP_OK', 1)
    assert all(line['owner'] is None for line in w.chips['/dev/gpiochip0'].values())


@pytest.mark.parametrize('fixture', ['world', 'world_v2'])
def test_found_by_name_when_the_offset_is_different(fixture, request):
    w = request.getfixturevalue(fixture)
    chip = w.chips['/dev/gpiochip0']
    chip[200] = chip.pop(106)                       # PQ.06 is somewhere else on this JetPack
    with gpio.Lines(outputs={'JETSON_UP': 1}):
        assert chip[200]['value'] == 1


def test_environment_override(world, monkeypatch):
    monkeypatch.setenv('ATLAS_GPIO_JETSON_UP', 'gpiochip0:105')
    with gpio.Lines(outputs={'JETSON_UP': 1}):
        assert world.chips['/dev/gpiochip0'][105]['value'] == 1
    monkeypatch.setenv('ATLAS_GPIO_JETSON_UP', 'PH.00')
    assert gpio.spec('JETSON_UP') == ('/dev/gpiochip0', None, 'PH.00')


def test_busy_line_and_read_inputs(world):
    held = gpio.Lines(inputs=('ESTOP_OK',), consumer='atlas_power')
    with pytest.raises(gpio.GpioUnavailable):
        gpio.Lines(inputs=('ESTOP_OK',))
    assert gpio.read_inputs() == {}
    held.release()
    assert gpio.read_inputs() == {'ESTOP_OK': 1, 'CHG_STAT_N': 1}


def test_no_libgpiod(monkeypatch):
    monkeypatch.setitem(sys.modules, 'gpiod', None)
    with pytest.raises(gpio.GpioUnavailable, match='python3-libgpiod'):
        gpio.Lines(outputs={'JETSON_UP': 1})


@pytest.mark.parametrize('level, on, current, edges', [
    (0, True, None, [1]),           # rising edge
    (1, False, None, [0]),          # falling edge
    (0, False, None, [1, 0]),       # already low: pulse so the Pico sees a falling edge
    (1, True, None, [0, 1]),        # already high: pulse the other way
    (0, True, True, [1]),           # already on: just bring the level into line
    (1, True, True, []),            # already on and level right: nothing
    (1, False, False, [0]),
])
def test_lidar_edges(world, level, on, current, edges):
    with gpio.Lines(outputs={'LIDAR_REQ': level}) as g:
        world.history.clear()
        gpio.request_lidar(g, on, current=current, sleep=lambda s: None)
        assert [v for off, v in world.history if off == 105] == edges
        assert g.values['LIDAR_REQ'] == (1 if on else 0)
