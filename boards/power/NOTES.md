# ATLAS-PWR-1 rev B: judgment calls and open questions (agent D)

## Judgment calls

1. **130 x 84 mm, with resistors and small capacitors as 1206 chips on the bottom.** The mech kit limits the board
   to 130 mm (at 150 the front edge and a standoff sit in the lidar plug envelope). With every part through-hole,
   the courtyards alone add up to about 11,800 mm2 on a 10,920 mm2 board; even at 150 mm the all-through-hole
   placement did not close. So the 98 resistors and small capacitors moved to 1206 (five 10 uF parts to 1210) on
   the bottom side, with KiCad's hand-solder pads (BRIEF rule 2 fallback). Every IC, transistor, diode,
   electrolytic, connector and power part stays through-hole. The two power resistors (10 Ohm 5 W precharge,
   10 Ohm 0.6 W R-78E filter) stay through-hole. By the same area count an all-through-hole board would need
   roughly 160 mm, or a second, stacked logic board.
2. **Parts under socketed modules.** The Pico and the CH334F hub stand on 8.5 mm sockets (Sullins PPTC, insulator
   0.335 in = 8.51 mm), so their undersides are 11 mm up. The 74HCT08 (socketed) and the two J14 PC817s sit under
   the Pico; the MCP2221A (socketed) and its MCP1700 under the hub. The modules' courtyards are drawn as their
   socket strips only, and `placer.py` got a `HOLLOW` setting for it.
3. **PD trigger off the board.** PHASE2 put the Adafruit 5807 at the Y = 0 edge. To fit 130 mm it now sits in the
   side pod at the charge window together with the CC/CV buck (which was already off the board), wired to two
   pads (PD+, PD-). The charge input TVS, 10 uF, the 20 V detector, the reverse-block P-FET and the 5 A fuse stay on
   the board. The pod window for the charge port is no longer tied to the board.
4. **Camera regulator output goes straight to the camera.** The Pololu S18V20F12 sits on the tray; the board feeds
   its input (fused, two pads) and its 12 V output goes to the Triton's M8 lead. PHASE2 listed a JST-XH 2 camera
   connector at the front edge; there is none now.
5. **ESC and pack on wire pads, not XT60PW/XT90PW.** The XT90PW drawing could not be read and Amass rates it 30 A
   (UL). The pack gets a 10 AWG pigtail with an XT90 male (mates with the pack's XT90-S); the FSESC leads solder
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
   carrier spec 3.8): a TL431 trips an IRF9Z34N off at 18.6 V and releases at 17.9 V, so regen with the BMS open
   or a failed charger cannot hold the dev kit above about 18.6 V for longer than a spike (the P6KE20A takes the
   fast edge). The same P-FET is the Pico's power-cycle switch
   (GP22 DEVKIT_PWR, low = off). Its pull-up is now 10k (about 2.7 V on GP22 during a Pico reset); the comment in
   `firmware/supervisor/pins.py` still says 47k, the code does not depend on it.
10. **GP15 is CHG_PRESENT_N (active low, open collector)**, not a divider: the divider back-powers an unpowered Pico
    when the charger is in with the car off.
11. **Mini blade fuses** (Keystone 3568 holder + 5 A ATM fuse, USD 1.48) for the dev-kit feed and the charge path in
    place of the Littelfuse FLR ATO holder (USD 4.67): smaller and USD 6.38 cheaper per board.
12. **10 uF X7R 1210 ceramics** in place of the small electrolytics (MIC5014 supply, R-78E in and out, charge input,
    Pico VSYS). At 17 V a 50 V X7R 10 uF keeps roughly 4 uF; enough for these spots. The bulk caps on the pack,
    the servo rail and the dev-kit lead stay electrolytic.
13. **Hub ports:** port 1 dev kit, port 2 the console (under the hub, shortest pair), port 3 the FSESC, port 4 spare.
14. **Heatsink bar 40 x 15 x 3 mm** (was 45) so the BAT- pad fits beside it; all three tabs are drains, so they
    bolt to the bar with no insulators. The bar is live at BAT+.
15. **I2C link to J12 (330 Ohm) and the UART1 CTS strap are DNP**, as before: an unpowered Pico would clamp the dev
    kit's I2C bus, and the CTS strap is only needed if the VESC driver keeps hardware flow control (B_esc.md).
16. **Netcheck warnings left as warnings:** 0.05-0.28 mA flows into unpowered pins (Pico GP11/12/21 and the
    74HCT08 input with the board off and the Jetson or ESC on; MCP2221A URx with the laptop unplugged; the FSESC
    RX with the ESC off; the ADC clamps on a 30 V spike). All are behind 10k or 100k and below the 0.5 mA limit.

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
   button is held; precharge give-up timing as in PHASE2.
8. USB 2.0 high speed through the hub, the 4-pin headers and the jack leads is not impedance controlled; if the dev
   kit's USB device link is flaky at 480 Mb/s, shorten the leads or move that cable to a dev-kit USB-A port.
9. `tools/build_pcb.py` uses KiCad 9 calls (FOOTPRINT.SetField, FLIP_DIRECTION_LEFT_RIGHT) that KiCad 7.0.11's
   pcbnew does not have; the layout step has to adapt it.
