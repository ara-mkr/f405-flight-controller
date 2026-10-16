# -*- coding: utf-8 -*-
"""Complete netlist for the 30.5x30.5 mm STM32F405 flight controller.

Source of truth is DESIGN_PLAN.md plus the Phase 3 Step 1-3 corrections that were
put to the user and approved:
  * barometer DPS310 -> BMP388            (DPS310 not carried by JLCPCB)
  * MCU  STM32F405RGT6 -> RGT7            (29 units in stock)
  * AT7456E SOIC-28 -> HTSSOP-28-EP, plus the datasheet-mandated video coupling
    network, SAG correction and RESET pull-up that the plan omitted
  * USB VBUS -> Schottky -> +5V           (plan never connected VBUS)
  * MCU VDD decoupling 5 caps -> 4        (LQFP64 has 4 VDD pins, not 5)
  * 9 V compensation R31/C14/C15 = 11.5k / 33nF / 47pF   (Step 2 calculation)
Every value carries the datasheet it came from in the comments.
"""

# ---------------------------------------------------------------- footprints
FP_R    = "Resistor_SMD:R_0402_1005Metric"
FP_R6   = "Resistor_SMD:R_0603_1608Metric"
FP_C    = "Capacitor_SMD:C_0402_1005Metric"
FP_C6   = "Capacitor_SMD:C_0603_1608Metric"
FP_C8   = "Capacitor_SMD:C_0805_2012Metric"
FP_C12  = "Capacitor_SMD:C_1210_3225Metric"
FP_FB   = "Resistor_SMD:R_0603_1608Metric"
FP_LED  = "LED_SMD:LED_0603_1608Metric"
FP_IND  = "fc_f405:L_SMMS0630_7.1x6.6mm"
FP_XTAL = "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm"
FP_SMB  = "Diode_SMD:D_SMB"
FP_SMC  = "Diode_SMD:D_SMC"
FP_SOD123 = "Diode_SMD:D_SOD-123"
FP_SOT23  = "Package_TO_SOT_SMD:SOT-23"
FP_ELEC   = "Capacitor_SMD:CP_Elec_8x10.5"

C = []   # components
T = []   # sheet annotations

def add(ref, lib, val, at, pins, fp="", lcsc="", mpn="", ds="~", rdy=12.7, vdy=10.16):
    C.append(dict(ref=ref, lib=lib, val=val, at=at, pins=pins, fp=fp,
                  lcsc=lcsc, mpn=mpn, ds=ds, rdy=rdy, vdy=vdy))

def R(ref, val, at, a, b, fp=FP_R, lcsc="", mpn=""):
    add(ref, "Device:R", val, at, {"1": a, "2": b}, fp, lcsc, mpn, rdy=2.54, vdy=-2.54)

def Cap(ref, val, at, a, b, fp=FP_C, lcsc="", mpn=""):
    add(ref, "Device:C", val, at, {"1": a, "2": b}, fp, lcsc, mpn, rdy=2.54, vdy=-2.54)

def note(s, at, sz=2.5): T.append(dict(s=s, at=at, sz=sz))

# =========================================================== 1. POWER INPUT
note("1. BATTERY INPUT, REVERSE POLARITY, TVS CLAMP", (20, 22), 3.0)
add("J1", "Connector_Generic:Conn_01x02", "VBAT pads", (40, 45),
    {"1": "VBAT_IN", "2": "GND"}, "fc_f405:SolderPad_3mm_x2", mpn="Dia 3mm plated pads")
# Q1 CJAE10P06: -60V/-10A/26mR@-10V, Vgs +-20V  (LCSC C2943210 datasheet p.1)
add("Q1", "fc_f405:CJAE10P06", "CJAE10P06", (75, 55),
    {"1": "VBAT_IN", "2": "VBAT_IN", "3": "VBAT_IN", "4": "Q1_GATE",
     "5": "VBAT", "6": "VBAT", "7": "VBAT", "8": "VBAT", "9": "VBAT"},
    "fc_f405:PDFNWB-8L_3x3mm_DrainPad", "C2943210", "CJAE10P06", rdy=16, vdy=-16)
R("R22", "100k", (60, 80), "Q1_GATE", "GND", lcsc="C25741", mpn="0402WGF1003TCE")
# D4 clamps Vgs to 15 V so the +-20 V Vgs limit is never reached at 6S (26.1 V)
add("D4", "Device:D_Zener", "BZT52C15", (95, 80), {"1": "VBAT_IN", "2": "Q1_GATE"},
    FP_SOD123, "C2932746", "BZT52C15", rdy=6, vdy=-6)
# D3 SMBJ30A: 30 V standoff (above 26.1 V worst case), ~48 V clamp, 600 W
add("D3", "fc_f405:D_TVS_Uni", "SMBJ30A", (120, 55), {"1": "VBAT", "2": "GND"},
    FP_SMB, "C19077584", "SMBJ30A", rdy=6, vdy=-6)
