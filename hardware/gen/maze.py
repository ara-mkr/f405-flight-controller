# -*- coding: utf-8 -*-
"""Clean-up maze router (system python + numpy/scipy). See cleanup.py.

Grid 0.05 mm over F / In2 / In3 / B (In1 GND and In4 +3V3 are planes, never routed).
Every existing copper item is rasterised exactly, then for the net being routed
the foreign copper is dilated by clearance + half the trace width with a
Euclidean distance transform - so a free cell is legal to the 0.127 mm rule
by construction, with a half-diagonal of margin for 45-degree segments.
A* over (layer, y, x), 8-connected, with a via cost; each finished route is
committed to the raster before the next one starts.
"""
import sys, json, math, heapq
import numpy as np
from scipy import ndimage

G = 0.05
W = H = 37.0; R = 5.0
HOLES = [(3.25, 3.25), (33.75, 3.25), (3.25, 33.75), (33.75, 33.75)]
KEEP_R = 3.5
CLR = 0.13
PCLR = 0.205     # HV class clearance (0.2 mm rule)
WCLR = 0.155     # PWR class (+5V / +9V / VBUS) clearance (0.15 mm rule)
EDGE = 0.3
VIA_D, VIA_DR = 0.45, 0.2
VIA_COST = 14
NX = int(round(W / G)) + 1; NY = int(round(H / G)) + 1
LAYERS = ["F", "I", "J", "B"]
NL = len(LAYERS)
WIDTHS = {  # net class -> widths to try, widest first
    "HV":  [0.6, 0.45, 0.3, 0.2], "PWR": [0.5, 0.4, 0.3, 0.2], "PWR3V3": [0.3, 0.25, 0.2],
    "Default": [0.127]}
CLASS = {**{n: "HV" for n in ("VBAT", "VBAT_IN", "SW_5V", "SW_9V")},
         **{n: "PWR" for n in ("+5V", "+9V", "USB_VBUS")},
         **{n: "PWR3V3" for n in ("+3V3", "+3V3_GYRO", "VDDA")}}

ys, xs = np.mgrid[0:NY, 0:NX]
X = xs * G; Y = ys * G

def inside_board(m):
    ok = (X >= m) & (Y >= m) & (X <= W - m) & (Y <= H - m)
    for cx, cy in ((R, R), (W - R, R), (R, H - R), (W - R, H - R)):
        q = ((X - cx) * (cx - W/2) > 0) & ((Y - cy) * (cy - H/2) > 0)
        ok &= ~(q & (np.hypot(X - cx, Y - cy) > R - m))
    for hx, hy in HOLES:                      # keep-out ring applies to the copper edge
        ok &= np.hypot(X - hx, Y - hy) >= KEEP_R + max(0.0, m - EDGE)
    return ok

def win(x0, y0, x1, y1):
    i0 = max(0, int(math.floor(x0 / G)) - 1); i1 = min(NX, int(math.ceil(x1 / G)) + 2)
    j0 = max(0, int(math.floor(y0 / G)) - 1); j1 = min(NY, int(math.ceil(y1 / G)) + 2)
    return j0, j1, i0, i1

