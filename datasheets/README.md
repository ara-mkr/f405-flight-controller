# Datasheets

## Verified — Phase 1
| File | Part | Document | Used for |
|------|------|----------|----------|
| TPS54360_TI_SLVSBB4G_RevG.pdf | TPS54360 | TI SLVSBB4G Rev G, Jun 2018 | Both bucks. 5 V design example Fig. 34 sec 8.2. Compensation Eq 44-51 (NOT 27-37 — that numbering is from an older revision) |
| TLV1117_TI_SLVS561O_RevO.pdf | TLV1117-33 | TI SLVS561O Rev O, Jun 2025 | 3.3 V LDO |
| W25Q128JV_Winbond_RevF.pdf | W25Q128JV | Winbond Rev F, Mar 2018 | Blackbox flash |

## Verified — Phase 3 Step 1 (the four gates)
Retrieved via the JLCPCB file API / LCSC CDN after ST, TDK, Infineon and Maxim all
bot-blocked direct curl. Method that works:
  1. `sqlite3 ~/Library/Application\ Support/kicad-mcp/jlcpcb_parts.db \
       "SELECT datasheet FROM components WHERE mfr_part LIKE '<part>%'"`
  2. `curl -sL -A "<browser UA>" -e "https://jlcpcb.com/" -o out.pdf "<that url>"`
For LCSC: fetch `https://www.lcsc.com/datasheet/<Ccode>.pdf`, grep the returned HTML for
`https://datasheet.lcsc.com/datasheet/pdf/<hash>.pdf`, then curl that with a Referer.

| File | Part | Document | Gate closed |
|------|------|----------|-------------|
| raw/STM32F405_ST.pdf | STM32F405RGT6 | ST DocID022152 Rev 4 | VDD pin count (4, not 5), VCAP 2x2.2uF/ESR<2R, VDDA network, VREF+ internally bonded on LQFP64, no USB series R |
| raw/ICM42688P_TDK.pdf | ICM-42688-P | TDK DS-000347 Rev 1.2 | VDD/VDDIO 1.71-3.6 V, 24 MHz SPI, C1/C2/C3 = 0.1uF/2.2uF/10nF, pin 7 RESV must go to GND |
| raw/AT7456E.pdf | AT7456E | Hangzhou Zhongke S402-V1.1 | 3 rails 3.15-5.25 V, 27 MHz xtal (no load caps), 75R in/out, 0.1uF Cin, 22uF Cout+Csag, RESET pull-up |
| raw/DPS368_Infineon.pdf | DPS368 | Infineon v1.1 | Read for reference — DPS310 is NOT carried by JLCPCB, DPS368 only 285 in stock |

## Verified — Phase 3 Step 3 (substitutions and newly-locked MPNs)
| File | Part | Why |
|------|------|-----|
| raw/BMP388_Bosch.pdf | BMP388 | Proposed barometer replacing the unavailable DPS310. 15k stock |
| raw/CJAE10P06_PFET.pdf | CJAE10P06 | Reverse-polarity P-FET. -60 V / -10 A / 26 mR @ -10 V / Vgs +-20 V, DFN 3x3 |
| raw/SMMS0630-220M_L22uH.pdf | SMMS0630-220M | 9 V inductor. 22 uH, Isat 3.5 A, Irms 2.6 A, DCR 135 mR |
| raw/MWSA0603S-8R2M_L8u2.pdf | MWSA0603S-8R2MT | 5 V inductor alternative (SMMS0630-8R2M preferred — same family) |
| raw/RVT1H101M0607_bulk.pdf | RVT1H101M0607 | Bulk cap candidate. Ripple 130 mA@120Hz x1.40 @>=10kHz = 182 mA |

Extracted text (`*.txt`) is gitignored — regenerate with
`pdftotext -layout <file>.pdf <file>.txt`.
