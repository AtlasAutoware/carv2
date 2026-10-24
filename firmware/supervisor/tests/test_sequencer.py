"""The state machine on the simulated power board (sim.Rig runs the real main.App)."""
import pytest

import sequencer as Q
from sim import Rig


def rises(rig, name):
    return [t for t, n, v in rig.hw.changes if n == name and v == 1]


def falls(rig, name):
    return [t for t, n, v in rig.hw.changes if n == name and v == 0]


def running(**kw):
    rig = Rig(**kw)
    rig.run(1000)
    assert rig.state() == Q.RUN
    return rig


def up_and_talking(**kw):
    rig = running(**kw)
    rig.jetson_boots()
    rig.run_with_heartbeat(3000)
    assert rig.seq.up and rig.seq.hb_seen
    return rig


# ---------------------------------------------------------------- precharge
def test_precharge_success():
    rig = running()
    hw = rig.hw
    t_pre, t_main = rises(rig, 'PRECHARGE_EN')[0], rises(rig, 'MAIN_EN')[0]
    t_pre_off = falls(rig, 'PRECHARGE_EN')[0]
    assert t_pre < t_main < t_pre_off
    assert t_pre_off - t_main >= Q.Settings.PRECHARGE_OVERLAP_MS
    assert hw.out['MAIN_EN'] == 1 and hw.out['PRECHARGE_EN'] == 0 and hw.out['VESC_KILL'] == 1
    assert rig.seq.precharge_ms <= rig.seq.precharge_timeout_ms()
    assert hw.vm == pytest.approx(16.0)
    assert rig.hw.out['LIDAR_EN'] == 1                  # lidar on by default (rev B spec)


def test_precharge_short_gives_up_after_three_short_tries():
    rig = Rig()
    rig.hw.load_ohm = 0.5                               # a short on the motor bus
    rig.run(8000)
    assert rig.state() == Q.FAULT and rig.seq.why == 'short'
    on, off = rises(rig, 'PRECHARGE_EN'), falls(rig, 'PRECHARGE_EN')
    assert len(on) == 3
    for a, b in zip(on, off):
        assert b - a <= 20                              # stopped at the 10 ms check
    for a, b in zip(on, on[1:]):
        assert b - a >= Q.Settings.PRECHARGE_RETRY_GAP_MS
    assert rises(rig, 'MAIN_EN') == []
    assert [e['why'] for e in rig.events('precharge_failed')] == ['short'] * 3


def test_precharge_partial_short_stops_at_five_tau():
    rig = Rig()
    rig.hw.load_ohm = 10.0                              # bus settles at half the pack (review F3 case)
    rig.run(8000)
    assert rig.state() == Q.FAULT and rig.seq.why == 'slow'
    on, off = rises(rig, 'PRECHARGE_EN'), falls(rig, 'PRECHARGE_EN')
    for a, b in zip(on, off):
        assert b - a <= rig.seq.precharge_timeout_ms() + 10
    assert rises(rig, 'MAIN_EN') == []


def test_precharge_retry_succeeds_once_the_short_is_gone():
    rig = Rig()
    rig.hw.load_ohm = 0.5
    rig.run(200)
    assert rig.events('precharge_failed')
    rig.hw.load_ohm = None
    rig.run(3000)
    assert rig.state() == Q.RUN and rig.seq.attempt == 2


def test_bigger_esc_capacitance_needs_the_setting():
    rig = Rig(vm_cap_uf=8000.0)                         # 8 mF where 2 mF is assumed: looks like a short
    rig.run(8000)
    assert rig.state() == Q.FAULT and rig.seq.why in ('short', 'slow')

    class Big(Q.Settings):
        VM_CAP_UF = 8000.0
    rig = Rig(settings=Big, vm_cap_uf=8000.0)
    rig.run(1500)
    assert rig.state() == Q.RUN


def test_healthy_bus_on_a_low_pack_is_not_a_short():
    # rev A's fixed 4 V at 10 ms would fail this one (12 V pack, 2.5 mF, tau 25 ms: 3.96 V)
    rig = Rig(bat_v=12.0, vm_cap_uf=2500.0)
    rig.run(1500)
    assert rig.state() == Q.RUN and not rig.events('precharge_failed')


