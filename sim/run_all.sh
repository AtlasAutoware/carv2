#!/bin/bash
# Run every simulation in this folder (needs ngspice and python3 with numpy, scipy, matplotlib).
# Results land in out/: PNG plots, the ngspice netlists, and one JSON file per simulation.
set -e
cd "$(dirname "$0")"
python3 dclink.py 30 50 70 100
python3 precharge.py
python3 poe_boost.py
python3 drive_thermal.py 70
python3 drive_thermal.py 100
H_CONV=8 python3 drive_thermal.py 70
