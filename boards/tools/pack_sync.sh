#!/bin/bash
# pack the board sources for the KiCad machine: code and small inputs only. Prints the tarball path.
cd /home/claude/carv2
N=/mnt/user-data/outputs/sync_$(date +%H%M%S).tar.gz
tar czf $N --exclude='__pycache__' --exclude='*.kicad_pcb' --exclude='*.kicad_sch' --exclude='*.kicad_pro' \
  --exclude='fab' --exclude='out/*.png' --exclude='out/*.svg' --exclude='out/*_geom.json' --exclude='out/fp_lib.json' --exclude='out/*.dsn' --exclude='out/*.ses' --exclude='out/*.net' --exclude='lib/stock_symbols' --exclude='*_parts.json' --exclude='*.rpt' --exclude='out/*_dump.json' --exclude='out/maze_*' --exclude='boards/*/vendor' boards firmware ${EXTRA} 2>/dev/null
echo $N
