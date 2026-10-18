# How to order the board

pretty easy, you can use PCBWay or JLCPCB, whichever one you like.

1. sign into [PCBWay](https://www.pcbway.com) or [JLCPCB](https://jlcpcb.com)
2. upload this [gerber file](production/fc_f405_gerbers.zip)
3. it should fill in most of the settings by itself, just double check these:
   - 6 layers
   - 37 x 37 mm
   - 1.6 mm thick
   - ENIG surface finish (has to be ENIG, the gyro and baro need flat pads)
   - black solder mask, white silkscreen
   - 1 oz copper
   - min hole 0.2 mm, min track/spacing 5/5 mil
   - quantity 5
4. if you want them to solder the parts on too, turn on assembly and pick **both sides** (theres parts on the top and the bottom)
5. upload the [BOM](production/fc_f405_bom.csv) and the [pick and place file](production/fc_f405_cpl.csv)
   - if it asks which column is which, just match them up
   - JLC uses the LCSC column for part numbers, PCBWay uses the MPN column
6. look over the parts it matched and make sure everything is in stock
7. check the placement preview, rotations get messed up sometimes on the chips and diodes. make sure pin 1 and the polarity marks line up
8. add to cart and check out

if you get stuck these help:
- [schematic](production/fc_f405_schematic.pdf)
- [top assembly drawing](production/fc_f405_assembly_top.pdf)
- [bottom assembly drawing](production/fc_f405_assembly_bottom.pdf)

heads up, the 2 sided assembly is what makes it pricey. JLC's cheap "Economic" assembly only does one side so you need "Standard". JLC also charges a small fee for each "Extended" part. PCBWay might say the quote is "under review" for a bit while they price out the parts, thats normal.
