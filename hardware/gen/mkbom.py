# -*- coding: utf-8 -*-
"""Ordering BOM, grouped by identical part, with LCSC codes and JLCPCB stock."""
import sys, os, sqlite3, collections, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design

DB = os.path.expanduser("~/Library/Application Support/kicad-mcp/jlcpcb_parts.db")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "docs")

def main():
    con = sqlite3.connect(DB); cur = con.cursor()
    groups = collections.defaultdict(list)
    for c in design.COMPONENTS:
        if not c.get("fp") or c.get("mech"): continue   # PWR_FLAGs / mounting holes
        groups[(c["val"], c.get("mpn",""), c.get("lcsc",""), c["fp"])].append(c["ref"])

    def refkey(r):
        i = len(r)
        while i and r[i-1].isdigit(): i -= 1
        return (r[:i], int(r[i:] or 0))

    rows = []
    for (val, mpn, lcsc, fp), refs in groups.items():
        stock = lib = ""
        if lcsc:
            cur.execute("SELECT stock, library_type, mfr_part FROM components WHERE lcsc=?", (lcsc,))
            r = cur.fetchone()
            if r: stock, lib, dbmpn = r[0], r[1], r[2]
        rows.append(dict(refs=",".join(sorted(refs, key=refkey)), qty=len(refs),
                         value=val, mpn=mpn, lcsc=lcsc, footprint=fp.split(":")[-1],
                         stock=stock, type=lib))
    rows.sort(key=lambda r: refkey(r["refs"].split(",")[0]))

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "BOM.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, ["refs","qty","value","mpn","lcsc","footprint","stock","type"])
        w.writeheader(); w.writerows(rows)

    print(f"{'Refs':<26} {'Qty':>3} {'Value':<18} {'MPN':<26} {'LCSC':<11} {'Stock':>8} Type")
    print("-"*112)
    for r in rows:
        print(f"{r['refs'][:25]:<26} {r['qty']:>3} {r['value'][:17]:<18} "
              f"{str(r['mpn'])[:25]:<26} {r['lcsc']:<11} {str(r['stock']):>8} {r['type']}")
    print("-"*112)
    print(f"{len(rows)} unique parts, {sum(r['qty'] for r in rows)} placements")
    basic = [r for r in rows if r["type"] in ("Basic","Preferred")]
    ext   = [r for r in rows if r["type"] == "Extended"]
    nostk = [r for r in rows if not r["lcsc"]]
    print(f"Basic/Preferred (free assembly): {len(basic)}   Extended ($3 setup each): {len(ext)}"
          f"   -> extended setup cost ~${3*len(ext)}")
    if nostk: print("NO LCSC CODE: " + ", ".join(r["refs"] for r in nostk))
    low = [r for r in rows if r["stock"] != "" and isinstance(r["stock"], int) and r["stock"] < 2000]
    if low:
        print("\nLOW STOCK (<2000):")
        for r in low: print(f"   {r['refs']:<20} {r['mpn']:<24} {r['lcsc']:<10} {r['stock']}")
    print(f"\nwritten to {path}")

if __name__ == "__main__":
    main()
