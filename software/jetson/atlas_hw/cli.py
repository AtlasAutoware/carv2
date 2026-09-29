"""`atlas`: one command for the drive board and brain board hardware.

  atlas status                     everything at a glance
  atlas battery [--json]           pack voltage, current, state of charge
  atlas lidar [on|off]             lidar power (brain board expander P2)
  atlas pd status                  USB-C PD controller mode and connection
  atlas pd load LOW.bin            run a configuration from RAM (controller in PTCH mode)
  atlas pd flash FULL.bin [--lowregion LOW.bin]   first programming of the PD EEPROM
  atlas pd update LOW.bin          later updates (TI's A/B region update)
  atlas pd restart                 restart the PD controller from its EEPROM
  atlas id [--write --serial 001 --rev A]         drive board ID EEPROM
  atlas usb-role [device|host|none]               role of the Jetson's USB0
  atlas stm32 bootloader|run|reset needs the POWER_EN fix (docs/FLASHING.md)
  atlas hw-init / pd ensure / battery-daemon      used by the systemd services

With --ftdi, the stack I2C commands (battery, pd, id) go through an FT232H wired to the drive
board's stack socket instead of /dev/i2c-N, for bench work with the brain board off.
"""
import argparse
import json
import os
import sys
import time

from . import board
from .i2c import FtdiI2C, I2CError, LinuxI2C


def _env_flag(name):
    return os.environ.get(name, '0').strip().lower() in ('1', 'yes', 'true', 'on')


def _stack(args):
    if args.ftdi:
        return FtdiI2C(args.ftdi_url)
    return LinuxI2C(args.stack_bus if args.stack_bus is not None else board.stack_i2c_bus())


def _sys(args):
    if args.ftdi:
        sys.exit('the brain board expander is not on the stack I2C; --ftdi cannot reach it')
    return LinuxI2C(args.sys_bus if args.sys_bus is not None else board.sys_i2c_bus())


def _expander(args):
    from .expander import Expander
    return Expander(_sys(args))


def _read_file(path):
    with open(path, 'rb') as f:
        return f.read()


def _progress(label):
    state = {'last': -1}

    def show(done, total):
        pct = done * 100 // total
        if pct != state['last'] and (pct % 10 == 0 or done == total):
            print(f'  {label}: {pct} %', flush=True)
            state['last'] = pct
    return show


# ------------------------------------------------------------------ battery, lidar, status
def cmd_battery(args):
    from . import battery
    from .ina228 import INA228
    live = battery.read_live()
    if live is None:
        ina = INA228(_stack(args))
        ina.configure(reset_accumulators=False)
        r = ina.read_all()
        r['cell_v'] = r['voltage'] / board.PACK_CELLS_SERIES
        r['soc'] = None
    else:
        r = live
    if args.json:
        print(json.dumps(r, indent=1))
        return
    print(f"pack     {r['voltage']:.2f} V ({r['cell_v']:.3f} V per cell)")
    print(f"current  {r['current']:+.2f} A (positive = discharging)")
    print(f"power    {r['power']:.1f} W")
    if r.get('soc') is not None:
        print(f"charge   {r['soc'] * 100:.0f} % (estimate, start-up value from {r['soc_source']})")
    else:
        print('charge   unknown (atlas-battery.service is not running)')


def cmd_battery_daemon(args):
    from . import battery
    from .ina228 import INA228
    exp = None
    try:
        exp = _expander(args)
    except (SystemExit, OSError):
        pass                    # bench set-up without the brain board: no charging input

    def charging():
        try:
            return exp.charging() if exp else False
        except OSError:
            return False
    limit = args.shutdown_cell_v
    if limit is None and os.environ.get('ATLAS_SHUTDOWN_CELL_V'):
        limit = float(os.environ['ATLAS_SHUTDOWN_CELL_V'])
    battery.run_daemon(INA228(_stack(args)), shutdown_cell_v=limit or None, is_charging=charging)


