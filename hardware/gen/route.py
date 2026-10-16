# -*- coding: utf-8 -*-
"""Deterministic grid router for fc_f405.

Why a router lives in this repo at all: freerouting 2.1.0 throws
NullPointerExceptions in its maze router on this board and gets worse pass over
pass, and the DSN round trip needs three separate hand surgeries before it will
even place a via. Everything else here is generated from design.py, so the
routing is generated too - same inputs, same board, every time.

Model
-----
Four layers. DESIGN_PLAN sec 7.1 gave In2 to the power pours; measurement showed
the two signal layers need 75% of their free area for the signal nets alone, well
past what any maze router closes, so In2 is now a mixed power/signal layer (put
to the user and approved):

  F.Cu    signal + components + GND pour
  In1.Cu  solid, uninterrupted GND plane - untouched. This is the reference
          under every trace and under the gyro (sec 7.2)
  In2.Cu  routing, carrying the power rails as wide traces at their sec 7.5
          widths, with a GND pour filling whatever is left over
  B.Cu    signal + components + GND pour

GND still needs no tracks - it is the two outer pours plus the In1 plane, tied
together by stitching vias - but every other net, power rails included, is now
routed rather than dropped onto a plane.

Geometry is rasterised onto a 0.1 mm grid. Obstacles are rasterised *outward*
(a superset of the true copper), so any cell the router considers free is at
least its dilation radius away from real copper - the rounding can only ever be
conservative. All footprint rotations are multiples of 90 degrees, so every pad
stays an axis-aligned rectangle and no polygon fill is needed.

Search is a multi-source wavefront BFS over a (2, H, W) grid with layer changes
allowed wherever a via would be legal. Among equal-length paths the backtrack
prefers staying on the layer it is already on, which keeps the via count down
without needing a weighted queue.
"""
import sys, os, math, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy import ndimage
import place, board, design, geom

G          = 0.1        # grid pitch, mm
TRACE_W    = 0.2        # default signal trace width
CLEAR      = 0.2        # copper clearance from the net class
VIA_D      = 0.6
VIA_DRILL  = 0.3
# fc_f405.kicad_dru "hole to hole" is 0.5 mm edge to edge, and two 0.6 mm via
# pads on different nets need 0.2 mm between them. Both come out at 0.8 mm centre
# to centre, and it applies to same-net vias too - _free() treats same-net copper
# as free, so without this vias landed on top of each other.
VIA_PITCH  = 0.8
# The BFS validates cell CENTRES, but an emitted 45-degree segment runs between
# them and its midpoint sits up to half a cell diagonal (0.071 mm) further out
# than either centre. Padding a TRACE's clearance by one cell keeps the real gap
# at or above the 0.2 mm rule instead of 0.106 mm at the worst diagonal.
#
# It does NOT apply to a via: a via is a disc centred on the grid point the
# search validated, so there is no interpolation error to absorb. Charging it
# the margin anyway cost 0.2 mm across the LQFP escape ring - the gap between
# the MCU's pads and its neighbours' is 1.05 mm and a via needs 1.0 mm of that,
# so the spurious margin left only 10% of the ring usable and 29 of 53 pins with
# nowhere to escape to.
QUANT      = G
# fc_f405.kicad_dru asks 0.3 mm, but the board setup carries
# min_copper_edge_clearance = 0.5 and DRC applies whichever is stricter.
EDGE_CLR   = 0.5
PLANE_NETS = ("+3V3", "+5V", "+9V", "VBAT")

# minimum widths from fc_f405.kicad_dru sec 7.5; the stub to a plane via has to
# satisfy the same rule the DRC applies to the net
NET_W = {"VBAT": 2.0, "VBAT_IN": 2.0,          # 3 A worst case at 3S (sec 1)
         "SW_5V": 1.0, "SW_9V": 1.0,           # 26 V at 600 kHz, short and wide
         "+5V": 0.8, "+9V": 0.8,
         "+3V3": 0.4, "+3V3_GYRO": 0.4}

# sec 7.2: nothing switching may pass under the gyro. Motor outputs and the two
# switch nodes are kept out of a disc around it on every layer.
GYRO_EXCLUDE = 3.5
def _noisy(net):
    return net.startswith("MOTOR") or net in ("SW_5V", "SW_9V")

NX = int(round(board.W / G)) + 1
NY = int(round(board.H / G)) + 1