def test_main_switch_that_does_not_conduct_is_a_fault():
    rig = Rig()
    rig.hw.main_switch_works = False
    rig.run(1500)
    assert rig.state() == Q.FAULT and rig.seq.why == 'main_switch'
    assert rig.hw.out['MAIN_EN'] == 0 and rig.hw.out['VESC_KILL'] == 0


def test_bad_pack_reading_is_not_precharged():
    rig = Rig(bat_v=8.0)
    rig.run(8000)
    assert rig.state() == Q.FAULT and rig.seq.why == 'bat_sense'
    assert rises(rig, 'PRECHARGE_EN') == []


def test_restart_waits_for_a_press():
    rig = Rig(cold_start=False)
    rig.run(1000)
    assert rig.state() == Q.LOCKOUT and rig.seq.why == 'restart'
    assert rises(rig, 'PRECHARGE_EN') == []
    rig.press()
    rig.run(1000)
    assert rig.state() == Q.RUN


# ---------------------------------------------------------------- E-stop
def test_estop_open_at_power_on_waits_for_loop_and_press():
    rig = Rig()
    rig.hw.set_input('ESTOP_OK', 0)
    rig.run(1000)
    assert rig.state() == Q.LOCKOUT and rig.seq.why == 'estop'
    rig.hw.set_input('ESTOP_OK', 1)
    rig.run(2000)
    assert rig.state() == Q.LOCKOUT                     # closing the loop alone does nothing
    assert rises(rig, 'PRECHARGE_EN') == []
    rig.press()
    rig.run(1000)
    assert rig.state() == Q.RUN


def test_estop_cut_while_running_and_rearm():
    rig = up_and_talking()
    hw = rig.hw
    t_cut = rig.clock.now()
    hw.set_input('ESTOP_OK', 0)
    # the interrupt dropped the enables at once, before any tick
    assert hw.out['MAIN_EN'] == 0 and hw.out['VESC_KILL'] == 0 and hw.out['PRECHARGE_EN'] == 0
    assert falls(rig, 'MAIN_EN')[-1] == t_cut
    rig.run(100)
    assert rig.state() == Q.LOCKOUT and rig.seq.why == 'estop'
    assert rig.events('estop')[-1]['open'] is True
    assert hw.out['ESTOP_OK_TO_JETSON'] == 0
    hw.set_input('ESTOP_OK', 1)
    rig.run_with_heartbeat(3000)
    assert rig.state() == Q.LOCKOUT and hw.out['MAIN_EN'] == 0      # no automatic restart
    assert hw.out['ESTOP_OK_TO_JETSON'] == 1
    n = len(rises(rig, 'PRECHARGE_EN'))
    rig.press()
    rig.run_with_heartbeat(1000)
    assert rig.state() == Q.RUN
    assert len(rises(rig, 'PRECHARGE_EN')) == n + 1                 # re-armed through a precharge
    assert rig.seq.estops == 1


def test_estop_glitch_between_ticks_still_latches():
    rig = running()
    rig.hw.set_input('ESTOP_OK', 0)
    rig.hw.set_input('ESTOP_OK', 1)                     # back before the next tick
    rig.run(500)
    assert rig.state() == Q.LOCKOUT and rig.hw.out['MAIN_EN'] == 0


def test_estop_during_precharge():
    rig = Rig()
    rig.run(130)                                        # INIT 100 ms, then charging
    assert rig.state() == Q.PRECHARGE
    rig.hw.set_input('ESTOP_OK', 0)
    rig.run(1000)
    assert rig.state() == Q.LOCKOUT and rises(rig, 'MAIN_EN') == []


def test_press_with_loop_still_open_is_ignored():
    # review m16: a press in LOCKOUT never shuts the car down; with the loop open it is refused
    rig = up_and_talking()
    rig.hw.set_input('ESTOP_OK', 0)
    rig.run(100)
    n = len(rises(rig, 'PRECHARGE_EN'))
    rig.press()
    assert rig.state() == Q.LOCKOUT
    assert rig.events('rearm_refused')[-1]['why'] == 'E-stop loop open'
    assert rig.hw.pulses_of('JETSON_PWR_KEY') == [] and len(rises(rig, 'PRECHARGE_EN')) == n