# C_BULK 100uF/50V 105C. Ripple 130 mA@120Hz x1.40 (>=10 kHz factor, datasheet p.3)
# = 182 mA vs ~139 mA seen; the 4 input ceramics take ~87% of the 1.05 A total.
add("C43", "Device:C_Polarized", "100uF/50V", (140, 55), {"1": "VBAT", "2": "GND"},
    FP_ELEC, "C116241", "UUD1H101MNL1GS", rdy=6, vdy=-6)
add("#FLG01", "power:PWR_FLAG", "PWR_FLAG", (40, 100), {"1": "VBAT"}, rdy=4, vdy=-4)
add("#FLG02", "power:PWR_FLAG", "PWR_FLAG", (55, 80), {"1": "GND"}, rdy=4, vdy=-4)

# ============================================================== 2. 5 V BUCK
note("2. 5 V BUCK - TPS54360, values verbatim from TI SLVSBB4G Fig. 34", (170, 22), 3.0)
add("U6", "Regulator_Switching:TPS54360DDA", "TPS54360DDAR", (215, 60),
    {"1": "BOOT_5V", "2": "VBAT", "3": "UVLO_5V", "4": "RT_5V", "5": "FB_5V",
     "6": "COMP_5V", "7": "GND", "8": "SW_5V", "9": "GND"},
    "Package_SO:SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.95x4.9mm_Mask2.71x3.4mm", "C44377", "TPS54360DDAR",
    rdy=17, vdy=-17)
Cap("C1", "2.2uF/50V", (180, 90), "VBAT", "GND", FP_C12, "C1950", "1210B225K500NT")
Cap("C2", "2.2uF/50V", (192, 90), "VBAT", "GND", FP_C12, "C1950", "1210B225K500NT")
Cap("C10", "0.1uF/25V", (245, 35), "BOOT_5V", "SW_5V", FP_C6, "C14663", "CC0603KRX7R9BB104")
R("R1", "523k", (175, 45), "VBAT", "UVLO_5V", FP_R6, "C5126197", "FRC0603F5233TS")
R("R2", "84.5k", (175, 68), "UVLO_5V", "GND", FP_R6, "C2998081", "FRC0603F8452TS")
R("R3", "162k", (192, 68), "RT_5V", "GND", FP_R6, "C2998114", "FRC0603F1623TS")
add("D1", "Device:D_Schottky", "B560C-13-F", (250, 75), {"1": "SW_5V", "2": "GND"},
    FP_SMC, "C85100", "B560C-13-F", rdy=6, vdy=-6)
add("L1", "Device:L", "8.2uH", (265, 50), {"1": "SW_5V", "2": "+5V"},
    FP_IND, "C128691", "SMMS0630-8R2M", rdy=6, vdy=-6)
Cap("C6", "47uF/10V", (282, 75), "+5V", "GND", FP_C12, "C5189825", "CS3225X7R476K100NRL")
Cap("C7", "47uF/10V", (294, 75), "+5V", "GND", FP_C12, "C5189825", "CS3225X7R476K100NRL")
# Vout = 0.8 x (1 + 53.6/10.2) = 5.004 V
R("R5", "53.6k", (310, 45), "+5V", "FB_5V", FP_R6, "C2930115", "FRC0603F5362TS")
R("R6", "10.2k", (310, 68), "FB_5V", "GND", FP_R6, "C2933125", "FRC0603F1022TS")
R("R4", "13.0k", (330, 45), "COMP_5V", "COMP_5V_M", FP_R6, "C22797", "0603WAF1302T5E")
Cap("C12", "6800pF", (330, 68), "COMP_5V_M", "GND", FP_C, "C1542", "0402B682K500NT")
Cap("C13", "39pF", (345, 60), "COMP_5V", "GND", FP_C, "C1563", "0402CG390J500NT")
add("#FLG03", "power:PWR_FLAG", "PWR_FLAG", (282, 100), {"1": "+5V"}, rdy=4, vdy=-4)

# ============================================================== 3. 9 V BUCK
note("3. 9 V VTX BUCK - TPS54360, L recomputed and R31/C14/C15 from TI Eq 44-51", (380, 22), 3.0)
add("U7", "Regulator_Switching:TPS54360DDA", "TPS54360DDAR", (425, 60),
    {"1": "BOOT_9V", "2": "VBAT", "3": "UVLO_9V", "4": "RT_9V", "5": "FB_9V",
     "6": "COMP_9V", "7": "GND", "8": "SW_9V", "9": "GND"},
    "Package_SO:SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.95x4.9mm_Mask2.71x3.4mm", "C44377", "TPS54360DDAR",
    rdy=17, vdy=-17)
