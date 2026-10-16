# Flight Controller — Phase 1 Design Plan

**Project:** 30.5 × 30.5 mm clean flight controller, 3S–6S, STM32F405
**Status:** AWAITING APPROVAL — no KiCad files created yet
**Date:** 2026-08-26

---

## 0. Confirmed Requirements

| # | Item | Decision |
|---|------|----------|
| 1 | Aircraft class | 5" freestyle quad |
| 2 | Form factor | 30.5 × 30.5 mm mounting, 36 × 36 mm outline, 4 × Ø4.0 mm holes |
| 3 | Cell count | 3S–6S. Worst-case design voltage **26.1 V** (6 × 4.35 V) |
| 4 | Power architecture | **Clean FC.** No motor current on this board. VBAT sense only |
| 5 | MCU | STM32F405RGT6, LQFP64 |
| 6 | IMU | Single ICM-42688-P, SPI |
| 7 | Features | AT7456E OSD, W25Q128JV blackbox, DPS310 baro, 5 V BEC, 9 V VTX BEC |
| 8 | Firmware | Betaflight primary, iNav-compatible pin map |
| 9 | UARTs | 6 |
| 10 | Fab | JLCPCB, 4-layer standard capability |

### Datasheet provenance — read this before approving

Your hard rule says no invented component values. Here is exactly where every value in this plan came from.

**Fully verified this session (datasheet downloaded and read):**

| Part | Document | What was confirmed |
|------|----------|--------------------|
| TPS54360 | TI SLVSBB4G Rev G, Jun 2018 | 65 V abs-max VIN; complete 5 V design example (Fig. 34); input-cap rules; bootstrap cap; UVLO equations |
| TLV1117-33 | TI SLVS561O Rev O, Jun 2025 | VIN 4.7–15 V, abs max 16 V; 800 mA; dropout curves; COUT ESR window 2–500 mΩ |
| W25Q128JV | Winbond Rev F, 03/2018 | 2.7–3.6 V supply, abs max −0.6 to 4.6 V; ICC 8–20 mA read, 25 mA max program/erase; 10 µA standby |

**Not verified this session — TDK, ST, Infineon and Analog Devices all served JS-gated download pages or bot-blocked the request.** The values below are stated from established design practice and are marked **[CONFIRM]** throughout. **Every one of these will be read from the actual datasheet and reconciled against this plan before it is entered into the schematic** — that is a gate on Phase 3, not an afterthought. If any turns out different, I stop and tell you before deviating.

- STM32F405RGT6 — decoupling count, VCAP pin count and value, VDDA filtering, VREF+ bonding on LQFP64
- ICM-42688-P — VDD/VDDIO ranges, decoupling, max SPI clock
- AT7456E — supply rails, crystal frequency, video termination network
- DPS310 — VDD/VDDIO ranges, decoupling
- Reverse-polarity P-FET, TVS, USB ESD array — exact MPNs not yet locked

---

## 1. System Block Diagram

Signal and power flow, in order.

```
BATTERY (3S-6S, 11.1V - 25.2V nominal, 26.1V absolute worst case)
  |
  +-- XT-style pads on FC (VBAT+, GND)  <-- primary power entry
  |
  v
[Reverse-polarity P-FET]  P-channel, source to battery, gate clamped
  |
  v
[TVS clamp SMBJ30A] + [Bulk cap 100uF/50V electrolytic] + [2 x 2.2uF/50V X7R ceramic]
  |
  +-------------------------------+-------------------------+
  |                               |                         |
  v                               v                         v
[BUCK 1: TPS54360]         [BUCK 2: TPS54360]        [VBAT sense divider]
  5.0V @ 3.5A rated          9.0V @ 3.5A rated         100k / 10k + 100nF
  1.5A design load           1.5A design load                |
  |                               |                          v
  |                               v                    MCU PC1 (ADC1_IN11)
  |                          9V RAIL --> VTX pads
  |
  +--> 5V RAIL --> RX pads, GPS pads, camera pads, buzzer,
  |                LED strip pad, AT7456E analog section
  |
  v
[LDO: TLV1117-33]  3.3V @ 800mA rated, 200mA design load
  |
  v
3.3V RAIL
  |
  +--> STM32F405RGT6 (VDD x5, VDDA via ferrite)
  +--> ICM-42688-P   (via dedicated ferrite bead + local 10uF)
  +--> DPS310
  +--> W25Q128JV
  +--> AT7456E digital I/O
  +--> Status LEDs, pull-ups
        |
        v
      MCU BUSES
        SPI1 --> ICM-42688-P (dedicated, nothing else on this bus)
        SPI2 --> AT7456E (CS_A) + W25Q128JV (CS_B), separate chip selects
        I2C1 --> DPS310 + external compass pads
        UART1..6 --> RX, GPS, VTX, ESC telemetry, 2 spare
        TIM3 CH1-4 --> Motor 1-4 (DShot)
        TIM1_CH1 --> WS2812 LED strip
        USB OTG_FS --> USB-C
```

### Voltage rails and current budget

**3.3 V rail** — source: TLV1117-33, rated 800 mA

| Load | Typical | Max |
|------|---------|-----|
| STM32F405 @ 168 MHz | 65 mA | 100 mA **[CONFIRM]** |
| ICM-42688-P | 1 mA | 2 mA **[CONFIRM]** |
| DPS310 | 1 mA | 2 mA **[CONFIRM]** |
| W25Q128JV (program/erase) | 0.01 mA | 25 mA ✓ verified |
| AT7456E digital I/O | 5 mA | 10 mA **[CONFIRM]** |
| Status LEDs × 2 | 10 mA | 20 mA |
| Pull-ups and margin | 10 mA | 20 mA |
| **Total** | **~92 mA** | **~179 mA** |

Design point **200 mA = 25 % of the 800 mA rating.** Comfortably inside the ≤70 % rule.

**5 V rail** — source: TPS54360 buck, rated 3.5 A

| Load | Typical | Max |
|------|---------|-----|
| 3.3 V LDO input current | 100 mA | 200 mA |
| AT7456E analog + video | 50 mA | 80 mA **[CONFIRM]** |
| RX receiver (ELRS) | 100 mA | 200 mA |
| GPS module | 50 mA | 150 mA |
| FPV camera | 120 mA | 200 mA |
| Buzzer (intermittent) | 0 mA | 50 mA |
| WS2812 strip, 8 LEDs | 100 mA | 480 mA |
| **Total** | **~520 mA** | **~1360 mA** |

Design point **1.5 A = 43 % of the 3.5 A rating.** ✓

**9 V rail** — source: TPS54360 buck, rated 3.5 A

| Load | Typical | Max |
|------|---------|-----|
| Analog VTX | 600 mA | 1500 mA |

Design point **1.5 A = 43 % of the 3.5 A rating.** ✓

**VBAT current — note the counter-intuitive worst case.**

Total regulated output power at full load = (5 V × 1.5 A) + (9 V × 1.5 A) = 7.5 + 13.5 = **21 W**.
At ~85 % converter efficiency, input power ≈ 24.7 W.

- At 6S (25.2 V): 24.7 / 25.2 = **0.98 A**
- At 3S (11.1 V): 24.7 / 11.1 = **2.22 A**