# ---------------------------------------------------------------- button and Jetson shutdown
def test_power_on_press_does_not_count():
    rig = Rig()
    rig.hw.set_input('BUTTON_N', 0)                     # still held from switching the car on
    rig.run(1500)
    rig.hw.set_input('BUTTON_N', 1)
    rig.run(500)
    assert rig.state() == Q.RUN


def test_button_press_key_pulse_halt_latch_off():
    rig = up_and_talking()
    rig.press()
    assert rig.state() == Q.SHUTDOWN_REQUESTED
    keys = rig.hw.pulses_of('JETSON_PWR_KEY')
    assert len(keys) == 1 and 150 <= keys[0][2] <= 200
    assert rig.hw.out['VESC_KILL'] == 0 and rig.hw.out['MAIN_EN'] == 0
    # the Jetson's shutdown starts: its daemon says bye, then the systemd hook sends HALT
    rig.usb.send({'cmd': 'bye'})
    rig.run(15000)
    assert rig.state() == Q.SHUTDOWN_REQUESTED
    assert len(rig.hw.pulses_of('JETSON_PWR_KEY')) == 1             # no re-press after bye (F6)
    rig.usb.send({'cmd': 'halt', 'verb': 'poweroff'})
    rig.hw.set_input('JETSON_UP', 0)
    rig.run(100)
    assert rig.state() == Q.HALTING
    assert rig.hw.out['LIDAR_EN'] == 0
    rig.run(2800)
    assert rig.state() == Q.HALTING                     # 3 s before the latch goes off
    rig.run(300)
    assert rig.state() == Q.OFF
    rig.run(2000)
    offs = rig.hw.pulses_of('LATCH_OFF')
    assert len(offs) >= 4                               # pulsed again while still powered
    assert all(p[2] == Q.Settings.LATCH_OFF_PULSE_MS for p in offs)


def test_key_pressed_again_every_10s_then_forced_off_at_60s():
    rig = up_and_talking()
    rig.press()
    t0 = rig.seq.t_shutdown
    rig.run_with_heartbeat(59000)                       # the Jetson keeps running, ignores the key
    assert rig.state() == Q.SHUTDOWN_REQUESTED
    keys = [p[0] - t0 for p in rig.hw.pulses_of('JETSON_PWR_KEY')]
    assert len(keys) == 6
    for a, b in zip(keys, keys[1:]):
        assert b - a == pytest.approx(10000, abs=20)
    rig.run_with_heartbeat(1500)
    assert rig.state() == Q.HALTING and rig.seq.why == 'shutdown_timeout'


def test_no_repress_when_the_jetson_went_quiet():
    rig = up_and_talking()
    rig.press()
    rig.run(30000)                                      # heartbeats stopped (daemon killed, no bye)
    assert len(rig.hw.pulses_of('JETSON_PWR_KEY')) == 1


def test_bye_extends_the_shutdown_wait():
    rig = up_and_talking()
    rig.press()
    rig.usb.send({'cmd': 'bye'})
    rig.run(70000)
    assert rig.state() == Q.SHUTDOWN_REQUESTED          # past 60 s: the Jetson said it is going down
    rig.run(51000)
    assert rig.state() in (Q.HALTING, Q.OFF)


def test_jetson_already_off_goes_straight_to_halting():
    rig = running()
    rig.press()
    assert rig.state() == Q.HALTING and rig.seq.why == 'jetson_off'
    assert rig.hw.pulses_of('JETSON_PWR_KEY') == []


