# -*- coding: utf-8 -*-
"""Put the net classes and stack-up roles into fc_f405.dsn for freerouting.

pcbnew's standalone loader does not apply the project's net-class patterns, so
its DSN puts every net in one 0.2 mm class. This rewrites:
  * In1 (GND) and In4 (+3V3) as power layers - freerouting never routes on them,
    only drops plane vias into them
  * via padstacks: 0.5/0.2 mm signal, 0.6/0.3 mm power
  * one class per net class in fc_f405.kicad_pro with its width and clearance
"""
import re, sys, os
HW  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DSN = os.path.join(HW, "fc_f405.dsn")

CLASSES = {   # name: (width um, clearance um, via, nets)
    "HV":     (600,  200, "Via[0-5]_600:300_um", ["VBAT", "VBAT_IN", "SW_5V", "SW_9V"]),
    "PWR":    (600,  150, "Via[0-5]_600:300_um", ["+5V", "+9V", "USB_VBUS"]),
    "PWR3V3": (300,  130, "Via[0-5]_450:200_um", ["+3V3", "+3V3_GYRO", "VDDA"]),
    "GND":    (400,  130, "Via[0-5]_450:200_um", ["GND"]),
}
VIAS = {"Via[0-5]_450:200_um": (450, 200), "Via[0-5]_500:200_um": (500, 200), "Via[0-5]_600:300_um": (600, 300)}

t = open(DSN).read()
for L in ("In1.Cu", "In4.Cu"):          # GND plane, +3V3 plane
    t = t.replace('(layer %s\n      (type signal)' % L, '(layer %s\n      (type power)' % L)
layers = ["F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu"]
def padstack(name, d):
    return ('    (padstack "%s"\n' % name + "".join(
        "      (shape (circle %s %d))\n" % (L, d) for L in layers) + "      (attach off)\n    )\n")
# drop every via padstack KiCad wrote, then insert exactly ours
ms = list(re.finditer(r'    \(padstack "Via\[0-\d\]_[0-9:]*_um"\n.*?\n    \)\n', t, re.S))
first = ms[0].start()
for m in reversed(ms):
    t = t[:m.start()] + t[m.end():]
t = t[:first] + "".join(padstack(k, v[0]) for k, v in VIAS.items()) + t[first:]
t = re.sub(r'\n    \(via "Via[^\n]*\)\n    \(rule', '\n    (via "Via[0-5]_450:200_um" "Via[0-5]_600:300_um")\n    (rule', t, count=1)
t = re.sub(r'\(rule\n      \(width 200\)\n      \(clearance 200\)',
           '(rule\n      (width 127)\n      (clearance 130)', t, count=1)

m = re.search(r'    \(class kicad_default (.*?)\n      \(circuit', t, re.S)
allnets = m.group(1).split()
special = {n for c in CLASSES.values() for n in c[3]}
def cls(name, nets, w, c, via):
    return ("    (class %s %s\n      (circuit\n        (use_via \"%s\")\n      )\n"
            "      (rule\n        (width %d)\n        (clearance %d)\n      )\n    )\n"
            % (name, " ".join(nets), via, w, c))
blocks = cls("kicad_default", [n for n in allnets if n not in special], 127, 130, "Via[0-5]_450:200_um")
for name, (w, c, via, nets) in CLASSES.items():
    blocks += cls(name, nets, w, c, via)
end = t.index("\n    )\n", m.end()) + len("\n    )\n")
t = t[:m.start()] + blocks + t[end:]
open(DSN, "w").write(t)
print("patched", DSN)
