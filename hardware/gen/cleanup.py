# -*- coding: utf-8 -*-
"""KiCad side of the clean-up router (KiCad python, no numpy here).

  python3.9 cleanup.py export <drc.rpt> <geom.json>   copper + unconnected pairs -> JSON
  python3     maze.py <geom.json> <routes.json>        (system python, numpy)
  python3.9 cleanup.py apply <routes.json>             tracks / vias -> board

freerouting leaves a handful of connections it cannot close on this board; the
maze router finishes them against the exact copper already placed.
"""
import sys, os, re, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pcbnew, rules

PCB = os.path.join(os.path.dirname(HERE), "fc_f405.kicad_pcb")
MM = pcbnew.FromMM; T = pcbnew.ToMM
LAY = {pcbnew.F_Cu: "F", pcbnew.In2_Cu: "I", pcbnew.In3_Cu: "J", pcbnew.B_Cu: "B"}
LAYID = {"F": pcbnew.F_Cu, "I": pcbnew.In2_Cu, "J": pcbnew.In3_Cu, "B": pcbnew.B_Cu}

def export(rpt, out):
    b = pcbnew.LoadBoard(PCB)
    pads, tracks, vias = [], [], []
    for fp in b.Footprints():
        for p in fp.Pads():
            ls = [L for lid, L in LAY.items() if p.IsOnLayer(lid)]
            if not ls: continue
            bb = p.GetBoundingBox()
            pads.append(dict(net=p.GetNetname(), layers=ls,
                             r=[T(bb.GetX()), T(bb.GetY()), T(bb.GetRight()), T(bb.GetBottom())],
                             ref=fp.GetReference(), num=p.GetNumber()))
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            c = t.GetPosition()
            vias.append(dict(net=t.GetNetname(), x=T(c.x), y=T(c.y), d=T(t.GetWidth(pcbnew.F_Cu))))
        elif t.GetLayer() in LAY:
            s, e = t.GetStart(), t.GetEnd()
            tracks.append(dict(net=t.GetNetname(), layer=LAY[t.GetLayer()],
                               a=[T(s.x), T(s.y)], b=[T(e.x), T(e.y)], w=T(t.GetWidth())))
    # unconnected pairs straight from KiCad's DRC: each is two anchor points
    pairs, lines = [], open(rpt).read().split("\n")
    for i, l in enumerate(lines):
        if not l.startswith("[unconnected_items]"): continue
        pts = []
        for j in range(i + 1, min(i + 5, len(lines))):
            m = re.match(r"\s+@\(([\d.]+) mm, ([\d.]+) mm\): (.*)", lines[j])
            if m:
                desc = m.group(3)
                net = re.search(r"\[([^\]]*)\]", desc).group(1)
                lay = re.findall(r"on (F\.Cu|B\.Cu|In2\.Cu|In3\.Cu)", desc)
                code = {"F.Cu": "F", "B.Cu": "B", "In2.Cu": "I", "In3.Cu": "J"}
                L = ["F", "I", "J", "B"] if ("Via" in desc or "PTH" in desc) else \
                    [code[lay[0]] if lay else "F"]
                pts.append(dict(x=float(m.group(1)), y=float(m.group(2)), net=net, layers=L))
        if len(pts) == 2:
            pairs.append(pts)
    json.dump(dict(pads=pads, tracks=tracks, vias=vias, pairs=pairs), open(out, "w"))
    print("exported %d pads, %d tracks, %d vias, %d unconnected pairs"
          % (len(pads), len(tracks), len(vias), len(pairs)))

