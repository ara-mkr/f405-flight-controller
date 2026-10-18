# Pull fan-out vias off SMD pads (PCBWay DFM, 2026-10-18: "move vias away from SMD pads"
# instead of paying for via-in-pad fill). Every such via hangs off a 0.3 mm stub from its
# pad; the stub is lengthened until the via copper sits PAD_GAP clear of every SMD pad
# (vias are tented, so that leaves a mask web between the pad opening and the via).
# Exposed-pad thermal arrays (U4.29, U6.9, U7.9) are intentional and left alone.
# Run with KiCad's python, from hardware/:  .../python3 gen/via_off_pad.py fc_f405.kicad_pcb
import math, sys
import pcbnew

MM = pcbnew.FromMM
PAD_GAP = MM(0.15)      # via copper edge -> any SMD pad copper edge
MARGIN = MM(0.01)       # on top of each pair's netclass / rule clearance
HOLE_CLR = MM(0.22)     # via hole -> other-net copper (board min 0.2)
HOLE_HOLE = MM(0.30)    # hole edge -> hole edge (fc_f405.kicad_dru)
EDGE = MM(0.30)         # copper -> board edge
THERMAL = {("U4", "29"), ("U6", "9"), ("U7", "9")}
CU = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu]

b = pcbnew.LoadBoard(sys.argv[1])
tracks = list(b.GetTracks())
vias = [t for t in tracks if t.GetClass() == "PCB_VIA"]
segs = [t for t in tracks if t.GetClass() == "PCB_TRACK"]
pads = [p for fp in b.GetFootprints() for p in fp.Pads()]
smd = [p for p in pads if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
keepouts = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
outline = pcbnew.SHAPE_POLY_SET()
b.GetBoardPolygonOutlines(outline, True)


def side(p):
    return pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu


def name(p):
    return f"{p.GetParentFootprint().GetReference()}.{p.GetNumber()}"


def touching(v):
    """SMD pads (bar thermal EPs) whose copper the via ring overlaps."""
    out = []
    for p in smd:
        if (p.GetParentFootprint().GetReference(), p.GetNumber()) in THERMAL or p.GetNumber() == "":
            continue
        if p.GetEffectivePolygon(side(p)).Collide(v.GetPosition(), v.GetWidth(side(p)) // 2):
            out.append(p)
    return out


def near(item, c, r):
    bb = item.GetBoundingBox()
    return bb.GetLeft() - r < c.x < bb.GetRight() + r and bb.GetTop() - r < c.y < bb.GetBottom() + r


def clr(a, b):
    """Required copper gap between two other-net items: the larger netclass / rule clearance."""
    return max(a.GetOwnClearance(pcbnew.F_Cu), b.GetOwnClearance(pcbnew.F_Cu)) + MARGIN


def ok(v, mine, gap=PAD_GAP):
    """None if the via (and its stub / bridge tracks) fit, else the reason they don't."""
    c, r = v.GetPosition(), v.GetWidth(pcbnew.F_Cu) // 2
    if not outline.Contains(c):
        return "outside board"
    for i in range(outline.OutlineCount()):
        ol = outline.COutline(i)
        for k in range(ol.SegmentCount()):
            if ol.CSegment(k).Distance(c) < r + EDGE:
                return "board edge"
    for z in keepouts:
        if z.Outline().Collide(c, r):
            return "via keepout"
    vhole = v.GetEffectiveHoleShape()
    net = v.GetNetCode()
    for p in pads:
        if not near(p, c, MM(3)):
            continue
        for lay in CU:
            if not p.IsOnLayer(lay):
                continue
            ps = p.GetEffectiveShape(lay)
            if p.GetNetCode() != net:
                if ps.Collide(v.GetEffectiveShape(lay), clr(p, v)) or ps.Collide(vhole, HOLE_CLR):
                    return "pad " + name(p)
            elif p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD and ps.Collide(v.GetEffectiveShape(lay), gap):
                return "in-pad " + name(p)
        if p.HasHole() and p.GetEffectiveHoleShape().Collide(vhole, HOLE_HOLE):
            return "hole " + name(p)
    for o in vias:
        if o is v or not near(o, c, MM(3)):
            continue
        if o.GetEffectiveHoleShape().Collide(vhole, HOLE_HOLE):
            return "via hole-hole"
        if o.GetNetCode() != net and o.GetEffectiveShape(pcbnew.F_Cu).Collide(v.GetEffectiveShape(pcbnew.F_Cu), clr(o, v)):
            return "via " + o.GetNetname()
    for s in segs:
        if s.GetNetCode() == net or not near(s, c, MM(4)):
            continue
        ss = s.GetEffectiveShape()
        if ss.Collide(v.GetEffectiveShape(s.GetLayer()), clr(s, v)) or ss.Collide(vhole, HOLE_CLR):
            return f"track {s.GetNetname()} {b.GetLayerName(s.GetLayer())}"
        for m in mine:
            if m.GetLayer() == s.GetLayer() and ss.Collide(m.GetEffectiveShape(), clr(s, m)):
                return f"stub x track {s.GetNetname()}"
    for m in mine:
        ms = m.GetEffectiveShape()
        for p in pads:
            if p.GetNetCode() != net and p.IsOnLayer(m.GetLayer()) and near(p, c, MM(4)):
                if p.GetEffectiveShape(m.GetLayer()).Collide(ms, clr(p, m)):
                    return "stub x pad " + name(p)
        for o in vias:
            if o.GetNetCode() != net and near(o, c, MM(4)):
                if o.GetEffectiveShape(m.GetLayer()).Collide(ms, clr(o, m)):
                    return "stub x via " + o.GetNetname()
    return None


def attached(v):
    """Tracks ending on this via (router endpoints can sit a hair off the via centre)."""
    c, r = v.GetPosition(), v.GetWidth(pcbnew.F_Cu) // 2
    out = []
    for s in segs:
        for end in ("start", "end"):
            p = s.GetStart() if end == "start" else s.GetEnd()
            if (p - c).EuclideanNorm() < r:
                out.append((s, end)); break
    return out


def search(v, ps, stub, extra, anchor, gap, step, reach):
    """Shortest stub (pad-side anchor -> via) that puts the via ring `gap` off every pad."""
    old = v.GetPosition()
    pc = ps[0].GetPosition()
    base = math.atan2(old.y - pc.y, old.x - pc.x)
    polys = [q.GetEffectivePolygon(side(q)) for q in ps]
    r = v.GetWidth(pcbnew.F_Cu) // 2
    cands = []
    for da in range(-180, 180, step):
        a = base + math.radians(da)
        ux, uy = math.cos(a), math.sin(a)
        t0 = None                                     # first point where the ring clears the pads
        for i in range(120):
            t = MM(0.05) * i
            pt = pcbnew.VECTOR2I(int(pc.x + ux * t), int(pc.y + uy * t))
            if all(not poly.Collide(pt, r + gap - 1) for poly in polys):
                t0 = t; break
        if t0 is None:
            continue
        for j in range(reach):
            t = t0 + MM(0.05) * j
            pt = pcbnew.VECTOR2I(int(pc.x + ux * t), int(pc.y + uy * t))
            cands.append(((pt - anchor).EuclideanNorm() + MM(0.25) * abs(math.radians(da)), pt))
    cands.sort(key=lambda k: k[0])
    why = {}
    for _, pt in cands:
        v.SetPosition(pt)
        if stub:
            stub.SetEnd(pt)
        for e in extra:
            e.SetEnd(pt)
        bad = ok(v, ([stub] if stub else []) + extra, gap)
        if bad is None:
            return pt, why
        why[bad] = why.get(bad, 0) + 1
    v.SetPosition(old)
    if stub:
        stub.SetEnd(old)
    for e in extra:
        e.SetEnd(old)
    return None, why


def stitch(v, ps):
    """GND only: free-standing via in the pour as near the pad as fits (pours make the link)."""
    old = v.GetPosition()
    cands = []
    for i in range(-50, 51):
        for j in range(-50, 51):
            pt = pcbnew.VECTOR2I(old.x + MM(0.05) * i, old.y + MM(0.05) * j)
            cands.append(((pt - old).EuclideanNorm(), pt))
    cands.sort(key=lambda k: k[0])
    for d, pt in cands:
        if d > MM(2.5):
            break
        if not all(z.Outline().Contains(pt) for z in gnd_pours):
            continue
        v.SetPosition(pt)
        if ok(v, []) is None:
            return pt
    v.SetPosition(old)
    return None


gnd_pours = [z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname() == "GND"
             and (z.GetLayerSet().Contains(pcbnew.F_Cu) or z.GetLayerSet().Contains(pcbnew.B_Cu))]
targets = [(v, touching(v)) for v in vias if v.GetDrill() < MM(0.25)]
targets = [(v, ps) for v, ps in targets if ps]
print(f"{len(targets)} vias sit on SMD pads")
log = {"moved": [], "relaxed": [], "stitched": [], "failed": []}
stuck = {}
for v, ps in targets:
    old = v.GetPosition()
    lay = side(ps[0])
    att = attached(v)
    stub, se = [(s, e) for s, e in att if s.GetLayer() == lay][0]
    others = [s for s, e in att if s is not stub]
    if se == "start":
        stub.SetStart(stub.GetEnd())
    stub.SetEnd(old)
    anchor = stub.GetStart()                          # pad-side end of the stub
    extra = []                                        # bridge any other-layer track to the new spot
    for o in others:
        e = pcbnew.PCB_TRACK(b)
        e.SetLayer(o.GetLayer()); e.SetWidth(o.GetWidth()); e.SetNetCode(o.GetNetCode()); e.SetStart(old)
        extra.append(e)
    ref = "/".join(name(q) for q in ps)
    at = f"({pcbnew.ToMM(old.x):.3f},{pcbnew.ToMM(old.y):.3f})"
    done, kind = None, None
    w0 = v.GetWidth(pcbnew.F_Cu)
    for gap, step, reach, k, w in ((PAD_GAP, 10, 16, "moved", w0), (PAD_GAP, 5, 30, "moved", w0),
                                   (MM(0.10), 5, 30, "relaxed", w0), (MM(0.10), 5, 30, "relaxed", MM(0.45))):
        v.SetWidth(w)                                 # last resort: board-minimum 0.45 mm via
        done, why = search(v, ps, stub, extra, anchor, gap, step, reach)
        if done:
            kind = k; break
    if not done:
        v.SetWidth(w0)
    if done:
        for e in extra:
            b.Add(e); segs.append(e)
        log[kind].append(ref)
        print(f"  {kind:8s} {ref:9s} {v.GetNetname():5s} {at} -> ({pcbnew.ToMM(done.x):.3f},{pcbnew.ToMM(done.y):.3f})"
              f"  stub {pcbnew.ToMM(stub.GetLength()):.2f} mm" + ("  (0.45 via)" if v.GetWidth(pcbnew.F_Cu) != w0 else ""))
        continue
    if v.GetNetname() == "GND" and not others:
        b.Remove(stub); segs.remove(stub)
        pt = stitch(v, ps)
        if pt:
            log["stitched"].append(ref)
            print(f"  stitched {ref:9s} GND   {at} -> free via ({pcbnew.ToMM(pt.x):.3f},{pcbnew.ToMM(pt.y):.3f}), pad on pour")
        else:
            b.Remove(v); vias.remove(v)
            log["stitched"].append(ref)
            print(f"  removed  {ref:9s} GND   {at}, pad on pour")
        continue
    log["failed"].append(ref); stuck[ref] = v
    top = sorted(why.items(), key=lambda k: -k[1])[:4]
    print(f"  FAIL     {ref:9s} {v.GetNetname():5s} {at} {top}")



# ---- hand fixes for the vias no straight stub can free (dense QFP / SOIC / SOT-223 spots) ----
def P(x, y):
    return pcbnew.VECTOR2I(MM(x), MM(y))


def pad_of(spec):
    ref, num = spec.split(".")
    return [p for p in b.FindFootprintByReference(ref).Pads() if p.GetNumber() == num]


def drop_via(v):
    for s, _ in attached(v):
        b.Remove(s); segs.remove(s)
    b.Remove(v); vias.remove(v)


def track_bad(t):
    ts, net, lay = t.GetEffectiveShape(), t.GetNetCode(), t.GetLayer()
    for p in pads:
        if p.GetNetCode() != net and p.IsOnLayer(lay) and p.GetEffectiveShape(lay).Collide(ts, clr(p, t)):
            return "pad " + name(p)
    for o in vias:
        if o.GetNetCode() != net and o.GetEffectiveShape(lay).Collide(ts, clr(o, t)):
            return "via " + o.GetNetname()
    for o in segs:
        if o.GetNetCode() != net and o.GetLayer() == lay and o.GetEffectiveShape().Collide(ts, clr(o, t)):
            return "track " + o.GetNetname()
    return None


def add_track(lay, pts, width, netname):
    new = []
    for a, c in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetLayer(lay); t.SetWidth(MM(width)); t.SetNet(b.FindNet(netname)); t.SetStart(a); t.SetEnd(c)
        bad = track_bad(t)
        if bad:
            return bad
        new.append(t)
    for t in new:
        b.Add(t); segs.append(t)
    return None


def pin_to_ep(pin, ep, width):
    """Straight in-line track from a GND pin into the exposed pad it faces (classic HTSSOP/SOIC-EP tie)."""
    p, e = pad_of(pin)[0], pad_of(ep)[0]
    lay = side(p)
    pc, bb = p.GetPosition(), e.GetBoundingBox()
    x = min(max(pc.x, bb.GetLeft() + MM(0.2)), bb.GetRight() - MM(0.2))
    return add_track(lay, [pc, pcbnew.VECTOR2I(x, pc.y)], width, "GND")


def fix(ref, what, err=None):
    print(f"  {'FAIL' if err else 'fixed':8s} {ref:9s} {what}" + (f"  ({err})" if err else ""))
    if not err:
        log["failed"].remove(ref) if ref in log["failed"] else None


if "U1.32" in stuck:      # C19's +3V3 track already lands on pin 32 and runs to C19's own via
    drop_via(stuck["U1.32"]); fix("U1.32", "dropped duplicate via; pin 32 -> C19.1 -> C19 via -> +3V3 plane")
if "U4.23" in stuck:      # GND pin: tie it straight into the grounded exposed pad (9 thermal vias)
    drop_via(stuck["U4.23"]); fix("U4.23", "via dropped, pin 23 tied into EP U4.29", pin_to_ep("U4.23", "U4.29", 0.3))
for pin, ep in (("U4.13", "U4.29"), ("U6.7", "U6.9")):   # their vias became pour stitches; add the EP tie too
    err = pin_to_ep(pin, ep, 0.3)
    print(f"  {'tie' if not err else 'no tie':8s} {pin:9s} -> EP {ep}" + (f"  ({err})" if err else ""))
def seg_at(lay, a, c):
    """The track on `lay` running a-c (either direction), endpoints matched to 1 um."""
    for t in segs:
        if t.GetLayer() == lay and {(round(pcbnew.ToMM(p.x), 3), round(pcbnew.ToMM(p.y), 3))
                                    for p in (t.GetStart(), t.GetEnd())} == {a, c}:
            return t
    raise LookupError(f"no track {a}-{c}")


if "U6.7" in stuck:       # buck GND pin: its via also grounds C41.2 (CURR_SENSE filter cap) on F.Cu
    v = stuck["U6.7"]     # the pin itself is now tied into EP U6.9 on B.Cu (above)
    drop_via(v)
    t = seg_at(pcbnew.F_Cu, (9.03, 20.64), (9.42, 20.25)); b.Remove(t); segs.remove(t)
    # In3 RSSI_IN crossed the only free spot at y 20.185; run it 0.57 mm lower along its own
    # y 20.753 segment and rejoin its existing 45-degree leg (shorter, same layer)
    In3 = pcbnew.In3_Cu
    for a, c in (((5.324, 20.753), (5.892, 20.185)), ((5.892, 20.185), (9.722, 20.185))):
        t = seg_at(In3, a, c); b.Remove(t); segs.remove(t)
    leg = seg_at(In3, (9.722, 20.185), (13.094, 23.557))
    if (leg.GetStart() - P(9.722, 20.185)).EuclideanNorm() < (leg.GetEnd() - P(9.722, 20.185)).EuclideanNorm():
        leg.SetStart(P(10.29, 20.753))
    else:
        leg.SetEnd(P(10.29, 20.753))
    err = add_track(In3, [P(5.324, 20.753), P(10.29, 20.753)], 0.127, "RSSI_IN")
    b.Add(v); vias.append(v)
    cap = pad_of("C41.2")[0]
    stub = pcbnew.PCB_TRACK(b)
    stub.SetLayer(pcbnew.F_Cu); stub.SetWidth(MM(0.3)); stub.SetNet(b.FindNet("GND")); stub.SetStart(cap.GetPosition())
    best = None
    for w in (v.GetWidth(pcbnew.F_Cu), MM(0.45)):
        v.SetWidth(w)
        for i in range(-15, 16):
            for j in range(-15, 16):
                pt = P(8.75 + 0.01 * i, 20.25 + 0.01 * j)
                v.SetPosition(pt); stub.SetEnd(pt)
                if ok(v, [stub], MM(0.10)) is None:
                    d = (pt - P(8.75, 20.25)).EuclideanNorm()
                    if best is None or d < best[0]:
                        best = (d, pt)
        if best:
            break
    if best and not err:
        v.SetPosition(best[1]); stub.SetEnd(best[1]); b.Add(stub); segs.append(stub)
        fix("U6.7", f"via -> {pcbnew.ToMM(v.GetWidth(pcbnew.F_Cu)):.2f} mm at ({pcbnew.ToMM(best[1].x):.3f},"
                    f"{pcbnew.ToMM(best[1].y):.3f}) grounding C41.2; In3 RSSI_IN moved to y 20.753")
    else:
        b.Remove(v); vias.remove(v)
        fix("U6.7", "no spot for the C41.2 ground via", err or "grid search empty")


if "U5.3" in stuck:       # flash /WP: 0.2 mm F.Cu feed from the +3V3 via left of the chip
    drop_via(stuck["U5.3"])
    fix("U5.3", "via dropped, fed from +3V3 via (23.290,25.672)",
        add_track(pcbnew.F_Cu, [P(26.012, 26.635), P(24.45, 26.635), P(23.29, 25.6715)], 0.2, "+3V3"))
if "U8.2" in stuck:       # SOT-223 pin 2 is the tab inside the package; the tab keeps its via
    drop_via(stuck["U8.2"])
    b.FindFootprintByReference("U8").SetDuplicatePadNumbersAreJumpers(True)
    fix("U8.2", "pin-2 via dropped; pin 2 and tab marked as one internal node (tab via feeds +3V3)")

pcbnew.ZONE_FILLER(b).Fill(b.Zones())


def edge_dist(o, pt):
    return min(o.CSegment(k).Distance(pt) for k in range(o.SegmentCount()))


def stitch_islands():
    """A pad's old via may have been the only tie for a scrap of GND pour; give each orphan a via."""
    tmpl = next(v for v in vias if v.GetNetname() == "GND" and v.GetDrill() < MM(0.25))
    pth = [p for p in pads if p.GetNetname() == "GND" and p.HasHole()]
    added = 0
    for z in b.Zones():
        if z.GetNetname() != "GND" or z.GetIsRuleArea():
            continue
        for lay in z.GetLayerSet().Seq():
            fill = z.GetFilledPolysList(lay)
            for i in range(fill.OutlineCount()):
                o = fill.Outline(i)
                if any(o.PointInside(v.GetPosition()) for v in vias if v.GetNetname() == "GND") or \
                   any(o.PointInside(p.GetPosition()) for p in pth):
                    continue
                bb = o.BBox(); c = bb.Centre()
                pts = [pcbnew.VECTOR2I(x, y) for x in range(bb.GetLeft(), bb.GetRight(), MM(0.05))
                       for y in range(bb.GetTop(), bb.GetBottom(), MM(0.05))]
                pts.sort(key=lambda p: (p - c).EuclideanNorm())
                v = pcbnew.PCB_VIA(tmpl); b.Add(v); vias.append(v)
                for pt in pts:
                    if not o.PointInside(pt) or edge_dist(o, pt) < tmpl.GetWidth(pcbnew.F_Cu) // 2 + MM(0.05):
                        continue
                    v.SetPosition(pt)
                    if ok(v, []) is None:
                        added += 1
                        print(f"  island   {z.GetZoneName()} {b.GetLayerName(lay)}: stitch via ({pcbnew.ToMM(pt.x):.3f},{pcbnew.ToMM(pt.y):.3f})")
                        break
                else:
                    b.Remove(v); vias.remove(v)
                    print(f"  island   {z.GetZoneName()} {b.GetLayerName(lay)} at {pcbnew.ToMM(c.x):.2f},{pcbnew.ToMM(c.y):.2f}: no room")
    return added


if stitch_islands():
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
print({k: len(x) for k, x in log.items()}, "failed:", log["failed"])
b.Save(sys.argv[1])
