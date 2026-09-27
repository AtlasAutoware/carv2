#!/bin/bash
# Runs on the KiCad machine. usage: run_kicad.sh SYNC_TARBALL [steps...]
# steps: sch-drive erc-drive pcb-drive dsn-drive ses-drive sestrim-drive padvia-drive finish-drive drc-drive svg-drive,
#        fork-brain net-brain geom-brain forkpcb-brain dsn-brain ..., stack,
#        render-<board> (3D images to out/render), glb-<board> (3D model for share/make_renders.py),
#        fab-<board> (gerbers, drill, CPL, BOM to out/fab)
set -e
ROOT=/home/eshanki/atlasstuff/carv2
cd $ROOT
if [ -n "$1" ] && [ -f ".work/$1" ]; then tar xzf ".work/$1"; fi
shift || true
export KICAD_STOCK_SYMBOLS=$HOME/.local/share/flatpak/runtime/org.kicad.KiCad.Library.Symbols/x86_64/stable/active/files/symbols
export KICAD_FP_DIR=$HOME/.local/share/flatpak/runtime/org.kicad.KiCad.Library.Footprints/x86_64/stable/active/files/footprints
KCLI="flatpak run --command=kicad-cli org.kicad.KiCad"
KPY="flatpak run --command=python3 --filesystem=home org.kicad.KiCad"
for step in "$@"; do
  case $step in
    sch-*) b=${step#sch-}; (cd boards/tools && python3 make_footprints.py >/dev/null && python3 build_sch.py $b) ;;
    erc-*) b=${step#erc-}; (cd boards/$b && $KCLI sch erc --severity-all -o erc.rpt atlas_$b.kicad_sch | tail -1 && \
             grep -E "^\[" erc.rpt | sed 's/:.*//' | sort | uniq -c | sort -rn) ;;
    pcb-*) b=${step#pcb-}; (cd boards/tools && $KPY build_pcb.py $b) ;;
    drc-*) b=${step#drc-}; (cd boards/$b && $KCLI pcb drc --schematic-parity --severity-all -o drc.rpt atlas_$b.kicad_pcb | tail -2 && \
             grep -E "^\[" drc.rpt | sed 's/:.*//' | sort | uniq -c | sort -rn) ;;
    dsn-*) b=${step#dsn-}; (cd boards/tools && $KPY dsn_export.py $b) ;;
    fork-*) b=${step#fork-}; V=boards/$b/vendor/antmicro; A=.work/jetson-orin-baseboard; mkdir -p $V && \
             (cd $A && cp -n LICENSE README.md *.kicad_sch jetson-orin-baseboard.kicad_pro jetson-orin-baseboard.kicad_dru \
                jetson-orin-baseboard.kicad_pcb $ROOT/$V/) && (cd boards/$b && python3 fork.py) ;;
    geom-*) (cd boards/tools && $KPY fork_pcb.py --geom) ;;
    forkpcb-*) (cd boards/tools && $KPY fork_pcb.py) ;;
    net-*) b=${step#net-}; (cd boards/$b && mkdir -p out && $KCLI sch export netlist --format kicadsexpr \
             -o out/atlas_$b.net atlas_$b.kicad_sch | tail -2 && ls -la out/atlas_$b.net) ;;
    ses-*) b=${step#ses-}; (cd boards/tools && $KPY ses_import.py $b) ;;
    sestrim-*) b=${step#sestrim-}; (cd boards/tools && $KPY ses_import.py $b --trim) ;;
    padvia-drive) (cd boards/tools && $KPY pad_vias.py drive) ;;
    padvia-brain) (cd boards/tools && $KPY pad_vias.py brain --via 0.45/0.2 --track 0.15) ;;
    finish-*) b=${step#finish-}; (cd boards/tools && $KPY finish_pcb.py $b) ;;
    addroutes-*) b=${step#addroutes-}; (cd boards/tools && $KPY add_routes.py $b ../$b/out/maze_routes.json) ;;
    dump-*) b=${step#dump-}; (cd boards/$b && $KPY ../tools/dump_board.py atlas_$b.kicad_pcb out/atlas_${b}_dump.json | tail -1) ;;
    stripdrc-*) b=${step#stripdrc-}; (cd boards/tools && $KPY strip_routes.py $b --drc) ;;
    stack) (cd boards/tools && python3 check_stack.py) ;;
    netclass-*) b=${step#netclass-}; (cd boards/tools && python3 set_netclasses.py $b) ;;
    clean-*) b=${step#clean-}; (cd boards/tools && $KPY clean_tracks.py $b) ;;
    svg-*) b=${step#svg-}; (cd boards/$b && mkdir -p out && \
             $KCLI pcb export svg --mode-single --page-size-mode 2 --exclude-drawing-sheet --layers F.Cu,F.Silkscreen,F.Courtyard,F.Fab,Edge.Cuts -o out/top.svg atlas_$b.kicad_pcb >/dev/null && \
             $KCLI pcb export svg --mode-single --page-size-mode 2 --exclude-drawing-sheet --mirror --layers B.Cu,B.Silkscreen,B.Courtyard,B.Fab,Edge.Cuts -o out/bottom.svg atlas_$b.kicad_pcb >/dev/null && \
             $KCLI pcb export svg --mode-single --page-size-mode 2 --exclude-drawing-sheet --layers In1.Cu,Edge.Cuts -o out/in1.svg atlas_$b.kicad_pcb >/dev/null && \
             $KCLI pcb export svg --mode-single --page-size-mode 2 --exclude-drawing-sheet --layers In2.Cu,Edge.Cuts -o out/in2.svg atlas_$b.kicad_pcb >/dev/null && ls out) ;;
    render-*) b=${step#render-}; (cd boards/$b && mkdir -p out/render && R="$KCLI pcb render --quality high --floor --background opaque" && \
             $R --side top -w 2400 -h 1600 -o out/render/${b}_top.png atlas_$b.kicad_pcb >/dev/null && \
             $R --side bottom -w 2400 -h 1600 -o out/render/${b}_bottom.png atlas_$b.kicad_pcb >/dev/null && \
             $R --perspective --rotate '-50,0,-35' --zoom 0.85 -w 2400 -h 1600 -o out/render/${b}_iso.png atlas_$b.kicad_pcb >/dev/null && \
             $R --perspective --rotate '-130,0,-35' --zoom 0.85 -w 2400 -h 1600 -o out/render/${b}_iso_bottom.png atlas_$b.kicad_pcb >/dev/null && \
             ls -la out/render) ;;
    glb-*) b=${step#glb-}; (cd boards/$b && mkdir -p out/render && \
             O=$([ $b = drive ] && echo 30x120mm || echo 29.75x128.75mm) && \
             $KCLI pcb export glb --force --subst-models --include-tracks --include-pads --include-zones \
                --include-silkscreen --include-soldermask --user-origin $O -o out/render/atlas_$b.glb atlas_$b.kicad_pcb | tail -1 && \
             ls -la out/render/atlas_$b.glb) ;;
    fab-*) b=${step#fab-}; (cd boards/$b && F=out/fab && rm -rf $F && mkdir -p $F/gerbers && \
             CU=$(grep -oE '\([0-9]+ "(F|B|In[0-9]+)\.Cu" (signal|power|mixed|jumper)' atlas_$b.kicad_pcb | \
                  grep -oE '(F|B|In[0-9]+)\.Cu' | awk '!s[$0]++' | paste -sd, -) && \
             $KCLI pcb export gerbers --layers "$CU,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts" \
                --subtract-soldermask -o $F/gerbers/ atlas_$b.kicad_pcb | tail -1 && \
             $KCLI pcb export drill --format excellon --excellon-separate-th --generate-map --map-format gerberx2 \
                -o $F/gerbers/ atlas_$b.kicad_pcb | tail -1 && \
             $KCLI pcb export pos --format csv --units mm --side both --exclude-dnp -o $F/atlas_${b}_cpl.csv atlas_$b.kicad_pcb | tail -1 && \
             $KCLI sch export bom --fields 'Reference,Value,Footprint,MPN,Manufacturer,${QUANTITY}' \
                --labels 'Designator,Value,Footprint,MPN,Manufacturer,Qty' --group-by 'Value,Footprint,MPN' --exclude-dnp \
                -o $F/atlas_${b}_bom.csv atlas_$b.kicad_sch | tail -1 && \
             (cd $F/gerbers && python3 -c "import zipfile,os;z=zipfile.ZipFile('../atlas_${b}_gerbers.zip','w',zipfile.ZIP_DEFLATED);[z.write(f) for f in sorted(os.listdir('.'))]") && \
             echo "copper: $CU" && ls -la $F $F/gerbers | tail -30) ;;
    *) echo "unknown step $step" ;;
  esac
done
