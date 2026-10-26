"""The USB CDC line protocol between the supervisor and the Jetson.

One message per line, newline-terminated, both ways. Messages are JSON objects.

  Jetson -> Pico: {"cmd": "<name>", ...arguments..., "id": <optional number echoed in the reply>}
  Pico -> Jetson: {"t": "status" | "ack" | "err" | "evt", ...}

A person can also type plain words in a terminal (`screen /dev/atlas_supervisor 115200`):
"status", "lidar off", "fan 40", "fan auto", "shutdown", "reboot", "reboot hard", "help",
"bms_fets on|off|charge_off|discharge_off [force]", "hb_timeout 0", "jetson_power_cycle [s]",
"log", "repl". The Pico does
not echo what you type. A line ends at CR or LF, so screen's Enter key works.

Lines that are JSON objects without "cmd" (for example our own status lines echoed back by a
terminal in cooked mode) are ignored, so an echoing tty cannot start a reply storm.

A Ctrl-C byte (0x03) is turned into {"cmd": "repl", "via": "ctrl-c"}: that is how Thonny and
mpremote get to the REPL (main.py makes the outputs safe before it leaves).

The full command list and the status fields are in README.md.
"""
import json

MAX_LINE = 300

WORDS = ('status', 'help', 'version', 'hb', 'bye', 'shutdown', 'repl', 'log')


def parse_words(words):
    c = words[0].lower()
    a = [w.lower() for w in words[1:]]
    if c in WORDS:
        return {'cmd': c}
    if c == 'lidar' and a and a[0] in ('on', 'off'):
        return {'cmd': 'lidar', 'on': a[0] == 'on'}
    if c == 'reboot':
        return {'cmd': 'reboot', 'hard': 'hard' in a}
    if c == 'halt':
        return {'cmd': 'halt', 'verb': a[0] if a else 'poweroff'}
    if c == 'fan' and a:
        if a[0] == 'auto':
            return {'cmd': 'fan', 'auto': True}
        try:
            return {'cmd': 'fan', 'duty': int(a[0])}
        except ValueError:
            pass
    if c == 'bms_fets' and a:
        modes = {'on': (True, True), 'off': (False, False),
                 'charge_off': (False, True), 'discharge_off': (True, False)}
        if a[0] in modes:
            chg, dsg = modes[a[0]]
            return {'cmd': 'bms_fets', 'charge': chg, 'discharge': dsg, 'force': 'force' in a}
    if c == 'jetson_power_cycle':
        if not a:
            return {'cmd': c}
        try:
            return {'cmd': c, 'off_s': int(a[0])}
        except ValueError:
            pass
    if c == 'hb_timeout' and a:
        try:
            return {'cmd': 'hb_timeout', 's': int(a[0])}
        except ValueError:
            pass
    return {'cmd': '?', 'text': ' '.join(words)}


def parse_line(text):
    """One received line -> a command dict, or None for an empty or ignored line."""
    text = text.strip()
    if not text:
        return None
    if text[0] == '{':
        try:
            obj = json.loads(text)
        except ValueError:
            return {'cmd': '?', 'text': text[:40], 'error': 'bad JSON'}
        if not isinstance(obj, dict):
            return {'cmd': '?', 'error': 'not a JSON object'}
        if 'cmd' not in obj:
            return None
        return obj
    return parse_words(text.split())


class LineLink:
    def __init__(self, io):
        self.io = io
        self._buf = bytearray()
        self._overflow = False
        self.rx_lines = 0
        self.tx_lines = 0
        self.dropped = 0

    def poll(self):
        """Commands received since the last call, in order."""
        data = self.io.read_available()
        msgs = []
        for b in data:
            if b == 3:                      # Ctrl-C: someone wants the REPL
                self._buf = bytearray()
                self._overflow = False
                msgs.append({'cmd': 'repl', 'via': 'ctrl-c'})
                break
            if b == 10 or b == 13:
                if self._overflow:
                    self.dropped += 1
                elif self._buf:
                    msg = self._decode(bytes(self._buf))
                    if msg is not None:
                        self.rx_lines += 1
                        msgs.append(msg)
                self._buf = bytearray()
                self._overflow = False
            elif len(self._buf) < MAX_LINE:
                self._buf.append(b)
            else:
                self._overflow = True
        return msgs

    def _decode(self, raw):
        try:
            text = raw.decode()
        except (UnicodeError, ValueError):
            self.dropped += 1
            return None
        return parse_line(text)

    def send(self, obj):
        self.io.write((json.dumps(obj) + '\n').encode())
        self.tx_lines += 1