def test_long_press_cuts_at_5s_and_releases_the_latch_after_the_button():
    # review M5: LATCH_OFF never pulses while the button holds the Pololu's ON input
    rig = up_and_talking()
    rig.hw.set_input('BUTTON_N', 0)
    rig.run(4900)
    assert rig.state() == Q.RUN
    rig.run(200)
    assert rig.state() == Q.OFF and rig.seq.why == 'long_press'
    hw = rig.hw
    assert hw.out['MAIN_EN'] == 0 and hw.out['PRECHARGE_EN'] == 0 and hw.out['LIDAR_EN'] == 0
    assert hw.out['DEVKIT_PWR'] == 0                    # the Jetson is cut at once (force off)
    rig.run(5000)                                       # still held
    assert hw.pulses_of('LATCH_OFF') == []
    assert hw.out['LED_STATUS'] == 1 and hw.out['LED_FAULT'] == 1
    t_release = rig.clock.now()
    hw.set_input('BUTTON_N', 1)
    rig.run(200)
    offs = hw.pulses_of('LATCH_OFF')
    assert len(offs) == 1 and offs[0][0] >= t_release


def test_shutdown_command_from_the_jetson():
    rig = up_and_talking()
    rig.usb.send({'cmd': 'shutdown', 'id': 7})
    rig.run(100)
    ack = [m for m in rig.replies('ack') if m['cmd'] == 'shutdown'][0]
    assert ack['id'] == 7 and ack['started'] is True
    assert rig.state() == Q.SHUTDOWN_REQUESTED and len(rig.hw.pulses_of('JETSON_PWR_KEY')) == 1


# ---------------------------------------------------------------- halt detection
def test_heartbeat_lost_with_the_jetson_up_asks_it_to_shut_down():
    # review M4: a crashed daemon or a loose Pico cable must not hard-cut a running Jetson
    rig = up_and_talking()
    rig.run(59000)
    assert rig.state() == Q.RUN
    rig.run(1100)
    assert rig.state() == Q.SHUTDOWN_REQUESTED and rig.seq.why == 'hb_lost'
    t0 = rig.seq.t_shutdown
    rig.run(120000)                                     # the Jetson ignores the key and stays up
    assert rig.state() == Q.SHUTDOWN_REQUESTED          # no forced cut
    keys = [p[0] - t0 for p in rig.hw.pulses_of('JETSON_PWR_KEY')]
    assert keys[0] == 0 and len(keys) == 6 and keys[-1] < 60000     # every 10 s, up to 60 s
    assert rig.hw.pulses_of('LATCH_OFF') == []
    rig.hw.set_input('JETSON_3V3_SENSE', 0)             # the module finally powers off
    rig.hw.set_input('JETSON_UP', 0)
    rig.run(2100)
    assert rig.state() == Q.HALTING and rig.seq.why == '3v3_lost'
    rig.run(3100)
    assert rig.state() == Q.OFF


def test_heartbeat_lost_then_halt_frame():
    rig = up_and_talking()
    rig.run(61000)
    assert rig.state() == Q.SHUTDOWN_REQUESTED
    rig.usb.send({'cmd': 'halt', 'verb': 'poweroff'})
    rig.run(100)
    assert rig.state() == Q.HALTING


def test_heartbeat_lost_with_the_jetson_down_halts():
    rig = up_and_talking()
    rig.hw.set_input('JETSON_UP', 0)
    rig.seq.v33_seen = False                            # a 3.3 V sense that never worked
    rig.hw.set_input('JETSON_3V3_SENSE', 0)
    rig.run(61100)
    assert rig.state() == Q.HALTING and rig.seq.why == 'hb_lost'


def test_no_heartbeat_ever_means_no_timeout():
    rig = running()
    rig.hw.set_input('JETSON_3V3_SENSE', 1)
    rig.hw.set_input('JETSON_UP', 1)
    rig.usb.send('status')                              # a person at a laptop, not the Jetson's daemon
    rig.run(130000)
    assert rig.state() == Q.RUN


def test_hb_timeout_zero_disables_it():
    rig = up_and_talking()
    rig.usb.send({'cmd': 'hb_timeout', 's': 0})
    rig.run(200000)
    assert rig.state() == Q.RUN


def test_bye_gives_a_longer_grace():
    rig = up_and_talking()
    rig.usb.send({'cmd': 'bye'})
    rig.run(100000)
    assert rig.state() == Q.RUN
    rig.run(21000)
    assert rig.state() == Q.SHUTDOWN_REQUESTED and rig.seq.why == 'hb_lost'
    rig.hw.set_input('JETSON_3V3_SENSE', 0)
    rig.run(2100)
    assert rig.state() == Q.HALTING


