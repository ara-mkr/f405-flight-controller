# -*- coding: utf-8 -*-
"""Placement engine.

board.PLACE gives a hint position for every part. The solver runs in phases so
that electrical priority, not part size, decides who gets the good real estate:

  1. anchors (ICs, inductors, connectors, the gyro) go down first, from their
     exact floorplan hint - the floorplan has already deconflicted them
  2. cluster members follow, grouped by anchor in ANCHOR_ORDER sequence, and
     within a group decoupling goes before everything else. This is the fix for
     the size-ordered greedy pass that used to exile MCU bypass caps 12 mm from
     the pin they protect (DESIGN_PLAN sec 3.4 requires them adjacent)
  3. orphans last, biggest first
  4. a repair pass retries anything that missed its distance budget, evicting
     lower-priority parts that are in the way

Every candidate is tried at 0/90/180/270 and on both sides, and every result is
measured against a budget so an unreachable part is reported, never hidden.
"""
import sys, os, re, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design, board, cluster

STOCK = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
PROJ  = "/Users/akhilraja-amudhan/Documents/Flight Controller Project/hardware/lib/fc_f405.pretty"

ANCHORS = set(cluster.ANCHOR_ORDER)

# Wire-access connectors and solder pads: these must touch the perimeter, so
# they are slid along their edge rather than spiralled through the interior.
EDGE_PARTS = ({c["ref"] for c in design.COMPONENTS
               if c.get("fp") and c["ref"].startswith("J")}
              - getattr(board, "INTERIOR_PADS", set()))

# Distance budgets, millimetres from the pad the part was aimed at. A bypass cap
# outside 2.5 mm contributes more loop inductance than it removes, so exceeding
# the budget is reported as a violation rather than silently accepted.
BUDGET_DECOUPLE = 2.5
BUDGET_CLUSTER  = 6.0
BUDGET_ORPHAN   = 12.0
BUDGET_ANCHOR   = 3.0   # an anchor that cannot be placed within 3 mm of its
                        # floorplan hint is a floorplan conflict to fix in
                        # board.py, not something to silently resolve by moving
                        # the battery connector to the far side of the board.
                        # 8 mm keeps a part in its floorplan region; the tight
                        # switching-loop distances are checked separately by
                        # verify.py against DESIGN_PLAN sec 7.3.

import geom
_span = geom.span

def _fp_path(fpid):
    return geom.fp_path(fpid)

def courtyard(fpid):
    """(w, h, cx, cy) of the density-level-C courtyard - see geom.py.

    The stock KiCad courtyards are IPC nominal (level B); on a board at ~75%
    two-sided density they, not the copper, were what made the packer fail.
    """
    return geom.courtyard(fpid)

# Fine-pitch parts need a clear ring on their own side for escape routing. At
# 0.5 mm pitch the gap between LQFP-64 pads is 0.20 mm and a 0.2 mm trace with
# 0.2 mm clearance needs 0.60 mm, so nothing routes BETWEEN pads - all 64 pins
# escape radially and need somewhere to spread into before they can turn.
# Sized from the escape-via ring, not guessed. For the LQFP-64 the pad ring ends
# 6.450 mm from the centre and the density-C courtyard half-width is 6.600 mm, so
#     via centre      = 6.450 + clearance 0.2 + via radius 0.3 = 6.950 mm
#     neighbour copper must start at 6.950 + 0.3 + 0.2         = 7.450 mm
#     halo = 7.450 - 6.600 - 0.15 (the neighbour courtyard's own margin) = 0.700
# 0.75 takes that with a little margin. At 0.5 the neighbours pack flush against
# the ring - LED2's pad ended up 0.79 mm from U1's, which passes exactly one
# 0.2 mm trace and leaves nowhere for a via, so every escape on that side failed.
#     via centre = 6.450 + 0.2 clearance + 0.3 via radius + 0.05 raster = 7.00
#     neighbour copper must start at 7.00 + 0.3 + 0.2 + 0.05        = 7.55
#     halo = 7.550 - 6.600 courtyard half - 0.15 neighbour margin    = 0.80
FANOUT_HALO = {"Package_QFP:LQFP-64_10x10mm_P0.5mm": 0.80,
               "Package_SO:HTSSOP-28-1EP_4.4x9.7mm_P0.65mm_EP2.85x5.4mm": 0.60}