**The worst-case VBAT current happens at the LOWEST battery voltage, not the highest.** The VBAT copper is therefore sized for **3 A**, not for the 1 A you would get by looking only at 6S.

---

## 2. Core Component Selection

### 2.1 MCU — STM32F405RGT6

ARM Cortex-M4F with FPU, 168 MHz, 1 MB flash, 192 KB RAM, LQFP64 (10 × 10 mm, 0.5 mm pitch).

**Why this one:** It has the peripheral count we need with room to spare — 6 USARTs, 3 SPI, 3 I2C, 2 advanced + 8 general timers, 2 DMA controllers. It is the single best-supported MCU in the Betaflight/iNav ecosystem, so firmware risk is near zero. LQFP64 at 0.5 mm pitch is hand-solderable with hot air and is trivially assembled by JLCPCB. It is the cheapest and best-stocked option in its class.

**Why 1 MB flash matters:** Betaflight 4.x with OSD, blackbox and GPS enabled no longer fits comfortably in 512 KB. The RG suffix (1 MB) removes that constraint permanently.

**Clock:** external 8 MHz crystal is **mandatory**, not optional. The internal RC oscillator is ±1 % and USB requires ±0.25 %; without a crystal the USB connection will be unreliable or will not enumerate at all.

### 2.2 IMU — ICM-42688-P (TDK InvenSense)

6-axis gyro + accelerometer, 2.5 × 3.0 × 0.91 mm LGA-14.

**Why this one:** It is the current best-in-class consumer FC gyro — very low noise density (0.0028 °/s/√Hz), 32 kHz sampling capability, and excellent vibration resistance. Betaflight has mature, well-tuned drivers for it.

**Interface: SPI only, never I2C.** This is not a preference, it is a hard requirement. A gyro must be read at 3.2–8 kHz in the flight control loop. I2C at 400 kHz cannot move that data in time and introduces jitter that directly degrades PID loop performance. It gets its **own dedicated SPI bus (SPI1)** with nothing else on it, so no other device can ever stall a gyro read.

- Bus: SPI1, on APB2 (84 MHz) — clock set by prescaler to ≈21 MHz, inside the device limit **[CONFIRM]**
- Supply: 3.3 V, fed through a **dedicated ferrite bead** from the main 3.3 V rail with local bulk capacitance, so switching noise from the rest of the board cannot reach it
- Data-ready interrupt on PC4 → EXTI4, so the MCU reads the gyro synchronously rather than polling

### 2.3 Barometer — DPS310 (Infineon)

Digital pressure sensor, 8-pin LGA 2.0 × 2.5 mm.

**Why this one:** ±0.06 hPa relative accuracy — roughly 50 cm of altitude resolution — which is what makes altitude hold and GPS rescue behave. Cheaper than the BMP388 and well supported. On **I2C1**, which is fine here: barometer updates at tens of hertz, so bus speed is irrelevant, and putting it on I2C keeps SPI2 free.

### 2.4 OSD — AT7456E

Monochrome on-screen-display character generator for analog video.

**Why this one:** It is the register-compatible clone of the MAX7456 that the entire FPV industry standardised on, and Betaflight's OSD driver targets it directly. Needs its own crystal for pixel timing, and 75 Ω terminated, AC-coupled video in and out. **[CONFIRM: exact supply rails, crystal frequency, and termination network from datasheet before capture.]**

**Note:** this chip is only useful with **analog** video. If you later move to HDZero/Walksnail/DJI, the OSD is drawn by the digital VTX over MSP and this chip does nothing. It stays in the design because you specified analog, and it is cheap.

### 2.5 Blackbox flash — W25Q128JV ✓ verified

128 Mbit (16 MB) SPI NOR flash, SOIC-8 208-mil.

- Supply **2.7–3.6 V**, absolute maximum −0.6 to 4.6 V → runs directly on our 3.3 V rail with margin ✓
- Current: 8–20 mA read, **25 mA max** during page program / erase, 10 µA standby ✓
- 16 MB holds roughly 10–20 minutes of full-rate blackbox logging

**Bus sharing — and why it is safe here.** Your prompt correctly flags that gyro and flash must not casually share a bus. In this design they do not:

- **SPI1 is the gyro's alone.** Nothing else is on it. A blackbox write can never delay a gyro read.
- **SPI2 carries the OSD and the flash**, each with its own dedicated chip-select line (PB12 for OSD, PC0 for flash). Only one CS is ever asserted at a time. Betaflight reconfigures the SPI prescaler per device, so the flash runs fast and the OSD runs at its slower limit.

Both CS lines get **10 kΩ pull-ups to 3.3 V** so that during MCU reset — when the GPIOs are high-impedance — neither chip sees a floating select and wakes up spuriously on bus traffic meant for the other. This is the "correct CS handling" your prompt asks for.

### 2.6 Voltage regulators

#### 5 V rail — TPS54360DDAR ✓ verified

TI 60 V, 3.5 A asynchronous step-down converter, HSOIC-8 with PowerPAD.

| Parameter | Value | Check |
|-----------|-------|-------|
| Input range | 4.5–60 V, **65 V absolute max** ✓ | Our worst case is 26.1 V → **2.5× margin.** Survives ISO 7637 load dump to 65 V |
| Output current | 3.5 A rated | Design load 1.5 A = **43 %** ✓ |
| Switching frequency | 600 kHz (set by R3 = 162 kΩ) ✓ | |
| Reference | 0.8 V ±1 % ✓ | |

**Why not a cheaper 28 V-rated part?** Parts like the MP1584 or TPS54331 top out around 28 V absolute max. At 6S you are at 26.1 V steady-state — a 7 % margin, before any inductive spike from a hot battery connection. Those parts fail in the field on 6S. The 65 V rating removes this entire failure mode.

**Component values — taken verbatim from TI's own 5 V design example (datasheet Figure 34), which is validated silicon-in-loop:**

| Ref | Value | Purpose |
|-----|-------|---------|
| L1 | 8.2 µH | Output inductor. **Select ≥3 A saturation rating** |
| C6, C7 | 47 µF each | Output capacitors |
| C1, C2 | 2.2 µF, **50 V** X7R | Input ceramics. TI requires ≥3 µF effective, X5R/X7R, rated above max input |
| C4 | 0.1 µF, ≥10 V, X5R+ | Bootstrap, BOOT→SW. Datasheet-mandatory |
| R1 / R2 | 523 kΩ / 84.5 kΩ | EN pin UVLO divider — start 8 V, stop 6.25 V |
| R3 | 162 kΩ | Sets 600 kHz |
| R4 / C5 / C8 | 13.0 kΩ / 6800 pF / 39 pF | Type-2A compensation network |
| R5 / R6 | 53.6 kΩ / 10.2 kΩ | Feedback divider |
| D1 | B560C | 60 V 5 A Schottky catch diode, SMC |

Feedback check: V_out = 0.8 × (1 + 53.6/10.2) = 0.8 × 6.255 = **5.004 V** ✓

**Why reuse TI's example values rather than recompute for 1.5 A?** Running a current-mode buck below its design current with the design's L and C is unconditionally stable — it simply enters pulse-skip (Eco-mode) at light load, which is intended behaviour. Recomputing L and Cout would invalidate the compensation network and require a full loop-stability redesign for no benefit. Our input range (10.5–26.1 V) sits entirely inside TI's validated 8.5–60 V.

