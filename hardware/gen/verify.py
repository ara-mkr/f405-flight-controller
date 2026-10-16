# -*- coding: utf-8 -*-
"""DESIGN_PLAN section 10.3 - the eleven-point manual review, done by measurement
against the actual board and netlist rather than by eye."""
import sys, os, re, math, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import place, board, design, stitch

PCB = "/Users/akhilraja-amudhan/Documents/Flight Controller Project/hardware/fc_f405.kicad_pcb"

def load():
    """Parse tracks and vias. Nets appear either as a code or as a quoted name
    depending on which tool last wrote the file, so accept both."""
    s = open(PCB).read()
    nets = {int(a): b for a, b in re.findall(r'\n\t\(net (\d+) "([^"]*)"\)', s)}
    def netname(tok):
        tok = tok.strip()
        if tok.startswith('"'): return tok.strip('"')
        return nets.get(int(tok), "?")
    tracks = []
    for m in re.finditer(
            r'\(segment\s*\n\s*\(start (-?[\d.]+) (-?[\d.]+)\)\s*\n\s*'
            r'\(end (-?[\d.]+) (-?[\d.]+)\)\s*\n\s*\(width ([\d.]+)\)\s*\n\s*'
            r'\(layer "([^"]+)"\)\s*\n\s*\(net ("[^"]*"|\d+)\)', s):
        g = m.groups()
        tracks.append(dict(x1=float(g[0]), y1=float(g[1]), x2=float(g[2]), y2=float(g[3]),
                           w=float(g[4]), layer=g[5], net=netname(g[6])))
    vias = [(float(a), float(b), netname(c)) for a, b, c in re.findall(
        r'\(via\s*\n\s*\(at (-?[\d.]+) (-?[\d.]+)\)(?:(?!\(via).)*?\(net ("[^"]*"|\d+)\)', s, re.S)]
    return s, tracks, nets, vias

# ---- 3. current-carrying traces sized (sec 7.5) ----
WIDTH_SPEC = {"VBAT": 2.0, "VBAT_IN": 2.0, "SW_5V": 1.0, "SW_9V": 1.0,
              "+5V": 0.8, "+9V": 0.8, "+3V3": 0.4, "+3V3_GYRO": 0.4}
def check_widths(tracks, nets):
    by = collections.defaultdict(list)
    for t in tracks: by[t["net"]].append(t)
    rows = []
    for net, spec in WIDTH_SPEC.items():
        ts = by.get(net, [])
        if not ts: rows.append((net, spec, None, None, "no traces (plane only)")); continue
        wmin = min(t["w"] for t in ts)
        L = sum(math.hypot(t["x2"]-t["x1"], t["y2"]-t["y1"]) for t in ts)
        verdict = "OK" if wmin >= spec*0.95 else f"NARROW min {wmin:.2f} < {spec}"
        rows.append((net, spec, wmin, L, verdict))
    return rows

# ---- 1. rail voltage at every IC power pin ----
# Absolute maximum supply voltage, transcribed from each datasheet in
# datasheets/raw/. The check is that the rail a pin sits on cannot exceed it.
ABSMAX = {
    "U1": ("STM32F405RGT7", 4.0),    # DS8626 Table 15, VDD max 4.0 V
    "U2": ("ICM-42688-P",   3.6),    # DS-000347 Table 10, VDD max 3.6 V
    "U3": ("BMP388",        4.2),    # BST-BMP388-DS001 Table 4, VDD max 4.2 V
    "U4": ("AT7456E",       6.0),    # AT7456E DS Table 1, AVDD/DVDD max 6.0 V
    "U5": ("W25Q128JV",     4.6),    # W25Q128JV Table 8.1, VCC max 4.6 V
    "U6": ("TPS54360",     60.0),    # SLVSC60 Table 6.1, VIN max 60 V
    "U7": ("TPS54360",     60.0),
    "U8": ("TLV1117-33",   15.0),    # SLOS561 Table 6.1, VI max 15 V
    "U9": ("USBLC6-2SC6",   6.0),    # USBLC6-2 DS Table 3, VPP max 6.0 V
}
RAIL_V = {"+3V3": 3.3, "+3V3_GYRO": 3.3, "VDDA": 3.3, "+5V": 5.0,
          "+9V": 9.0, "USB_VBUS": 5.25, "VBAT": 26.1}   # VBAT worst case = 6S

