import math, cmath

# ---- Device constants, TPS54360 SLVSBB4G Rev G ----
VREF  = 0.8       # V,  sec 8.2.2.9 / Eq 48
GMPS  = 12.0      # A/V power-stage transconductance, sec 8.2.2.11
GMEA  = 350e-6    # A/V error-amp transconductance,   sec 8.2.2.11
FSW   = 600e3     # Hz, set by R3 = 162 k
L     = 22e-6     # H,  9 V inductor, DESIGN_PLAN sec 2.6
VOUT  = 9.0
IOUT  = 1.5       # A, 9 V rail design load, DESIGN_PLAN sec 2.6

def design(cout, resr):
    fp_mod = IOUT / (2*math.pi*VOUT*cout)          # Eq 44
    fz_mod = 1.0 / (2*math.pi*resr*cout)           # Eq 45
    fco_a  = math.sqrt(fp_mod*fz_mod)              # Eq 46
    fco_b  = math.sqrt(fp_mod*FSW/2.0)             # Eq 47
    fco    = min(fco_a, fco_b)
    R4 = (2*math.pi*fco*cout/GMPS)*(VOUT/(VREF*GMEA))   # Eq 48
    C5 = 1.0/(2*math.pi*R4*fp_mod)                      # Eq 49
    C8a = cout*resr/R4                                  # Eq 50
    C8b = 1.0/(R4*FSW*math.pi)                          # Eq 51
    C8 = max(C8a, C8b)
    return dict(fp_mod=fp_mod, fz_mod=fz_mod, fco_a=fco_a, fco_b=fco_b,
                fco=fco, R4=R4, C5=C5, C8a=C8a, C8b=C8b, C8=C8)

def loop(f, cout, resr, R4, C5, C8, iout=IOUT):
    s = 2j*math.pi*f
    Rload = VOUT/iout
    # modulator: current-mode, single pole + ESR zero
    Gmod = GMPS*Rload*(1+s*resr*cout)/(1+s*Rload*cout)
    # type-2A network impedance
    Z = (R4 + 1/(s*C5)) * (1/(s*C8)) / ((R4 + 1/(s*C5)) + 1/(s*C8))
    beta = VREF/VOUT
    return Gmod*GMEA*Z*beta

def margins(cout, resr, R4, C5, C8, iout=IOUT):
    lo, hi = 1.0, 1e6
    for _ in range(200):
        mid = math.sqrt(lo*hi)
        if abs(loop(mid, cout, resr, R4, C5, C8, iout)) > 1: lo = mid
        else: hi = mid
    fx = math.sqrt(lo*hi)
    ph = math.degrees(cmath.phase(loop(fx, cout, resr, R4, C5, C8, iout)))
    return fx, 180+ph   # loop() has no inverting sign; PM = 180 + arg

print("="*78)
print("TI SLVSBB4G Rev G method, Eq 44-51, applied to the 9 V rail")
print("VOUT=9.0 V  IOUT=1.5 A  L=22 uH  fsw=600 kHz  gmps=12 A/V  gmea=350 uA/V")
print("="*78)
for cout,resr,lbl in [(58.3e-6,2.5e-3,"58.3 uF  (TI's own derated 2x47uF figure)")]:
    d = design(cout,resr)
    print(f"\n-- COUT = {lbl}, RESR = {resr*1e3:.1f} mOhm --")
    print(f"  Eq44 fp(mod) = {d['fp_mod']:8.1f} Hz")
    print(f"  Eq45 fz(mod) = {d['fz_mod']/1e3:8.1f} kHz")
    print(f"  Eq46 fco     = {d['fco_a']/1e3:8.2f} kHz   (geometric mean of pole & ESR zero)")
    print(f"  Eq47 fco     = {d['fco_b']/1e3:8.2f} kHz   (geometric mean of pole & fsw/2)")
    print(f"  -> use lower : {d['fco']/1e3:8.2f} kHz")
    print(f"  Eq48 R4      = {d['R4']/1e3:8.3f} kOhm")
    print(f"  Eq49 C5      = {d['C5']*1e12:8.0f} pF")
    print(f"  Eq50 C8      = {d['C8a']*1e12:8.1f} pF")
    print(f"  Eq51 C8      = {d['C8b']*1e12:8.1f} pF  -> use larger = {d['C8']*1e12:.1f} pF")

