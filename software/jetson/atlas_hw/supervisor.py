"""The power board's supervisor (a Raspberry Pi Pico running firmware/supervisor/) over USB CDC.

Protocol (firmware/supervisor/README.md has the full list): one JSON object per line, both ways.
  Jetson -> Pico  {"cmd": "status" | "lidar" | "shutdown" | "reboot" | "halt" | "hb" | "bye" |
                   "bms_fets" | "fan" | "hb_timeout" | "log" | "version" | "help" | "repl", ...,
                   "id": n}
  Pico -> Jetson  {"t": "status" | "ack" | "err" | "evt", ..., "id": n (replies only)}

Only one process may read the port, so:
  Daemon        runs inside `atlas battery-daemon` (atlas-battery.service). It owns the port, sends
                the 1 Hz heartbeat, holds JETSON_UP (and LIDAR_REQ) high, writes the latest status
                to /run/atlas/supervisor.json, logs the Pico's events to the journal, and answers
                other programs on /run/atlas/supervisor.sock. When it stops it sends "bye", which
                gives the Jetson's shutdown 120 s before the supervisor stops waiting for HALT.
  DaemonClient  a request through that socket (the CLI and the ROS node use this).
  Link          a direct connection to /dev/atlas_supervisor: the daemon itself, the shutdown hook
                (the daemon is gone by then), and the CLI when the daemon is not running.
  connect()     DaemonClient if the daemon answers, else Link.
"""
import errno
import json
import os
import select
import socket
import termios
import time

from . import board

SOCKET_PATH = '/run/atlas/supervisor.sock'
LIVE_PATH = '/run/atlas/supervisor.json'


class SupervisorError(IOError):
    pass


# ---------------------------------------------------------------- the serial port
def raw_tty(fd, baud=board.SUPERVISOR_BAUD):
    """Raw mode, no echo, no flow control. Echo matters: a cooked tty would send every status line
    straight back to the Pico."""
    try:
        iflag, oflag, cflag, lflag, ispeed, ospeed, cc = termios.tcgetattr(fd)
    except termios.error:
        return
    iflag &= ~(termios.IGNBRK | termios.BRKINT | termios.PARMRK | termios.ISTRIP | termios.INLCR |
               termios.IGNCR | termios.ICRNL | termios.IXON | termios.IXOFF | termios.IXANY)
    oflag &= ~termios.OPOST
    lflag &= ~(termios.ECHO | termios.ECHONL | termios.ICANON | termios.ISIG | termios.IEXTEN)
    cflag &= ~(termios.CSIZE | termios.PARENB | getattr(termios, 'CRTSCTS', 0))
    cflag |= termios.CS8 | termios.CREAD | termios.CLOCAL
    # VMIN 1 with O_NONBLOCK: a read with nothing waiting fails with EAGAIN and a read of 0 bytes
    # means the port hung up (Pico unplugged). With VMIN 0 both would read as 0 bytes.
    cc[termios.VMIN] = 1
    cc[termios.VTIME] = 0
    speed = getattr(termios, f'B{baud}', termios.B115200)
    termios.tcsetattr(fd, termios.TCSANOW, [iflag, oflag, cflag, lflag, speed, speed, cc])


def open_tty(path):
    try:
        fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    except OSError as e:
        raise SupervisorError(f'cannot open {path}: {e.strerror}') from e
    raw_tty(fd)
    return fd


def encode(obj):
    return (json.dumps(obj, separators=(',', ':')) + '\n').encode()


def parse(line):
    """A JSON object from one line, or None."""
    line = line.strip()
    if not line.startswith('{'):
        return None
    try:
        obj = json.loads(line)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


class LineBuffer:
    def __init__(self, limit=8192):
        self.buf = b''
        self.limit = limit

    def feed(self, data):
        parts = (self.buf + data).replace(b'\r', b'\n').split(b'\n')
        self.buf = parts[-1][-self.limit:]
        return [p.decode('utf-8', 'replace').strip() for p in parts[:-1] if p.strip()]


def in_repl(lines):
    """True if recent non-JSON lines look like the MicroPython REPL (the firmware is stopped)."""
    return any(x.startswith('>>>') or x.startswith('MicroPython v') or x.startswith('ATLAS supervisor stopped')
               for x in lines)


