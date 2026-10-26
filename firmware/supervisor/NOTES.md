# Supervisor firmware: judgment calls, unverified items, open questions

Written Oct 24, 2026 with the first version (fw 0.1.0, protocol 1), and revised the same day for
the independent review (docs/review_revb_2026-10-24.md: M3, M4, M5, m7, m8, m16). The main
session and the reviewer read this; README.md is the user guide.

## Changes for the Oct 24 review

| Finding | Fix | Tests (tests/test_sequencer.py unless noted) |
| --- | --- | --- |
| M3 precharge never finishes with 150-200 mA on VM | "Charged" is 90 % of the pack, or within 2.5 V of it and rising less than 0.1 V per 10 ms; the 5 tau timeout stays. sim.SimHardware takes `vm_load_a` | `test_precharge_with_esc_and_bec_loading_the_bus` (12.0-16.8 V x 50-200 mA, 10.6 ohm), `test_settled_bus_too_far_below_the_pack_still_fails` |
| M4 a lost heartbeat hard-cuts a running Jetson | With J12 3.3 V or JETSON_UP high: SHUTDOWN_REQUESTED (`hb_lost`), power key every 10 s for 60 s, no forced cut; halt only on HALT or the 3.3 V going. With both low and no working 3.3 V sense: halt as before | `test_heartbeat_lost_with_the_jetson_up_asks_it_to_shut_down`, `..._then_halt_frame`, `..._with_the_jetson_down_halts`, `test_bye_gives_a_longer_grace` |
| M5 the 5 s press pulses LATCH_OFF with the button still held | At 5 s: OFF, with MAIN, precharge, lidar and DEVKIT_PWR off and both LEDs lit; LATCH_OFF only once the button is released (in OFF from any path) | `test_long_press_cuts_at_5s_and_releases_the_latch_after_the_button`, `test_halting_while_the_button_is_held_waits_for_release`, test_leds.py `test_off_lights_both_while_held_then_goes_dark` |
| m7 low-pack checks off while charging | Active while charging; paused only while the pack rises by more than 0.05 V per 10 s (and for the first 10 s, until there is history) | `test_low_battery_cut_stays_active_while_charging`, `test_low_battery_checks_pause_while_the_charger_raises_the_pack` |
| m8 OFF pulses LATCH_OFF forever | Pulses stop when VSYS_SW (BAT_SENSE) is gone or after 20; a Pico still running on USB power restarts when it comes back, with `coldstart.flag` so it starts as after a power-on | `test_off_stops_pulsing_once_the_latch_has_dropped_and_restarts_when_power_returns`, `test_off_gives_up_after_max_pulses_and_a_click_retries` |
| m16 a press in LOCKOUT with the loop open shuts down | Refused and logged (`rearm_refused`, "E-stop loop open") | `test_press_with_loop_still_open_is_ignored` |

The reviewer's scenario script (scratchpad review_revb/sim_checks.py) now reports RUN for all 16
precharge cases, SHUTDOWN_REQUESTED with no LATCH_OFF after a lost heartbeat, no LATCH_OFF while
the button is held, and a low-battery shutdown while charging.

## Judgment calls

1. **Short-circuit check scales with R x C.** The rev B spec keeps rev A's "under 4 V after
   10 ms = short". With the FSESC's unknown capacitance that misfires: a healthy 2.5 mF bus on a
   12.0 V pack reads 3.96 V at 10 ms (tau 25 ms). The firmware uses the lower of 4 V and half of
   what R x C predicts at 10 ms. With the assumed 2 mF and a 16 V pack the threshold is 3.15 V; a
   dead short still reads near 0 V. Test: `test_healthy_bus_on_a_low_pack_is_not_a_short`.
2. **Precharge retry gap 2 s** instead of rev A's 15 s. Rev A's gap protected two 2512 chip
   resistors; rev B has one 10 ohm 5 W wirewound, and a try on a dead short is stopped at 10 ms
   (about 0.3 J at 16.8 V). Check the chosen resistor's pulse curve.
3. **Main-switch check after closing** (new): VM must stay at 90 % of the pack for 300 ms after
   MAIN_EN, or FAULT `main_switch`. It catches a MIC5014 or FET that does not turn on, which
   would otherwise leave the VESC running from the precharge resistor.
4. **Outputs are a function of the state**, rewritten every 10 ms tick (MAIN_EN, PRECHARGE_EN,
   VESC_KILL, LIDAR_EN, the two J12 mirrors). This removes the class of bug in review F4.
5. **E-stop interrupt.** A hard IRQ on the falling edge of ESTOP_OK drops MAIN_EN, PRECHARGE_EN
   and VESC_KILL at once. Without it, a loop that opens and closes within one 10 ms tick would let
   the 74HC08 re-close the main switch onto a partly drained bus. Even a glitch the main loop never
   sees latches LOCKOUT.