Cap("C3", "2.2uF/50V", (390, 90), "VBAT", "GND", FP_C12, "C1950", "1210B225K500NT")
Cap("C4", "2.2uF/50V", (402, 90), "VBAT", "GND", FP_C12, "C1950", "1210B225K500NT")
Cap("C11", "0.1uF/25V", (455, 35), "BOOT_9V", "SW_9V", FP_C6, "C14663", "CC0603KRX7R9BB104")
R("R9", "523k", (385, 45), "VBAT", "UVLO_9V", FP_R6, "C5126197", "FRC0603F5233TS")
R("R10", "84.5k", (385, 68), "UVLO_9V", "GND", FP_R6, "C2998081", "FRC0603F8452TS")
R("R11", "162k", (402, 68), "RT_9V", "GND", FP_R6, "C2998114", "FRC0603F1623TS")
add("D2", "Device:D_Schottky", "B560C-13-F", (460, 75), {"1": "SW_9V", "2": "GND"},
    FP_SMC, "C85100", "B560C-13-F", rdy=6, vdy=-6)
# L2 = 22uH: Lmin 21.8uH from TI inductor eq at Vin 26.1 V, Vout 9 V, K_IND 0.3.
# SMMS0630-220M Isat 3.50 A vs 1.72 A peak, Irms 2.60 A vs 1.5 A.
add("L2", "Device:L", "22uH", (475, 50), {"1": "SW_9V", "2": "+9V"},
    FP_IND, "C128694", "SMMS0630-220M", rdy=6, vdy=-6)
Cap("C8", "47uF/16V", (492, 75), "+9V", "GND", FP_C12, "C5440143", "CS3225X7R476K160NRL")
Cap("C9", "47uF/16V", (504, 75), "+9V", "GND", FP_C12, "C5440143", "CS3225X7R476K160NRL")
# Vout = 0.8 x (1 + 105/10.2) = 9.035 V
R("R8", "105k", (520, 45), "+9V", "FB_9V", FP_R6, "C2933067", "FRC0402F1053TS")
R("R7", "10.2k", (520, 68), "FB_9V", "GND", FP_R6, "C2933125", "FRC0603F1022TS")
# ---- Step 2 result: computed 11.463k / 30515pF / 46.3pF, NOT copied from the 5 V rail
R("R31", "11.5k", (540, 45), "COMP_9V", "COMP_9V_M", FP_R6, "C25949", "0603WAF1152T5E")
Cap("C14", "33nF", (540, 68), "COMP_9V_M", "GND", FP_C, "C507072", "0402B333K500NT")
Cap("C15", "47pF", (555, 60), "COMP_9V", "GND", FP_C, "C1567", "0402CG470J500NT")
add("#FLG04", "power:PWR_FLAG", "PWR_FLAG", (492, 100), {"1": "+9V"}, rdy=4, vdy=-4)

# ================================================= 4. 3.3 V LDO + USB FEED
note("4. 3.3 V LDO AND USB VBUS OR-ING", (610, 22), 3.0)
# TLV1117 DCY SOT-223: 1 = ADJ/GND, 2 = OUTPUT (tab), 3 = INPUT  (SLVS561O Fig 4-1)
add("U8", "Regulator_Linear:TLV1117-33", "TLV1117-33IDCYR", (660, 55),
    {"1": "GND", "2": "+3V3", "3": "+5V"},
    "Package_TO_SOT_SMD:SOT-223-3_TabPin2", "C37359", "TLV1117-33IDCYR", rdy=10, vdy=-10)
Cap("C16", "10uF/16V", (635, 75), "+5V", "GND", FP_C8, "C162430", "GRM21BZ71C106KE15L")
Cap("C17", "22uF/10V", (690, 75), "+3V3", "GND", FP_C8, "C45783", "CL21A226MAQNNNE")
# USB VBUS -> +5V. B5819W 40 V / 1 A. At the USB low limit 4.75 V and Vf ~0.4 V the
# rail is 4.35 V; TLV1117 worst-case dropout at 240 mA is ~0.55 V -> 0.50 V headroom.
add("D6", "Device:D_Schottky", "B5819W", (660, 90), {"1": "+5V", "2": "USB_VBUS"},
    FP_SOD123, "C8598", "B5819W SL", rdy=6, vdy=-6)
add("#FLG06", "power:PWR_FLAG", "PWR_FLAG", (730, 75), {"1": "USB_VBUS"}, rdy=4, vdy=-4)