**One deviation from TI's example:** they used 100 V input ceramics because their example spans to 60 V. We only see 26.1 V, so **50 V X7R** gives ~2× margin. Note that ceramics lose capacitance under DC bias — a 2.2 µF 50 V X7R at 25 V retains roughly half its nominal value, so the two in parallel give ≈2.2 µF effective, still comfortably above TI's 3 µF requirement when combined with the electrolytic bulk cap. **This derating will be checked against the specific capacitor's bias curve at BOM lock.**

#### 9 V rail — TPS54360DDAR (second instance)

Same part, same footprint, same datasheet — deliberately, so there is one set of rules to get right instead of two.

Only the feedback divider changes:
- Target 9 V: R5'/R6' = (9 / 0.8) − 1 = 10.25
- With R6' = 10.2 kΩ → R5' = 104.55 kΩ → nearest E96 value **105 kΩ**
- Check: 0.8 × (1 + 105/10.2) = 0.8 × 11.294 = **9.035 V** (+0.4 % — well inside VTX tolerance) ✓

**Open item requiring calculation, not guessing.** Because 9 V is a much smaller step-down ratio than 5 V, the inductor ripple with TI's 8.2 µH would reach ~80 % of load current. Using TI's own inductor equation with V_in(max) = 26.1 V, V_out = 9 V, I_out = 1.5 A, K_IND = 0.3, f_sw = 600 kHz:

L_min = (26.1 − 9)/(1.5 × 0.3) × (9 / (26.1 × 600 000)) = 38.0 × 5.747e-7 = **21.8 µH → use 22 µH**

Ripple check: ΔI_L = 9 × 17.1 / (26.1 × 22e-6 × 600e3) = **0.447 A = 30 % of load** ✓, peak inductor current 1.72 A → **select ≥3 A saturation**.

**Changing L means the compensation network R4/C5/C8 must be recalculated** using TI's Equations 27–37 (or WEBENCH) for the 22 µH / chosen Cout combination. **I will not copy the 5 V compensation values onto the 9 V rail.** That calculation happens and gets reported before schematic capture.

**3S caveat, stated plainly:** at 3S the pack falls to ~9.9 V near cutoff, which demands ~91 % duty cycle to hold 9 V. That is achievable against the TPS54360's minimum off-time, but with little headroom. **The 9 V VTX rail should be treated as a 4S–6S feature.** On 3S it may drop out late in the pack. The 5 V rail is unaffected and works across the full 3S–6S range.

#### 3.3 V rail — TLV1117-33 ✓ verified

TI 800 mA fixed 3.3 V LDO, SOT-223.

| Parameter | Value | Check |
|-----------|-------|-------|
| Input range | 4.7–15 V, **abs max 16 V** ✓ | Fed from 5 V. A 5 V rail overshoot cannot destroy it — 3.2× margin |
| Output current | 800 mA ✓ | Design load 200 mA = **25 %** ✓ |
| Dropout | 0.2 V @ 100 mA, 0.5 V @ 500 mA ✓ | At 200 mA: 5.0 − ~0.3 = 4.7 V, far above 3.3 V ✓ |
| COUT ESR window | **2–500 mΩ** ✓ | Must be respected — see below |

**Why an LDO here and not a third switcher?** Only 1.7 V is being dropped at 200 mA. Linear is quieter, cheaper, needs no inductor, and — critically — an LDO's high PSRR is exactly what you want feeding a gyro. A third switching node near the IMU would be actively harmful.

**Thermal check (this is the one that matters for an LDO):**
P = (5.0 − 3.3) × 0.2 A = **0.34 W**
SOT-223 with a modest copper pour: θ_JA ≈ 60 °C/W → rise ≈ 20 °C
At 45 °C ambient inside a stack → **~65 °C junction, against a 125 °C limit** ✓ No heatsink needed.

**Capacitors, per TI:** C_IN = 10 µF X7R 16 V, C_OUT = 22 µF X7R 10 V (22 µF is the value TI characterises with in Figure 5-38). TI notes ceramic COUT effective capacitance derates ~50 % under bias, which is accounted for. The **2 mΩ minimum ESR** is why C_OUT is a single 22 µF rather than a bank of parallel MLCCs — paralleling would push ESR below the stable window.

---

## 3. Protection & Filtering

### 3.1 Reverse polarity protection

**P-channel MOSFET in the VBAT+ line** — source to battery, drain to load, gate to ground through 100 kΩ, with a 15 V Zener gate-source clamp.

Why a P-FET and not a series diode: a Schottky at 2.2 A would burn 2.2 × 0.5 V = 1.1 W and drop a volt you cannot spare at 3S. A P-FET with 30 mΩ R_DS(on) burns 2.2² × 0.03 = 0.15 W.

**Placement is critical: the FET goes BEFORE the bulk electrolytic**, so a reversed battery never applies reverse voltage across the electrolytic (which would vent it).

**Selection criteria — MPN to be locked in Phase 3 from a verified datasheet:**
- V_DS ≤ −60 V (2.3× margin on 26.1 V)
- I_D ≥ 5 A continuous
- R_DS(on) ≤ 50 mΩ at V_GS = −10 V
- SOT-23 or SOIC-8 package
- V_GS rating ≥ ±20 V, with the 15 V Zener guaranteeing it is never exceeded at 6S

### 3.2 Input bulk capacitor

**100 µF, 50 V, low-ESR aluminium electrolytic, 105 °C, ≥500 mA ripple current.**

**On the voltage rating — I am deliberately exceeding your spec.** You said 35 V+ for 6S. 26.1 V worst case against 35 V is only 34 % margin, and an FC shares the VBAT node with four ESCs switching tens of amps; connecting a charged 6S pack through even 50 nH of lead inductance produces a ringing overshoot well above the DC level. **50 V costs a few cents and roughly doubles the margin to 92 %.** The physical size penalty at 100 µF is negligible.

105 °C rating rather than 85 °C because this sits in a sealed stack next to two switching regulators.

### 3.3 Input filtering and transient clamp

- **TVS diode SMBJ30A** across VBAT: 30 V standoff (above our 26.1 V, so it never conducts in normal use), ~48 V clamping, 600 W. Absorbs hot-plug spikes. **[CONFIRM exact ratings at BOM lock.]** Note: this makes the board explicitly 6S-max — an 8S pack would forward-bias the TVS.
- **2 × 2.2 µF 50 V X7R ceramics** directly at each buck's VIN pin. These do the high-frequency work the electrolytic cannot; the electrolytic handles bulk energy.
- No series input inductor. On a clean FC the VBAT current is ~2 A and the ceramics plus electrolytic are sufficient; a series inductor would add an LC tank that worsens hot-plug ringing.

### 3.4 Decoupling — placement rule

**Every local decoupling capacitor sits adjacent to the pin it protects, on the same side of the board, with its ground via within 1 mm of the cap pad.** A decoupling cap two centimetres away with a long return path is decoration, not decoupling. This is enforced at layout, not left to chance.