def cells(mm):      return int(math.ceil(mm / G - 1e-9))
def to_g(v):        return int(round(v / G))
def to_mm(i):       return round(i * G, 3)

# --------------------------------------------------------------------- pads
def pad_list(final, parts):
    """[(ref, pad, net, x, y, w, h, layers, pth)] with rotation applied.

    The pad's own (at x y angle) and the footprint's orientation both matter:
    on an LQFP the left/right pads carry a 90 degree angle of their own, so
    taking the footprint rotation alone transposes the wrong ones and the
    package silently self-shorts.
    """
    out = []
    for ref, (px, py, rot, side) in final.items():
        txt = open(geom.fp_path(parts[ref]["fp"])).read()
        pos = 0
        while True:
            m = re.compile(r'\(pad\s+"([^"]*)"\s+(\S+)').search(txt, pos)
            if not m: break
            end = geom.span(txt, m.start()); b = txt[m.start():end]; pos = end
            at = re.search(r'\(at (-?[\d.]+) (-?[\d.]+)(?: (-?[\d.]+))?\)', b)
            sz = re.search(r'\(size ([\d.]+) ([\d.]+)\)', b)
            if not (at and sz): continue
            lx, ly = float(at.group(1)), float(at.group(2))
            pa     = float(at.group(3) or 0.0)
            w, h   = float(sz.group(1)), float(sz.group(2))
            if side == 'B': ly, pa = -ly, -pa
            # KiCad's board Y axis points DOWN, so a footprint's children
            # rotate by -theta in file coordinates. Using +theta swapped pad 1
            # and pad 2 on every 90-degree part - 140 of 434 pads landed on the
            # wrong number, so the router was wiring nets to the wrong end of
            # the component.
            a = math.radians(rot)
            ax = px + lx*math.cos(a) + ly*math.sin(a)
            ay = py - lx*math.sin(a) + ly*math.cos(a)
            if int(round(pa + rot)) % 180 == 90: w, h = h, w
            pth = "thru_hole" in b
            if pth:              lay = {'F', 'I2', 'B'}  # the barrel crosses In2
            elif side == 'B':    lay = {'B'}
            else:                lay = {'F'}
            out.append((ref, m.group(1), parts[ref]["pins"].get(m.group(1)),
                        ax, ay, w, h, lay, pth))
    return out

# ------------------------------------------------------------------- canvas
_bm = {}
def board_mask(w=TRACE_W):
    """True where a track centre of width `w` is allowed by the outline.

    The margin has to scale with the trace: a 0.4 mm +5V track laid on the
    0.2 mm-trace mask put copper 0.2 mm from the edge against a 0.3 mm rule.
    """
    if w in _bm: return _bm[w]
    ys, xs = np.mgrid[0:NY, 0:NX]
    X, Y = xs*G, ys*G
    m = EDGE_CLR + w/2
    ok = (X >= m) & (Y >= m) & (X <= board.W-m) & (Y <= board.H-m)
    R = board.CORNER_R
    for cx, cy in ((R,R), (board.W-R,R), (R,board.H-R), (board.W-R,board.H-R)):
        q = (((X-cx)*(1 if cx < board.W/2 else -1) < 0) &
             ((Y-cy)*(1 if cy < board.H/2 else -1) < 0))
        ok &= ~(q & (np.hypot(X-cx, Y-cy) > R - m))
    # DESIGN_PLAN sec 7.4: 1.5 mm keep-out ring, no traces and no components
    for hx, hy in board.HOLE_XY:
        ok &= np.hypot(X-hx, Y-hy) >= board.HOLE_KEEPOUT_R + w/2
    _bm[w] = ok
    return ok

def blank_copper():
    return np.zeros((NL, NY, NX), np.int32)    # 0 = free, otherwise net code

LAYER = {'F': 0, 'I2': 1, 'B': 2}
LNAME = ("F.Cu", "In2.Cu", "B.Cu")
NL    = 3

def stamp_rect(arr, x, y, w, h, val, grow=0.0):
    x0 = max(0, int(math.floor((x-w/2-grow)/G)));  x1 = min(NX-1, int(math.ceil((x+w/2+grow)/G)))
    y0 = max(0, int(math.floor((y-h/2-grow)/G)));  y1 = min(NY-1, int(math.ceil((y+h/2+grow)/G)))
    if x1 >= x0 and y1 >= y0: arr[y0:y1+1, x0:x1+1] = val

