"""Author the three symbols KiCad does not ship. Pin data transcribed from datasheets
   read in Phase 3 Step 1 - see comments for the exact source."""

import os

HDR = '(kicad_symbol_lib (version 20251024) (generator "fc_f405_gen")\n'

def pin(num, name, x, y, ang, etype="passive", ln=2.54, shape="line"):
    return (f'      (pin {etype} {shape} (at {round(x,4):g} {round(y,4):g} {ang:g}) (length {ln})\n'
            f'        (name "{name}" (effects (font (size 1.27 1.27))))\n'
            f'        (number "{num}" (effects (font (size 1.27 1.27))))\n'
            f'      )\n')

def sym(name, ref, value, fp, ds, desc, kw, w, h, pins_):
    s  = f'  (symbol "{name}" (pin_names (offset 0.508)) (in_bom yes) (on_board yes)\n'
    s += f'    (property "Reference" "{ref}" (at 0 {h/2+2.54:g} 0) (effects (font (size 1.27 1.27))))\n'
    s += f'    (property "Value" "{value}" (at 0 {-(h/2+2.54):g} 0) (effects (font (size 1.27 1.27))))\n'
    s += f'    (property "Footprint" "{fp}" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))\n'
    s += f'    (property "Datasheet" "{ds}" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))\n'
    s += f'    (property "Description" "{desc}" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))\n'
    s += f'    (property "ki_keywords" "{kw}" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))\n'
    s += f'    (symbol "{name}_0_1"\n'
    s += (f'      (rectangle (start {-w/2:g} {h/2:g}) (end {w/2:g} {-h/2:g})\n'
          f'        (stroke (width 0.254) (type default)) (fill (type background)))\n    )\n')
    s += f'    (symbol "{name}_1_1"\n' + "".join(pins_) + '    )\n  )\n'
    return s

out = [HDR]

# ---------------------------------------------------------------- ICM-42688-P
# TDK DS-000347 Rev 1.2, Table 9 "Signal Descriptions" (p.18) + Fig 4 pin-out (p.19)
W, H = 25.4, 30.48
p = []
for num, nm, y in [("12","AP_CS",10.16),("13","AP_SCLK",7.62),("14","AP_SDI",5.08),
                   ("1","AP_SDO",2.54),("4","INT1",-2.54),("9","INT2/FSYNC/CLKIN",-5.08)]:
    et = {"12":"input","13":"input","14":"input","1":"output","4":"output","9":"input"}[num]
    p.append(pin(num, nm, -(W/2+2.54), y, 0, et))
for num, y in [("2",10.16),("3",7.62),("7",5.08),("10",2.54),("11",0)]:
    p.append(pin(num, "RESV", W/2+2.54, y, 180, "passive"))
p.append(pin("8",  "VDD",   -2.54, H/2+2.54, 270, "power_in"))
p.append(pin("5",  "VDDIO",  2.54, H/2+2.54, 270, "power_in"))
p.append(pin("6",  "GND",    0,   -(H/2+2.54), 90, "power_in"))
out.append(sym("ICM-42688-P","U","ICM-42688-P",
    "fc_f405:TDK_LGA-14_2.5x3.0mm",
    "https://invensense.tdk.com/download-pdf/icm-42688-p-datasheet/",
    "6-axis MEMS gyro+accel, SPI/I2C/I3C, LGA-14 2.5x3.0mm. VDD/VDDIO 1.71-3.6V, SPI to 24MHz",
    "IMU gyroscope accelerometer SPI", W, H, p))

# -------------------------------------------------------------------- BMP388
# Bosch BST-BMP388-DS001-07 Rev 1.7, Table 50 "Pin description" (p.47)
W, H = 20.32, 20.32
p = []
for num, nm, y, et in [("2","SCK",5.08,"input"),("4","SDI",2.54,"bidirectional"),
                       ("5","SDO",0,"bidirectional"),("6","CSB",-2.54,"input"),
                       ("7","INT",-5.08,"output")]:
    p.append(pin(num, nm, -(W/2+2.54), y, 0, et))
p.append(pin("1",  "VDDIO", -2.54, H/2+2.54, 270, "power_in"))
p.append(pin("10", "VDD",    2.54, H/2+2.54, 270, "power_in"))
for num, x in [("3",-2.54),("8",0),("9",2.54)]:
    p.append(pin(num, "VSS", x, -(H/2+2.54), 90, "power_in" if num=="3" else "passive"))
out.append(sym("BMP388","U","BMP388",
    "fc_f405:Bosch_LGA-10_2.0x2.0mm",
    "https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmp388-ds001.pdf",
    "Barometric pressure sensor, I2C/SPI, LGA-10 2.0x2.0mm. VDD 1.65-3.6V, abs max 3.8V",
    "barometer pressure altimeter I2C", W, H, p))