class Raster:
    def __init__(self, geom):
        self.nets = {}
        self.own = np.zeros((NL, NY, NX), np.int32)       # 0 free, >0 net id, -1 conflict
        self.viahole = np.zeros((NY, NX), bool)           # existing via barrels
        self.ownpad = np.zeros((NL, NY, NX), np.int32)     # SMD pad area per net (no via-in-pad)
        for p in geom["pads"]:
            for L in p["layers"]:
                self.rect(LAYERS.index(L), p["r"], self.nid(p["net"]))
                if len(p["layers"]) == 1:
                    j0, j1, i0, i1 = win(*p["r"])
                    self.ownpad[LAYERS.index(L), j0:j1, i0:i1] = self.nid(p["net"])
        self.padown = self.own.copy()
        for t in geom["tracks"]:
            self.seg(LAYERS.index(t["layer"]), t["a"], t["b"], t["w"], self.nid(t["net"]))
        for v in geom["vias"]:
            self.add_via(v["x"], v["y"], v["d"], self.nid(v["net"]))
        self.board_tr = {}

    def nid(self, net):
        if not net: return -1
        return self.nets.setdefault(net, len(self.nets) + 1)

    def add_via(self, x, y, d, n):
        for k in range(NL): self.disc(k, x, y, d/2, n)
        j0, j1, i0, i1 = win(x-0.6, y-0.6, x+0.6, y+0.6)
        # hole-to-hole 0.3 mm: 0.55 mm centre spacing next to a 0.3 mm drill (0.6 via), 0.5 next to 0.2
        self.viahole[j0:j1, i0:i1] |= np.hypot(X[j0:j1, i0:i1]-x, Y[j0:j1, i0:i1]-y) < (0.56 if d >= 0.6 else 0.51)

    def _mark(self, k, sl, mask, n):
        cur = self.own[k][sl]
        new = np.where(mask & (cur == 0), n, cur)
        new = np.where(mask & (cur != 0) & (cur != n), -1, new)
        self.own[k][sl] = new

    def rect(self, k, r, n):
        j0, j1, i0, i1 = win(r[0], r[1], r[2], r[3])
        sl = (slice(j0, j1), slice(i0, i1))
        m = (X[sl] >= r[0]) & (X[sl] <= r[2]) & (Y[sl] >= r[1]) & (Y[sl] <= r[3])
        self._mark(k, sl, m, n)

    def disc(self, k, x, y, rad, n):
        j0, j1, i0, i1 = win(x - rad, y - rad, x + rad, y + rad)
        sl = (slice(j0, j1), slice(i0, i1))
        self._mark(k, sl, np.hypot(X[sl] - x, Y[sl] - y) <= rad, n)

    def seg(self, k, a, b, w, n):
        r = w/2
        j0, j1, i0, i1 = win(min(a[0], b[0]) - r, min(a[1], b[1]) - r, max(a[0], b[0]) + r, max(a[1], b[1]) + r)
        sl = (slice(j0, j1), slice(i0, i1))
        px, py = X[sl], Y[sl]
        vx, vy = b[0] - a[0], b[1] - a[1]; L2 = vx*vx + vy*vy
        u = np.clip(((px - a[0])*vx + (py - a[1])*vy) / L2, 0, 1) if L2 > 0 else 0
        d = np.hypot(px - a[0] - u*vx, py - a[1] - u*vy)
        self._mark(k, sl, d <= r, n)

    def power_ids(self):
        # copper that needs the 0.2 mm HV clearance from everything else
        return [i for net, i in self.nets.items() if CLASS.get(net) == "HV"]

    def clr_of(self, n):
        inv = {v: k for k, v in self.nets.items()}
        c = CLASS.get(inv.get(n))
        return PCLR if c == "HV" else (WCLR if c == "PWR" else CLR)

    def free(self, n, w):
        """per-layer mask of cells where a trace of width w on net n may run.
        Clearance is the larger of the two net classes: 0.2 mm next to (or for)
        HV / PWR copper, 0.13 mm otherwise."""
        out = []
        m = self.clr_of(n) + w/2 + G
        mp = PCLR + w/2 + G
        pw = self.power_ids()
        if w not in self.board_tr: self.board_tr[w] = inside_board(EDGE + w/2)
        for k in range(NL):
            foreign = (self.own[k] != 0) & (self.own[k] != n)
            d = ndimage.distance_transform_edt(~foreign) * G
            fp = foreign & np.isin(self.own[k], pw)
            dp = ndimage.distance_transform_edt(~fp) * G
            out.append((d > m) & (dp > mp) & self.board_tr[w])
        return np.array(out)

    def free_soft(self, n, w):
        """like free(), but copper of rippable nets is passable (penalised)"""
        inv = {v: k for k, v in self.nets.items()}
        ripp = np.zeros(self.own.shape, bool)
        for net, i in self.nets.items():
            if RIPPABLE(net) and i != n: ripp |= (self.own == i)
        hard = []; pen = []
        m = CLR + w/2 + G*0.5 + G*0.5
        if w not in self.board_tr: self.board_tr[w] = inside_board(EDGE + w/2)
        for k in range(NL):
            foreign = (self.own[k] != 0) & (self.own[k] != n) & ~ripp[k]
            d = ndimage.distance_transform_edt(~foreign) * G
            hard.append((d > m) & self.board_tr[w])
            dr = ndimage.distance_transform_edt(~ripp[k]) * G
            pen.append(dr <= m)
        mv = CLR + VIA_D/2 + G*0.5 + G*0.5
        vok = inside_board(EDGE + VIA_D/2)
        for k in range(NL):
            foreign = (self.own[k] != 0) & (self.own[k] != n) & ~ripp[k]
            vok &= ndimage.distance_transform_edt(~foreign) * G > mv
        for k in (0, NL - 1):
            vok &= ~ndimage.binary_dilation(self.ownpad[k] == n, iterations=3)
        return np.array(hard), vok, np.array(pen)

    def free_plane_soft(self, n, w):
        """plane-net (GND / +3V3) tracks and vias are passable at a cost;
        pads of every net stay hard"""
        pids = [i for net, i in self.nets.items() if net in PLANE and i != n]
        pw = self.power_ids()
        m = self.clr_of(n) + w/2 + G; mp = PCLR + w/2 + G
        if w not in self.board_tr: self.board_tr[w] = inside_board(EDGE + w/2)
        hard, pen = [], []
        for k in range(NL):
            own = self.own[k]
            soft = np.isin(own, pids) & ~np.isin(self.padown[k], pids)
            foreign = (own != 0) & (own != n) & ~soft
            ok = ndimage.distance_transform_edt(~foreign) * G > m
            fp = foreign & np.isin(own, pw)
            ok &= ndimage.distance_transform_edt(~fp) * G > mp
            hard.append(ok & self.board_tr[w])
            pen.append(ndimage.distance_transform_edt(~soft) * G <= m)
        mv = self.clr_of(n) + VIA_D/2 + G
        vok = inside_board(EDGE + VIA_D/2)
        for k in range(NL):
            own = self.own[k]
            soft = np.isin(own, pids) & ~np.isin(self.padown[k], pids)
            foreign = (own != 0) & (own != n) & ~soft
            vok &= ndimage.distance_transform_edt(~foreign) * G > mv
        for k in (0, NL - 1):
            vok &= ~ndimage.binary_dilation(self.ownpad[k] == n, iterations=3)
        return np.array(hard), vok, np.array(pen)

    def nets_on_path(self, path, n):
        inv = {v: k for k, v in self.nets.items()}
        hit = set()
        rr = 6
        for k, j, i in path:
            blk = self.own[k, max(0, j-rr):j+rr+1, max(0, i-rr):i+rr+1]
            for v in np.unique(blk):
                if v > 0 and v != n: hit.add(inv[int(v)])
        return hit

    def via_ok(self, n):
        m = self.clr_of(n) + VIA_D/2 + G
        mp = PCLR + VIA_D/2 + G
        pw = self.power_ids()
        ok = inside_board(EDGE + VIA_D/2)
        for k in range(NL):
            foreign = (self.own[k] != 0) & (self.own[k] != n)
            ok &= ndimage.distance_transform_edt(~foreign) * G > m
            fp = foreign & np.isin(self.own[k], pw)
            ok &= ndimage.distance_transform_edt(~fp) * G > mp
        ok &= ~self.viahole
        for k in (0, NL - 1):                     # no via inside an SMD pad of this net
            ok &= ~ndimage.binary_dilation(self.ownpad[k] == n, iterations=3)
        return ok

