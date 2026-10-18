# Datasheets

These are the datasheets I used while designing the board. The .txt files are just text versions of the PDFs (made with `pdftotext -layout`) so they're easier to search.

## Power and memory

| File | Part | What I used it for |
|------|------|--------------------|
| [TPS54360_TI_SLVSBB4G_RevG.pdf](TPS54360_TI_SLVSBB4G_RevG.pdf) | TPS54360 | Both buck converters. The 5 V example is Fig. 34 in section 8.2. The compensation math is Eq 44-51 in this revision (older revisions number them 27-37) |
| [TLV1117_TI_SLVS561O_RevO.pdf](TLV1117_TI_SLVS561O_RevO.pdf) | TLV1117-33 | 3.3 V regulator |
| [W25Q128JV_Winbond_RevF.pdf](W25Q128JV_Winbond_RevF.pdf) | W25Q128JV | Blackbox flash |

## Main chips

| File | Part | What I checked |
|------|------|----------------|
| [raw/STM32F405_ST.pdf](raw/STM32F405_ST.pdf) | STM32F405RGT6 | 4 VDD pins (not 5), VCAP is 2x 2.2 uF with ESR under 2 ohm, VDDA filtering, VREF+ is tied inside on the LQFP-64, USB doesn't need series resistors |
| [raw/ICM42688P_TDK.pdf](raw/ICM42688P_TDK.pdf) | ICM-42688-P | Runs on 1.71-3.6 V, SPI up to 24 MHz, caps are 0.1 uF / 2.2 uF / 10 nF, pin 7 has to go to GND |
| [raw/AT7456E.pdf](raw/AT7456E.pdf) | AT7456E | 3 supply pins at 3.15-5.25 V, 27 MHz crystal with no load caps, 75 ohm on video in/out, 0.1 uF in, 22 uF out, pull-up on RESET |
| [raw/DPS368_Infineon.pdf](raw/DPS368_Infineon.pdf) | DPS368 | Just for reference. JLCPCB doesn't carry the DPS310 and barely had any DPS368 so I went with the BMP388 |

## Swapped parts

| File | Part | Why |
|------|------|-----|
| [raw/BMP388_Bosch.pdf](raw/BMP388_Bosch.pdf) | BMP388 | Barometer, replaces the DPS310 since it was actually in stock |
| [raw/CJAE10P06_PFET.pdf](raw/CJAE10P06_PFET.pdf) | CJAE10P06 | Reverse polarity protection FET. -60 V, -10 A, 26 mohm, DFN 3x3 |
| [raw/SMMS0630-220M_L22uH.pdf](raw/SMMS0630-220M_L22uH.pdf) | SMMS0630-220M | 22 uH inductor for the 9 V rail, 3.5 A saturation, 2.6 A rms, 135 mohm |
| [raw/MWSA0603S-8R2M_L8u2.pdf](raw/MWSA0603S-8R2M_L8u2.pdf) | MWSA0603S-8R2MT | Backup inductor for 5 V. I'd rather use the SMMS0630-8R2M since it's the same family as the 9 V one |
| [raw/RVT1H101M0607_bulk.pdf](raw/RVT1H101M0607_bulk.pdf) | RVT1H101M0607 | Bulk input cap. Rated 130 mA ripple at 120 Hz, which works out to about 182 mA at 10 kHz and up |

A few of these manufacturer sites block downloads from scripts, so I grabbed the PDFs from JLCPCB/LCSC instead.