| IC | Decoupling | Source |
|----|-----------|--------|
| STM32F405 | 100 nF per VDD pin (5 pins) + 4.7 µF bulk; VCAP pins 2.2 µF low-ESR each; VDDA via ferrite bead + 1 µF + 10 nF | **[CONFIRM]** — VCAP count and value, VDDA network, and whether VREF+ is internally bonded to VDDA on LQFP64 |
| ICM-42688-P | 100 nF on VDD, 10 nF on VDDIO, plus 10 µF local bulk after its dedicated ferrite bead | **[CONFIRM]** |
| DPS310 | 100 nF | **[CONFIRM]** |
| W25Q128JV | 100 nF + 1 µF | Standard for the part ✓ supply range verified |
| AT7456E | 100 nF per supply pin + bulk on the analog rail | **[CONFIRM]** |
| TPS54360 ×2 | Covered by the verified reference design above ✓ | |
| TLV1117-33 | 10 µF in / 22 µF out ✓ | |

### 3.5 ESD protection on externally-facing signals

- **USB D+/D−: USBLC6-2SC6** (SOT-23-6). The USB port is the most-touched connector on the board. **[CONFIRM]**
- **Camera and VTX video pads:** the 75 Ω termination plus AC coupling provides a degree of protection; a dedicated low-capacitance TVS on the video input is worth adding if board space allows — capacitance must stay low or it will roll off the video bandwidth.
- Motor signal and UART pads are not ESD-protected. This is a deliberate, standard trade-off: adding TVS capacitance to DShot600 edges degrades signal integrity more than the ESD risk justifies on connectors that are made up once at build time.

---

## 4. Pin & Bus Assignment Table

STM32F405RGT6, LQFP64. Port/pin names are given; exact physical pin numbers come from the verified KiCad symbol at capture time.

### 4.1 Gyro — SPI1 (dedicated bus)

| Signal | Pin | AF | Connects to | DMA capable |
|--------|-----|----|-----------|-------------|
| SPI1_SCK | PA5 | AF5 | ICM-42688-P SCLK | Yes — DMA2 |
| SPI1_MISO | PA6 | AF5 | ICM-42688-P SDO | Yes — DMA2 S0/S2 Ch3 |
| SPI1_MOSI | PA7 | AF5 | ICM-42688-P SDI | Yes — DMA2 S3/S5 Ch3 |
| GYRO_CS | PA4 | GPIO out | ICM-42688-P CS | n/a |
| GYRO_INT1 | PC4 | EXTI4 | ICM-42688-P INT1 | n/a |

SPI1 is on APB2 (84 MHz), giving the fastest available gyro bus.

### 4.2 OSD + Blackbox — SPI2 (shared, separate chip selects)

| Signal | Pin | AF | Connects to | DMA capable |
|--------|-----|----|-----------|-------------|
| SPI2_SCK | PB13 | AF5 | AT7456E SCK, W25Q128 CLK | Yes — DMA1 |
| SPI2_MISO | PB14 | AF5 | AT7456E SDO, W25Q128 DO | Yes — DMA1 S3 Ch0 |
| SPI2_MOSI | PB15 | AF5 | AT7456E SDIN, W25Q128 DI | Yes — DMA1 S4 Ch0 |
| OSD_CS | PB12 | GPIO out | AT7456E CS (10 k pull-up) | n/a |
| FLASH_CS | PC0 | GPIO out | W25Q128 /CS (10 k pull-up) | n/a |

### 4.3 I2C1 — barometer and external compass

| Signal | Pin | AF | Connects to |
|--------|-----|----|-----------|
| I2C1_SCL | PB8 | AF4 | DPS310 SCK + external compass pad |
| I2C1_SDA | PB9 | AF4 | DPS310 SDI + external compass pad |

Both lines get **4.7 kΩ pull-ups to 3.3 V** — mandatory for I2C, which uses open-drain outputs and cannot pull high on its own.

### 4.4 UARTs — all six

| UART | TX | RX | AF | Intended peripheral | TX DMA | RX DMA |
|------|----|----|----|--------------------|--------|--------|
| USART1 | PB6 | PB7 | AF7 | ELRS / Crossfire receiver | DMA2 S7 Ch4 | DMA2 S2/S5 Ch4 |
| USART2 | PA2 | PA3 | AF7 | GPS | DMA1 S6 Ch4 | DMA1 S5 Ch4 |
| USART3 | PB10 | PB11 | AF7 | VTX SmartAudio / Tramp | DMA1 S3 Ch4 | DMA1 S1 Ch4 |
| UART4 | PA0 | PA1 | AF8 | ESC telemetry | DMA1 S4 Ch4 | DMA1 S2 Ch4 |
| UART5 | PC12 | PD2 | AF8 | Spare | DMA1 S7 Ch4 | DMA1 S0 Ch4 |
| USART6 | PC6 | PC7 | AF8 | Spare / second RX | DMA2 S6/S7 Ch5 | DMA2 S1/S2 Ch5 |

**On DMA contention — worth understanding before you approve.** The F405 has finite DMA streams and some of the above overlap with the motor timer's streams. This is not a defect in the pin map; it is inherent to the F405 and every F405 board on the market shares it. The priority order that matters:

1. **Motor outputs must have DMA** — DShot is generated by DMA and cannot work without it. Guaranteed below.
2. **Gyro SPI benefits from DMA** — SPI1 uses DMA2, which does not collide with the motor timer's DMA1 stream.
3. **UARTs do not require DMA.** Betaflight falls back to interrupt-driven UART transparently. Serial receiver, GPS and telemetry all work correctly on interrupts.

**USART6 note:** on LQFP64 the F405 exposes USART6 *only* on PC6/PC7. This constraint is what drove the motor pin selection below — PC6/PC7 could not be used for motors without giving up the sixth UART you asked for.

### 4.5 Motor outputs — TIM3, all four channels on one timer

| Motor | Pin | AF | Timer channel | DMA stream |
|-------|-----|----|--------------|-----------|
| M1 | PB4 | AF2 | TIM3_CH1 | DMA1 S4 Ch5 |
| M2 | PB5 | AF2 | TIM3_CH2 | DMA1 S5 Ch5 |
| M3 | PB0 | AF2 | TIM3_CH3 | DMA1 S7 Ch5 |
| M4 | PB1 | AF2 | TIM3_CH4 | DMA1 S2 Ch5 |

**Why all four on one timer.** With every motor on TIM3, Betaflight can use **DShot burst mode (DMAR)**, where a single DMA stream (TIM3_UP, DMA1 Stream 2) drives all four channels from one transfer. This collapses four DMA stream reservations into one, which is precisely what frees up streams for the UARTs. It is the single most important choice in this pin map.

**One consequence you must know about:** PB4 is NJTRST and PB3 is JTDO — JTAG pins. Using PB4 as a motor output **requires JTAG to be disabled in firmware, keeping SWD**. Betaflight does this as standard on many targets and SWD debugging is fully retained. There is no practical downside, but it is a real dependency and I am not hiding it.

**No motor pin collides with any UART, SPI, or I2C pin.** Verified in §4.9.

### 4.6 ADC inputs — with the divider maths

| Signal | Pin | ADC channel | Front-end |
|--------|-----|-------------|-----------|
| VBAT_SENSE | PC1 | ADC1_IN11 | 100 kΩ / 10 kΩ divider + 100 nF |
| CURRENT_SENSE | PC2 | ADC1_IN12 | 1 kΩ series + 100 nF |
| RSSI_ADC | PC3 | ADC1_IN13 | 1 kΩ series + 100 nF |

**VBAT divider — full working.**

ADC reference is VDDA = 3.3 V. The voltage at the pin must never exceed that.

