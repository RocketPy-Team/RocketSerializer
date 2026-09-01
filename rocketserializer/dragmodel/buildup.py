"""The zero-lift drag build-up: exact port of ``BarrowmanDragCalculator``.

Total ``CD = friction + pressure + base + override`` evaluated at a flight
condition ``(mach, reynolds, aoa)``; ``CD_axial`` applies OpenRocket's
angle-of-attack multiplier.  ``reynolds`` is OpenRocket's Reynolds number over
the rocket's *aerodynamic length* (the value stored in the "Reynolds number"
flight-data column), which supplies ``V/nu`` for the internal pipe-flow and
boundary-layer sub-models without needing an atmosphere model.

Version notes (defaults reproduce OpenRocket 24.12, which also matches 23.09
and 22.02 for every formula relevant here):

- ``fin_te_in_pressure=True`` books fin trailing-edge drag in the pressure
  component, as every release <= 24.12 does (current master moved it to base;
  totals are identical either way);
- ``tangent_ogive_zero_sinphi=False`` keeps 24.12's behavior of measuring the
  nose joint angle from the profile even for tangent ogives (master forces 0).
"""

import math

from .components import FINISH_ROUGHNESS, FinSet, LaunchLug, RailButton, TubeFinSet
from .geometry import EPSILON, safe_sqrt
from .interpolators import LinearInterpolator, eval_poly, poly_interpolator

GAMMA = 1.4

# --- sea-level ISA constants for the exported Cd(Mach) curve ---------------
SEA_LEVEL_TEMPERATURE = 288.15  # K
SEA_LEVEL_PRESSURE = 101325.0  # Pa
GAS_CONSTANT = 287.053  # J/(kg K)


def speed_of_sound(temperature):
    """OpenRocket's linear fit ``c = 165.77 + 0.606 T``."""
    return 165.77 + 0.606 * temperature


def kinematic_viscosity(temperature, density):
    """OpenRocket's linearized Sutherland fit divided by density."""
    return (3.7291e-6 + 4.9944e-8 * temperature) / density


# ---------------------------------------------------------------------------
# Static kernels
# ---------------------------------------------------------------------------


def stagnation_cd(mach):
    """``calculateStagnationCD``."""
    if mach <= 1:
        pressure = 1 + mach**2 / 4 + mach**4 / 40
    else:
        pressure = 1.84 - 0.76 / mach**2 + 0.166 / mach**4 + 0.035 / mach**6
    return 0.85 * pressure


def base_cd(mach):
    """``calculateBaseCD``."""
    if mach <= 1:
        return 0.12 + 0.13 * mach * mach
    return 0.25 / mach


def friction_coefficient(mach, reynolds, perfect_finish=False):
    """``calculateFrictionCoefficient``: smooth-wall Cf(Re, M)."""
    if perfect_finish:
        if reynolds < 1.0e4:
            cf = 1.33e-2
        elif reynolds < 5.39e5:
            cf = 1.328 / safe_sqrt(reynolds)
        else:
            cf = 1.0 / (1.50 * math.log(reynolds) - 5.6) ** 2 - 1700 / reynolds
        c1, c2 = 1.0, 1.0
        if mach < 1.1 and reynolds > 1.0e6:
            if reynolds < 3.0e6:
                c1 = 1 - 0.1 * mach**2 * (reynolds - 1.0e6) / 2.0e6
            else:
                c1 = 1 - 0.1 * mach**2
        if mach > 0.9 and reynolds > 1.0e6:
            if reynolds < 3.0e6:
                c2 = (
                    1
                    + (1.0 / (1 + 0.045 * mach**2) ** 0.25 - 1)
                    * (reynolds - 1.0e6)
                    / 2.0e6
                )
            else:
                c2 = 1.0 / (1 + 0.045 * mach**2) ** 0.25
    else:
        if reynolds < 1.0e4:
            cf = 1.48e-2
        else:
            cf = 1.0 / (1.50 * math.log(reynolds) - 5.6) ** 2
        c1 = 1 - 0.1 * mach**2
        c2 = 1 / (1 + 0.15 * mach**2) ** 0.58
    if mach < 0.9:
        cf *= c1
    elif mach < 1.1:
        cf *= c2 * (mach - 0.9) / 0.2 + c1 * (1.1 - mach) / 0.2
    else:
        cf *= c2
    return cf


