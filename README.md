# F405 Flight Controller

This is a flight controller I designed as a side project. It was fun and pretty challenging, and I'm planning to build a drone with it at some point!

<img src="docs/img/hero_top.png" width="560" alt="Top view of the flight controller design">

## The design

I did the schematic and layout in KiCad, and wrote some Python scripts to check the connections and spit out the manufacturing files.

It's built around an STM32F405. It reads the gyro and barometer and sends signals out to the ESCs. It also has its own power regulators and plugs for a receiver, GPS, and camera.

I haven't gotten it made or flown yet, so there's still a lot of building and testing to do. If you want to order one, here's [how I'd do it](HOW_TO_ORDER.md).

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

Design files are in [hardware/](hardware/) and the manufacturing stuff is in [production/](production/).

Licensed under [CERN-OHL-P-2.0](LICENSE).