def test_3v3_lost_for_2s_is_a_halt_and_a_blink_is_not():
    rig = up_and_talking()
    rig.hw.set_input('JETSON_3V3_SENSE', 0)
    rig.run_with_heartbeat(1000)
    rig.hw.set_input('JETSON_3V3_SENSE', 1)
    rig.run_with_heartbeat(3000)
    assert rig.state() == Q.RUN
    rig.hw.set_input('JETSON_3V3_SENSE', 0)
    rig.run(2100)
    assert rig.state() == Q.HALTING and rig.seq.why == '3v3_lost'


def test_reboot_keeps_power_and_ends_on_the_new_boot():
    rig = up_and_talking()
    rig.usb.send({'cmd': 'bye'})
    rig.usb.send({'cmd': 'halt', 'verb': 'reboot'})
    rig.run(100)
    assert rig.state() == Q.RUN and rig.seq.t_grace is not None
    rig.hw.set_input('JETSON_3V3_SENSE', 0)             # module resets
    rig.hw.set_input('JETSON_UP', 0)
    rig.run(5000)
    rig.hw.set_input('JETSON_3V3_SENSE', 1)
    rig.run(85000)                                      # booting: no heartbeat for 90 s
    assert rig.state() == Q.RUN
    rig.hw.set_input('JETSON_UP', 1)
    rig.run_with_heartbeat(2000, boot='b00t0002')
    assert rig.seq.t_grace is None and rig.seq.boots == 1
    assert rig.events('reboot_done')
    rig.run(61000)                                      # normal rules again
    assert rig.state() == Q.SHUTDOWN_REQUESTED and rig.seq.why == 'hb_lost'


def test_reboot_that_never_comes_back_halts():
    rig = up_and_talking()
    rig.usb.send({'cmd': 'halt', 'verb': 'reboot'})
    rig.hw.set_input('JETSON_3V3_SENSE', 0)
    rig.run(Q.Settings.REBOOT_GRACE_MS + 100)
    assert rig.state() in (Q.HALTING, Q.OFF)


def test_halt_during_shutdown_request_wins_over_reboot():
    rig = up_and_talking()
    rig.press()
    rig.usb.send({'cmd': 'halt', 'verb': 'reboot'})
    rig.run(100)
    assert rig.state() == Q.HALTING


def test_hard_reboot_pulses_reset():
    rig = up_and_talking()
    rig.usb.send('reboot hard')
    rig.run(100)
    resets = rig.hw.pulses_of('JETSON_RESET')
    assert len(resets) == 1 and resets[0][2] == 100
    assert rig.state() == Q.RUN


# ---------------------------------------------------------------- battery and temperature
def test_low_battery_warns_then_shuts_down():
    rig = up_and_talking()
    rig.hw.bat_v = 11.9                                 # the 2 s filter needs about 7 s to cross 12.0 V
    rig.run_with_heartbeat(30000)
    assert not rig.events('low_battery')
    rig.run_with_heartbeat(10000)
    warn = rig.events('low_battery')
    assert warn and warn[0]['level'] == 'warn'
    assert rig.state() == Q.RUN and rig.seq.status()['low'] is True
    rig.hw.bat_v = 11.5
    rig.run_with_heartbeat(9000)
    assert rig.state() == Q.RUN
    rig.run_with_heartbeat(6000)
    assert rig.state() == Q.SHUTDOWN_REQUESTED and rig.seq.why == 'low_battery'
    assert rig.events('low_battery')[-1]['level'] == 'shutdown'


def test_low_battery_cut_stays_active_while_charging():
    # review m7: the car can draw more than the charger gives; a flat pack still shuts down
    rig = up_and_talking()
    rig.hw.set_input('CHG_PRESENT_N', 0)
    rig.hw.bat_v = 11.5
    rig.run_with_heartbeat(30000)
    assert rig.hw.out['CHG_STAT_N_TO_JETSON'] == 0      # low = charging
    assert rig.state() == Q.SHUTDOWN_REQUESTED and rig.seq.why == 'low_battery'


