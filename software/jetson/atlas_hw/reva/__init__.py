"""Rev A (retired with the ATLAS-DRV-1 drive board and the ATLAS-BRN-1 brain board).

These drivers talked to chips that rev B does not have: the PCAL6408A expander, the INA228 on the
BMS shunt, the TPS25751 PD controller, the 24AA02 ID EEPROM, and the Jetson USB0 role switch of
the Antmicro-based carrier. They are kept, with their tests, so the rev A boards in boards/drive
and boards/brain can still be brought up; the `atlas` command no longer uses them.
"""
