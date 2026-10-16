#!/bin/bash
# Full board pipeline: placement -> plane vias -> freerouting -> clean-up router
# -> pours / power floods / stitching -> silkscreen -> DRC.
# usage: gen/run_all.sh [workdir]     (run from hardware/)
set -e
W=${1:-/tmp/fc_f405_build}; mkdir -p "$W"
KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3.9
KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
JAVA=${JAVA:-$HOME/.kicad-mcp/jdk25/jdk-25.0.4.1+1/Contents/Home/bin/java}
FR=${FR:-$HOME/.kicad-mcp/freerouting-2.4.1.jar}
q() { grep -v "wxApp\|leak\|Debug\|assert\|GetWidth" || true; }
$KP gen/build.py 2>&1 | q | tail -1
$KP gen/check_place.py 2>&1 | q | grep -v J5
$KP gen/handroute.py 2>&1 | q | tail -1          # locked pre-routes, before plane vias
$KP gen/gnd_vias.py 2>&1 | q | tail -3
$KP gen/route_fr.py prep 2>&1 | q | tail -1
python3 gen/dsn_patch.py
cp fc_f405.kicad_pcb "$W/placed.kicad_pcb"
rm -f fc_f405.ses
"$JAVA" -Xmx4g -jar "$FR" -de fc_f405.dsn -do fc_f405.ses -mp ${PASSES:-40} -mt 7 --gui.enabled=false > "$W/freerouting.log" 2>&1
grep -E "stage completed" "$W/freerouting.log" | sed -E 's/.*(Auto-routing|Optimization)/\1/' | cut -c1-120
$KP gen/route_fr.py importonly 2>&1 | q | head -1
cp fc_f405.kicad_pcb "$W/routed_raw.kicad_pcb"
$KP gen/route_fr.py pours 2>&1 | q | tail -1
$KC pcb drc -o "$W/drc_fr.rpt" fc_f405.kicad_pcb >/dev/null 2>&1 || true
cp "$W/routed_raw.kicad_pcb" fc_f405.kicad_pcb
$KP gen/cleanup.py export "$W/drc_fr.rpt" "$W/geom.json" 2>&1 | q
python3 gen/maze.py "$W/geom.json" "$W/routes.json" | grep -v "^routed"
gen/post.sh "$W"
