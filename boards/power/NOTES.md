# ATLAS-PWR-1 rev B: judgment calls and open questions (agent D)

## Judgment calls

1. **130 x 84 mm, with resistors and small capacitors as 1206 chips on the bottom.** The mech kit limits the board
   to 130 mm (at 150 the front edge and a standoff sit in the lidar plug envelope). With every part through-hole,
   the courtyards alone add up to about 11,800 mm2 on a 10,920 mm2 board; even at 150 mm the all-through-hole
   placement did not close. So the resistors and small capacitors (104 since the review) moved to 1206 (five 10 uF parts to 1210) on
   the bottom side, with KiCad's hand-solder pads (BRIEF rule 2 fallback). Every IC, transistor, diode,
   electrolytic, connector and power part stays through-hole. The two power resistors (10 Ohm 5 W precharge,
   4.7 Ohm 0.6 W R-78E filter) stay through-hole. By the same area count an all-through-hole board would need
   roughly 160 mm, or a second, stacked logic board.
2. **Parts under socketed modules.** The Pico and the CH334F hub stand on 8.5 mm sockets (Sullins PPTC, insulator
   0.335 in = 8.51 mm), so their undersides are 11 mm up. The 74HCT08 (socketed) and the two J14 PC817s sit under
   the Pico; the MCP2221A (socketed) and its MCP1700 under the hub. The modules' courtyards are drawn as their
   socket strips only, and `placer.py` got a `HOLLOW` setting for it.
3. **PD trigger off the board.** PHASE2 put the Adafruit 5807 at the Y = 0 edge. To fit 130 mm it now sits in the
   side pod at the charge window together with the CC/CV buck (which was already off the board), wired to two
   pads (PD+, and PD- on CHG_GND since the review). The charge input TVS, 10 uF, the 20 V detector, the
   reverse-block P-FET and the 5 A fuse stay on the board. The pod window for the charge port is no longer tied to the board.
4. **Camera regulator output goes straight to the camera.** The Pololu S18V20F12 sits on the tray; the board feeds
   its input (fused, two pads) and its 12 V output goes to the Triton's M8 lead. PHASE2 listed a JST-XH 2 camera
   connector at the front edge; there is none now.
5. **ESC and pack on wire pads, not XT60PW/XT90PW.** The XT90PW drawing could not be read and Amass rates it 30 A
   (UL). The pack gets a 10 AWG pigtail with an XT90 male, which mates with the XT90-S female on the pack (the
   female holds the anti-spark resistor in the probots and myfpvstore listings; one esk8.news thread says the male,
   so meter it: the half with a few ohms between two contacts of one pole goes on the pack); the FSESC leads solder
   in directly. ESC+ is at Y 42 and ESC- at Y 54, inside the ESC's own Y span, away from the inboard end of the
   rear edge, as the mech agent asked. The fan header moved to the rear edge.
6. **Right-angle power button** (C&K PTS645VL58-2 LFS) so it can be pressed through the pod window; the remote
   button header stays.
7. **VM pour on the top only, GND under it.** PHASE2 asked for BAT/VM at least 8 mm on both layers. VM is a top pour
   12-20 mm wide and the bottom under the whole power section is GND, which keeps the switching loop small and
   gives ESC- to BAT- a short return on both layers. A VM pour on the bottom would cut that return path.
8. **CC/CV set to 16.80 V, not 17.1 V.** The reverse block is a P-FET that is fully on while 20 V is present, so
   there is no diode drop to make up (PHASE2 assumed a diode).
9. **Dev-kit over-voltage cut-off** (C_jetson_mech.md asks for one below 19 V; the carrier's DC jack takes 9-20 V,
   carrier spec 3.8): a TL431 trips an IRF4905 off at 18.7 V and releases at 17.85 V, so regen with the BMS open
   or a failed charger cannot hold the dev kit above about 18.7 V for longer than a spike (the P6KE22A takes the
   fast edge). The same P-FET is the Pico's power-cycle switch
   (GP22 DEVKIT_PWR, low = off). Its pull-up is 10k (about 2.7 V on GP22 during a Pico reset).
10. **GP15 is CHG_PRESENT_N (active low, open collector)**, not a divider: the divider back-powers an unpowered Pico
    when the charger is in with the car off.
11. **Mini blade fuses** (Keystone 3568 holder + 5 A ATM fuse, USD 1.48) for the dev-kit feed and the charge path in
    place of the Littelfuse FLR ATO holder (USD 4.67): smaller and USD 6.38 cheaper per board.