def test_low_battery_checks_pause_while_the_charger_raises_the_pack():
    rig = Rig(bat_v=11.3)                               # switched on low, charger already in
    rig.hw.set_input('CHG_PRESENT_N', 0)
    rig.run(1000)
    rig.jetson_boots()
    for _ in range(60):                                 # +0.01 V per second for a minute
        rig.run_with_heartbeat(1000)
        rig.hw.bat_v += 0.01
    assert rig.state() == Q.RUN and not rig.events('low_battery')
    rig.hw.set_input('CHG_PRESENT_N', 1)                # charger out at 11.9 V: only a warning later
    rig.run_with_heartbeat(15000)
    assert rig.state() == Q.RUN


def test_short_sag_does_not_shut_down():
    rig = up_and_talking()
    rig.hw.bat_v = 11.0                                 # hard acceleration
    rig.run_with_heartbeat(3000)
    rig.hw.bat_v = 15.5
    rig.run_with_heartbeat(20000)
    assert rig.state() == Q.RUN


def test_hot_fets_open_the_main_switch_and_rearm_when_cool():
    rig = up_and_talking()
    rig.hw.fet_c = 95.0
    rig.run_with_heartbeat(1000)
    assert rig.state() == Q.LOCKOUT and rig.seq.why == 'fet_hot'
    assert rig.hw.out['MAIN_EN'] == 0
    rig.hw.fet_c = 80.0
    rig.press()
    assert rig.state() == Q.LOCKOUT and rig.events('rearm_refused')
    rig.hw.fet_c = 50.0
    rig.run_with_heartbeat(200)
    rig.press()
    rig.run_with_heartbeat(1000)
    assert rig.state() == Q.RUN


def test_no_ntc_fitted_runs_the_fan_flat_out():
    rig = Rig()
    rig.hw.fet_c = None
    rig.run(1000)
    assert rig.state() == Q.RUN and rig.seq.fet_c is None and rig.hw.fan_duty == 100


def test_bus_lost_while_running():
    rig = up_and_talking()
    rig.hw.main_switch_works = False
    rig.run_with_heartbeat(1000)
    assert rig.state() == Q.LOCKOUT and rig.seq.why == 'bus_lost'


# ---------------------------------------------------------------- lidar, fan, mirrors
def test_lidar_by_command_and_by_LIDAR_REQ():
    rig = up_and_talking()
    rig.usb.send({'cmd': 'lidar', 'on': False, 'id': 3})
    rig.run(100)
    assert rig.hw.out['LIDAR_EN'] == 0
    rig.hw.set_input('LIDAR_REQ', 1)
    rig.run(100)
    assert rig.hw.out['LIDAR_EN'] == 1
    rig.hw.set_input('LIDAR_REQ', 0)
    rig.run(100)
    assert rig.hw.out['LIDAR_EN'] == 0
    assert [e['source'] for e in rig.events('lidar')] == ['command', 'LIDAR_REQ', 'LIDAR_REQ']


def test_lidar_req_glitch_is_ignored():
    rig = running()
    rig.hw.set_input('LIDAR_REQ', 1)
    rig.run(10)
    rig.hw.set_input('LIDAR_REQ', 0)
    rig.run(200)
    assert rig.hw.out['LIDAR_EN'] == 1 and not rig.events('lidar')


def test_signals_to_the_jetson_only_while_its_3v3_is_up():
    rig = running()
    assert rig.hw.out['ESTOP_OK_TO_JETSON'] == 0 and rig.hw.out['CHG_STAT_N_TO_JETSON'] == 0
    rig.hw.set_input('JETSON_3V3_SENSE', 1)
    rig.run(20)
    assert rig.hw.out['ESTOP_OK_TO_JETSON'] == 1 and rig.hw.out['CHG_STAT_N_TO_JETSON'] == 1


