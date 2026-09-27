# Simulations

Checks run on the finished schematics, before anything is ordered. Each one is a short script; `run_all.sh`
runs them all (ngspice and Python with numpy, scipy and matplotlib) and writes the plots and a JSON file per
check to `out/`. Two of them changed the design; the changes are listed at the end.

| script | question | answer |
| --- | --- | --- |
| `dclink.py` | How much ripple current do the ESC's bus capacitors carry? | 3.5 A per capacitor at 30 A peak phase current, 7.6 A at 70 A, 10 A at 100 A. The 12 ceramics take 8-27 A between them, the battery leads about 2 A. |
| `precharge.py` | Does the precharge resistor survive switching the car on? | One 10 Ohm 2512 resistor took 0.29 J in about 10 ms, about 1.5 times its single-pulse rating. Two pulse-proof 22 Ohm resistors in parallel take 0.15 J each, inside theirs. |
| `poe_boost.py` | Is the camera's 52 V supply comfortable at full load? | Inductor peak 0.75 A with the camera (5 W) and 1.6 A at 15 W, against 4.2 A saturation and about 2.4 A current limit. 52 V ripple 80 mV at 5 W, 250 mV at 15 W. |
| `drive_thermal.py` | How hot does the drive board get? | At 70 A peak phase current with the fan: about 58 C on the hottest FET at 35 C air; 70 C at 100 A. Without the fan, 91 C at 70 A. |

## What the numbers rest on

- **Bus ripple (`dclink.py`).** Three ideal half-bridges switch at 30 kHz with sine-triangle PWM, modulation
  0.8, into a motor modelled as 10 mOhm + 20 uH per phase with a sinusoidal back-EMF at 400 Hz. The
  Puller Pro's phase resistance and inductance are not published; 20 uH is typical for a 540-size motor
  and mostly sets the switching ripple in the phase current, not the capacitor current. Capacitors:
  Panasonic EEH-ZU1V331P (330 uF, 11 mOhm, rated 4.8 A rms at 100 kHz and 125 C), twelve Murata
  GRM32ER71H106KA12L (10 uF 50 V X7R, about 6 uF each left at 14 V). Pack 24 mOhm with 150 nH of leads.
- **Precharge (`precharge.py`).** Full pack (16.8 V), 1.4 mF on the bus, and the servo supply switching on
  above 9 V and drawing 0.3 A, which holds the bus about 3 V below the pack until the main FETs close.
  The pulse rating comes from the single-pulse diagrams of the Vishay CRCW-HP series (about 100 W for 1 ms,
  20 W for 10 ms, 2 W for 100 ms, 2512 size) and of IRC's PWC series for a standard part (about half).
- **Boost (`poe_boost.py`).** The power stage only, at the duty cycle that holds 52 V: 47 uH Coilcraft
  XAL7070-473 (84 mOhm), CSD19538Q3A (60 mOhm taken hot), Vishay SS2H10, 3 x 2.2 uF 100 V ceramics (about
  0.9 uF each at 52 V) and a 22 uF aluminium can. The LM5155's loop is not simulated: its datasheet does not
  publish the internal gains a switching model would need. The compensation follows TI's design
  procedure (crossover about 5 kHz). Switching losses are left out, so the efficiency figure in the JSON
  file counts conduction losses only.
- **Temperature (`drive_thermal.py`).** A 0.5 mm grid over the 140 x 90 mm board: in-plane conduction from
  six 2 oz copper layers (90 % copper under the power stage, 50 % elsewhere) and FR4, both faces cooled by
  the side-pod fan's air (h = 25 W/m2K; 8 W/m2K for still air), and the aluminium spreader under the power
  stage coupled through the thermal pad and the FET package tops (taken as 20 C/W). Losses at the chosen
  operating point: FET conduction from the switch RMS currents with 1.2 mOhm hot, switching from
  56 ns edges (2 x 28 nC Qgd at 1 A gate drive), dead-time diode loss, the battery-path FETs and shunts,
  and about 2 W for the rest of the board. 70 A peak phase current is about 33 A from the pack.

These are estimates to find weak spots before building. The bench checks in `docs/ARCHITECTURE.md` (FET
and capacitor temperatures at 50 A and 70 A) still stand.

## Design changes they led to

1. **Precharge resistor.** R319 was one 10 Ohm 2512. It is now R319 + R320, two 22 Ohm Vishay CRCW2512-HP
   pulse-proof resistors in parallel, R320 directly under R319 on the bottom. The STM32 firmware also gives
   up on a precharge whose bus is still under 4 V after 10 ms (a short on the motor bus), because the
   resistors are rated for the charging pulse, not for 13 W each for as long as the old 1 s timeout
   (`firmware/vesc/hw_atlas_drv1.c`).
2. **Bus capacitors.** The 470 uF 35 V part turned out to be 16.8 mm tall, which would hit the brain
   board's NVMe SSD. The 330 uF 35 V part of the same series is 12.8 mm tall (2.4 mm clear of the SSD).
   The simulation shows why capacity matters less than ripple current here: at 70 A peak phase current each
   of the four capacitors carries about 7.6 A rms, above the 4.8 A rated at 125 C. That rating is set at
   the capacitor's maximum temperature; at 35-55 C board temperature they will run warm, not fail. Worth a
   thermocouple on one of them during the 70 A bench run.