def stamp_disc(arr, x, y, r, val, grow=True):
    """Rasterise a disc. `grow` rounds OUTWARD by half a cell so the raster is a
    superset of the real copper - painting only the cells whose centre falls
    inside the radius under-reports the copper, and the next via then sits up to
    0.07 mm closer than the clearance rule allows."""
    if grow: r = r + G/2
    return _stamp_disc(arr, x, y, r, val)

def _stamp_disc(arr, x, y, r, val):
    x0 = max(0, int(math.floor((x-r)/G))); x1 = min(NX-1, int(math.ceil((x+r)/G)))
    y0 = max(0, int(math.floor((y-r)/G))); y1 = min(NY-1, int(math.ceil((y+r)/G)))
    if x1 < x0 or y1 < y0: return
    ys, xs = np.mgrid[y0:y1+1, x0:x1+1]
    arr[y0:y1+1, x0:x1+1] = np.where(np.hypot(xs*G-x, ys*G-y) <= r,
                                     val, arr[y0:y1+1, x0:x1+1])

def paint_pads(copper, pads, code):
    for ref, pn, net, x, y, w, h, lay, pth in pads:
        v = code.get(net, -1) if net and net != "!NC" else -1
        for L in lay: stamp_rect(copper[LAYER[L]], x, y, w, h, v)

def paint_seg(copper, x1, y1, x2, y2, w, layer, val):
    """Rasterise a round-capped segment in one vectorised pass.

    Sampling discs every half cell along the line meant hundreds of calls per
    track, and the rip-up pass repaints every track it keeps - that alone was
    most of the router's runtime.
    """
    r = w/2 + G/2          # round outward, as stamp_disc does
    i0 = max(0, int(math.floor((min(x1, x2)-r)/G))); i1 = min(NX-1, int(math.ceil((max(x1, x2)+r)/G)))
    j0 = max(0, int(math.floor((min(y1, y2)-r)/G))); j1 = min(NY-1, int(math.ceil((max(y1, y2)+r)/G)))
    if i1 < i0 or j1 < j0: return
    ys, xs = np.mgrid[j0:j1+1, i0:i1+1]
    px, py = xs*G - x1, ys*G - y1
    dx, dy = x2-x1, y2-y1
    L2 = dx*dx + dy*dy
    t = 0.0 if L2 == 0 else np.clip((px*dx + py*dy)/L2, 0.0, 1.0)
    d = np.hypot(px - t*dx, py - t*dy)
    sub = copper[layer][j0:j1+1, i0:i1+1]
    copper[layer][j0:j1+1, i0:i1+1] = np.where(d <= r, val, sub)

# --------------------------------------------------------------------- BFS
def _free(copper, net, radius):
    """Cells whose centre is >= `radius` mm from copper of any other net.

    Via a Euclidean distance transform rather than a binary dilation: the
    dilation cost grows with the square of the radius, and VBAT at its sec 7.5
    width of 2.0 mm needs a 27x27 structuring element over three layers, which
    took seconds per call. The transform is linear in the grid size whatever the
    radius, and the result is exact rather than a discretised disc.
    """
    bad = (copper != 0) & (copper != net)
    if radius <= 0: return ~bad
    out = np.empty(bad.shape, bool)
    for L in range(bad.shape[0]):
        d = ndimage.distance_transform_edt(~bad[L], sampling=G)
        out[L] = d >= radius
    return out

