# -*- coding: utf-8 -*-
"""Generate fc_f405.kicad_pcb from design.py + the solved placement.

Deterministic and self-contained: footprint bodies come straight from the
libraries, so changing a footprint in design.py fully rebuilds the board.

Stack-up (DESIGN_PLAN sec 7.1), JLCPCB JLC04161H-7628:
  F.Cu   1 oz   components + signal
  In1.Cu 0.5oz  solid, uninterrupted GND
  In2.Cu 0.5oz  routing + power rails as wide traces + GND pour in the leftovers
                (sec 7.1 amended: two signal layers could not carry the nets)
  B.Cu   1 oz   components + signal
"""
import sys, os, re, math, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import place, board, design, stitch, geom, route, planes

HERE = os.path.dirname(os.path.abspath(__file__))
PCB   = "/Users/akhilraja-amudhan/Documents/Flight Controller Project/hardware/fc_f405.kicad_pcb"
STOCK = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
PROJ  = "/Users/akhilraja-amudhan/Documents/Flight Controller Project/hardware/lib/fc_f405.pretty"
_ns = uuid.UUID("6f1c9a42-0000-4000-8000-fc405f405f41")
def uid(*p): return str(uuid.uuid5(_ns, "|".join(map(str, p))))

LAYER_SWAP = [("F.Cu","B.Cu"),("F.Paste","B.Paste"),("F.Mask","B.Mask"),
              ("F.SilkS","B.SilkS"),("F.Fab","B.Fab"),("F.CrtYd","B.CrtYd"),
              ("F.Adhes","B.Adhes")]

def fp_text(fpid):
    lib, name = fpid.split(":", 1)
    p = (os.path.join(PROJ, name + ".kicad_mod") if lib == "fc_f405"
         else os.path.join(STOCK, lib + ".pretty", name + ".kicad_mod"))
    return open(p).read()

def mirror_y(body):
    """pcbnew's flip: mirror every child coordinate in Y, negate item rotations."""
    return re.sub(
        r'\((at|start|end|center|mid|xy) (-?[\d.]+) (-?[\d.]+)(?: (-?[\d.]+))?\)',
        lambda m: f"({m.group(1)} {m.group(2)} {-float(m.group(3)):g}"
                  + (f" {(-float(m.group(4))) % 360:g})" if m.group(4) else ")"),
        body)

def mirror_text(body):
    """Add (justify mirror) to every fp_text now living on a back layer.

    mirror_y flips the coordinates and swap_layers moves the item to B.SilkS,
    but neither touches the effects block, so the glyphs came out readable from
    the top - i.e. mirrored on the actual bottom copper.
    """
    out, pos = [], 0
    while True:
        m = re.compile(r'\(fp_text\b').search(body, pos)
        if not m: out.append(body[pos:]); break
        end = _span(body, m.start()); blk = body[m.start():end]
        if '"B.' in blk and 'mirror' not in blk:
            if '(justify' in blk:
                blk = blk.replace('(justify', '(justify mirror', 1)
            else:
                j = blk.rindex('(effects')
                k = _span(blk, j)
                blk = blk[:k-1] + '\n\t\t\t\t(justify mirror)\n\t\t\t' + blk[k-1:]
        out.append(body[pos:m.start()]); out.append(blk); pos = end
    return "".join(out)

def swap_layers(body):
    tmp = {}
    for i, (f, b) in enumerate(LAYER_SWAP):
        tmp[f'"@{i}@"'] = f'"{b}"'
        body = body.replace(f'"{f}"', f'"@{i}@"').replace(f'"{b}"', f'"{f}"')
    for k, v in tmp.items(): body = body.replace(k, v)
    return body

def _span(txt, start):
    """End index (exclusive) of the balanced s-expression beginning at `start`."""
    d = 0; k = start; ins = False
    while k < len(txt):
        c = txt[k]
        if ins:
            if c == '\\': k += 2; continue
            if c == '"': ins = False
        elif c == '"': ins = True
        elif c == '(': d += 1
        elif c == ')':
            d -= 1
            if d == 0: return k + 1
        k += 1
    raise ValueError("unbalanced")

