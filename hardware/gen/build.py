# -*- coding: utf-8 -*-
"""Rebuild fc_f405.kicad_pcb from design.py (netlist) + layout.py (placement).

Run with KiCad's bundled interpreter:
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3.9 build.py

Everything goes through pcbnew's own API - FootprintLoad, Flip, SetNet - so the
footprints on the board are byte-for-byte the library ones and nothing about
pad rotation or bottom-side mirroring is re-implemented by hand.
Writes a placed, unrouted board. Routing is route_fr.py's job.
"""
import sys, os, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew, rules
import design, layout, geom

HW    = os.path.dirname(HERE)
PCB   = os.path.join(HW, "fc_f405.kicad_pcb")
STOCK = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
PROJ  = os.path.join(HW, "lib", "fc_f405.pretty")

MM = pcbnew.FromMM
def V(x, y): return pcbnew.VECTOR2I(MM(x), MM(y))

def load_fp(fpid):
    lib, name = fpid.split(":", 1)
    path = PROJ if lib == "fc_f405" else os.path.join(STOCK, lib + ".pretty")
    fp = pcbnew.FootprintLoad(path, name)
    assert fp is not None, fpid
    fp.SetFPIDAsString(fpid)
    # IPC-7351 density level C courtyard (see geom.py) in place of the stock
    # nominal one - same rectangle the placement check packs against
    # (removing items crashes the KiCad 10 SWIG layer, so the stock outline is
    # parked on User.4 rather than deleted)
    for g in fp.GraphicalItems():
        if g.GetLayer() in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            g.SetLayer(pcbnew.User_4)
    if lib != "fc_f405" or "MountingHole" not in name:
        w, h, cx, cy = geom.courtyard(fpid)
        r = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_RECTANGLE)
        r.SetStart(V(cx - w/2, cy - h/2)); r.SetEnd(V(cx + w/2, cy + h/2))
        r.SetLayer(pcbnew.F_CrtYd); r.SetWidth(MM(0.05))
        fp.Add(r)
    return fp

def empty_board():
    """A board holding only the stack-up and setup from pcb_header.tpl."""
    tmp = os.path.join(HW, ".empty.kicad_pcb")
    open(tmp, "w").write(open(os.path.join(HERE, "pcb_header.tpl")).read() + "\n)\n")
    b = pcbnew.LoadBoard(tmp)
    os.remove(tmp)
    return b

def net(b, name):
    ni = b.FindNet(name)
    if ni is None:
        ni = pcbnew.NETINFO_ITEM(b, name)
        b.Add(ni)
    return ni

def bare_attrs(fp):
    """wire-pad groups are bare copper: out of the BOM and the pick-and-place
    (matches in_bom / in_pos_files no on their symbols)"""
    if fp.GetFPIDAsString().startswith("fc_f405:SolderPad"):
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        return 1
    return 0

def place(b, ref, comp, x, y, rot, side):
    fp = load_fp(comp["fp"])
    fp.SetReference(ref)
    fp.SetValue(comp["val"])
    b.Add(fp)
    fp.SetPosition(V(x, y))
    if side == 'B':
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(rot)
    bare_attrs(fp)
    for pad in fp.Pads():
        n = comp["pins"].get(pad.GetNumber())
        if n and n != "!NC":
            pad.SetNet(net(b, n))
    return fp

def outline(b):
    W, H, R = layout.W, layout.H, layout.CORNER_R
    def seg(x1, y1, x2, y2):
        s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(V(x1, y1)); s.SetEnd(V(x2, y2))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); b.Add(s)
    def arc(cx, cy, sx, sy, ang):
        s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_ARC)
        s.SetCenter(V(cx, cy)); s.SetStart(V(sx, sy))
        s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(ang, pcbnew.DEGREES_T))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); b.Add(s)
    seg(R, 0, W-R, 0); seg(W, R, W, H-R); seg(W-R, H, R, H); seg(0, H-R, 0, R)
    arc(W-R, R, W-R, 0, 90); arc(W-R, H-R, W, H-R, 90)
    arc(R, H-R, R, H, 90);   arc(R, R, 0, R, 90)

def holes(b):
    for n, (hx, hy) in enumerate(layout.HOLE_XY):
        fp = load_fp("fc_f405:MountingHole_4.0mm")
        fp.SetReference("H%d" % (n + 1)); fp.SetValue("M3")
        fp.SetPosition(V(hx, hy))
        b.Add(fp)