def search(copper, via_free, net, src, dst, allow_via=True, w=TRACE_W,
           margin=6.0, block=None):
    """Wavefront BFS. src/dst are boolean (2,NY,NX) masks. Returns a cell path.

    The wave is run inside a window around the two endpoints, not over the whole
    board: a full-board dilation per wavefront step costs milliseconds and a
    long net needs hundreds of steps, which put a single connection into the
    tens of seconds. The window is grown and retried if the first attempt is
    boxed in.
    """
    idx = np.argwhere(src | dst)
    if not len(idx): return None
    for grow in (margin, margin*3, max(board.W, board.H)):
        pad = cells(grow)
        y0 = max(0, int(idx[:,1].min()) - pad); y1 = min(NY, int(idx[:,1].max()) + pad + 1)
        x0 = max(0, int(idx[:,2].min()) - pad); x1 = min(NX, int(idx[:,2].max()) + pad + 1)
        # The clearance dilation is computed over the WHOLE board and only then
        # cropped. Dilating the cropped copper instead treats everything outside
        # the window as empty, so copper just beyond the edge stops blocking and
        # traces and vias land on top of pads - that was 51 shorts.
        okw = board_mask(w)[y0:y1, x0:x1]
        if block is not None: okw = okw & ~block[y0:y1, x0:x1]
        s_  = src[:, y0:y1, x0:x1]
        d_  = dst[:, y0:y1, x0:x1]
        free_t = _free(copper, net, CLEAR + w/2 + QUANT)[:, y0:y1, x0:x1] & okw[None, :, :]
        free_t |= s_ | d_                     # a pad's own copper is reachable
        if allow_via:
            fv = _free(copper, net, CLEAR + VIA_D/2 + G/2)
            # a through via crosses every layer, so it must be clear on all of them
            free_v = fv.all(axis=0)[y0:y1, x0:x1] & okw & via_free[y0:y1, x0:x1]
        else:
            free_v = np.zeros(okw.shape, bool)
        h_, w_ = okw.shape
        dist = np.full((NL, h_, w_), -1, np.int32)
        cur = s_ & free_t
        if not cur.any(): continue
        dist[cur] = 0
        se = np.ones((3, 3), bool)
        hit = None
        for d in range(1, 2*(h_ + w_) + 8):
            nxt = np.empty_like(cur)
            for L in range(NL):
                nxt[L] = ndimage.binary_dilation(cur[L], se, border_value=0)
            if allow_via:
                reach = cur.any(axis=0) & free_v   # one through via joins them all
                for L in range(NL): nxt[L] |= reach
            nxt &= free_t & (dist < 0)
            if not nxt.any(): break
            dist[nxt] = d
            if (nxt & d_).any():
                hit = (np.argwhere(nxt & d_)[0], d); break
            cur = nxt
        if hit is None: continue
        p = _backtrack(dist, free_v, tuple(hit[0]), hit[1], allow_via, h_, w_)
        if p is None: continue
        return [(L, y + y0, x + x0) for (L, y, x) in p]
    return None

def _backtrack(dist, free_v, end, d, allow_via, NYw, NXw):
    """Walk the distance field back to a source, preferring straight runs.

    Among equal-length paths a plain BFS picks an arbitrary one, which comes out
    as a staircase; a staircase sterilises a much wider corridor than the 45
    degree run it is equivalent to, and on a board this dense that congestion is
    what stops later nets routing. Continuing in the current direction first, and
    only then changing layer, keeps the paths straight and the via count low.
    """
    path = [end]
    L, y, x = end
    pdy = pdx = 0
    last_via = None          # vias within one path must respect the same pitch
    while d > 0:
        found = None
        dirs = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                if (dy, dx) != (0, 0)]
        if (pdy, pdx) != (0, 0):
            dirs.sort(key=lambda v: (v != (pdy, pdx),
                                     abs(v[0]-pdy) + abs(v[1]-pdx)))
        for dy, dx in dirs:
            ny_, nx_ = y+dy, x+dx
            if 0 <= ny_ < NYw and 0 <= nx_ < NXw and dist[L, ny_, nx_] == d-1:
                found = (L, ny_, nx_); pdy, pdx = dy, dx; break
        # A layer change is a via, so it may only happen in place and only where
        # a via is actually legal. The old fallback below accepted a predecessor
        # on the other layer at a DIFFERENT cell, which simplify() then emitted
        # as a via at the wrong position and which nothing had checked for via
        # clearance - that produced vias sitting on top of other nets' pads.
        if found is None and allow_via and free_v[y, x] and (
                last_via is None or
                math.hypot(y-last_via[0], x-last_via[1])*G >= VIA_PITCH):
            for L2 in range(NL):
                if L2 != L and dist[L2, y, x] == d-1:
                    found = (L2, y, x); pdy = pdx = 0; last_via = (y, x); break
        if found is None: return None
        path.append(found); L, y, x = found; d -= 1
    path.reverse()
    return path