# ================================================================== 5. MCU
note("5. MCU - STM32F405RGT7, LQFP-64. Pin map per DESIGN_PLAN sec 4", (20, 175), 3.0)
add("U1", "MCU_ST_STM32F4:STM32F405RGTx", "STM32F405RGT7", (105, 300), {
    # -- power (LQFP64 has FOUR VDD pins: 19/32/48/64, and VSS on 18/63) --
    "19": "+3V3", "32": "+3V3", "48": "+3V3", "64": "+3V3",
    "18": "GND", "63": "GND",
    "13": "VDDA", "12": "GND",
    "1":  "+3V3",                      # VBAT tied to 3V3, no RTC coin cell
    "31": "VCAP_1", "47": "VCAP_2",
    "7":  "NRST",  "60": "BOOT0",
    "5":  "OSC_IN", "6": "OSC_OUT",    # PH0 / PH1
    # -- UART4 (ESC telemetry) --
    "14": "UART4_TX", "15": "UART4_RX",          # PA0 PA1
    # -- USART2 (GPS) --
    "16": "UART2_TX", "17": "UART2_RX",          # PA2 PA3
    # -- SPI1, gyro only --
    "20": "GYRO_CS",  "21": "SPI1_SCK",          # PA4 PA5
    "22": "SPI1_MISO","23": "SPI1_MOSI",         # PA6 PA7
    "41": "LED_STRIP",                            # PA8  TIM1_CH1
    "42": "!NC", "43": "!NC",                     # PA9 PA10 spare
    "44": "USB_DM", "45": "USB_DP",               # PA11 PA12
    "46": "SWDIO", "49": "SWCLK",                 # PA13 PA14
    "50": "!NC",                                  # PA15 spare
    # -- port C --
    "8":  "FLASH_CS",                             # PC0
    "9":  "VBAT_SENSE", "10": "CURR_SENSE", "11": "RSSI_ADC",   # PC1 PC2 PC3
    "24": "GYRO_INT",  "25": "LED1",              # PC4 PC5
    "37": "UART6_TX", "38": "UART6_RX",           # PC6 PC7
    "39": "CAM_CTRL",                             # PC8  TIM8_CH3
    "40": "!NC",                                  # PC9  spare
    "51": "!NC", "52": "!NC",                     # PC10 PC11 spare
    "53": "UART5_TX",                             # PC12
    "2":  "BEEPER_GATE",                          # PC13
    "3":  "!NC", "4": "!NC",                      # PC14 PC15 OSC32, unused
    "54": "UART5_RX",                             # PD2
    # -- port B --
    "26": "MOTOR3", "27": "MOTOR4",               # PB0 PB1
    "28": "BOOT1",                                # PB2
    "55": "LED0",                                 # PB3  (JTDO, free once JTAG off)
    "56": "MOTOR1", "57": "MOTOR2",               # PB4 PB5
    "58": "UART1_TX", "59": "UART1_RX",           # PB6 PB7
    "61": "I2C1_SCL", "62": "I2C1_SDA",           # PB8 PB9
    "29": "UART3_TX", "30": "UART3_RX",           # PB10 PB11
    "33": "OSD_CS",                               # PB12
    "34": "SPI2_SCK", "35": "SPI2_MISO", "36": "SPI2_MOSI",     # PB13-15
    },
    "Package_QFP:LQFP-64_10x10mm_P0.5mm", "C1337199", "STM32F405RGT7",
    "https://www.st.com/resource/en/datasheet/stm32f405rg.pdf", rdy=52, vdy=-52)

# MCU decoupling. ST Fig. 21: one 100 nF per VDD pin + one 4.7 uF bulk;
# VCAP 2 x 2.2 uF ESR < 2 ohm (Table 16); VDDA 1 uF // 100 nF // 10 nF.
for i, x in enumerate((150, 162, 174, 186)):
    Cap("C%d" % (18 + i), "0.1uF", (x, 200), "+3V3", "GND", FP_C, "C1525", "CL05B104KO5NNNC")
Cap("C23", "4.7uF", (198, 200), "+3V3", "GND", FP_C6, "C389010", "GRM188Z71C475KE21D")
Cap("C24", "2.2uF", (150, 230), "VCAP_1", "GND", FP_C6, "C86018", "GRM188R71A225KE15D")
Cap("C25", "2.2uF", (162, 230), "VCAP_2", "GND", FP_C6, "C86018", "GRM188R71A225KE15D")
add("FB1", "Device:FerriteBead", "600R/100MHz", (180, 240), {"1": "+3V3", "2": "VDDA"},
    FP_FB, "C1002", "GZ1608D601TF", rdy=6, vdy=-6)