def cmd_lidar(args):
    exp = _expander(args)
    if args.state:
        exp.setup()
        exp.lidar(args.state == 'on')
    print('lidar power', 'on' if exp.lidar() else 'off')


def cmd_hw_init(args):
    """Boot-time set-up of the brain board expander: outputs defined, lidar as configured."""
    exp = _expander(args)
    exp.setup()
    want = args.lidar or ('on' if _env_flag('ATLAS_LIDAR_AT_BOOT') else 'keep')
    if want != 'keep':
        exp.lidar(want == 'on')
    print(f"expander ready; lidar {'on' if exp.lidar() else 'off'}, E-stop "
          f"{'closed' if exp.estop_ok() else 'OPEN'}, {'charging' if exp.charging() else 'not charging'}")


def cmd_status(args):
    from . import battery, usbrole
    from .ina228 import INA228
    from .tps25751 import TPS25751
    from .ideeprom import IDEEPROM
    stack = _stack(args)
    rows = []
    try:
        rec = IDEEPROM(stack).record()
        rows.append(('drive board', f"{rec.get('board', '?')} rev {rec.get('rev', '?')} serial {rec.get('serial', '?')}"
                     if rec else 'ID EEPROM blank'))
    except (OSError, ValueError) as e:
        rows.append(('drive board', f'ID EEPROM: {e}'))
    live = battery.read_live()
    try:
        r = live or INA228(stack).read_all()
        soc = f", {r['soc'] * 100:.0f} %" if live else ''
        rows.append(('battery', f"{r['voltage']:.2f} V, {r['current']:+.2f} A{soc}"))
    except OSError as e:
        rows.append(('battery', f'INA228: {e}'))
    try:
        st = TPS25751(stack).status()
        text = st['mode'].strip()
        if 'plug_present' in st:
            text += f", {'plugged in' if st['plug_present'] else 'no USB-C cable'}, VBUS {st['vbus']}"
        rows.append(('USB-C PD', text))
    except OSError as e:
        rows.append(('USB-C PD', f'TPS25751: {e}'))
    if not args.ftdi:
        try:
            exp = _expander(args)
            rows.append(('E-stop', 'closed' if exp.estop_ok() else 'OPEN'))
            rows.append(('charger', 'charging' if exp.charging() else 'not charging'))
            rows.append(('lidar power', 'on' if exp.lidar() else 'off'))
        except OSError as e:
            rows.append(('expander', str(e)))
        rows.append(('USB0 role', usbrole.get_role() or 'no role switch found'))
        rows.append(('VESC UART', board.vesc_tty()))
    for k, v in rows:
        print(f'{k:12} {v}')


