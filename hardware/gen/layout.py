# -*- coding: utf-8 -*-
"""Hand floorplan for fc_f405 - every part placed deliberately.

Board 37 x 37 mm, origin top-left, y down. Mounting holes on the 30.5 mm
pattern at 3.25 mm from each edge, 3.5 mm keep-out radius around each.

TOP (F)    - the digital side: MCU, OSD, flash, baro, USB, every wire pad.
BOTTOM (B) - the power side: both TPS54360 bucks at opposite edges, the
             battery input + reverse-polarity FET + TVS + bulk cap between
             them, the 3.3 V LDO - and the gyro alone at the geometric centre,
             as far as the board allows from both switchers (DESIGN_PLAN 7.2).

Coordinates for bottom parts are board coordinates seen from the top.
"""
W = H = 37.0
CX = CY = 18.5
CORNER_R = 5.0
HOLE_XY = [(3.25, 3.25), (33.75, 3.25), (3.25, 33.75), (33.75, 33.75)]
HOLE_D = 4.0
HOLE_KEEPOUT_R = 3.5

PLACE = {}
def P(ref, x, y, rot=0, side='F'):
    assert ref not in PLACE, ref
    PLACE[ref] = (x, y, rot, side)
def B(ref, x, y, rot=0): P(ref, x, y, rot, 'B')

# ======================================================================= TOP
# --- MCU. Pin-row pad centres: W x=ux-5.7, E x=ux+5.7, N y=uy-5.7, S y=uy+5.7
ux, uy = 17.5, 19.3
P("U1", ux, uy, 0)
# VDD decoupling, each against its VDD/VSS pin pair
P("C21", ux - 3.73, uy - 7.25, 0)     # pins 63/64  (N)
P("C23", 18.62, 11.9, 0)           # 4.7 uF bulk (N)
P("R18", 16.18, 11.95, 0)         # BOOT0 pull-down, pad right above pin 60
P("C18", ux - 2.77, uy + 7.25, 180)     # pins 18/19  (S)
P("R19", ux + 1.5,  uy + 7.25, 0)     # BOOT1 pull-down, pin 28
P("C19", ux + 3.9,  uy + 7.25, 0)     # pin 32      (S)
P("C24", ux + 2.5,  uy + 8.55, 0)     # VCAP1, pin 31
P("C20", ux + 7.3,  uy - 4.0, 90)     # pin 48      (E)
P("C25", ux + 7.4,  uy - 1.6, 270)    # VCAP2, pin 47 - VCAP pad toward the pin
# 8 MHz crystal at OSC_IN/OUT (pins 5, 6), NRST cap (pin 7)
P("Y1",  8.6, 17.0, 180)
P("C28", 9.5, 14.6, 0); P("C29", 6.1, 17.8, 90)
P("C30", 9.9, 19.2, 180)
# ADC anti-alias RCs (pins 10, 11) and the VDDA ferrite + caps (pin 13)
P("C41", 9.9, 20.25, 180); P("R24", 6.4, 20.25, 0)
P("C42", 9.9, 21.3, 0);    P("R25", 6.4, 21.3, 0)    # GND pad faces VSSA (pin 12)
P("C26", 9.9, 22.35, 180); P("C44", 9.9, 23.4, 180); P("C27", 9.9, 24.45, 180)
P("FB1", 6.4, 23.45, 90)

# --- USB-C on the north edge; ESD array and CC pull-downs between it and the MCU
P("J5", 18.5, 4.0, 180)
P("U9", 22.1, 10.8, 0)
P("R20", 13.0, 9.9, 0); P("R21", 13.0, 11.0, 0)
P("D6", 24.6, 5.6, 270)          # VBUS Schottky beside the ESD array

# --- OSD column east of the MCU: SPI2 faces the MCU, the video pins face the
#     video pads on the east edge, so the 75 R / coupling network stays short
P("U4", 29.4, 14.4, 0)
P("Y2", 27.9, 7.5, 0)
P("C36", 25.08, 10.5, 90)                       # DVDD, pin 3
P("R30", 33.85, 10.55, 90); P("C37", 33.85, 12.5, 90)    # VTX 75 R | PVDD decap at pin 24
P("C45", 33.85, 14.45, 90); P("C38", 33.85, 16.4, 270)   # VIN coupling at pin 22 | AVDD decap
P("R32", 33.85, 18.35, 90)                                # RESET pull-up, pin 19
P("C46", 28.0, 20.5, 0); P("C47", 31.4, 20.5, 0); P("R29", 35.9, 16.45, 270)   # CAM 75 R right under J9's CAM pad; R
# --- blackbox flash under it
P("U5", 29.6, 26.0, 0)
P("C49", 30.3, 22.4, 0); P("C48", 32.3, 22.4, 0)
P("R16", 25.2, 20.8, 90); P("R17", 27.3, 22.4, 0)

