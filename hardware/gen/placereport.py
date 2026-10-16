import sys, math; sys.path.insert(0,'.')
import place, board, design, cluster
final, failed = place.solve()
parts={c["ref"]:c for c in design.COMPONENTS if c.get("fp")}
boxes={r:(place.box(x,y,parts[r]["fp"],rot,s),s) for r,(x,y,rot,s) in final.items()}

bad=[]; refs=sorted(boxes)
for i,a in enumerate(refs):
    (ax0,ay0,ax1,ay1),sa=boxes[a]
    if ax0<0.5 or ay0<0.5 or ax1>35.5 or ay1>35.5: bad.append(f"{a} breaks the 0.5 mm edge margin")
    for hx,hy in board.HOLE_XY:
        nx=max(ax0,min(hx,ax1)); ny=max(ay0,min(hy,ay1))
        if math.hypot(nx-hx,ny-hy)<board.HOLE_KEEPOUT_R: bad.append(f"{a} in mounting keep-out")
    for b in refs[i+1:]:
        (bx0,by0,bx1,by1),sb=boxes[b]
        if sa!=sb: continue
        if min(ax1,bx1)-max(ax0,bx0)>0.01 and min(ay1,by1)-max(ay0,by0)>0.01:
            bad.append(f"courtyard overlap {a}/{b}")
print("="*72); print(f"HARD CONSTRAINTS: {len(bad)} violation(s)"); print("="*72)
for b in bad[:20]: print("  *",b)

print("\n" + "="*72); print("SEC 7.2  GYRO ISOLATION"); print("="*72)
gx,gy,_,gs = final["U2"]
print(f"  gyro U2 at ({gx},{gy}) side {gs}  (board centre is 18,18)")
for r in ["L1","L2","U6","U7","D1","D2","Q1"]:
    x,y,_,s=final[r]
    print(f"    {r:<3} {parts[r]['val']:<14} ({x:5.1f},{y:5.1f}){s}  {math.hypot(x-gx,y-gy):5.2f} mm away")

print("\n" + "="*72); print("SEC 3.4  DECOUPLING ADJACENCY (part centre -> the pin pad it serves)"); print("="*72)
rows=[]
for r,anc in cluster.CLUSTER.items():
    if r not in final or anc not in final: continue
    x,y,_,s=final[r]; ax,ay,_,asd=final[anc]
    tx,ty = place.TARGET.get(r,(ax,ay))       # the actual pin pad it serves
    rows.append((math.hypot(x-tx,y-ty), r, parts[r]['val'], anc, s==asd))
rows.sort(reverse=True)
print(f"  worst 12 of {len(rows)}:")
for d,r,v,a,same in rows[:12]:
    print(f"    {r:<5} {v:<12} -> {a:<4} {d:5.2f} mm {'(same side)' if same else '(opposite side)'}")
print(f"  median distance to anchor: {sorted(x[0] for x in rows)[len(rows)//2]:.2f} mm")