Cap("C26", "1uF", (192, 255), "VDDA", "GND", FP_C, "C88945", "GRM155R70J105KA12D")
Cap("C44", "0.1uF", (204, 255), "VDDA", "GND", FP_C, "C1525", "CL05B104KO5NNNC")
Cap("C27", "10nF", (216, 255), "VDDA", "GND", FP_C, "C15195", "CL05B103KB5NNNC")
add("#FLG07", "power:PWR_FLAG", "PWR_FLAG", (228, 240), {"1": "VDDA"}, rdy=4, vdy=-4)
Cap("C30", "0.1uF", (150, 262), "NRST", "GND", FP_C, "C1525", "CL05B104KO5NNNC")
R("R18", "10k", (165, 262), "BOOT0", "GND", lcsc="C25744", mpn="0402WGF1002TCE")
R("R19", "10k", (178, 262), "BOOT1", "GND", lcsc="C25744", mpn="0402WGF1002TCE")

# 8 MHz crystal. Sourced part TAXM8M4RDBCCT2T has CL = 10 pF, so the plan's
# C = 2 x (CL - Cstray) = 2 x (10 - 3) = 14 pF -> 15 pF standard (plan assumed CL 8 pF).
add("Y1", "Device:Crystal_GND24", "8MHz", (150, 290),
    {"1": "OSC_IN", "2": "GND", "3": "OSC_OUT", "4": "GND"},
    FP_XTAL, "C400090", "TAXM8M4RDBCCT2T", rdy=8, vdy=-8)
Cap("C28", "15pF", (140, 310), "OSC_IN", "GND", FP_C, "C1548", "0402CG150J500NT")
Cap("C29", "15pF", (162, 310), "OSC_OUT", "GND", FP_C, "C1548", "0402CG150J500NT")

# SWD + boot pads
add("J2", "Connector_Generic:Conn_01x04", "SWD pads", (150, 345),
    {"1": "+3V3", "2": "SWDIO", "3": "SWCLK", "4": "GND"},
    "fc_f405:SolderPad_1mm_x4", mpn="1.0mm pads", rdy=10, vdy=-10)
add("J3", "Connector_Generic:Conn_01x02", "BOOT pads", (150, 375),
    {"1": "BOOT0", "2": "+3V3"}, "fc_f405:SolderPad_1mm_x2", mpn="1.0mm pads",
    rdy=8, vdy=-8)

# =================================================================== 6. IMU
note("6. IMU - ICM-42688-P, own SPI1", (250, 175), 3.0)
add("U2", "fc_f405:ICM-42688-P", "ICM-42688-P", (300, 230), {
    "12": "GYRO_CS", "13": "SPI1_SCK", "14": "SPI1_MOSI", "1": "SPI1_MISO",
    "4": "GYRO_INT",
    "9": "GND",            # INT2/FSYNC -> GND, datasheet: "Connect to GND if FSYNC not used"
    "5": "+3V3_GYRO", "8": "+3V3_GYRO", "6": "GND",
    "7": "GND",            # RESV pin 7 is a MANDATORY ground, not optional
    "2": "GND", "3": "GND", "10": "GND", "11": "GND"},
    "fc_f405:TDK_LGA-14_2.5x3.0mm", "C1850418", "ICM-42688-P",
    "https://invensense.tdk.com/download-pdf/icm-42688-p-datasheet/", rdy=20, vdy=-20)
add("FB2", "Device:FerriteBead", "600R/100MHz", (270, 195), {"1": "+3V3", "2": "+3V3_GYRO"},
    FP_FB, "C1002", "GZ1608D601TF", rdy=6, vdy=-6)
Cap("C39", "10uF", (255, 265), "+3V3_GYRO", "GND", FP_C6, "C19702", "CL10A106KP8NNNC")
Cap("C31", "0.1uF", (270, 265), "+3V3_GYRO", "GND", FP_C, "C1525", "CL05B104KO5NNNC")
# datasheet Table 10 BOM: C1 0.1uF + C2 2.2uF on VDD, C3 10nF on VDDIO
Cap("C32", "2.2uF", (285, 265), "+3V3_GYRO", "GND", FP_C6, "C86018", "GRM188R71A225KE15D")
Cap("C33", "10nF", (300, 265), "+3V3_GYRO", "GND", FP_C, "C15195", "CL05B103KB5NNNC")
add("#FLG08", "power:PWR_FLAG", "PWR_FLAG", (315, 195), {"1": "+3V3_GYRO"}, rdy=4, vdy=-4)

# ============================================================== 7. BAROMETER
note("7. BAROMETER - BMP388 on I2C1", (350, 175), 3.0)
add("U3", "fc_f405:BMP388", "BMP388", (390, 230), {
    "1": "+3V3", "10": "+3V3", "3": "GND", "8": "GND", "9": "GND",
    "2": "I2C1_SCL", "4": "I2C1_SDA",
    "5": "GND",        # SDO low -> I2C address 0x76. Datasheet: SDO must NOT float.
    "6": "+3V3",       # CSB high selects I2C
    "7": "!NC"},       # INT unused
    "fc_f405:Bosch_LGA-10_2.0x2.0mm", "C779278", "BMP388",
    "https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmp388-ds001.pdf",
    rdy=15, vdy=-15)