def rip(nets):
    """delete every unlocked segment / via of the given nets from the board file"""
    t = open(PCB).read()
    out, pos, n = [], 0, 0
    rx = re.compile(r"\n\t\((segment|via)\n")
    while True:
        m = rx.search(t, pos)
        if not m: out.append(t[pos:]); break
        st = m.start() + 1
        d, k = 0, st
        while True:
            c = t[k]
            if c == "(": d += 1
            elif c == ")":
                d -= 1
                if d == 0: break
            k += 1
        blk = t[st:k+1]
        nm = re.search(r'\(net "([^"]*)"\)', blk)
        out.append(t[pos:st])
        if nm and nm.group(1) in nets and "(locked yes)" not in blk:
            n += 1
            pos = k + 1      # keep the newline: the next block needs it to match
        else:
            out.append(blk); pos = k + 1
    open(PCB, "w").write("".join(out))
    return n

def remove_items(vias, tracks):
    """delete specific vias / segments (matched numerically on position + net),
    including locked ones - used when the clean-up router moves a plane via"""
    t = open(PCB).read()
    out, pos, n = [], 0, 0
    rx = re.compile(r"\n\t\((segment|via)\n")
    num = r"(-?[\d.]+)"
    while True:
        m = rx.search(t, pos)
        if not m: out.append(t[pos:]); break
        st = m.start() + 1; d, k = 0, st
        while True:
            ch = t[k]
            if ch == "(": d += 1
            elif ch == ")":
                d -= 1
                if d == 0: break
            k += 1
        blk = t[st:k+1]; net = re.search(r'\(net "([^"]*)"\)', blk)
        net = net.group(1) if net else ""
        hit = False
        if m.group(1) == "via":
            at = re.search(r"\(at %s %s\)" % (num, num), blk)
            x, y = float(at.group(1)), float(at.group(2))
            hit = any(v["net"] == net and abs(v["x"]-x) < 1e-3 and abs(v["y"]-y) < 1e-3 for v in vias)
        else:
            s0 = re.search(r"\(start %s %s\)" % (num, num), blk); e0 = re.search(r"\(end %s %s\)" % (num, num), blk)
            ax, ay, bx, by = float(s0.group(1)), float(s0.group(2)), float(e0.group(1)), float(e0.group(2))
            hit = any(s["net"] == net and abs(s["a"][0]-ax) < 1e-3 and abs(s["a"][1]-ay) < 1e-3
                      and abs(s["b"][0]-bx) < 1e-3 and abs(s["b"][1]-by) < 1e-3 for s in tracks)
        out.append(t[pos:st])
        if hit:
            n += 1; pos = k + 1      # keep the newline: the next block needs it to match
        else:
            out.append(blk); pos = k + 1
    open(PCB, "w").write("".join(out))
    return n

def apply(path):
    R = json.load(open(path))
    if R.get("rip"):
        print("ripped %d items of %s" % (rip(set(R["rip"])), R["rip"]))
    if R.get("remove_vias") or R.get("remove_tracks"):
        print("removed %d moved plane items (of %d)" % (remove_items(R["remove_vias"], R["remove_tracks"]),
                                                    len(R["remove_vias"]) + len(R["remove_tracks"])))
    b = pcbnew.LoadBoard(PCB)
    nt = nv = 0
    for s in R["tracks"]:
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(MM(s["a"][0]), MM(s["a"][1])))
        t.SetEnd(pcbnew.VECTOR2I(MM(s["b"][0]), MM(s["b"][1])))
        t.SetWidth(MM(s["w"])); t.SetLayer(LAYID[s["layer"]])
        t.SetNet(b.FindNet(s["net"])); b.Add(t); nt += 1
    for v in R["vias"]:
        o = pcbnew.PCB_VIA(b)
        o.SetPosition(pcbnew.VECTOR2I(MM(v["x"]), MM(v["y"])))
        o.SetWidth(MM(v["d"])); o.SetDrill(MM(v["drill"]))
        o.SetNet(b.FindNet(v["net"])); b.Add(o); nv += 1
    pcbnew.SaveBoard(PCB, b)
    rules.apply()
    print("added %d track segments, %d vias" % (nt, nv))

if __name__ == "__main__":
    if sys.argv[1] == "export": export(sys.argv[2], sys.argv[3])
    else: apply(sys.argv[2])
