"""Cross-check every pin reference in design.py against the real symbol pin lists,
and against the STM32 LQFP64 pinout transcribed from ST DocID022152 Rev 4 Fig. 12."""
import sys, collections
sys.path.insert(0, '.')
import design, mksch

err = []
netpins = collections.defaultdict(list)
refs = collections.Counter()

for c in design.COMPONENTS:
    refs[c["ref"]] += 1
    have = set(mksch.sympins(c["lib"]))
    want = set(c["pins"])
    for p in want - have:
        err.append(f"{c['ref']} ({c['lib']}): pin '{p}' does not exist on the symbol")
    for p in have - want:
        pass  # unlisted pins become explicit no-connects; reported separately
    for p, n in c["pins"].items():
        if n and n != "!NC":
            netpins[n].append(f"{c['ref']}.{p}")

for r, n in refs.items():
    if n > 1: err.append(f"duplicate reference designator: {r} used {n} times")

# --- STM32F405RGT6/7 LQFP64, ST DocID022152 Rev 4, Figure 12 (p.39) ---
LQFP64 = {1:"VBAT",2:"PC13",3:"PC14",4:"PC15",5:"PH0",6:"PH1",7:"NRST",8:"PC0",9:"PC1",
 10:"PC2",11:"PC3",12:"VSSA",13:"VDDA",14:"PA0",15:"PA1",16:"PA2",17:"PA3",18:"VSS",
 19:"VDD",20:"PA4",21:"PA5",22:"PA6",23:"PA7",24:"PC4",25:"PC5",26:"PB0",27:"PB1",
 28:"PB2",29:"PB10",30:"PB11",31:"VCAP_1",32:"VDD",33:"PB12",34:"PB13",35:"PB14",
 36:"PB15",37:"PC6",38:"PC7",39:"PC8",40:"PC9",41:"PA8",42:"PA9",43:"PA10",44:"PA11",
 45:"PA12",46:"PA13",47:"VCAP_2",48:"VDD",49:"PA14",50:"PA15",51:"PC10",52:"PC11",
 53:"PC12",54:"PD2",55:"PB3",56:"PB4",57:"PB5",58:"PB6",59:"PB7",60:"BOOT0",61:"PB8",
 62:"PB9",63:"VSS",64:"VDD"}
# What DESIGN_PLAN sec 4 says each port pin must carry
PLAN = {"PA0":"UART4_TX","PA1":"UART4_RX","PA2":"UART2_TX","PA3":"UART2_RX",
 "PA4":"GYRO_CS","PA5":"SPI1_SCK","PA6":"SPI1_MISO","PA7":"SPI1_MOSI","PA8":"LED_STRIP",
 "PA11":"USB_DM","PA12":"USB_DP","PA13":"SWDIO","PA14":"SWCLK",
 "PB0":"MOTOR3","PB1":"MOTOR4","PB2":"BOOT1","PB3":"LED0","PB4":"MOTOR1","PB5":"MOTOR2",
 "PB6":"UART1_TX","PB7":"UART1_RX","PB8":"I2C1_SCL","PB9":"I2C1_SDA","PB10":"UART3_TX",
 "PB11":"UART3_RX","PB12":"OSD_CS","PB13":"SPI2_SCK","PB14":"SPI2_MISO","PB15":"SPI2_MOSI",
 "PC0":"FLASH_CS","PC1":"VBAT_SENSE","PC2":"CURR_SENSE","PC3":"RSSI_ADC","PC4":"GYRO_INT",
 "PC5":"LED1","PC6":"UART6_TX","PC7":"UART6_RX","PC8":"CAM_CTRL","PC12":"UART5_TX",
 "PD2":"UART5_RX","PC13":"BEEPER_GATE"}
mcu = next(c for c in design.COMPONENTS if c["ref"] == "U1")
for num, port in LQFP64.items():
    got = mcu["pins"].get(str(num))
    if port in PLAN:
        if got != PLAN[port]:
            err.append(f"U1 pin {num} ({port}): plan wants {PLAN[port]!r}, schematic has {got!r}")
    if got is None:
        err.append(f"U1 pin {num} ({port}) is missing from the pin map entirely")

print("=" * 70)
if err:
    print("VALIDATION FAILED - %d problem(s):" % len(err))
    for e in err: print("  *", e)
else:
    print("VALIDATION PASSED")
print("=" * 70)
print(f"{len(design.COMPONENTS)} components, {len(netpins)} nets")
single = sorted(n for n, p in netpins.items() if len(p) < 2)
if single:
    print(f"\nNets with fewer than 2 connections ({len(single)}):")
    for n in single: print(f"  {n}: {netpins[n]}")

# ---- geometric check: no two different nets may share a label/stub coordinate ----
import collections as _c
occupied = _c.defaultdict(set)
for c in design.COMPONENTS:
    pins = mksch.sympins(c["lib"])
    cx, cy = mksch.snap(c["at"])
    for pnum, pd in pins.items():
        net = c["pins"].get(pnum)
        if not net or net == "!NC": continue
        sx, sy = round(cx + pd["x"], 3), round(cy - pd["y"], 3)
        dx, dy = {0:(-1,0),180:(1,0),90:(0,1),270:(0,-1)}[int(pd["angle"]) % 360]
        for t in (0.0, 1.0):   # both the pin end and the label end
            px = round(sx + dx*mksch.STUB*t, 2); py = round(sy + dy*mksch.STUB*t, 2)
            occupied[(px, py)].add((net, f"{c['ref']}.{pnum}"))
clash = {k: v for k, v in occupied.items() if len({n for n, _ in v}) > 1}
print("\nGeometric collisions between different nets: %d" % len(clash))
for k, v in sorted(clash.items())[:15]:
    print(f"  at {k}: " + ", ".join(f"{n} ({r})" for n, r in sorted(v)))
offgrid = [(k, v) for k, v in occupied.items()
           if abs(k[0]/1.27 - round(k[0]/1.27)) > 1e-6 or abs(k[1]/1.27 - round(k[1]/1.27)) > 1e-6]
print("Off-grid endpoints: %d" % len(offgrid))
for k, v in offgrid[:5]: print("   ", k, list(v)[:1])