def roughness_correction(mach):
    """``calculateRoughnessCorrection``."""
    if mach < 0.9:
        return 1 - 0.1 * mach**2
    if mach > 1.1:
        return 1 / (1 + 0.18 * mach**2)
    c1 = 1 - 0.1 * 0.9**2
    c2 = 1.0 / (1 + 0.18 * 1.1**2)
    return c2 * (mach - 0.9) / 0.2 + c1 * (1.1 - mach) / 0.2


# --- CD -> axial CD multiplier (static polynomials) ------------------------

_AOA_KNOT = 17 * math.pi / 180
_AXIAL_POLY_1 = poly_interpolator([0, _AOA_KNOT], [0, _AOA_KNOT], [], [1, 1.3, 0, 0])
_AXIAL_POLY_2 = poly_interpolator(
    [_AOA_KNOT, math.pi / 2],
    [_AOA_KNOT, math.pi / 2],
    [math.pi / 2],
    [1.3, 0, 0, 0, 0],
)


def axial_cd(cd, aoa):
    """``calculateAxialCD``: the CD -> CA conversion vs angle of attack."""
    clamped = min(max(aoa, 0.0), math.pi)
    mirrored = math.pi - clamped if clamped > math.pi / 2 else clamped
    if mirrored < _AOA_KNOT:
        mul = eval_poly(mirrored, _AXIAL_POLY_1)
    else:
        mul = eval_poly(mirrored, _AXIAL_POLY_2)
    return mul * cd if aoa < math.pi / 2 else -mul * cd


# ---------------------------------------------------------------------------
# Nose/transition pressure-drag interpolator (SymmetricComponentCalc)
# ---------------------------------------------------------------------------

# NASA TR-R-100 fineness-ratio-3 tables (exact OpenRocket constants)
_ELLIPSOID = LinearInterpolator(
    [1.2, 1.25, 1.3, 1.4, 1.6, 2.0, 2.4],
    [0.110, 0.128, 0.140, 0.148, 0.152, 0.159, 0.162],
)
_X14 = LinearInterpolator(
    [1.2, 1.3, 1.4, 1.6, 1.8, 2.2, 2.6, 3.0, 3.6],
    [0.140, 0.156, 0.169, 0.192, 0.206, 0.227, 0.241, 0.249, 0.252],
)
_X12 = LinearInterpolator(
    [0.925, 0.95, 1.0, 1.05, 1.1, 1.2, 1.3, 1.7, 2.0],
    [0, 0.014, 0.050, 0.060, 0.059, 0.081, 0.084, 0.085, 0.078],
)
_X34 = LinearInterpolator(
    [0.8, 0.9, 1.0, 1.06, 1.2, 1.4, 1.6, 2.0, 2.8, 3.4],
    [0, 0.015, 0.078, 0.121, 0.110, 0.098, 0.090, 0.084, 0.078, 0.074],
)
_VON_KARMAN = LinearInterpolator(
    [0.9, 0.95, 1.0, 1.05, 1.1, 1.2, 1.4, 1.6, 2.0, 3.0],
    [0, 0.010, 0.027, 0.055, 0.070, 0.081, 0.095, 0.097, 0.091, 0.083],
)
_LV_HAACK = LinearInterpolator(
    [0.9, 0.95, 1.0, 1.05, 1.1, 1.2, 1.4, 1.6, 2.0],
    [0, 0.010, 0.024, 0.066, 0.084, 0.100, 0.114, 0.117, 0.113],
)
_PARABOLIC = LinearInterpolator(
    [0.95, 0.975, 1.0, 1.05, 1.1, 1.2, 1.4, 1.7],
    [0, 0.016, 0.041, 0.092, 0.109, 0.119, 0.113, 0.108],
)
_PARABOLIC_12 = LinearInterpolator(
    [0.8, 0.9, 0.95, 1.0, 1.05, 1.1, 1.3, 1.5, 1.8],
    [0, 0.016, 0.042, 0.100, 0.126, 0.125, 0.100, 0.090, 0.088],
)
_PARABOLIC_34 = LinearInterpolator(
    [0.9, 0.95, 1.0, 1.05, 1.1, 1.2, 1.4, 1.7],
    [0, 0.023, 0.073, 0.098, 0.107, 0.106, 0.089, 0.082],
)