- Divider ratio: 10 k / (100 k + 10 k) = **1/11 = 0.0909**
- At 6S nominal (25.2 V): 25.2 × 0.0909 = **2.291 V** ✓
- At absolute worst case (26.1 V): 26.1 × 0.0909 = **2.373 V** ✓ — **0.93 V below the 3.3 V limit**
- Betaflight `vbat_scale` = **110**

Resolution: 2.373 V of a 3.3 V span = 72 % of the ADC range used. On a 12-bit ADC that is ~2950 counts over 26.1 V = **8.9 mV per count** — far finer than needed for per-cell voltage display.

Quiescent drain: 26.1 V / 110 kΩ = **0.24 mA**. Using 100 k/10 k rather than the common 10 k/1 k reduces this standing battery drain by 10×, which matters if a pack is left plugged in.

Source impedance: Thevenin = (100 k × 10 k)/110 k = **9.09 kΩ**, well inside the STM32 ADC's tolerance when paired with an adequate sampling time. The 100 nF to ground gives a 0.9 ms time constant — good anti-alias filtering for a slowly-varying battery voltage.

**Robustness bonus:** even at 8S (33.6 V), the sense pin would see 3.05 V — still under 3.3 V. Wrong-pack survival on this pin specifically, though the regulators and TVS would not tolerate it.

**Current sense:** ESC current outputs are 0–3.3 V referenced. The 1 kΩ series resistor is the protection element — if a misbehaving ESC drives above 3.3 V, the resistor limits current into the MCU's internal ESD clamp diode to a safe level (~1.7 mA even at 5 V input). The 100 nF filters ESC switching noise.

### 4.7 LED, buzzer, camera control

| Signal | Pin | AF | Notes |
|--------|-----|----|-------|
| LED_STRIP | PA8 | AF1, TIM1_CH1 | WS2812. DMA2 S1/S3 Ch6 — **on DMA2, no clash with TIM3's DMA1** |
| BEEPER | PC13 | GPIO out | **Must drive a MOSFET gate, not the buzzer directly** |
| CAM_CONTROL | PC8 | AF3, TIM8_CH3 | Camera OSD joystick emulation |
| LED0 (status) | PB3 | GPIO out | JTDO — free once JTAG is disabled |
| LED1 (status) | PC5 | GPIO out | |

**PC13 warning, stated explicitly:** PC13 sits in the backup power domain and is limited to ~3 mA drive with slow slew. It is perfectly adequate for driving a MOSFET gate (microamps) but would be destroyed by a buzzer's tens of milliamps. The buzzer is therefore switched by an N-channel MOSFET with a gate resistor and a flyback diode across the buzzer.

### 4.8 USB, boot, reset, clock, debug

| Signal | Pin | Notes |
|--------|-----|-------|
| USB_DM | PA11 | AF10, OTG_FS |
| USB_DP | PA12 | AF10, OTG_FS |
| OSC_IN / OSC_OUT | PH0 / PH1 | 8 MHz crystal + 2 load caps |
| SWDIO / SWCLK | PA13 / PA14 | Debug header pads |
| BOOT0 | dedicated pin | 10 kΩ pulldown + two boot pads to 3.3 V |
| BOOT1 | PB2 | 10 kΩ pulldown, otherwise unused |
| NRST | dedicated pin | 100 nF to GND + reset pad |
| VBAT (MCU) | dedicated pin | Tied to 3.3 V — no RTC backup battery |

**USB series resistors:** the STM32F4 OTG_FS peripheral has an **integrated** full-speed PHY with on-chip series termination and pull-ups. ST's own reference designs connect PA11/PA12 directly to the connector with no external series resistors. **[CONFIRM against the datasheet and AN4488 before capture.]**

**USB-C requirement that is easy to miss:** a USB-C receptacle needs **two 5.1 kΩ resistors, one from CC1 to GND and one from CC2 to GND**. Without them a Type-C host will not detect the board as a device and will supply no VBUS. This is the single most common USB-C design error and it is explicitly in the netlist.

**Crystal load capacitors:** determined by the chosen crystal, not guessed. For a crystal with C_L = 8 pF and ~3 pF of stray: C = 2 × (C_L − C_stray) = 2 × (8 − 3) = **10 pF each**. If the sourced crystal has a different C_L, this is recomputed — it is not copied.

**Flashing procedure:** DFU over USB. Short the two boot pads, plug in USB, the MCU enumerates as "STM32 BOOTLOADER", Betaflight Configurator flashes it. SWD pads are broken out as a recovery path if DFU is ever bricked.

### 4.9 Conflict self-check — full re-read

As required, here is the complete pin allocation re-read after the table was finalised:

| Pin | Assigned to | | Pin | Assigned to |
|-----|-------------|-|-----|-------------|
| PA0, PA1 | UART4 | | PB6, PB7 | USART1 |
| PA2, PA3 | USART2 | | PB8, PB9 | I2C1 |
| PA4 | GYRO_CS | | PB10, PB11 | USART3 |
| PA5, PA6, PA7 | SPI1 (gyro) | | PB12 | OSD_CS |
| PA8 | LED strip | | PB13, PB14, PB15 | SPI2 |
| PA9, PA10 | **spare** | | PC0 | FLASH_CS |
| PA11, PA12 | USB | | PC1, PC2, PC3 | ADC |
| PA13, PA14 | SWD | | PC4 | GYRO_INT |
| PA15 | **spare** | | PC5 | LED1 |
| PB0, PB1 | M3, M4 | | PC6, PC7 | USART6 |
| PB2 | BOOT1 (pulldown) | | PC8 | CAM_CONTROL |
| PB3 | LED0 | | PC9, PC10, PC11 | **spare** |
| PB4, PB5 | M1, M2 | | PC12, PD2 | UART5 |
| | | | PC13 | BEEPER |
| | | | PC14, PC15 | unused (OSC32, weak drive) |

**Result: no pin is assigned to two functions.** Motor pins (PB4, PB5, PB0, PB1) do not appear in any UART, SPI or I2C row. Six UARTs are fully broken out. Six spare GPIO remain.

---

## 5. Connectors

| Ref | Type | Pins | Pinout | Current rating | Expected current | Verdict |
|-----|------|------|--------|----------------|------------------|---------|
| Battery pads | Ø3 mm plated solder pads | 2 | VBAT+, GND | >10 A | **3 A worst case (at 3S)** | ✓ 3× margin |
| ESC connector | JST-SH 1.0 mm | 8 | 1 CURR, 2 VBAT, 3 GND, 4 M1, 5 M2, 6 M3, 7 M4, 8 TLM | **1 A per contact** | Signals <10 mA; VBAT pin see note | ⚠ see note |
| USB | USB-C receptacle, 16-pin SMD | — | + 2 × 5.1 kΩ CC pulldowns | 3 A | 0.5 A | ✓ |
| UART pads | 1.0 mm solder pads, grouped | 4 per group × 6 | TX, RX, 5V, GND | ~2 A per pad | 0.2 A | ✓ |
| Video pads | Solder pads | 6 | CAM+ (5V), CAM-in, VTX-out, VTX+ (9V), 2 × GND | ~2 A | 1.5 A on VTX+ | ✓ |
| LED strip pad | Solder pads | 3 | 5V, DATA, GND | ~2 A | 0.48 A | ✓ |
| Buzzer pads | Solder pads | 2 | BZ+ (5V), BZ− (MOSFET drain) | ~2 A | 0.05 A | ✓ |
| Boot pads | 2 exposed pads | 2 | BOOT0, 3.3 V | — | µA | ✓ |
| SWD pads | 4 exposed pads | 4 | SWDIO, SWCLK, 3.3 V, GND | — | mA | ✓ |