def simplify(path):
    """Collapse the cell path into straight runs and via transitions."""
    out = []
    i = 0
    while i < len(path) - 1:
        L, y, x = path[i]
        if path[i+1][0] != L:                       # via: must be in place
            assert (path[i+1][1], path[i+1][2]) == (y, x), "layer change moved"
            out.append(("via", to_mm(x), to_mm(y))); i += 1; continue
        j = i + 1
        dy, dx = path[j][1]-y, path[j][2]-x
        while (j + 1 < len(path) and path[j+1][0] == L and
               (path[j+1][1]-path[j][1], path[j+1][2]-path[j][2]) == (dy, dx)):
            j += 1
        out.append(("seg", L, to_mm(x), to_mm(y), to_mm(path[j][2]), to_mm(path[j][1])))
        i = j
    return out

# ------------------------------------------------------------------ driver
# DRU minimums: the rails carry an explicit min-width rule, everything else the
# board-setup default.
def net_min(net):
    return 0.25 if net in NET_W else TRACE_W

def net_width(net):
    return NET_W.get(net, TRACE_W)

def route_width(net):
    """Width to SEARCH at - kept modest so a rail can still find a path.

    Searching at VBAT's full 2.0 mm sterilises a 2.4 mm corridor and almost
    nothing routes. The path is found narrow and each segment is then widened to
    whatever the surrounding copper actually allows, up to the sec 7.5 figure.
    """
    return min(net_width(net), 0.4)

def dist_field(copper, net):
    """Distance in mm from every cell to the nearest copper of another net."""
    bad = (copper != 0) & (copper != net)
    out = np.empty(bad.shape, float)
    for L in range(bad.shape[0]):
        out[L] = ndimage.distance_transform_edt(~bad[L], sampling=G)
    return out

