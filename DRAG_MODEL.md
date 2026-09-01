# The Drag Model — Every Equation

This document describes all equations used by `rocketserializer.dragmodel` (and
the `ork2dragcurve` command) to compute a rocket's drag curve. The model is an
exact re-implementation of OpenRocket 24.12's zero-lift drag build-up, which
itself follows Barrowman's method extended in S. Niskanen, *OpenRocket
technical documentation* (Chapter: Drag). Each section names the OpenRocket
class the equation comes from.

**Units:** SI everywhere (m, m², K, Pa, kg/m³), angles in radians, Mach number
$M$ and all coefficients dimensionless. Every drag coefficient is referenced to
the rocket's **reference area**

$$A_{ref} = \frac{\pi}{4}\, d_{ref}^2$$

where $d_{ref}$ is the reference length — by default (`referencetype
maximum`) twice the largest body radius of the rocket.

---

## 1. Total drag coefficient

*(BarrowmanDragCalculator.calculateDrag)*

The drag coefficient at a flight condition $(M, Re, \alpha)$ is the sum of four
independent parts:

$$C_D = C_{D,friction} + C_{D,pressure} + C_{D,base} + C_{D,override}$$

- **friction** — skin friction of every exposed surface (§3);
- **pressure** — nose cones, shoulders, boattails, fin leading edges, launch
  lugs, rail buttons (§4);
- **base** — low-pressure wake behind every rearward-facing surface (§5);
- **override** — user-set per-component $C_D$ values replacing the computed
  ones (§6).

The **axial** drag coefficient (the one that actually decelerates the rocket
along its axis) applies an angle-of-attack multiplier (§7):

$$C_A = \mu(\alpha)\; C_D$$

## 2. Flight conditions

The two flow parameters are Mach number and Reynolds number. OpenRocket uses
linear fits for the speed of sound and the dynamic viscosity of air:

$$a = 165.77 + 0.606\,T \qquad \text{[m/s, T in K]}$$

$$\nu = \frac{3.7291\times10^{-6} + 4.9944\times10^{-8}\,T}{\rho}
\qquad\qquad \rho = \frac{p}{R\,T},\quad R = 287.053$$

The Reynolds number is built on the **aerodynamic length** $L$ — the total
nose-to-tail length of the outside surfaces (including any fin overhang past
the body):

$$Re = \frac{M\,a\,L}{\nu}$$

For the exported drag curve (`ork2dragcurve`, `DragBuildup.drag_curve`) the
conditions are sea-level ISA, zero angle of attack:
$T = 288.15\ \text{K}$, $p = 101325\ \text{Pa}$.

## 3. Skin-friction drag

*(BarrowmanDragCalculator.calculateFrictionCD / calculateFrictionCoefficient)*

### 3.1 Smooth-wall friction coefficient $C_f(Re, M)$

One friction coefficient is computed for the whole rocket (turbulent flow,
the default "not polished to perfection" case):

$$C_f =
\begin{cases}
1.48\times10^{-2} & Re < 10^4 \\[4pt]
\dfrac{1}{(1.50\,\ln Re - 5.6)^2} & Re \ge 10^4
\end{cases}$$

It is then corrected for compressibility with

$$c_1 = 1 - 0.1 M^2 \qquad\qquad c_2 = \frac{1}{(1 + 0.15\,M^2)^{0.58}}$$

$$C_f \leftarrow
\begin{cases}
C_f\,c_1 & M < 0.9\\[2pt]
C_f\left[\,c_2\frac{M-0.9}{0.2} + c_1\frac{1.1-M}{0.2}\right] & 0.9 \le M < 1.1
\quad\text{(linear blend)}\\[2pt]
C_f\,c_2 & M \ge 1.1
\end{cases}$$

*(A "perfect finish" mode with laminar/transitional branches exists —
$C_f = 1.328/\sqrt{Re}$ for $Re < 5.39\times10^5$, then
$1/(1.50\ln Re - 5.6)^2 - 1700/Re$ — but no LASC design uses it.)*