class Link:
    def __init__(self, path=None, fd=None):
        self.path = path or board.supervisor_tty()
        self.fd = open_tty(self.path) if fd is None else fd
        self._lines = LineBuffer()
        self.other = []                 # the last few non-JSON lines (a REPL prompt, a traceback)
        self.unsolicited = []           # frames that arrived while waiting for a reply
        self._id = (os.getpid() % 1000) * 1000

    def fileno(self):
        return self.fd

    def send(self, obj, timeout=1.0):
        data = encode(obj)
        end = time.monotonic() + timeout
        while data:
            try:
                n = os.write(self.fd, data)
                data = data[n:]
            except BlockingIOError:
                if time.monotonic() > end:
                    raise SupervisorError('write to the supervisor timed out')
                select.select([], [self.fd], [], 0.05)
            except OSError as e:
                raise SupervisorError(f'write to the supervisor failed: {e.strerror}') from e

    def read_available(self):
        out = []
        while True:
            try:
                data = os.read(self.fd, 4096)
            except BlockingIOError:
                break
            except OSError as e:
                if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    break
                raise SupervisorError(f'supervisor link lost: {e.strerror}') from e
            if not data:
                raise SupervisorError('supervisor link closed')
            for line in self._lines.feed(data):
                msg = parse(line)
                if msg is None:
                    self.other = (self.other + [line])[-5:]
                else:
                    out.append(msg)
        return out

    def wait(self, timeout):
        r, _, _ = select.select([self.fd], [], [], max(0.0, timeout))
        return self.read_available() if r else []

    def request(self, obj, timeout=2.0):
        obj = dict(obj)
        self._id += 1
        obj['id'] = self._id
        self.send(obj)
        end = time.monotonic() + timeout
        while True:
            left = end - time.monotonic()
            if left <= 0:
                hint = ''
                if in_repl(self.other):
                    hint = ' (it is in the MicroPython REPL: press Ctrl-D in a terminal to restart it)'
                raise SupervisorError(f'the supervisor did not answer "{obj.get("cmd")}" within {timeout:g} s{hint}')
            for msg in self.wait(left):
                if msg.get('id') == obj['id'] and msg.get('t') in ('ack', 'err', 'status'):
                    return msg
                self.unsolicited = (self.unsolicited + [msg])[-50:]

    def close(self):
        try:
            os.close(self.fd)
        except OSError:
            pass


class DaemonClient:
    """One request per connection to atlas-battery.service's socket."""

    def __init__(self, path=None, timeout=5.0):
        self.path = path or SOCKET_PATH
        self.timeout = timeout

    def request(self, obj, timeout=None):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout or self.timeout)
        data = b''
        try:
            s.connect(self.path)
            s.sendall(encode(obj))
            while b'\n' not in data:
                chunk = s.recv(65536)
                if not chunk:
                    break
                data += chunk
        except OSError as e:
            raise SupervisorError(f'atlas-battery.service ({self.path}): {e}') from e
        finally:
            s.close()
        msg = parse(data.split(b'\n')[0].decode('utf-8', 'replace'))
        if msg is None:
            raise SupervisorError('no reply from atlas-battery.service')
        return msg

    def close(self):
        pass


def connect(socket_path=None, tty=None):
    socket_path = socket_path or SOCKET_PATH
    if os.path.exists(socket_path):
        client = DaemonClient(socket_path)
        try:
            client.request({'cmd': 'daemon'}, timeout=2.0)
            return client
        except SupervisorError:
            pass
    return Link(tty)


def read_live(path=None, max_age=5.0):
    """The daemon's latest status frame, or None if it is not running (or the file is stale)."""
    try:
        with open(path or LIVE_PATH) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if time.time() - data.get('time', 0) > max_age:
        return None
    return data


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f)
    os.replace(tmp, path)


def boot_id():
    try:
        with open('/proc/sys/kernel/random/boot_id') as f:
            return f.read().strip().replace('-', '')[:8]
    except OSError:
        return 'unknown'


def uptime_s():
    try:
        with open('/proc/uptime') as f:
            return int(float(f.read().split()[0]))
    except (OSError, ValueError, IndexError):
        return None


def describe_event(e):
    """One journal line for a Pico event."""
    name = e.get('evt')
    if name == 'state':
        return f"state {e.get('was')} -> {e.get('to')} ({e.get('why')})"
    rest = ', '.join(f'{k}={v}' for k, v in e.items() if k not in ('t', 'evt', 'ms'))
    return f'{name}: {rest}' if rest else str(name)


