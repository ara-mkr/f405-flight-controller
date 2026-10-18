# F405 Flight Controller

I worked on this flight controller as a fun and challenging personal project. I plan to build a drone with it in the future.

<img src="docs/img/hero_top.png" width="560" alt="Top view of the flight controller design">

## The design

I used KiCad and Python scripts to put together the schematic and board layout, check the connections, and export the files for manufacturing.

The main controller reads the motion sensors and sends signals to the motor controllers. The board also handles power for its electronics and has connections for a receiver, GPS, and camera.

It hasn't been manufactured, assembled, or flown yet, so there's still building and testing ahead.

<table>
<tr>
<td width="50%"><img src="docs/img/iso.png" alt="Angled render of the board"><br>Angled view</td>
<td width="50%"><img src="docs/img/bottom.png" alt="Bottom render of the board"><br>Bottom view</td>
</tr>
<tr>
<td><img src="docs/img/copper.png" alt="The board's copper layers"><br>Copper layers</td>
<td><img src="docs/img/schematic.png" alt="Circuit schematic"><br><a href="production/fc_f405_schematic.pdf">Schematic</a></td>
</tr>
</table>

The design files are in [hardware/](hardware/), and the manufacturing files are in [production/](production/).

Licensed under [CERN-OHL-P-2.0](LICENSE).
