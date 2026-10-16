# -*- coding: utf-8 -*-
"""Post-route copper (KiCad python), run after route_fr.py import:

  1. power-stage floods - a 1.6 mm same-net copper strip along every pad-to-pad
     step of each power path (VIN, switch node, output, battery input), above
     the GND pour in priority. DESIGN_PLAN 7.5 asks for 2 mm VBAT and
     1 mm switch nodes; the routed traces are 0.6 mm, the floods carry the current.
  2. GND stitching - a via on a 1.6 mm grid wherever every copper layer is
     clear, tying the F / In2 / B pours to the In1 plane.
"""
import sys, os, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pcbnew, layout, rules

PCB = os.path.join(os.path.dirname(HERE), "fc_f405.kicad_pcb")
MM = pcbnew.FromMM; T = pcbnew.ToMM

# Chain floods: (net, [(ref, pad), ...]) - a 1.6 mm copper strip on B.Cu along
# each consecutive pad pair, i.e. exactly the power path, so the flood carries
# the current without spreading over (and being cut up by) unrelated parts.
CHAINS = [
    ("SW_9V",   [("U7", "8"), ("D2", "1"), ("L2", "1")]),
    ("SW_9V",   [("C11", "2"), ("U7", "8")]),
    ("SW_5V",   [("U6", "8"), ("D1", "1"), ("L1", "1")]),
    ("SW_5V",   [("C10", "2"), ("U6", "8")]),
    ("VBAT",    [("C3", "1"), ("U7", "2")]),
    ("VBAT",    [("C1", "1"), ("U6", "2")]),
    ("+9V",     [("L2", "2"), ("C8", "1")]),
    ("+5V",     [("L1", "2"), ("C6", "1")]),
    ("VBAT_IN", [("J1", "1"), ("Q1", "2")]),
    ("VBAT",    [("Q1", "9"), ("C43", "1")]),
]
STRIP = 1.6
_prio = [5]

def pad_xy(b, ref, num):
    for fp in b.Footprints():
        if fp.GetReference() == ref:
            for p in fp.Pads():
                if p.GetNumber() == num:
                    c = p.GetPosition(); return T(c.x), T(c.y)
    raise KeyError((ref, num))

