# -*- coding: utf-8 -*-
"""Floorplan for the 36 x 36 mm board.

Rules being satisfied (DESIGN_PLAN sec 7):
  7.2  gyro at the geometric centre, maximum distance from both switchers,
       solid GND under it, no L3 power pour and no motor traces beneath
  7.3  each buck's CIN -> VIN -> SW -> L -> D loop kept tight; both regulators
       at the edge opposite the gyro and separated from each other
  7.4  4 x M3 on a 30.5 mm pattern, 1.5 mm keep-out, components 0.5 mm inside
       the edge. Corner radius 4.0 mm, not the 5.0 mm the plan specified -
       5.0 mm cuts 0.18 mm into the mounting holes (approved deviation).
Coordinates are millimetres, board spans 0..37 in both axes, centre (18.5,18.5).

Connector edge budget. The four M3 keep-outs (3.5 mm radius on the fixed 30.5 mm
pattern) leave exactly 23.5 mm of usable perimeter on each edge, and that figure
does not change when the board grows because the hole pattern is fixed. J5 is
through-hole so it consumes its 10.70 mm on BOTH sides. Allocation:

  bottom  F: J5 USB-C 9.94             B: J6 11.10              (11.10 / 23.5)
  left    F: J7 3.10 + J8 4.90          B: J10 6.70              ( 6.70 / 23.5)
  right   F: J4 6.70 + J15 8.50         B: J9 10.30 + J13 6.70   (17.00 / 23.5)
  top     F: J1 11.50                   B: J12 + J11 + J14 20.10 (20.10 / 23.5)

Two things forced this away from the original all-round arrangement:

  * J5 and J6 both sat at bottom centre. J5 is through-hole, so its body split
    the 23.5 mm span into two 6.4 mm gaps and J6 fitted in neither - on a board
    of any size, because the hole pattern is fixed. They are end-to-end now.
  * the left edge is the only corridor wide enough for U4 and its escape halo,
    so only one pad group (J10) may sit there; J11 and J12 moved to the bottom
    and top edges, which had the slack.
"""
W = H = 37.0
CX = CY = 18.5
CORNER_R = 5.0                       # restored to the plan's original spec: at
                                      # 37x37 the 30.5mm hole pattern (3.25mm
                                      # from each edge) clears a 5mm radius with
                                      # margin, so the 36x36/R4.0 deviation is
                                      # no longer needed.
HOLE_XY  = [(3.25, 3.25), (33.75, 3.25), (3.25, 33.75), (33.75, 33.75)]
HOLE_D   = 4.0
HOLE_KEEPOUT_R = HOLE_D / 2 + 1.5    # 3.5 mm

# J2 (SWD) and J3 (BOOT) are made up once at build or recovery time, not wired
# to anything that leaves the board, so they do not need perimeter access. Left
# on the top edge they denied the 100 uF VBAT bulk the only 9 mm strip that fits
# between the MCU escape ring and the edge connectors.
INTERIOR_PADS = {"J2", "J3"}

# ref -> (x, y, rotation, side)   side 'F' = top, 'B' = bottom
PLACE = {}
def P(ref, x, y, rot=0, side='F'): PLACE[ref] = (x, y, rot, side)

# ============================================================ TOP SIDE
# --- centre: gyro dead centre, its ferrite and bypasses hard against it
P("U2",  18.5, 18.5,  0,'F'); P("FB2", 19, 22,  0,'F')
P("C31", 15.1, 18.5, 90,'F'); P("C32", 21.9, 18.5, 90,'F')
P("C33", 15.1, 20.9, 90,'F'); P("C39", 21.9, 20.9, 90,'F')

# --- 5 V buck, top-left. C2 sits against VIN (pin 2, left edge of U6);
#     D1 spans SW(8)->GND(7) immediately below; L1 takes SW onward.
P("C2", 3.4, 28.5, 90,'F'); P("U6", 9.5, 28.5,  0,'F')
P("C1", 9.5, 33.6,  0,'F'); P("D1", 9.5, 22.2,  0,'F')
P("L1", 7.5, 15.0,  0,'F')

# --- 9 V buck, top-right, mirrored about x = 18
P("C4", 33.6, 28.5, 90,'F'); P("U7", 27.5, 28.5,  0,'F')
P("C3", 27.5, 33.6,  0,'F'); P("D2", 27.5, 22.2,  0,'F')
P("L2", 29.5, 15.0,  0,'F')

# --- battery entry, top centre (between the two buck clusters)
P("J1", 18.5, 33.5,  0,'F'); P("Q1", 18.5, 28.1,  0,'F')
P("D3", 18.5, 23.9,  0,'F')

# --- 3.3 V LDO and USB, bottom half
P("U8", 18.5, 12.5,  0,'F'); P("D6", 14.0, 8.0, 90,'F')
P("J5",  12.1,  5.4,  0,'F'); P("U9", 24.5, 9.5,  0,'F')
P("U3", 24.0, 5.5,  0,'F')

