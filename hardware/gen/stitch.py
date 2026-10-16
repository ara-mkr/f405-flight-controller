# -*- coding: utf-8 -*-
"""Ground stitching.

Signal routing and the power-pad-to-plane vias live in route.py. What is left
here is the ground work, which is not routing at all:

  * a via array under every exposed thermal pad (DESIGN_PLAN sec 7.3 asks for
    >= 9 x 0.3 mm under each TPS54360 PowerPAD, down to the In1 ground plane)
  * a coarse stitching grid tying the F.Cu and B.Cu ground pours to that plane

GND signal pads need no via of their own - they sit inside the outer pours and
the zone fill connects them directly.

Everything here places vias through route.py's rasterised clearance model rather
than its own float comparisons. The previous version compared centre distances
pad by pad and let same-net vias sit 0 mm apart, which is what produced the
shorting_items, hole_clearance and solder_mask_bridge errors and four
hole-to-hole violations at 0.00 mm.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import route, board

VIA_D, VIA_DRILL = route.VIA_D, route.VIA_DRILL
GRID_MM = 3.0            # stitching pitch: ~ lambda/20 at the 600 kHz harmonics
HOLE_TO_HOLE = 0.5       # fc_f405.kicad_dru "hole to hole"

def _via_ok(copper, ok, gnd, vias):
    """Cells where a GND via may be dropped, given what is already there."""
    fv = route._free(copper, gnd, route.CLEAR + VIA_D/2 + route.G/2)
    m = fv.all(axis=0) & ok
    # hole-to-hole applies between same-net vias too - the old code skipped that
    # check for matching nets and produced 0.00 mm hole separations
    for (vx, vy, _n) in vias:
        r = VIA_DRILL + HOLE_TO_HOLE
        x0 = max(0, route.to_g(vx-r)); x1 = min(route.NX, route.to_g(vx+r)+1)
        y0 = max(0, route.to_g(vy-r)); y1 = min(route.NY, route.to_g(vy+r)+1)
        if x1 <= x0 or y1 <= y0: continue
        ys, xs = np.mgrid[y0:y1, x0:x1]
        m[y0:y1, x0:x1] &= np.hypot(xs*route.G-vx, ys*route.G-vy) >= r
    return m

def _knock(m, x, y):
    """Clear the cells a newly placed via forbids to the next one."""
    r = max(VIA_D + route.CLEAR, VIA_DRILL + HOLE_TO_HOLE)
    x0 = max(0, route.to_g(x-r)); x1 = min(route.NX, route.to_g(x+r)+1)
    y0 = max(0, route.to_g(y-r)); y1 = min(route.NY, route.to_g(y+r)+1)
    if x1 <= x0 or y1 <= y0: return
    ys, xs = np.mgrid[y0:y1, x0:x1]
    m[y0:y1, x0:x1] &= np.hypot(xs*route.G-x, ys*route.G-y) >= r

def build(final, parts, code, copper, ok, pads, vias, via_free=None):
    """Append thermal and stitching vias to `vias`. Returns (added, thermal)."""
    gnd = code["GND"]
    added = thermal = 0
    m = _via_ok(copper, ok, gnd, vias)
    if via_free is not None: m &= via_free

    def drop(x, y):
        nonlocal added
        vias.append((x, y, "GND"))
        for L in range(route.NL):
            route.stamp_disc(copper[L], x, y, VIA_D/2, gnd)
        _knock(m, x, y)
        added += 1

    # 1. thermal via arrays under the exposed pads
    for ref, pn, net, x, y, w, h, lay, pth in sorted(
            pads, key=lambda p: -(p[5]*p[6])):
        if net != "GND" or w < 2.0 or h < 2.0: continue
        nx, ny = max(2, int(w // 1.2)), max(2, int(h // 1.2))
        for i in range(nx):
            for j in range(ny):
                vx = round(x - w/2 + w*(i+0.5)/nx, 2)
                vy = round(y - h/2 + h*(j+0.5)/ny, 2)
                gi, gj = route.to_g(vx), route.to_g(vy)
                if 0 <= gj < route.NY and 0 <= gi < route.NX and m[gj, gi]:
                    drop(vx, vy); thermal += 1

    # 2. coarse stitching grid over both outer pours
    x = GRID_MM
    while x < board.W:
        y = GRID_MM
        while y < board.H:
            gi, gj = route.to_g(x), route.to_g(y)
            if 0 <= gj < route.NY and 0 <= gi < route.NX and m[gj, gi]:
                drop(round(x, 2), round(y, 2))
            y += GRID_MM
        x += GRID_MM
    return added, thermal