def astar(free, vok, starts, goals, box, pen=None, pcost=0):
    j0, j1, i0, i1 = box
    gset = set(goals)
    gx = sum(g[2] for g in goals)/len(goals); gy = sum(g[1] for g in goals)/len(goals)
    h = lambda j, i: math.hypot(i - gx, j - gy)
    dist = {}; prev = {}; pq = []
    for s in starts:
        dist[s] = 0.0; heapq.heappush(pq, (h(s[1], s[2]), 0.0, s))
    steps = [(0, 1, 1.0), (0, -1, 1.0), (1, 0, 1.0), (-1, 0, 1.0),
             (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142)]
    while pq:
        f, d, c = heapq.heappop(pq)
        if d > dist.get(c, 1e18): continue
        if c in gset:
            path = [c]
            while path[-1] in prev: path.append(prev[path[-1]])
            return path[::-1]
        k, j, i = c
        nb = []
        for dj, di, cost in steps:
            jj, ii = j + dj, i + di
            if j0 <= jj < j1 and i0 <= ii < i1 and free[k, jj, ii]:
                if dj and di and not (free[k, j, ii] and free[k, jj, i]): continue
                extra = pcost if (pen is not None and pen[k, jj, ii]) else 0
                nb.append(((k, jj, ii), cost + extra + (0.0 if 0 < k < NL - 1 else 0.1)))
        if vok[j, i]:
            for kk in range(NL):
                if kk != k and free[kk, j, i]:
                    nb.append(((kk, j, i), VIA_COST))
        for nc, cost in nb:
            nd = d + cost
            if nd < dist.get(nc, 1e18):
                dist[nc] = nd; prev[nc] = c
                heapq.heappush(pq, (nd + h(nc[1], nc[2]), nd, nc))
    return None

