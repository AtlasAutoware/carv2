"""`atlas`: one command for the car's hardware (rev B: dev-kit carrier + ATLAS-PWR-1 power board).

  atlas status                         everything at a glance
  atlas battery [--json]               pack voltage, current, state of charge, cells (BMS via the Pico)
  atlas lidar [on|off]                 lidar power (the supervisor's switch)
  atlas supervisor [status] [--json]   the Pico: state, faults, Jetson link, BMS
  atlas supervisor shutdown            switch the car off cleanly (same as a short button press)
  atlas supervisor fan 0-100|auto      fan speed
  atlas supervisor bms-fets on|charge-off|discharge-off|off [--yes]
  atlas supervisor hb-timeout SECONDS  0 = never switch off on a missing heartbeat (until the Pico restarts)
  atlas supervisor log                 the Pico's last events
  atlas supervisor send '{"cmd": ...}' any protocol message (firmware/supervisor/README.md)
  atlas supervisor repl --yes          stop the supervisor firmware (motor bus off) and free its USB port
  atlas supervisor resume              take the port back after a REPL session
  atlas vesc [--probe]                 the FSESC's UART and (with --probe) its firmware version
  atlas hw-init / battery-daemon / halt-hook VERB   used by the systemd units and the shutdown hook

Rev A commands (pd, usb-role, stm32, id) went with the rev A boards; their drivers are kept in
atlas_hw.reva.
"""
import argparse
import json
import os
import sys
import time

from . import board
from .supervisor import SupervisorError


def _env_flag(name, default='0'):
    return os.environ.get(name, default).strip().lower() in ('1', 'yes', 'true', 'on')


def _client(args):
    from . import supervisor
    return supervisor.connect(tty=args.tty)


def _request(args, obj, timeout=None):
    client = _client(args)
    try:
        reply = client.request(obj, timeout) if timeout else client.request(obj)
    finally:
        client.close()
    if reply.get('t') == 'err':
        sys.exit(f"atlas: supervisor: {reply.get('msg', 'error')}")
    return reply


def _status(args):
    """The latest status: the daemon's file if fresh, else a request."""
    from . import supervisor
    live = supervisor.read_live()
    if live is not None:
        return live
    return _request(args, {'cmd': 'status'})


def _fmt(v, spec, unit=''):
    return '?' if v is None else f'{v:{spec}}{unit}'


# ------------------------------------------------------------------ battery, lidar, status
def cmd_battery(args):
    from . import battery
    r = battery.read_live()
    if r is None:
        st = _status(args)
        r = battery.PackSource().reading(st) or {}
        r['soc'] = None
    if args.json:
        print(json.dumps(r, indent=1))
        return
    cells = r.get('cells')
    print(f"pack     {_fmt(r.get('voltage'), '.2f', ' V')} ({r.get('source', '?')})"
          + (f", cells {' '.join(f'{c:.3f}' for c in cells)} V" if cells else ''))
    if r.get('current_known', True) and r.get('current') is not None:
        print(f"current  {r['current']:+.2f} A (positive = discharging)")
    else:
        print('current  unknown (the BMS is not answering; voltage from the Pico\'s divider)')
    if r.get('soc') is not None:
        print(f"charge   {r['soc'] * 100:.0f} % (estimate, start-up value from {r['soc_source']})"
              + (f"; BMS says {r['bms_soc']} %" if r.get('bms_soc') is not None else ''))
    else:
        print('charge   unknown (atlas-battery.service is not running)')
    if r.get('temps'):
        print(f"temps    {', '.join(f'{t:.1f}' for t in r['temps'])} C")


def cmd_battery_daemon(args):
    from . import battery
    limit = args.shutdown_cell_v
    if limit is None and os.environ.get('ATLAS_SHUTDOWN_CELL_V'):
        limit = float(os.environ['ATLAS_SHUTDOWN_CELL_V'])
    battery.run_daemon(shutdown_cell_v=limit or None, tty=args.tty)


def cmd_lidar(args):
    if args.state:
        reply = _request(args, {'cmd': 'lidar', 'on': args.state == 'on'})
        on = reply.get('on')
        via = reply.get('via')
        print('lidar power', 'on' if on else 'off', f'({via})' if via else '')
        return
    st = _status(args)
    print('lidar power', 'on' if st.get('lidar') else 'off')


