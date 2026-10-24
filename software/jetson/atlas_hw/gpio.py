"""The four J12 GPIO lines the Jetson uses on rev B, through libgpiod.

  JETSON_UP   out, pin 31  high while the Atlas software runs (the supervisor reads it as "the
                           Jetson is up"; the shutdown hook drives it low at the very end)
  LIDAR_REQ   out, pin 29  lidar power request: a rising edge asks for on, a falling edge for off
  ESTOP_OK    in,  pin 33  high = E-stop loop closed (the Pico drives it while the Jetson is up)
  CHG_STAT_N  in,  pin 32  low = charger connected

Works with both Python bindings: python3-libgpiod 1.x (Ubuntu 22.04 / JetPack 6 ships 1.6.3) and
gpiod 2.x. Lines are looked up by name (`gpioinfo` shows names such as PQ.06 on Tegra), then by
the offset in board.py. Neither has been checked on the car's JetPack: run `gpioinfo` and set
ATLAS_GPIO_<NAME> in /etc/atlas/atlas.conf if they differ.

JetPack 6 note: NVIDIA reported a gpioset output problem in JP 6.0/6.1, fixed in 6.2 (R36.4.3).
If the outputs do not move on the car, the supervisor link still carries everything they do.
"""
import os
import time

from . import board


class GpioUnavailable(OSError):
    pass


def _gpiod():
    try:
        import gpiod
    except ImportError as e:
        raise GpioUnavailable('libgpiod Python bindings missing (sudo apt install python3-libgpiod)') from e
    if hasattr(gpiod, 'request_lines'):
        return 2, gpiod
    if hasattr(gpiod, 'Chip') and hasattr(gpiod, 'LINE_REQ_DIR_OUT'):
        return 1, gpiod
    raise GpioUnavailable('unrecognised gpiod module')


def _chip_path(chip):
    chip = str(chip)
    if chip.isdigit():
        chip = 'gpiochip' + chip
    return chip if chip.startswith('/') else '/dev/' + chip


def spec(name):
    """(chip path, offset or None, line name or None) for a line, from the environment or board.py."""
    chip, offset, line_name = getattr(board, 'GPIO_' + name)
    override = os.environ.get('ATLAS_GPIO_' + name, '').strip()
    if override:
        if ':' in override:
            chip, rest = override.split(':', 1)
        else:
            rest = override
        if rest.isdigit():
            offset, line_name = int(rest), None
        else:
            offset, line_name = None, rest
    return _chip_path(chip), offset, line_name


def _find_v1(gpiod, chip, offset, line_name):
    if line_name:
        try:
            line = chip.find_line(line_name)
            if line is not None:
                return line
        except (OSError, AttributeError, TypeError):
            pass
    if offset is None:
        raise GpioUnavailable(f'no GPIO line named {line_name}')
    return chip.get_line(offset)


def _offset_v2(gpiod, path, offset, line_name):
    if line_name:
        try:
            with gpiod.Chip(path) as chip:
                return chip.line_offset_from_id(line_name)
        except (OSError, ValueError, AttributeError):
            pass
    if offset is None:
        raise GpioUnavailable(f'no GPIO line named {line_name}')
    return offset