def cell(x, y): return int(round(y / G)), int(round(x / G))

def to_geom(path, a, b, net, w):
    tracks, vias = [], []
    pts = [(path[0][0], a[0], a[1])] + [(k, i*G, j*G) for k, j, i in path] + [(path[-1][0], b[0], b[1])]
    run = [pts[0]]
    def flush(run):
        if len(run) < 2: return
        simp = [run[0]]
        for p in run[1:]:
            if len(simp) >= 2:
                (_, x0, y0), (_, x1, y1) = simp[-2], simp[-1]
                if abs((x1-x0)*(p[2]-y1) - (y1-y0)*(p[1]-x1)) < 1e-9:
                    simp[-1] = p; continue
            simp.append(p)
        for p, q in zip(simp, simp[1:]):
            if math.hypot(q[1]-p[1], q[2]-p[2]) > 1e-6:
                tracks.append(dict(net=net, layer=LAYERS[p[0]], a=[round(p[1], 4), round(p[2], 4)],
                                   b=[round(q[1], 4), round(q[2], 4)], w=w))
    for p in pts[1:]:
        if p[0] != run[-1][0]:
            flush(run)
            vias.append(dict(net=net, x=round(run[-1][1], 4), y=round(run[-1][2], 4), d=VIA_D, drill=VIA_DR))
            run = [(p[0], run[-1][1], run[-1][2]), p]
        else:
            run.append(p)
    flush(run)
    return tracks, vias

RIPPABLE = lambda net: bool(net) and net != "GND" and CLASS.get(net, "Default") == "Default"

def route_pair(Rs, net, A, B, ripcost=None):
    """A* for one connection; returns (tracks, vias) or None. With ripcost set,
    foreign copper of rippable nets is passable at that extra cost per cell."""
    n = Rs.nid(net)
    for w in WIDTHS[CLASS.get(net, "Default")]:
        if ripcost is None:
            free = Rs.free(n, w); vok = Rs.via_ok(n); pen = None
        elif ripcost == "plane":
            free, vok, pen = Rs.free_plane_soft(n, w)
        else:
            free, vok, pen = Rs.free_soft(n, w)
        sa = [(LAYERS.index(L),) + cell(A["x"], A["y"]) for L in A["layers"]]
        sb = [(LAYERS.index(L),) + cell(B["x"], B["y"]) for L in B["layers"]]
        for c in sa + sb: free[c] = True
        for pad in (8, 30):
            box = win(min(A["x"], B["x"]) - pad, min(A["y"], B["y"]) - pad,
                      max(A["x"], B["x"]) + pad, max(A["y"], B["y"]) + pad)
            path = astar(free, vok, sa, sb, box, pen, 25 if ripcost == "plane" else (ripcost or 0))
            if path:
                return to_geom(path, (A["x"], A["y"]), (B["x"], B["y"]), net, w), path
    return None