def cmd_hw_init(args):
    """Boot: wait for atlas-battery.service (heartbeat, JETSON_UP), then lidar per the config."""
    from . import supervisor
    want = args.lidar or ('on' if _env_flag('ATLAS_LIDAR_AT_BOOT', '1') else 'off')
    deadline = time.monotonic() + args.wait
    client = None
    while time.monotonic() < deadline:
        try:
            client = supervisor.DaemonClient()
            info = client.request({'cmd': 'daemon'}, timeout=2.0)
            if info.get('link'):
                break
        except SupervisorError:
            pass
        client = None
        time.sleep(1.0)
    if client is None:
        print('atlas-battery.service is not up (or has no link to the supervisor); trying the port directly')
    try:
        if want != 'keep':
            r = _request(args, {'cmd': 'lidar', 'on': want == 'on'})
            print(f"lidar {'on' if r.get('on') else 'off'} (ATLAS_LIDAR_AT_BOOT)")
        st = _request(args, {'cmd': 'status'})
    except SupervisorError as e:
        sys.exit(f'atlas hw-init: {e}')
    jet = st.get('jet', {})
    print(f"supervisor {st.get('state')} ({st.get('why')}), E-stop {'closed' if st.get('estop') else 'OPEN'}, "
          f"JETSON_UP seen {'yes' if jet.get('up') else 'not yet'}, heartbeat {jet.get('hb')} s ago")


def _print_status(st, daemon=None, gpio_in=None):
    bms = st.get('bms') or {}
    jet = st.get('jet') or {}
    rows = []
    state = f"{st.get('state')} ({st.get('why')})"
    if st.get('last_fail'):
        state += f", last precharge failure: {st['last_fail']}"
    rows.append(('supervisor', f"{state}, firmware {st.get('fw')}, up {st.get('ms', 0) // 1000} s"))
    if bms.get('v') is not None:
        cells = ' '.join(f'{c:.3f}' for c in bms.get('cells', []))
        rows.append(('battery', f"{bms['v']:.2f} V, {bms.get('i', 0):+.2f} A, BMS {bms.get('soc')} %"
                     + (f', cells {cells} V' if cells else '')))
        prot = ', '.join(bms.get('prot_names', [])) or 'none'
        rows.append(('BMS', f"{'ok' if bms.get('ok') else 'NOT ANSWERING'} ({bms.get('age')} s), FETs charge "
                     f"{'on' if bms.get('fet_chg') else 'OFF'} / discharge {'on' if bms.get('fet_dsg') else 'OFF'}, "
                     f"temps {bms.get('temps')}, protection {prot}"))
    else:
        rows.append(('battery', f"{_fmt(st.get('bat'), '.2f', ' V')} (Pico divider; the BMS is not answering)"))
    rows.append(('motor bus', f"{_fmt(st.get('vm'), '.2f', ' V')}, main switch {'on' if st.get('main') else 'off'}, "
                 f"E-stop {'closed' if st.get('estop') else 'OPEN'} ({st.get('estops', 0)} openings), "
                 f"VESC {'killed' if st.get('kill') else 'run'}"))
    rows.append(('FET heatsink', f"{_fmt(st.get('fet_c'), '.0f', ' C')}, fan {st.get('fan')} %"
                 f"{' (auto)' if st.get('fan_auto') else ''}"))
    rows.append(('lidar power', 'on' if st.get('lidar') else 'off'))
    rows.append(('charger', 'connected' if st.get('chg') else 'not connected'))
    rows.append(('Jetson link', f"heartbeat {jet.get('hb')} s ago, JETSON_UP {'seen' if jet.get('up') else 'not seen'}, "
                 f"3.3 V {'on' if jet.get('v33') else 'off'}, timeout {jet.get('hb_timeout')} s"
                 + (f", reboot grace {jet['grace']} s" if jet.get('grace') else '')))
    if st.get('low'):
        rows.append(('WARNING', 'pack low (under 12.0 V for 30 s)'))
    if daemon is not None:
        rows.append(('daemon', f"port {daemon.get('link') or 'not open'}{' (paused)' if daemon.get('paused') else ''}, "
                     f"lines {daemon.get('gpio')}"))
    if gpio_in:
        rows.append(('J12 inputs', ', '.join(f'{k} {v}' for k, v in gpio_in.items())))
    rows.append(('VESC UART', board.vesc_tty()))
    for k, v in rows:
        print(f'{k:13}{v}')


