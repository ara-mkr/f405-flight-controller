# -*- coding: utf-8 -*-
"""In2.Cu power-plane partitioning, computed from where the loads actually are.

DESIGN_PLAN sec 7.1 gives In2 to the power pours (VBAT / +9V / +5V / +3V3). It
does not say where each rail's territory ends, and the hand-drawn rectangles
that used to do that job had drifted badly out of step with the placement: only
46 of the 80 power pads sat over their own pour, so the other 34 got a via down
to a plane carrying a different net. Those vias connect nothing, KiCad's
connectivity pass absorbs them into the ground plane on the next save, and they
then read as shorts.

Each rail's territory is instead assigned by nearest-pad (a discrete Voronoi over
In2), so every power pad is over its own copper by construction. The regions are
emitted as axis-aligned rectangles - one zone each - which KiCad fills with the
usual inter-zone clearance.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import board

CELL = 1.5                      # partition resolution, mm
SMOOTH = 0                      # majority passes; measured to cost pad coverage
                                # without meaningfully cutting the zone count
RAILS = ("+3V3", "+5V", "+9V", "VBAT")

def partition(pads, margin=0.35, keepouts=()):
    """{net: [(x0,y0,x1,y1), ...]} tiling the board, nearest power pad wins."""
    x0, y0 = margin, margin
    x1, y1 = board.W - margin, board.H - margin
    nx = int((x1-x0)/CELL) + 1
    ny = int((y1-y0)/CELL) + 1
    xs = x0 + np.arange(nx)*CELL
    ys = y0 + np.arange(ny)*CELL
    X, Y = np.meshgrid(xs, ys)

    best_d = np.full(X.shape, np.inf)
    best_i = np.full(X.shape, -1, int)
    for i, rail in enumerate(RAILS):
        pts = [(p[3], p[4]) for p in pads if p[2] == rail]
        if not pts: continue
        d = np.full(X.shape, np.inf)
        for px, py in pts:
            np.minimum(d, np.hypot(X-px, Y-py), out=d)
        take = d < best_d
        best_d[take] = d[take]; best_i[take] = i

    # Smooth the boundaries: a raw nearest-pad partition is ragged and each
    # jag becomes another zone for KiCad to fill. A few majority passes cost a
    # little accuracy at the edges and cut the zone count by roughly 5x.
    for _ in range(SMOOTH):
        nb = np.stack([np.roll(np.roll(best_i, dy, 0), dx, 1)
                       for dy in (-1, 0, 1) for dx in (-1, 0, 1)])
        maj = np.zeros_like(best_i)
        for i in range(len(RAILS)):
            cnt = (nb == i).sum(0)
            maj = np.where(cnt > (nb >= 0).sum(0)/2, i, maj)
        keep = (nb >= 0).sum(0) > 0
        best_i = np.where(keep, maj, best_i)

    # the gyro sits over a hole in the power plane (DESIGN_PLAN sec 7.2)
    for (kx0, ky0, kx1, ky1) in keepouts:
        best_i[(X >= kx0) & (X <= kx1) & (Y >= ky0) & (Y <= ky1)] = -1

    out = {}
    for i, rail in enumerate(RAILS):
        out[rail] = _rects(best_i == i, xs, ys, best_i, i)
    return out

def masks(regions, NY, NX, G):
    """{net: bool array on the router grid} - where each rail's copper lives."""
    import numpy as _np
    out = {}
    for net, rs in regions.items():
        m = _np.zeros((NY, NX), bool)
        for (x0, y0, x1, y1) in rs:
            i0 = max(0, int(x0/G)); i1 = min(NX, int(x1/G)+1)
            j0 = max(0, int(y0/G)); j1 = min(NY, int(y1/G)+1)
            m[j0:j1, i0:i1] = True
        out[net] = m
    return out

def _rects(mask, xs, ys, owner=None, me=None):
    """Cover a boolean grid with axis-aligned rectangles, greedily.

    Each rectangle is grown right as far as the row allows and then down as far
    as the full width stays inside the mask. Merging only identical runs (the
    obvious approach) leaves a staircase of one-row slivers - this cuts the zone
    count by roughly three times on the same partition.
    """
    m = mask.copy()
    ny, nx = m.shape
    rects = []
    half = CELL/2
    for j in range(ny):
        i = 0
        while i < nx:
            if not m[j, i]: i += 1; continue
            k = i
            while k+1 < nx and m[j, k+1]: k += 1
            j2 = j
            while j2+1 < ny and m[j2+1, i:k+1].all(): j2 += 1
            m[j:j2+1, i:k+1] = False
            # Grow a side that borders more of our own copper so the pieces of
            # one rail stay electrically continuous; pull back from a side that
            # borders a different rail so the two zones do not touch. KiCad
            # rejects intersecting zones outright unless their priorities differ,
            # and touching zones of different nets are a fill conflict.
            GROW, BACK = half, 0.10
            def side(cells_):
                if owner is None: return -BACK
                vals = [owner[b, a] for (b, a) in cells_
                        if 0 <= b < ny and 0 <= a < nx]
                if not vals: return -BACK                 # board edge
                return GROW if all(v == me for v in vals) else -BACK
            dl = side([(b, i-1) for b in range(j, j2+1)])
            dr = side([(b, k+1) for b in range(j, j2+1)])
            dt = side([(j-1, a) for a in range(i, k+1)])
            db = side([(j2+1, a) for a in range(i, k+1)])
            rects.append((xs[i]-half-dl, ys[j]-half-dt,
                          xs[k]+half+dr, ys[j2]+half+db))
            i = k+1
    return rects