# ------------------------------------------------------------------ PD controller
def cmd_pd(args):
    from . import tps25751 as T
    tps = T.TPS25751(_stack(args), log=print)
    if args.pd_cmd == 'status':
        st = tps.status()
        if args.json:
            print(json.dumps(st, indent=1))
            return
        print(f"mode          {st['mode']!r}: {T.MODE_NAMES.get(st['mode'], '?')}")
        print(f"boot status   0x{st['boot_status']:010x} (EEPROM {'found' if st['eeprom_present'] else 'not found'}"
              f"{', dead-battery start' if st['dead_battery'] else ''})")
        if 'status' in st:
            print(f"USB-C         {'cable in' if st['plug_present'] else 'no cable'}, VBUS {st['vbus']}, "
                  f"{'sink' if st['sink'] else 'source'}, current {st['typec_current']}")
            print(f"powered from  {st['power_source']}")
    elif args.pd_cmd == 'load':
        tps.load_patch(_read_file(args.file))
    elif args.pd_cmd == 'ensure':
        mode = tps.mode()
        path = args.lowregion or os.environ.get('ATLAS_PD_LOWREGION', '')
        if mode == 'PTCH' and path and os.path.exists(path):
            print('PD controller waits for a patch (EEPROM blank or bad); loading', path)
            tps.load_patch(_read_file(path))
        elif mode == 'PTCH':
            print('PD controller waits for a patch and no Low Region binary is configured: USB-C charging is off')
            sys.exit(1)
        else:
            print(f'PD controller mode {mode!r}')
    elif args.pd_cmd == 'flash':
        image = _read_file(args.image)
        T.check_full_image(image)
        low = _read_file(args.lowregion) if args.lowregion else None
        if low is not None:
            match = T.lowregion_matches(image, low)
            print('Low Region binary matches the Full Flash image:', 'yes' if match else 'NO')
            if not match and not args.force:
                sys.exit('refusing: the two files look like different TI tool runs (--force to go on)')
        mode = tps.mode()
        if mode == 'PTCH':
            if low is None:
                sys.exit('the controller waits in PTCH mode; give --lowregion so it can run the configuration first')
            tps.load_patch(low)
        elif mode != 'APP ':
            sys.exit(f'controller in mode {mode!r}')
        print(f'writing {len(image)} bytes to the PD EEPROM through the controller')
        tps.eeprom_write_full(image, verify=not args.no_verify, progress=_progress('EEPROM'))
        _restart_and_check(tps)
    elif args.pd_cmd == 'update':
        low = _read_file(args.file)
        tps.eeprom_update(low, verify=not args.no_verify, progress=_progress('EEPROM'))
        _restart_and_check(tps)
    elif args.pd_cmd == 'restart':
        print('mode after restart:', repr(tps.restart()))


def _restart_and_check(tps):
    print('restarting the PD controller from its EEPROM')
    mode = tps.restart()
    st = tps.status()
    if mode == 'APP ' and st['eeprom_present']:
        print('done: the controller booted from the EEPROM')
    else:
        sys.exit(f"the controller came back in mode {mode!r} (EEPROM {'found' if st['eeprom_present'] else 'not found'}): "
                 'it did not take the EEPROM image; `atlas pd load` runs the configuration from RAM meanwhile')


# ------------------------------------------------------------------ ID EEPROM, USB role, STM32
def cmd_id(args):
    from .ideeprom import IDEEPROM
    eep = IDEEPROM(_stack(args))
    if args.write:
        rec = {'board': args.board, 'rev': args.rev, 'serial': args.serial,
               'built': args.built or time.strftime('%Y-%m-%d')}
        if args.note:
            rec['note'] = args.note
        eep.write_record(rec)
    rec = eep.record()
    print(json.dumps(rec) if rec else 'ID EEPROM is blank')


def cmd_usb_role(args):
    from . import usbrole
    if args.role:
        print('wrote', args.role, 'to', usbrole.set_role(args.role))
    print('USB0 role:', usbrole.get_role())


def cmd_stm32(args):
    if not (args.power_en_fixed or _env_flag('ATLAS_POWER_EN_FIXED')):
        sys.exit('refusing: ATLAS_POWER_EN_FIXED is not set. On a drive board without the POWER_EN fix '
                 '(R609 to GND, built from files older than Sept 29), resetting the STM32 switches off the '
                 'brain board and this Jetson with it. With the fix (docs/FLASHING.md) set '
                 'ATLAS_POWER_EN_FIXED=1 or pass --power-en-fixed.')
    exp = _expander(args)
    exp.setup()
    if args.action == 'bootloader':
        exp.set_line(board.EXP_MCU_BOOT0, 1)
    elif args.action == 'run':
        exp.set_line(board.EXP_MCU_BOOT0, 0)
    exp.set_line(board.EXP_MCU_RST_REQ, 1)
    time.sleep(0.05)
    exp.set_line(board.EXP_MCU_RST_REQ, 0)
    time.sleep(0.1)
    if args.action == 'bootloader':
        print(f'STM32 is in its ROM bootloader (USART3 on {board.vesc_tty()}, or USB DFU through hub port 2).')
        print(f'  stm32flash -b 115200 -w atlas_drv1_full.hex -v {board.vesc_tty()}')
        print('then: atlas stm32 run')
    else:
        print('STM32 restarted' + (' from flash' if args.action == 'run' else ''))