print("\n" + "="*78)
print("Rounding to standard values")
print("="*78)
R4s, C5s, C8s = 11.5e3, 33e-9, 47e-12
print(f"  R4 = 11.463 k -> E96 standard  11.5 kOhm  (+0.3%)")
print(f"  C5 = 30515 pF -> E6  standard  33 nF      (+8.1%, moves zero DOWN to "
      f"{1/(2*math.pi*R4s*C5s):.0f} Hz, i.e. below fp(mod) -> more phase margin)")
print(f"  C8 = 46.3 pF  -> E24 standard  47 pF      (+1.5%)")

print("\n" + "="*78)
print("VERIFICATION - closed-loop crossover & phase margin vs COUT derating and load")
print("(COUT nominal 2 x 47 uF = 94 uF; sweep covers 0% .. 68% derating)")
print("="*78)
print(f"{'COUT(uF)':>9} {'derate':>7} | {'0.15A':>15} {'0.75A':>15} {'1.5A':>15} {'3.5A':>15}")
print(f"{'':>9} {'':>7} | " + " ".join(f"{'fc kHz / PM':>15}" for _ in range(4)))
print("-"*78)
worst = 999
for cout_uF in [30, 40, 47, 58.3, 70, 80, 94]:
    cout = cout_uF*1e-6
    resr = 2.5e-3
    row = f"{cout_uF:9.1f} {100*(1-cout_uF/94):6.0f}% |"
    for iout in [0.15, 0.75, 1.5, 3.5]:
        fx, pm = margins(cout, resr, R4s, C5s, C8s, iout)
        worst = min(worst, pm)
        row += f" {fx/1e3:7.2f}/{pm:5.1f}deg"
    print(row)
print("-"*78)
print(f"WORST-CASE PHASE MARGIN across the entire sweep: {worst:.1f} deg")
print("Target: >45 deg is the usual stability criterion; >60 deg is comfortable.")

print("\n" + "="*78)
print("OUTPUT CAPACITOR SIZING CHECK - TI Eq 32/33/34/35 for the 9 V rail")
print("="*78)
dI, dV = 1.5, 0.04*9      # full load step 0 -> 1.5 A, 4% of Vout
c32 = 2*dI/(FSW*dV)
c33 = L*(1.5**2 - 0**2)/((9.36**2)-(9.0**2))
Iripple = 9*(26.1-9)/(26.1*22e-6*600e3)
c34 = (1/(8*FSW))*(Iripple/0.025)
r35 = 0.025/Iripple
print(f"  Inductor ripple dI_L (plan sec 2.6)   = {Iripple:.3f} A  ({100*Iripple/1.5:.0f}% of 1.5 A load)")
print(f"  Eq32 transient  0->1.5 A, dV=4%       = {c32*1e6:6.2f} uF")
print(f"  Eq33 overshoot  1.5->0 A, dV=4%       = {c33*1e6:6.2f} uF")
print(f"  Eq34 ripple     VORIPPLE = 25 mV      = {c34*1e6:6.2f} uF")
print(f"  Eq35 max ESR    VORIPPLE = 25 mV      = {r35*1e3:6.1f} mOhm")
print(f"  --> governing minimum = {max(c32,c33,c34)*1e6:.2f} uF derated")
print(f"  --> 2 x 47 uF even at 68% derating = 30 uF = {30/ (max(c32,c33,c34)*1e6):.1f}x the minimum  OK")
print(f"  --> chosen RESR 2.5 mOhm (2 x 5 mOhm 1210 MLCC) is {r35/2.5e-3:.0f}x under the Eq35 limit  OK")