def cmd_status(args):
    from . import gpio, supervisor
    try:
        st = _status(args)
    except SupervisorError as e:
        sys.exit(f'atlas: {e}')
    daemon = None
    try:
        daemon = supervisor.DaemonClient().request({'cmd': 'daemon'}, timeout=1.0)
    except SupervisorError:
        pass
    if args.json:
        print(json.dumps(st, indent=1))
        return
    _print_status(st, daemon, gpio.read_inputs())


# ------------------------------------------------------------------ supervisor
FET_MODES = {'on': (True, True), 'charge-off': (False, True), 'discharge-off': (True, False), 'off': (False, False)}


def cmd_supervisor(args):
    a = args.action
    if a == 'status':
        st = _request(args, {'cmd': 'status'})
        if args.json:
            print(json.dumps(st, indent=1))
        else:
            _print_status(st)
    elif a == 'shutdown':
        r = _request(args, {'cmd': 'shutdown'})
        print('shutting down: the supervisor pressed the power key' if r.get('started')
              else f"already shutting down ({r.get('state')})")
    elif a == 'fan':
        if not args.value:
            sys.exit('atlas supervisor fan 0-100|auto')
        obj = {'cmd': 'fan', 'auto': True} if args.value == 'auto' else {'cmd': 'fan', 'duty': int(args.value)}
        r = _request(args, obj)
        print(f"fan {r.get('duty')} %{' (auto)' if r.get('auto') else ''}")
    elif a == 'bms-fets':
        if args.value not in FET_MODES:
            sys.exit('atlas supervisor bms-fets on|charge-off|discharge-off|off')
        chg, dsg = FET_MODES[args.value]
        if not dsg and not args.yes:
            sys.exit('refusing: opening the discharge FETs cuts power to the whole car, this Jetson included, '
                     'and the car may not wake again until the BMS is reset. Add --yes if you mean it.')
        r = _request(args, {'cmd': 'bms_fets', 'charge': chg, 'discharge': dsg, 'force': not dsg})
        print(f"BMS FETs: charge {'on' if chg else 'off'}, discharge {'on' if dsg else 'off'} (sent)")
    elif a == 'hb-timeout':
        if args.value is None:
            sys.exit('atlas supervisor hb-timeout SECONDS')
        r = _request(args, {'cmd': 'hb_timeout', 's': float(args.value)})
        print(f"heartbeat timeout {r.get('s')} s{' (never)' if not r.get('s') else ''}")
    elif a == 'log':
        r = _request(args, {'cmd': 'log'})
        from .supervisor import describe_event
        for e in r.get('events', []):
            print(f"{e.get('ms', 0) / 1000:9.1f} s  {describe_event(e)}")
    elif a == 'send':
        try:
            obj = json.loads(args.value or '')
        except ValueError:
            sys.exit('atlas supervisor send \'{"cmd": "status"}\'')
        client = _client(args)
        try:
            reply = client.request(obj)
        finally:
            client.close()
        print(json.dumps(reply, indent=1))
        if reply.get('t') == 'err':
            sys.exit(1)
    elif a == 'repl':
        if not args.yes:
            sys.exit('this stops the supervisor firmware: the motor bus goes off, the Jetson stays on, and '
                     'halt detection stops until it is restarted (Ctrl-D in its REPL). Add --yes.')
        _request(args, {'cmd': 'repl'})
        print('the supervisor is in its REPL. If atlas-battery.service is running it has let go of the port.\n'
              'Use Thonny, mpremote or `screen /dev/atlas_supervisor 115200`; press Ctrl-D there to restart the '
              'firmware, then `atlas supervisor resume`.')
    elif a == 'resume':
        from .supervisor import DaemonClient
        try:
            DaemonClient().request({'cmd': 'resume'})
            print('atlas-battery.service takes the port back')
        except SupervisorError as e:
            sys.exit(f'atlas: {e}')


