"""Emit fc_f405.kicad_sch from the declarative design in design.py.

Every component pin that carries a net gets a short wire stub terminated in a net
label; same-named labels are one net in KiCad's connectivity engine. Pins listed as
NC get a no_connect flag instead. All symbols are placed at rotation 0 so the
symbol->sheet transform stays (cx+px, cy-py).
"""
import sys, os, uuid, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ksym

GRID = 1.27          # KiCad's default connection grid
STUB = 3.81          # 3 x GRID          # mm of wire between pin end and its label
PROJLIB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")

_ns = uuid.UUID("6f1c9a42-0000-4000-8000-fc405f405f40")
def snap(pt):
    """Round a placement onto the connection grid; pin offsets are grid multiples,
    so an on-grid origin guarantees on-grid pin ends."""
    return (round(round(pt[0] / GRID) * GRID, 4), round(round(pt[1] / GRID) * GRID, 4))

def uid(*parts):
    return str(uuid.uuid5(_ns, "|".join(str(p) for p in parts)))

def sympins(lib_id):
    """Pin table for a symbol, following (extends "parent") for derived symbols."""
    lib, sym = lib_id.split(":", 1)
    old = ksym.LIBDIR
    if lib == "fc_f405": ksym.LIBDIR = PROJLIB
    try:
        for _ in range(8):
            p = ksym.pins(lib, sym)
            if p: return p
            ext = ksym.find(ksym.parse(ksym.raw_symbol(lib, sym)), "extends")
            if not ext: return p
            sym = ext[1]
        raise RuntimeError("extends chain too deep: " + lib_id)
    finally: ksym.LIBDIR = old

def _block(txt, marker, frm=0):
    """Raw text of the s-expression starting at `marker`, brackets balanced."""
    i = txt.find(marker, frm)
    if i < 0: return None, -1
    depth, j, instr = 0, i, False
    while j < len(txt):
        c = txt[j]
        if instr:
            if c == '\\': j += 2; continue
            if c == '"': instr = False
        elif c == '"': instr = True
        elif c == '(': depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0: return txt[i:j+1], j + 1
        j += 1
    return None, -1

_DERIVED_CACHE = None
def _cached(lib_id):
    global _DERIVED_CACHE
    if _DERIVED_CACHE is None:
        import json
        f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache",
                         "derived_symbols.json")
        _DERIVED_CACHE = json.load(open(f)) if os.path.exists(f) else {}
    return _DERIVED_CACHE.get(lib_id)

def rawsym(lib_id):
    """Symbol text ready to drop into a schematic's lib_symbols.

    Derived symbols (`(extends "Parent")`) are flattened the way KiCad does it:
    the parent's _0_1 / _1_1 sub-symbol blocks are spliced in and renamed to the
    child, and the child keeps its own property overrides.
    """
    hit = _cached(lib_id)
    if hit: return hit
    lib, sym = lib_id.split(":", 1)
    old = ksym.LIBDIR
    if lib == "fc_f405": ksym.LIBDIR = PROJLIB
    try:
        txt = ksym.raw_symbol(lib, sym)
        ext = ksym.find(ksym.parse(txt), "extends")
        if ext:
            parent = ext[1]
            ptxt = ksym.raw_symbol(lib, parent)
            subs, pos = [], 0
            while True:
                blk, pos = _block(ptxt, '(symbol "%s_' % parent, pos)
                if blk is None: break
                subs.append(blk.replace('(symbol "%s_' % parent,
                                        '(symbol "%s_' % sym, 1))
            txt = txt.replace('(extends "%s")' % parent, "\n".join(subs))
        return txt.replace('(symbol "%s"' % sym, '(symbol "%s"' % lib_id, 1)
    finally: ksym.LIBDIR = old

def _ser(n):
    out = []
    for c in n:
        if isinstance(c, list): out.append(_ser(c))
        elif c and (c[0].isalpha() or c[0] == '_') and all(
                ch.isalnum() or ch in "_-./+~{}" for ch in c): out.append(c)
        else: out.append('"%s"' % c.replace('\\', '\\\\').replace('"', '\\"'))
    return "(" + " ".join(out) + ")"