Cap("C34", "0.1uF", (365, 262), "+3V3", "GND", FP_C, "C1525", "CL05B104KO5NNNC")
Cap("C35", "0.1uF", (378, 262), "+3V3", "GND", FP_C, "C1525", "CL05B104KO5NNNC")
R("R14", "4.7k", (415, 195), "+3V3", "I2C1_SCL", lcsc="C25900", mpn="0402WGF4701TCE")
R("R15", "4.7k", (428, 195), "+3V3", "I2C1_SDA", lcsc="C25900", mpn="0402WGF4701TCE")
add("J4", "Connector_Generic:Conn_01x04", "I2C pads", (390, 300),
    {"1": "+3V3", "2": "I2C1_SCL", "3": "I2C1_SDA", "4": "GND"},
    "fc_f405:SolderPad_1mm_x4", mpn="ext compass", rdy=10, vdy=-10)

# ================================================================== 8. OSD
note("8. OSD - AT7456E. DVDD on 3.3 V so SDOUT never puts 5 V on shared SPI2", (470, 175), 3.0)
add("U4", "fc_f405:AT7456E", "AT7456E", (540, 250), {
    "3": "+3V3", "4": "GND",            # DVDD 3.3 V -> SPI levels match the MCU and flash
    "21": "+5V", "20": "GND",           # AVDD 5 V for full 2.4 Vpp video swing
    "24": "+5V", "23": "GND",           # PVDD 5 V, driver
    "29": "GND",                        # exposed pad, internally AGND
    "5": "OSD_XI", "6": "OSD_XO",
    "8": "OSD_CS", "9": "SPI2_MOSI", "10": "SPI2_SCK", "11": "SPI2_MISO",
    "19": "OSD_RESET",
    "13": "GND",                        # SYNC_IN unused -> defined level
    "7": "!NC", "12": "!NC", "17": "!NC", "18": "!NC",   # CLKOUT, LOS, VSYNC, HSYNC
    "22": "OSD_VIN", "26": "OSD_VOUT", "25": "OSD_SAG"},
    "Package_SO:HTSSOP-28-1EP_4.4x9.7mm_P0.65mm_EP2.85x5.4mm", "C82351", "AT7456E",
    "https://www.lcsc.com/datasheet/C82351.pdf", rdy=28, vdy=-28)
Cap("C36", "0.1uF", (495, 300), "+3V3", "GND", FP_C, "C1525", "CL05B104KO5NNNC")   # DVDD
Cap("C37", "0.1uF", (508, 300), "+5V", "GND", FP_C, "C1525", "CL05B104KO5NNNC")    # AVDD
Cap("C38", "0.1uF", (521, 300), "+5V", "GND", FP_C, "C1525", "CL05B104KO5NNNC")    # PVDD
# 27 MHz between CLKIN and XFB. Datasheet Fig. 2 shows a bare crystal - no load caps.
add("Y2", "Device:Crystal_GND24", "27MHz", (495, 215),
    {"1": "OSD_XI", "2": "GND", "3": "OSD_XO", "4": "GND"},
    FP_XTAL, "C19711726", "XL2EL89CMI-111YLC-27M", rdy=8, vdy=-8)
# RESET pull-up to AVDD (+5 V): datasheet abs max for RESET is VAVDD + 0.3 V and
# VIH is 2.1 V, so 5 V is legal - and it keeps R32 on the OSD's own supply.
R("R32", "1k", (575, 205), "+5V", "OSD_RESET", lcsc="C11702", mpn="0402WGF1001TCE")
# Video in: 75 R termination + 0.1 uF AC coupling (datasheet: coupling cap is mandatory)
R("R29", "75R", (600, 300), "CAM_IN", "GND", lcsc="C25133", mpn="0402WGF750JTCE")
Cap("C45", "0.1uF", (600, 270), "CAM_IN", "OSD_VIN", FP_C, "C1525", "CL05B104KO5NNNC")
# Video out: COUT + CSAG = 22uF/22uF -> 0.4% line-time distortion (datasheet Table 2),
# then a 75 R back-match into the VTX's 75 R = the 150 R "standard video load".
Cap("C46", "22uF", (600, 215), "OSD_VOUT", "VID_NODE", FP_C8, "C45783", "CL21A226MAQNNNE")
Cap("C47", "22uF", (640, 215), "OSD_SAG", "VID_NODE", FP_C8, "C45783", "CL21A226MAQNNNE")
R("R30", "75R", (670, 215), "VID_NODE", "VTX_OUT", lcsc="C25133", mpn="0402WGF750JTCE")