def fix_fields(parts):
    """Field edits the KiCad 10 SWIG bindings cannot do (GetField returns an
    opaque pointer), applied to the saved file instead:
      * Reference moves to the Fab layer - the silkscreen carries pad labels
        and the logo, like any production flight controller
      * Value is hidden
      * LCSC / MPN become hidden footprint properties for the assembly BOM
    """
    import re
    t = open(PCB).read()
    out, pos = [], 0
    rx = re.compile(r'\(footprint "')
    while True:
        m = rx.search(t, pos)
        if not m: out.append(t[pos:]); break
        end = geom.span(t, m.start()); blk = t[m.start():end]
        ref = re.search(r'\(property "Reference" "([^"]*)"', blk).group(1)
        def sub_prop(name, fn):
            nonlocal blk
            mm = re.search(r'\(property "%s" ' % name, blk)
            if not mm: return
            e = geom.span(blk, mm.start())
            blk = blk[:mm.start()] + fn(blk[mm.start():e]) + blk[e:]
        def to_fab(p):
            p = p.replace('"F.SilkS"', '"F.Fab"').replace('"B.SilkS"', '"B.Fab"')
            return p
        def hide(p):
            if "(hide yes)" in p: return p
            return re.sub(r'\(layer ("[^"]*")\)', r'(layer \1)\n\t\t\t(hide yes)', p, count=1)
        sub_prop("Reference", to_fab)
        sub_prop("Value", hide)
        if ref.startswith("H"):
            sub_prop("Reference", hide)
        comp = parts.get(ref)
        if comp:
            lay = "B.Fab" if '(layer "B.Cu")' in blk[:300] else "F.Fab"
            extra = "".join(
                '\t\t(property "%s" "%s"\n\t\t\t(at 0 0 0)\n\t\t\t(layer "%s")\n'
                '\t\t\t(hide yes)\n\t\t\t(effects (font (size 1 1) (thickness 0.15)))\n\t\t)\n'
                % (k.upper(), comp[k], lay) for k in ("lcsc", "mpn") if comp.get(k))
            if extra:
                mm = re.search(r'\(property "Value" ', blk)
                e = geom.span(blk, mm.start())
                blk = blk[:e] + "\n" + extra + blk[e:]
        out.append(t[pos:m.start()]); out.append(blk); pos = end
    open(PCB, "w").write("".join(out))

def sync_datasheets():
    """Each footprint's Datasheet field = its symbol's (schematic parity). Text
    edit, idempotent, copper untouched - also run on a routed board:
    python3.9 build.py fields"""
    import re
    ds = {c["ref"]: c.get("ds", "~") for c in design.COMPONENTS}
    t = open(PCB).read()
    out, pos = [], 0
    rx = re.compile(r'\(footprint "')
    while True:
        m = rx.search(t, pos)
        if not m: out.append(t[pos:]); break
        end = geom.span(t, m.start()); blk = t[m.start():end]
        ref = re.search(r'\(property "Reference" "([^"]*)"', blk).group(1)
        if ref in ds:
            blk = re.sub(r'\(property "Datasheet" "[^"]*"', '(property "Datasheet" "%s"' % ds[ref], blk, count=1)
        out.append(t[pos:m.start()]); out.append(blk); pos = end
    open(PCB, "w").write("".join(out))

def nc_nets():
    """No-connect pins: KiCad's netlist gives each its own "unconnected-(...)"
    net; put the same name on the pad so board and schematic are in parity.
    Names come from the schematic's own netlist export. Also run on a routed
    board: python3.9 build.py ncnets"""
    import re, subprocess, tempfile
    kc = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "fc.net")
        subprocess.run([kc, "sch", "export", "netlist", "-o", out, os.path.join(HW, "fc_f405.kicad_sch")],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        txt = open(out).read()
    want = {}
    blocks = re.split(r'\(net\s+\(code ', txt)[1:]
    for blk in blocks:
        nm = re.search(r'\(name "([^"]*)"\)', blk).group(1)
        if not nm.startswith("unconnected-"): continue
        for r, pn in re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', blk):
            want[(r, pn)] = nm
    b = pcbnew.LoadBoard(PCB); n = 0
    for fp in b.Footprints():
        for p in fp.Pads():
            name = want.get((fp.GetReference(), p.GetNumber()))
            if name and p.GetNetname() != name:
                p.SetNet(net(b, name)); n += 1
    pcbnew.SaveBoard(PCB, b)
    return n

def main():
    b = empty_board()
    parts = {c["ref"]: c for c in design.COMPONENTS if c.get("fp") and not c.get("mech")}
    missing = sorted(set(parts) - set(layout.PLACE))
    extra = sorted(set(layout.PLACE) - set(parts))
    assert not missing and not extra, (missing, extra)
    for ref, (x, y, rot, side) in sorted(layout.PLACE.items()):
        place(b, ref, parts[ref], x, y, rot, side)
    outline(b)
    holes(b)
    b.BuildConnectivity()
    pcbnew.SaveBoard(PCB, b)
    fix_fields(parts)
    sync_datasheets()
    nc_nets()
    rules.apply()
    print("placed %d parts, %d nets" % (len(parts), b.GetNetCount()))

if __name__ == "__main__":
    if sys.argv[1:] == ["fields"]: sync_datasheets(); print("datasheet fields synced")
    elif sys.argv[1:] == ["attrs"]:
        b = pcbnew.LoadBoard(PCB); k = sum(bare_attrs(fp) for fp in b.Footprints())
        pcbnew.SaveBoard(PCB, b); rules.apply(); print("wire-pad groups out of BOM / CPL:", k)
    elif sys.argv[1:] == ["ncnets"]: print("no-connect pads given their netlist names:", nc_nets()); rules.apply()
    else: main()
