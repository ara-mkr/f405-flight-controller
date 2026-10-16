#!/bin/bash
# Fab + assembly outputs into ../production (run from hardware/ after post.sh).
#   fc_f405_gerbers.zip    6 copper layers, masks, paste, silk, outline + Excellon drill
#   fc_f405_bom.csv        grouped BOM with LCSC part numbers and MPNs
#   fc_f405_cpl.csv        pick-and-place, mm, both sides
#   fc_f405_assembly_top.pdf / _bottom.pdf   Fab layers, pads sketched
#   fc_f405_schematic.pdf
set -e
KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
P=../production; G=$P/gerbers
mkdir -p "$G"
$KC pcb export gerbers -o "$G" --subtract-soldermask \
    -l F.Cu,In1.Cu,In2.Cu,In3.Cu,In4.Cu,B.Cu,F.Mask,B.Mask,F.Paste,B.Paste,F.SilkS,B.SilkS,Edge.Cuts \
    fc_f405.kicad_pcb >/dev/null
$KC pcb export drill -o "$G/" --format excellon --excellon-units mm --excellon-separate-th \
    --generate-map --map-format gerberx2 fc_f405.kicad_pcb >/dev/null
rm -f "$P/fc_f405_gerbers.zip"
(cd "$G" && zip -q -j ../fc_f405_gerbers.zip ./*)
$KC sch export bom -o "$P/fc_f405_bom.csv" \
    --fields "Reference,Value,Footprint,MPN,LCSC,\${QUANTITY}" \
    --labels "Designator,Value,Footprint,MPN,LCSC,Qty" \
    --group-by "Value,Footprint,MPN,LCSC" --ref-range-delimiter "" fc_f405.kicad_sch >/dev/null
$KC pcb export pos -o "$P/fc_f405_cpl.csv" --format csv --units mm --side both fc_f405.kicad_pcb >/dev/null
$KC pcb export pdf --mode-single -o "$P/fc_f405_assembly_top.pdf" -l F.Fab,Edge.Cuts \
    --sketch-pads-on-fab-layers --scale 0 fc_f405.kicad_pcb >/dev/null
$KC pcb export pdf --mode-single -o "$P/fc_f405_assembly_bottom.pdf" -l B.Fab,Edge.Cuts --mirror \
    --sketch-pads-on-fab-layers --scale 0 fc_f405.kicad_pcb >/dev/null
$KC sch export pdf -o "$P/fc_f405_schematic.pdf" fc_f405.kicad_sch >/dev/null
ls -la "$P" "$G"