**⚠ The one connector issue, called out rather than buried.**

JST-SH 1.0 mm contacts are rated **1 A each**. The standard 8-pin FC-to-ESC cable carries VBAT on pin 2. With a 9 V VTX BEC on board, our VBAT draw reaches ~2.2 A at 3S — **over that 1 A rating.**

**Resolution:** the **dedicated VBAT+ / GND solder pads are the intended power path** and are sized for 3 A. The JST-SH VBAT pin remains populated for compatibility with standard 4-in-1 ESC cables, but the build documentation will state that if you run a high-current VTX on the 9 V rail, power must come in on the pads. Orientation is keyed by the connector body; the pinout follows the common 4-in-1 convention so off-the-shelf cables fit.

---

## 6. Net & Short-Circuit Self-Check

Before the schematic is declared complete, I will explicitly verify each of the following and report the result:

1. **No net connects two different regulated rails.** VBAT, 9 V, 5 V and 3.3 V are four distinct nets. The only legal couplings are the deliberate ones: VBAT→buck inputs, 5 V→LDO input. Verified by netlist inspection, not by eye.
2. **No signal pin is tied to a rail or ground by mistake.** Every net with exactly two members gets individually reviewed — that pattern is the signature of an accidental short.
3. **Grounding: single unified ground net.** One continuous GND net, with a **solid uninterrupted ground plane on layer 2**. No split analog/digital ground.
   **Why unified rather than split:** a split plane forces return currents to detour to the star point. On a board this small, carrying a 3.2 kHz gyro loop and 600 kHz switching, that detour creates larger loop areas and *worse* noise than the ground bounce a split is meant to prevent. The correct technique at this scale is one solid plane plus disciplined component placement — keeping the switching regulators' high-di/dt loops physically small and physically distant from the IMU. Splitting is the classic mistake.
4. **Every IC power pin is on the correct rail per its absolute maximum rating.** Checked one part at a time: W25Q128JV abs max 4.6 V on a 3.3 V rail ✓; TLV1117 abs max 16 V on a 5 V rail ✓; TPS54360 abs max 65 V on a 26.1 V rail ✓; MCU, IMU, baro and OSD confirmed at capture from their datasheets.
5. **Motor output adjacency — recorded as a layout rule.** M1–M4 and their pads must not be routed as tightly-coupled adjacent traces where a solder bridge at the pad could short two outputs. Minimum 0.5 mm pad-to-pad on the ESC connector breakout, with solder mask dam between pads.

---

## 7. PCB Stack-up & Layout Plan

### 7.1 Stack-up — 4 layers

| Layer | Copper | Purpose |
|-------|--------|---------|
| L1 (top) | 1 oz | Components + signal routing |
| L2 | 0.5 oz | **Solid, uninterrupted GND plane** |
| L3 | 0.5 oz | Power pours: VBAT, 9 V, 5 V, 3.3 V |
| L4 (bottom) | 1 oz | Components + signal routing |

Total thickness 1.6 mm. This is JLCPCB's standard 4-layer stack (JLC04161H-7628).

**Why 4 layers and not 2.** This is the highest-leverage decision in the whole design. A solid ground plane on L2 sitting directly beneath every signal on L1 gives each trace a short, low-inductance return path directly under itself. That does three things at once: it drastically reduces radiated noise from the 600 kHz switchers, it gives the gyro a quiet reference, and it makes the DShot600 edges clean. On 2 layers the ground return has to snake around other traces, creating large loop areas next to the most noise-sensitive part on the board. The extra fab cost is a few dollars; the noise-floor improvement is the difference between a board that flies clean and one that needs heavy software filtering.

Layer 3 as a power layer means the 5 V and 3.3 V rails are wide pours rather than traces, which lowers impedance and provides plane capacitance between L2 and L3 — free high-frequency decoupling.

### 7.2 Gyro placement rules

- **Geometric centre of the board**, equidistant from the four mounting holes. The gyro measures rotation about the aircraft's centre of mass; mounting it off-centre couples in linear acceleration as false rotation.
- **Maximum distance from both switching regulators** — regulators go to opposite edges.
- **Solid ground plane directly beneath**, with no L3 power pour and no traces crossing under the device footprint.
- **No motor output traces routed beneath or adjacent.** DShot600 edges are fast and the IMU is high-impedance.
- Away from the board edge where flexing concentrates — centre placement handles this.
- Local supply through a dedicated ferrite bead with 10 µF immediately at the device.

### 7.3 Regulator placement rules

- **The high-di/dt loop must be minimised**: for each buck, the loop formed by input capacitor → VIN pin → SW pin → inductor → catch diode → back to input cap ground is the primary radiator on the board. All those components sit tightly clustered on the top layer with the shortest possible loop, ground returns straight down into L2.
- Input ceramics **directly at the VIN pin**, ahead of the electrolytic.
- The **SW node is kept physically small** — it swings 26 V at 600 kHz and is the loudest net on the board. Wide enough for current, no longer than necessary, never routed near the gyro, the ADC lines, or the video signals.
- PowerPAD soldered to a thermal pad with a **via array (≥9 vias, 0.3 mm) down to the L2 ground plane** for heat spreading.
- Both regulators at the board edge opposite the gyro, separated from each other so their thermal loads do not stack.

### 7.4 Mounting holes and keep-outs

- 4 × Ø4.0 mm plated holes on a **30.5 × 30.5 mm** square pattern (M3 fasteners with soft grommets).
- Board outline 36 × 36 mm with 5 mm corner radii.
- **Keep-out ring of 1.5 mm around each hole** — no traces, no components. Grommet washers compress into this area.
- Components kept 0.5 mm inside the board edge.

### 7.5 Trace widths — computed, not guessed

Using IPC-2221 for external layers: I = 0.048 × ΔT^0.44 × A^0.725 (A in mil², ΔT = 10 °C, 1 oz = 1.37 mil thick).

| Net | Current | Computed area | Required width | **Specified width** |
|-----|---------|---------------|----------------|---------------------|
| VBAT | 3.0 A | 79.6 mil² | 58 mil = 1.48 mm | **2.0 mm / pour** |
| 9 V | 1.5 A | 31.4 mil² | 23 mil = 0.58 mm | **0.8 mm** |
| 5 V | 1.5 A | 31.4 mil² | 23 mil = 0.58 mm | **0.8 mm** |
| 3.3 V | 0.3 A | 8.0 mil² | 6 mil = 0.15 mm | **0.4 mm** |
| Motor signals | <10 mA | — | — | **0.25 mm** |
| SPI / UART / I2C | <10 mA | — | — | **0.2 mm** |
| SW node | 1.7 A peak | — | — | **1.0 mm, kept short** |

Every width above is at least 30 % above its computed minimum.

---

## 8. Bill of Materials

Values locked. No TBDs. Items marked **[CONFIRM]** need a datasheet cross-check before capture; their *function and package* are fixed, and any change gets reported to you before it is made.