def strip_zone(b, net, a, c, w=STRIP):
    (x1, y1), (x2, y2) = a, c
    L = math.hypot(x2 - x1, y2 - y1) or 1e-6
    ux, uy = (x2 - x1)/L, (y2 - y1)/L; nx, ny = -uy*w/2, ux*w/2
    ex, ey = ux*w/2, uy*w/2                      # run past each pad centre
    pts = [(x1 - ex + nx, y1 - ey + ny), (x2 + ex + nx, y2 + ey + ny),
           (x2 + ex - nx, y2 + ey - ny), (x1 - ex - nx, y1 - ey - ny)]
    z = pcbnew.ZONE(b)
    z.SetLayer(pcbnew.B_Cu)
    z.SetNet(b.FindNet(net))
    _prio[0] += 1
    z.SetZoneName("flood_%s_%d" % (net, _prio[0]))
    z.SetAssignedPriority(_prio[0])
    z.SetLocalClearance(MM(0.25))
    z.SetMinThickness(MM(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    o = z.Outline(); o.NewOutline()
    for x, y in pts: o.Append(MM(x), MM(y))
    b.Add(z)

def flood_chains(b):
    n = 0
    for net, chain in CHAINS:
        xy = [pad_xy(b, r, p) for r, p in chain]
        for a, c in zip(xy, xy[1:]):
            strip_zone(b, net, a, c); n += 1
    return n

def ep_rects(b, refs=("U6", "U7", "U4")):
    out = []
    for fp in b.Footprints():
        if fp.GetReference() not in refs: continue
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            r = (T(bb.GetX()), T(bb.GetY()), T(bb.GetRight()), T(bb.GetBottom()))
            if p.GetNetname() == "GND" and (r[2]-r[0])*(r[3]-r[1]) > 4: out.append(r)
    return out

def stitch(b, pitch=1.6, d=0.5, drill=0.2, clr=0.25):
    obst = []          # (kind, geometry, half-width, net) in mm
    for fp in b.Footprints():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            obst.append(("r", (T(bb.GetX()), T(bb.GetY()), T(bb.GetRight()), T(bb.GetBottom())), 0, p.GetNetname()))
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            c = t.GetPosition(); obst.append(("c", (T(c.x), T(c.y)), T(t.GetWidth(pcbnew.F_Cu))/2, t.GetNetname()))
        else:
            s, e = t.GetStart(), t.GetEnd()
            obst.append(("s", (T(s.x), T(s.y), T(e.x), T(e.y)), T(t.GetWidth())/2, t.GetNetname()))
    def dist(o, x, y):
        k, g, hw, _ = o
        if k == "r":
            dx = max(g[0]-x, 0, x-g[2]); dy = max(g[1]-y, 0, y-g[3]); return math.hypot(dx, dy)
        if k == "c":
            return math.hypot(x-g[0], y-g[1]) - hw
        ax, ay, bx, by = g; vx, vy = bx-ax, by-ay; L2 = vx*vx + vy*vy
        u = 0 if L2 == 0 else max(0, min(1, ((x-ax)*vx + (y-ay)*vy)/L2))
        return math.hypot(x-ax-u*vx, y-ay-u*vy) - hw
    n = 0
    # 1. extra thermal vias inside each exposed pad (0.45 mm fits where 0.6 did not)
    eps = ep_rects(b)
    def in_ep(r): return any(abs(r[0]-e[0]) < 1e-3 and abs(r[3]-e[3]) < 1e-3 for e in eps)
    for e in eps:
        have = sum(1 for o in obst if o[0] == "c" and o[3] == "GND" and e[0] <= o[1][0] <= e[2] and e[1] <= o[1][1] <= e[3])
        yy = e[1] + 0.35
        while yy <= e[3] - 0.35 and have < 9:
            xx = e[0] + 0.35
            while xx <= e[2] - 0.35 and have < 9:
                ok = True
                for o in obst:
                    if o[0] == "r" and o[3] == "GND" and in_ep(o[1]): continue
                    need = 0.225 + (clr if o[3] != "GND" else 0.15)
                    if dist(o, xx, yy) < need: ok = False; break
                if ok:
                    v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(MM(xx), MM(yy)))
                    v.SetWidth(MM(0.45)); v.SetDrill(MM(0.2)); v.SetNet(b.FindNet("GND"))
                    b.Add(v); obst.append(("c", (xx, yy), 0.225, "GND")); have += 1; n += 1
                xx += 0.25
            yy += 0.25
    W, H, R = layout.W, layout.H, layout.CORNER_R
    y = 1.0
    while y < H - 0.9:
        x = 1.0
        while x < W - 0.9:
            ok = all(math.hypot(x-hx, y-hy) > layout.HOLE_KEEPOUT_R + d/2 for hx, hy in layout.HOLE_XY)
            for cx, cy in ((R, R), (W-R, R), (R, H-R), (W-R, H-R)):
                if ((x-cx)*(cx-W/2) > 0 and (y-cy)*(cy-H/2) > 0 and math.hypot(x-cx, y-cy) > R - 0.9):
                    ok = False
            if ok:
                for o in obst:
                    need = d/2 + (clr if o[3] != "GND" else 0.15)
                    if dist(o, x, y) < need: ok = False; break
            if ok:
                v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
                v.SetWidth(MM(d)); v.SetDrill(MM(drill)); v.SetNet(b.FindNet("GND"))
                b.Add(v); obst.append(("c", (x, y), d/2, "GND")); n += 1
            x += pitch
        y += pitch
    return n

def widen(b, wmin=0.127):
    """freerouting necks traces down at fine-pitch pins, sometimes to 0.095 mm;
    the board is ordered at 5/5 mil, so lift any such stub to 0.127 mm. The
    final DRC catches the rare stub that then crowds a pad (one SDA jog beside
    R15 was re-drawn by hand on the shipped board)."""
    n = 0
    for t in b.GetTracks():
        if t.GetClass() != "PCB_VIA" and t.GetWidth() < MM(wmin):
            t.SetWidth(MM(wmin)); n += 1
    return n

def main():
    b = pcbnew.LoadBoard(PCB)
    print("necked stubs widened to 0.127 mm:", widen(b))
    made = flood_chains(b)
    n = stitch(b)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.BuildConnectivity()
    pcbnew.SaveBoard(PCB, b)
    rules.apply()
    print("power floods: %d, stitching vias: %d, unrouted: %d"
          % (made, n, b.GetConnectivity().GetUnconnectedCount(True)))

if __name__ == "__main__":
    main()