def strip_layer(txt, frag):
    """Remove every graphic item drawn on a layer whose name contains `frag`."""
    out, pos = [], 0
    while True:
        m = re.compile(r'\(fp_(?:line|rect|poly|circle|arc)\b').search(txt, pos)
        if not m: out.append(txt[pos:]); break
        end = _span(txt, m.start()); blk = txt[m.start():end]
        out.append(txt[pos:m.start()])
        if frag not in blk: out.append(blk)
        pos = end
    return "".join(out)

def strip_prop(txt, name):
    while True:
        m = re.search(r'\(property "%s" ' % name, txt)
        if not m: return txt
        txt = txt[:m.start()] + txt[_span(txt, m.start()):]

def set_pad_nets(txt, pins, code):
    """Insert (net N "name") INSIDE each pad block - pads may be one line or many."""
    out, pos = [], 0
    while True:
        m = re.compile(r'\(pad "([^"]*)"').search(txt, pos)
        if not m: out.append(txt[pos:]); break
        end = _span(txt, m.start())
        blk = txt[m.start():end]
        net = pins.get(m.group(1))
        if net and net != "!NC":
            blk = blk[:-1].rstrip() + f'\n\t\t\t(net {code[net]} "{net}")\n\t\t)'
        out.append(txt[pos:m.start()]); out.append(blk); pos = end
    return "".join(out)

def emit_footprint(ref, comp, x, y, rot, side, code):
    txt = fp_text(comp["fp"])
    inner = txt[txt.index("\n"):].rstrip()
    assert inner.endswith(")"); inner = inner[:-1]
    # our own Reference/Value replace the library's
    inner = strip_prop(strip_prop(inner, "Reference"), "Value")
    # Replace the library's IPC-nominal courtyard with the density-level-C
    # rectangle place.py packed against, so DRC checks the same geometry the
    # solver used. Leaving the stock outline here would report overlaps that the
    # placer never allowed, and vice versa.
    inner = strip_layer(inner, "CrtYd")
    cw, ch, ccx, ccy = geom.courtyard(comp["fp"])
    inner += (f'\n\t\t(fp_rect\n\t\t\t(start {ccx-cw/2:g} {ccy-ch/2:g})\n'
              f'\t\t\t(end {ccx+cw/2:g} {ccy+ch/2:g})\n'
              f'\t\t\t(stroke (width 0.05) (type solid))\n\t\t\t(fill none)\n'
              f'\t\t\t(layer "F.CrtYd")\n\t\t\t(uuid "{uid("cy", ref)}")\n\t\t)')
    if side == 'B':
        inner = mirror_text(swap_layers(mirror_y(inner)))
    if rot:
        # KiCad rotates a footprint's pad POSITIONS by the footprint orientation but
        # takes the pad SHAPE angle from the pad's own (at x y angle) field, so the
        # rotation has to be written into every pad and text item explicitly.
        def addrot(m):
            a = (float(m.group(3)) if m.group(3) else 0.0) + rot
            return f"(at {m.group(1)} {m.group(2)} {a % 360:g})"
        out, pos = [], 0
        while True:
            mm = re.compile(r'\((?:pad|fp_text)\b').search(inner, pos)
            if not mm: out.append(inner[pos:]); break
            end = _span(inner, mm.start()); b = inner[mm.start():end]
            b = re.sub(r'\(at (-?[\d.]+) (-?[\d.]+)(?: (-?[\d.]+))?\)', addrot, b, count=1)
            out.append(inner[pos:mm.start()]); out.append(b); pos = end
        inner = "".join(out)
    inner = set_pad_nets(inner, comp["pins"], code)
    ly = "B.Cu" if side == 'B' else "F.Cu"
    txt_layer = "B.SilkS" if side == 'B' else "F.SilkS"
    fab_layer = "B.Fab" if side == 'B' else "F.Fab"
    mir = "\n\t\t\t\t(justify mirror)" if side == 'B' else ""
    head = (f'\t(footprint "{comp["fp"]}"\n'
            f'\t\t(layer "{ly}")\n'
            f'\t\t(uuid "{uid("fp", ref)}")\n'
            f'\t\t(at {x:g} {y:g}{"" if rot == 0 else " " + str(rot)})\n'
            f'\t\t(property "Reference" "{ref}"\n\t\t\t(at 0 -{2.2:g} 0)\n'
            f'\t\t\t(layer "{fab_layer}")\n\t\t\t(uuid "{uid("fpr", ref)}")\n'
            f'\t\t\t(effects (font (size 0.8 0.8) (thickness 0.15)){mir})\n\t\t)\n'
            f'\t\t(property "Value" "{comp["val"]}"\n\t\t\t(at 0 {2.2:g} 0)\n'
            f'\t\t\t(layer "{fab_layer}")\n\t\t\t(hide yes)\n\t\t\t(uuid "{uid("fpv", ref)}")\n'
            f'\t\t\t(effects (font (size 0.8 0.8) (thickness 0.15)){mir})\n\t\t)\n')
    for k, v in (("LCSC", comp.get("lcsc")), ("MPN", comp.get("mpn"))):
        if v:
            head += (f'\t\t(property "{k}" "{v}"\n\t\t\t(at 0 0 0)\n'
                     f'\t\t\t(layer "{fab_layer}")\n\t\t\t(hide yes)\n'
                     f'\t\t\t(uuid "{uid("fp"+k, ref)}")\n'
                     f'\t\t\t(effects (font (size 0.8 0.8) (thickness 0.15)))\n\t\t)\n')
    return head + inner + "\n\t)\n"

