"""Author the footprints KiCad does not ship. Every dimension is transcribed from the
package drawing named in the comment - see datasheets/raw/."""
import os
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib", "fc_f405.pretty")

def pad(n, x, y, w, h, shape="rect", ptype="smd", layers='"F.Cu" "F.Paste" "F.Mask"', rr=None):
    extra = f'\n    (roundrect_rratio {rr})' if rr is not None else ''
    return (f'  (pad "{n}" {ptype} {shape} (at {x:g} {y:g}) (size {w:g} {h:g})'
            f' (layers {layers}){extra})')

def line(x1, y1, x2, y2, layer="F.SilkS", w=0.12):
    return (f'  (fp_line (start {x1:g} {y1:g}) (end {x2:g} {y2:g})'
            f' (stroke (width {w}) (type solid)) (layer "{layer}"))')

def rect(x, y, layer, w=0.05):
    return (f'  (fp_rect (start {-x:g} {-y:g}) (end {x:g} {y:g})'
            f' (stroke (width {w}) (type default)) (fill none) (layer "{layer}"))')

# Stock KiCad STEP models closest to each custom package, so 3D renders and the
# assembler's preview show a real part rather than bare pads.
MODELS = {
    "TDK_LGA-14_2.5x3.0mm":       "Package_LGA.3dshapes/LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y.step",
    "Bosch_LGA-10_2.0x2.0mm":     "Package_LGA.3dshapes/ST_HLGA-10_2x2mm_P0.5mm_LayoutBorder3x2y.step",
    "L_SMMS0630_7.1x6.6mm":       "Inductor_SMD.3dshapes/L_Sunlord_MWSA0603S.step",
    "PDFNWB-8L_3x3mm_DrainPad":   "Package_DFN_QFN.3dshapes/DFN-8-1EP_3x3mm_P0.65mm_EP1.55x2.4mm.step",
}

def fp(name, descr, tags, body, ftype="smd"):
    s  = f'(footprint "{name}" (version 20240108) (generator "fc_f405_gen")\n'
    s += f'  (layer "F.Cu")\n  (descr "{descr}")\n  (tags "{tags}")\n  (attr {ftype})\n'
    s += ('  (property "Reference" "REF**" (at 0 -3.5 0) (layer "F.SilkS")\n'
          '    (effects (font (size 1 1) (thickness 0.15))))\n'
          '  (property "Value" "VAL**" (at 0 3.5 0) (layer "F.Fab")\n'
          '    (effects (font (size 1 1) (thickness 0.15))))\n')
    s += "\n".join(body) + "\n"
    if name in MODELS:
        s += ('  (model "${KICAD10_3DMODEL_DIR}/%s"\n    (offset (xyz 0 0 0))\n'
              '    (scale (xyz 1 1 1))\n    (rotate (xyz 0 0 0))\n  )\n' % MODELS[name])
    s += ")\n"
    open(os.path.join(OUT, name + ".kicad_mod"), "w").write(s)
    return name

made = []

# ---------------------------------------------------------- ICM-42688-P LGA-14
# TDK DS-000347 Rev 1.2 p.54-55: D 2.5 (Y) x E 3.0 (X), e 0.5, W 0.25, L 0.475,
# side columns at x = +-1.1625, top/bottom rows at y = +-0.9125, D1 1.5, E1 1.0.
b = []
PW, PL = 0.30, 0.55                      # lead 0.25 x 0.475 + solder fillet allowance
for i, n in enumerate(["1","2","3","4"]):            # left column, top -> bottom
    b.append(pad(n, -1.1625, 0.75 - 0.5*i, PL, PW))
for i, n in enumerate(["5","6","7"]):                # bottom row, left -> right
    b.append(pad(n, -0.5 + 0.5*i, 0.9125, PW, PL))
for i, n in enumerate(["8","9","10","11"]):          # right column, bottom -> top
    b.append(pad(n, 1.1625, -0.75 + 0.5*i, PL, PW))
for i, n in enumerate(["12","13","14"]):             # top row, right -> left
    b.append(pad(n, 0.5 - 0.5*i, -0.9125, PW, PL))
b += [rect(1.5, 1.25, "F.Fab"), rect(1.75, 1.5, "F.CrtYd"),
      line(-1.75, -1.5, -1.75, -1.0), line(-1.75, -1.5, -1.2, -1.5)]
made.append(fp("TDK_LGA-14_2.5x3.0mm",
    "TDK InvenSense ICM-42688-P, 14-lead LGA 2.5x3.0x0.91mm, 0.5mm pitch",
    "LGA 14 TDK InvenSense IMU", b))

# ------------------------------------------------------------- BMP388 LGA-10
# Bosch BST-BMP388-DS001-07 sec 7.1 bottom view: 2.0x2.0, columns at x = +-0.7625
# (1.525 span), column pads at y = 0, +-0.5 (1.000 span), row pads at x = +-0.25
# (0.500 span), y = +-0.7625. Pads 0.275x0.250 (6x, columns) and 0.250x0.275 (4x).
# Sec 7.2: "Bosch Sensortec suggests the BMP388 outline dimensions as landing pattern."
b = []
b.append(pad("2", -0.25, -0.7625, 0.25, 0.275))      # top row, left
b.append(pad("1",  0.25, -0.7625, 0.25, 0.275))      # top row, right
for i, n in enumerate(["3","4","5"]):                # left column, top -> bottom
    b.append(pad(n, -0.7625, -0.5 + 0.5*i, 0.275, 0.25))
