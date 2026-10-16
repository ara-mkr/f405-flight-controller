# -*- coding: utf-8 -*-
"""Placement sanity check (KiCad python): courtyard overlaps per side, parts in
a mounting-hole keep-out ring, parts closer than 0.5 mm to the board edge."""
import sys, os, math, itertools
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pcbnew, layout
PCB = os.path.join(os.path.dirname(HERE), "fc_f405.kicad_pcb")
b = pcbnew.LoadBoard(PCB)
mm = pcbnew.ToMM
boxes = []
for fp in b.Footprints():
    ref = fp.GetReference()
    if ref.startswith("H"): continue
    tht = any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH for p in fp.Pads())
    for side, lay in (("F", pcbnew.F_CrtYd), ("B", pcbnew.B_CrtYd)):
        cy = fp.GetCourtyard(lay)
        if cy.OutlineCount() == 0: continue
        bb = cy.BBox()
        r = (mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetRight()), mm(bb.GetBottom()))
        boxes.append((ref, side, r))
        if tht:
            boxes.append((ref, "B" if side == "F" else "F", r))
bad = 0
for (ra, sa, a), (rb, sb, c) in itertools.combinations(boxes, 2):
    if sa != sb or ra == rb: continue
    ox = min(a[2], c[2]) - max(a[0], c[0]); oy = min(a[3], c[3]) - max(a[1], c[1])
    if ox > 0.001 and oy > 0.001:
        print("OVERLAP %s %-5s %-5s  %.2f x %.2f" % (sa, ra, rb, ox, oy)); bad += 1
for ref, s, (x0, y0, x1, y1) in boxes:
    if ref != "J5" and x0 < 0.5 or y0 < 0.5 or x1 > layout.W-0.5 or y1 > layout.H-0.5:
        print("EDGE    %s %-5s %.2f %.2f %.2f %.2f" % (s, ref, x0, y0, x1, y1)); bad += 1
    for hx, hy in layout.HOLE_XY:
        dx = max(x0 - hx, 0, hx - x1); dy = max(y0 - hy, 0, hy - y1)
        d = math.hypot(dx, dy)
        if d < layout.HOLE_KEEPOUT_R - 0.01:
            print("HOLE    %s %-5s %.2f mm inside keep-out" % (s, ref, layout.HOLE_KEEPOUT_R - d)); bad += 1
print("problems:", bad)