def mst_pairs(pads):
    """Prim's MST over a net's pads -> list of (A, B) endpoint dicts"""
    pts = [dict(x=(p["r"][0]+p["r"][2])/2, y=(p["r"][1]+p["r"][3])/2, net=p["net"],
                layers=p["layers"]) for p in pads]
    if len(pts) < 2: return []
    inn = {0}; out = []
    while len(inn) < len(pts):
        best = None
        for i in inn:
            for j in range(len(pts)):
                if j in inn: continue
                d = math.hypot(pts[i]["x"]-pts[j]["x"], pts[i]["y"]-pts[j]["y"])
                if best is None or d < best[0]: best = (d, i, j)
        inn.add(best[2]); out.append((pts[best[1]], pts[best[2]]))
    return out

PLANE = {"GND", "+3V3"}

def plane_connect(Rs, P):
    """route a plane-net pad to the nearest legal via site and drop a via"""
    net = P["net"]; n = Rs.nid(net)
    free = Rs.free(n, 0.2); vok = Rs.via_ok(n)
    k0 = LAYERS.index(P["layers"][0]); j0, i0 = cell(P["x"], P["y"])
    free[k0, j0, i0] = True
    R = int(2.5 / G)
    jj, ii = np.mgrid[max(0, j0-R):j0+R+1, max(0, i0-R):i0+R+1]
    jj = jj.clip(0, NY-1); ii = ii.clip(0, NX-1)
    sel = vok[jj, ii] & free[k0, jj, ii]
    goals = [(k0, int(a), int(b)) for a, b in zip(jj[sel], ii[sel])]
    if not goals: return None
    box = win(P["x"]-2.6, P["y"]-2.6, P["x"]+2.6, P["y"]+2.6)
    path = astar(free, np.zeros_like(vok), [(k0, j0, i0)], goals, box)
    if not path: return None
    end = path[-1]
    t, _ = to_geom(path, (P["x"], P["y"]), (end[2]*G, end[1]*G), net, 0.2)
    v = [dict(net=net, x=round(end[2]*G, 4), y=round(end[1]*G, 4), d=VIA_D, drill=VIA_DR)]
    return t, v

SHARED = {}

def seg_dist(px, py, a, b):
    vx, vy = b[0]-a[0], b[1]-a[1]; L2 = vx*vx + vy*vy
    u = 0 if L2 == 0 else max(0, min(1, ((px-a[0])*vx + (py-a[1])*vy)/L2))
    return math.hypot(px-a[0]-u*vx, py-a[1]-u*vy)