# --- baro beside the MCU's I2C pins (61/62), beeper driver by its pads
P("U3", 8.4, 12.9, 0)
P("C34", 6.6, 13.0, 90); P("C35", 10.2, 12.9, 90)
P("R14", 4.45, 12.9, 90); P("R15", 5.53, 12.9, 90)
P("Q2", 5.2, 9.0, 0); P("R23", 5.2, 11.2, 0); P("D5", 8.6, 8.9, 90)

# --- 3.3 V LDO, south-west, +5V in from the In2 rail
P("U8", 11.4, 30.6, 180)
P("C17", 6.1, 28.4, 90)                         # 3V3 out, at the tab
P("C16", 16.75, 28.85, 90)                       # 5V in, at pin 3
# --- status LEDs
P("LED1", 19.3, 29.4, 0); P("R27", 22.6, 27.75, 0)
P("LED2", 22.45, 29.4, 0); P("R28", 24.45, 28.6, 90)

# --- wire pads around the edges
P("J12", 10.07, 1.5, 0)         # UART3 (VTX)       north, west of USB
P("J13", 26.93, 1.5, 0)         # UART5             north, east of USB
P("J7",  1.5, 8.35, 90)         # buzzer            west
P("J10", 1.5, 13.95, 90)        # UART1 (RX)        west
P("J11", 1.5, 21.35, 90)        # UART2 (GPS)       west
P("J8",  1.5, 27.8, 90)         # LED strip         west
P("J9",  35.5, 11.15, 90)       # video             east
P("J15", 35.5, 24.3, 90)        # cam ctrl / rssi   east
P("J6",  21.5, 33.5, 180)       # ESC JST-SH        south
P("J14", 10.07, 35.5, 0)        # UART6             south

# ==================================================================== BOTTOM
# --- gyro dead centre, its ferrite and caps hugging it
B("U2", 18.5, 18.5, 0)
B("C31", 16.0, 18.5, 90); B("C33", 21.0, 18.5, 90)
B("C32", 22.4, 18.5, 90);  B("C39", 18.5, 16.4, 0)
B("FB2", 18.5, 14.9, 0)
# SWD / boot / I2C pads, interior
B("J2", 27.0, 5.25, 0); P("J3", 28.7, 30.5, 0); B("J4", 18.5, 21.6, 0)   # BOOT pads on top (tweezers) | I2C pads
# VBAT sense divider at the bulk cap
B("R12", 14.35, 12.9, 90); B("R13", 14.35, 15.0, 90); B("C40", 14.35, 17.0, 90)
# TVS on VBAT
B("D3", 18.5, 11.6, 0)

# --- 9 V buck, east. U7 sits directly under the OSD (U4, top side) so the two
#     exposed pads overlap and share one thermal via array - the OSD's pin row
#     leaves no other room above U7 for vias. VIN faces north into C3, SW faces
#     south into D2 and L2; the compensation / feedback parts take the strip
#     between the buck and the gyro.
B("U7", 29.4, 13.15, 270)
B("C3", 29.0, 7.9, 0);  B("C4", 33.6, 13.82, 90)   # VBAT pad clears the +5V via beside C38 (top)
B("C11", 26.08, 13.15, 270)
B("R10", 33.6, 8.1, 0); B("R9", 33.6, 9.5, 180); B("R11", 33.6, 10.9, 0)
B("D2", 31.6, 20.05, 0)
B("L2", 32.0, 26.75, 0)
B("C8", 27.3, 31.75, 0); B("C9", 27.3, 34.85, 0)
B("R31", 23.8, 16.1, 90); B("C14", 23.8, 18.5, 90); B("C15", 23.8, 20.42, 90)
B("R8", 25.7, 22.8, 90); B("R7", 25.7, 25.65, 90)

# --- 5 V buck, west: the 9 V cluster rotated 180 deg about the board centre.
#     A rotation (not a mirror) keeps the TPS54360's pin chirality, so VIN still
#     faces its input cap and SW still runs straight through D1 into L1.
_ROT180 = {"U7": "U6", "C3": "C1", "C4": "C2", "C11": "C10", "R10": "R2",
           "R9": "R1", "R11": "R3", "D2": "D1", "L2": "L1", "C8": "C6",
           "C9": "C7", "R31": "R4", "C14": "C12", "C15": "C13", "R8": "R5",
           "R7": "R6"}
for _a, _b in _ROT180.items():
    _x, _y, _r, _s = PLACE[_a]
    B(_b, W - _x, H - _y, (_r + 180) % 360)

# --- battery input, south edge: pads -> P-FET -> bulk cap
B("J1", 18.5, 34.25, 0)
B("C43", 18.5, 27.4, 0)
B("Q1", 10.75, 32.45, 0); B("D4", 9.6, 35.4, 0); B("R22", 8.4, 32.4, 90)