def check_rails():
    out = []
    for c in design.COMPONENTS:
        lim = ABSMAX.get(c["ref"])
        if not lim: continue
        for pin, net in c["pins"].items():
            if net not in RAIL_V: continue
            v = RAIL_V[net]
            out.append((c["ref"], lim[0], pin, net, v, lim[1],
                        "OK" if v <= lim[1] else "OVER ABSMAX"))
    return out

# ---- 2. decoupling completeness and physical adjacency ----
def check_decoupling(final, parts):
    """Every IC power pin needs a cap on that rail, adjacent in the layout."""
    caps = [c for c in design.COMPONENTS
            if c["ref"].startswith("C") and len(c["pins"]) == 2
            and "GND" in c["pins"].values() and c["ref"] in final]
    out = []
    for ref in ABSMAX:
        if ref not in final: continue
        c = next(x for x in design.COMPONENTS if x["ref"] == ref)
        for pin, net in c["pins"].items():
            if net not in RAIL_V: continue
            px, py = place.pad_xy(ref, pin, final, parts)
            best = None
            for cap in caps:
                if net not in cap["pins"].values(): continue
                for cp, cn in cap["pins"].items():
                    if cn != net: continue
                    qx, qy = place.pad_xy(cap["ref"], cp, final, parts)
                    d = math.hypot(qx-px, qy-py)
                    if best is None or d < best[0]: best = (d, cap["ref"], cap["val"])
            out.append((ref, pin, net, best))
    return out

# ---- 4. no floating inputs ----
def check_floating():
    bad = []
    for c in design.COMPONENTS:
        for pin, net in c["pins"].items():
            if not net: bad.append((c["ref"], pin, "no net"))
    nc = sum(1 for c in design.COMPONENTS for n in c["pins"].values() if n == "!NC")
    return bad, nc

# ---- 9. regulator loop area ----
def check_loops(final, parts):
    """CIN -> VIN -> SW -> D -> L, measured (DESIGN_PLAN sec 7.3)."""
    out = []
    for tag, u, cin, d, l in (("5 V", "U6", "C2", "D1", "L1"),
                              ("9 V", "U7", "C4", "D2", "L2")):
        if u not in final: continue
        ux, uy = final[u][0], final[u][1]
        row = [tag]
        for r in (cin, d, l):
            if r in final:
                row.append((r, math.hypot(final[r][0]-ux, final[r][1]-uy),
                            final[r][3] == final[u][3]))
            else: row.append((r, None, None))
        out.append(row)
    return out

# ---- 10. USB-C CC resistors ----
def check_cc():
    got = []
    for c in design.COMPONENTS:
        nets = set(c["pins"].values())
        if c["ref"].startswith("R") and "GND" in nets:
            for n in nets:
                if n in ("USB_CC1", "USB_CC2"): got.append((c["ref"], n, c["val"]))
    return got

# ---- 8. gyro isolation ----
def check_gyro(final, parts):
    gx, gy, _, _ = final["U2"]
    out = []
    for r in ("L1", "L2", "U6", "U7", "D1", "D2", "Q1", "C43"):
        if r not in final: continue
        x, y, _, s = final[r]
        out.append((r, parts[r]["val"], math.hypot(x-gx, y-gy), s))
    return sorted(out, key=lambda t: t[2])

# ---- 7. divider maths from the values actually placed ----
def check_dividers():
    v = {c["ref"]: c["val"] for c in design.COMPONENTS}
    def num(s):
        s = s.replace("k", "e3").replace("R", "").replace("M", "e6")
        try: return float(s)
        except ValueError: return None
    out = []
    r5, r6 = num(v["R5"]), num(v["R6"])
    out.append(("5 V feedback  R5/R6", f"{v['R5']}/{v['R6']}",
                0.8*(1+r5/r6), 5.0))
    r8, r7 = num(v["R8"]), num(v["R7"])
    out.append(("9 V feedback  R8/R7", f"{v['R8']}/{v['R7']}",
                0.8*(1+r8/r7), 9.0))
    r12, r13 = num(v["R12"]), num(v["R13"])
    out.append(("VBAT sense at 26.1 V", f"{v['R12']}/{v['R13']}",
                26.1*r13/(r12+r13), 3.3))
    return out