# ================================================================ 9. FLASH
note("9. BLACKBOX FLASH - W25Q128JV on SPI2", (285, 340), 3.0)
add("U5", "Memory_Flash:W25Q128JVS", "W25Q128JVSIQ", (300, 375), {
    "1": "FLASH_CS", "2": "SPI2_MISO", "5": "SPI2_MOSI", "6": "SPI2_SCK",
    "3": "+3V3",       # /WP high - must not float
    "7": "+3V3",       # /HOLD high - must not float
    "8": "+3V3", "4": "GND"},
    "Package_SO:SOIC-8_5.3x5.3mm_P1.27mm", "C97521", "W25Q128JVSIQ",
    "https://www.winbond.com/resource-files/w25q128jv%20revf%2003272018%20plus.pdf",
    rdy=17, vdy=-17)
Cap("C48", "0.1uF", (335, 400), "+3V3", "GND", FP_C, "C1525", "CL05B104KO5NNNC")
Cap("C49", "1uF", (348, 400), "+3V3", "GND", FP_C, "C88945", "GRM155R70J105KA12D")
# Both chip selects pulled up so neither device wakes on the other's traffic during reset
R("R16", "10k", (255, 340), "+3V3", "OSD_CS", lcsc="C25744", mpn="0402WGF1002TCE")
R("R17", "10k", (268, 340), "+3V3", "FLASH_CS", lcsc="C25744", mpn="0402WGF1002TCE")

# ================================================================== 10. USB
note("10. USB-C + ESD", (20, 420), 3.0)
add("J5", "Connector:USB_C_Receptacle_USB2.0_16P", "USB-C 16P", (60, 470), {
    "A1": "GND", "B1": "GND", "A12": "GND", "B12": "GND",
    "A4": "USB_VBUS", "B4": "USB_VBUS", "A9": "USB_VBUS", "B9": "USB_VBUS",
    "A5": "USB_CC1", "B5": "USB_CC2",
    "A6": "USB_DP_C", "B6": "USB_DP_C", "A7": "USB_DM_C", "B7": "USB_DM_C",
    "A8": "!NC", "B8": "!NC", "SH": "GND"},
    "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", "C2765186", "TYPE-C 16PIN 2MD(073)",
    rdy=32, vdy=-32)
# Mandatory: without these two the host never sees a device and supplies no VBUS
R("R20", "5.1k", (95, 500), "USB_CC1", "GND", lcsc="C25905", mpn="0402WGF5101TCE")
R("R21", "5.1k", (108, 500), "USB_CC2", "GND", lcsc="C25905", mpn="0402WGF5101TCE")
add("U9", "Power_Protection:USBLC6-2SC6", "USBLC6-2SC6", (140, 465), {
    "1": "USB_DP_C", "6": "USB_DP", "3": "USB_DM_C", "4": "USB_DM",
    "5": "USB_VBUS", "2": "GND"},
    "Package_TO_SOT_SMD:SOT-23-6", "C2687116", "USBLC6-2SC6", rdy=12, vdy=-12)

# ================================================ 11. ESC / MOTOR CONNECTOR
note("11. ESC CONNECTOR AND POWER PADS", (200, 420), 3.0)
add("J6", "Connector_Generic:Conn_01x08", "JST-SH 8P", (230, 470), {
    "1": "CURR_IN", "2": "VBAT", "3": "GND", "4": "MOTOR1", "5": "MOTOR2",
    "6": "MOTOR3", "7": "MOTOR4", "8": "UART4_RX"},
    "Connector_JST:JST_SH_SM08B-SRSS-TB_1x08-1MP_P1.00mm_Horizontal",
    "C160407", "SM08B-SRSS-TB(LF)(SN)", rdy=20, vdy=-20)

# ============================================== 12. ADC FRONT ENDS (sec 4.6)
note("12. ADC FRONT ENDS", (300, 420), 3.0)
# 100k/10k -> 1/11. At 26.1 V worst case the pin sees 2.373 V, 0.93 V under VDDA.
R("R12", "100k", (330, 455), "VBAT", "VBAT_SENSE", lcsc="C25741", mpn="0402WGF1003TCE")
R("R13", "10k", (330, 478), "VBAT_SENSE", "GND", lcsc="C25744", mpn="0402WGF1002TCE")
Cap("C40", "0.1uF", (345, 478), "VBAT_SENSE", "GND", FP_C, "C1525", "CL05B104KO5NNNC")
R("R24", "1k", (370, 455), "CURR_IN", "CURR_SENSE", lcsc="C11702", mpn="0402WGF1001TCE")
Cap("C41", "0.1uF", (370, 478), "CURR_SENSE", "GND", FP_C, "C1525", "CL05B104KO5NNNC")
R("R25", "1k", (395, 455), "RSSI_IN", "RSSI_ADC", lcsc="C11702", mpn="0402WGF1001TCE")
Cap("C42", "0.1uF", (395, 478), "RSSI_ADC", "GND", FP_C, "C1525", "CL05B104KO5NNNC")