### 3.2 Surface-roughness limit

At high Reynolds number the friction cannot drop below the roughness-limited
value, which depends on each component's surface finish (roughness height
$k$):

$$C_{f,rough} = 0.032\left(\frac{k}{L}\right)^{0.2} \cdot r(M),
\qquad
r(M) =
\begin{cases}
1 - 0.1 M^2 & M < 0.9\\
\text{linear blend} & 0.9 \le M \le 1.1\\
\dfrac{1}{1 + 0.18\,M^2} & M > 1.1
\end{cases}$$

Each component uses $C_{f,c} = \max(C_f,\; C_{f,rough})$.

Roughness heights (`ExternalComponent.Finish`):

| finish | $k$ (µm) | | finish | $k$ (µm) |
|---|---|---|---|---|
| rough | 500 | | optimum paint | 5 |
| rough unfinished | 250 | | aircraft sheet metal | 2 |
| unfinished | 150 | | polished | 0.5 |
| **regular paint (default)** | **60** | | mirror | 0 |
| smooth paint | 20 | | | |

### 3.3 Per-component friction drag

$$C_{D,friction,c} =
\begin{cases}
C_{f,c}\,\dfrac{A_{wet}}{A_{ref}} & \text{body tube / nose / transition}\\[8pt]
C_{f,c}\left(1 + \dfrac{2t}{\bar{c}}\right)\dfrac{2\,A_{fin}}{A_{ref}}
& \text{each fin}\\[8pt]
0 & \text{launch lugs, rail buttons}
\end{cases}$$

where $A_{wet}$ is the component's wetted (outside) area, $t$ the fin
thickness, $\bar{c}$ the fin mean aerodynamic chord and $A_{fin}$ the
one-sided planform area of a single fin (the $2$ counts both sides).

### 3.4 Body fineness correction

Body (not fin) friction is increased for stubby rockets. With body length
$\ell = x_{max}-x_{min}$ and maximum body radius $r_{max}$:

$$f_B = \frac{\ell + 0.0001}{r_{max}}
\qquad\qquad
C_{D,friction} = C_{D,fins} + \left(1 + \frac{1}{2 f_B}\right) C_{D,body}$$

## 4. Pressure drag

Two helper coefficients, evaluated at the current Mach number, scale most
pressure-drag terms *(BarrowmanDragCalculator.calculateStagnationCD /
calculateBaseCD)*:

**Stagnation coefficient** (drag of a forward-facing flat surface):

$$C_{stag}(M) = 0.85 \cdot
\begin{cases}
1 + \dfrac{M^2}{4} + \dfrac{M^4}{40} & M \le 1\\[6pt]
1.84 - \dfrac{0.76}{M^2} + \dfrac{0.166}{M^4} + \dfrac{0.035}{M^6} & M > 1
\end{cases}$$

**Base coefficient** (suction behind a rearward-facing flat surface):

$$C_{base}(M) =
\begin{cases}
0.12 + 0.13\,M^2 & M \le 1\\[2pt]
0.25 / M & M > 1
\end{cases}$$

### 4.1 Nose cones — conical and ogive

*(SymmetricComponentCalc.calculateOgiveNoseInterpolator)*

The key geometric input is $\sin\phi$ — the sine of the surface slope over
the last 1 % of the nose length, at the joint to the body:

$$\sin\phi = \frac{R - r(0.99\,L_n)}{\sqrt{\big(R - r(0.99 L_n)\big)^2 + (0.01 L_n)^2}}$$

(For a cone this equals the sine of the half-apex angle; for a perfectly
tangent ogive it approaches 0, so a tangent ogive has almost no pressure
drag.)

Transonic anchor values:

$$C_{D,p}(M{=}1) = \sin\phi
\qquad
C_{D,p}(M{=}1.3) = 2.1\sin^2\phi + 0.6019\sin\phi$$

joined on $1 \le M \le 1.3$ by the cubic polynomial that also matches the
slopes

