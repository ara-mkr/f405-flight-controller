# -*- coding: utf-8 -*-
"""Routing pipeline around freerouting (KiCad python).

  python3.9 route_fr.py prep     placed board -> In1 GND plane + hole keep-outs -> fc_f405.dsn
  freerouting-cli -de fc_f405.dsn -do fc_f405.ses ...
  python3.9 route_fr.py import   fc_f405.ses -> tracks/vias -> GND pours on F/In2/B -> fill -> save

Stack-up (6 layers): F signal, In1 solid GND plane, In2 signal, In3 signal,
In4 solid +3V3 plane, B signal. Neither plane is ever routed. Freerouting sees In1 as a GND plane and drops a via
from every GND pad into it; everything else is routed on F, In2 and B.
"""
import sys, os, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pcbnew, layout, rules

HW  = os.path.dirname(HERE)
PCB = os.path.join(HW, "fc_f405.kicad_pcb")
DSN = os.path.join(HW, "fc_f405.dsn")
SES = os.path.join(HW, "fc_f405.ses")
MM = pcbnew.FromMM
def V(x, y): return pcbnew.VECTOR2I(MM(x), MM(y))

def board_poly(zone, inset=0.0):
    """Rounded-square board outline, as a polygon, inset by `inset` mm."""
    W, H, R = layout.W, layout.H, layout.CORNER_R
    o = zone.Outline(); o.NewOutline()
    pts = []
    for cx, cy, a0 in ((W-R, R, -90), (W-R, H-R, 0), (R, H-R, 90), (R, R, 180)):
        for k in range(10):
            a = math.radians(a0 + 90*k/9)
            pts.append((cx + (R-inset)*math.cos(a), cy + (R-inset)*math.sin(a)))
    for x, y in pts: o.Append(MM(x), MM(y))

def circle_poly(zone, cx, cy, r, n=32):
    o = zone.Outline(); o.NewOutline()
    for k in range(n):
        a = 2*math.pi*k/n
        o.Append(MM(cx + r*math.cos(a)), MM(cy + r*math.sin(a)))

def gnd_zone(b, layer, prio, name, net="GND"):
    z = pcbnew.ZONE(b)
    z.SetLayer(layer)
    z.SetNet(b.FindNet(net))
    z.SetZoneName(name)
    z.SetAssignedPriority(prio)
    z.SetLocalClearance(MM(0.2))
    z.SetMinThickness(MM(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    board_poly(z)
    b.Add(z)
    return z

def keepouts(b):
    cu = pcbnew.LSET.AllCuMask()
    for n, (hx, hy) in enumerate(layout.HOLE_XY):
        z = pcbnew.ZONE(b)
        z.SetIsRuleArea(True)
        z.SetLayerSet(cu)
        z.SetZoneName("hole%d_keepout" % (n + 1))
        z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True)
        z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
        z.SetDoNotAllowZoneFills(False)      # GND pour may ring the hole
        circle_poly(z, hx, hy, layout.HOLE_KEEPOUT_R)
        b.Add(z)

def prep():
    b = pcbnew.LoadBoard(PCB)
    if not any(z.GetZoneName() == "L2_GND_plane" for z in b.Zones()):   # idempotent
        gnd_zone(b, pcbnew.In1_Cu, 10, "L2_GND_plane")
        gnd_zone(b, pcbnew.In4_Cu, 10, "L5_3V3_plane", net="+3V3")
        keepouts(b)
    pcbnew.SaveBoard(PCB, b)
    rules.apply()
    b = pcbnew.LoadBoard(PCB)
    ok = pcbnew.ExportSpecctraDSN(b, DSN)
    print("DSN export:", ok, DSN)

def do_import():
    b = pcbnew.LoadBoard(PCB)
    ok = pcbnew.ImportSpecctraSES(b, SES)
    print("SES import:", ok)
    for lay, name in ((pcbnew.F_Cu, "F_GND"), (pcbnew.In2_Cu, "L3_GND"), (pcbnew.B_Cu, "B_GND")):
        gnd_zone(b, lay, 1, name)
    filler = pcbnew.ZONE_FILLER(b)
    filler.Fill(b.Zones())
    b.BuildConnectivity()
    print("unrouted:", b.GetConnectivity().GetUnconnectedCount(True))
    pcbnew.SaveBoard(PCB, b)
    rules.apply()

def import_only():
    """Tracks from the session onto the placed board, no pours - the input for
    a continuation run of freerouting."""
    b = pcbnew.LoadBoard(PCB)
    print("SES import:", pcbnew.ImportSpecctraSES(b, SES))
    pcbnew.SaveBoard(PCB, b)
    rules.apply()
    b = pcbnew.LoadBoard(PCB)
    print("DSN export:", pcbnew.ExportSpecctraDSN(b, DSN))

def pours():
    """GND pours on F / In2 / B (idempotent) and fill."""
    b = pcbnew.LoadBoard(PCB)
    have = {z.GetZoneName() for z in b.Zones()}
    for lay, name in ((pcbnew.F_Cu, "F_GND"), (pcbnew.In2_Cu, "L3_GND"),
                      (pcbnew.In3_Cu, "L4_GND"), (pcbnew.B_Cu, "B_GND")):
        if name not in have: gnd_zone(b, lay, 1, name)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.BuildConnectivity()
    print("unrouted:", b.GetConnectivity().GetUnconnectedCount(True))
    pcbnew.SaveBoard(PCB, b)
    rules.apply()

def fill():
    b = pcbnew.LoadBoard(PCB)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.BuildConnectivity()
    print("unrouted:", b.GetConnectivity().GetUnconnectedCount(True))
    pcbnew.SaveBoard(PCB, b)
    rules.apply()

if __name__ == "__main__":
    {"prep": prep, "import": do_import, "importonly": import_only, "pours": pours, "fill": fill}[sys.argv[1]]()