class Lines:
    """A held request for some of the J12 lines.

        with Lines(outputs={'JETSON_UP': 1}) as g:
            g.set('JETSON_UP', 0)
    """

    def __init__(self, outputs=None, inputs=(), consumer='atlas'):
        self.outputs = dict(outputs or {})
        self.inputs = tuple(inputs)
        self.values = dict(self.outputs)
        self.version, gpiod = _gpiod()
        self._gpiod = gpiod
        self._lines = {}
        self._requests = []
        self._chips = {}
        try:
            if self.version == 1:
                self._request_v1(consumer)
            else:
                self._request_v2(consumer)
        except OSError as e:
            self.release()
            raise GpioUnavailable(f'GPIO request failed: {e}') from e

    def _request_v1(self, consumer):
        gpiod = self._gpiod
        for name in list(self.outputs) + list(self.inputs):
            path, offset, line_name = spec(name)
            chip = self._chips.get(path)
            if chip is None:
                chip = self._chips[path] = gpiod.Chip(path)
            line = _find_v1(gpiod, chip, offset, line_name)
            if name in self.outputs:
                line.request(consumer=consumer, type=gpiod.LINE_REQ_DIR_OUT,
                             default_vals=[1 if self.outputs[name] else 0])
            else:
                line.request(consumer=consumer, type=gpiod.LINE_REQ_DIR_IN)
            self._lines[name] = line

    def _request_v2(self, consumer):
        gpiod = self._gpiod
        from gpiod.line import Direction, Value
        by_chip = {}
        for name in list(self.outputs) + list(self.inputs):
            path, offset, line_name = spec(name)
            off = _offset_v2(gpiod, path, offset, line_name)
            if name in self.outputs:
                settings = gpiod.LineSettings(direction=Direction.OUTPUT,
                                              output_value=Value.ACTIVE if self.outputs[name] else Value.INACTIVE)
            else:
                settings = gpiod.LineSettings(direction=Direction.INPUT)
            by_chip.setdefault(path, {})[off] = settings
            self._lines[name] = (path, off)
        reqs = {}
        for path, config in by_chip.items():
            reqs[path] = gpiod.request_lines(path, consumer=consumer, config=config)
            self._requests.append(reqs[path])
        self._v2req = reqs

    def get(self, name):
        if self.version == 1:
            return int(self._lines[name].get_value())
        from gpiod.line import Value
        path, off = self._lines[name]
        return 1 if self._v2req[path].get_value(off) == Value.ACTIVE else 0

    def set(self, name, value):
        if name not in self.outputs:
            raise ValueError(f'{name} is not an output')
        v = 1 if value else 0
        if self.version == 1:
            self._lines[name].set_value(v)
        else:
            from gpiod.line import Value
            path, off = self._lines[name]
            self._v2req[path].set_value(off, Value.ACTIVE if v else Value.INACTIVE)
        self.values[name] = v

    def release(self):
        if self.version == 1:
            for line in self._lines.values():
                try:
                    line.release()
                except (OSError, AttributeError):
                    pass
            for chip in self._chips.values():
                try:
                    chip.close()
                except (OSError, AttributeError):
                    pass
        else:
            for req in self._requests:
                try:
                    req.release()
                except (OSError, AttributeError):
                    pass
        self._lines = {}
        self._requests = []
        self._chips = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.release()
        return False


def read_inputs(names=board.GPIO_INPUTS):
    """{name: 0|1} read with a short request, or {} if the lines are busy or libgpiod is missing."""
    try:
        with Lines(inputs=names, consumer='atlas-read') as g:
            return {n: g.get(n) for n in names}
    except GpioUnavailable:
        return {}


def request_lidar(lines, on, current=None, sleep=time.sleep):
    """Ask for lidar power through LIDAR_REQ, which the Pico reads by its edges: a rising edge
    means on, a falling edge off (the lidar command on the USB link does the same job).

    current is the lidar state the supervisor last reported (None if unknown). When it already
    equals the request, the level is only brought into line (any edge that makes points the
    same way, so it changes nothing). Otherwise an edge towards the request is made, with a
    60 ms pulse the other way first if the line already sits at the requested level (the Pico
    filters edges for 20 ms)."""
    want = 1 if on else 0
    level = 1 if lines.values.get('LIDAR_REQ') else 0
    if current is not None and bool(current) == bool(on):
        if level != want:
            lines.set('LIDAR_REQ', want)
        return
    if level == want:
        lines.set('LIDAR_REQ', 1 - want)
        sleep(0.06)
    lines.set('LIDAR_REQ', want)
