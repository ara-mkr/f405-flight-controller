"""Placement sanity: every part placed, inside the board, clear of the mounting-hole
keep-outs, and no courtyard overlaps between parts on the same side."""
import sys, os, re, math
sys.path.insert(0,'.')
import design, board
STOCK="/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
PROJ="/Users/akhilraja-amudhan/Documents/Flight Controller Project/hardware/lib/fc_f405.pretty"

_cy={}
def courtyard(fpid):
    if fpid in _cy: return _cy[fpid]
    lib,name=fpid.split(":",1)
    p=os.path.join(PROJ,name+".kicad_mod") if lib=="fc_f405" else os.path.join(STOCK,lib+".pretty",name+".kicad_mod")
    t=open(p).read(); xs=[];ys=[]
    for m in re.finditer(r'\(fp_(?:line|rect|poly|circle|arc)\b(.*?)\n\t*\)', t, re.S):
        b=m.group(1)
        if 'CrtYd' not in b: continue
        for x,y in re.findall(r'\((?:start|end|center|mid|xy) (-?[\d.]+) (-?[\d.]+)\)', b):
            xs.append(float(x)); ys.append(float(y))
    if not xs:   # fall back to pad extents + 0.25 mm
        for x,y,w,h in re.findall(r'\(at (-?[\d.]+) (-?[\d.]+)[^)]*\)\s*\n?\s*\(size ([\d.]+) ([\d.]+)\)', t):
            xs += [float(x)-float(w)/2-0.25, float(x)+float(w)/2+0.25]
            ys += [float(y)-float(h)/2-0.25, float(y)+float(h)/2+0.25]
    r=(min(xs),min(ys),max(xs),max(ys)); _cy[fpid]=r; return r

def bbox(ref, fpid):
    x,y,rot,side = board.PLACE[ref]
    x0,y0,x1,y1 = courtyard(fpid)
    if rot % 180 == 90: x0,y0,x1,y1 = y0,x0,y1,x1  # swap extents
    if rot % 180 == 90:
        w,h = (y1-y0), (x1-x0)
    else:
        w,h = (x1-x0), (y1-y0)
    return (x-w/2, y-h/2, x+w/2, y+h/2), side

errs=[]
parts=[c for c in design.COMPONENTS if c.get("fp")]
missing=[c["ref"] for c in parts if c["ref"] not in board.PLACE]
if missing: errs.append("NOT PLACED: " + ", ".join(sorted(missing)))

boxes={}
for c in parts:
    if c["ref"] not in board.PLACE: continue
    bb, side = bbox(c["ref"], c["fp"]); boxes[c["ref"]]=(bb, side, c["val"])
    x0,y0,x1,y1 = bb
    if x0 < 0.5 or y0 < 0.5 or x1 > board.W-0.5 or y1 > board.H-0.5:
        errs.append(f"{c['ref']} [{c['val']}] outside the 0.5 mm edge margin: "
                    f"({x0:.1f},{y0:.1f})-({x1:.1f},{y1:.1f})")
    for hx,hy in board.HOLE_XY:
        nx=max(x0,min(hx,x1)); ny=max(y0,min(hy,y1))
        d=math.hypot(nx-hx, ny-hy)
        if d < board.HOLE_KEEPOUT_R:
            errs.append(f"{c['ref']} [{c['val']}] intrudes into the mounting-hole "
                        f"keep-out at ({hx},{hy}): {d:.2f} < {board.HOLE_KEEPOUT_R}")
refs=sorted(boxes)
for i,a in enumerate(refs):
    (ax0,ay0,ax1,ay1),sa,va = boxes[a]
    for b in refs[i+1:]:
        (bx0,by0,bx1,by1),sb,vb = boxes[b]
        if sa!=sb: continue
        ox = min(ax1,bx1)-max(ax0,bx0); oy = min(ay1,by1)-max(ay0,by0)
        if ox > 0.01 and oy > 0.01:
            errs.append(f"courtyard overlap ({sa}): {a} [{va}] vs {b} [{vb}]  "
                        f"{ox:.2f} x {oy:.2f} mm")
print("="*74)
print(f"placement check: {len(boxes)} parts placed, {len(errs)} problem(s)")
print("="*74)
for e in errs[:40]: print("  *", e)
if len(errs)>40: print(f"  ... and {len(errs)-40} more")
