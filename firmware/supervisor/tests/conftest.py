"""The firmware modules sit one folder up and import each other by plain name, as on the Pico."""
import os
import sys

FIRMWARE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if FIRMWARE not in sys.path:
    sys.path.insert(0, FIRMWARE)
