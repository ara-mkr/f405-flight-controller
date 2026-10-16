# -*- coding: utf-8 -*-
"""Ground vias, placed before autorouting (KiCad python).

DESIGN_PLAN 3.4: every decoupling cap has its ground via within 1 mm of its pad.
This gives every GND pad its own via into the In1 plane - nearest legal spot,
joined by a short stub - and fills each regulator / OSD exposed pad with a
thermal via array (7.3: >= 9 vias under each TPS54360). All of it is locked, so
the autorouter treats ground as done and spends the board on signals.

    python3.9 gnd_vias.py          (after build.py, before route_fr.py prep)
"""
import sys, os, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pcbnew, layout, rules

PCB = os.path.join(os.path.dirname(HERE), "fc_f405.kicad_pcb")
MM = pcbnew.FromMM; T = pcbnew.ToMM
def V(x, y): return pcbnew.VECTOR2I(MM(x), MM(y))

VIA_D, VIA_DR = 0.5, 0.2          # signal via (PCBWay: 0.2 drill free, 0.15 ring)
TH_D, TH_DR   = 0.6, 0.3          # thermal via in exposed pads
CLR    = 0.2                      # keep 0.05 above the 0.15 rule for margin
STUB_W = 0.3
EP_GRID = {"U6": (3, 3), "U7": (3, 3), "U4": (2, 3)}   # cols x rows

def rect_dist(px, py, r):
    x0, y0, x1, y1 = r
    dx = max(x0 - px, 0, px - x1); dy = max(y0 - py, 0, py - y1)
    return math.hypot(dx, dy)