def _blunt_interpolator():
    interp = LinearInterpolator()
    m = 0.0
    while m < 3:
        interp.add_point(m, stagnation_cd(m))
        m += 0.05
    return interp


_BLUNT = _blunt_interpolator()

_CONICAL_POLY_XS = ([1.0, 1.3], [1.0, 1.3])


def ogive_nose_interpolator(param, sinphi):
    """``calculateOgiveNoseInterpolator``: analytic conical/ogive drag curve."""
    cd_mach1 = sinphi
    cd_mach1_3 = 2.1 * sinphi**2 + 0.6019 * sinphi
    poly = poly_interpolator(
        _CONICAL_POLY_XS[0],
        _CONICAL_POLY_XS[1],
        [],
        [
            cd_mach1,
            cd_mach1_3,
            4.0 / (GAMMA + 1) * (1 - 0.5 * cd_mach1),
            -1.1341 * sinphi,
        ],
    )
    mul = 0.72 * (param - 0.5) ** 2 + 0.82
    interp = LinearInterpolator()
    m = 1.0
    while m < 1.3001:
        interp.add_point(m, mul * eval_poly(m, poly))
        m += 0.02
    m = 1.32
    while m < 4:
        interp.add_point(
            m, mul * (2.1 * sinphi**2 + 0.5 * sinphi / safe_sqrt(m * m - 1))
        )
        m += 0.02
    return interp


def nose_pressure_interpolator(shape, param, fineness, sinphi):
    """``calculateNoseInterpolator``: the full per-shape Cd(Mach) curve.

    ``fineness = length / (2 |r_aft - r_fore|)``; ``sinphi`` is the surface
    slope sine over the last 1 % of length at the aft joint.
    """
    int1 = int2 = None
    p = 0.0
    if shape == "conical":
        result = ogive_nose_interpolator(0.0, sinphi)
    elif shape == "ogive":
        result = ogive_nose_interpolator(param, sinphi)
    else:
        if shape == "ellipsoid":
            int1 = _ELLIPSOID
        elif shape == "power":
            if param <= 0.25:
                int1, int2, p = _BLUNT, _X14, param * 4
            elif param <= 0.5:
                int1, int2, p = _X14, _X12, (param - 0.25) * 4
            elif param <= 0.75:
                int1, int2, p = _X12, _X34, (param - 0.5) * 4
            else:
                cone_sinphi = 1 / safe_sqrt(1 + 4 * fineness**2)
                int1 = _X34
                int2 = ogive_nose_interpolator(0.0, cone_sinphi)
                p = (param - 0.75) * 4
        elif shape == "parabolic":
            if param <= 0.5:
                cone_sinphi = 1 / safe_sqrt(1 + 4 * fineness**2)
                int1 = ogive_nose_interpolator(0.0, cone_sinphi)
                int2, p = _PARABOLIC_12, param * 2
            elif param <= 0.75:
                int1, int2, p = _PARABOLIC_12, _PARABOLIC_34, (param - 0.5) * 4
            else:
                int1, int2, p = _PARABOLIC_34, _PARABOLIC, (param - 0.75) * 4
        elif shape == "haack":
            int1, int2, p = _VON_KARMAN, _LV_HAACK, param * 3
        else:
            raise ValueError("unsupported nose shape: %s" % shape)

        if int2 is not None:
            blended = LinearInterpolator()
            for m in sorted(set(int1.x_points()) | set(int2.x_points())):
                blended.add_point(
                    m, p * int2.get_value(m) + (1 - p) * int1.get_value(m)
                )
            int1 = blended

        # fineness-ratio extrapolation against the blunt (stagnation) curve
        result = LinearInterpolator()
        log4 = math.log(fineness + 1) / math.log(4)
        for m in int1.x_points():
            stag = _BLUNT.get_value(m)
            result.add_point(m, stag * (int1.get_value(m) / stag) ** log4)

    # subsonic power-law extension  Cd = a M^b + Cd(M=0)
    m_min = result.x_points()[0]
    min_value = result.get_value(m_min)
    if min_value < 0.001:
        return result
    cd_mach0 = 0.8 * sinphi**2
    min_deriv = (result.get_value(m_min + 0.01) - min_value) / 0.01
    if cd_mach0 >= min_value - 0.01 or min_deriv <= 0.01:
        return result
    b = m_min * min_deriv / (min_value - cd_mach0)
    a = (min_value - cd_mach0) / m_min**b
    m = 0.0
    while m < m_min:
        result.add_point(m, a * m**b + cd_mach0)
        m += 0.05
    return result


