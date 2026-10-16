#!/bin/bash
# post-routing half of run_all.sh, from a saved routed board + routes.json
W=$1
KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3.9
KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
q() { grep -v "wxApp\|leak\|Debug\|assert\|GetWidth" || true; }
cp "$W/routed_raw.kicad_pcb" fc_f405.kicad_pcb
$KP gen/cleanup.py apply "$W/routes.json" 2>&1 | q
# further clean-up rounds against the real pours, each seeing the last one's copper
for i in 1 2 3; do
  cp fc_f405.kicad_pcb "$W/r$i.kicad_pcb"
  $KP gen/route_fr.py pours 2>&1 | q | tail -1
  $KC pcb drc -o "$W/d$i.rpt" fc_f405.kicad_pcb >/dev/null 2>&1 || true
  cp "$W/r$i.kicad_pcb" fc_f405.kicad_pcb
  $KP gen/cleanup.py export "$W/d$i.rpt" "$W/g$i.json" 2>&1 | q
  python3 gen/maze.py "$W/g$i.json" "$W/routes$i.json" | grep -v "^routed .*w="
  $KP gen/cleanup.py apply "$W/routes$i.json" 2>&1 | q
done
$KP gen/route_fr.py pours 2>&1 | q | tail -1
$KP gen/finish.py 2>&1 | q | tail -2
$KP gen/silk.py 2>&1 | q | tail -7
python3 gen/stackup.py
$KC pcb drc -o drc.rpt fc_f405.kicad_pcb >/dev/null 2>&1 || true
grep "Found" drc.rpt; grep -o "^\[[a-z_]*\]" drc.rpt | sort | uniq -c
