"""The supervisor's state machine: main switch, E-stop latch, Jetson shutdown and halt, faults.

Ported from rev A's STM32 code (firmware/vesc/hw_atlas_drv1.c: sup_thread, atlas_precharge,
atlas_power_off, the button handling) for the rev B hardware: a Raspberry Pi Pico on the
ATLAS-PWR-1 power board, the Jetson on its NVIDIA dev-kit carrier, the Flipsky FSESC.
The Oct 23 review's firmware findings are designed out:
  F1  nothing here can crash on a failed precharge; the button works in every state
  F3  the precharge gives up on a bus that does not reach 90 % in 5 time constants, using real
      elapsed time, so a partial short gets one short pulse per try
  F4  nothing blocks: the outputs are recomputed from the state on every tick, so a command,
      a button press or an E-stop is never undone by a precharge that was in progress
  F6  the power key is only pressed again while the Jetson is evidently still running

    INIT -> PRECHARGE -> RUN -> SHUTDOWN_REQUESTED -> HALTING -> OFF
            |  ^            \\
            v  | (press)     LOCKOUT (E-stop, hot FETs, bus lost, restart): press to re-arm
            FAULT (precharge gave up, main switch did not hold the bus): press = shut down

Call tick() every Settings.TICK_MS. It never waits. Every timing and threshold is in Settings.
"""
import math

import pins

FW_VERSION = '0.1.0'
PROTOCOL = 1