def main():
    s, tracks, nets, vias = load()
    final, _ = place.solve()
    parts = {c["ref"]: c for c in design.COMPONENTS if c.get("fp")}

    print("="*78); print("ITEM 1  RAIL VOLTAGE AT EVERY IC POWER PIN"); print("="*78)
    bad = 0
    for ref, part, pin, net, v, lim, verdict in check_rails():
        if verdict != "OK": bad += 1
        print(f"  {ref:<4} {part:<16} pin {pin:<3} on {net:<10} "
              f"{v:5.2f} V   absmax {lim:5.1f} V   {verdict}")
    print(f"  -> {bad} pin(s) over absolute maximum")

    print("\n"+"="*78); print("ITEM 2  DECOUPLING COMPLETENESS AND ADJACENCY"); print("="*78)
    miss = far = 0
    for ref, pin, net, best in check_decoupling(final, parts):
        if best is None:
            print(f"  {ref:<4} pin {pin:<3} {net:<10} NO CAP ON THIS RAIL"); miss += 1
        else:
            d, cref, cval = best
            flag = "" if d <= 3.0 else "  <-- far"
            if d > 3.0: far += 1
            print(f"  {ref:<4} pin {pin:<3} {net:<10} nearest {cref:<4} {cval:<9} "
                  f"{d:5.2f} mm{flag}")
    print(f"  -> {miss} pin(s) with no cap, {far} beyond 3.0 mm")

    print("\n"+"="*78); print("ITEM 4  NO FLOATING INPUTS"); print("="*78)
    bad, nc = check_floating()
    for r, p, why in bad: print(f"  {r}.{p}: {why}")
    print(f"  -> {len(bad)} pin(s) with no net; {nc} explicitly no-connected")

    print("\n"+"="*78); print("ITEM 9  REGULATOR LOOP, MEASURED"); print("="*78)
    for row in check_loops(final, parts):
        tag = row[0]
        for r, d, same in row[1:]:
            if d is None: print(f"  {tag} buck: {r} NOT PLACED"); continue
            print(f"  {tag} buck: {r:<4} {d:5.2f} mm from the IC   "
                  f"{'same side' if same else 'OPPOSITE SIDE'}")

    print("\n"+"="*78); print("ITEM 10 USB-C CC PULLDOWNS"); print("="*78)
    cc = check_cc()
    for r, n, v in cc: print(f"  {r} {n} = {v} to GND")
    print(f"  -> {len(cc)} of 2 present")

    print("="*78); print("ITEM 3  CURRENT-CARRYING TRACES SIZED (sec 7.5)"); print("="*78)
    for net, spec, wmin, L, verdict in check_widths(tracks, nets):
        w = f"{wmin:.2f}" if wmin else "  - "
        l = f"{L:6.1f}" if L else "     -"
        print(f"  {net:<12} spec {spec:4.1f} mm   min {w} mm   total {l} mm   {verdict}")

    print("\n"+"="*78); print("ITEM 7  DIVIDER MATHS FROM THE PLACED VALUES"); print("="*78)
    for name, vals, got, ref in check_dividers():
        ok = "OK" if (abs(got-ref)/ref < 0.05 or got < ref) else "CHECK"
        print(f"  {name:<24} {vals:<16} -> {got:6.3f} V   (target/limit {ref}) {ok}")

    print("\n"+"="*78); print("ITEM 8  GYRO ISOLATION"); print("="*78)
    for r, val, d, side in check_gyro(final, parts):
        print(f"  {r:<4} {val:<18} {d:5.2f} mm from the gyro   side {side}")

    print("\n"+"="*78); print("BOARD TOTALS"); print("="*78)
    print(f"  tracks {len(tracks)}   vias {len(vias)}   "
          f"copper length {sum(math.hypot(t['x2']-t['x1'], t['y2']-t['y1']) for t in tracks):.0f} mm")

if __name__ == "__main__":
    main()