def plan(final, parts, code, plane_mask=None):
    """Route everything. Returns (tracks, vias, report)."""
    pads = pad_list(final, parts)
    ok   = board_mask()
    copper = blank_copper()
    paint_pads(copper, pads, code)

    tracks, vias = [], []
    via_free = np.ones((NY, NX), bool)      # cleared around every via placed

    def note_via(x, y):
        r = VIA_PITCH
        x0 = max(0, to_g(x-r)); x1 = min(NX, to_g(x+r)+1)
        y0 = max(0, to_g(y-r)); y1 = min(NY, to_g(y+r)+1)
        if x1 <= x0 or y1 <= y0: return
        ys, xs = np.mgrid[y0:y1, x0:x1]
        via_free[y0:y1, x0:x1] &= np.hypot(xs*G-x, ys*G-y) >= r
    rep = {"signal_ok": 0, "signal_fail": [], "power_ok": 0, "power_fail": [],
           "rips": 0}

    by_net = {}
    for p in pads:
        if p[2] and p[2] != "!NC": by_net.setdefault(p[2], []).append(p)

    def emit(path, net, w):
        nc = code[net]
        # computed once per path: dist_field excludes same-net copper, so the
        # segments this path is about to lay down do not change it
        df = dist_field(copper, nc)
        for item in simplify(path):
            if item[0] == "via":
                _, x, y = item
                vias.append((x, y, net)); note_via(x, y)
                for L in range(NL): stamp_disc(copper[L], x, y, VIA_D/2, nc)
            else:
                _, L, x1, y1, x2, y2 = item
                if (x1, y1) == (x2, y2): continue
                ww = _fit_width(df, L, x1, y1, x2, y2, net)
                tracks.append((x1, y1, x2, y2, net, LNAME[L], ww))
                paint_seg(copper, x1, y1, x2, y2, ww, L, nc)

    def _escape_room(p, nc):
        """How many free cells touch this pad - 0 means it cannot be left."""
        m = np.zeros((NY, NX), bool)
        stamp_rect(m, p[3], p[4], p[5], p[6], True)
        halo = ndimage.binary_dilation(m, np.ones((3, 3), bool)) & ~m
        f = _free(copper, nc, CLEAR + TRACE_W/2)
        return int(sum((halo & f[LAYER[L]] & ok).sum() for L in p[7]))

    def _fit_width(df, L, x1, y1, x2, y2, net):
        """As wide as the surrounding copper allows, capped at the sec 7.5 width.

        Sampling the distance field along the segment is what keeps a widened
        VBAT trace from swallowing a neighbouring GND pad - forcing a pad's own
        cells free is sound for a 0.2 mm trace but a 2.0 mm one reaches 1 mm past
        the pad edge.
        """
        fl = df[L]
        n = max(2, int(math.hypot(x2-x1, y2-y1)/G))
        worst = None
        for i in range(n+1):
            t = i/n
            gi = min(NX-1, max(0, to_g(x1+(x2-x1)*t)))
            gj = min(NY-1, max(0, to_g(y1+(y2-y1)*t)))
            d = fl[gj, gi]
            if worst is None or d < worst: worst = d
        avail = 2.0*(worst - CLEAR - QUANT)
        return round(min(net_width(net), max(net_min(net), avail)), 2)

    def pad_mask(p):
        m = np.zeros((NL, NY, NX), bool)
        _, _, _, x, y, w, h, lay, _ = p
        for L in lay:
            t = np.zeros((NY, NX), bool); stamp_rect(t, x, y, w, h, True)
            m[LAYER[L]] = t
        return m

    # ---- route every net except GND, shortest span first
    def span_of(ps):
        xs = [p[3] for p in ps]; ys = [p[4] for p in ps]
        return (max(xs)-min(xs)) + (max(ys)-min(ys))
    # GND is still the two outer pours plus the In1 plane, so it is never
    # routed; everything else, power rails included, is.
    sig = [(n, ps) for n, ps in by_net.items() if n != "GND" and len(ps) > 1]
    sig.sort(key=lambda kv: (span_of(kv[1]), len(kv[1])))

    gx, gy = final["U2"][0], final["U2"][1]
    _ys, _xs = np.mgrid[0:NY, 0:NX]
    _gyro = np.hypot(_xs*G - gx, _ys*G - gy) < GYRO_EXCLUDE

    def connect(net, ps, conn=None, done=None, todo=None):
        """Grow one net's island until every pad is on it. Returns the stragglers."""
        w = route_width(net); nc = code[net]
        if conn is None:
            # Seed from the pad with the most room around it, not ps[0]. Seeding
            # on an enclosed pad makes the island unable to grow and every other
            # pad of the net then fails - that is what took out all 7 pads of
            # +3V3_GYRO at once.
            seed = max(ps, key=lambda q: _escape_room(q, nc))
            rest = [q for q in ps if q is not seed]
            conn = pad_mask(seed); done = [seed]; todo = list(rest)
        stuck = []
        # A pad that cannot be reached from the island yet may well be reachable
        # once the island has grown towards it, so failures go to the back of the
        # queue instead of being dropped. Keep going while any pass makes progress.
        while todo:
            progressed = False
            todo.sort(key=lambda q: min(math.hypot(q[3]-d[3], q[4]-d[4]) for d in done))
            for tgt in list(todo):
                path = search(copper, via_free, nc, conn, pad_mask(tgt), w=w,
                              block=_gyro if _noisy(net) else None)
                if path is None: continue
                emit(path, net, w)
                for (L, y, x) in path: conn[L, y, x] = True
                conn |= pad_mask(tgt)
                done.append(tgt); todo.remove(tgt)
                rep["signal_ok"] += 1; progressed = True
            if not progressed:
                stuck = list(todo); break
        return conn, done, stuck

    state = {}
    for net, ps in sig:
        state[net] = connect(net, ps)

    # ---- 3. rip-up and retry. A connection that lost a race for a channel is
    #         often routable once whatever took that channel is lifted and put
    #         back afterwards, so each straggler gets one attempt with the nets
    #         crossing its bounding box removed.
    def rebuild():
        """Re-raster everything from scratch. Erasing a ripped net by painting
        zeros over its footprint also wiped whatever else shared those cells -
        neighbouring pads included - so the next net routed straight through
        them and shorted. Rebuilding is a few milliseconds and is exact."""
        copper[:] = 0
        via_free[:] = True
        paint_pads(copper, pads, code)
        for (x1, y1, x2, y2, n, lay, w) in tracks:
            paint_seg(copper, x1, y1, x2, y2, w, LNAME.index(lay), code[n])
        for (x, y, n) in vias:
            for L in range(NL): stamp_disc(copper[L], x, y, VIA_D/2, code[n])
            note_via(x, y)

    def rip(net):
        removed = ([t for t in tracks if t[4] == net], [v for v in vias if v[2] == net])
        tracks[:] = [t for t in tracks if t[4] != net]
        vias[:]   = [v for v in vias if v[2] != net]
        rebuild()
        return removed

    for net, ps in sig:
        conn, done, stuck = state[net]
        for tgt in list(stuck):
            x0 = min(tgt[3], min(d[3] for d in done)) - 3
            x1 = max(tgt[3], max(d[3] for d in done)) + 3
            y0 = min(tgt[4], min(d[4] for d in done)) - 3
            y1 = max(tgt[4], max(d[4] for d in done)) + 3
            blockers = {t[4] for t in tracks
                        if t[4] != net and t[4] not in PLANE_NETS
                        and x0 <= t[0] <= x1 and y0 <= t[1] <= y1}
            if not blockers or len(blockers) > 6 or rep["rips"] > 200: continue
            rep["rips"] += len(blockers)
            saved = {b: rip(b) for b in blockers}
            path = search(copper, via_free, code[net], conn, pad_mask(tgt),
                          w=route_width(net),
                          block=_gyro if _noisy(net) else None)
            if path is not None:
                emit(path, net, net_width(net))
                for (L, y, x) in path: conn[L, y, x] = True
                conn |= pad_mask(tgt)
                done.append(tgt); stuck.remove(tgt)
                rep["signal_ok"] += 1
            # put the ripped nets back, rerouting them around the new trace
            for b in blockers:
                bps = by_net[b]
                c2, d2, s2 = connect(b, bps)
                state[b] = (c2, d2, s2)
        state[net] = (conn, done, stuck)

    # ---- 4. drop stubs. A rip that could not be put back leaves track ends
    #         touching nothing, which KiCad reports as track_dangling and which
    #         would be a genuine manufacturing defect.
    for _ in range(4):
        ends = {}
        for (x1, y1, x2, y2, n, lay, w) in tracks:
            ends.setdefault(n, []).append((x1, y1)); ends[n].append((x2, y2))
        anchor = {}
        for p in pads:
            if p[2]: anchor.setdefault(p[2], []).append((p[3], p[4], max(p[5], p[6])/2))
        for (vx, vy, vn) in vias: anchor.setdefault(vn, []).append((vx, vy, VIA_D/2))
        drop = []
        for t in tracks:
            x1, y1, x2, y2, n, lay, w = t
            for (ex, ey) in ((x1, y1), (x2, y2)):
                near_pad = any(math.hypot(ex-ax, ey-ay) <= ar + w/2 + G
                               for (ax, ay, ar) in anchor.get(n, []))
                if near_pad: continue
                shared = sum(1 for (ox, oy) in ends.get(n, [])
                             if math.hypot(ex-ox, ey-oy) < G)
                if shared <= 1: drop.append(t); break
        if not drop: break
        dr = set(map(id, drop))
        tracks[:] = [t for t in tracks if id(t) not in dr]
    used = {t[4] for t in tracks}
    vias[:] = [v for v in vias
               if v[2] in used or any(math.hypot(v[0]-p[3], v[1]-p[4]) < VIA_D
                                      for p in pads if p[2] == v[2])]

    need = 0
    for net, (conn, done, stuck) in state.items():
        need += len(by_net[net]) - 1
        for tgt in stuck:
            rep["signal_fail"].append(f"{net}:{tgt[0]}.{tgt[1]}")
    rep["signal_need"] = need
    rep["signal_ok"] = need - len(rep["signal_fail"])
    return tracks, vias, rep, copper, ok, pads, via_free

