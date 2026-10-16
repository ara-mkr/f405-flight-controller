"""Electrical grouping: each part names the anchor it must stay close to.

The placer puts anchors down first (biggest first, from the floorplan hints) and
then spiral-searches each remaining part around its anchor's ACTUAL position, so
decoupling ends up adjacent to the pin it protects (DESIGN_PLAN sec 3.4) and the
regulator loop components stay clustered (sec 7.3).
"""
# order matters: these go down first, in this order
ANCHOR_ORDER = [
    # U2/U1 are position-locked (gyro dead centre, MCU under it). Y1 and Y2 come
    # immediately after the part they clock: a crystal is position-critical and
    # placing them last left the 27 MHz Y2 with nothing inside 26 mm of the OSD.
    # The rest are ordered biggest-first - the large parts have to claim their
    # ground before the passives fill in.
    "U2", "U1", "Y1",
    "J5", "C43", "U4", "Y2", "J6", "U6", "U7", "D1", "D2", "L1", "L2", "U8",
    "J1", "U5", "J9", "J15", "J2", "J4", "J10", "J11", "J12", "J13", "J14",
    "Q1", "D3", "J8", "J3", "J7",
    "U3", "U9"]

# Clusters are filled in THIS order - electrical criticality, not anchor order
# and not part size. The 5 V/9 V input ceramics carry the highest di/dt on the
# board and the gyro and MCU bypasses set the noise floor, so they claim the
# copper next to their pin before anything else is allowed to. Filling in
# ANCHOR_ORDER instead let the OSD's bypass caps take the space beside the 5 V
# regulator's VIN pin and pushed C1/C2 15 mm away (DESIGN_PLAN sec 7.3, 3.4).
CLUSTER_ORDER = [
    "U6", "U7",               # buck switching loops
    "U2",                     # gyro bypass and its ferrite
    "U1",                     # MCU decoupling
    "L1", "L2",               # buck output filtering
    "C43", "Q1",              # battery entry
    "U8", "Y1", "U3",         # LDO, crystal, barometer
    "U4", "U5", "Y2",         # OSD, flash, OSD crystal
    "J5", "J6", "J7", "J15",  # connector-side passives
    "LED1", "LED2", "Q2",
]

CLUSTER = {
  # 5 V buck - input ceramics hard at VIN, output caps and the feedback/comp
  # network can sit a little further out (they are not in the high-di/dt loop)
  "C1":"U6", "C2":"U6", "C10":"U6", "C12":"U6", "C13":"U6",
  "R1":"U6", "R2":"U6", "R3":"U6", "R4":"U6", "R5":"U6", "R6":"U6",
  "C6":"L1", "C7":"L1",
  # 9 V buck
  "C3":"U7", "C4":"U7", "C11":"U7", "C14":"U7", "C15":"U7",
  "R9":"U7", "R10":"U7", "R11":"U7", "R7":"U7", "R8":"U7", "R31":"U7",
  "C8":"L2", "C9":"L2",
  # battery entry / protection
  "D3":"C43", "D4":"Q1", "R22":"Q1", "R12":"C43", "R13":"C43", "C40":"C43",
  # 3.3 V LDO
  "C16":"U8", "C17":"U8", "D6":"U8",
  # gyro - ferrite then bulk then the two datasheet bypasses, all hard at the part
  "FB2":"U2", "C39":"U2", "C31":"U2", "C32":"U2", "C33":"U2",
  # MCU
  "C18":"U1","C19":"U1","C20":"U1","C21":"U1","C23":"U1","C24":"U1","C25":"U1",
  "C26":"U1","C27":"U1","C30":"U1","C44":"U1","FB1":"U1",
  "R18":"U1","R19":"U1","C28":"Y1","C29":"Y1",
  # barometer
  "C34":"U3", "C35":"U3", "R14":"U3", "R15":"U3",
  # OSD
  "C36":"U4","C37":"U4","C38":"U4","R32":"U4",
  "C45":"U4","C46":"U4","C47":"U4","R29":"U4","R30":"U4",
  # flash
  "C48":"U5","C49":"U5","R16":"U5","R17":"U5",
  # USB
  "R20":"J5","R21":"J5",
  # indicators / buzzer
  "R27":"LED1","R28":"LED2","LED1":"U1","LED2":"U1",
  "Q2":"J7","R23":"Q2","D5":"J7",
  "R24":"J6","R25":"J15",
}