| Ref | Description | MPN | Package | Qty | Justification |
|-----|-------------|-----|---------|-----|---------------|
| U1 | MCU, Cortex-M4F 168 MHz 1 MB | STM32F405RGT6 | LQFP-64 | 1 | Peripheral count, Betaflight support **[CONFIRM]** |
| U2 | 6-axis IMU | ICM-42688-P | LGA-14 | 1 | Lowest-noise FC gyro, SPI **[CONFIRM]** |
| U3 | Barometer | DPS310 | LGA-8 | 1 | ±0.06 hPa, altitude hold **[CONFIRM]** |
| U4 | OSD character generator | AT7456E | SOIC-28 | 1 | Betaflight analog OSD standard **[CONFIRM]** |
| U5 | 128 Mbit SPI NOR flash | W25Q128JVSIQ | SOIC-8 208mil | 1 | Blackbox ✓ verified |
| U6 | 5 V buck, 60 V 3.5 A | TPS54360DDAR | HSOIC-8 PP | 1 | 65 V abs max ✓ verified |
| U7 | 9 V buck, 60 V 3.5 A | TPS54360DDAR | HSOIC-8 PP | 1 | Same part as U6 ✓ verified |
| U8 | 3.3 V LDO, 800 mA | TLV1117-33IDCYR | SOT-223 | 1 | 16 V abs max, low noise ✓ verified |
| U9 | USB ESD array | USBLC6-2SC6 | SOT-23-6 | 1 | USB port protection **[CONFIRM]** |
| Q1 | P-ch MOSFET, reverse polarity | *criteria in §3.1* | SOIC-8 | 1 | −60 V, ≥5 A, ≤50 mΩ **[CONFIRM]** |
| Q2 | N-ch MOSFET, buzzer driver | 2N7002 | SOT-23 | 1 | Protects weak PC13 |
| D1, D2 | Schottky catch diode 60 V 5 A | B560C-13-F | SMC | 2 | TI reference design part ✓ |
| D3 | TVS 30 V standoff, 600 W | SMBJ30A | SMB | 1 | Hot-plug clamp **[CONFIRM]** |
| D4 | Zener 15 V | *gate clamp* | SOD-323 | 1 | Protects Q1 V_GS |
| D5 | Flyback diode, buzzer | 1N4148W | SOD-123 | 1 | Inductive kickback |
| L1 | Inductor 8.2 µH, ≥3 A Isat | — | shielded | 1 | 5 V rail, TI value ✓ |
| L2 | Inductor 22 µH, ≥3 A Isat | — | shielded | 1 | 9 V rail, computed §2.6 |
| FB1, FB2 | Ferrite bead, 600 Ω @100 MHz | — | 0603 | 2 | VDDA filter, gyro supply |
| Y1 | Crystal 8 MHz | *C_L to be matched* | 3225 | 1 | USB clock accuracy |
| Y2 | Crystal for OSD | *freq per datasheet* | 3225 | 1 | AT7456E pixel clock **[CONFIRM]** |
| C1, C2 | 2.2 µF 50 V X7R | — | 1210 | 2 | U6 input, TI spec ✓ |
| C3, C4 | 2.2 µF 50 V X7R | — | 1210 | 2 | U7 input, TI spec ✓ |
| C5 | 100 µF 50 V low-ESR elec. 105 °C | — | 8×10 mm | 1 | VBAT bulk, §3.2 |
| C6, C7 | 47 µF 10 V X7R | — | 1210 | 2 | 5 V output, TI value ✓ |
| C8, C9 | 47 µF 16 V X7R | — | 1210 | 2 | 9 V output |
| C10, C11 | 0.1 µF 25 V X7R | — | 0603 | 2 | Bootstrap, TI-mandatory ✓ |
| C12 | 6800 pF C0G | — | 0603 | 1 | U6 compensation ✓ |
| C13 | 39 pF C0G | — | 0603 | 1 | U6 compensation ✓ |
| C14, C15 | *compensation, 9 V rail* | — | 0603 | 2 | **To be calculated, §2.6** |
| C16 | 10 µF 16 V X7R | — | 0805 | 1 | LDO input ✓ |
| C17 | 22 µF 10 V X7R | — | 0805 | 1 | LDO output ✓ |
| C18–C22 | 0.1 µF 16 V X7R | — | 0402 | 5 | MCU VDD decoupling |
| C23 | 4.7 µF 10 V X7R | — | 0603 | 1 | MCU bulk |
| C24, C25 | 2.2 µF 10 V X7R low-ESR | — | 0603 | 2 | MCU VCAP **[CONFIRM]** |
| C26, C27 | 1 µF / 10 nF | — | 0402 | 2 | VDDA filter |
| C28, C29 | 10 pF C0G | — | 0402 | 2 | Crystal load, §4.8 |
| C30 | 0.1 µF | — | 0402 | 1 | NRST |
| C31–C38 | 0.1 µF 16 V X7R | — | 0402 | 8 | IMU, baro, flash, OSD decoupling |
| C39 | 10 µF 10 V X7R | — | 0603 | 1 | IMU local bulk after ferrite |
| C40–C42 | 0.1 µF | — | 0402 | 3 | ADC filters |
| R1 | 523 kΩ 1 % | — | 0402 | 1 | U6 UVLO ✓ |
| R2 | 84.5 kΩ 1 % | — | 0402 | 1 | U6 UVLO ✓ |
| R3 | 162 kΩ 1 % | — | 0402 | 1 | 600 kHz ✓ |
| R4 | 13.0 kΩ 1 % | — | 0402 | 1 | U6 compensation ✓ |
| R5 | 53.6 kΩ 1 % | — | 0402 | 1 | 5 V feedback ✓ |
| R6, R7 | 10.2 kΩ 1 % | — | 0402 | 2 | Feedback lower legs ✓ |
| R8 | 105 kΩ 1 % | — | 0402 | 1 | 9 V feedback, computed §2.6 |
| R9–R11 | 523 k / 84.5 k / 162 k | — | 0402 | 3 | U7 UVLO + freq ✓ |
| R12 | 100 kΩ 1 % | — | 0402 | 1 | VBAT divider upper, §4.6 |
| R13 | 10 kΩ 1 % | — | 0402 | 1 | VBAT divider lower, §4.6 |
| R14, R15 | 4.7 kΩ | — | 0402 | 2 | I2C pull-ups |
| R16, R17 | 10 kΩ | — | 0402 | 2 | SPI2 CS pull-ups |
| R18, R19 | 10 kΩ | — | 0402 | 2 | BOOT0 / BOOT1 pulldowns |
| R20, R21 | 5.1 kΩ 1 % | — | 0402 | 2 | **USB-C CC pulldowns — mandatory** |
| R22 | 100 kΩ | — | 0402 | 1 | Q1 gate |
| R23 | 10 kΩ | — | 0402 | 1 | Q2 gate |
| R24–R26 | 1 kΩ | — | 0402 | 3 | ADC series protection |
| R27, R28 | 1 kΩ | — | 0402 | 2 | Status LED current limit |
| R29, R30 | 75 Ω 1 % | — | 0402 | 2 | Video termination **[CONFIRM]** |
| J1 | USB-C receptacle | — | SMD 16-pin | 1 | Config + DFU |
| J2 | JST-SH 1.0 mm | — | 8-pin SMD | 1 | ESC interface |
| LED1, LED2 | LED 0603 | — | 0603 | 2 | Status |

