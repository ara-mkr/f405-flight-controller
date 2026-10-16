# Continuation prompt - FC-F405 flight controller: finish, publish, order

You are continuing a long engineering session on a custom STM32F405 flight controller in
KiCad 10. **Work as long as it takes and do not stop until every task below is done and
verified. Be thorough, check your own work, and report honestly.** The user wants it to
"lock in": make engineering calls yourself, then explain them. Do not hand back a board
with shorts, overlaps, dangling tracks or unrouted nets.

Project root: `/Users/akhilraja-amudhan/Documents/Flight Controller Project`
Read `DESIGN_PLAN.md` (the approved spec) and skim `hardware/gen/*.py` before starting.

## The tasks (all required)

1. **Finish the board to perfection.** DRC must report **0 errors, 0 unconnected items**.
   No shorts, clearance, hole, crossing or dangling violations. The only acceptable leftovers
   are a few `silk_overlap` warnings, ideally zero. Courtyard overlaps must be 0
   (`python3.9 gen/check_place.py` may list only the intentional J5 USB-C edge flag).
2. **ERC**: keep 0 errors. The 3 known warnings are intentional (U5 WP/HOLD tied to 3V3,
   BMP388 SDO to GND).
3. **Open the board in the KiCad app** (pcbnew GUI) and show the user: computer-use, or
   `open -a KiCad` on `hardware/fc_f405.kicad_pro`. Screenshot the 2D and 3D views.
4. **Manufacturing outputs** in `production/`: Gerbers + drill (zip), BOM CSV (with LCSC/MPN
   fields), pick-and-place CPL, assembly PDF from the Fab layers, schematic PDF.
   kicad-cli: `pcb export gerbers`, `pcb export drill`, `pcb export pos`, `sch export pdf`,
   `sch export bom`.
5. **Images** in `docs/img/`: hero 3D render top, bottom render, isometric, per-layer copper
   composite, schematic preview. 3D render works:
   `kicad-cli pcb render -o out.png --side top --width 2000 --height 2000 --quality high --background transparent --floor fc_f405.kicad_pcb`
   (use `--rotate "-45,0,45" --perspective` for isometric). Run `python3 gen/stackup.py` first:
   it writes the matte-black / white-silk / ENIG stack-up the renders take colours from.
   Look at every image before using it.
