"""Rev B stand-ins: a scripted Pico on a pseudo-terminal, and fake libgpiod modules (1.x and 2.x).

FakePico answers the supervisor protocol on the master side of a pty; the code under test opens
the slave side as if it were /dev/atlas_supervisor. It is deliberately simple. The real firmware
is exercised against the Jetson code in test_integration_firmware.py.
"""
import errno
import json
import os
import select
import threading
import tty
import types


# ---------------------------------------------------------------- a scripted Pico
class FakePico:
    def __init__(self):
        self.master, self.slave = os.openpty()
        tty.setraw(self.slave)          # a pty echoes by default; a Pico's CDC port does not
        self.slave_path = os.ttyname(self.slave)
        self.received = []
        self.state = {'t': 'status', 'state': 'RUN', 'why': 'test', 'bat': 15.6, 'vm': 15.6, 'lidar': True,
                      'estop': True, 'chg': False, 'fan': 30, 'fan_auto': True, 'main': True, 'kill': False,
                      'ms': 1000, 'fw': 'fake', 'jet': {'hb': 0.5, 'up': True, 'v33': True, 'hb_timeout': 60},
                      'bms': {'ok': True, 'age': 0.4, 'v': 15.62, 'i': 1.5, 'soc': 60, 'cells': [3.9, 3.9, 3.91, 3.91],
                              'temps': [24.0, 25.0], 'rem_ah': 5.0, 'full_ah': 8.4, 'fet_chg': True,
                              'fet_dsg': True, 'prot': 0}}
        self.silent = False
        self.extra = []             # raw lines to emit on the next pump
        self._buf = b''
        self._stop = threading.Event()
        self._thread = None

    def write(self, obj_or_text):
        if isinstance(obj_or_text, dict):
            obj_or_text = json.dumps(obj_or_text)
        os.write(self.master, obj_or_text.encode() + b'\n')

    def answer(self, msg):
        cmd = msg.get('cmd')
        reply = None
        if cmd == 'status':
            reply = dict(self.state)
        elif cmd == 'lidar':
            self.state['lidar'] = msg['on']
            reply = {'t': 'ack', 'cmd': 'lidar', 'on': msg['on']}
        elif cmd in ('hb', ):
            return
        elif cmd == 'nope':
            reply = {'t': 'err', 'cmd': 'nope', 'msg': 'unknown command'}
        elif cmd is not None:
            reply = {'t': 'ack', 'cmd': cmd}
        if reply is not None and 'id' in msg:
            reply['id'] = msg['id']
        if reply is not None:
            self.write(reply)

    def pump(self, timeout=0.0):
        """Read what the Jetson side wrote and answer it."""
        for line in self.extra:
            self.write(line)
        self.extra = []
        r, _, _ = select.select([self.master], [], [], timeout)
        if not r:
            return
        try:
            data = os.read(self.master, 4096)
        except OSError as e:
            if e.errno == errno.EIO:
                return
            raise
        self._buf += data
        *lines, self._buf = self._buf.split(b'\n')
        for line in lines:
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                self.received.append({'raw': line.decode('utf-8', 'replace')})
                continue
            self.received.append(msg)
            if not self.silent:
                self.answer(msg)

    def start(self):
        def loop():
            while not self._stop.is_set():
                self.pump(0.02)
        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(1.0)

    def close(self):
        self.stop()
        for fd in (self.master, self.slave):
            try:
                os.close(fd)
            except OSError:
                pass

    def cmds(self):
        return [m.get('cmd') for m in self.received]


# ---------------------------------------------------------------- fake libgpiod
class GpioWorld:
    """The lines on the fake chips: {path: {offset: dict(name, value, owner)}}."""

    def __init__(self):
        self.chips = {'/dev/gpiochip0': {
            106: {'name': 'PQ.06', 'value': 0, 'owner': None, 'dir': 'in'},
            105: {'name': 'PQ.05', 'value': 0, 'owner': None, 'dir': 'in'},
            43: {'name': 'PH.00', 'value': 1, 'owner': None, 'dir': 'in'},
            41: {'name': 'PG.06', 'value': 1, 'owner': None, 'dir': 'in'},
        }}
        self.history = []           # (offset, value) every time an output changes

    def line(self, path, offset):
        try:
            return self.chips[path][offset]
        except KeyError:
            raise OSError(errno.EINVAL, f'no line {offset} on {path}')

    def find(self, path, name):
        for off, line in self.chips.get(path, {}).items():
            if line['name'] == name:
                return off
        return None

    def claim(self, path, offset, owner, direction, value=None):
        line = self.line(path, offset)
        if line['owner'] is not None:
            raise OSError(errno.EBUSY, 'Device or resource busy')
        line['owner'] = owner
        line['dir'] = direction
        if direction == 'out':
            self.set(path, offset, value)

    def set(self, path, offset, value):
        line = self.line(path, offset)
        line['value'] = 1 if value else 0
        self.history.append((offset, line['value']))

    def free(self, path, offset):
        self.line(path, offset)['owner'] = None


def gpiod_v1(world):
    m = types.ModuleType('gpiod')
    m.LINE_REQ_DIR_IN = 2
    m.LINE_REQ_DIR_OUT = 3

    class Line:
        def __init__(self, path, offset):
            self.path, self.offset = path, offset

        def request(self, consumer, type, default_vals=None):
            if type == m.LINE_REQ_DIR_OUT:
                world.claim(self.path, self.offset, consumer, 'out', default_vals[0])
            else:
                world.claim(self.path, self.offset, consumer, 'in')

        def get_value(self):
            return world.line(self.path, self.offset)['value']

        def set_value(self, v):
            world.set(self.path, self.offset, v)

        def release(self):
            world.free(self.path, self.offset)

    class Chip:
        def __init__(self, path):
            if path not in world.chips:
                raise OSError(errno.ENOENT, path)
            self.path = path

        def get_line(self, offset):
            world.line(self.path, offset)
            return Line(self.path, offset)

        def find_line(self, name):
            off = world.find(self.path, name)
            return None if off is None else Line(self.path, off)

        def close(self):
            pass

    m.Chip = Chip
    return m


def gpiod_v2(world):
    m = types.ModuleType('gpiod')
    line_mod = types.ModuleType('gpiod.line')

    class Direction:
        INPUT = 'in'
        OUTPUT = 'out'

    class Value:
        ACTIVE = 1
        INACTIVE = 0

    line_mod.Direction = Direction
    line_mod.Value = Value

    class LineSettings:
        def __init__(self, direction='in', output_value=None):
            self.direction, self.output_value = direction, output_value

    class Request:
        def __init__(self, path, consumer, config):
            self.path = path
            self.offsets = list(config)
            done = []
            try:
                for off, st in config.items():
                    world.claim(path, off, consumer, st.direction, st.output_value)
                    done.append(off)
            except OSError:
                for off in done:
                    world.free(path, off)
                raise

        def get_value(self, off):
            return Value.ACTIVE if world.line(self.path, off)['value'] else Value.INACTIVE

        def set_value(self, off, v):
            world.set(self.path, off, v == Value.ACTIVE)

        def release(self):
            for off in self.offsets:
                world.free(self.path, off)

    class Chip:
        def __init__(self, path):
            self.path = path

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def line_offset_from_id(self, name):
            off = world.find(self.path, name)
            if off is None:
                raise OSError(errno.ENOENT, name)
            return off

    m.LineSettings = LineSettings
    m.Chip = Chip
    m.request_lines = lambda path, consumer, config: Request(path, consumer, config)
    m.line = line_mod
    return m, line_mod