# ---------------------------------------------------------------- the daemon
class Daemon:
    HB_PERIOD = 1.0
    REQUEST_TIMEOUT = 3.0
    REOPEN_PERIOD = 2.0
    LIDAR_SYNC_HOLD = 3.0       # after a lidar request, do not resync LIDAR_REQ from status for this long

    def __init__(self, open_link=Link, lines=None, socket_path=None, live_path=None,
                 boot=None, on_status=None, log=print, clock=time.monotonic):
        self.open_link = open_link
        self.lines = lines
        self.socket_path = socket_path or SOCKET_PATH
        self.live_path = live_path or LIVE_PATH
        self.boot = boot or boot_id()
        self.on_status = on_status
        self.log = log
        self.clock = clock
        self.link = None
        self.server = None
        self.clients = {}           # socket -> received bytes
        self.pending = {}           # our id -> (socket, client's id, deadline)
        self.paused = False         # the supervisor is in its REPL: let go of the port
        self.last_status = None
        self.t_status = None
        self.lidar_state = None
        self._next_id = 0
        self._t_hb = None
        self._t_open = None
        self._open_error = None
        self._lidar_hold = 0.0

    # ---- set-up and tear-down
    def start_server(self):
        os.makedirs(os.path.dirname(self.socket_path), exist_ok=True)
        try:
            os.unlink(self.socket_path)
        except FileNotFoundError:
            pass
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.bind(self.socket_path)
        s.listen(8)
        s.setblocking(False)
        try:
            import grp
            os.chown(self.socket_path, -1, grp.getgrnam('dialout').gr_gid)
            os.chmod(self.socket_path, 0o660)
        except (KeyError, OSError, ImportError):
            os.chmod(self.socket_path, 0o666)
        self.server = s

    def stop(self):
        """Say bye (the supervisor then waits up to 120 s for HALT instead of 60 s for a heartbeat)."""
        if self.link is not None:
            try:
                self.link.send({'cmd': 'bye'})
            except (SupervisorError, OSError):
                pass
            self.link.close()
            self.link = None
        for sock in list(self.clients):
            sock.close()
        self.clients = {}
        if self.server is not None:
            self.server.close()
            self.server = None
            try:
                os.unlink(self.socket_path)
            except OSError:
                pass

    def run(self, should_stop=lambda: False):
        self.start_server()
        try:
            while not should_stop():
                self.step()
        finally:
            self.stop()

    # ---- the loop
    def step(self, max_wait=0.5):
        now = self.clock()
        if self.link is None and not self.paused and (
                self._t_open is None or now - self._t_open >= self.REOPEN_PERIOD):
            self._t_open = now
            self._open()
        if self.link is not None and (self._t_hb is None or now - self._t_hb >= self.HB_PERIOD):
            self._t_hb = now
            self._send({'cmd': 'hb', 'boot': self.boot, 'up': uptime_s()})
        fds = list(self.clients)
        if self.server is not None:
            fds.append(self.server)
        if self.link is not None:
            fds.append(self.link.fileno())
        wait = max_wait
        if self.link is not None:
            wait = min(wait, max(0.0, self._t_hb + self.HB_PERIOD - self.clock()))
        try:
            ready, _, _ = select.select(fds, [], [], wait)
        except (OSError, ValueError):
            ready = []
        for r in ready:
            if r is self.server:
                self._accept()
            elif self.link is not None and r == self.link.fileno():
                self._from_pico()
            elif r in self.clients:
                self._from_client(r)
        self._expire()

    def _open(self):
        try:
            self.link = self.open_link()
        except (SupervisorError, OSError) as e:
            if str(e) != self._open_error:
                self.log(f'supervisor: {e} (retrying every {self.REOPEN_PERIOD:g} s)')
                self._open_error = str(e)
            self.link = None
            return
        self._open_error = None
        self._t_hb = None
        self.log(f'supervisor: link open on {self.link.path}')

    def _lost(self, why):
        self.log(f'supervisor: {why}')
        if self.link is not None:
            self.link.close()
        self.link = None
        for mid in list(self.pending):
            self._reply_pending(mid, {'t': 'err', 'msg': f'supervisor link lost: {why}'})

    def _send(self, obj):
        try:
            self.link.send(obj)
            return True
        except (SupervisorError, OSError) as e:
            self._lost(str(e))
            return False

    def pause(self, why):
        self.log(f'supervisor: {why}; letting go of the port until `atlas supervisor resume`')
        if self.link is not None:
            self.link.close()
            self.link = None
        self.paused = True

    def resume(self):
        self.paused = False
        self._t_open = None

    def _from_pico(self):
        try:
            msgs = self.link.read_available()
        except SupervisorError as e:
            self._lost(str(e))
            return
        for m in msgs:
            self._on_message(m)
        if self.link is not None and in_repl(self.link.other):
            self.pause('the supervisor is in its MicroPython REPL')

    def _on_message(self, m):
        t = m.get('t')
        if t == 'status':
            self.last_status = m
            self.t_status = self.clock()
            live = dict(m)
            live.pop('id', None)
            live['time'] = time.time()
            try:
                _write_json(self.live_path, live)
            except OSError as e:
                self.log(f'supervisor: cannot write {self.live_path}: {e}')
            self._sync_lidar(m.get('lidar'))
            if self.on_status is not None:
                self.on_status(m)
        elif t == 'evt':
            self.log('supervisor: ' + describe_event(m))
        mid = m.get('id')
        if mid in self.pending:
            self._reply_pending(mid, m)
            if m.get('t') == 'ack' and m.get('cmd') == 'repl':
                self.pause('the supervisor left for its REPL on request')

    def _sync_lidar(self, on):
        if not isinstance(on, bool):
            return
        self.lidar_state = on
        if self.lines is None or self.clock() < self._lidar_hold:
            return
        if bool(self.lines.values.get('LIDAR_REQ')) != on:
            try:
                self.lines.set('LIDAR_REQ', on)     # an edge the same way as the state: no change
            except OSError:
                pass

    # ---- socket clients
    def _accept(self):
        try:
            sock, _ = self.server.accept()
        except OSError:
            return
        sock.setblocking(False)
        self.clients[sock] = b''

    def _close_client(self, sock):
        self.clients.pop(sock, None)
        try:
            sock.close()
        except OSError:
            pass

    def _answer(self, sock, msg):
        try:
            sock.setblocking(True)
            sock.settimeout(1.0)
            sock.sendall(encode(msg))
        except OSError:
            pass
        self._close_client(sock)

    def _from_client(self, sock):
        try:
            data = sock.recv(65536)
        except OSError:
            data = b''
        if not data:
            self._close_client(sock)
            return
        buf = self.clients[sock] + data
        if b'\n' not in buf:
            self.clients[sock] = buf[-65536:]
            return
        line = buf.split(b'\n')[0].decode('utf-8', 'replace')
        self._client_request(sock, parse(line))

    def _client_request(self, sock, msg):
        if msg is None or 'cmd' not in msg:
            return self._answer(sock, {'t': 'err', 'msg': 'send one JSON object with "cmd"'})
        cmd = msg['cmd']
        cid = msg.get('id')
        if cmd == 'daemon':
            return self._answer(sock, self.info(cid))
        if cmd == 'resume':
            self.resume()
            return self._answer(sock, {'t': 'ack', 'cmd': 'resume', 'id': cid})
        if cmd in ('hb', 'bye'):
            return self._answer(sock, {'t': 'err', 'cmd': cmd, 'id': cid,
                                       'msg': 'heartbeats belong to atlas-battery.service'})
        if cmd == 'lidar' and isinstance(msg.get('on'), bool) and self.lines is not None:
            try:
                from .gpio import request_lidar
                request_lidar(self.lines, msg['on'], current=self.lidar_state)
                self._lidar_hold = self.clock() + self.LIDAR_SYNC_HOLD
            except OSError:
                pass
            if self.link is None:
                return self._answer(sock, {'t': 'ack', 'cmd': 'lidar', 'id': cid, 'on': msg['on'],
                                           'via': 'LIDAR_REQ only (no USB link)'})
        if self.link is None:
            why = 'paused: the supervisor is in its REPL' if self.paused else 'no link to the supervisor'
            return self._answer(sock, {'t': 'err', 'cmd': cmd, 'id': cid, 'msg': why})
        self._next_id += 1
        mid = self._next_id
        fwd = dict(msg)
        fwd['id'] = mid
        self.pending[mid] = (sock, cid, self.clock() + self.REQUEST_TIMEOUT)
        self.clients.pop(sock, None)                # no more reads from this client
        self._send(fwd)

    def _reply_pending(self, mid, msg):
        sock, cid, _ = self.pending.pop(mid)
        reply = dict(msg)
        if cid is None:
            reply.pop('id', None)
        else:
            reply['id'] = cid
        self._answer(sock, reply)

    def _expire(self):
        now = self.clock()
        for mid in [m for m, (_, _, deadline) in self.pending.items() if now > deadline]:
            self._reply_pending(mid, {'t': 'err', 'msg': 'the supervisor did not answer'})

    def info(self, cid=None):
        age = None if self.t_status is None else round(self.clock() - self.t_status, 1)
        return {'t': 'ack', 'cmd': 'daemon', 'id': cid, 'link': self.link.path if self.link else None,
                'paused': self.paused, 'status_age': age, 'boot': self.boot,
                'gpio': dict(self.lines.values) if self.lines is not None else None}


# ---------------------------------------------------------------- the shutdown hook
def send_halt(verb, path=None, wait=0.5):
    """Called from /usr/lib/systemd/system-shutdown/atlas-halt at the very end of shutdown.
    Returns the supervisor's ack, or None if none came within `wait` seconds (it was sent anyway)."""
    link = Link(path)
    try:
        link.send({'cmd': 'halt', 'verb': verb})
        end = time.monotonic() + wait
        while time.monotonic() < end:
            try:
                msgs = link.wait(end - time.monotonic())
            except SupervisorError:
                return None
            for msg in msgs:
                if msg.get('t') == 'ack' and msg.get('cmd') == 'halt':
                    return msg
        return None
    finally:
        link.close()