$$\left.\frac{dC_{D,p}}{dM}\right|_{M=1} = \frac{4}{\gamma+1}\left(1 - \tfrac{1}{2}\sin\phi\right),
\qquad
\left.\frac{dC_{D,p}}{dM}\right|_{M=1.3} = -1.1341\,\sin\phi
\qquad (\gamma = 1.4)$$

Above $M = 1.3$:

$$C_{D,p}(M) = 2.1\sin^2\phi + \frac{0.5\,\sin\phi}{\sqrt{M^2-1}}$$

Secant ogives (shape parameter $0<p<1$) multiply the whole curve by
$0.72\,(p-0.5)^2 + 0.82$ (equal to 1 for a cone and a tangent ogive).

### 4.2 Nose cones — other shapes

*(SymmetricComponentCalc.calculateNoseInterpolator)*

For ellipsoid, power-series, parabolic and Haack shapes, the transonic drag
comes from wind-tunnel tables (NASA TR-R-100) measured at fineness ratio 3,
linearly interpolated in Mach and blended between neighbouring shapes by the
shape parameter. The tabulated $C_{D,p}$ values (referenced to the nose
frontal area):

| $M$ | ellipsoid | $x^{1/2}$ power | von Kármán | LV-Haack | full parabolic |
|-----|-----------|-----------------|------------|----------|----------------|
| 0.9 | – | – | 0 | 0 | – |
| 0.95| – | 0.014 | 0.010 | 0.010 | 0 |
| 1.0 | – | 0.050 | 0.027 | 0.024 | 0.041 |
| 1.05| – | 0.060 | 0.055 | 0.066 | 0.092 |
| 1.1 | – | 0.059 | 0.070 | 0.084 | 0.109 |
| 1.2 | 0.110 | 0.081 | 0.081 | 0.100 | 0.119 |
| 1.3 | 0.140 | 0.084 | – | – | – |
| 1.4 | 0.148 | – | 0.095 | 0.114 | 0.113 |
| 2.0 | 0.159 | 0.078 | 0.091 | 0.113 | – |

*(plus tables for $x^{1/4}$, $x^{3/4}$, ½- and ¾-parabolic; values outside a
table hold the end value constant.)*

Two corrections adapt the fineness-3 tables to the actual nose:

**Fineness extrapolation** — with $f_N = L_n / (2R)$ and the blunt-body value
$C_{stag}(M)$:

$$C_{D,p}(M) = C_{stag}(M)\left(\frac{C_{D,p,f=3}(M)}{C_{stag}(M)}\right)^{\log_4(f_N+1)}$$

(at $f_N = 3$ the table is recovered; at $f_N = 0$ the nose behaves like a
flat disk).

**Subsonic extension** — below the first tabulated Mach $M_0$, a power law is
fitted matching the value and slope at $M_0$, anchored at

$$C_{D,p}(0) = 0.8\,\sin^2\phi:
\qquad
C_{D,p}(M) = a\,M^b + 0.8\sin^2\phi$$