def plane_shuffle(Rs, geom, tracks, vias, net, A, B, rebuild, commit):
    """route through movable GND/+3V3 plane vias; re-seat every pad that loses
    its via; all-or-nothing"""
    r2 = route_pair(Rs, net, A, B, ripcost="plane")
    if r2 is None: return None
    (t, v), path = r2
    w = t[0]["w"] if t else 0.127
    pts = [(i*G, j*G) for k, j, i in path]
    def near(x, y, rad):
        return any(math.hypot(x-px, y-py) < rad for px, py in pts[::2])
    kill_v = [o for o in vias if o["net"] in PLANE and o["net"] != net
              and near(o["x"], o["y"], o["d"]/2 + w/2 + PCLR + 0.1)]
    kill_t = [s for s in tracks if s["net"] in PLANE and s["net"] != net and
              any(seg_dist(px, py, s["a"], s["b"]) < s["w"]/2 + w/2 + PCLR + 0.1 for px, py in pts[::2])]
    if not kill_v and not kill_t: return None
    # pads served by the removed vias: stubs start at a pad centre
    reseat = []
    for o in kill_v:
        for s in tracks:
            if s["net"] == o["net"] and (math.hypot(s["b"][0]-o["x"], s["b"][1]-o["y"]) < 0.01):
                reseat.append((s["net"], s["a"], s["layer"]))
    for s in kill_t:
        reseat.append((s["net"], s["a"], s["layer"]))
    snap_t, snap_v = list(tracks), list(vias)
    kv = {id(o) for o in kill_v}; kt = {id(s) for s in kill_t}
    tracks[:] = [s for s in tracks if id(s) not in kt and not any(
        math.hypot(s["b"][0]-o["x"], s["b"][1]-o["y"]) < 0.01 and s["net"] == o["net"] for o in kill_v)]
    vias[:] = [o for o in vias if id(o) not in kv]
    Rs2 = rebuild()
    SHARED["Rs"] = Rs2
    r = route_pair(Rs2, net, A, B)
    ok = r is not None
    if ok:
        commit(r[0][0], r[0][1], net)
        seen = set()
        for pn, a, L in reseat:
            key = (pn, round(a[0], 3), round(a[1], 3))
            if key in seen: continue
            seen.add(key)
            rr = plane_connect(SHARED["Rs"], dict(net=pn, x=a[0], y=a[1], layers=[L]))
            if rr is None: ok = False; break
            commit(rr[0], rr[1], pn)
    if ok:
        print("  moved %d plane vias for %s" % (len(kill_v), net))
        return "done"
    tracks[:] = snap_t; vias[:] = snap_v
    SHARED["Rs"] = rebuild()
    return None

def main(gpath, opath):
    geom = json.load(open(gpath))
    tracks = list(geom["tracks"]); vias = list(geom["vias"])
    ripped = set()
    def rebuild():
        return Raster(dict(pads=geom["pads"], tracks=tracks, vias=vias))
    Rs = rebuild(); SHARED["Rs"] = Rs
    def commit(t, v, net):
        R_ = SHARED["Rs"]; n = R_.nid(net)
        for s in t: R_.seg(LAYERS.index(s["layer"]), s["a"], s["b"], s["w"], n)
        for o in v: R_.add_via(o["x"], o["y"], VIA_D, n)
        tracks.extend(t); vias.extend(v)
    # 1. plane pads with no way into their plane
    for A, B in geom["pairs"]:
        if A["net"] not in PLANE: continue
        for P in (A, B):
            if not any(abs(p["r"][0] - P["x"]) < 3 for p in geom["pads"]): pass
            r = plane_connect(Rs, P)
            if r:
                commit(r[0], r[1], P["net"]); print("plane via for %s at (%.1f,%.1f)" % (P["net"], P["x"], P["y"]))
    # 2. everything else, widest classes first
    pairs = [p for p in geom["pairs"] if p[0]["net"] not in PLANE]
    queue = sorted(pairs, key=lambda p: (CLASS.get(p[0]["net"], "Default") == "Default",
                                         math.hypot(p[0]["x"]-p[1]["x"], p[0]["y"]-p[1]["y"])))
    fails = []; budget = 0 if NORIP else 25
    for A, B in queue:
        net = A["net"]
        if net in ripped: continue           # re-routed whole from its pads already
        r = route_pair(Rs, net, A, B)
        if r is None:
            r = plane_shuffle(Rs, geom, tracks, vias, net, A, B, rebuild, commit)
            Rs = SHARED["Rs"]                 # shuffle may have rebuilt the raster
            if r == "done":
                print("routed %-12s (moved plane vias)" % net); continue
            r = None
        if r is None and budget > 0:
            r2 = route_pair(Rs, net, A, B, ripcost=40)
            hit = set()
            if r2 is not None:
                hit = {h for h in Rs.nets_on_path(r2[1], Rs.nid(net)) if RIPPABLE(h) and h != net}
            if hit and len(hit) <= 4:
                budget -= 1
                snap_t, snap_v, snap_rs = list(tracks), list(vias), Rs
                tracks[:] = [x for x in tracks if x["net"] not in hit]
                vias[:] = [x for x in vias if x["net"] not in hit]
                Rs = rebuild(); SHARED["Rs"] = Rs
                ok = route_pair(Rs, net, A, B)
                if ok:
                    commit(ok[0][0], ok[0][1], net)
                    for h in sorted(hit):
                        for pa, pb in mst_pairs([p for p in geom["pads"] if p["net"] == h]):
                            rr = route_pair(Rs, h, pa, pb)
                            if rr is None: ok = None; break
                            commit(rr[0][0], rr[0][1], h)
                        if ok is None: break
                if ok:
                    ripped |= hit; print("rip-up OK: %s rerouted for %s" % (sorted(hit), net)); continue
                tracks[:] = snap_t; vias[:] = snap_v
                Rs = rebuild(); SHARED["Rs"] = Rs
                print("rip-up reverted for %s (%s)" % (net, sorted(hit)))
        if r is None:
            fails.append(net); print("FAILED %s (%.1f,%.1f)->(%.1f,%.1f)" % (net, A["x"], A["y"], B["x"], B["y"]))
            continue
        commit(r[0][0], r[0][1], net)
        print("routed %-12s w=%.3f" % (net, r[0][0][0]["w"] if r[0][0] else 0))
    keep_t = [x for x in geom["tracks"] if x["net"] not in ripped]
    keep_v = [x for x in geom["vias"] if x["net"] not in ripped]
    new_t = [x for x in tracks if x not in keep_t]
    new_v = [x for x in vias if x not in keep_v]
    gone_v = [x for x in keep_v if x not in vias]          # moved plane vias
    gone_t = [x for x in keep_t if x not in tracks]
    json.dump(dict(tracks=new_t, vias=new_v, rip=sorted(ripped),
                   remove_vias=gone_v, remove_tracks=gone_t), open(opath, "w"))
    print("done: %d failed %s; ripped and re-routed %d nets" % (len(fails), fails, len(ripped)))

