# -*- coding: utf-8 -*-
"""Write the physical 6-layer stack-up into fc_f405.kicad_pcb (plain python).

1.6 mm, outer 1 oz / inner 0.5 oz, ENIG (flat pads for the LGA gyro and baro -
HASL leaves them domed), matte black solder mask, white legend. KiCad's 3D
viewer and `kicad-cli pcb render` take their colours from this block.

  L1 F.Cu   signal + parts          L4 In3.Cu signal
  L2 In1.Cu solid GND               L5 In4.Cu solid +3V3
  L3 In2.Cu signal                  L6 B.Cu   signal + parts
"""
import os, re
PCB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fc_f405.kicad_pcb")

def layer(name, typ, **kw):
    s = '\t\t\t(layer "%s"\n\t\t\t\t(type "%s")\n' % (name, typ)
    for k, v in kw.items():
        s += '\t\t\t\t(%s %s)\n' % (k, '"%s"' % v if isinstance(v, str) else v)
    return s + '\t\t\t)\n'

def stackup():
    d = lambda n, t, th: layer(n, t, thickness=th, material="FR4", epsilon_r=4.4, loss_tangent=0.02)
    s = "\t\t(stackup\n"
    s += layer("F.SilkS", "Top Silk Screen", color="White")
    s += layer("F.Paste", "Top Solder Paste")
    s += layer("F.Mask", "Top Solder Mask", color="Black", thickness=0.01)
    s += layer("F.Cu", "copper", thickness=0.035)
    s += d("dielectric 1", "prepreg", 0.2)
    s += layer("In1.Cu", "copper", thickness=0.0175)
    s += d("dielectric 2", "core", 0.2)
    s += layer("In2.Cu", "copper", thickness=0.0175)
    s += d("dielectric 3", "prepreg", 0.65)
    s += layer("In3.Cu", "copper", thickness=0.0175)
    s += d("dielectric 4", "core", 0.2)
    s += layer("In4.Cu", "copper", thickness=0.0175)
    s += d("dielectric 5", "prepreg", 0.2)
    s += layer("B.Cu", "copper", thickness=0.035)
    s += layer("B.Mask", "Bottom Solder Mask", color="Black", thickness=0.01)
    s += layer("B.Paste", "Bottom Solder Paste")
    s += layer("B.SilkS", "Bottom Silk Screen", color="White")
    s += '\t\t\t(copper_finish "ENIG")\n\t\t\t(dielectric_constraints no)\n\t\t)\n'
    return s

# KiCad 10 ships no 3D body for the HRO TYPE-C-31-M-12; renders borrow the GCT
# USB4105 (same 16-pin top-mount receptacle), shifted 0.365 mm so its pad row
# lands on the HRO one. Cosmetic only - pads and courtyard stay HRO.
USB_HRO = 'USB_C_Receptacle_HRO_TYPE-C-31-M-12.step"\n\t\t\t(offset\n\t\t\t\t(xyz 0 0 0)'
USB_GCT = 'USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal.step"\n\t\t\t(offset\n\t\t\t\t(xyz 0 0.365 0)'

def main():
    t = open(PCB).read()
    t = re.sub(r"\t\t\(stackup\n.*?\n\t\t\)\n", "", t, flags=re.S)       # idempotent
    i = t.index("\t(setup\n") + len("\t(setup\n")
    t = (t[:i] + stackup() + t[i:]).replace(USB_HRO, USB_GCT)
    open(PCB, "w").write(t)
    print("stack-up written: 6 layers, 1.6 mm, ENIG, matte black / white")

if __name__ == "__main__":
    main()