# ---------------------------------------------------------------------------
# Per-component calculators
# ---------------------------------------------------------------------------


class _SymmetricCalc:
    """``SymmetricComponentCalc`` geometry snapshot + pressure dispatch."""

    def __init__(self, comp, tangent_ogive_zero_sinphi):
        self.comp = comp
        self.length = comp.length
        if self.length > 0:
            self.fore_radius = comp.fore_radius
            self.aft_radius = comp.aft_radius
        else:  # zero-length disk: both radii forced to the maximum
            r = max(comp.fore_radius, comp.aft_radius)
            self.fore_radius = self.aft_radius = r
        diff = abs(self.aft_radius - self.fore_radius)
        self.fineness = self.length / (2 * diff) if diff > 0 else math.inf
        self.frontal_area = abs(math.pi * (self.fore_radius**2 - self.aft_radius**2))
        if comp.kind == "bodytube" or (
            tangent_ogive_zero_sinphi
            and comp.shape == "ogive"
            and comp.shape_param == 1.0
        ):
            self.sinphi = 0.0
        else:
            r = comp.radius(0.99 * self.length) if self.length > 0 else self.aft_radius
            dr = self.aft_radius - r
            hyp = math.hypot(dr, 0.01 * self.length)
            self.sinphi = dr / hyp if hyp > 0 else 0.0
        self._interpolator = None

    def friction_cd(self, cf, ref_area):
        return cf * self.comp.wet_area / ref_area

    def pressure_cd(self, mach, stagnation, base, ref_area):
        if self.fore_radius == self.aft_radius:
            return 0.0
        if self.length < 0.001:  # thin disk
            if self.fore_radius < self.aft_radius:
                return stagnation * self.frontal_area / ref_area
            return base * self.frontal_area / ref_area
        if self.aft_radius < self.fore_radius:  # boat-tail
            if self.fineness >= 3:
                return 0.0
            cd = base * self.frontal_area / ref_area
            if self.fineness <= 1:
                return cd
            return cd * (3 - self.fineness) / 2
        # nose cone or expanding shoulder
        if self._interpolator is None:
            self._interpolator = nose_pressure_interpolator(
                self.comp.shape, self.comp.shape_param, self.fineness, self.sinphi
            )
        return self._interpolator.get_value(mach) * self.frontal_area / ref_area


