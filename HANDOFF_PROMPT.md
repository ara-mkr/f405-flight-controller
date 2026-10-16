# Flight Controller — Phase 3 continuation (routing)

You are an experienced flight controller hardware design engineer with deep expertise in
multirotor avionics, high-speed digital design, power electronics, and KiCad. You have
KiCad MCP tools available.

Work directory: `/Users/akhilraja-amudhan/Documents/Flight Controller Project`

## Read first

1. `DESIGN_PLAN.md` — the approved Phase 1 spec. Still authoritative.
2. `datasheets/README.md` — every datasheet is now retrieved and verified.
3. `git log` — 11 commits. `e1304e8` is the current head.

**Do not re-plan, re-verify datasheets, or re-check JLCPCB stock. Steps 0–6 are done.**

## Status

| Step | State |
|---|---|
| 0 Setup, 1 Datasheets, 2 Compensation, 3 Stock | ✅ complete |
| 4 Schematic | ✅ 125 symbols, 90 nets |
| 5 ERC | ✅ **zero errors**, 3 reviewed warnings |
| 6 Footprints | ✅ all 117 parts pass symbol-pin ↔ footprint-pad check |
| 7 Layout | ⚠️ **placed 118/118, not routed** |
| 8 DRC | ❌ 190 unconnected + 28 errors |
| 9 Checklist | 6 of 11 items verifiable (`hardware/gen/verify.py`) |
| 10 BOM | ✅ `docs/BOM.csv` |

## Your task

**Route the board and drive DRC to zero errors and zero unrouted nets.** Then complete
Step 9 (the 11-point checklist in DESIGN_PLAN §10.3) and Step 10 (final summary + BOM).

## The one thing blocking routing

At 0.5 mm LQFP-64 pitch the gap between pads is 0.20 mm. A 0.2 mm trace with 0.2 mm
clearance needs 0.60 mm. **Nothing can route between the MCU's pads** — every one of its
~50 signal pins must escape radially to its own dog-bone via.

That needs roughly a 1.4 mm clear ring around U1. `place.FANOUT_HALO` implements it but is
currently set to `0.0` because the greedy packer cannot close with it:

```
LQFP halo 1.4 -> 3 parts unplaced
LQFP halo 1.2 -> 1 part unplaced      <- closest
LQFP halo 0.0 -> 118/118 (current committed state)
```

Only 15 of ~50 fanout vias currently fit. **Fixing this is the whole job.** Options, best first:

1. **Improve the packer** in `hardware/gen/place.py`. It is greedy, axis-aligned,
   bounding-box only, and its results are non-monotonic in the halo (0.6 closes, 0.5 does
   not) — a clear sign it is leaving usable space on the table. Adding 90°/180° rotation
   candidates, a finer spiral, or a simple backtrack/anneal pass should recover the ~120 mm²
   the halo needs. Density is only 70.3 % two-sided.
2. **Hand-place the U1 neighbourhood in Pcbnew**, fan out all 64 pins, then autoroute the
   rest. Fastest path to a fabricable board.
3. **38 × 38 mm** — drops density to 71.0 % *with* the halo. The user already accepted
   growing the board once; ask before doing it again.

## Build pipeline — everything is generated

```bash
cd "hardware/gen"
python3 place.py            # solve placement, report violations
python3 mkpcb.py            # regenerate the whole .kicad_pcb from design.py
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3.9 fillzones.py
cd .. && /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc --output drc.rpt fc_f405.kicad_pcb
```

| File | Role |
|---|---|
| `design.py` | netlist + BOM — source of truth for every component and value |
| `board.py` | board geometry and floorplan hints |
| `place.py` | placement solver, courtyard parsing, `FANOUT_HALO` |
| `cluster.py` | placement order + which anchor each part must stay near |
| `stitch.py` | plane-stitching vias, thermal vias, dog-bone fanout |
| `mkpcb.py` | emits the complete `.kicad_pcb` |
| `fillzones.py` | zone fill via KiCad's own Python |
| `verify.py` | §10.3 checklist by measurement |
| `mkbom.py` | ordering BOM |

`mksch.py` + `mksym.py` + `mkfp.py` regenerate the schematic, symbol library and footprints.

## Traps already paid for — do not rediscover these

- **The KiCad MCP clobbers the board file** with its stale in-memory copy on any write
  (`refill_zones`, `sync_schematic_to_board`). Use `fillzones.py` as the only writer after
  `mkpcb.py`. MCP *read* calls are fine.
- **pcbnew stores pad positions unrotated** but takes the pad *shape* angle from each pad's
  own `(at x y angle)`. Omit it and rotated fine-pitch parts silently self-short.
- **Courtyard parsing must use balanced brackets** — a non-greedy regex truncates multi-line
  `fp_poly`/`fp_arc` and under-reports extents, letting the packer overlap parts.
- **`_ThermalVias` footprint variants use 0.2 mm drills**, under JLCPCB's 0.3 mm minimum,
  and punch into parts on the other side. Plain EP variants + `stitch.py` vias instead.
- **DSN surgery for freerouting** — all three of these independently stop it routing:
  - dropping inner layers leaves dangling layer names in the via padstack → no vias at all
  - `(net GND` as a match opener also strips the inline `(net GND)` attribute from wires →
    3760 "net not found" warnings. Remove GND *wiring* first, then match `(net GND\n`.
  - plane definitions on unroutable layers give power pads no reachable target
- **freerouting 2.1.0 throws NullPointerExceptions** in its maze router and gets *worse*
  pass over pass on this board. **v2.3.0 is available and worth trying first:**
  `curl -L -o ~/.kicad-mcp/freerouting.jar https://github.com/freerouting/freerouting/releases/download/v2.3.0/freerouting-2.3.0.jar`
  Cap the heap (`-Xmx3g`) — it ate 20+ GB and nearly exhausted swap.

## Environment

- WebSearch/WebFetch are broken. Use `curl`. Datasheets are already in `datasheets/raw/`.
- A **fact-forcing gate** requires stating the request and what a command verifies before
  the first Bash call of a session, and before creating a new file.
- Java 21 (Temurin) and freerouting 2.1.0 are installed and detected (`check_freerouting`
  reports `ready: true`).
- `pdftotext`/`pdftoppm` at `/opt/homebrew/bin/`.

## Decisions already approved — do not reopen

- DPS310 → **BMP388** (DPS310 not carried by JLCPCB)
- STM32F405RGT6 → **RGT7** (only 29 units of the T6; identical die, wider temp grade)
- AT7456E is **HTSSOP-28-EP**, not SOIC-28, plus the datasheet-mandated video coupling
  network, SAG correction and RESET pull-up the plan omitted
- USB VBUS → **Schottky (B5819W) → +5 V rail** (plan never connected VBUS)
- MCU decoupling is **4 caps, not 5** — LQFP64 has four VDD pins
- 9 V compensation **R31/C14/C15 = 11.5 kΩ / 33 nF / 47 pF**, computed, 85° phase margin
- Board is **37 × 37 mm with 5 mm corner radii** — at this size the 30.5 mm pattern clears
  the radius, so the earlier 36×36/R4.0 deviation is withdrawn and the outline now matches
  DESIGN_PLAN §7.4 as originally written

## Rules

- Never invent a component value. Cite the datasheet you read it from.
- If you find an error in the approved plan, stop and report before deviating.
- No floating inputs.
- Report honestly. Show DRC output. If you skip something, say so.
