"""Fill the copper pours using KiCad's own engine, then save.

Run with KiCad's bundled interpreter:
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3.9
The MCP's board cache clobbers externally-generated files, so this is the only
writer that touches the board after mkpcb.py.
"""
import sys, pcbnew

PCB = "/Users/akhilraja-amudhan/Documents/Flight Controller Project/hardware/fc_f405.kicad_pcb"

def main():
    b = pcbnew.LoadBoard(PCB)
    zones = list(b.Zones())
    print("zones:", len(zones))
    filler = pcbnew.ZONE_FILLER(b)
    ok = filler.Fill(b.Zones())
    print("fill returned:", ok)
    b.BuildConnectivity()
    conn = b.GetConnectivity()
    print("unconnected (ratsnest):", conn.GetUnconnectedCount(True))
    pcbnew.SaveBoard(PCB, b)
    print("saved")

if __name__ == "__main__":
    main()
