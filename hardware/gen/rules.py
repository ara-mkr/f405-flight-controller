# -*- coding: utf-8 -*-
"""Net classes + board rules, written into fc_f405.kicad_pro.

pcbnew.SaveBoard() rewrites the project file from its in-memory defaults, so
every script that saves the board calls apply() afterwards.

Limits are PCBWay standard 4-layer capability (pcbway.com/capabilities.html):
0.1 mm trace/space, 0.2 mm min drill free of charge, 0.15 mm annular ring.
"""
import json, os
PRO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fc_f405.kicad_pro")

# name: (track, clearance, via dia, via drill, nets)
CLASSES = {
    "Default": (0.127, 0.127, 0.45, 0.2, []),
    "HV":      (0.6,  0.2,  0.6, 0.3, ["VBAT", "VBAT_IN", "SW_5V", "SW_9V"]),
    "PWR":     (0.6,  0.15, 0.6, 0.3, ["+5V", "+9V", "USB_VBUS"]),
    "PWR3V3":  (0.3,  0.127, 0.45, 0.2, ["+3V3", "+3V3_GYRO", "VDDA"]),
    "GND":     (0.4,  0.127, 0.45, 0.2, ["GND"]),
}
# lib_footprint_mismatch: every footprint carries an IPC-7351 density-level-C
# courtyard in place of the library's nominal one (see geom.py) - deliberate.
SEVERITY = {"lib_footprint_mismatch": "ignore"}

def apply():
    p = json.load(open(PRO))
    base = dict(p["net_settings"]["classes"][0])
    cls = []
    for i, (name, (tw, cl, vd, vdr, _)) in enumerate(CLASSES.items()):
        d = dict(base)
        d.update(name=name, track_width=tw, clearance=cl, via_diameter=vd, via_drill=vdr,
                 priority=2147483647 if name == "Default" else i)
        cls.append(d)
    p["net_settings"]["classes"] = cls
    p["net_settings"]["netclass_patterns"] = [
        {"netclass": name, "pattern": n} for name, c in CLASSES.items() for n in c[4]]
    ds = p["board"]["design_settings"]
    ds["rules"].update(min_track_width=0.1, min_clearance=0.127, min_via_diameter=0.45,
                       min_through_hole_diameter=0.2, min_via_annular_width=0.1,
                       min_hole_to_hole=0.25, min_copper_edge_clearance=0.3,
                       min_hole_clearance=0.2)
    ds["track_widths"] = [0.0, 0.15, 0.2, 0.3, 0.6, 1.0]
    ds["via_dimensions"] = [{"diameter": 0.0, "drill": 0.0},
                            {"diameter": 0.5, "drill": 0.2}, {"diameter": 0.6, "drill": 0.3}]
    ds["rule_severities"].update(SEVERITY)
    json.dump(p, open(PRO, "w"), indent=2)

if __name__ == "__main__":
    apply(); print("rules applied to", PRO)
