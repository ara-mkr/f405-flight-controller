# -*- coding: utf-8 -*-
"""Silkscreen pass (KiCad python): a label beside every wire pad, battery
polarity, board name. Run after routing; it only touches the silk layers.

Text is 0.8 mm tall / 0.15 mm stroke - PCBWay's minimum legible legend.
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pcbnew, rules, layout

PCB = os.path.join(os.path.dirname(HERE), "fc_f405.kicad_pcb")
MM = pcbnew.FromMM
def V(x, y): return pcbnew.VECTOR2I(MM(x), MM(y))

# connector -> label per pad number
LABELS = {
    "J12": ["5V", "T3", "R3", "G"],            # UART3  (VTX control)
    "J13": ["5V", "T5", "R5", "G"],            # UART5
    "J14": ["5V", "T6", "R6", "G"],            # UART6
    "J10": ["5V", "TX1", "RX1", "G"],          # UART1  (receiver)
    "J11": ["5V", "TX2", "RX2", "G"],          # UART2  (GPS)
    "J8":  ["5V", "LED", "G"],                 # WS2812 strip
    "J7":  ["BZ+", "BZ-"],                     # buzzer
    "J9":  ["CAM", "5V", "G", "VTX", "9V"],
    "J15": ["CC", "RSI", "TX4", "3V3", "G"],   # camera control / RSSI / UART4 TX
    "J2":  ["3V", "IO", "CK", "G"],            # SWD (bottom)
    "J3":  ["B0", "3V"],                       # boot (bottom)
    "J4":  ["3V", "CL", "DA", "G"],            # I2C compass (bottom)
}

# shorter forms, tried only where the full label fits nowhere (README legend lists them)
ALT = {"CAM": "VI", "VTX": "VO", "RSI": "RS", "TX4": "T4", "3V3": "3V", "BZ+": "B+",
       "BZ-": "B-", "RX1": "R1", "TX1": "T1", "RX2": "R2", "TX2": "T2", "LED": "LD"}

def text(b, s, x, y, layer, h=0.8, angle=0, justify=0, bold=False, w=None, add=True):
    t = pcbnew.PCB_TEXT(b)
    t.SetText(s)
    t.SetLayer(layer)
    t.SetTextSize(V(w or h, h))
    t.SetTextThickness(MM(0.15 if h <= 1.0 else 0.2))
    t.SetBold(bold)
    t.SetTextAngleDegrees(angle)
    if justify < 0: t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    elif justify > 0: t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT)
    if layer == pcbnew.B_SilkS: t.SetMirrored(True)
    t.SetPosition(V(x, y))
    if add: b.Add(t)
    return t

def strip_passive_silk(b):
    """Dense FC practice: no silkscreen outlines on R / C / ferrites (they only
    overlap their neighbours at this density). Moved to Fab, so the assembly
    drawing keeps them. ICs, diodes and LEDs keep pin-1 / polarity marks."""
    n = 0
    for fp in b.Footprints():
        ref = fp.GetReference()
        if not (ref[:1] in ("R", "C") or ref.startswith("FB")): continue
        for g in fp.GraphicalItems():
            if g.GetLayer() == pcbnew.F_SilkS: g.SetLayer(pcbnew.F_Fab); n += 1
            elif g.GetLayer() == pcbnew.B_SilkS: g.SetLayer(pcbnew.B_Fab); n += 1
    return n

def clear_clashes(b, placed, m=0.15):
    """A pad label beats its own connector's outline: any outline segment under a
    label goes to Fab. Crystal outlines (Y*) touching another part's silk - U4's
    pin-1 mark beside Y2 - go to Fab too; IC pin-1 / polarity marks always stay."""
    T = pcbnew.ToMM
    def box(g):
        q = g.GetBoundingBox(); return (T(q.GetX()), T(q.GetY()), T(q.GetRight()), T(q.GetBottom()))
    def hit(a, c):
        return a[0] < c[2] + m and c[0] - m < a[2] and a[1] < c[3] + m and c[1] - m < a[3]
    silk = []                                   # (ref, item, side, box)
    for fp in b.Footprints():
        for g in fp.GraphicalItems():
            if g.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
                silk.append((fp.GetReference(), g, "F" if g.GetLayer() == pcbnew.F_SilkS else "B", box(g)))
    n = 0
    for ref, g, sd, bx in silk:
        clash = any(hit(bx, lb[1:]) for lb in placed[sd] if lb[0] == ref)
        if not clash and ref.startswith("Y"):
            clash = any(r2 != ref and s2 == sd and hit(bx, b2) for r2, g2, s2, b2 in silk)
        if clash:
            g.SetLayer(pcbnew.F_Fab if sd == "F" else pcbnew.B_Fab); n += 1
    return n

def main():
    b = pcbnew.LoadBoard(PCB)
    print("passive silk outlines moved to fab:", strip_passive_silk(b))
    W = layout.W
    # obstacles per side: every pad, every part body (its Fab outline - silk
    # under a body would be hidden) and every other part's silk. Courtyards are
    # an assembly keep-out, not a silk one, so a label may sit in one.
    T = pcbnew.ToMM
    obst = {"F": [], "B": []}
    def bbox(items):
        bs = [g.GetBoundingBox() for g in items]
        return (T(min(q.GetX() for q in bs)), T(min(q.GetY() for q in bs)),
                T(max(q.GetRight() for q in bs)), T(max(q.GetBottom() for q in bs)))
    for fp in b.Footprints():
        sd = "B" if fp.IsFlipped() else "F"
        fab = [g for g in fp.GraphicalItems() if g.GetLayer() in (pcbnew.F_Fab, pcbnew.B_Fab)]
        if fab:
            obst[sd].append((fp.GetReference(), ) + bbox(fab))
        else:
            cy = fp.GetCourtyard(pcbnew.B_CrtYd if sd == "B" else pcbnew.F_CrtYd)
            if cy.OutlineCount():
                bb = cy.BBox()
                obst[sd].append((fp.GetReference(), T(bb.GetX()), T(bb.GetY()), T(bb.GetRight()), T(bb.GetBottom())))
        for g in fp.GraphicalItems():
            if g.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
                obst["F" if g.GetLayer() == pcbnew.F_SilkS else "B"].append((fp.GetReference() + "#silk", ) + bbox([g]))
        for p in fp.Pads():
            q = p.GetBoundingBox()
            for s2 in ("F", "B"):
                if p.IsOnLayer(pcbnew.F_Cu if s2 == "F" else pcbnew.B_Cu):
                    obst[s2].append((fp.GetReference() + "#pad", T(q.GetX()), T(q.GetY()), T(q.GetRight()), T(q.GetBottom())))
    placed = {"F": [], "B": []}
    def free(sd, own, box):
        x0, y0, x1, y1 = box
        if x0 < 0.4 or y0 < 0.4 or x1 > W - 0.4 or y1 > W - 0.4: return False
        for r, a0, b0, a1, b1 in obst[sd] + placed[sd]:
            if r in (own, own + "#silk"): continue    # own body / outline: clear_clashes yields it
            if x0 < a1 + 0.1 and a0 - 0.1 < x1 and y0 < b1 + 0.1 and b0 - 0.1 < y1: return False
        return True
    def tbox(x, y, s, h, just):
        w = 0.72 * h * len(s) + 0.15
        x0 = x if just < 0 else (x - w if just > 0 else x - w/2)
        return (x0, y - h/2 - 0.08, x0 + w, y + h/2 + 0.08)
    skipped, flipped, narrow, short = [], [], [], []
    for fp in b.Footprints():
        ref = fp.GetReference()
        if ref not in LABELS: continue
        sd = "B" if fp.IsFlipped() else "F"
        lay = pcbnew.B_SilkS if sd == "B" else pcbnew.F_SilkS
        pads = {}
        for p in fp.Pads():
            c = p.GetPosition(); bb = p.GetBoundingBox()
            pads[p.GetNumber()] = (T(c.x), T(c.y), T(bb.GetWidth()), T(bb.GetHeight()))
        xs = [v[0] for v in pads.values()]; ys = [v[1] for v in pads.values()]
        vertical = (max(ys) - min(ys)) > (max(xs) - min(xs))
        cx, cy = sum(xs)/len(xs), sum(ys)/len(ys)
        def place(lab, x, y, w, h, s2, tw, rot):
            """beside the pad, inward, on side s2 - or, on the other side (no pad
            there), behind the pad itself. rot = 90 runs the text along the pad
            pitch. Each candidate is measured with KiCad's own text bounding box.
            tw < 0.8 is a condensed face: same 0.8 mm height and 0.15 mm stroke."""
            lay2 = pcbnew.B_SilkS if s2 == "B" else pcbnew.F_SilkS
            inward = (1 if cx < W/2 else -1) if vertical else (1 if cy < W/2 else -1)
            ext = w if vertical else h                     # pad size across the row
            if s2 == sd:
                cands = [(ext/2 + d, -inward if not rot else 0) for d in (0.3, 0.55, 0.8, 1.1, 1.4)]
                if rot: cands = [(ext/2 + d, 0) for d in (0.62, 0.85, 1.1)]
            else:                                          # centred on the pad, then sliding inward
                cands = [(0, 0)] + [(o, -inward if not rot else 0) for o in (0.1, 0.3, 0.5, ext/2 + 0.3)] \
                        + [(o, 0) for o in (-0.2, -0.35, -0.5)]      # or out toward the board edge
            for off, anchor in cands:
                if vertical: tx, ty = x + inward*off, y
                else: tx, ty = x, y + inward*(off + (0.4 if s2 == sd and not rot else 0))
                just = 0 if (rot or not vertical) else (anchor if s2 == "F" else -anchor)
                o = text(b, lab, tx, ty, lay2, justify=just, w=tw, add=False, angle=90 if rot else 0)
                q = o.GetBoundingBox()
                box = (T(q.GetX()) - 0.08, T(q.GetY()) - 0.08, T(q.GetRight()) + 0.08, T(q.GetBottom()) + 0.08)
                if free(s2, ref, box):
                    b.Add(o); placed[s2].append((ref, ) + box); return True
            return False
        other = "B" if sd == "F" else "F"
        TRIES = [(sd, 0.8, 0), (sd, 0.55, 0), (sd, 0.8, 1), (sd, 0.55, 1)]
        if ref not in ("J2", "J3", "J4"):      # edge wire pads: a label behind the pad still reads
            TRIES += [(other, 0.8, 0), (other, 0.55, 0), (other, 0.8, 1), (other, 0.55, 1)]
        for i, lab in enumerate(LABELS[ref]):
            x, y, w, h = pads[str(i + 1)]; tag = "%s.%d" % (ref, i + 1)
            done = False
            for s in [lab] + ([ALT[lab]] if lab in ALT else []):
                for s2, tw, rot in TRIES:
                    if place(s, x, y, w, h, s2, tw, rot):
                        if s2 != sd: flipped.append(tag)
                        if tw < 0.8 or rot: narrow.append(tag)
                        if s != lab: short.append("%s=%s" % (tag, s))
                        done = True; break
                if done: break
            if not done: skipped.append(tag)
    # groups with a label left off get a pin-1 dot, so README's pin order applies
    dots = []
    for ref in sorted({s.split(".")[0] for s in skipped}):
        fp = b.FindFootprintByReference(ref); sd = "B" if fp.IsFlipped() else "F"
        p1 = [p for p in fp.Pads() if p.GetNumber() == "1"][0]
        c = p1.GetPosition(); q = p1.GetBoundingBox()
        x, y = T(c.x), T(c.y); hw, hh = T(q.GetWidth())/2, T(q.GetHeight())/2
        for k, (dx, dy) in [(k, v) for k in (0.5, 0.7) for v in
                            ((0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (1, -1), (-1, 1), (1, 1))]:
            px, py = x + dx*(hw + k), y + dy*(hh + k)
            box = (px - 0.3, py - 0.3, px + 0.3, py + 0.3)
            own_lab = any(r == ref and box[0] < a1 + 0.1 and a0 - 0.1 < box[2] and box[1] < b1 + 0.1
                          and b0 - 0.1 < box[3] for r, a0, b0, a1, b1 in placed[sd])
            if not own_lab and free(sd, ref, box):
                d = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_CIRCLE)
                d.SetCenter(V(px, py)); d.SetEnd(V(px + 0.1, py)); d.SetWidth(MM(0.2))
                d.SetFilled(True); d.SetLayer(pcbnew.B_SilkS if sd == "B" else pcbnew.F_SilkS)
                b.Add(d); placed[sd].append((ref, ) + box); dots.append(ref); break
    print("pin-1 dots:", dots)
    print("labels on the far side, behind their pad:", flipped)
    print("condensed / rotated labels:", narrow)
    print("short forms:", short)
    print("labels without a clear spot (left off):", skipped)
    print("outline segments under labels / other parts' silk moved to fab:", clear_clashes(b, placed))
    # battery polarity, beside the 3.2 mm pads on the bottom
    for fp in b.Footprints():
        if fp.GetReference() == "J1":
            for p in fp.Pads():
                c = p.GetPosition()
                x, y = pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)
                s = "+" if p.GetNumber() == "1" else "-"
                text(b, s, x + (2.6 if s == "+" else -2.6), y, pcbnew.B_SilkS, h=1.5, bold=True)
    pcbnew.SaveBoard(PCB, b)
    rules.apply()
    print("silkscreen labels added")

if __name__ == "__main__":
    main()