6. **Main switch off at the start of a shutdown request**, together with VESC_KILL. Rev A kept
   the bus up (with the gate driver disabled) until the end. Nothing needs VM while the Jetson
   shuts down.
7. **Button semantics.** A click acts on release (so a 5 s hold can mean "force off" without
   first triggering a click). In LOCKOUT a click re-arms if it can and otherwise does nothing but
   log `rearm_refused` (review m16); in FAULT it shuts down. FAULT is left only by a power cycle (or a Pico restart,
   which lands in LOCKOUT). No Jetson command can re-arm the motor bus: only a person at the car.
8. **Restart = LOCKOUT.** After a watchdog reset, `machine.reset()`, a crash or a REPL session the
   supervisor does not precharge on its own; it waits for a button press.
9. **Heartbeat rules.** Only `hb` arms the 60 s timeout, so a person typing at the Pico from a
   laptop never starts it. `bye` (sent by atlas-battery.service when it stops) stretches it to
   120 s and stops further power-key presses (review F6). `hb_timeout 0` turns it off until the
   next start, for bench work. When the timeout runs out and the Jetson is still powered, the
   supervisor asks it to shut down instead of cutting it (review M4): presses every 10 s for 60 s,
   then it waits for HALT or the 3.3 V to go, with no forced cut. Trade-off: a Jetson that is hung
   for good leaves the car on with the motor bus off until someone holds the button 5 s (or uses
   `jetson_power_cycle`), and the repeated presses risk the review-F6 case (a press landing at
   the very end of a shutdown can start the Jetson again); JETSON_UP falling when the daemon stops
   usually ends the presses before that.
10. **Reboot grace** of 240 s after `reboot` or `halt reboot`, ended early by a heartbeat carrying a
    new boot id (the Jetson's `/proc/sys/kernel/random/boot_id`). If the Jetson never comes back,
    the normal rules apply when the grace ends: with its 3.3 V gone, the car switches off.
11. **JETSON_UP is not a halt trigger.** It is held by atlas-battery.service, so it can fall when
    that service stops, early in a shutdown and well before the file systems are synced. The
    supervisor uses it as "the Jetson is up" only (and, after a lost heartbeat, as a reason to
    press the key rather than cut). The halt triggers are the HALT frame and J12 3.3 V gone for
    2 s; a lost heartbeat halts only when neither line says the Jetson is powered.
12. **Shutdown wait** is 60 s (rev B spec), or 120 s once the Jetson has said `bye`, because a
    stuck unit can hold a systemd shutdown for 90 s. It ends in a forced off only for a shutdown a
    person or the pack asked for (button, `shutdown`, low pack), not for a lost heartbeat.
13. **Low battery.** 12.0 V for 30 s warns; 11.6 V for 10 s shuts down cleanly (the 10 s is mine,
    to ride through motor sag; the pack voltage is also averaged over about 2 s). With a charger
    in, both pause only while the pack is rising (review m7: at 25 W plus lidar and camera the car
    can draw more than the 42 W charger gives). Note: with the BMS's planned 3.00 V cell undervoltage, a balanced
    pack is cut by the BMS at 12.0 V, so the 11.6 V step only matters under load sag or with
    unbalanced cells. The Jetson's own 3.30 V per cell rule (13.2 V, I x R corrected) normally
    shuts down first. Consider 12.8 V / 12.4 V here.
14. **Heatsink re-arm hysteresis** 70 C (trip at 90 C). An open NTC (not fitted) reads as "no
    sensor" and the fan runs at 100 %; a shorted one reads 200 C and keeps the main switch off.
15. **LIDAR_REQ is edge-triggered**, and the last change wins between it and the USB `lidar`
    command, so the two paths cannot fight. On a restart under a running Jetson the supervisor
    takes LIDAR_REQ's level as the lidar state.
16. **`bms_fets` discharge-off needs `"force": true`**: opening the BMS discharge FETs kills the
    Pico and the Jetson too, and the car may not wake until the BMS is reset.
17. **No `os.dupterm`.** It cannot detach the REPL from the RP2040's built-in USB CDC (it only adds
    a terminal; see README). `main.py` owns the port instead, with `kbd_intr(-1)`; Ctrl-C bytes,
    the `repl` command and a 3 s button hold at start-up lead back to the REPL, always with the
    motor bus made safe first. Connecting Thonny or mpremote therefore stops the supervisor.
18. **Fan PWM inverted by default** (`pins.FAN_PWM_INVERT = True`): with the 2N7000 pulling the
    fan's PWM wire low, a dead Pico leaves the fan at full speed.