$$b = \frac{M_0\; C'_{D,p}(M_0)}{C_{D,p}(M_0) - 0.8\sin^2\phi}
\qquad
a = \frac{C_{D,p}(M_0) - 0.8\sin^2\phi}{M_0^{\,b}}$$

Finally the coefficient is referenced to the rocket:

$$C_{D,nose} = C_{D,p}(M)\,\frac{A_{frontal}}{A_{ref}},
\qquad A_{frontal} = \pi\left|r_{aft}^2 - r_{fore}^2\right|$$

The same equations handle **expanding transitions** (conical shoulders), using
the annular frontal area.

### 4.3 Boattails (reducing transitions)

*(SymmetricComponentCalc.calculatePressureCD)*

With the "reduction fineness" $\gamma_t = \dfrac{L_t}{2\,|r_{fore}-r_{aft}|}$:

$$C_{D,boattail} =
\begin{cases}
C_{base}(M)\,\dfrac{A_{frontal}}{A_{ref}} & \gamma_t \le 1\\[8pt]
C_{base}(M)\,\dfrac{A_{frontal}}{A_{ref}}\cdot\dfrac{3-\gamma_t}{2} & 1 < \gamma_t < 3\\[8pt]
0 & \gamma_t \ge 3
\end{cases}$$

(a gentle enough taper recovers all the pressure; a blunt cut behaves like a
base).

### 4.4 Diameter steps

*(BarrowmanDragCalculator.calculatePressureCD)*

Wherever a component's fore radius exceeds the previous component's aft
radius, the exposed forward-facing ring gets full stagnation drag:

$$C_{D,step} = C_{stag}(M)\,\frac{\pi\,(r_{fore}^2 - r_{prev}^2)}{A_{ref}}$$

### 4.5 Fin leading edge

*(FinSetCalc.calculatePressureCD)* — per fin, scaled by the frontal area
$s\,t$ (span × thickness) and the leading-edge sweep angle $\Gamma_L$:

$$C_{D,LE} = c_{le}(M)\,\cos^2\Gamma_L\,\frac{s\,t}{A_{ref}}$$

Rounded or airfoil cross-section:

$$c_{le}(M) =
\begin{cases}
(1-M^2)^{-0.417} - 1 & M < 0.9\\[2pt]
1 - 1.785\,(M - 0.9) & 0.9 \le M < 1\\[2pt]
1.214 - \dfrac{0.502}{M^2} + \dfrac{0.1095}{M^4} & M \ge 1
\end{cases}$$

Square cross-section: $c_{le}(M) = C_{stag}(M)$.

### 4.6 Fin trailing edge

*(FinSetCalc, booked in the pressure component as in OpenRocket ≤ 24.12)*

$$C_{D,TE} = c_{te}\,\frac{s\,t}{A_{ref}},
\qquad
c_{te} =
\begin{cases}
C_{base}(M) & \text{square}\\
C_{base}(M)/2 & \text{rounded}\\
0 & \text{airfoil (tapered)}
\end{cases}$$

### 4.7 Launch lugs (tubes with through-flow)

*(TubeCalc.calculatePressureCD)* — the bore adds internal pipe friction
(Swamee–Jain friction factor $f$ with the finish roughness $\varepsilon$ and
the bore diameter $d$), the annular wall adds external drag:

$$Re_d = \frac{V\,d}{\nu}
\qquad
f = \frac{0.25}{\left[\log_{10}\!\left(\dfrac{\varepsilon}{3.7\,d} +
\dfrac{5.74}{Re_d^{0.9}}\right)\right]^2}$$

The Darcy–Weisbach pressure drop over the tube length $\ell$ reduces to a
drag coefficient independent of the air state:

$$C_{D,bore} = \frac{2\,\Delta p}{\rho V^2} = f\,\frac{\ell}{d}$$

$$C_{D,lug} = \frac{C_{D,bore}\,A_{bore} + 0.7\,\big(C_{stag}+C_{base}\big)\,A_{annulus}}{A_{ref}}$$

### 4.8 Rail buttons

*(RailButtonCalc.calculatePressureCD, Gowen & Perkins NACA TN-2960)*

Each button of height $h$ at distance $x$ from the nose tip sits partly inside
the turbulent boundary layer of thickness

$$\delta = \frac{0.37\,x}{Re_x^{0.2}}, \qquad Re_x = \frac{V x}{\nu}$$

and therefore sees a reduced **effective Mach number**

$$M_{eff} =
\begin{cases}
\dfrac{h - \delta/2}{h}\,M & h > \delta\\[6pt]
\dfrac{h/2}{\delta}\,M & h \le \delta
\end{cases}$$

The cylinder drag table (piecewise linear):

| $M$ | 0 | 0.2 | 0.3 | 0.4 | 0.5 | 0.6 | 0.7 | 1.0 | 1.6 | 2.0 | 2.8+ |
|-----|---|-----|-----|-----|-----|-----|-----|-----|-----|-----|------|
| $c_d$ |1.20|1.22|1.25|1.30|1.40|1.50|1.60|**2.10**|1.50|1.45|1.33|

$$C_{D,button} = c_d(M_{eff})\,\frac{M_{eff}^2}{M^2}\cdot
C_{stag}(M)\,\frac{A_{button}}{A_{ref}}$$

with the side-silhouette area
$A_{button} = h\,D_{out} - (D_{out}-D_{in})\,h_{inner}$.

## 5. Base drag

*(BarrowmanDragCalculator.calculateBaseCD)*

Wherever a component's aft radius exceeds the next component's fore radius —
including the very tail of the rocket, where the "next radius" is zero — the
exposed rearward-facing ring gets base drag:

$$C_{D,base} = C_{base}(M)\,\frac{\pi\,(r_{aft}^2 - r_{next}^2)}{A_{ref}}$$

(OpenRocket applies this during motor burn too — there is no power-on /
power-off distinction in its drag model.)

## 6. Component CD overrides

A component with a user override contributes exactly

$$C_{D,override} = n \cdot C_{D,set}$$

($n$ = number of instances, e.g. fins in a set) and is excluded from the
friction, pressure and base sums. An override marked "for all subcomponents"
also silences every descendant.

## 7. Angle-of-attack (axial) conversion

*(BarrowmanDragCalculator.calculateAxialCD)*

The drag coefficient acts along the flow; the axial coefficient along the
rocket axis. OpenRocket uses a smooth empirical multiplier $\mu(\alpha)$
built from two polynomials:

- $0 \le \alpha \le 17°$: cubic with $\mu(0)=1$, $\mu(17°)=1.3$,
  $\mu'(0)=\mu'(17°)=0$ — equivalently
  $$\mu = 1 + 0.3\,(3u^2 - 2u^3), \qquad u = \alpha / 17°$$
- $17° \le \alpha \le 90°$: quartic with $\mu(17°)=1.3$, $\mu(90°)=0$,
  $\mu'(17°)=\mu'(90°)=\mu''(90°)=0$.

For $\alpha > 90°$ the curve is mirrored ($\alpha \to \pi-\alpha$) and the
sign flips (the rocket flies backwards):

$$C_A = \begin{cases} \mu(\alpha)\,C_D & \alpha < 90° \\ -\mu(\pi-\alpha)\,C_D & \alpha \ge 90° \end{cases}$$

At zero angle of attack — the exported drag curve — $\mu = 1$ and
$C_A = C_D$.

## 8. Geometry inputs

The equations above consume a few integrated geometric quantities, computed
exactly as OpenRocket does:

- **Wetted area** of a nose/transition: the profile $r(x)$ is split into 128
  conical frusta, $A_{wet} = \pi \sum (r_1+r_2)\sqrt{(r_1-r_2)^2+\Delta x^2}$;
  a body tube is analytic, $A_{wet} = 2\pi r \ell$.
- **Fin planform area** $A_{fin}$: area enclosed between the fin outline and
  the body surface (trapezoid-rule curve integral).
- **Fin MAC** $\bar{c}$ and **leading-edge sweep** $\cos\Gamma_L$: the fin
  (plus its root curve) is sliced into 48 spanwise strips;
  $\bar{c} = \sum c_i^2 \,/\, \sum c_i$ and $\cos\Gamma_L$ is the mean of
  $\Delta y / \sqrt{\Delta x_{LE}^2 + \Delta y^2}$ over the strips.
- **Profile shapes** $r(x)$ for conical, ogive (with parameter), ellipsoid,
  power, parabolic and Haack noses/transitions, including clipped
  transitions.

## 9. Validation

Replaying the stored per-datapoint $(M, Re, \alpha)$ of every simulation
saved inside the LASC 2026 `.ork` files through these equations reproduces
OpenRocket's stored `Friction/Pressure/Base/Drag/Axial drag coefficient`
columns within their serialized precision (three decimals, ≈ ±0.001) for
**every up-to-date simulation in the corpus** (~133,000 datapoints across
165 simulation branches, OpenRocket 22.02/23.09/24.12). The corpus covers
Mach 0–0.99; the supersonic branches are pinned by unit tests against
OpenRocket's constants.