# ------------------------------------------------------------------- AT7456E
# Hangzhou Zhongke AT7456E-S402-V1.1: pin table p.6 + Fig 2 typical operating circuit p.5
W, H = 30.48, 45.72
p = []
left = [("5","CLKIN",17.78,"input"),("6","XFB",15.24,"passive"),("7","CLKOUT",12.7,"output"),
        ("8","~{CS}",7.62,"input"),("9","SDIN",5.08,"input"),("10","SCLK",2.54,"input"),
        ("11","SDOUT",0,"tri_state"),("19","~{RESET}",-5.08,"input"),
        ("13","SYNC_IN",-7.62,"input"),("12","LOS",-12.7,"open_collector"),
        ("18","~{HSYNC}",-15.24,"open_collector"),("17","~{VSYNC}",-17.78,"open_collector")]
for num, nm, y, et in left:
    p.append(pin(num, nm, -(W/2+2.54), y, 0, et))
for num, nm, y, et in [("22","VIN",10.16,"input"),("26","VOUT",-2.54,"output"),
                       ("25","SAG",-5.08,"passive")]:
    p.append(pin(num, nm, W/2+2.54, y, 180, et))
for num, nm, x in [("3","DVDD",-7.62),("21","AVDD",0),("24","PVDD",7.62)]:
    p.append(pin(num, nm, x, H/2+2.54, 270, "power_in"))
for num, nm, x in [("4","DGND",-10.16),("20","AGND",-2.54),("23","PGND",5.08),("29","EP",12.7)]:
    p.append(pin(num, nm, x, -(H/2+2.54), 90, "power_in"))
for i, num in enumerate(["1","2","14","15","16","27","28"]):
    p.append(pin(num, "NC", W/2+2.54, -12.7-2.54*i, 180, "no_connect"))
out.append(sym("AT7456E","U","AT7456E",
    "fc_f405:HTSSOP-28-1EP_4.4x9.7mm_P0.65mm",
    "https://www.lcsc.com/datasheet/C82351.pdf",
    "Monochrome OSD character generator with EEPROM, MAX7456-compatible, HTSSOP-28-EP. "
    "AVDD/DVDD/PVDD 3.15-5.25V, 27MHz xtal, SPI to 10MHz",
    "OSD video character generator MAX7456", W, H, p))

# ------------------------------------------------------------------ CJAE10P06
# Jiangsu Changjing CJAE10P06, PDFNWB3x3-8L. Equivalent-circuit diagram p.1:
# pins 1,2,3 = Source; pin 4 = Gate; pins 5,6,7,8 = Drain; EP (D1 2.35-2.55 x
# E1 1.70-1.90 mm) is the drain tab -> pad 9.
W, H = 20.32, 20.32
p = [pin("4", "G", -(W/2+2.54), 0, 0, "input")]
for i, num in enumerate(["1","2","3"]):
    p.append(pin(num, "S", -5.08+2.54*i, -(H/2+2.54), 90, "passive"))
for i, num in enumerate(["5","6","7","8","9"]):
    p.append(pin(num, "D" if num!="9" else "D(EP)", -5.08+2.54*i, H/2+2.54, 270, "passive"))
out.append(sym("CJAE10P06","Q","CJAE10P06",
    "fc_f405:PDFNWB-8L_3x3mm_DrainPad",
    "https://www.lcsc.com/datasheet/C2943210.pdf",
    "P-channel MOSFET -60V -10A 26mR@-10V, Vgs +-20V, DFN 3x3 8L. Reverse-polarity switch",
    "PMOS MOSFET P-channel reverse polarity", W, H, p))

# ---------------------------------------------------------------- D_TVS_Uni
# Unidirectional TVS (SMBJ30A). Pin 1 = cathode (banded end, SMB pad 1),
# pin 2 = anode. Device:D_TVS is the bidirectional A1/A2 symbol and is wrong here.
W, H = 7.62, 7.62
p = [pin("1", "K", -(W/2+2.54), 0, 0, "passive"),
     pin("2", "A",  (W/2+2.54), 0, 180, "passive")]
out.append(sym("D_TVS_Uni","D","D_TVS_Uni",
    "Diode_SMD:D_SMB",
    "https://www.lcsc.com/datasheet/C19077584.pdf",
    "Unidirectional TVS diode, cathode = pin 1 (banded end)",
    "TVS transient suppressor unidirectional", W, H, p))

out.append(')\n')
open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib", "fc_f405.kicad_sym"),"w").write("".join(out))
print("wrote fc_f405.kicad_sym")
