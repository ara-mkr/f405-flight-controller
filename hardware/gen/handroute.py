# -*- coding: utf-8 -*-
"""Hand pre-routes (KiCad python), laid BEFORE gnd_vias.py and freerouting.

The OSD's east column (U4 pins 19-26 -> C37 / C45 / C38 / R32 -> J9 / R29) is
the tightest spot on the board. Its +5V links only fit as 0.2-0.3 mm branches,
narrower than the PWR class freerouting routes at, and the one via site beside
C38 exists only with C4 (bottom, under the column) nudged north. So the whole
+5V cluster there is laid by hand and locked; gnd_vias.py places its plane vias
around it and freerouting routes OSD_SAG / OSD_VOUT / CAM_IN around it.

  U4.24 -> C37 -> J9.2        PVDD decap, video-pad supply (0.3 / 0.6 mm)
  U4.21 -> C38 -> via -> In3  AVDD decap, between the pin tips and the C45 column
  R32.1 -> via -> In3        OSD RESET pull-up, In3 round C38's GND via
  via on the C37-J9.2 run -> In3 -> C38's via: one cluster, which freerouting
                              then joins to the +5V rail on an inner layer
Coordinates are pad-derived (mm). Checked by KiCad DRC at the end of the run.
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pcbnew, rules
PCB = os.path.join(os.path.dirname(HERE), "fc_f405.kicad_pcb")
MM = pcbnew.FromMM

def pad(b, ref, num):
    for fp in b.Footprints():
        if fp.GetReference() == ref:
            for p in fp.Pads():
                if p.GetNumber() == num:
                    c = p.GetPosition(); return pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)
    raise KeyError("%s.%s" % (ref, num))

def path(b, net, pts, w, layer=pcbnew.F_Cu):
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(MM(x1), MM(y1))); t.SetEnd(pcbnew.VECTOR2I(MM(x2), MM(y2)))
        t.SetWidth(MM(w)); t.SetLayer(layer); t.SetNet(b.FindNet(net)); t.SetLocked(True)
        b.Add(t)

def via(b, net, xy, d=0.45, dr=0.2):
    v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(MM(xy[0]), MM(xy[1])))
    v.SetWidth(MM(d)); v.SetDrill(MM(dr)); v.SetNet(b.FindNet(net)); v.SetLocked(True)
    b.Add(v)

def main():
    b = pcbnew.LoadBoard(PCB)
    if any(t.GetNetname() == "+5V" for t in b.GetTracks()):
        print("hand routes already present"); return          # idempotent
    tip = 0.775 + 0.2505            # pin centre -> clear of the pin tips, 0.2 mm trace
    # PVDD: pin 24 -> C37 -> J9.2
    x24, y24 = pad(b, "U4", "24"); c37 = pad(b, "C37", "1"); j92 = pad(b, "J9", "2")
    path(b, "+5V", [(x24, y24), (x24 + 0.95, y24), c37], 0.3)
    path(b, "+5V", [c37, j92], 0.6)
    va = (c37[0] + 0.72, y24 + 0.725)                      # between C4's pads (bottom)
    path(b, "+5V", [(va[0], c37[1]), va], 0.3); via(b, "+5V", va)
    # AVDD: pin 21 -> C38 in front of the pin tips, then C38 -> via
    x21, y21 = pad(b, "U4", "21"); c38 = pad(b, "C38", "1"); xs = x21 + tip
    path(b, "+5V", [(x21 + 0.6, y21), (xs, y21), (xs, c38[1]), c38], 0.2)
    vc = (c38[0] + 0.83, c38[1] + 0.4)
    path(b, "+5V", [c38, (vc[0], c38[1]), vc], 0.25); via(b, "+5V", vc)
    path(b, "+5V", [va, vc], 0.3, pcbnew.In3_Cu)
    # C38's GND pad is boxed in by the +5V around it: its plane via goes here, by hand
    g38p = pad(b, "C38", "2"); g38 = (vc[0] - 0.06, vc[1] + 0.73)
    path(b, "GND", [g38p, g38], 0.3); via(b, "GND", g38, 0.5)
    # RESET pull-up: R32.1 -> own via, then In3 round C38's GND via to C38's +5V via
    r32 = pad(b, "R32", "1"); vr = (vc[0], vc[1] + 1.53)
    path(b, "+5V", [r32, (vr[0], r32[1]), vr], 0.25); via(b, "+5V", vr)
    path(b, "+5V", [vr, (vc[0] + 0.52, vr[1] - 0.52), (vc[0] + 0.52, vc[1] + 0.28), vc], 0.3, pcbnew.In3_Cu)
    pcbnew.SaveBoard(PCB, b); rules.apply()
    print("hand pre-routes added: OSD +5V cluster")

if __name__ == "__main__":
    main()