6. **README**: simple but super cool and aesthetic. Centered hero image, badges (KiCad 10,
   6-layer, 37x37 mm, STM32F405, DRC 0, ERC 0, CERN-OHL-P-2.0), top/bottom gallery table,
   specs table, mermaid block diagram, stack-up table, design notes, pinout tables,
   verification table with the *real* final numbers, ordering settings, "how it's built"
   pipeline, honest status ("designed and DRC/ERC-clean, not yet fabricated or flown; needs
   a Betaflight target"), license.
   Pin map: DESIGN_PLAN.md section 4.
   Fab settings: 6 layers, 1.6 mm, ENIG, matte black / white, 5/5 mil, 0.2 mm min hole.
7. **Public GitHub repo** `ara-mkr/f405-flight-controller` (gh is logged in as ara-mkr; the
   name is free).
   - Publish a **clean tree**, not the local history: the local history contains ~43 MB of
     vendor datasheet PDFs, which must not be redistributed.
   - The export script is `scratchpad/export.sh`. If the scratchpad is gone, recreate it: it
     copies `hardware/*.kicad_*`, `fp-lib-table`, `sym-lib-table`, `lib/`, the live
     `hardware/gen` scripts, `DESIGN_PLAN.md` → `docs/`, `docs/9v_compensation_*` and
     `datasheets/README.md` into a fresh folder. Live `gen` scripts: design, layout, build,
     check_place, geom, gnd_vias, route_fr, dsn_patch, maze, cleanup, handroute, finish,
     silk, stackup, rules, run_all.sh, post.sh, mkfp, mksym, mksch, ksym, validate, checkfp,
     mkbom, pcb_header.tpl.
   - Leave out the obsolete old-pipeline scripts: mkpcb, place, route, stitch, planes,
     cluster, board, checkplace, placereport, fillzones, verify.
   - Add `production/`, `docs/img/`, README.md, a CERN-OHL-P-2.0 LICENSE
     (`gh api licenses/cern-ohl-p-2.0 --jq .body`) and a `.gitignore` (KiCad backups,
     `*.dsn`, `*.ses`, `__pycache__`, `*.kicad_prl`, `fp-info-cache`).
   - `git init`, commit, `gh repo create ara-mkr/f405-flight-controller --public --source . --push`.
     Add a description and topics.
   - Also commit the work into the **local** repo on `main`. Do not push local history.
8. **PCBWay cart, no purchase.** Use the built-in browser pane on pcbway.com:
   - PCB Instant Quote → upload the Gerber zip.
   - Settings: 6 layers, 37 × 37 mm, qty 5, FR-4 TG150, 1.6 mm, min track/space 5/5 mil,
     min hole 0.2 mm, matte black mask, white silk, ENIG, 1 oz outer copper.
   - Calculate, then **Add to Cart**.
   - **Never click checkout / pay / place order.** If login is required, ask the user to
     sign in themselves in the browser pane. Never type passwords. Decline non-essential
     cookies.
   - Screenshot the cart and report the price.

## Current state (as of this handoff)

- **Stack-up:** 6 layers, 1.6 mm. F signal+parts / In1 solid GND / In2 signal / In3 signal /
  In4 solid +3V3 plane / B signal+parts. Board 37×37 mm, R5 corners, 4× M3 on 30.5 mm,
  3.5 mm keep-out rings.
- **Placement** is hand-designed in `hardware/gen/layout.py` with zero courtyard overlaps
  (IPC-7351 density-C courtyards via `geom.py`):
  - **Top:** MCU, OSD, flash, baro, USB-C, LDO, all pads.
  - **Bottom:** both TPS54360 bucks. 9V at east, 5V at west as an exact 180° rotation, which
    preserves pin chirality. VIN faces its input cap; SW → diode → inductor in one straight
    line; boot caps across BOOT/SW. Gyro at dead centre, battery input + bulk cap south.
- **Design changes this session** (all justified, mention them in the README / report):
  - 4 → 6 layers (+3V3 plane); PCBWay-grade rules.
  - R32 (AT7456E RESET pull-up) now goes to +5V. Datasheet: RESET abs max AVDD+0.3, VIH 2.1 V.
  - J9 video pads 6 → 5. Pin order is now 1 CAM_IN, 2 +5V, 3 GND, 4 VTX_OUT, 5 +9V.
  - D6 VBUS Schottky moved beside the USB ESD array; J3 BOOT pads moved to top SE.
  - OSD east column re-ordered to match pin order; R29 sits under J9's CAM pad.
  - C42 rot 0 with its GND pad facing VSSA. Schematic regenerated with `gen/mksch.py`;
    ERC still 0 errors.
- **Rules** (`gen/rules.py` + `hardware/fc_f405.kicad_dru`; both are rewritten by
  `rules.apply()` after every SaveBoard, because pcbnew clobbers `.kicad_pro`):
  - Default 0.127 mm / 0.127 mm, via 0.45 / 0.2.
  - HV (VBAT, VBAT_IN, SW_*): 0.6 mm, clearance 0.2.
  - PWR (+5V, +9V, USB_VBUS): 0.6 mm, clearance 0.15.
  - PWR3V3: 0.3 mm. Floors are 0.2 for sense branches.
  - `lib_footprint_mismatch` ignored (deliberate density-C courtyards).
- **Pipeline** (run from `hardware/`):
  `gen/run_all.sh <workdir>` = build → check_place → gnd_vias (plane via per GND/+3V3 pad,
  thermal arrays) → route_fr prep (planes, keep-outs, DSN) → dsn_patch (classes, power
  layers, via padstacks) → freerouting 2.4.1 → route_fr importonly → DRC → cleanup export
  → maze → `gen/post.sh <workdir>`.
  `post.sh` = apply → handroute → 3 cleanup rounds against the real pours → pours → finish
  (chain floods, stitching, EP vias) → silk → stackup → DRC → `drc.rpt`. About 30 min per
  full run; post.sh alone is a few minutes.
- **Tools:**
  - KiCad python: `/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3.9` (no numpy)
  - System `python3` has numpy/scipy (maze.py).
  - Freerouting: `~/.kicad-mcp/freerouting-2.4.1.jar` on `~/.kicad-mcp/jdk25/jdk-25.0.4.1+1/Contents/Home/bin/java -Xmx4g`.
    The native 2.5.0 CLI crashes; don't use it.
  - kicad-cli: `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`.
- **Latest results.** Run 15 had 3 unconnected (SPI2_MOSI, R9 VBAT, BOOT0) + 2 clearance.
  Run 16 had 5 unconnected (USB_VBUS ×3, SPI2_MISO, OSD_CS) + 1 short/2 crossings from the
  R29 snake (fixed in layout since). **Run 17** was launched into
  `scratchpad/b17` (log `scratchpad/run17.log`); check `hardware/drc.rpt` for its result.
  Snapshots `scratchpad/best_b15.kicad_pcb` / `best_b16.kicad_pcb` may still exist.
  **Run 17 finished: every signal net routed; 4 unconnected, all +5V islands at the OSD**:
  - U4 pin 24 (PVDD) alone
  - C37's +5V pad + J9 pin 2
  - pin 21 / C38 / R32 (hand-routed) + the via at (35.6, 18.86)

  There are also 1 tracks_crossing and 2 dangling vias (check whether they're the handroute via/stub).
  Fix idea: tie these three +5V islands together on In2/In3 with a couple of vias. Free
  spots are the east strip x 34.7-36.3, y 15.5-19.9 on top, and the bottom strip
  x 35.1-36.4, y 11.8-18.5 (avoid the In2 +9V trace near x 35.3-36). Or route pin 24 to
  C37's +5V pad directly (they face each other at y 12.8-13.0).
  Freerouting results vary run to run. If a run leaves a handful of failures, re-run
  `post.sh` from that workdir, or add targeted fixes.

## How to close the last connections (proven techniques)

- `gen/maze.py` is the clean-up router:
  - A*, 0.05 mm grid, 4 routing layers, class-aware clearances.
  - Transactional rip-up of Default-class nets (rolls back if any ripped net fails).
  - `plane_shuffle` moves GND/+3V3 plane vias out of the way and re-seats them.
  - `--norip` flag available.
- `gen/handroute.py` holds exact hand routes (OSD pin 21 → C38, R32 +5V → via). It runs in
  post.sh after round 0. Add more there for stubborn short links; always verify with DRC.
- When a short link fails, ASCII-map the local free cells. Example in this session: build
  `maze.Raster(json)` from `cleanup.py export`, print `free(net, w)` / `via_ok(net)` around
  the point. Then fix the **placement**: part orientation (pads facing their pins), column
  order, moving a part to a free strip. Rebuild and rerun. This is what fixed most failures.
- Known-good facts:
  - Bottom side = Y-mirror then rotate.
  - KiCad 10 SWIG: never `fp.Remove()`, never `GetField()`; use `via.GetWidth(pcbnew.F_Cu)`.
  - Footprint/field edits go via text post-processing (`build.fix_fields`).
- Bugs fixed this session (don't reintroduce):
  - stale raster after a failed shuffle (`Rs = SHARED["Rs"]`)
  - keep-out ring checked at the copper edge
  - rip text-deletion keeping the newline
  - numeric coordinate matching for removals
  - stale pairs of ripped nets skipped
  - idempotent prep
- **Hook:** a "fact-forcing gate" hook blocks the first Bash/Write of a session and any
  destructive-looking command. State the requested facts (callers, schema, user's verbatim
  instruction, files touched, rollback), then retry the identical call.

## Final report to the user

Short and honest:
- DRC/ERC numbers (paste the summary)
- what changed vs. the approved plan, and why
- the repo URL
- the PCBWay cart screenshot and price (nothing purchased)
- what's left before flying (bench bring-up, Betaflight target)