def pt_seg(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay; L2 = vx*vx + vy*vy
    u = 0 if L2 == 0 else max(0, min(1, ((px - ax)*vx + (py - ay)*vy) / L2))
    return math.hypot(px - ax - u*vx, py - ay - u*vy)

def seg_rect_dist(ax, ay, bx, by, r, n=12):
    return min(rect_dist(ax + (bx-ax)*k/n, ay + (by-ay)*k/n, r) for k in range(n+1))

class Board:
    def __init__(self, b):
        self.b = b
        self.pads = []            # (pad, net, layers {'F','B'}, rect, ref)
        for fp in b.Footprints():
            for p in fp.Pads():
                bb = p.GetBoundingBox()
                r = (T(bb.GetX()), T(bb.GetY()), T(bb.GetRight()), T(bb.GetBottom()))
                ls = set()
                if p.IsOnLayer(pcbnew.F_Cu): ls.add('F')
                if p.IsOnLayer(pcbnew.B_Cu): ls.add('B')
                if not ls: continue           # paste-only aperture, no copper
                self.pads.append((p, p.GetNetname(), ls, r, fp.GetReference()))
        self.vias = []            # (x, y, d, net) - ours, plus any already on the board
        self.tracks = []          # (layer, ax, ay, bx, by, w, net) laid before us (handroute.py)
        LAY = {pcbnew.F_Cu: 'F', pcbnew.B_Cu: 'B', pcbnew.In2_Cu: 'I', pcbnew.In3_Cu: 'J'}
        for t in b.GetTracks():
            if t.GetClass() == "PCB_VIA":
                c = t.GetPosition()
                self.vias.append((T(c.x), T(c.y), T(t.GetWidth(pcbnew.F_Cu)), t.GetNetname()))
            elif t.GetLayer() in LAY:
                s, e = t.GetStart(), t.GetEnd()
                self.tracks.append((LAY[t.GetLayer()], T(s.x), T(s.y), T(e.x), T(e.y),
                                    T(t.GetWidth()), t.GetNetname()))
        self.net = "GND"

    def via_ok(self, x, y, d, own=None, in_ep=False):
        if not self.inside(x, y, d/2 + 0.35): return False
        for hx, hy in layout.HOLE_XY:
            if math.hypot(x - hx, y - hy) < layout.HOLE_KEEPOUT_R + d/2: return False
        for p, net, ls, r, ref in self.pads:
            if p is own: continue
            # a thermal via may sit inside ANOTHER part's GND exposed pad
            # (U7 under U4 share one array)
            if in_ep and net == "GND" and (r[2]-r[0])*(r[3]-r[1]) > 4: continue
            need = d/2 + (CLR if net != self.net else 0.1)
            if rect_dist(x, y, r) < need: return False
        for vx, vy, vd, vn in self.vias:
            if math.hypot(x - vx, y - vy) < (d + vd)/2 + CLR: return False
        for L, tax, tay, tbx, tby, tw, tn in self.tracks:     # a via crosses every layer
            if tn != self.net and pt_seg(x, y, tax, tay, tbx, tby) < d/2 + tw/2 + CLR: return False
        return True

    def stub_ok(self, layer, ax, ay, bx, by, own, w=STUB_W, clr=CLR):
        for p, net, ls, r, ref in self.pads:
            if p is own or layer not in ls or net == self.net: continue
            if seg_rect_dist(ax, ay, bx, by, r, n=24) < w/2 + clr: return False
        for L, tax, tay, tbx, tby, tw, tn in self.tracks:
            if L != layer or tn == self.net: continue
            if min(pt_seg(ax + (bx-ax)*k/24, ay + (by-ay)*k/24, tax, tay, tbx, tby)
                   for k in range(25)) < w/2 + tw/2 + clr: return False
        for vx, vy, vd, vn in self.vias:
            if vn != self.net and pt_seg(vx, vy, ax, ay, bx, by) < w/2 + vd/2 + clr: return False
        return True

    @staticmethod
    def inside(x, y, m):
        W, H, R = layout.W, layout.H, layout.CORNER_R
        if x < m or y < m or x > W - m or y > H - m: return False
        for cx, cy in ((R, R), (W-R, R), (R, H-R), (W-R, H-R)):
            if ((x - cx)*(cx - W/2) > 0 and (y - cy)*(cy - H/2) > 0 and
                    math.hypot(x - cx, y - cy) > R - m):
                return False
        return True

    def add_via(self, x, y, d, dr):
        v = pcbnew.PCB_VIA(self.b)
        v.SetPosition(V(x, y)); v.SetWidth(MM(d)); v.SetDrill(MM(dr))
        v.SetNet(self.b.FindNet(self.net)); v.SetLocked(True)
        self.b.Add(v); self.vias.append((x, y, d, self.net))

    def add_stub(self, layer, ax, ay, bx, by, w=STUB_W):
        t = pcbnew.PCB_TRACK(self.b)
        t.SetStart(V(ax, ay)); t.SetEnd(V(bx, by)); t.SetWidth(MM(w))
        t.SetLayer(pcbnew.F_Cu if layer == 'F' else pcbnew.B_Cu)
        t.SetNet(self.b.FindNet(self.net)); t.SetLocked(True)
        self.b.Add(t)

def main():
    b = pcbnew.LoadBoard(PCB)
    B = Board(b)
    # 1. thermal arrays inside the exposed pads
    ep_done = set()
    for p, net, ls, r, ref in B.pads:
        if ref in EP_GRID and net == "GND":
            w, h = r[2] - r[0], r[3] - r[1]
            if w * h < 6: continue                    # a pin, not the EP
            # candidate grid over the pad; keep every spot that clears the
            # copper on BOTH sides (the other side may carry fine-pitch parts)
            cx, cy = (r[0] + r[2])/2, (r[1] + r[3])/2
            want = EP_GRID[ref][0] * EP_GRID[ref][1]
            got = 0
            cand = []
            for i in range(-6, 7):
                for j in range(-8, 9):
                    x, y = cx + i*0.25, cy + j*0.25
                    if abs(x - cx) <= w/2 - TH_D/2 - 0.1 and abs(y - cy) <= h/2 - TH_D/2 - 0.1:
                        cand.append((abs(i) + abs(j), x, y))
            for _, x, y in sorted(cand):
                if got >= want: break
                if B.via_ok(x, y, TH_D, own=p, in_ep=True):
                    B.add_via(x, y, TH_D, TH_DR); got += 1
            print("  %s exposed pad: %d thermal vias" % (ref, got))
            ep_done.add(id(p))
    # 2. one via per remaining SMD pad of each plane net (GND -> In1, +3V3 -> In4)
    for PNET in ("GND", "+3V3"):
      B.net = PNET
      placed = failed = joined = 0; fails = []
      for p, net, ls, r, ref in B.pads:
        if net != PNET or id(p) in ep_done or len(ls) != 1: continue
        # ADC anti-alias caps: a via here would sit in the R -> C signal path;
        # their GND pads join the F.Cu pour instead
        if ref == "C41" and PNET == "GND": continue
        layer = next(iter(ls))
        # already served by a hand pre-route (handroute.py): a same-net track ends in it
        if any(tn == PNET and L == layer and any(r[0] <= x <= r[2] and r[1] <= y <= r[3]
               for x, y in ((tax, tay), (tbx, tby)))
               for L, tax, tay, tbx, tby, tw, tn in B.tracks):
            continue
        cx, cy = (r[0] + r[2])/2, (r[1] + r[3])/2
        fpos = p.GetParentFootprint().GetPosition()
        ox, oy = cx - T(fpos.x), cy - T(fpos.y)                  # outward from the part
        on = math.hypot(ox, oy) or 1.0
        best = None
        for k in range(0, 26):
            rad = min(r[2]-r[0], r[3]-r[1])/2 + VIA_D/2 + 0.12 + 0.08*k
            cands = []
            for a in range(0, 360, 15):
                x = cx + rad*math.cos(math.radians(a)); y = cy + rad*math.sin(math.radians(a))
                cands.append((-((x - cx)*ox + (y - cy)*oy)/(rad*on), x, y))
            for _, x, y in sorted(cands):
                if B.via_ok(x, y, VIA_D, own=p) and B.stub_ok(layer, cx, cy, x, y, p):
                    best = (x, y); break
            if best: break
        if best:
            B.add_via(best[0], best[1], VIA_D, VIA_DR)
            B.add_stub(layer, cx, cy, best[0], best[1])
            placed += 1
            continue
        # fallback: stub to the nearest point (inset 0.15 mm) of another pad of
        # the same net on this layer, or to a via of that net already placed
        targets = []
        for p2, n2, ls2, r2, ref2 in B.pads:
            if n2 != PNET or p2 is p or layer not in ls2: continue
            tx = min(max(cx, r2[0] + 0.15), r2[2] - 0.15)
            ty = min(max(cy, r2[1] + 0.15), r2[3] - 0.15)
            targets.append((tx, ty))
        targets += [(vx, vy) for vx, vy, vd, vn in B.vias if vn == PNET]
        targets.sort(key=lambda t: math.hypot(t[0]-cx, t[1]-cy))
        for tx, ty in targets:
            if math.hypot(tx-cx, ty-cy) > 2.6: break
            if B.stub_ok(layer, cx, cy, tx, ty, p, w=0.2, clr=0.17):
                B.add_stub(layer, cx, cy, tx, ty, w=0.2); best = (tx, ty); joined += 1; break
        if not best:
            failed += 1; fails.append("%s.%s" % (ref, p.GetNumber()))
      print("%s: %d pad vias, %d pads stubbed to a neighbour, %d left to the router: %s"
            % (PNET, placed, joined, failed, " ".join(fails)))
    pcbnew.SaveBoard(PCB, b)
    rules.apply()
    print("thermal vias: %d" % sum(1 for v in B.vias if v[2] == TH_D))

if __name__ == "__main__":
    main()