def build(design, out_path, paper="A1"):
    comps, texts = design.COMPONENTS, design.TEXTS
    used = sorted({c["lib"] for c in comps})
    L = ['(kicad_sch (version 20260101) (generator "fc_f405_gen") (generator_version "10.0")',
         f'  (uuid "{uid("sheet")}")', f'  (paper "{paper}")', '  (lib_symbols']
    for lid in used:
        L.append("    " + rawsym(lid).replace("\n", "\n    "))
    L.append('  )')

    wires, labels, ncs = [], [], []
    for c in comps:
        pins = sympins(c["lib"])
        cx, cy = snap(c["at"])
        for pnum, pdata in pins.items():
            net = c["pins"].get(pnum)
            px, py, ang = pdata["x"], pdata["y"], pdata["angle"]
            sx, sy = round(cx + px, 3), round(cy - py, 3)
            dx, dy = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[int(ang) % 360]
            ex, ey = round(sx + dx * STUB, 3), round(sy + dy * STUB, 3)
            if net is None:
                if pdata["etype"] != "no_connect":
                    ncs.append(f'  (no_connect (at {sx} {sy}) (uuid "{uid("nc",c["ref"],pnum)}"))')
                continue
            if net == "!NC":
                ncs.append(f'  (no_connect (at {sx} {sy}) (uuid "{uid("nc",c["ref"],pnum)}"))')
                continue
            wires.append(f'  (wire (pts (xy {sx} {sy}) (xy {ex} {ey}))\n'
                         f'    (stroke (width 0) (type default)) (uuid "{uid("w",c["ref"],pnum)}"))')
            # global labels: the net is "GND", not the sheet-local "/GND", so its
            # name matches the board's (built from the same design.py)
            if dx < 0:   lang, just = 180, "right"
            elif dx > 0: lang, just = 0, "left"
            elif dy > 0: lang, just = 270, "right"
            else:        lang, just = 90, "left"
            labels.append(f'  (global_label "{net}" (shape passive) (at {ex} {ey} {lang})\n'
                          f'    (effects (font (size 1.27 1.27)) (justify {just}))\n'
                          f'    (uuid "{uid("l",c["ref"],pnum)}"))')
    L += wires + labels + ncs

    for t in texts:
        L.append(f'  (text "{t["s"]}" (at {t["at"][0]} {t["at"][1]} 0)\n'
                 f'    (effects (font (size {t.get("sz",2.0)} {t.get("sz",2.0)}) (bold yes))'
                 f' (justify left bottom)) (uuid "{uid("t",t["s"],t["at"][0])}"))')

    for c in comps:
        cx, cy = snap(c["at"])
        u = uid("sym", c["ref"])
        L.append(f'  (symbol (lib_id "{c["lib"]}") (at {cx} {cy} 0) (unit 1)')
        virt = c["ref"].startswith("#")                  # PWR_FLAG: schematic only
        bare = c.get("fp", "").startswith("fc_f405:SolderPad")   # wire pads: copper, not a part
        bom = "no" if virt or c.get("mech") or bare else "yes"
        brd = "no" if virt else "yes"
        L.append(f'    (body_style 1) (exclude_from_sim no) (in_bom {bom}) (on_board {brd}) (in_pos_files {bom}) (dnp no) (uuid "{u}")')
        L.append(f'    (property "Reference" "{c["ref"]}" (at {cx} {round(cy-c.get("rdy",12.7),3)} 0)'
                 f' (effects (font (size 1.27 1.27)) (justify left)))')
        L.append(f'    (property "Value" "{c["val"]}" (at {cx} {round(cy-c.get("vdy",10.16),3)} 0)'
                 f' (effects (font (size 1.27 1.27)) (justify left)))')
        L.append(f'    (property "Footprint" "{c.get("fp","")}" (at {cx} {cy} 0)'
                 f' (hide yes) (effects (font (size 1.27 1.27))))')
        L.append(f'    (property "Datasheet" "{c.get("ds","~")}" (at {cx} {cy} 0)'
                 f' (hide yes) (effects (font (size 1.27 1.27))))')
        if c.get("lcsc"):
            L.append(f'    (property "LCSC" "{c["lcsc"]}" (at {cx} {cy} 0)'
                     f' (hide yes) (effects (font (size 1.27 1.27))))')
        if c.get("mpn"):
            L.append(f'    (property "MPN" "{c["mpn"]}" (at {cx} {cy} 0)'
                     f' (hide yes) (effects (font (size 1.27 1.27))))')
        for pnum in sorted(sympins(c["lib"])):
            L.append(f'    (pin "{pnum}" (uuid "{uid("p",c["ref"],pnum)}"))')
        L.append(f'    (instances (project "fc_f405" (path "/{uid("sheet")}"'
                 f' (reference "{c["ref"]}") (unit 1))))')
        L.append('  )')

    L.append(f'  (sheet_instances (path "/" (page "1")))')
    L.append(')')
    open(out_path, "w").write("\n".join(L) + "\n")
    return len(comps), len(wires), len(labels), len(ncs)

if __name__ == "__main__":
    import design
    n = build(design, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fc_f405.kicad_sch"))
    print("components=%d wires=%d labels=%d no-connects=%d" % n)