def _old_main(gpath, opath):
    geom = json.load(open(gpath))
    Rs = Raster(geom)
    pairs = [p for p in geom["pairs"] if p[0]["net"] not in ("GND", "+3V3")]
    order = sorted(pairs, key=lambda p: (CLASS.get(p[0]["net"], "Default") == "Default",
                                         math.hypot(p[0]["x"]-p[1]["x"], p[0]["y"]-p[1]["y"])))
    out_t, out_v, fails = [], [], []
    for A, B in order:
        net = A["net"]; n = Rs.nid(net)
        done = False
        for w in WIDTHS[CLASS.get(net, "Default")]:
            free = Rs.free(n, w); vok = Rs.via_ok(n)
            sa = [(LAYERS.index(L),) + cell(A["x"], A["y"]) for L in A["layers"]]
            sb = [(LAYERS.index(L),) + cell(B["x"], B["y"]) for L in B["layers"]]
            for c in sa + sb: free[c] = True        # endpoints sit on own copper
            path = None
            for pad in (8, 30):
                box = win(min(A["x"], B["x"]) - pad, min(A["y"], B["y"]) - pad,
                          max(A["x"], B["x"]) + pad, max(A["y"], B["y"]) + pad)
                path = astar(free, vok, sa, sb, box)
                if path: break
            if path:
                t, v = to_geom(path, (A["x"], A["y"]), (B["x"], B["y"]), net, w)
                for s in t: Rs.seg(LAYERS.index(s["layer"]), s["a"], s["b"], s["w"], n)
                for o in v: Rs.add_via(o["x"], o["y"], VIA_D, n)
                out_t += t; out_v += v
                print("routed %-12s w=%.3f  %d segs %d vias" % (net, w, len(t), len(v)))
                done = True; break
        if not done:
            fails.append(net); print("FAILED %s (%.1f,%.1f)->(%.1f,%.1f)" % (net, A["x"], A["y"], B["x"], B["y"]))
    json.dump(dict(tracks=out_t, vias=out_v), open(opath, "w"))
    print("done: %d routed, %d failed %s" % (len(order) - len(fails), len(fails), fails))

NORIP = "--norip" in sys.argv
if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