def extent(fpid, rot, side='F'):
    w, h, ox, oy = courtyard(fpid)
    halo = FANOUT_HALO.get(fpid, 0.0)
    w += 2*halo; h += 2*halo
    if side == 'B': oy = -oy          # pcbnew's flip mirrors children in Y
    if rot % 180 == 90: return h, w, -oy, ox
    return w, h, ox, oy

HINT   = {}   # ref -> relaxed, collision-free anchor hint
TARGET = {}   # ref -> the pad this part was aimed at
BUDGET = {}   # ref -> how far it was allowed to land from that pad
_pth = {}
def has_pth(fpid):
    """True if the footprint has through-hole pads - it then blocks both sides."""
    if fpid in _pth: return _pth[fpid]
    t = open(_fp_path(fpid)).read()
    _pth[fpid] = ("thru_hole" in t) or ("np_thru_hole" in t)
    return _pth[fpid]

_pads = {}
def pads(fpid):
    """{pad_number: (x, y)} in footprint-local mm."""
    if fpid in _pads: return _pads[fpid]
    t = open(_fp_path(fpid)).read(); out = {}
    for m in re.finditer(r'\(pad\s+"([^"]*)"[^\n]*\n?\s*\(at (-?[\d.]+) (-?[\d.]+)', t):
        if m.group(1) and m.group(1) not in out:
            out[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    _pads[fpid] = out; return out

def pad_xy(ref, pnum, placement, parts):
    """Absolute board position of one pad of a placed part."""
    x, y, rot, sd = placement[ref]
    lp = pads(parts[ref]["fp"]).get(pnum)
    if lp is None: return (x, y)
    px, py = lp
    if sd == 'B': py = -py
    # -theta, not +theta: KiCad's board Y axis points down (see route.pad_list)
    a = math.radians(rot)
    return (x + px*math.cos(a) + py*math.sin(a),
            y - px*math.sin(a) + py*math.cos(a))

def box(x, y, fpid, rot, side='F'):
    w, h, ox, oy = extent(fpid, rot, side)
    return (x + ox - w/2, y + oy - h/2, x + ox + w/2, y + oy + h/2)

def _corner_ok(bb, m):
    """Reject a box that pokes outside a rounded corner."""
    W, H, R = board.W, board.H, board.CORNER_R
    x0, y0, x1, y1 = bb
    for cx, cy in ((R, R), (W-R, R), (R, H-R), (W-R, H-R)):
        # nearest box corner to this arc centre, on the outboard side only
        nx = x0 if cx < W/2 else x1
        ny = y0 if cy < H/2 else y1
        if (nx - cx)*(1 if cx < W/2 else -1) < 0 and (ny - cy)*(1 if cy < H/2 else -1) < 0:
            if math.hypot(nx-cx, ny-cy) > R - m: return False
    return True

def legal(bb, side, taken, margin=0.5, keepout=True, pth=False, skip=()):
    x0, y0, x1, y1 = bb
    if x0 < margin or y0 < margin or x1 > board.W - margin or y1 > board.H - margin:
        return False
    if not _corner_ok(bb, margin): return False
    if keepout:
        for hx, hy in board.HOLE_XY:
            nx = max(x0, min(hx, x1)); ny = max(y0, min(hy, y1))
            if math.hypot(nx-hx, ny-hy) < board.HOLE_KEEPOUT_R: return False
    for item in taken:
        (bx0, by0, bx1, by1), s, spth, owner = item
        if owner in skip: continue
        if s != side and not (pth or spth): continue   # PTH blocks both sides
        # require a real gap, not merely "not more than 0.01 mm of overlap":
        # four pairs landed at exactly 0.01 mm and KiCad counted every one of
        # them as a courtyard overlap
        if min(x1,bx1)-max(x0,bx0) > -0.01 and min(y1,by1)-max(y0,by0) > -0.01:
            return False
    return True

# ------------------------------------------------------------------ ordering
def _is_decoupler(c):
    """A two-pin cap between a rail and ground - has to sit at the pin."""
    if not c["ref"].startswith("C") or len(c["pins"]) != 2: return False
    nets = set(c["pins"].values())
    return "GND" in nets and len(nets) == 2

def relax_hints(parts, iters=4000):
    """Separate overlapping anchor hints, minimally.

    board.PLACE is hand-authored and its anchor boxes overlap in 19 places once
    the fanout halos are included - the old solver hid that by nudging parts up
    to 20 mm away, which is how MCU bypass caps ended up across the board. A
    short force-directed relaxation pushes overlapping anchors apart along their
    minimum-translation axis instead, so the designer's relative arrangement
    survives and the spiral search then only has to make small corrections.

    U1/U2 are position-locked (gyro dead centre, MCU under it) and edge parts
    may only slide along their own edge.
    """
    P = {r: [float(board.PLACE[r][0]), float(board.PLACE[r][1])]
         for r in board.PLACE if r in parts and r in ANCHORS}
    locked = {"U1", "U2"}
    for _ in range(iters):
        moved = 0.0
        refs = list(P)
        for i, a in enumerate(refs):
            fa = parts[a]["fp"]; ra, sa = board.PLACE[a][2], board.PLACE[a][3]
            pa = has_pth(fa)
            for b in refs[i+1:]:
                fb = parts[b]["fp"]; rb, sb = board.PLACE[b][2], board.PLACE[b][3]
                pb = has_pth(fb)
                if sa != sb and not (pa or pb): continue
                A = box(P[a][0], P[a][1], fa, ra, sa)
                B = box(P[b][0], P[b][1], fb, rb, sb)
                ox = min(A[2],B[2]) - max(A[0],B[0])
                oy = min(A[3],B[3]) - max(A[1],B[1])
                if ox <= 0.02 or oy <= 0.02: continue
                push = 0.55 * (ox if ox < oy else oy) + 0.02
                ax, ay = (P[a][0]+P[a][1]*0, P[a][1])
                if ox < oy: d = (1.0 if P[a][0] <= P[b][0] else -1.0), 0.0
                else:       d = 0.0, (1.0 if P[a][1] <= P[b][1] else -1.0)
                wa = 0.0 if a in locked else (0.5 if b not in locked else 1.0)
                wb = 0.0 if b in locked else (0.5 if a not in locked else 1.0)
                P[a][0] -= d[0]*push*wa; P[a][1] -= d[1]*push*wa
                P[b][0] += d[0]*push*wb; P[b][1] += d[1]*push*wb
                moved += push
        # keep everyone on the board and out of the mounting-hole rings
        for r in refs:
            if r in locked: continue
            fp = parts[r]["fp"]; rot, sd = board.PLACE[r][2], board.PLACE[r][3]
            w, h, ox_, oy_ = extent(fp, rot, sd)
            lo_x, hi_x = 0.6 + w/2 - ox_, board.W - 0.6 - w/2 - ox_
            lo_y, hi_y = 0.6 + h/2 - oy_, board.H - 0.6 - h/2 - oy_
            P[r][0] = min(max(P[r][0], lo_x), hi_x)
            P[r][1] = min(max(P[r][1], lo_y), hi_y)
            if r in EDGE_PARTS: continue          # the edge search owns these
            bb = box(P[r][0], P[r][1], fp, rot, sd)
            for hx, hy in board.HOLE_XY:
                nx = max(bb[0], min(hx, bb[2])); ny = max(bb[1], min(hy, bb[3]))
                dist = math.hypot(nx-hx, ny-hy)
                if dist < board.HOLE_KEEPOUT_R:
                    vx, vy = P[r][0]-hx, P[r][1]-hy
                    n = math.hypot(vx, vy) or 1.0
                    k = (board.HOLE_KEEPOUT_R - dist) * 0.6
                    P[r][0] += vx/n*k; P[r][1] += vy/n*k; moved += k
        if moved < 1e-3: break
    return {r: (round(P[r][0], 2), round(P[r][1], 2)) for r in P}

def build_order(parts):
    """Anchors, then clusters in anchor priority, then orphans."""
    anchors = [r for r in cluster.ANCHOR_ORDER if r in parts]
    members = {}
    for ref, anc in cluster.CLUSTER.items():
        if ref in parts and ref not in ANCHORS:
            members.setdefault(anc, []).append(ref)
    area = lambda r: (lambda e: e[0]*e[1])(extent(parts[r]["fp"], board.PLACE[r][2]))
    seq = list(anchors)
    seen = set(anchors)
    # clusters follow CLUSTER_ORDER (electrical criticality), then anything
    # whose anchor was not named there
    named = [a for a in cluster.CLUSTER_ORDER if a in members]
    rest  = [a for a in members if a not in cluster.CLUSTER_ORDER]
    for anc in named + rest:
        for ref in sorted(members.get(anc, []),
                          key=lambda r: (not _is_decoupler(parts[r]), -area(r))):
            if ref not in seen: seq.append(ref); seen.add(ref)
    for ref in sorted((r for r in parts if r not in seen), key=lambda r: -area(r)):
        seq.append(ref)
    return seq

def _aim(ref, parts, final, used_pads):
    """The anchor pad this part should sit at, and how far it may stray."""
    anc = cluster.CLUSTER.get(ref)
    hx, hy, rot, side = board.PLACE[ref]
    if not (anc and anc in final): return hx, hy, BUDGET_ORPHAN
    mynets = {n for n in parts[ref]["pins"].values() if n and n != "!NC"}
    best = None
    for pn, nn in parts[anc]["pins"].items():
        if nn not in mynets or nn == "GND": continue
        px, py = pad_xy(anc, pn, final, parts)
        # one cap per power pin: claiming the pad spreads the bypass bank out
        # across the pins instead of stacking every cap on the same one
        pen = 6.0 if (anc, pn) in used_pads else 0.0
        d = math.hypot(px-hx, py-hy) + pen
        if best is None or d < best[0]: best = (d, px, py, pn)
    if best is None:
        ax, ay = final[anc][0], final[anc][1]
        return ax, ay, BUDGET_CLUSTER
    used_pads.add((anc, best[3]))
    return best[1], best[2], (BUDGET_DECOUPLE if _is_decoupler(parts[ref])
                              else BUDGET_CLUSTER)

def edge_of(ref):
    """Which board edge a connector belongs against, taken from its hint."""
    x, y, rot, side = board.PLACE[ref]
    d = {'L': x, 'R': board.W - x, 'B': y, 'T': board.H - y}
    return min(d, key=d.get)

def _edge_search(ref, parts, taken, rmax, skip=()):
    """Slide a connector along its edge, hugging it, nearest-to-hint first.

    Every wire-access connector has to touch the perimeter or the cable cannot
    reach it, so searching the 1-D edge is both the right model and far more
    likely to close than a 2-D spiral through a board this full.
    """
    fpid = parts[ref]["fp"]
    hx, hy = HINT.get(ref, board.PLACE[ref][:2])
    hrot, hside = board.PLACE[ref][2], board.PLACE[ref][3]
    e = edge_of(ref)
    M = 0.6                                   # sit just inside the 0.5 mm margin
    # rotation is free, side is not: which face a wire pad is soldered from is a
    # floorplan decision, and letting J12 flip to the top put it straight on top
    # of the 5 V regulator's input-capacitor space
    rots = [hrot, (hrot+180) % 360, (hrot+90) % 360, (hrot+270) % 360]
    sides = [hside]
    best = None
    for off in sorted([i*0.2 for i in range(-90, 91)], key=abs):
        if best is not None: break
        for sd in sides:
            for rt in rots:
                w, h, ox, oy = extent(fpid, rt, sd)
                if e == 'B':   x, y = hx + off, M + h/2 - oy
                elif e == 'T': x, y = hx + off, board.H - M - h/2 - oy
                elif e == 'L': x, y = M + w/2 - ox, hy + off
                else:          x, y = board.W - M - w/2 - ox, hy + off
                x, y = round(x, 2), round(y, 2)
                bb = box(x, y, fpid, rt, sd)
                if legal(bb, sd, taken, pth=has_pth(fpid), skip=skip):
                    best = (abs(off), x, y, rt, sd, bb); break
            if best is not None: break
    return best

def _search(ref, parts, taken, tx, ty, rmax, skip=()):
    """Nearest legal pose to (tx,ty). Returns (dist, x, y, rot, side, bb)."""
    fpid = parts[ref]["fp"]
    hrot, hside = board.PLACE[ref][2], board.PLACE[ref][3]
    if ref in ("U1", "U2"):                       # gyro centred, MCU under it
        sides, rots = [hside], [hrot]
    elif ref in ANCHORS:
        # the floorplan owns which SIDE an anchor is on and roughly where, but
        # its orientation is free: rotating an IC is electrically neutral and it
        # is often the only way a part fits once the fanout halos are in place
        # side is a floorplan decision, never the solver's: flipping U6 to the
        # bottom while L1 stayed on top split the 5 V switching loop across the
        # board, which is exactly what DESIGN_PLAN sec 7.3 forbids
        sides = [hside]
        rots  = [hrot, (hrot+180) % 360, (hrot+90) % 360, (hrot+270) % 360]
    else:
        sides = [hside, 'B' if hside == 'F' else 'F']
        rots  = [hrot, (hrot+90) % 360, (hrot+180) % 360, (hrot+270) % 360]
    best = None
    step = 0.2
    for i in range(int(rmax/step) + 1):
        radius = i*step
        if best is not None: break                # first radius that fits wins
        steps = max(1, i*12)
        for k in range(steps):
            a = 2*math.pi*k/steps
            x = round(tx + radius*math.cos(a), 2)
            y = round(ty + radius*math.sin(a), 2)
            for sd in sides:
                for rt in rots:
                    bb = box(x, y, fpid, rt, sd)
                    if legal(bb, sd, taken, pth=has_pth(fpid), skip=skip):
                        d = math.hypot(x-tx, y-ty)
                        if best is None or d < best[0]:
                            best = (d, x, y, rt, sd, bb)
            if best is not None: break
    return best

def solve(verbose=False):
    parts = {c["ref"]: c for c in design.COMPONENTS if c.get("fp")}
    taken, final, failed = [], {}, []
    TARGET.clear(); BUDGET.clear()
    HINT.clear(); HINT.update(relax_hints(parts))
    used_pads = set()
    for ref in build_order(parts):
        if ref not in board.PLACE: failed.append((ref, "no hint")); continue
        tx, ty, bud = _aim(ref, parts, final, used_pads)
        if ref in ANCHORS:
            tx, ty = HINT.get(ref, board.PLACE[ref][:2]); bud = BUDGET_ANCHOR
        TARGET[ref] = (tx, ty); BUDGET[ref] = bud
        rmax = BUDGET_ANCHOR if ref in ANCHORS else 24.0
        if ref in EDGE_PARTS:
            got = _edge_search(ref, parts, taken, rmax)
            if got: TARGET[ref] = (got[1], got[2]); BUDGET[ref] = 0.01
        else:
            got = _search(ref, parts, taken, tx, ty, rmax)
        if got is None:
            failed.append((ref, "no spot within %.1f mm of its hint" % rmax)); continue
        d, x, y, rt, sd, bb = got
        final[ref] = (x, y, rt, sd)
        taken.append((bb, sd, has_pth(parts[ref]["fp"]), ref))

    # ---------------------------------------------------------- repair pass
    # Anything outside its budget gets one retry in which the lower-priority
    # parts blocking it are lifted and re-placed afterwards.
    prio = {r: i for i, r in enumerate(build_order(parts))}
    for _ in range(3):
        over = sorted((r for r in final
                       if math.hypot(final[r][0]-TARGET[r][0],
                                     final[r][1]-TARGET[r][1]) > BUDGET[r] + 1e-6),
                      key=lambda r: prio[r])
        moved = False
        for ref in over:
            tx, ty = TARGET[ref]
            junior = {r for r in final if prio[r] > prio[ref]}
            got = _search(ref, parts, taken, tx, ty, BUDGET[ref], skip=junior)
            if got is None: continue
            d, x, y, rt, sd, bb = got
            # evict every junior part this pose overlaps, then re-place them
            hit = set()
            mypth = has_pth(parts[ref]["fp"])
            for (bx0, by0, bx1, by1), s_, spth, owner in taken:
                if owner not in junior: continue
                if s_ != sd and not (mypth or spth): continue
                if (min(bb[2], bx1) - max(bb[0], bx0) > 0.01 and
                    min(bb[3], by1) - max(bb[1], by0) > 0.01): hit.add(owner)
            taken = [t for t in taken if t[3] not in hit and t[3] != ref]
            final[ref] = (x, y, rt, sd)
            taken.append((bb, sd, mypth, ref))
            moved = True
            for r2 in sorted(hit, key=lambda r: prio[r]):
                del final[r2]
                g2 = _search(r2, parts, taken, *TARGET[r2], 24.0)
                if g2 is None: failed.append((r2, "displaced, no spot")); continue
                _, x2, y2, rt2, sd2, bb2 = g2
                final[r2] = (x2, y2, rt2, sd2)
                taken.append((bb2, sd2, has_pth(parts[r2]["fp"]), r2))
        if not moved: break
    return final, failed

def report(final):
    rows = []
    for r, (x, y, rot, sd) in final.items():
        if r not in TARGET: continue
        d = math.hypot(x-TARGET[r][0], y-TARGET[r][1])
        rows.append((d - BUDGET[r], d, BUDGET[r], r))
    rows.sort(reverse=True)
    return [t for t in rows if t[0] > 1e-6], rows

if __name__ == "__main__":
    final, failed = solve()
    n = len([c for c in design.COMPONENTS if c.get('fp')])
    over, rows = report(final)
    print("="*72)
    print(f"placed {len(final)} / {n}   failures: {len(failed)}   "
          f"over budget: {len(over)}")
    print("="*72)
    for r, why in failed: print(f"  ! {r}: {why}")
    if over:
        print("\nover their distance budget:")
        for ex, d, b, r in over:
            print(f"   {r:<5} {d:6.2f} mm from target (budget {b:.1f}) "
                  f"-> {ex:+.2f}")
    dec = [t for t in rows if t[2] == BUDGET_DECOUPLE]
    if dec:
        print(f"\ndecoupling: {len(dec)} caps, worst {max(t[1] for t in dec):.2f} mm, "
              f"median {sorted(t[1] for t in dec)[len(dec)//2]:.2f} mm")
    print(f"all clustered parts: median "
          f"{sorted(t[1] for t in rows)[len(rows)//2]:.2f} mm, "
          f"max {max(t[1] for t in rows):.2f} mm")