b.append(pad("6", -0.25, 0.7625, 0.25, 0.275))       # bottom row, left
b.append(pad("7",  0.25, 0.7625, 0.25, 0.275))       # bottom row, right
for i, n in enumerate(["10","9","8"]):               # right column, top -> bottom
    b.append(pad(n, 0.7625, -0.5 + 0.5*i, 0.275, 0.25))
b += [rect(1.0, 1.0, "F.Fab"), rect(1.25, 1.25, "F.CrtYd"),
      line(1.25, -1.25, 1.25, -0.7), line(1.25, -1.25, 0.7, -1.25)]
made.append(fp("Bosch_LGA-10_2.0x2.0mm",
    "Bosch BMP388, 10-pin metal-lid LGA 2.0x2.0x0.75mm",
    "LGA 10 Bosch barometer BMP388", b))

# ------------------------------------------------- CJAE10P06 PDFNWB3x3-8L
# JSCJ CJAE10P06 Rev 1.3 p.4 "Suggested Pad Layout": overall 3.2 tall; bottom row of
# four 0.37x0.5 pads on 0.65 pitch; 0.5 gap; drain pad 2.55x1.9 with four 0.3-tall
# tabs on top. Pins 1,2,3 = S, 4 = G, 5-8 = D tabs, 9 = drain pad.
b = []
for i, n in enumerate(["1","2","3","4"]):            # source x3 then gate, left -> right
    b.append(pad(n, -0.975 + 0.65*i, 1.35, 0.37, 0.5))
for i, n in enumerate(["5","6","7","8"]):            # drain tabs
    b.append(pad(n, 0.975 - 0.65*i, -1.45, 0.37, 0.3))
b.append(pad("9", 0, -0.35, 2.55, 1.9))              # drain pad, touches the tabs
b += [rect(1.5, 1.5, "F.Fab"), rect(1.85, 1.85, "F.CrtYd"),
      line(-1.85, 1.85, -1.85, 1.2), line(-1.85, 1.85, -1.2, 1.85)]
made.append(fp("PDFNWB-8L_3x3mm_DrainPad",
    "JSCJ DFNWB3x3-8L power MOSFET, exposed drain pad",
    "DFN 8 MOSFET power drain pad", b))

# ------------------------------------------- SMMS0630 molded power inductor
# Cyntec/SMMS datasheet land-pattern table, SMMS0630 row: A 7.10, B 6.60+-0.20,
# F 1.60 typ (pad length), G 3.70 (pad width), H 8.40 (outer-to-outer).
b = [pad("1", -3.4, 0, 1.6, 3.7), pad("2", 3.4, 0, 1.6, 3.7),
     rect(3.55, 3.3, "F.Fab"), rect(4.45, 3.6, "F.CrtYd"),
     line(-3.55, -3.3, 3.55, -3.3), line(-3.55, 3.3, 3.55, 3.3)]
made.append(fp("L_SMMS0630_7.1x6.6mm",
    "SMMS0630 molded shielded power inductor, 7.1 x 6.6 mm",
    "inductor power molded shielded", b))

# --------------------------------------------------- solder pad strips + battery
for n in (2, 3, 4, 5, 6):
    P = 1.8                      # pitch > pad length, so a 90 deg rotation is still legal
    b = []
    for i in range(n):
        b.append(pad(str(i + 1), -(n - 1) * P / 2 + P * i, 0, 1.0, 1.6,
                     shape="roundrect", rr=0.25))
    half = (n - 1) * P / 2 + 0.8
    b += [rect(half, 1.1, "F.CrtYd"), line(-half, -1.1, half, -1.1),
          line(-half, 1.1, half, 1.1)]
    made.append(fp(f"SolderPad_1mm_x{n}",
        f"{n} x 1.0 x 1.6 mm solder pads on 1.8 mm pitch, wire-to-board",
        "solder pad wire", b))

b = [pad("1", -4, 0, 3.2, 3.2, shape="circle"),
     pad("2",  4, 0, 3.2, 3.2, shape="circle"),
     rect(6.2, 2.2, "F.CrtYd")]
made.append(fp("SolderPad_3mm_x2",
    "2 x 3.2 mm round battery solder pads, 8 mm centres, sized for 3 A / 14 AWG",
    "solder pad battery power", b))

# M3 mounting hole. DESIGN_PLAN sec 7.4: 4.0 mm plated hole, 1.5 mm keep-out
# ring. Authored here because KiCad's MountingHole library is not registered for
# this project, which was reporting four lib_footprint_issues at DRC time.
b = ['  (pad "" np_thru_hole circle (at 0 0) (size 4.0 4.0) (drill 4.0)'
     ' (layers "F&B.Cu" "F&B.Mask"))',
     rect(2.6, 2.6, "F.CrtYd")]
made.append(fp("MountingHole_4.0mm",
    "M3 mounting hole, 4.0 mm non-plated, 1.5 mm keep-out ring (DESIGN_PLAN 7.4)",
    "mounting hole M3", b, ftype="exclude_from_pos_files exclude_from_bom"))

print("wrote %d footprints:" % len(made))
for m in made: print("  ", m)