class Settings:
    """Every timing and threshold in one table.  value  # rev A value (hw_atlas_drv1.c): why"""
    # ---------------------------------------------------------------- main loop
    TICK_MS = 10                    # rev A 5 (SUP_PERIOD_MS): 10 ms is enough for a 10 ms precharge check
    INIT_MS = 100                   # rev A waited for the ADC (up to 3 s): ADC and inputs settle
    STATUS_PERIOD_MS = 1000         # new: 1 Hz status frame to the Jetson (rev B spec)
    # ---------------------------------------------------------------- precharge and main switch
    PRECHARGE_R_OHM = 10.0          # rev A 11 (2 x 22 ohm 2512 in parallel): 10 ohm 5 W wirewound
    VM_CAP_UF = 2000.0              # new: FSESC input capacitance, not published; the rev B ESC study
                                    #   says plan for 2 mF. Measure it and set it here (tau = R x C = 20 ms)
    PRECHARGE_TAUS = 5              # rev A PRECHARGE_MAX_MS 400 (really 460, review F3): rev B spec "within 5 tau"
    PRECHARGE_DONE_RATIO = 0.90     # rev A "settled above 9 V": rev B spec "VM reaches 90 % of BAT_SENSE" ...
    PRECHARGE_SETTLED_MARGIN_V = 2.5  # ... or (review M3) VM within 2.5 V of the pack and no longer rising:
    PRECHARGE_SETTLED_DV = 0.1        #   under 0.1 V per 10 ms. The ESC booting and the Castle BEC load VM
                                      #   (150-200 mA), so a healthy bus can settle short of 90 % on 10 ohm
    PRECHARGE_SHORT_CHECK_MS = 10   # rev A PRECHARGE_CHECK_MS 10: the short-circuit check comes this early
    PRECHARGE_SHORT_V = 4.0         # rev A 4.0: under this at 10 ms = something on VM is shorted ...
    PRECHARGE_SHORT_FRACTION = 0.5  # new: ... or under half of what R x C predicts at 10 ms, if that is
                                    #   lower. A healthy 2.5 mF bus on a 12 V pack reads 3.96 V at 10 ms,
                                    #   so rev A's fixed 4 V would call it a short
    PRECHARGE_OVERLAP_MS = 50       # rev A 20: rev B spec "MAIN_EN, 50 ms, precharge off"
    MAIN_VERIFY_MS = 300            # new: VM must stay above 90 % this long after main on, or the
                                    #   main FETs are not conducting (MIC5014 or FET fault)
    PRECHARGE_TRIES = 3             # rev A 1 at boot + 3 after trips: rev B spec "give up after 3 tries"
    PRECHARGE_RETRY_GAP_MS = 2000   # rev A 15000, set by the 2512 SMD resistors' pulse rating. A 5 W
                                    #   wirewound takes the <= 0.3 J of a 10 ms try easily
    BAT_MIN_V = 10.0                # new: no precharge if the pack reads under this (bad sense divider)
    BUS_LOST_RATIO = 0.5            # rev A BUS_LOST_V 6.0: VM under half the pack while on ...
    BUS_LOST_MS = 50                # rev A BUS_LOST_MS 20: ... this long = the main switch dropped out
    # ---------------------------------------------------------------- Jetson
    PWR_KEY_PULSE_MS = 180          # rev A 1000 (JETSON_SHUTDOWN_PRESS_MS): 150-200 ms (dev-kit study,
                                    #   review MINOR-1: a long press can force a hard power-off)
    RESET_PULSE_MS = 100            # new: J14 SYS_RESET* through PC817 #2 (rev B spec)
    REPRESS_MS = 10000              # rev A 10000: press again this often while the Jetson still runs
    SHUTDOWN_WAIT_MS = 60000        # rev A 60000: then force off (rev B spec), except after a lost
                                    #   heartbeat (review M4): then keep waiting for HALT or 3.3 V to go
    SHUTDOWN_WAIT_ACK_MS = 120000   # new: the Jetson said "bye" (its shutdown has started): wait longer
    BOOTING_MS = 90000              # review F6 fix: with no heartbeat ever, re-press only if the Jetson
                                    #   had been on for less than this (it may have missed the press)
    HB_TIMEOUT_MS = 60000           # new (rev B spec): no heartbeat this long after the first one: if the
                                    #   Jetson is still powered, ask it to shut down (review M4); if not, halt
    HB_FRESH_MS = 3000              # new: a heartbeat this recent means "running normally"
    BYE_GRACE_MS = 120000           # new: after "bye" (daemon stopping), this replaces HB_TIMEOUT_MS
    REBOOT_GRACE_MS = 240000        # new: after REBOOT, ignore a missing heartbeat and 3.3 V this long
    JETSON_CYCLE_OFF_MS = 10000     # new: `jetson_power_cycle` holds the dev kit off this long by default
                                    #   (dev-kit study: let the rails discharge for at least 10 s)
    JETSON_CYCLE_MAX_S = 120
    V33_LOST_MS = 2000              # new (dev-kit study): J12 3.3 V gone this long = module off
    UP_CONFIRM_MS = 1000            # rev A JETSON_ON_CONFIRM_MS 1000: JETSON_UP steady this long
    HALT_TO_OFF_MS = 3000           # rev A 100 + 10: rev B spec "MAIN_EN off, lidar off, 3 s, LATCH_OFF"
    LATCH_OFF_PULSE_MS = 100        # new: Pololu #2813 "a high pulse on OFF turns off the switch"; only
                                    #   with the button released (review M5: ON and OFF never together)
    OFF_RETRY_MS = 500              # rev A re-asserted KILL every 100 ms while the button was held
    OFF_MAX_PULSES = 20             # new (review m8): stop after 10 s of pulses; a click tries again
    BAT_GONE_V = 4.0                # new (review m8): VSYS_SW under this = the latch is off; a Pico still
    BAT_BACK_V = 9.0                #   running (on USB power) restarts when it comes back above this ...
    BAT_BACK_MS = 200               #   ... for this long (the car was switched on again)
    # ---------------------------------------------------------------- button
    DEBOUNCE_MS = 30                # rev A BUTTON_SAMPLES 3 x 10 ms
    LONG_PRESS_MS = 5000            # new (rev B spec): held this long = force off now
    # ---------------------------------------------------------------- lidar and fan
    LIDAR_REQ_DEBOUNCE_MS = 20      # new: J12 pin 29 edges
    FAN_MIN = 30                    # new: fan duty (%) at or below FAN_LOW_C
    FAN_LOW_C = 35.0
    FAN_HIGH_C = 60.0               # 100 % at or above this
    FAN_NO_SENSOR = 100             # no NTC fitted: full speed
    LIDAR_AT_BOOT = True            # new (rev B spec): "lidar per config (default on)"
    # ---------------------------------------------------------------- faults
    FET_PERIOD_MS = 100             # new: NTC read rate
    FET_HOT_C = 90.0                # new (rev B spec): main-switch heatsink over this ...
    FET_HOT_MS = 500                # ... this long = main switch off
    FET_REARM_C = 70.0              # new: a press re-arms only below this
    BAT_FILTER_MS = 2000            # new: pack voltage averaged over about this long
    BAT_LOW_V = 12.0                # new (rev B spec): under this for BAT_LOW_MS = tell the Jetson
    BAT_LOW_MS = 30000
    BAT_CUT_V = 11.6                # new (rev B spec): under this for BAT_CUT_MS = clean shutdown
    BAT_CUT_MS = 10000              # judgment call: long enough to ride through motor sag
    BAT_RISING_V = 0.05             # new (review m7): with a charger in, the low-pack checks pause only
    BAT_RISING_MS = 10000           #   while the pack rises by more than this per this long
    HISTORY = 20                    # events kept for the `log` command


INIT = 'INIT'
PRECHARGE = 'PRECHARGE'
RUN = 'RUN'
LOCKOUT = 'LOCKOUT'
FAULT = 'FAULT'
SHUTDOWN_REQUESTED = 'SHUTDOWN_REQUESTED'
HALTING = 'HALTING'
OFF = 'OFF'

COMMANDS = ('hb', 'status', 'lidar', 'shutdown', 'reboot', 'halt', 'bye', 'bms_fets', 'fan',
            'hb_timeout', 'jetson_power_cycle', 'log', 'version', 'help', 'repl')


def ntc_celsius(v):
    """FET heatsink temperature from the NTC node voltage (NTC to ground, pull-up to 3.3 V)."""
    vref = pins.ADC_VREF
    if v >= vref - 0.01:
        return None                 # open: no NTC fitted
    if v <= 0.01:
        return 200.0                # shorted: report hot, so the main switch stays off
    r = pins.NTC_PULLUP_OHM * v / (vref - v)
    inv_t = 1.0 / 298.15 + math.log(r / pins.NTC_R25_OHM) / pins.NTC_BETA
    return round(1.0 / inv_t - 273.15, 1)


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