def main(argv=None):
    p = argparse.ArgumentParser(prog='atlas', description='Atlas car v2 hardware tool')
    p.add_argument('--ftdi', action='store_true',
                   help='use an FT232H on the stack socket for the stack I2C (bench, brain board off)')
    p.add_argument('--ftdi-url', default='ftdi://ftdi:232h/1', help='pyftdi URL of the FT232H')
    p.add_argument('--stack-bus', type=int, help='Linux I2C bus number of the stack I2C (default: found by address)')
    p.add_argument('--sys-bus', type=int, help='Linux I2C bus number of the brain board expander')
    sub = p.add_subparsers(dest='cmd', required=True)

    sub.add_parser('status').set_defaults(fn=cmd_status)
    s = sub.add_parser('battery')
    s.add_argument('--json', action='store_true')
    s.set_defaults(fn=cmd_battery)
    s = sub.add_parser('battery-daemon')
    s.add_argument('--shutdown-cell-v', type=float, help='power off below this corrected cell voltage (30 s)')
    s.set_defaults(fn=cmd_battery_daemon)
    s = sub.add_parser('lidar')
    s.add_argument('state', nargs='?', choices=('on', 'off'))
    s.set_defaults(fn=cmd_lidar)
    s = sub.add_parser('hw-init')
    s.add_argument('--lidar', choices=('on', 'off', 'keep'))
    s.set_defaults(fn=cmd_hw_init)

    s = sub.add_parser('pd', help='USB-C PD controller (TPS25751D)')
    pd = s.add_subparsers(dest='pd_cmd', required=True)
    t = pd.add_parser('status')
    t.add_argument('--json', action='store_true')
    t = pd.add_parser('load')
    t.add_argument('file', help='Low Region binary from TI\'s Application Customization Tool')
    t = pd.add_parser('ensure')
    t.add_argument('--lowregion', help='default: $ATLAS_PD_LOWREGION')
    t = pd.add_parser('flash')
    t.add_argument('image', help='Full Flash binary from TI\'s Application Customization Tool')
    t.add_argument('--lowregion', help='Low Region binary from the same tool run')
    t.add_argument('--no-verify', action='store_true')
    t.add_argument('--force', action='store_true')
    t = pd.add_parser('update')
    t.add_argument('file', help='Low Region binary')
    t.add_argument('--no-verify', action='store_true')
    pd.add_parser('restart')
    s.set_defaults(fn=cmd_pd)

    s = sub.add_parser('id', help='drive board ID EEPROM')
    s.add_argument('--write', action='store_true')
    s.add_argument('--board', default='ATLAS-DRV-1')
    s.add_argument('--rev', default='A')
    s.add_argument('--serial')
    s.add_argument('--built', help='YYYY-MM-DD (default today)')
    s.add_argument('--note')
    s.set_defaults(fn=cmd_id)

    s = sub.add_parser('usb-role')
    s.add_argument('role', nargs='?', choices=('device', 'host', 'none'))
    s.set_defaults(fn=cmd_usb_role)

    s = sub.add_parser('stm32', help='STM32 reset and ROM bootloader through the brain board expander')
    s.add_argument('action', choices=('bootloader', 'run', 'reset'))
    s.add_argument('--power-en-fixed', action='store_true')
    s.set_defaults(fn=cmd_stm32)

    args = p.parse_args(argv)
    if args.cmd == 'id' and args.write and not args.serial:
        p.error('id --write needs --serial')
    try:
        args.fn(args)
    except (I2CError, OSError) as e:
        sys.exit(f'atlas: {e}')


if __name__ == '__main__':
    main()