class _FinSetCalc:
    """``FinSetCalc`` drag parts (leading edge, trailing edge, friction)."""

    def __init__(self, fin_set):
        self.fin_set = fin_set
        geo = fin_set.geometry()
        self.fin_area = geo.fin_area
        self.mac_length = geo.mac_length
        self.cos_gamma_lead = geo.cos_gamma_lead
        self.span = fin_set.span
        self.thickness = fin_set.thickness
        self.cross_section = fin_set.cross_section

    def friction_cd(self, cf, ref_area):
        if self.fin_area < EPSILON or self.mac_length < EPSILON:
            return 0.0
        return (
            cf
            * (1 + 2 * self.thickness / self.mac_length)
            * 2
            * self.fin_area
            / ref_area
        )

    def leading_edge_cd(self, mach, stagnation, ref_area):
        if self.fin_area < EPSILON:
            return 0.0
        if self.cross_section in ("airfoil", "rounded"):
            if mach < 0.9:
                cd = (1 - mach**2) ** -0.417 - 1
            elif mach < 1:
                cd = 1 - 1.785 * (mach - 0.9)
            else:
                cd = 1.214 - 0.502 / mach**2 + 0.1095 / mach**4
        elif self.cross_section == "square":
            cd = stagnation
        else:
            raise ValueError("unsupported cross section: %s" % self.cross_section)
        cd *= self.cos_gamma_lead**2
        cd *= self.span * self.thickness / ref_area
        return cd

    def trailing_edge_cd(self, base, ref_area):
        if self.fin_area < EPSILON:
            return 0.0
        if self.cross_section == "square":
            cd = base
        elif self.cross_section == "rounded":
            cd = base / 2
        else:  # airfoil
            cd = 0.0
        return cd * self.span * self.thickness / ref_area


def _tube_pressure_cd(
    v_positive,
    re_per_meter,
    bore_diameter,
    length,
    inner_area,
    frontal_area,
    roughness,
    stagnation,
    base,
    ref_area,
):
    """``TubeCalc.calculatePressureCD``.

    ``tubeCD = 2 dp / (rho V^2)`` reduces to ``f L / d`` with the Swamee-Jain
    friction factor, so only ``V/nu`` (via the global Reynolds number) is
    needed.  ``v_positive`` is False only at a standstill.
    """
    if not v_positive:
        return 0.0
    tube_cd = 0.0
    if inner_area > EPSILON:
        re_d = re_per_meter * bore_diameter
        f = 0.25 / math.log10(roughness / (3.7 * bore_diameter) + 5.74 / re_d**0.9) ** 2
        tube_cd = f * length / bore_diameter
    return (tube_cd * inner_area + 0.7 * (stagnation + base) * frontal_area) / ref_area


_RAIL_BUTTON_MACHS = [0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 1.0, 1.6, 2.0, 2.8, 100.0]
_RAIL_BUTTON_CDS = [1.2, 1.22, 1.25, 1.3, 1.4, 1.5, 1.6, 2.1, 1.5, 1.45, 1.33, 1.33]
_RAIL_BUTTON_STANDSTILL = 8.786395072609939e-4


def _rail_button_pressure_cd(button, mach, re_per_meter, stagnation, ref_area):
    """``RailButtonCalc.calculatePressureCD``."""
    height = button.total_height
    inner_height = height - button.flange_height - button.base_height
    button_area = (
        height * button.outer_diameter
        - (button.outer_diameter - button.inner_diameter) * inner_height
    )
    if mach > EPSILON:
        cd_mul = 0.0
        for i in range(button.instance_count):
            x = button.abs_x + i * button.instance_separation
            re_x = re_per_meter * x
            # Java's Math.pow yields NaN for x <= 0; mirror that instead of
            # raising (ZeroDivisionError / complex power)
            delta = 0.37 * x / re_x**0.2 if re_x > 0 else math.nan
            if height > delta:
                mach_eff = (height - 0.5 * delta) * mach / height
            else:
                mach_eff = (height / 2) / delta * mach
            cd = _interpolate_clamped_nan(
                _RAIL_BUTTON_MACHS, _RAIL_BUTTON_CDS, mach_eff
            )
            cd_mul += cd * mach_eff**2 / mach**2
        cd_mul /= button.instance_count
    else:
        cd_mul = _RAIL_BUTTON_STANDSTILL
    return cd_mul * stagnation * button_area / ref_area


def _interpolate_clamped_nan(xs, ys, t):
    """``MathUtil.interpolate``: piecewise linear inside the domain."""
    if math.isnan(t) or t < xs[0] or t > xs[-1]:
        return math.nan
    for i in range(1, len(xs)):
        if t <= xs[i]:
            x1, x2 = xs[i - 1], xs[i]
            y1, y2 = ys[i - 1], ys[i]
            return y1 + (y2 - y1) * (t - x1) / (x2 - x1)
    return ys[-1]


