# -*- coding: utf-8 -*-
"""README images (system python3 + Pillow), run from hardware/ after post.sh.

  docs/img/hero_top.png   3D render, top          (kicad-cli pcb render)
  docs/img/bottom.png     3D render, bottom
  docs/img/iso.png        3D render, isometric perspective
  docs/img/copper.png     all six copper layers, one panel each
  docs/img/schematic.png  schematic preview

The render colours come from the stack-up block stackup.py writes.
SVGs are rasterised with macOS Quick Look (qlmanage) after their width/height
are rewritten in pixels - Quick Look draws an SVG at its declared size.
"""
import os, re, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont, ImageOps

HW = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(HW, "fc_f405.kicad_pcb"); SCH = os.path.join(HW, "fc_f405.kicad_sch")
OUT = os.path.join(os.path.dirname(HW), "docs", "img")
KC = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
FONT = "/System/Library/Fonts/SFNSMono.ttf"
BG = (13, 17, 23)                                   # GitHub dark canvas

def run(*a):
    subprocess.run(a, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def render(name, *extra, size=2000):
    out = os.path.join(OUT, name)
    run(KC, "pcb", "render", "-o", out, "--width", str(size), "--height", str(size),
        "--quality", "high", "--background", "transparent", "--use-board-stackup-colors",
        *extra, PCB)
    im = Image.open(out); bb = im.getbbox()          # trim empty margin, keep a little air
    if bb:
        pad = size // 40
        im = im.crop((max(0, bb[0]-pad), max(0, bb[1]-pad), min(im.width, bb[2]+pad), min(im.height, bb[3]+pad)))
        im.save(out)
    print("wrote", out, im.size)

def svg_png(svg, px, tmp):
    """rasterise an SVG to px wide via Quick Look; returns an RGB image"""
    t = open(svg).read()
    m = re.search(r'width="([\d.]+)mm" height="([\d.]+)mm"', t)
    w, h = float(m.group(1)), float(m.group(2))
    t = t.replace(m.group(0), 'width="%dpx" height="%dpx"' % (px, round(px * h / w)), 1)
    fixed = os.path.join(tmp, "px_" + os.path.basename(svg)); open(fixed, "w").write(t)
    run("qlmanage", "-t", "-s", str(px), "-o", tmp, fixed)
    im = Image.open(fixed + ".png").convert("RGB")
    return im.crop((0, 0, px, round(px * h / w)))

LAYERS = [("F.Cu", "L1  F.Cu   signal + GND fill", (232, 120, 72)),
          ("In1.Cu", "L2  In1.Cu  GND plane", (110, 160, 220)),
          ("In2.Cu", "L3  In2.Cu  signal + GND fill", (226, 196, 84)),
          ("In3.Cu", "L4  In3.Cu  signal + GND fill", (120, 200, 120)),
          ("In4.Cu", "L5  In4.Cu  +3V3 plane", (200, 120, 200)),
          ("B.Cu", "L6  B.Cu   power + GND fill", (90, 200, 210))]

def copper(tmp):
    px, gap, lab = 900, 36, 64
    font = ImageFont.truetype(FONT, 30)
    sheet = Image.new("RGB", (3 * px + 4 * gap, 2 * (px + lab) + 3 * gap), BG)
    for i, (ly, title, col) in enumerate(LAYERS):
        svg = os.path.join(tmp, ly + ".svg")
        run(KC, "pcb", "export", "svg", "--mode-single", "-o", svg, "-l", ly + ",Edge.Cuts",
            "--black-and-white", "--fit-page-to-board", "--exclude-drawing-sheet",
            "--drill-shape-opt", "2", PCB)
        g = ImageOps.invert(svg_png(svg, px, tmp).convert("L"))       # copper -> bright
        panel = Image.composite(Image.new("RGB", g.size, col), Image.new("RGB", g.size, BG), g)
        x = gap + (i % 3) * (px + gap); y = gap + (i // 3) * (px + lab + gap)
        ImageDraw.Draw(sheet).text((x, y), title, fill=(220, 225, 230), font=font)
        sheet.paste(panel, (x, y + lab))
    out = os.path.join(OUT, "copper.png"); sheet.save(out); print("wrote", out, sheet.size)

def schematic(tmp):
    # via PDF: Quick Look clips an SVG as large as the A1 sheet, but draws a PDF page whole
    pdf = os.path.join(tmp, "sch.pdf")
    run(KC, "sch", "export", "pdf", "-o", pdf, "--exclude-drawing-sheet", "--black-and-white", SCH)
    run("qlmanage", "-t", "-s", "3000", "-o", tmp, pdf)
    im = Image.open(pdf + ".png").convert("RGB")
    bb = ImageOps.invert(im.convert("L")).getbbox()
    im = im.crop((max(0, bb[0]-30), max(0, bb[1]-30), min(im.width, bb[2]+30), min(im.height, bb[3]+30)))
    out = os.path.join(OUT, "schematic.png"); im.save(out); print("wrote", out, im.size)

def main():
    os.makedirs(OUT, exist_ok=True)
    only = sys.argv[1:]
    want = lambda k: not only or k in only
    if want("3d"):
        render("hero_top.png", "--side", "top", "--floor")
        render("bottom.png", "--side", "bottom", "--floor")
        render("iso.png", "--rotate", "-45,0,45", "--perspective", "--floor", "--zoom", "0.68")
    with tempfile.TemporaryDirectory() as tmp:
        if want("copper"): copper(tmp)
        if want("sch"): schematic(tmp)

if __name__ == "__main__":
    main()