def test_fan_manual_and_auto():
    rig = running()
    assert rig.hw.fan_duty == Q.Settings.FAN_MIN        # 25 C
    rig.usb.send('fan 70')
    rig.run(50)
    assert rig.hw.fan_duty == 70
    rig.usb.send({'cmd': 'fan', 'auto': True})
    rig.hw.fet_c = 60.0
    rig.run(300)
    assert rig.hw.fan_duty == 100
    rig.usb.send({'cmd': 'fan', 'duty': 140})
    rig.run(20)
    assert rig.replies('err')[-1]['cmd'] == 'fan'


# ---------------------------------------------------------------- commands and status
def test_status_frame_every_second_and_on_request():
    rig = running()
    statuses = rig.replies('status')
    assert len(statuses) == 1
    rig.usb.send({'cmd': 'status', 'id': 42})
    rig.run(20)
    st = rig.replies('status')[-1]
    assert st['id'] == 42 and st['state'] == 'RUN' and st['bms']['ok'] is True
    assert st['bms']['cells'] == [3.9, 3.91, 3.9, 3.92]
    assert st['vm'] == pytest.approx(16.0) and st['estop'] is True and st['kill'] is False


def test_bms_fets_needs_force_for_discharge_off():
    rig = running()
    rig.usb.send({'cmd': 'bms_fets', 'charge': True, 'discharge': False, 'id': 1})
    rig.run(50)
    assert rig.replies('err')[-1]['id'] == 1
    assert rig.bms.mos_writes == []
    rig.usb.send('bms_fets charge_off')
    rig.run(300)
    assert rig.bms.mos_writes == [1]
    rig.usb.send({'cmd': 'bms_fets', 'charge': False, 'discharge': False, 'force': True})
    rig.run(300)
    assert rig.bms.mos_writes == [1, 3]


def test_bms_fets_refused_when_bms_offline():
    rig = running()
    rig.bms.answer = False
    rig.run(6000)
    rig.usb.send('bms_fets on')
    rig.run(50)
    assert 'not answering' in rig.replies('err')[-1]['msg']
    assert rig.events('bms')[-1]['online'] is False


def test_unknown_and_junk_commands():
    rig = running()
    rig.usb.send('fly to the moon')
    rig.usb.send('{"cmd": "dance"}')
    rig.usb.send('{"t": "status", "state": "RUN"}')     # our own line echoed back: ignored
    rig.usb.send('{not json')
    rig.run(50)
    errs = rig.replies('err')
    assert len(errs) == 3
    assert rig.state() == Q.RUN


def test_repl_command_and_ctrl_c():
    rig = running()
    rig.usb.send('repl')
    rig.clock.advance(10)
    rig.hw.step(10)
    assert rig.app.step() == 'repl'
    rig = running()
    rig.usb.rx += b'\x03\r\x01'                         # Thonny / mpremote: Ctrl-C then raw REPL
    rig.clock.advance(10)
    assert rig.app.step() == 'repl'
    assert bytes(rig.usb.rx) == b'\r\x01'               # left for the REPL
    rig.seq.make_safe()
    assert rig.hw.out['MAIN_EN'] == 0 and rig.hw.out['VESC_KILL'] == 0


def test_log_and_help():
    rig = running()
    rig.usb.send('log')
    rig.usb.send('help')
    rig.run(20)
    acks = {a['cmd']: a for a in rig.replies('ack')}
    assert any(e['evt'] == 'state' for e in acks['log']['events'])
    assert 'bms_fets' in acks['help']['commands']


def test_jetson_power_cycle():
    rig = up_and_talking()
    rig.usb.send({'cmd': 'jetson_power_cycle', 'off_s': 10})
    rig.run(100)
    assert rig.hw.out['DEVKIT_PWR'] == 0 and rig.seq.status()['jet']['power'] is False
    rig.hw.set_input('JETSON_3V3_SENSE', 0)             # the module loses power
    rig.hw.set_input('JETSON_UP', 0)
    rig.run(9800)
    assert rig.hw.out['DEVKIT_PWR'] == 0 and rig.state() == Q.RUN
    rig.run(300)
    assert rig.hw.out['DEVKIT_PWR'] == 1                # back on after 10 s
    rig.run(60000)                                      # booting: the reboot grace covers it
    assert rig.state() == Q.RUN
    rig.hw.set_input('JETSON_3V3_SENSE', 1)
    rig.run_with_heartbeat(2000, boot='b00t0002')
    assert rig.seq.t_grace is None and rig.state() == Q.RUN
    rig.usb.send('jetson_power_cycle 500')
    rig.run(20)
    assert rig.replies('err')[-1]['cmd'] == 'jetson_power_cycle'