# ============================== 13. LEDs, BUZZER, LED STRIP, VIDEO/UART PADS
note("13. INDICATORS, BUZZER, EXTERNAL PADS", (440, 420), 3.0)
R("R27", "1k", (455, 450), "+3V3", "LED0_A", lcsc="C11702", mpn="0402WGF1001TCE")
add("LED1", "Device:LED", "GRN", (470, 465), {"2": "LED0_A", "1": "LED0"},
    FP_LED, "C965804", "XL-1608UGC-04", rdy=6, vdy=-6)
R("R28", "1k", (455, 490), "+3V3", "LED1_A", lcsc="C11702", mpn="0402WGF1001TCE")
add("LED2", "Device:LED", "RED", (470, 505), {"2": "LED1_A", "1": "LED1"},
    FP_LED, "C965799", "XL-1608SURC-06", rdy=6, vdy=-6)
# PC13 is limited to ~3 mA, so it drives a FET gate, never the buzzer itself
R("R23", "10k", (510, 450), "BEEPER_GATE", "Q2_G", lcsc="C25744", mpn="0402WGF1002TCE")
add("Q2", "Transistor_FET:Q_NMOS_GSD", "2N7002", (530, 470),
    {"1": "Q2_G", "2": "GND", "3": "BEEPER_DRAIN"}, FP_SOT23, "C414015", "2N7002K",
    rdy=12, vdy=-12)
add("D5", "Device:D", "1N4148W", (555, 450), {"1": "+5V", "2": "BEEPER_DRAIN"},
    FP_SOD123, "C81598", "1N4148W", rdy=6, vdy=-6)
add("J7", "Connector_Generic:Conn_01x02", "Buzzer pads", (585, 465),
    {"1": "+5V", "2": "BEEPER_DRAIN"}, "fc_f405:SolderPad_1mm_x2", rdy=8, vdy=-8)
add("J8", "Connector_Generic:Conn_01x03", "LED strip", (585, 505),
    {"1": "+5V", "2": "LED_STRIP", "3": "GND"}, "fc_f405:SolderPad_1mm_x3", rdy=10, vdy=-10)
# one shared GND pad for camera and VTX (both grounds also return through the
# plane) - frees the board edge the OSD's supply pins need
add("J9", "Connector_Generic:Conn_01x05", "Video pads", (650, 465), {
    "1": "CAM_IN", "2": "+5V", "3": "GND", "4": "VTX_OUT", "5": "+9V"},
    "fc_f405:SolderPad_1mm_x5", rdy=14, vdy=-14)
add("J10", "Connector_Generic:Conn_01x04", "UART1 (RX)", (700, 465),
    {"1": "+5V", "2": "UART1_TX", "3": "UART1_RX", "4": "GND"},
    "fc_f405:SolderPad_1mm_x4", rdy=12, vdy=-12)
add("J11", "Connector_Generic:Conn_01x04", "UART2 (GPS)", (740, 465),
    {"1": "+5V", "2": "UART2_TX", "3": "UART2_RX", "4": "GND"},
    "fc_f405:SolderPad_1mm_x4", rdy=12, vdy=-12)
add("J12", "Connector_Generic:Conn_01x04", "UART3 (VTX)", (780, 465),
    {"1": "+5V", "2": "UART3_TX", "3": "UART3_RX", "4": "GND"},
    "fc_f405:SolderPad_1mm_x4", rdy=12, vdy=-12)
add("J13", "Connector_Generic:Conn_01x04", "UART5", (700, 525),
    {"1": "+5V", "2": "UART5_TX", "3": "UART5_RX", "4": "GND"},
    "fc_f405:SolderPad_1mm_x4", rdy=12, vdy=-12)
add("J14", "Connector_Generic:Conn_01x04", "UART6", (740, 525),
    {"1": "+5V", "2": "UART6_TX", "3": "UART6_RX", "4": "GND"},
    "fc_f405:SolderPad_1mm_x4", rdy=12, vdy=-12)
add("J15", "Connector_Generic:Conn_01x05", "CAM/RSSI/U4TX", (780, 525),
    {"1": "CAM_CTRL", "2": "RSSI_IN", "3": "UART4_TX", "4": "+3V3", "5": "GND"},
    "fc_f405:SolderPad_1mm_x5", rdy=14, vdy=-14)

# ======================================================== 14. MOUNTING HOLES
# 4 x M3 on the 30.5 mm pattern (layout.HOLE_XY). On the board, not in the BOM.
for _i in range(4):
    add("H%d" % (_i + 1), "Mechanical:MountingHole", "M3", (40 + 25*_i, 560), {},
        "fc_f405:MountingHole_4.0mm", rdy=4, vdy=-4)
    C[-1]["mech"] = True

COMPONENTS, TEXTS = C, T