19. **No boot-time power-key press.** The dev kit's auto power-on stays enabled, so the
    supervisor only ever presses the key to shut the Jetson down (rev A pressed it at boot too).
20. **Pin map follows the board design draft.** boards/power/design.py (Oct 24 draft) moved GP15
    to CHG_PRESENT_N (open collector, low = charger) and GP22 to DEVKIT_PWR (an output that cuts
    the dev kit's DC feed). PINMAP.md did not exist yet, so pins.py follows design.py, and
    tests/test_pins.py checks pins.py against design.py's Pico nets (passing) and against
    PINMAP.md once it exists. The divider (100 k / 18 k) and NTC (NTCLE100E3103JB0, B 3977 K)
    values also come from design.py.
21. **DEVKIT_PWR** stays high (dev kit powered) in every state except OFF, where it goes low with
    the main switch and the lidar (review M5: a 5 s press cuts them at once; after a normal halt
    the Jetson is already off). The `jetson_power_cycle` command also drops it (a hard power cut
    for a hung Jetson, 10 s by default, then the reboot grace).

22. **Moving the Pico's cable off the Jetson on a running car** stops the heartbeats with no
    "bye", so 60 s later the supervisor presses the power key and the Jetson shuts down, unless
    someone sends `hb_timeout 0`. The firmware cannot tell a vanished Jetson from a moved cable
    (MicroPython has no portable call for the CDC host's DTR state), so this is documented.
23. **OFF and the latch** (reviews M5, m8). LATCH_OFF pulses only with the button released (the
    button drives the Pololu ON input), stop once VSYS_SW has gone or after 20 pulses (10 s), and a
    short press in OFF tries again if the latch did not drop. A Pico kept alive by USB from a
    laptop restarts when VSYS_SW comes back for 200 ms, and the `coldstart.flag` file makes that
    start precharge as after a power-on: the person who switched the car on should not need a
    second press.
24. **Precharge margin** (review M3). With 150-200 mA on VM the simulated bus finishes in
    80-90 ms against the 100 ms (5 tau) timeout. The timeout was kept as asked; if the bench shows
    the FSESC has more than 2 mF, raise `VM_CAP_UF` from `pre_ms`.

## Unverified

- MicroPython itself: nothing has run on a Pico. Specific APIs relied on: `Pin(..., value=)`
  setting the level before the direction (checked in ports/rp2/machine_pin.c), hard IRQs and
  hard one-shot timers (machine_timer.c has `hard`), `UART(invert=)`, `select.poll` on
  `sys.stdin`, `machine.reset_cause()`, `micropython.kbd_intr`, `machine.mem32`.
- JBD frames: from the V4 protocol document and esphome-jbd-bms, not captured from the team's BMS.
  The UART is through two PC817s whose polarity depends on the board.
- The Pico's USB IDs 2e8a:0005 (MicroPython rp2 port default).
- The FSESC's input capacitance (2 mF assumed) and therefore the precharge timeout.
- The dividers and NTC as drawn in design.py's draft; the BMS opto stages (non-inverting) and the
  fan stage (inverting) as drawn there.
- The Pololu #2813 turning off on an OFF pulse after the button is released (never tried).
- JETSON_3V3_SENSE: that J12's 3.3 V falls when the module powers off (the dev-kit study rates
  this "likely, verify"). Since review M4 this matters more: without it, a Jetson that halts
  without sending HALT leaves the car on (motor bus off) until a 5 s press.
- RAM use on the Pico: about 1,700 lines of source in the six files; if the heap gets tight,
  precompile with `mpy-cross` (no change to the code).

## Open questions

1. `boards/power/PINMAP.md` now exists and records the GP15 and GP22 changes; pins.py matches it
   and design.py's Pico nets (`tests/test_pins.py`). Re-run that test when the design agent's
   `boards/power/DESIGN_FIXED.md` appears (it was not there on Oct 24 when these fixes were made).
2. Should the E-stop give the VESC a braked stop before the bus cut (a 200 ms RC on the MIC5014
   input, the ESC study's suggestion)? The rev B spec says cut at once, so the firmware just
   follows the hardware.
3. Should a hung Jetson (3.3 V present, no heartbeat, the power key ignored for 60 s) get an
   automatic SYS_RESET* pulse or `jetson_power_cycle`? Since review M4 it waits for a person (5 s
   press, or `reboot hard` / `jetson_power_cycle` from a laptop).
4. Should the low-battery thresholds move up (judgment call 13)?
5. Resolved: DEVKIT_PWR's pull-up is now 10 k (about 2.7 V against the RP2040's reset
   pull-downs), so the dev kit stays on through a Pico reset.