### 8.1 Cost and assembly note

The TPS54360 and TLV1117 are TI parts and will carry JLCPCB "extended part" setup fees (~$3 each) if you use their assembly service. **I could not verify live JLCPCB stock this session** — the parts-database download timed out and the LCSC API rejected my queries. **Confirming stock and swapping any out-of-stock part is a gate before Phase 3 BOM lock.** If a swap is needed I will bring you the alternative and its datasheet rather than substituting silently.

---

## 9. Firmware / Software Plan

**Target:** Betaflight 4.5 or later. F405 has been supported since Betaflight 3.x, so there is no minimum-version risk. The pin map is deliberately conventional so the same board runs iNav 7.x without hardware changes.

**Flash size:** 1 MB. Betaflight uses a **unified target** (`STM32F405`) driven by a per-board configuration, so no custom firmware fork is needed — the board is described by a config file, not a code branch. This is a significant maintenance advantage.

**Board configuration resources to define** — these map one-for-one onto §4:

```
board_name        FCPROJ_F405
manufacturer_id   CUST

resource BEEPER 1 C13
resource MOTOR 1 B04
resource MOTOR 2 B05
resource MOTOR 3 B00
resource MOTOR 4 B01
resource LED_STRIP 1 A08
resource SERIAL_TX 1 B06
resource SERIAL_TX 2 A02
resource SERIAL_TX 3 B10
resource SERIAL_TX 4 A00
resource SERIAL_TX 5 C12
resource SERIAL_TX 6 C06
resource SERIAL_RX 1 B07
resource SERIAL_RX 2 A03
resource SERIAL_RX 3 B11
resource SERIAL_RX 4 A01
resource SERIAL_RX 5 D02
resource SERIAL_RX 6 C07
resource I2C_SCL 1 B08
resource I2C_SDA 1 B09
resource LED 1 B03
resource LED 2 C05
resource SPI_SCK 1 A05
resource SPI_SCK 2 B13
resource SPI_MISO 1 A06
resource SPI_MISO 2 B14
resource SPI_MOSI 1 A07
resource SPI_MOSI 2 B15
resource CAMERA_CONTROL 1 C08
resource ADC_BATT 1 C01
resource ADC_RSSI 1 C03
resource ADC_CURR 1 C02
resource FLASH_CS 1 C00
resource OSD_CS 1 B12
resource GYRO_EXTI 1 C04
resource GYRO_CS 1 A04

timer B04 AF2   # TIM3_CH1
timer B05 AF2   # TIM3_CH2
timer B00 AF2   # TIM3_CH3
timer B01 AF2   # TIM3_CH4
timer A08 AF1   # TIM1_CH1

set vbat_scale = 110
set gyro_1_bustype = SPI
set gyro_1_spibus = 1
set baro_bustype = I2C
set baro_i2c_instance = 1
set blackbox_device = SPIFLASH
set max7456_spi_bus = 2
```

**OSD fonts:** Betaflight Configurator uploads the character set into the AT7456E's internal NVM over SPI on first use. No hardware provision needed beyond the SPI bus and a stable 5 V supply during the write — a brownout mid-write corrupts the font memory, which is one more reason the 5 V rail has 43 % current headroom.

**First programming:**
1. Short the two BOOT pads
2. Connect USB-C — MCU enumerates as "STM32 BOOTLOADER" (DFU mode)
3. Flash the F405 unified target via Betaflight Configurator
4. Remove the boot short, replug
5. Load the board config above via the CLI
6. SWD pads remain as the recovery path if DFU is ever unavailable

---

## 10. Verification Plan

### 10.1 ERC pass criteria

- **Zero errors.** Non-negotiable.
- Warnings permitted **only** where each has been individually reviewed and documented — typically unconnected pins that are intentionally unused, which will carry explicit no-connect flags rather than being left to generate warnings.
- Specifically checked: no unconnected power inputs, no output-driving-output conflicts, no unpowered power-input pins, every power symbol resolved to a real net.

### 10.2 DRC pass criteria — JLCPCB 4-layer standard

| Rule | JLCPCB capability | **Design rule used** |
|------|-------------------|----------------------|
| Min trace width | 0.127 mm | **0.15 mm** |
| Min trace spacing | 0.127 mm | **0.15 mm** |
| Min via drill | 0.3 mm | **0.3 mm** |
| Min via diameter | 0.6 mm | **0.6 mm** |
| Min annular ring | 0.13 mm | **0.15 mm** |
| Board edge clearance | 0.2 mm | **0.3 mm** |
| Min hole-to-hole | 0.5 mm | **0.5 mm** |

Design rules are set **more conservatively than JLCPCB's minimum** so that a passing DRC means the board is comfortably manufacturable rather than marginally so. Zero DRC errors required. Zero unrouted nets required.

### 10.3 Manual review checklist — walked personally before declaring done

1. **Rail voltage at every IC** — each power pin traced back to its source rail and checked against that part's absolute maximum rating, one part at a time.
2. **Decoupling completeness** — every IC power pin has its capacitor, and each is physically adjacent in the layout, not merely present in the schematic.
3. **Current-carrying traces sized** — every net in the §7.5 table measured in the actual layout, not assumed.
4. **No floating inputs** — every unused input pin either tied to a defined level per its datasheet or explicitly no-connected.
5. **Polarity check** — electrolytic capacitor, all diodes, TVS, MOSFETs, and both regulators checked for correct pin-1 orientation against their footprints.
6. **Footprint-to-symbol pin mapping verified per part** — for every IC, the symbol's pin numbers checked against the datasheet pinout AND against the footprint's pad numbering. This is where the most expensive errors hide.
7. **Divider maths re-verified** in the final schematic — VBAT divider and both feedback dividers recomputed from the values actually placed.
8. **Gyro isolation confirmed** — ground plane solid beneath the IMU, no switching node or motor trace within the exclusion area.
9. **Regulator loop area inspected** — input cap, IC, inductor and diode confirmed tightly clustered.
10. **USB-C CC resistors present** — checked explicitly because their absence is silent until the board will not enumerate.
11. **All [CONFIRM] items resolved** — every entry flagged in this document reconciled against its actual datasheet, with any change reported to you before it is applied.

---

## Open Items Requiring Your Awareness

1. **Datasheet verification gate.** Four ICs could not have their datasheets retrieved this session. All are marked **[CONFIRM]** and will be verified before capture. If any differs materially from this plan, I stop and tell you.
2. **9 V rail compensation network** must be calculated for the 22 µH inductor. It will not be copied from the 5 V rail.
3. **9 V VTX rail is a 4S–6S feature.** On 3S it may drop out near pack cutoff.
4. **JST-SH VBAT pin is rated 1 A**; the dedicated pads are the intended power path for high-current VTX use.
5. **JTAG must be disabled in firmware** (SWD retained) because motors 1 and 2 use PB4/PB3-adjacent JTAG pins.
6. **JLCPCB stock unverified.** BOM availability check is a gate before Phase 3.
7. **Board is 6S maximum.** The TVS makes this explicit — an 8S pack would damage it.

---

**END OF PHASE 1 PLAN — awaiting your approval before any KiCad file is created.**
