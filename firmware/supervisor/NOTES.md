# Supervisor firmware: judgment calls, unverified items, open questions

Written Oct 24, 2026 with the first version (fw 0.1.0, protocol 1). The main session and the
reviewer read this; README.md is the user guide.

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
   first triggering a click). In LOCKOUT a click re-arms if the loop is closed and shuts down if
   it is open; in FAULT it shuts down. FAULT is left only by a power cycle (or a Pico restart,
   which lands in LOCKOUT). No Jetson command can re-arm the motor bus: only a person at the car.
8. **Restart = LOCKOUT.** After a watchdog reset, `machine.reset()`, a crash or a REPL session the
   supervisor does not precharge on its own; it waits for a button press.
9. **Heartbeat rules.** Only `hb` arms the 60 s timeout, so a person typing at the Pico from a
   laptop never starts it. `bye` (sent by atlas-battery.service when it stops) stretches the wait to
   120 s and stops further power-key presses (review F6). `hb_timeout 0` turns it off until the
   next start, for bench work.
10. **Reboot grace** of 240 s after `reboot` or `halt reboot`, ended early by a heartbeat carrying a
    new boot id (the Jetson's `/proc/sys/kernel/random/boot_id`). If the Jetson never comes back,
    the normal rules apply when the grace ends and the car switches off.
11. **JETSON_UP is not a halt trigger.** It is held by atlas-battery.service, so it can fall when
    that service stops, early in a shutdown and well before the file systems are synced. The
    supervisor uses it as "the Jetson is up" only. The halt triggers are the HALT frame, J12 3.3 V
    gone for 2 s, and the heartbeat timeout.
12. **Shutdown wait** is 60 s (rev B spec), or 120 s once the Jetson has said `bye`, because a
    stuck unit can hold a systemd shutdown for 90 s.
13. **Low battery.** 12.0 V for 30 s warns; 11.6 V for 10 s shuts down cleanly (the 10 s is mine,
    to ride through motor sag; the pack voltage is also averaged over about 2 s). Both are skipped
    while a charger is present. Note: with the BMS's planned 3.00 V cell undervoltage, a balanced
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
21. **DEVKIT_PWR is only used on request.** The firmware keeps it high (dev kit powered) in every
    state, including HALTING and OFF, and drops it only for the `jetson_power_cycle` command (a
    hard power cut for a hung Jetson, 10 s by default, then the reboot grace). The rev B spec's
    rule for a missing heartbeat (switch the car off) is unchanged.

22. **Moving the Pico's cable off the Jetson on a running car** stops the heartbeats with no
    "bye", so the car switches off 60 s later unless someone sends `hb_timeout 0`. The firmware
    cannot tell a vanished Jetson from a moved cable (MicroPython has no portable call for the
    CDC host's DTR state), and the rev B spec wants the 60 s rule, so this is documented rather
    than worked around.

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
- The Pololu #2813's response to OFF pulses while ON is still held by the button.
- JETSON_3V3_SENSE: that J12's 3.3 V falls when the module powers off (the dev-kit study rates
  this "likely, verify"); if it does not, halts are caught by HALT or the heartbeat timeout.
- RAM use on the Pico: about 1,700 lines of source in the six files; if the heap gets tight,
  precompile with `mpy-cross` (no change to the code).

## Open questions

1. `boards/power/PINMAP.md` did not exist when this was written; `tests/test_pins.py` will compare
   it with `pins.py` as soon as it does. It should record the GP15 and GP22 changes that
   design.py already made (judgment call 20).
2. Should the E-stop give the VESC a braked stop before the bus cut (a 200 ms RC on the MIC5014
   input, the ESC study's suggestion)? The rev B spec says cut at once, so the firmware just
   follows the hardware.
3. Should a hung Jetson (3.3 V present, no heartbeat) get a SYS_RESET* pulse before the car is
   switched off? The rev B spec says switch off; the `reboot hard` command exists for a person to
   do it by hand.
4. Should the low-battery thresholds move up (judgment call 13)?
5. For the board designer: RP2040 pads come out of reset with their pull-downs enabled (about
   50-80 k), and they stay that way until main.py configures the pins. Against design.py's 47 k
   pull-up on DEVKIT_PWR that leaves about 1.7 V on GP22 during a Pico reset; by my estimate still
   enough to keep Q407 on (about 0.2 mA of base current), but a 10 k pull-up would remove the
   doubt. The other lines that must hold a level through a reset (MAIN_EN, PRECHARGE_EN, LIDAR_EN,
   VESC_KILL, LATCH_OFF, the key optocouplers) want low, which the internal pull-downs help.