def test_devkit_power_stays_on_until_off():
    rig = up_and_talking()
    rig.press()
    rig.usb.send({'cmd': 'halt', 'verb': 'poweroff'})
    rig.run(2000)
    assert [c for c in rig.hw.changes if c[1] == 'DEVKIT_PWR'] == []
    rig.run(2000)
    assert rig.state() == Q.OFF and rig.hw.out['DEVKIT_PWR'] == 0


# ---------------------------------------------------------------- review fixes (Oct 24 review)
@pytest.mark.parametrize('bat', [12.0, 13.0, 14.4, 16.8])
@pytest.mark.parametrize('load_a', [0.05, 0.10, 0.15, 0.20])
def test_precharge_with_esc_and_bec_loading_the_bus(bat, load_a):
    # review M3: the reviewer's cases (10.6 ohm with the PTC and FET) all arm on the first try
    rig = Rig(bat_v=bat, precharge_ohm=10.6, vm_load_a=load_a)
    rig.run(1500)
    assert rig.state() == Q.RUN and not rig.events('precharge_failed')
    assert rig.seq.precharge_ms <= rig.seq.precharge_timeout_ms()


def test_settled_bus_too_far_below_the_pack_still_fails():
    rig = Rig(bat_v=12.0, vm_load_a=0.4)                # settles 3.5 V short of the pack
    rig.run(8000)
    assert rig.state() == Q.FAULT and rig.seq.why == 'slow'


def test_off_stops_pulsing_once_the_latch_has_dropped_and_restarts_when_power_returns():
    # review m8: a Pico on USB power must not switch the car off again when it is switched on
    rig = up_and_talking()
    rig.hw.set_input('BUTTON_N', 0)
    rig.run(5200)
    rig.hw.set_input('BUTTON_N', 1)
    rig.run(200)
    assert rig.hw.pulses_of('LATCH_OFF')
    rig.hw.bat_v = 0.0                                  # the latch dropped VSYS_SW; USB keeps the Pico up
    rig.run(3000)
    n = len(rig.hw.pulses_of('LATCH_OFF'))
    rig.run(5000)
    assert len(rig.hw.pulses_of('LATCH_OFF')) == n      # no more pulses
    assert rig.events('latch_off') and not rig.seq.reset_requested
    rig.hw.bat_v = 15.5                                 # someone switches the car on again
    rig.run(300)
    assert rig.seq.reset_requested and rig.events('power_returned')
    assert len(rig.hw.pulses_of('LATCH_OFF')) == n
    rig.clock.advance(10)
    assert rig.app.step() == 'reset'


def test_off_gives_up_after_max_pulses_and_a_click_retries():
    rig = up_and_talking()
    rig.hw.set_input('BUTTON_N', 0)
    rig.run(5200)
    rig.hw.set_input('BUTTON_N', 1)
    rig.run(15000)                                      # the latch never drops (sim: pack stays)
    assert len(rig.hw.pulses_of('LATCH_OFF')) == Q.Settings.OFF_MAX_PULSES
    assert rig.seq.latch_stuck and rig.events('latch_stuck')
    rig.press()
    rig.run(1000)
    assert len(rig.hw.pulses_of('LATCH_OFF')) > Q.Settings.OFF_MAX_PULSES


def test_halting_while_the_button_is_held_waits_for_release():
    rig = up_and_talking()
    rig.press()
    rig.usb.send({'cmd': 'halt', 'verb': 'poweroff'})
    rig.hw.set_input('BUTTON_N', 0)                     # someone presses again and holds
    rig.run(3500)
    assert rig.state() == Q.OFF and rig.hw.pulses_of('LATCH_OFF') == []
    rig.hw.set_input('BUTTON_N', 1)
    rig.run(100)
    assert len(rig.hw.pulses_of('LATCH_OFF')) == 1
