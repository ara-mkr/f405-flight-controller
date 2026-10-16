"""Checklist item 6: for every part, the symbol's pin numbers must equal the
footprint's pad numbers. This is where the most expensive errors hide."""
import sys, os, re, glob
sys.path.insert(0,'.')
import design, mksch

STOCK = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
PROJ  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib", "fc_f405.pretty")

def fp_pads(fpid):
    lib, name = fpid.split(":", 1)
    path = (os.path.join(PROJ, name + ".kicad_mod") if lib == "fc_f405"
            else os.path.join(STOCK, lib + ".pretty", name + ".kicad_mod"))
    if not os.path.exists(path): return None, path
    txt = open(path).read()
    pads = re.findall(r'\(pad\s+("(?:[^"]*)"|\S+)\s', txt)
    return {p.strip('"') for p in pads if p.strip('"') != ""}, path

bad, ok = [], 0
for c in sorted(design.COMPONENTS, key=lambda d: d["ref"]):
    fpid = c.get("fp", "")
    if not fpid:
        if not c["ref"].startswith("#FLG"): bad.append(f"{c['ref']}: no footprint assigned")
        continue
    pads, path = fp_pads(fpid)
    if pads is None:
        bad.append(f"{c['ref']}: footprint file missing -> {path}"); continue
    pins = set(mksch.sympins(c["lib"]))
    missing = pins - pads
    extra   = pads - pins
    if missing:
        bad.append(f"{c['ref']} [{c['val']}] {fpid.split(':')[-1]}: "
                   f"symbol pins with NO pad: {sorted(missing)}")
    elif extra:
        # extra pads are fine only when they are mechanical (mounting/shield)
        bad.append(f"{c['ref']} [{c['val']}] {fpid.split(':')[-1]}: "
                   f"footprint pads with no symbol pin: {sorted(extra)}  (review)")
    else:
        ok += 1

print("=" * 72)
print(f"symbol/footprint pad map: {ok} parts match exactly, {len(bad)} to review")
print("=" * 72)
for b in bad: print("  *", b)