class _TubeFinSetCalc:
    """``TubeFinSetCalc`` drag parts (per single tube; caller multiplies)."""

    def __init__(self, tube_fin):
        self.tube_fin = tube_fin
        r_out = tube_fin.outer_radius
        r_in = max(r_out - tube_fin.thickness, 0.0)
        r_body = tube_fin.parent.radius(tube_fin.rel_x)
        chord = tube_fin.length
        self.bore_diameter = 2 * r_in
        self.inner_area = math.pi * r_in**2
        self.frontal_area = math.pi * (r_out**2 - r_in**2)
        # interstice between tube, its neighbor and the body surface
        d = safe_sqrt((r_body + r_out) ** 2 - r_out**2)
        theta1 = math.acos(r_out / (r_out + r_body))
        theta2 = math.pi / 2 - theta1
        self.interstice_area = d * r_out - r_out**2 * theta1 - r_body**2 * theta2
        outer_area = chord * 2 * (math.pi - theta1) * r_out
        masked_area = chord * 2 * theta2 * r_body
        self.wetted_area = outer_area - masked_area
        self.length = chord

    def friction_cd(self, cf, ref_area):
        return cf * self.wetted_area / ref_area

    def pressure_cd(self, v_positive, re_per_meter, stagnation, base, ref_area):
        cd = _tube_pressure_cd(
            v_positive,
            re_per_meter,
            self.bore_diameter,
            self.length,
            self.inner_area,
            self.frontal_area,
            FINISH_ROUGHNESS[self.tube_fin.finish],
            stagnation,
            base,
            ref_area,
        )
        return cd + (stagnation + base) * self.interstice_area / ref_area


# ---------------------------------------------------------------------------
# The build-up driver
# ---------------------------------------------------------------------------


class DragResult:
    """One evaluated flight condition, broken into OpenRocket's components."""

    __slots__ = (
        "aoa",
        "base",
        "cd",
        "cd_axial",
        "friction",
        "mach",
        "override",
        "pressure",
        "reynolds",
    )

    def __init__(self, mach, reynolds, aoa, friction, pressure, base, override):
        self.mach = mach
        self.reynolds = reynolds
        self.aoa = aoa
        self.friction = friction
        self.pressure = pressure
        self.base = base
        self.override = override
        self.cd = friction + pressure + base + override
        self.cd_axial = axial_cd(self.cd, aoa)

    def __repr__(self):
        return (
            "DragResult(mach=%.3f, cd=%.4f, friction=%.4f, pressure=%.4f, "
            "base=%.4f, override=%.4f)"
            % (
                self.mach,
                self.cd,
                self.friction,
                self.pressure,
                self.base,
                self.override,
            )
        )