# --- edge pads on the top side (see the edge budget note below)
P("J4", 35.3, 12.0, 90,'F'); P("J8", 1.7, 15.0, 90,'F')
P("J7", 1.7,  9.0, 90,'F');  P("J15", 35.3, 23.0, 90,'F')

# ============================================================ BOTTOM SIDE
P("U1",  18.5, 18.5,  0,'B')          # MCU directly under the gyro
P("C43", 14.0, 30.9,  0,'B')          # 100 uF bulk, near the battery pads
P("J6", 24.3, 3.9,  0,'B')          # ESC connector, right of the USB
P("U4", 6.0, 20.5,  0,'B')          # OSD
P("U5", 31.0, 20.5,  0,'B')          # blackbox flash
P("Y1", 29.5, 29.5,  0,'B')          # 8 MHz, near the MCU
P("Y2", 5.5, 29.0,  0,'B')          # 27 MHz, near the OSD
P("D4", 21.0, 25.5, 90,'F'); P("R22", 22.5, 27.5, 90,'B')
P("J2", 10.0, 12.5,  0,'B'); P("J3", 24.0, 30.5,  0,'B')
P("J9", 35.3, 12.0, 90,'B')
P("J10", 1.7,  9.0, 90,'B'); P("J11", 17.5, 35.3,  0,'B')
P("J12", 10.0, 35.3,  0,'B')
P("J13", 35.3, 24.0, 90,'B'); P("J14", 25.0, 35.3,  0,'B')
P("LED1", 13.5, 12.5,  0,'B'); P("LED2", 23.5, 12.5, 0,'B')
P("Q2", 16.5, 12.5,  0,'B'); P("J8x", 0.5, 0.5,0,'B')
del PLACE["J8x"]

# hints for everything else - the placer moves these to the nearest legal spot
# around their cluster anchor, so the exact value here only breaks ties
for _r, _xy in {
  "C6":(5.8,13.5),"C7":(10,13.5),"C8":(31.2,13.5),"C9":(27,13.5),
  "C10":(13.5,30),"C12":(13.5,27.5),"C13":(13.5,25.3),
  "C11":(23.5,30),"C14":(23.5,27.5),"C15":(23.5,25.3),
  "R1":(6.5,31.5),"R2":(6.5,29.5),"R3":(6.5,25.5),"R4":(13,31.5),
  "R5":(13,29.5),"R6":(13,25.5),
  "R9":(30.5,31.5),"R10":(30.5,29.5),"R11":(30.5,25.5),"R7":(24,31.5),
  "R8":(24,29.5),"R31":(24,25.5),
  "C16":(14,11),"C17":(7,11),
  "C34":(31,14),"C35":(28,11),"R14":(31,16.5),"R15":(28,16.5),
  "C18":(13.5,15.5),"C19":(23.5,15.5),"C20":(13.5,21.5),"C21":(23.5,21.5),
  "C23":(18.5,15),"C24":(16.5,16),"C25":(20.5,16),
  "FB1":(18.5,24.5),"C26":(16,24.5),"C27":(21,24.5),"C44":(18.5,23),
  "C30":(11.5,24.5),"R18":(11.5,16.5),"R19":(11.5,18.5),
  "C28":(29,24),"C29":(29,30),
  "C36":(4.5,14.8),"C37":(7.5,14.8),"C38":(10.5,14.8),"R32":(4.5,12.9),
  "C45":(7.5,12.9),"C46":(10.5,12.9),"C47":(13.5,12.9),
  "R29":(13.5,14.8),"R30":(16.5,12.9),
  "C48":(30.5,17),"C49":(30.5,24),"R16":(33.5,20.5),"R17":(27,24),
  "R20":(14.5,8.5),"R21":(22.5,8.5),
  "R12":(21.5,31.5),"R13":(15.5,31.5),"C40":(18.5,26),
  "R24":(14.5,6),"R25":(24.5,4.5),"C41":(12.5,6),"C42":(26.5,4.5),
  "R27":(13.5,10.5),"R28":(23.5,10.5),"R23":(19.5,12.5),"D5":(16.5,14.5),
}.items():
    P(_r, _xy[0], _xy[1], 0, 'B' if _r in (
      "C10","C12","C13","C11","C14","C15","R1","R2","R3","R4","R5","R6",
      "R9","R10","R11","R7","R8","R31","C18","C19","C20","C21","C23","C24",
      "C25","FB1","C26","C27","C44","C30","R18","R19","C28","C29","C36",
      "C37","C38","R32","C45","C46","C47","R29","R30","C48","C49","R16",
      "R17","R12","R13","C40","R24","R25","R23","D5","C41","C42") else 'F')
