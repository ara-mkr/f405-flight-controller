# Continuation prompt: assembled-board quotes (JLCPCB + PCBWay), no purchase

You are picking up a finished KiCad 10 design for a custom STM32F405 flight controller.
The board itself is DONE and verified. Do not touch the routing. Your job is purely
**quoting fully assembled boards** (PCB + all components soldered) at **JLCPCB** and
**PCBWay**, putting each in the cart, and giving the user a clear side-by-side
comparison. **Never purchase, never click checkout / pay / place order.**

Project root: `/Users/akhilraja-amudhan/Documents/Flight Controller Project`

## What exists (do not regenerate unless something is wrong)

`production/` (made by `hardware/gen/production.sh`):
- `fc_f405_gerbers.zip`: 6 copper layers, masks, paste, silk, outline, Excellon drill
- `fc_f405_bom.csv`: 57 lines, columns `Designator,Value,Footprint,MPN,LCSC,Qty`.
  Every line has an LCSC code. Bare wire-pad groups and mounting holes are excluded.
- `fc_f405_cpl.csv`: 105 placements, KiCad CSV `Ref,Val,Package,PosX,PosY,Rot,Side`,
  mm, Y is negative (KiCad convention). **59 top, 46 bottom.**
  Bottom side: C1-C4, C6-C15, C31-C33, C39, C40, C43, D1-D4, FB2, L1, L2, Q1,
  R1-R13, R22, R31, U2 (ICM-42688-P gyro, LGA-14), U6, U7 (TPS54360 bucks).
- `fc_f405_assembly_top.pdf` / `_bottom.pdf`, `fc_f405_schematic.pdf`

Board facts: 37 x 37 mm, 6 layers, 1.6 mm, FR-4 TG150, min track/space 0.127 mm
(5/5 mil), min drill 0.2 mm, ENIG (required: LGA gyro and baro need flat pads),
matte black mask, white silk, 1 oz outer copper. Quantity: 5.
Fine-pitch / hard parts: STM32F405RGT7 LQFP-64 0.5 mm, AT7456E HTSSOP-28 with exposed
pad, ICM-42688-P LGA-14, BMP388 LGA-10, Q1 DFN 3x3 drain pad, 2x TPS54360 SOIC-8-EP.

## The key cost driver: two-sided assembly

Parts are on BOTH sides. Report the price as-is (both sides), and also say what it
would take to make it one-sided (it would need a re-layout, which is not in scope;
just mention it as an option, do not do it).
- JLCPCB "Economic" PCBA is one side only; two-sided needs "Standard" PCBA.
  Check the current rules on the site rather than assuming.
- JLCPCB charges a one-time fee per "Extended" part; count how many BOM lines are
  Extended vs Basic/Preferred and include it.

## Task 1: JLCPCB (jlcpcb.com), boards + assembly, add to cart

1. PCB quote: upload `production/fc_f405_gerbers.zip`, set 6 layers, 37 x 37, qty 5,
   1.6 mm, ENIG, black (matte if offered) mask / white silk, 1 oz outer, min via
   0.2 mm, the stackup JLC offers for 6-layer 1.6 mm (note which one).
2. Turn on PCB Assembly, assemble **both sides**, quantity 5 (or the minimum it allows).
3. BOM / CPL: JLC wants BOM columns `Comment, Designator, Footprint, JLCPCB Part #`
   and CPL columns `Designator, Mid X, Mid Y, Layer, Rotation`. Write converted copies
   to a scratch folder (Python, from the files above): Comment = Value,
   JLCPCB Part # = LCSC; Mid X/Mid Y = PosX/PosY with "mm" (keep KiCad's sign, or
   use `abs(PosY)` if JLC's preview shows the board flipped), Layer = Top/Bottom.
4. On JLC's part-matching page, check every line matched to the intended LCSC part and
   is in stock. On the placement preview, **check rotations**. KiCad vs JLC rotation
   offsets are common on SOT-23, SOT-223, SOIC, QFP, LGA and diodes. Fix any that are
   wrong in the CPL (record what you changed) and re-check visually. Polarised parts
   (diodes, electrolytic C43, LEDs, ICs pin 1) matter most.
5. Add to cart. Screenshot the cart + the price breakdown (PCB, assembly, components,
   extended-part fees, stencil/setup, shipping to USA).

## Task 2: PCBWay (pcbway.com), add assembly to the existing order

The user's PCBWay account already has the bare-board item in the cart:
**W881886AS1F1**, 5 x 6-layer, all specs verified, **$194.00**, "File not upload."
1. Get the PCBWay **PCB Assembly** quote for the same boards: turnkey (PCBWay sources
   the parts), both sides, qty 5, SMD part count 105 (59 top / 46 bottom), unique
   parts 57, fine-pitch / BGA-like: LQFP-64 0.5 mm + 2 LGA, no through-hole parts.
   Upload BOM + CPL (+ Gerbers) where it asks. PCBWay accepts the KiCad files; the
   BOM's MPN column is what they quote against.
2. Either attach it to W881886AS1F1 (if the flow allows) or create the assembled
   order as a new cart item. Do not delete the existing item without asking.
3. Screenshot the cart and the price breakdown. PCBWay assembly quotes are often
   "under review" until an engineer prices the parts. If so, say so and give the
   part of the price that is shown.

## Rules (hard)

- Use the built-in browser pane. **Never type passwords.** If a site needs sign-in,
  ask the user to sign in themselves in the pane, then continue.
- The built-in pane cannot pick local files. When an upload is needed, tell the user
  the exact file path and which button to click, wait for them, then continue.
- Export-control / terms dialogs ("Agree"): the user has OK'd PCBWay's before; for
  JLCPCB, ask once before agreeing.
- Decline non-essential cookies.
- Never checkout / pay / place order / submit for production.
- Do **not** add Claude co-author lines to any git commit, and do not push anything.
  The user publishes their repo themselves.
- Verify every price on screen before reporting it; don't estimate where a real
  number is available.

## Final report to the user (short, plain language)

A table: JLCPCB vs PCBWay with bare-board price, assembly price, component cost,
setup/extended fees, shipping, **total for 5 assembled boards**, lead time.
Then: which one you recommend and why, any parts that were out of stock or
substituted, any rotation fixes you made to the CPL, and the cart screenshots.
Nothing purchased.