class Sequencer:
    def __init__(self, hw, clock, settings=Settings, cold_start=True, bms=None):
        self.hw = hw
        self.clock = clock
        self.S = settings
        self.bms = bms
        self.cold_start = cold_start
        now = clock.now()
        self.t_start = now
        self.state = INIT
        self.why = 'power-on' if cold_start else 'restart'
        self.t_state = now
        self.events = []
        self.history = []
        self.repl_requested = False
        self.reset_requested = False    # main.py restarts the Pico (power came back while in OFF)
        # measurements
        self.estop_ok = False
        self._estop_prev = False
        self._estop_irq = False
        self.estops = 0
        self.vm = 0.0
        self.dv10 = None            # VM change per 10 ms (precharge "stopped rising" test)
        self._vm_prev = None
        self.bat = 0.0
        self.bat_avg = None
        self.chg = False
        self.fet_c = None
        self._t_fet = None
        # precharge
        self.attempt = 0
        self.phase = ''
        self.t_phase = now
        self.precharge_ms = None
        self.last_fail = ''
        self._t_bus_low = None
        self._t_hot = None
        # button
        self._btn_raw = 0
        self._btn_stable = 0        # assume pressed: the press that switched the car on
        self._t_btn_raw = now
        self._btn_armed = False
        self._t_btn_down = None
        self._long_done = False
        # Jetson
        self.v33 = False
        self.v33_seen = False
        self._t_v33_high = None
        self._t_v33_first = None
        self.up = False
        self._up_raw = 0
        self._t_up_raw = now
        self.hb_seen = False
        self.t_hb = None
        self.t_bye = None
        self.t_grace = None
        self.boot_id = None
        self.boots = 0
        self.hb_timeout_ms = settings.HB_TIMEOUT_MS
        self.t_cycle = None         # dev kit power switched off for a power cycle since this time
        self.cycle_ms = 0
        # shutdown
        self.t_shutdown = None
        self.t_press = None
        self.presses = 0
        self._age_at_shutdown = 0
        self.shutdown_force = True  # force off when the shutdown wait runs out (not after a lost heartbeat)
        self._t_off_pulse = None
        self._off_pulses = 0
        self._bat_gone = False
        self._t_bat_back = None
        self.latch_stuck = False
        # lidar, fan, battery
        self.lidar_on = settings.LIDAR_AT_BOOT
        self._lreq_raw = 0
        self._lreq_stable = 0
        self._t_lreq = now
        self.fan_manual = None
        self.fan_duty = None
        self._t_low = None
        self.low_warned = False
        self._t_cut = None
        self._bat_hist = []
        self._bms_online = False
        self._bms_prot = 0

    # ================================================================ start and interrupt
    def start(self):
        for name, _gp, level in pins.OUTPUTS:
            self.hw.write(name, level)
        r = self.hw.read('LIDAR_REQ')
        self._lreq_raw = self._lreq_stable = r
        if not self.cold_start and self.hw.read('JETSON_UP') == 1:
            self.lidar_on = r == 1      # restarted under a running Jetson: keep what it asked for
        self._estop_prev = self.hw.read('ESTOP_OK') == 1
        self.hw.on_estop_open(self.estop_irq)
        self.event('boot', fw=FW_VERSION, proto=PROTOCOL, cold=self.cold_start)

    def estop_irq(self, pin=None):
        """Hard interrupt on the E-stop loop opening. The 74HC08 has already cut the main
        switch; drop our enables too, so closing the loop again cannot re-close the switch
        onto a drained bus without a precharge. Only pin writes and a flag here."""
        hw = self.hw
        hw.write('MAIN_EN', 0)
        hw.write('PRECHARGE_EN', 0)
        hw.write('VESC_KILL', 0)
        hw.write('ESTOP_OK_TO_JETSON', 0)
        self._estop_irq = True

    # ================================================================ the tick
    def tick(self):
        now = self.clock.now()
        self._read_inputs(now)
        self._estop(now)
        self._button(now)
        self._jetson(now)
        self._battery(now)
        self._bms_watch()
        self._step_state(now)
        self._apply_outputs(now)

    # ---------------------------------------------------------------- inputs
    def _read_inputs(self, now):
        S = self.S
        hw = self.hw
        self.estop_ok = hw.read('ESTOP_OK') == 1
        self.vm = hw.volts('VM_SENSE') * pins.VM_DIVIDER
        if self._vm_prev is not None:
            dt = self.clock.since(self._vm_prev[0])
            self.dv10 = (self.vm - self._vm_prev[1]) * 10.0 / dt if dt > 0 else self.dv10
        self._vm_prev = (now, self.vm)
        self.bat = hw.volts('BAT_SENSE') * pins.BAT_DIVIDER
        if self.bat_avg is None:
            self.bat_avg = self.bat
        else:
            self.bat_avg += (self.bat - self.bat_avg) * S.TICK_MS / (S.TICK_MS + S.BAT_FILTER_MS)
        self.chg = hw.read('CHG_PRESENT_N') == 0
        if self._t_fet is None or self.clock.since(self._t_fet) >= S.FET_PERIOD_MS:
            self._t_fet = now
            self.fet_c = ntc_celsius(hw.volts('FET_NTC'))
        r = hw.read('LIDAR_REQ')
        if r != self._lreq_raw:
            self._lreq_raw = r
            self._t_lreq = now
        elif r != self._lreq_stable and self.clock.since(self._t_lreq) >= S.LIDAR_REQ_DEBOUNCE_MS:
            self._lreq_stable = r
            self._set_lidar(r == 1, 'LIDAR_REQ')

    # ---------------------------------------------------------------- E-stop
    def _estop(self, now):
        opened = self._estop_irq or (self._estop_prev and not self.estop_ok)
        closed = not opened and not self._estop_prev and self.estop_ok
        self._estop_irq = False
        self._estop_prev = self.estop_ok
        if opened:
            self.estops += 1
            self.event('estop', open=True, state=self.state)
            if self.state in (PRECHARGE, RUN):
                self._lockout('estop')
        elif closed:
            hint = 'press the button to re-arm' if self.state == LOCKOUT else ''
            self.event('estop', open=False, hint=hint)

    # ---------------------------------------------------------------- button
    def _button(self, now):
        S = self.S
        raw = self.hw.read('BUTTON_N')          # 0 = pressed
        if raw != self._btn_raw:
            self._btn_raw = raw
            self._t_btn_raw = now
        elif raw != self._btn_stable and self.clock.since(self._t_btn_raw) >= S.DEBOUNCE_MS:
            self._btn_stable = raw
            if raw == 1:                        # released
                if not self._btn_armed:
                    self._btn_armed = True      # the press that switched the car on has ended
                elif self._t_btn_down is not None and not self._long_done:
                    self._click()
                self._t_btn_down = None
                self._long_done = False
            elif self._btn_armed:
                self._t_btn_down = now
        if (self._t_btn_down is not None and not self._long_done
                and self.clock.since(self._t_btn_down) >= S.LONG_PRESS_MS):
            self._long_done = True
            self.event('button', press='long')
            if self.state != OFF:
                self._force_off('long_press')   # LATCH_OFF waits for the release (review M5)

    def _click(self):
        self.event('button', press='short', state=self.state)
        s = self.state
        if s == LOCKOUT:
            refusal = self._rearm_refusal()
            if refusal:
                self.event('rearm_refused', why=refusal)    # review m16: never a shutdown from here
            else:
                self._start_precharge('button')
        elif s in (PRECHARGE, RUN, FAULT):
            self.request_shutdown('button')
        elif s == OFF and self.latch_stuck:
            self.latch_stuck = False                        # the latch did not drop: try again
            self._off_pulses = 0

    def _rearm_refusal(self):
        if not self.estop_ok:
            return 'E-stop loop open'
        if self.fet_c is not None and self.fet_c >= self.S.FET_REARM_C:
            return 'main-switch heatsink at %s C' % self.fet_c
        if self.bat < self.S.BAT_MIN_V:
            return 'pack reads %.1f V' % self.bat
        return ''

    # ---------------------------------------------------------------- Jetson
    def _jetson(self, now):
        S = self.S
        v33 = self.hw.read('JETSON_3V3_SENSE') == 1
        if v33:
            self._t_v33_high = now
            if not self.v33_seen:
                self.v33_seen = True
                self._t_v33_first = now
        self.v33 = v33
        up = self.hw.read('JETSON_UP')
        if up != self._up_raw:
            self._up_raw = up
            self._t_up_raw = now
        elif self.clock.since(self._t_up_raw) >= S.UP_CONFIRM_MS and self.up != (up == 1):
            self.up = up == 1
            self.event('jetson_up', up=self.up)
        if self.t_cycle is not None and self.clock.since(self.t_cycle) >= self.cycle_ms:
            self.t_cycle = None
            self.t_grace = now          # dev kit powered again: it boots like after a reboot
            self.event('jetson_power', on=True)
        if self.t_grace is not None and self.clock.since(self.t_grace) >= S.REBOOT_GRACE_MS:
            self.t_grace = None
            self.event('reboot_grace_over')
        if self.state in (HALTING, OFF) or self.t_grace is not None or self.t_cycle is not None:
            return
        if self.v33_seen and not v33 and self.clock.since(self._t_v33_high) >= S.V33_LOST_MS:
            self._halt('3v3_lost')
        elif self._hb_lost():
            # Review M4: a crashed daemon or a loose Pico cable also stops the heartbeat. While the
            # Jetson is evidently powered, ask it to shut down (power key) instead of cutting it;
            # the halt then comes from HALT or from its 3.3 V going away.
            if self.v33 or self.up:
                if self.state not in (SHUTDOWN_REQUESTED, HALTING, OFF):
                    self.event('hb_lost', v33=self.v33, up=self.up)
                    self.request_shutdown('hb_lost')
            elif not self.v33_seen:
                self._halt('hb_lost')   # no 3.3 V sense to go by and JETSON_UP low: the Jetson is off
            # else: the 3.3 V just went; the V33_LOST_MS rule above decides

    def _hb_lost(self):
        if not self.hb_seen or self.hb_timeout_ms <= 0:
            return False
        if self.t_bye is not None:
            return self.clock.since(self.t_bye) >= self.S.BYE_GRACE_MS
        return self.clock.since(self.t_hb) >= self.hb_timeout_ms

    def hb_age_s(self):
        if self.t_hb is None:
            return None
        return round(self.clock.since(self.t_hb) / 1000.0, 1)

    def link_alive(self):
        return self.t_hb is not None and self.clock.since(self.t_hb) < self.S.HB_FRESH_MS

    def _jetson_running(self):
        return self.v33 or self.up or self.link_alive()

    def _heard(self, now, msg):
        """Any command is a sign of life once heartbeats have started; only 'hb' starts them,
        so a person typing at the Pico from a laptop never arms the heartbeat timeout."""
        cmd = msg.get('cmd')
        if cmd == 'hb':
            self.t_hb = now
            self.hb_seen = True
            self.t_bye = None
            boot = msg.get('boot')
            if boot is not None and boot != self.boot_id:
                if self.boot_id is not None:
                    self.boots += 1
                    self.event('jetson_booted', boot=boot)
                    if self.t_grace is not None:
                        self.t_grace = None
                        self.event('reboot_done')
                self.boot_id = boot
        elif self.hb_seen and cmd not in ('?', 'repl'):
            self.t_hb = now

    # ---------------------------------------------------------------- battery and BMS
    def _battery(self, now):
        S = self.S
        if self.state in (INIT, HALTING, OFF, SHUTDOWN_REQUESTED):
            self._t_low = self._t_cut = None
            return
        v = self.bat_avg
        hist = self._bat_hist
        if not hist or self.clock.since(hist[-1][0]) >= S.BAT_RISING_MS // 2:
            hist.append((now, v))
            if len(hist) > 3:
                hist.pop(0)
        # Review m7: a charger does not mean the pack is gaining (the car can draw more than the
        # 42 W charger gives). Pause the low-pack checks only while the pack is actually rising,
        # or for the first BAT_RISING_MS until there is enough history to tell.
        if self.chg and (len(hist) < 3 or v - hist[0][1] > S.BAT_RISING_V):
            self._t_low = self._t_cut = None
            return
        if v < S.BAT_LOW_V:
            if self._t_low is None:
                self._t_low = now
            elif not self.low_warned and self.clock.since(self._t_low) >= S.BAT_LOW_MS:
                self.low_warned = True
                self.event('low_battery', level='warn', v=round(v, 2))
        else:
            self._t_low = None
            if v > S.BAT_LOW_V + 0.3:
                self.low_warned = False
        if v < S.BAT_CUT_V:
            if self._t_cut is None:
                self._t_cut = now
            elif self.clock.since(self._t_cut) >= S.BAT_CUT_MS:
                self._t_cut = None
                self.event('low_battery', level='shutdown', v=round(v, 2))
                self.request_shutdown('low_battery')
        else:
            self._t_cut = None

    def _bms_watch(self):
        if self.bms is None:
            return
        online = self.bms.online()
        if online != self._bms_online:
            self._bms_online = online
            self.event('bms', online=online)
        b = self.bms.basic
        prot = b['prot'] if b is not None else 0
        if online and prot != self._bms_prot:
            self._bms_prot = prot
            self.event('bms', prot=prot)

    # ---------------------------------------------------------------- states
    def _enter(self, state, why=''):
        old = self.state
        self.state = state
        self.why = why
        self.t_state = self.clock.now()
        self.event('state', to=state, why=why, was=old)

    def _lockout(self, why):
        self._enter(LOCKOUT, why)

    def _fault(self, why):
        self._enter(FAULT, why)

    def _start_precharge(self, why):
        self.attempt = 0
        self._enter(PRECHARGE, why)
        self._begin_attempt()

    def _begin_attempt(self):
        self.attempt += 1
        self.t_phase = self.clock.now()
        if self.bat < self.S.BAT_MIN_V:
            self._attempt_failed('bat_sense')
            return
        self.phase = 'charging'
        self.event('precharge', attempt=self.attempt, bat=round(self.bat, 2))

    def tau_ms(self):
        return self.S.PRECHARGE_R_OHM * self.S.VM_CAP_UF / 1000.0

    def short_threshold_v(self):
        S = self.S
        expected = self.bat * (1.0 - math.exp(-S.PRECHARGE_SHORT_CHECK_MS / self.tau_ms()))
        return min(S.PRECHARGE_SHORT_V, S.PRECHARGE_SHORT_FRACTION * expected)

    def precharge_timeout_ms(self):
        S = self.S
        return int(S.PRECHARGE_TAUS * self.tau_ms())

    def _precharged(self, target):
        """90 % of the pack, or (review M3) within PRECHARGE_SETTLED_MARGIN_V of it and no longer
        rising, which is where a bus with the ESC and the servo BEC drawing current settles."""
        S = self.S
        if self.vm >= target:
            return True
        return (self.vm >= self.bat - S.PRECHARGE_SETTLED_MARGIN_V and self.dv10 is not None
                and self.dv10 < S.PRECHARGE_SETTLED_DV)

    def _attempt_failed(self, why):
        self.last_fail = why
        self.event('precharge_failed', why=why, attempt=self.attempt, vm=round(self.vm, 2))
        if self.attempt >= self.S.PRECHARGE_TRIES:
            self.phase = ''
            self._fault(why)
        else:
            self.phase = 'gap'
            self.t_phase = self.clock.now()

    def _precharge(self, now):
        S = self.S
        el = self.clock.since(self.t_phase)
        target = S.PRECHARGE_DONE_RATIO * self.bat
        if self.phase == 'charging':
            if el >= S.PRECHARGE_SHORT_CHECK_MS and self.vm < self.short_threshold_v():
                self._attempt_failed('short')
            elif self.bat >= S.BAT_MIN_V and self._precharged(target):
                self.precharge_ms = el
                self.phase = 'overlap'
                self.t_phase = now
            elif el >= self.precharge_timeout_ms():
                self._attempt_failed('slow')
        elif self.phase == 'overlap':
            if el >= S.PRECHARGE_OVERLAP_MS:
                self.phase = 'verify'
                self.t_phase = now
        elif self.phase == 'verify':
            if self.vm < target:
                self.phase = ''
                self._fault('main_switch')
            elif el >= S.MAIN_VERIFY_MS:
                self.phase = ''
                self._enter(RUN, 'precharged in %d ms' % self.precharge_ms)
        elif self.phase == 'gap':
            if el >= S.PRECHARGE_RETRY_GAP_MS:
                self._begin_attempt()

    def _hot(self, now):
        S = self.S
        if self.fet_c is not None and self.fet_c > S.FET_HOT_C:
            if self._t_hot is None:
                self._t_hot = now
            elif self.clock.since(self._t_hot) >= S.FET_HOT_MS:
                self._t_hot = None
                self._lockout('fet_hot')
                return True
        else:
            self._t_hot = None
        return False

    def _step_state(self, now):
        S = self.S
        s = self.state
        if s == INIT:
            if self.clock.since(self.t_state) >= S.INIT_MS:
                if not self.cold_start:
                    self._lockout('restart')
                elif not self.estop_ok:
                    self._lockout('estop')
                else:
                    self._start_precharge('power-on')
        elif s == PRECHARGE:
            if not self._hot(now):
                self._precharge(now)
        elif s == RUN:
            if self._hot(now):
                return
            if self.vm < S.BUS_LOST_RATIO * self.bat:
                if self._t_bus_low is None:
                    self._t_bus_low = now
                elif self.clock.since(self._t_bus_low) >= S.BUS_LOST_MS:
                    self._t_bus_low = None
                    self._lockout('bus_lost')
            else:
                self._t_bus_low = None
        elif s == SHUTDOWN_REQUESTED:
            self._shutdown_wait(now)
        elif s == HALTING:
            if self.clock.since(self.t_state) >= S.HALT_TO_OFF_MS:
                self._force_off(self.why)
        elif s == OFF:
            self._off(now)

    def _off(self, now):
        """LATCH_OFF pulses until the pack bus (VSYS_SW) goes away, but never while the button is
        held, because the button drives the Pololu's ON input (review M5), and at most
        OFF_MAX_PULSES (review m8). A Pico that keeps running on USB power after the latch dropped
        restarts when the pack bus comes back, that is, when someone switches the car on again."""
        S = self.S
        if self._bat_gone:
            if self.bat >= S.BAT_BACK_V:
                if self._t_bat_back is None:
                    self._t_bat_back = now
                elif self.clock.since(self._t_bat_back) >= S.BAT_BACK_MS and not self.reset_requested:
                    self.reset_requested = True
                    self.event('power_returned', bat=round(self.bat, 2))
            else:
                self._t_bat_back = None
            return
        if self.bat < S.BAT_GONE_V:
            self._bat_gone = True
            self.event('latch_off', pulses=self._off_pulses)
            return
        if self.button_held():
            return
        if self._off_pulses >= S.OFF_MAX_PULSES:
            if not self.latch_stuck:
                self.latch_stuck = True
                self.event('latch_stuck', pulses=self._off_pulses)
            return
        if self._t_off_pulse is None or self.clock.since(self._t_off_pulse) >= S.OFF_RETRY_MS:
            self._t_off_pulse = now
            self._off_pulses += 1
            self.hw.pulse('LATCH_OFF', S.LATCH_OFF_PULSE_MS)

    def button_held(self):
        return self._btn_raw == 0 or self._btn_stable == 0

    # ---------------------------------------------------------------- shutdown and halt
    def request_shutdown(self, why):
        """Ask the Jetson to shut down (power key), then wait for its halt. False if a shutdown
        is already under way."""
        if self.state in (SHUTDOWN_REQUESTED, HALTING, OFF):
            return False
        now = self.clock.now()
        self.phase = ''
        self._enter(SHUTDOWN_REQUESTED, why)
        self.t_shutdown = now
        self.presses = 0
        self.shutdown_force = why != 'hb_lost'
        self._age_at_shutdown = self.clock.since(self._t_v33_first) if self._t_v33_first is not None else 0
        if self._jetson_running():
            self._press_key(now)
        else:
            self._halt('jetson_off')
        return True

    def _press_key(self, now):
        self.hw.pulse('JETSON_PWR_KEY', self.S.PWR_KEY_PULSE_MS)
        self.presses += 1
        self.t_press = now
        self.event('power_key', n=self.presses)

    def _bye_since_shutdown(self):
        if self.t_bye is None or self.t_shutdown is None:
            return False
        return self.clock.since(self.t_bye) <= self.clock.since(self.t_shutdown)

    def _may_repress(self):
        """Review F6: a press on a Jetson that is already halting can switch it back on. So
        press again only while it is evidently still up and has not said it is going down."""
        if self._bye_since_shutdown():
            return False
        if self.why == 'hb_lost':
            return self.v33 or self.up     # review M4: no heartbeat to judge by; press while it is powered
        if not self.v33:
            return False
        if self.hb_seen:
            return self.link_alive()
        return self._age_at_shutdown < self.S.BOOTING_MS

    def _shutdown_wait(self, now):
        S = self.S
        waited = self.clock.since(self.t_shutdown)
        if self.shutdown_force:
            limit = S.SHUTDOWN_WAIT_ACK_MS if self._bye_since_shutdown() else S.SHUTDOWN_WAIT_MS
            if waited >= limit:
                self._halt('shutdown_timeout')
                return
        if (waited < S.SHUTDOWN_WAIT_MS and self.clock.since(self.t_press) >= S.REPRESS_MS
                and self._may_repress()):
            self._press_key(now)

    def _halt(self, why):
        if self.state in (HALTING, OFF):
            return
        self.phase = ''
        self._enter(HALTING, why)

    def _force_off(self, why):
        """OFF: motor bus, lidar and the dev kit's feed off at once; LATCH_OFF follows in _off()."""
        self.phase = ''
        self._enter(OFF, why)
        self._t_off_pulse = None
        self._off_pulses = 0
        self._off(self.clock.now())

    def _reboot(self, hard, now):
        if hard:
            self.hw.pulse('JETSON_RESET', self.S.RESET_PULSE_MS)
        self.t_grace = now
        self.event('reboot', hard=hard)

    # ---------------------------------------------------------------- outputs
    def _fan(self):
        S = self.S
        if self.fan_manual is not None:
            return self.fan_manual
        t = self.fet_c
        if t is None:
            return S.FAN_NO_SENSOR
        if t <= S.FAN_LOW_C:
            return S.FAN_MIN
        if t >= S.FAN_HIGH_C:
            return 100
        return int(S.FAN_MIN + (100 - S.FAN_MIN) * (t - S.FAN_LOW_C) / (S.FAN_HIGH_C - S.FAN_LOW_C))

    def _apply_outputs(self, now):
        """Every output that follows the state is written here on every tick, from the state
        alone, so no earlier decision can leave a stale enable behind (review F4)."""
        hw = self.hw
        s = self.state
        ok = self.estop_ok
        main = ok and (s == RUN or (s == PRECHARGE and self.phase in ('overlap', 'verify')))
        pre = ok and s == PRECHARGE and self.phase in ('charging', 'overlap')
        hw.write('MAIN_EN', main)
        hw.write('PRECHARGE_EN', pre)
        hw.write('VESC_KILL', ok and s == RUN)              # 1 = run, 0 = kill (ADC2 low)
        hw.write('LIDAR_EN', self.lidar_on and s not in (HALTING, OFF))
        # Signals into the Jetson's 40-pin header only while its 3.3 V rail is up (no back-powering)
        hw.write('ESTOP_OK_TO_JETSON', self.v33 and ok)
        hw.write('CHG_STAT_N_TO_JETSON', self.v33 and not self.chg)
        hw.write('DEVKIT_PWR', self.t_cycle is None and s != OFF)     # 1 = dev kit powered
        duty = self._fan()
        if duty != self.fan_duty:
            self.fan_duty = duty
            hw.fan(duty)

    def _set_lidar(self, on, source):
        if on != self.lidar_on:
            self.lidar_on = on
            self.event('lidar', on=on, source=source)

    # ================================================================ events and status
    def event(self, name, **fields):
        e = {'t': 'evt', 'evt': name, 'ms': self.clock.since(self.t_start)}
        for k in fields:
            e[k] = fields[k]
        self.events.append(e)
        self.history.append(e)
        if len(self.history) > self.S.HISTORY:
            self.history.pop(0)

    def take_events(self):
        out = self.events
        self.events = []
        return out

    def status(self):
        grace = 0
        if self.t_grace is not None:
            grace = max(0, (self.S.REBOOT_GRACE_MS - self.clock.since(self.t_grace)) // 1000)
        st = {
            't': 'status', 'fw': FW_VERSION, 'proto': PROTOCOL,
            'ms': self.clock.since(self.t_start),
            'state': self.state, 'why': self.why,
            'bat': round(self.bat_avg if self.bat_avg is not None else self.bat, 2),
            'vm': round(self.vm, 2),
            'fet_c': self.fet_c,
            'estop': self.estop_ok, 'estops': self.estops,
            'main': self.hw.read('MAIN_EN') == 1,
            'kill': self.hw.read('VESC_KILL') == 0,
            'chg': self.chg,
            'lidar': self.lidar_on and self.state not in (HALTING, OFF),
            'fan': self.fan_duty, 'fan_auto': self.fan_manual is None,
            'low': self.low_warned,
            'pre_ms': self.precharge_ms,
            'jet': {'v33': self.v33, 'up': self.up, 'hb': self.hb_age_s(), 'bye': self.t_bye is not None,
                    'grace': grace, 'boot': self.boot_id, 'boots': self.boots, 'presses': self.presses,
                    'hb_timeout': self.hb_timeout_ms // 1000, 'power': self.t_cycle is None},
        }
        if self.state == PRECHARGE:
            st['phase'] = self.phase
            st['attempt'] = self.attempt
        if self.last_fail:
            st['last_fail'] = self.last_fail
        if self.bms is not None:
            st['bms'] = self.bms.summary()
        return st

    # ================================================================ commands
    def _ack(self, cmd, mid, **fields):
        r = {'t': 'ack', 'cmd': cmd}
        if mid is not None:
            r['id'] = mid
        for k in fields:
            r[k] = fields[k]
        return r

    def _err(self, cmd, mid, msg):
        r = {'t': 'err', 'cmd': cmd, 'msg': msg}
        if mid is not None:
            r['id'] = mid
        return r

    def command(self, msg):
        """Handle one message from the Jetson; returns the reply (or None for a heartbeat)."""
        cmd = msg.get('cmd')
        mid = msg.get('id')
        now = self.clock.now()
        self._heard(now, msg)
        if cmd == 'hb':
            return None
        if cmd == 'status':
            st = self.status()
            if mid is not None:
                st['id'] = mid
            return st
        if cmd == 'lidar':
            on = msg.get('on')
            if not isinstance(on, bool):
                return self._err(cmd, mid, 'lidar needs "on": true or false')
            self._set_lidar(on, 'command')
            return self._ack(cmd, mid, on=on)
        if cmd == 'shutdown':
            started = self.request_shutdown('jetson')
            return self._ack(cmd, mid, state=self.state, started=started)
        if cmd == 'reboot':
            hard = msg.get('hard') is True
            self._reboot(hard, now)
            return self._ack(cmd, mid, hard=hard, grace_s=self.S.REBOOT_GRACE_MS // 1000)
        if cmd == 'halt':
            verb = msg.get('verb', 'poweroff')
            if verb in ('reboot', 'kexec') and self.state != SHUTDOWN_REQUESTED:
                self._reboot(False, now)
            else:
                self._halt('halt_' + str(verb))
            return self._ack(cmd, mid, verb=verb, state=self.state)
        if cmd == 'bye':
            self.t_bye = now
            return self._ack(cmd, mid, grace_s=self.S.BYE_GRACE_MS // 1000)
        if cmd == 'bms_fets':
            return self._bms_fets(msg, mid)
        if cmd == 'fan':
            if msg.get('auto') is True:
                self.fan_manual = None
            else:
                duty = msg.get('duty')
                if not _num(duty) or not 0 <= duty <= 100:
                    return self._err(cmd, mid, 'fan needs "duty": 0-100 or "auto": true')
                self.fan_manual = int(duty)
            return self._ack(cmd, mid, duty=self._fan(), auto=self.fan_manual is None)
        if cmd == 'hb_timeout':
            s = msg.get('s')
            if not _num(s) or s < 0:
                return self._err(cmd, mid, 'hb_timeout needs "s": seconds (0 = never)')
            self.hb_timeout_ms = int(s * 1000)
            self.event('hb_timeout', s=s)
            return self._ack(cmd, mid, s=s)
        if cmd == 'jetson_power_cycle':
            off_s = msg.get('off_s', self.S.JETSON_CYCLE_OFF_MS / 1000.0)
            if not _num(off_s) or not 1 <= off_s <= self.S.JETSON_CYCLE_MAX_S:
                return self._err(cmd, mid, '"off_s" must be 1-%d seconds' % self.S.JETSON_CYCLE_MAX_S)
            if self.state in (HALTING, OFF):
                return self._err(cmd, mid, 'the car is switching off')
            self.t_cycle = now
            self.cycle_ms = int(off_s * 1000)
            self.event('jetson_power', on=False, off_s=off_s)
            return self._ack(cmd, mid, off_s=off_s,
                             msg='hard power cycle: the Jetson loses power without shutting down')
        if cmd == 'log':
            return self._ack(cmd, mid, events=list(self.history))
        if cmd == 'version':
            return self._ack(cmd, mid, fw=FW_VERSION, proto=PROTOCOL)
        if cmd == 'help':
            return self._ack(cmd, mid, commands=list(COMMANDS))
        if cmd == 'repl':
            self.repl_requested = True
            return self._ack(cmd, mid, via=msg.get('via', 'command'),
                             msg='supervisor stopping: motor off, Jetson stays on; Ctrl-D restarts it')
        return self._err(str(cmd), mid, 'unknown command (send "help")')

    def _bms_fets(self, msg, mid):
        cmd = 'bms_fets'
        if self.bms is None or not self.bms.online():
            return self._err(cmd, mid, 'the BMS is not answering')
        chg = msg.get('charge', True)
        dsg = msg.get('discharge', True)
        if not isinstance(chg, bool) or not isinstance(dsg, bool):
            return self._err(cmd, mid, '"charge" and "discharge" must be true or false')
        if not dsg and msg.get('force') is not True:
            return self._err(cmd, mid, 'discharge off cuts power to the whole car, the Pico and the '
                                       'Jetson included; add "force": true if that is what you want')
        self.bms.set_fets(chg, dsg)
        self.event('bms_fets', charge=chg, discharge=dsg)
        return self._ack(cmd, mid, charge=chg, discharge=dsg, queued=True)

    # ================================================================ leaving for the REPL
    def make_safe(self):
        """Motor bus off, VESC killed, no key presses; the lidar and the Jetson stay as they are."""
        hw = self.hw
        hw.write('MAIN_EN', 0)
        hw.write('PRECHARGE_EN', 0)
        hw.write('VESC_KILL', 0)
        hw.write('JETSON_PWR_KEY', 0)
        hw.write('JETSON_RESET', 0)
        hw.write('LATCH_OFF', 0)