def main():
    final, failed = place.solve()
    assert not failed, failed
    parts = {c["ref"]: c for c in design.COMPONENTS if c.get("fp")}
    W, H, R = board.W, board.H, board.CORNER_R

    nets = sorted({n for c in parts.values() for n in c["pins"].values()
                   if n and n != "!NC"})
    code = {n: i + 1 for i, n in enumerate(nets)}

    out = [open(os.path.join(HERE, "pcb_header.tpl")).read()]
    out.append('\t(net 0 "")\n')
    for n, i in sorted(code.items(), key=lambda kv: kv[1]):
        out.append(f'\t(net {i} "{n}")\n')
    for ref in sorted(final):
        x, y, rot, side = final[ref]
        out.append(emit_footprint(ref, parts[ref], x, y, rot, side, code))

    # ------------------------------------------------- outline + mounting holes
    seg = lambda x1,y1,x2,y2,t: (
        f'\t(gr_line (start {x1:g} {y1:g}) (end {x2:g} {y2:g})\n'
        f'\t\t(stroke (width 0.1) (type solid)) (layer "Edge.Cuts") (uuid "{uid(t)}"))\n')
    arc = lambda sx,sy,mx,my,ex,ey,t: (
        f'\t(gr_arc (start {sx:g} {sy:g}) (mid {mx:g} {my:g}) (end {ex:g} {ey:g})\n'
        f'\t\t(stroke (width 0.1) (type solid)) (layer "Edge.Cuts") (uuid "{uid(t)}"))\n')
    k = R - R*math.sqrt(0.5)
    out += [seg(R,0,W-R,0,"e1"), seg(W,R,W,H-R,"e2"), seg(W-R,H,R,H,"e3"), seg(0,H-R,0,R,"e4"),
            arc(W-R,0,W-k,k,W,R,"a1"), arc(W,H-R,W-k,H-k,W-R,H,"a2"),
            arc(R,H,k,H-k,0,H-R,"a3"), arc(0,R,k,k,R,0,"a4")]
    for n,(hx,hy) in enumerate(board.HOLE_XY):
        out.append(
            f'\t(footprint "fc_f405:MountingHole_4.0mm"\n\t\t(layer "F.Cu")\n'
            f'\t\t(uuid "{uid("mh",n)}")\n\t\t(at {hx:g} {hy:g})\n'
            f'\t\t(attr through_hole exclude_from_pos_files exclude_from_bom)\n'
            f'\t\t(property "Reference" "H{n+1}"\n\t\t\t(at 0 -3.2 0)\n\t\t\t(layer "F.SilkS")\n'
            f'\t\t\t(hide yes)\n\t\t\t(uuid "{uid("mhr",n)}")\n'
            f'\t\t\t(effects (font (size 0.8 0.8) (thickness 0.15))))\n'
            f'\t\t(property "Value" "M3"\n\t\t\t(at 0 3.2 0)\n\t\t\t(layer "F.Fab")\n'
            f'\t\t\t(hide yes)\n\t\t\t(uuid "{uid("mhv",n)}")\n'
            f'\t\t\t(effects (font (size 0.8 0.8) (thickness 0.15))))\n'
            f'\t\t(pad "" np_thru_hole circle\n\t\t\t(at 0 0)\n'
            f'\t\t\t(size {board.HOLE_D:g} {board.HOLE_D:g})\n\t\t\t(drill {board.HOLE_D:g})\n'
            f'\t\t\t(layers "F&B.Cu" "F&B.Mask")\n\t\t\t(uuid "{uid("mhp",n)}"))\n\t)\n')

    # --------------------------------------------- routing + plane stitching
    tracks, vias, rep, copper, ok, pads, via_free = route.plan(final, parts, code)
    gnd_added, thermal = stitch.build(final, parts, code, copper, ok, pads, vias, via_free)
    for x1,y1,x2,y2,net,layer,w in tracks:
        out.append(f'\t(segment\n\t\t(start {x1:g} {y1:g})\n\t\t(end {x2:g} {y2:g})\n'
                   f'\t\t(width {w:g})\n\t\t(layer "{layer}")\n\t\t(net {code[net]})\n'
                   f'\t\t(uuid "{uid("seg",x1,y1,x2,y2,net,layer)}")\n\t)\n')
    for vx,vy,net in vias:
        out.append(f'\t(via\n\t\t(at {vx:g} {vy:g})\n\t\t(size {route.VIA_D:g})\n'
                   f'\t\t(drill {route.VIA_DRILL:g})\n\t\t(layers "F.Cu" "B.Cu")\n'

                   f'\t\t(net {code[net]})\n\t\t(uuid "{uid("via",vx,vy,net)}")\n\t)\n')

    # --------------------------------------------------------------- pours
    def poly(x0,y0,x1,y1):
        return ("\t\t(polygon\n\t\t\t(pts\n"
                f"\t\t\t\t(xy {x0:g} {y0:g}) (xy {x1:g} {y0:g})\n"
                f"\t\t\t\t(xy {x1:g} {y1:g}) (xy {x0:g} {y1:g})\n\t\t\t)\n\t\t)\n")
    def zone(net, layers, x0, y0, x1, y1, tag, prio=0, solid=False):
        # inner planes take a solid pad connection: lower impedance, and thermal
        # spokes on a plane are what produce starved_thermal errors
        cp = ('yes\n\t\t\t(clearance 0.2)' if solid else '\n\t\t\t(clearance 0.2)')
        return (f'\t(zone\n\t\t(net {code.get(net,0)})\n\t\t(net_name "{net}")\n'
                f'\t\t(layers {layers})\n\t\t(uuid "{uid("z",tag)}")\n\t\t(name "{tag}")\n'
                f'\t\t(hatch edge 0.5)\n\t\t(priority {prio})\n'
                f'\t\t(connect_pads {cp}\n\t\t)\n'
                f'\t\t(min_thickness 0.2)\n\t\t(filled_areas_thickness no)\n'
                f'\t\t(fill yes\n\t\t\t(thermal_gap 0.25)\n\t\t\t(thermal_bridge_width 0.5)\n'
                f'\t\t\t(smoothing chamfer)\n\t\t\t(radius 0.3)\n\t\t)\n'
                + poly(x0,y0,x1,y1) + '\t)\n')
    def circle_pts(cx, cy, r, n=48):
        pts = "".join(f"\t\t\t\t(xy {cx+r*math.cos(2*math.pi*i/n):.3f} "
                      f"{cy+r*math.sin(2*math.pi*i/n):.3f})\n" for i in range(n))
        return "\t\t(polygon\n\t\t\t(pts\n" + pts + "\t\t\t)\n\t\t)\n"

    def keepout(layers, x0, y0, x1, y1, tag, pour_only=False, circle=None):
        t = ("(tracks allowed) (vias allowed) (pads allowed)" if pour_only
             else "(tracks not_allowed) (vias not_allowed) (pads not_allowed)")
        return (f'\t(zone\n\t\t(net 0)\n\t\t(net_name "")\n\t\t(layers {layers})\n'
                f'\t\t(uuid "{uid("ko",tag)}")\n\t\t(name "{tag}")\n\t\t(hatch edge 0.5)\n'
                f'\t\t(connect_pads\n\t\t\t(clearance 0)\n\t\t)\n\t\t(min_thickness 0.25)\n'
                f'\t\t(keepout {t} (copperpour not_allowed) (footprints allowed))\n'
                f'\t\t(fill\n\t\t\t(thermal_gap 0.5)\n\t\t\t(thermal_bridge_width 0.5)\n\t\t)\n'
                + (circle_pts(*circle) if circle else poly(x0,y0,x1,y1)) + '\t)\n')
    B = 0.35
    ALL = '"F.Cu" "In1.Cu" "In2.Cu" "B.Cu"'
    out.append(zone("GND", '"In1.Cu"', B,B,W-B,H-B, "L2_GND_plane", 10, solid=True))
    # In2 is a routing layer now (sec 7.1 as amended): the rails are wide traces
    # on it and this pour takes whatever copper is left, which keeps the layer
    # balanced for fab and gives the In2 traces a local return.
    out.append(zone("GND", '"In2.Cu"', B,B,W-B,H-B, "L3_GND", 1, solid=True))
    # solid, not thermal-relieved: a 0402 GND pad can only ever get one spoke,
    # which is exactly what starved_thermal flags, and thermal relief exists for
    # hand soldering - this board is reflow-assembled by JLCPCB
    out.append(zone("GND", '"F.Cu"', B,B,W-B,H-B, "F_GND", 1, solid=True))
    out.append(zone("GND", '"B.Cu"', B,B,W-B,H-B, "B_GND", 1, solid=True))
    # the old In2 keep-out existed to stop a POWER pour sitting under the gyro
    # (sec 7.2). In2 under the gyro is ground now, which is what that section
    # wanted; the "no motor or switch node beneath" half of the rule is enforced
    # in route.py, which keeps those nets out of a 3.5 mm disc on every layer.
    for n,(hx,hy) in enumerate(board.HOLE_XY):
        r = board.HOLE_KEEPOUT_R
        # circular, matching the 1.5 mm ring the placer enforces (sec 7.4)
        # pads allowed so the hole's own NPTH pad is legal; the placer already
        # keeps every other component out of the 1.5 mm ring (sec 7.4)
        out.append(keepout(ALL, 0,0,0,0, f"holeKeepout{n+1}",
                           pour_only=True, circle=(hx, hy, r)))
    out.append(")\n")
    open(PCB, "w").write("".join(out))
    print(f"board written: {len(final)} footprints, {len(code)} nets, "
          f"{W}x{H} mm, corner R{R}, 4 x M3")

    ngnd = sum(1 for _,_,n in vias if n == "GND")
    print(f"routing: {rep['signal_ok']} of {rep['signal_need']} connections made, "
          f"{len(rep['signal_fail'])} failed")
    print(f"         {len(tracks)} segments, {len(vias)} vias "
          f"({ngnd} GND / {len(vias)-ngnd} signal+power), {thermal} thermal")
    bad = route.selfcheck(tracks, vias, pads, code)
    print(f"   self-check against the router's own rules: {len(bad)} violation(s)")
    for b in bad[:8]: print("     ! " + b)
    if rep["signal_fail"]: print("   unrouted: " + ", ".join(rep["signal_fail"][:14]))


if __name__ == "__main__":
    main()