class DragBuildup:
    """Evaluate OpenRocket's zero-lift drag for a parsed :class:`Rocket`.

    Parameters
    ----------
    rocket : Rocket
        The parsed design.
    active_stages : set of int, optional
        Stage indices considered active (default: all).
    fin_te_in_pressure : bool
        Book fin trailing-edge drag in the pressure component (<= 24.12
        behavior, the default) instead of the base component (master).
    tangent_ogive_zero_sinphi : bool
        Force ``sinphi = 0`` for tangent ogives (master behavior; default off,
        matching 24.12 and earlier).
    """

    def __init__(
        self,
        rocket,
        active_stages=None,
        fin_te_in_pressure=True,
        tangent_ogive_zero_sinphi=False,
    ):
        self.rocket = rocket
        self.fin_te_in_pressure = fin_te_in_pressure
        if active_stages is not None:
            active_stages = set(active_stages)
        self.symmetric = rocket.active_symmetric(active_stages)
        self.others = rocket.active_others(active_stages)
        self.length_aero = rocket.length_aerodynamic(active_stages)
        self.ref_length = rocket.reference_length(active_stages)
        self.ref_area = math.pi * (self.ref_length / 2) ** 2

        self._sym_calcs = [
            _SymmetricCalc(c, tangent_ogive_zero_sinphi) for c in self.symmetric
        ]
        self._other_calcs = []
        for comp in self.others:
            if isinstance(comp, FinSet):
                self._other_calcs.append(_FinSetCalc(comp))
            elif isinstance(comp, TubeFinSet):
                self._other_calcs.append(_TubeFinSetCalc(comp))
            else:  # launch lugs and rail buttons carry no snapshot state
                self._other_calcs.append(comp)

    # -- override helpers --------------------------------------------------

    @staticmethod
    def _overridden(comp):
        return comp.cd_override is not None

    def _overridden_by_ancestor(self, comp):
        # a stage-level "override CD for all subcomponents" covers everything
        # in the stage (the ancestor chain in Java recurses up to the stage)
        overrides = self.rocket.stage_overrides
        if comp.stage < len(overrides):
            stage_cd, stage_sub = overrides[comp.stage]
            if stage_cd is not None and stage_sub:
                return True
        parent = getattr(comp, "parent", None)
        return (
            parent is not None
            and parent.cd_override is not None
            and parent.cd_override_subcomponents
        )

    def _skip(self, comp):
        return self._overridden(comp) or self._overridden_by_ancestor(comp)

    # -- the four sub-totals -----------------------------------------------

    def evaluate(self, mach, reynolds, aoa=0.0):
        """Evaluate the drag build-up at one flight condition."""
        friction = self._friction_cd(mach, reynolds)
        pressure, fin_te = self._pressure_cd(mach, reynolds)
        base = self._base_cd(mach)
        if self.fin_te_in_pressure:
            pressure += fin_te
        else:
            base += fin_te
        override = self._override_cd()
        return DragResult(mach, reynolds, aoa, friction, pressure, base, override)

    def _friction_cd(self, mach, reynolds):
        cf = friction_coefficient(mach, reynolds, self.rocket.perfect_finish)
        correction = roughness_correction(mach)
        rough_cache = {}
        body_cd = other_cd = 0.0
        min_x, max_x, max_r = math.inf, 0.0, 0.0
        for comp, calc in self._all_components():
            if self._skip(comp):
                continue
            k = FINISH_ROUGHNESS[comp.finish]
            if comp.finish not in rough_cache:
                # Java's k/0 -> Infinity; avoid ZeroDivisionError on a
                # degenerate zero-length aerodynamic bounding box
                if self.length_aero > 0:
                    limited = 0.032 * (k / self.length_aero) ** 0.2 * correction
                else:
                    limited = math.inf if k > 0 else 0.0
                rough_cache[comp.finish] = limited
            rough = rough_cache[comp.finish]
            if self.rocket.perfect_finish:
                comp_cf = rough if (reynolds > 1.0e6 and rough > cf) else cf
            else:
                comp_cf = max(cf, rough)
            if isinstance(calc, _SymmetricCalc):
                cd = calc.friction_cd(comp_cf, self.ref_area)
                body_cd += comp.instance_count * cd
                min_x = min(min_x, comp.abs_x)
                max_x = max(max_x, comp.abs_x + comp.length)
                max_r = max(max_r, comp.fore_radius, comp.aft_radius)
            elif isinstance(calc, (_FinSetCalc, _TubeFinSetCalc)):
                cd = calc.friction_cd(comp_cf, self.ref_area)
                other_cd += comp.instance_count * cd
            # launch lugs and rail buttons: friction 0
        if max_r > 0:
            fineness = (max_x - min_x + 0.0001) / max_r
            body_correction = 1 + 1.0 / (2 * fineness)
        else:
            body_correction = 1.0
        return other_cd + body_correction * body_cd

    def _pressure_cd(self, mach, reynolds):
        stag = stagnation_cd(mach)
        base = base_cd(mach)
        re_per_meter = reynolds / self.length_aero if self.length_aero > 0 else 0.0
        v_positive = mach > 0 and reynolds > 0
        total = 0.0
        fin_te_total = 0.0
        for comp, calc in self._all_components():
            if self._skip(comp):
                continue
            if isinstance(calc, _SymmetricCalc):
                cd = calc.pressure_cd(mach, stag, base, self.ref_area)
                total += comp.instance_count * cd
                # forward-facing shoulder / stagnation disk
                fore = comp.fore_radius
                if comp.length == 0:
                    fore = max(fore, comp.aft_radius)
                prev = self._previous_symmetric(comp)
                prev_radius = prev.aft_radius if prev is not None else 0.0
                if prev_radius < fore:
                    area = math.pi * (fore**2 - prev_radius**2)
                    total += comp.instance_count * stag * area / self.ref_area
            elif isinstance(calc, _FinSetCalc):
                total += comp.instance_count * calc.leading_edge_cd(
                    mach, stag, self.ref_area
                )
                fin_te_total += comp.instance_count * calc.trailing_edge_cd(
                    base, self.ref_area
                )
            elif isinstance(calc, _TubeFinSetCalc):
                total += comp.instance_count * calc.pressure_cd(
                    v_positive, re_per_meter, stag, base, self.ref_area
                )
            elif isinstance(comp, LaunchLug):
                cd = _tube_pressure_cd(
                    v_positive,
                    re_per_meter,
                    2 * comp.inner_radius,
                    comp.length,
                    math.pi * comp.inner_radius**2,
                    math.pi * (comp.radius**2 - comp.inner_radius**2),
                    FINISH_ROUGHNESS[comp.finish],
                    stag,
                    base,
                    self.ref_area,
                )
                total += comp.instance_count * cd
            elif isinstance(comp, RailButton):
                cd = _rail_button_pressure_cd(
                    comp, mach, re_per_meter, stag, self.ref_area
                )
                total += comp.instance_count * cd
        return total, fin_te_total

    def _base_cd(self, mach):
        base = base_cd(mach)
        total = 0.0
        for comp, calc in zip(self.symmetric, self._sym_calcs):
            if self._skip(comp):
                continue
            aft = comp.aft_radius
            if comp.length == 0:
                aft = max(comp.fore_radius, comp.aft_radius)
            nxt = self._next_symmetric(comp)
            next_radius = nxt.fore_radius if nxt is not None else 0.0
            if next_radius < aft:
                area = math.pi * (aft**2 - next_radius**2)
                total += comp.instance_count * base * area / self.ref_area
        return total

    def _override_cd(self):
        total = 0.0
        for comp, _ in self._all_components():
            if self._overridden(comp) and not self._overridden_by_ancestor(comp):
                total += comp.instance_count * comp.cd_override
        # stage-level overrides (ComponentAssembly path in OpenRocket)
        active = {c.stage for c in self.symmetric} | {c.stage for c in self.others}
        for stage, (stage_cd, _) in enumerate(self.rocket.stage_overrides):
            if stage_cd is not None and stage in active:
                total += stage_cd
        return total

    # -- iteration helpers -------------------------------------------------

    def _all_components(self):
        for comp, calc in zip(self.symmetric, self._sym_calcs):
            yield comp, calc
        for comp, calc in zip(self.others, self._other_calcs):
            yield comp, calc

    def _previous_symmetric(self, comp):
        i = self.symmetric.index(comp)
        return self.symmetric[i - 1] if i > 0 else None

    def _next_symmetric(self, comp):
        i = self.symmetric.index(comp)
        return self.symmetric[i + 1] if i + 1 < len(self.symmetric) else None

    # -- curve export ------------------------------------------------------

    def drag_curve(self, machs=None, aoa=0.0):
        """Cd(Mach) at sea-level ISA conditions (the exported curve).

        Reynolds follows ``Re(M) = M a L_aero / nu`` with ISA sea-level
        temperature and density; returns ``(machs, cds)``.
        """
        if machs is None:
            machs = [round(0.01 * i, 2) for i in range(1, 301)]
        density = SEA_LEVEL_PRESSURE / (GAS_CONSTANT * SEA_LEVEL_TEMPERATURE)
        sound = speed_of_sound(SEA_LEVEL_TEMPERATURE)
        nu = kinematic_viscosity(SEA_LEVEL_TEMPERATURE, density)
        cds = []
        for mach in machs:
            reynolds = mach * sound * self.length_aero / nu
            cds.append(self.evaluate(mach, reynolds, aoa).cd)
        return list(machs), cds