if __name__ == "__main__":
    import time
    final, failed = place.solve()
    assert not failed, failed
    parts = {c["ref"]: c for c in design.COMPONENTS if c.get("fp")}
    nets = sorted({n for c in parts.values() for n in c["pins"].values()
                   if n and n != "!NC"})
    code = {n: i + 1 for i, n in enumerate(nets)}
    t0 = time.time()
    tr, vi, rep, _c, _o, _p, _vf = plan(final, parts, code)
    print(f"routed in {time.time()-t0:.1f} s")
    print(f"  connections made {rep['signal_ok']} of {rep['signal_need']}, "
          f"failed {len(rep['signal_fail'])}")
    print(f"  {len(tr)} track segments, {len(vi)} vias")
    if rep["signal_fail"]: print("  unrouted:", ", ".join(rep["signal_fail"][:20]))
    if rep["power_fail"]:  print("  no plane via:", ", ".join(rep["power_fail"][:20]))

# ------------------------------------------------------------- self-check
def selfcheck(tracks, vias, pads, code):
    """Audit the router's own output against its own clearance rules.

    Cheap insurance: if this reports nothing but KiCad's DRC still finds
    clearance errors, the disagreement is in the model rather than in the
    search, which is a very different bug to go looking for.
    """
    bad = []
    prect = [(p[2], p[3], p[4], p[5], p[6], p[7]) for p in pads
             if p[2] and p[2] != "!NC"]
    def pad_gap(net, x, y, r, layers):
        worst = None
        for (n2, px, py, w2, h2, lay2) in prect:
            if n2 == net or not (layers & lay2): continue
            dx = max(0.0, abs(x-px) - w2/2); dy = max(0.0, abs(y-py) - h2/2)
            g = math.hypot(dx, dy) - r
            if worst is None or g < worst[0]: worst = (g, n2, px, py)
        return worst
    for (x, y, net) in vias:
        g = pad_gap(net, x, y, VIA_D/2, {'F', 'I2', 'B'})
        if g and g[0] < CLEAR - 1e-6:
            bad.append(f"via {net} @({x:.2f},{y:.2f}) is {g[0]:+.3f} mm from "
                       f"{g[1]} pad @({g[2]:.2f},{g[3]:.2f})")
    for (x1, y1, x2, y2, net, lay, w) in tracks:
        L = {"F.Cu": {'F'}, "In2.Cu": {'I2'}, "B.Cu": {'B'}}[lay]
        n = max(2, int(math.hypot(x2-x1, y2-y1)/0.1))
        for i in range(n+1):
            t = i/n
            g = pad_gap(net, x1+(x2-x1)*t, y1+(y2-y1)*t, w/2, L)
            if g and g[0] < CLEAR - 1e-6:
                bad.append(f"track {net} on {lay} @({x1:.2f},{y1:.2f})-"
                           f"({x2:.2f},{y2:.2f}) is {g[0]:+.3f} mm from {g[1]} pad")
                break
    for i, (x, y, n1) in enumerate(vias):
        for (x2, y2, n2) in vias[i+1:]:
            d = math.hypot(x-x2, y-y2)
            if d < VIA_PITCH - 1e-6:
                bad.append(f"via {n1} @({x:.2f},{y:.2f}) and via {n2} "
                           f"@({x2:.2f},{y2:.2f}) are {d:.3f} mm apart")

    # track vs track and track vs via. Checking only against pads left the whole
    # copper-to-copper class invisible: KiCad's connectivity pass merges two nets
    # whose copper touches and relabels the vias, which is what turned OSD_SAG
    # into VID_NODE and RSSI_ADC into GND on the last save.
    def seg_seg(a, b):
        (ax1, ay1, ax2, ay2), (bx1, by1, bx2, by2) = a, b
        def pt_seg(px, py, x1, y1, x2, y2):
            dx, dy = x2-x1, y2-y1
            L2 = dx*dx + dy*dy
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px-x1)*dx + (py-y1)*dy)/L2))
            return math.hypot(px-x1-t*dx, py-y1-t*dy)
        return min(pt_seg(ax1, ay1, bx1, by1, bx2, by2),
                   pt_seg(ax2, ay2, bx1, by1, bx2, by2),
                   pt_seg(bx1, by1, ax1, ay1, ax2, ay2),
                   pt_seg(bx2, by2, ax1, ay1, ax2, ay2))
    for i, t1 in enumerate(tracks):
        for t2 in tracks[i+1:]:
            if t1[4] == t2[4] or t1[5] != t2[5]: continue
            g = seg_seg(t1[:4], t2[:4]) - t1[6]/2 - t2[6]/2
            if g < CLEAR - 1e-6:
                bad.append(f"track {t1[4]} and track {t2[4]} on {t1[5]} are "
                           f"{g:+.3f} mm apart near ({t1[0]:.2f},{t1[1]:.2f})")
    for (vx, vy, vn) in vias:
        for t in tracks:
            if t[4] == vn: continue
            d = seg_seg((vx, vy, vx, vy), t[:4]) - VIA_D/2 - t[6]/2
            if d < CLEAR - 1e-6:
                bad.append(f"via {vn} @({vx:.2f},{vy:.2f}) is {d:+.3f} mm from "
                           f"track {t[4]} on {t[5]}")
    return bad