# ------------------------------------------------------------------ VESC, shutdown hook
def cmd_vesc(args):
    path = board.vesc_tty()
    real = os.path.realpath(path)
    exists = os.path.exists(path)
    print(f"VESC UART   {path}" + (f' -> {real}' if real != path else '') + ('' if exists else ' (missing)'))
    if not args.probe:
        print('  `atlas vesc --probe` asks the FSESC for its firmware (stop vesc_driver first)')
        return
    from . import vesc
    try:
        fw = vesc.probe(path)
    except (OSError, TimeoutError, ValueError) as e:
        sys.exit(f'atlas vesc: {e}')
    print(f"firmware    {fw['major']}.{fw['minor']:02d}, hardware {fw['hw']}, UUID {fw['uuid']}")


def cmd_halt_hook(args):
    """Run by /usr/lib/systemd/system-shutdown/atlas-halt: tell the supervisor, drop JETSON_UP."""
    import signal
    old = signal.signal(signal.SIGALRM, lambda *a: sys.exit('atlas halt-hook: timed out'))
    signal.alarm(4)
    try:
        _halt_hook(args)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def _halt_hook(args):
    from . import gpio, supervisor
    sent = 'not sent'
    try:
        ack = supervisor.send_halt(args.verb, args.tty)
        sent = 'acknowledged' if ack else 'sent'
    except (SupervisorError, OSError) as e:
        print(f'atlas halt-hook: {e}', file=sys.stderr)
    up = 'left as is'
    try:
        with gpio.Lines(outputs={'JETSON_UP': 0}, consumer='atlas-halt'):
            time.sleep(0.05)
        up = 'low'
    except gpio.GpioUnavailable as e:
        print(f'atlas halt-hook: {e}', file=sys.stderr)
    print(f'atlas halt-hook: {args.verb}: HALT {sent}, JETSON_UP {up}')


def main(argv=None):
    p = argparse.ArgumentParser(prog='atlas', description='Atlas car 2 (rev B) hardware tool')
    p.add_argument('--tty', help='supervisor port when not going through the daemon (default /dev/atlas_supervisor)')
    sub = p.add_subparsers(dest='cmd', required=True)

    s = sub.add_parser('status')
    s.add_argument('--json', action='store_true')
    s.set_defaults(fn=cmd_status)
    s = sub.add_parser('battery')
    s.add_argument('--json', action='store_true')
    s.set_defaults(fn=cmd_battery)
    s = sub.add_parser('battery-daemon', help='atlas-battery.service: supervisor link, heartbeat, battery estimate')
    s.add_argument('--shutdown-cell-v', type=float, help='power off below this corrected cell voltage (30 s)')
    s.set_defaults(fn=cmd_battery_daemon)
    s = sub.add_parser('lidar')
    s.add_argument('state', nargs='?', choices=('on', 'off'))
    s.set_defaults(fn=cmd_lidar)
    s = sub.add_parser('hw-init')
    s.add_argument('--lidar', choices=('on', 'off', 'keep'))
    s.add_argument('--wait', type=float, default=30.0, help='seconds to wait for atlas-battery.service')
    s.set_defaults(fn=cmd_hw_init)
    s = sub.add_parser('supervisor', help='the power board supervisor (Pico)')
    s.add_argument('action', nargs='?', default='status',
                   choices=('status', 'shutdown', 'fan', 'bms-fets', 'hb-timeout', 'log', 'send', 'repl', 'resume'))
    s.add_argument('value', nargs='?')
    s.add_argument('--json', action='store_true')
    s.add_argument('--yes', action='store_true')
    s.set_defaults(fn=cmd_supervisor)
    s = sub.add_parser('vesc', help='the FSESC on UART1')
    s.add_argument('--probe', action='store_true')
    s.set_defaults(fn=cmd_vesc)
    s = sub.add_parser('halt-hook', help=argparse.SUPPRESS)
    s.add_argument('verb', nargs='?', default='poweroff')
    s.set_defaults(fn=cmd_halt_hook)

    args = p.parse_args(argv)
    try:
        args.fn(args)
    except SupervisorError as e:
        sys.exit(f'atlas: {e}')
    except OSError as e:
        sys.exit(f'atlas: {e}')


if __name__ == '__main__':
    main()