12. **10 uF X7R 1210 ceramics** in place of the small electrolytics (MIC5014 supply, R-78E in and out, charge input,
    Pico VSYS). At 17 V a 50 V X7R 10 uF keeps roughly 4 uF; enough for these spots. The bulk caps on the pack,
    the servo rail and the dev-kit lead stay electrolytic.
13. **Hub ports:** port 1 dev kit (USB-A receptacle since the review), port 2 the console (under the hub, shortest
    pair), port 3 the FSESC (1x4 header), port 4 spare (1x4 header).
14. **Heatsink bar 40 x 15 x 3 mm** (was 45) so the BAT- pad fits beside it; all three tabs are drains, so they
    bolt to the bar with no insulators. The bar is live at BAT+.
15. **I2C link to J12 (330 Ohm) and the UART1 CTS strap are DNP**, as before: an unpowered Pico would clamp the dev
    kit's I2C bus, and the CTS strap is only needed if the VESC driver keeps hardware flow control (B_esc.md).
16. **Netcheck warnings left as warnings:** 0.05-0.28 mA flows into unpowered pins (Pico GP11/12/21 and the
    74HCT08 input with the board off and the Jetson or ESC on; MCP2221A URx with the laptop unplugged; the FSESC
    RX with the ESC off; the ADC clamps on a 30 V spike). All are behind 10k or 100k and below the 0.5 mA limit.
    Since the review, four more: 2.7 mA into the dev kit's J12 pins 10, 32 and 33 through their new 1k resistors
    while the dev kit is off (pin 10 from the FSESC TX; 32 and 33 only if the firmware kept driving them, which it
    does not: it drives them low while the Jetson's 3.3 V is down). The same 2.7 mA bound holds for J14 pin 3 from
    the console TX (the model does not drive that net). Allowed as warnings up to 3 mA: TXB0108-class translators
    list partial power-down (Ioff), so the real current is likely far lower; that this carrier uses them is
    unverified (the review's M1 bench test settles it).

## Open questions

1. FSESC COMM pin order (3V3, GND, TX, RX, ADC1, ADC2, PPM) is unverified: read the FSESC silkscreen before
   crimping. The crimps can be moved in the housing.
2. JBD UART port voltage (assumed 3.3-5 V on VDD) and its connector (JST-PA 2.0 on the BMS, adapter lead to
   JST-XH 4): measure before plugging in.
3. Heights to measure: the Adafruit 5997 underside (it must have no parts below its PCB where U601 sits; check the
   real module), the USB-C height on the hub (sets the pod window z), the PTS645VL58 plunger height (sets the
   button window z), the mini blade holder with a fuse fitted (must stay under 23 mm), the Wurth box header with
   the IDC plug (the mech model assumed 18 mm).
4. Footprint assumptions: Bourns MF-R lead spacing 5.1 mm, NTC on a 2.5 mm pitch disc footprint, Keystone 3568 on
   KiCad's footprint, Wurth 61204021621 on KiCad's generic IDC-Header_2x20 footprint (pins are standard; check the
   body outline against the Wurth drawing).
5. CC/CV buck module: generic XL4015 class, price and limits not verified (USD 8.00 from phase 1). Set it to
   16.80 V and 2.5 A with a meter before connecting OUT+.
6. Castle BEC 2.0 needs a Castle Link to set 7.5 V.
7. Firmware rules the board relies on: hold VESC_KILL low whenever VM is off; do not pulse LATCH_OFF while the
   button is held; precharge done when VM >= BAT - 2.5 V and has stopped rising (review M3); drive
   ESTOP_OK_TO_JETSON and CHG_STAT_N_TO_JETSON low while the Jetson's 3.3 V is down. The comments in
   `firmware/supervisor/pins.py` (lines 38-39) still say "through 10 k" for GP19 and GP20; they are 1k now.
8. USB 2.0 high speed to the dev kit now runs hub socket -> 7 mm of track -> USB-A receptacle -> one cable, without
   impedance control on a 2-layer board. NVIDIA documents flashing over a direct cable; if flashing through the hub
   fails, plug the laptop straight into the dev kit.
9. `tools/build_pcb.py` uses KiCad 9 calls (FOOTPRINT.SetField, FLIP_DIRECTION_LEFT_RIGHT) that KiCad 7.0.11's
   pcbnew does not have; the layout step has to adapt it.
10. No CC/CV module with high-side current sensing could be verified from a published schematic, so the design
    keeps the common low-side-shunt module and splits CHG_GND for it (review B1). A high-side module also works on
    these pads. README has the 5-minute bench check.

## Pre-order review fixes (2026-10-24)

The independent review (`docs/review_revb_2026-10-24.md`) asked for fixes before ordering, no redesign. Every change
with its refs is in `DESIGN_FIXED.md`; the reasons in short:

- **B1 charge ground.** The usual XL4015 module senses current in a shunt from IN- to OUT-; with both on GND the
  constant-current limit never acts (about 4 A from a 60 W charger, Q501 at 2-3 W). The charger side is now its own
  net CHG_GND (PD trigger GND, CC/CV IN-, D501, C501, the charger-present detector) and CC/CV OUT- is its only link
  to GND. Netcheck rule [14] enforces it.
- **M1 1k toward the Jetson.** R804, R812, R813 and R602 drive the dev kit's level-shifted inputs; a TXB-type part
  holds its pin through about 4k, so 10k only reached 0.94 V. At 1k the pin reaches about 2.6 V. The resistors from
  the Jetson toward the board stay 10k. Rule [6] now asks for 1k on the three J12 outputs.
- **M2 and m5 P-FETs.** Q402 and Q501 are IRF4905PBF (same G-D-S, 20 mOhm at -10 V) with 6.8k lower gate resistors:
  VGS -7.1 V at 12 V, -10 V at 16.8 V, -17.9 V at 30 V (under the 20 V limit). 100 nF gate-source on both (C407,
  C502) for about 0.4 ms soft start. The over-voltage trip moves from 18.6 to 18.7 V; release stays 17.85 V.
- **M3 precharge loads.** An alternative BEC input pad J410 on VSYS_SW, placed explicitly; BEC+ (J401, VM) stays
  the default. Two pads instead of a jumper or solder bridge: moving the 16 AWG lead is as quick, adds no part,
  and a 2.54 mm jumper is not rated for a stalled servo's peak current (not measured, several amps at the BEC
  input). On VSYS_SW the Pololu latch (6 A continuous) carries the servo as well as the dev kit, so this is the
  fallback only. R313 can be 4.7 Ohm 5 W in the same body.
- **M6 signal grounds.** COMM pin 2, the servo-lead ground and the FSESC USB ground each go to GND through a 1206
  resistor (R905 3.3, R906 3.3, R604 2.2 Ohm): 20-40 mA of loop current instead of amps, and they open like fuses
  if the ESC- joint fails. R604 is 2.2 Ohm because the FSESC may draw its USB VBUS current back through it.
- **M7 USB-A for the dev kit.** J601 is a Wurth 614004134726 through-hole USB-A standing on its edge at the Y = 0
  edge between the hub and the power button: one standard cable to the dev kit. J602 (FSESC, full speed) stays a
  1x4 header: two receptacles plus the right-angle power button do not fit in the 24 mm of edge there, and a
  stacked double USB-A has one shell for both ports, which would tie the FSESC's USB ground to GND and undo M6.
  The status LEDs moved to the edge beside the power button; the recovery button, F402, D405 and TP702 moved north.
- **m1** R304 2.2M (100k loaded the MIC5014 pump). **m3** C1001 10 nF, not a 74HCT132: one value change, no new
  IC; the edge now crosses the HCT threshold ten times faster, so a glitch that opens the switch is also an edge
  the Pico's E-stop interrupt sees (it then locks out until re-armed); 0.1 ms still filters pickup on the loop
  wire. **m4** D404, D405 P6KE22A (out of the pack TVS band).
  **m6** 10k series R316 between the NTC node and GP28. **m9** R408 4.7 Ohm: 0.5 V less drop at a sagging pack;
  on a 30 V spike D401 then takes about 2 A (netcheck), a 600 W part. **m12** BMS over-voltage 4.25 V in README.
  **m18** P6KE22A D406 fitted at the camera input. **m22** XT90-S gender text, DIP sockets as BOM lines, connector
  table in HANDOFF_E.md.
- **Not changed:** the dev kit's USB ground is in parallel with its DC lead, so an estimated 5 % of its supply
  current (around 0.2 A, from lead and cable resistances, not measured) returns through the USB cable; a resistor there would hurt 480 Mb/s signalling and the cable's
  ground wire carries that easily.
