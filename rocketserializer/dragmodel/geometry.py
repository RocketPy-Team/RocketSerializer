"""Geometry engine: component profiles and the integrals the drag model needs.

Ports, from OpenRocket 24.12:

- ``Transition.Shape.getRadius`` -- the six nose/transition profile equations,
  including clipped transitions (``Transition.getRadius`` + ``calculateClip``);
- ``SymmetricComponent.calculateProperties`` -- the 128-frustum integration
  producing wetted area, planform area and full (filled) volume;
- ``FinSet``/``FinSetCalc`` geometry -- fin outline points, root (mount)
  points, planform area via the curve integral, and the 48-strip chord scan
  yielding the MAC length and the mean leading-edge sweep cosine.

All lengths are meters, areas m^2, angles radians.
"""

import math

EPSILON = 1e-8  # MathUtil.EPSILON
CLIP_PRECISION = 0.0001  # Transition.CLIP_PRECISION
DIVISIONS_BODY = 128  # SymmetricComponent.DIVISIONS
DIVISIONS_FIN = 48  # FinSetCalc.DIVISIONS
MAX_ROOT_DIVISIONS = 100  # FinSet.MAX_ROOT_DIVISIONS


def safe_sqrt(value):
    """``MathUtil.safeSqrt``: 0 for negative arguments."""
    if value < 0:
        return 0.0
    return math.sqrt(value)


def _java_equals(a, b, epsilon=EPSILON):
    """``MathUtil.equals``: relative comparison with a near-zero fallback."""
    absb = abs(b)
    if absb < epsilon / 2:
        return abs(a) < epsilon / 2
    return abs(a - b) < epsilon * absb


# ---------------------------------------------------------------------------
# Transition shape profiles (radius 0 at x=0 growing to `radius` at x=length)
# ---------------------------------------------------------------------------


def shape_radius(shape, x, radius, length, param):
    """``Transition.Shape.getRadius`` for one shape, exact port."""
    if shape == "conical":
        return radius * x / length
    if shape == "ogive":
        if length < radius:
            # "Impossible to calculate ogive for length < radius, scale instead"
            x = x * radius / length
            length = radius
        if param < 0.001:  # Shape.MINFEATURE
            return radius * x / length
        big_r = safe_sqrt(
            (length * length + radius * radius)
            * (((2 - param) * length) ** 2 + (param * radius) ** 2)
            / (4 * (param * radius) ** 2)
        )
        big_l = length / param
        y0 = safe_sqrt(big_r * big_r - big_l * big_l)
        return safe_sqrt(big_r * big_r - (big_l - x) ** 2) - y0
    if shape == "ellipsoid":
        x = x * radius / length
        return safe_sqrt(2 * radius * x - x * x)
    if shape == "power":
        if param <= 0.00001:
            return 0.0 if x <= 0.00001 else radius
        return radius * (x / length) ** param
    if shape == "parabolic":
        xl = x / length
        return radius * ((2 * xl - param * xl * xl) / (2 - param))
    if shape == "haack":
        theta = math.acos(1 - 2 * x / length)
        if abs(param) < EPSILON:
            return radius * safe_sqrt((theta - math.sin(2 * theta) / 2) / math.pi)
        return radius * safe_sqrt(
            (theta - math.sin(2 * theta) / 2 + param * math.sin(theta) ** 3) / math.pi
        )
    raise ValueError("unsupported transition shape: %s" % shape)


#: shapes whose transitions are clipped by default (Shape.isClippable)
CLIPPABLE_SHAPES = frozenset(["ellipsoid", "power", "haack"])


def calculate_clip(shape, r1, r2, length, param):
    """``Transition.calculateClip``: bisect for the virtual clip length."""
    if r1 > r2:
        r1, r2 = r2, r1
    if r1 == 0:
        return 0.0
    if length <= 0:
        return 0.0
    # grow the bracket
    lo, hi = 0.0, length
    n = 0
    while shape_radius(shape, hi, r2, hi + length, param) - r1 < 0:
        lo = hi
        hi *= 2
        n += 1
        if n > 10:
            break
    # bisect
    while hi - lo > CLIP_PRECISION:
        mid = (lo + hi) / 2
        if shape_radius(shape, mid, r2, mid + length, param) - r1 > 0:
            hi = mid
        else:
            lo = mid
        # the Java loop recomputes clipLength as (min+max)/2 on entry; the
        # final returned value is the last midpoint
    return (lo + hi) / 2


def transition_radius_function(fore_radius, aft_radius, length, shape, param, clipped):
    """Return ``r(x)`` for a transition/nose cone (``Transition.getRadius``).

    Handles the boattail mirror (fore > aft), clipped transitions, and the
    non-clipped scaled profile sitting on the fore radius.
    """
    clip_length = None

    def radius(x):
        nonlocal clip_length
        if x < 0:
            return fore_radius
        if x >= length:
            return aft_radius
        r1, r2 = fore_radius, aft_radius
        xx = x
        if r1 > r2:
            xx = length - x
            r1, r2 = r2, r1
        if r1 == r2:
            return r1
        if clipped and shape in CLIPPABLE_SHAPES:
            if clip_length is None:
                clip_length = calculate_clip(shape, r1, r2, length, param)
            return shape_radius(
                shape, clip_length + xx, r2, clip_length + length, param
            )
        return r1 + shape_radius(shape, xx, r2 - r1, length, param)

    return radius


# ---------------------------------------------------------------------------
# SymmetricComponent.calculateProperties (outer-surface part)
# ---------------------------------------------------------------------------


def integrate_body(radius_fn, length):
    """128-frustum integration of a body profile, exact port.

    Returns ``(wet_area, planform_area, planform_center, full_volume)``.
    """
    if length < EPSILON:
        return 0.0, 0.0, 0.0, 0.0
    wet_area = 0.0
    plan_area = 0.0
    plan_center = 0.0
    full_volume = 0.0
    for n in range(DIVISIONS_BODY):
        x1 = n * length / DIVISIONS_BODY
        x2 = (n + 1) * length / DIVISIONS_BODY
        step = x2 - x1
        r1 = radius_fn(x1)
        r2 = radius_fn(x2)
        full_volume += step * (r1 * r1 + r1 * r2 + r2 * r2)  # (3/pi)x volume
        wet_area += (r1 + r2) * math.sqrt((r1 - r2) ** 2 + step * step)
        d_area = step * (r1 + r2)
        plan_area += d_area
        plan_center += d_area * x1 + 2.0 * step * step * (r1 / 6.0 + r2 / 3.0)
    if plan_area > 0:
        plan_center /= plan_area
    full_volume *= math.pi / 3
    wet_area *= math.pi
    return wet_area, plan_area, plan_center, full_volume


# ---------------------------------------------------------------------------
# Fin geometry
# ---------------------------------------------------------------------------


def trapezoid_fin_points(root_chord, tip_chord, sweep, height, root_points):
    """``TrapezoidFinSet.getFinPoints`` (fin-front frame, y=0 at root)."""
    points = [(0.0, 0.0), (sweep, height)]
    if tip_chord > 0.0001:
        points.append((sweep + tip_chord, height))
    points.append((max(root_chord, 0.0001), 0.0))
    if len(root_points) > 1:
        points[0] = root_points[0]
        points[-1] = root_points[-1]
    return points


def elliptical_fin_points(root_chord, height):
    """``EllipticalFinSet.getFinPoints``: 30-segment half ellipse."""
    n = 30  # EllipticalFinSet.POINTS - 1  (POINTS = 31 in every OR release)
    points = []
    for i in range(n + 1):
        a = math.pi - math.pi * i / n
        x = root_chord * (math.cos(a) + 1) / 2
        y = height * math.sin(a)
        points.append((x, y))
    return points


def mount_points(parent_radius_fn, parent_length, x_start, x_end, x_off, y_off, curved):
    """``FinSet.getMountPoints``: sample the parent surface under the fin root.

    ``curved`` is True when the parent is a non-conical transition (fin cant is
    always zero in this port, matching every LASC design).
    """
    interval = x_end - x_start
    division_count = 1
    if curved:
        division_count = min(MAX_ROOT_DIVISIONS, math.ceil(interval / 0.0025))
    x_inc = interval / division_count
    points = []
    x = x_start
    for _ in range(division_count + 1):
        points.append((x, parent_radius_fn(x)))
        x += x_inc
    # extra points when the fin overhangs the parent ends
    if x_start < 0 < x_end:
        _insert_point_by_x(points, 0.0, points[0][1])
    if x_end > parent_length > x_start:
        _insert_point_by_x(points, parent_length, points[-1][1])
    # snap the last point to the parent end when within rounding error
    lx, ly = points[-1]
    if abs(lx - parent_length) < EPSILON:
        points[-1] = (parent_length, ly)
    if abs(x_off) + abs(y_off) > EPSILON:
        points = [(px + x_off, py + y_off) for px, py in points]
    return points


def _insert_point_by_x(points, x, y):
    for px, _ in points:
        if abs(px - x) < EPSILON:
            return
    for i, (px, _) in enumerate(points):
        if px > x:
            points.insert(i, (x, y))
            return
    points.append((x, y))


def curve_integral_area(points):
    """|area| under a closed piecewise-linear curve (``calculateCurveIntegral``)."""
    area = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        area += (x2 - x1) * (y1 + y2) * 0.5
    return abs(area)


class FinGeometry:
    """The drag-relevant fin-set geometry (``FinSetCalc.calculateFinGeometry``).

    Attributes: ``span``, ``fin_area`` (single-fin planform), ``mac_length``,
    ``cos_gamma_lead`` (mean leading-edge sweep cosine).
    """

    def __init__(self, fin_points, root_points, span, planform_area):
        self.span = span
        self.fin_area = planform_area
        points = fin_points + list(reversed(root_points))
        lead = [math.inf] * DIVISIONS_FIN
        trail = [-math.inf] * DIVISIONS_FIN
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            if _java_equals(y1, y2, 0.001):  # skip near-horizontal segments
                continue
            i1 = int(y1 * 1.0001 / span * (DIVISIONS_FIN - 1))
            i2 = int(y2 * 1.0001 / span * (DIVISIONS_FIN - 1))
            i1 = min(max(i1, 0), DIVISIONS_FIN - 1)
            i2 = min(max(i2, 0), DIVISIONS_FIN - 1)
            if i1 > i2:
                i1, i2 = i2, i1
            for i in range(i1, i2 + 1):
                y = i * span / (DIVISIONS_FIN - 1)
                x = (y - y2) / (y1 - y2) * x1 + (y1 - y) / (y1 - y2) * x2
                x = min(max(x, min(x1, x2)), max(x1, x2))
                lead[i] = min(lead[i], x)
                trail[i] = max(trail[i], x)
        for i in range(DIVISIONS_FIN):
            if not (math.isfinite(lead[i]) and math.isfinite(trail[i])):
                lead[i] = 0.0
                trail[i] = 0.0

        mac_length = 0.0
        area = 0.0
        cos_gamma_lead = 0.0
        dy = span / (DIVISIONS_FIN - 1)
        for i in range(DIVISIONS_FIN):
            chord = trail[i] - lead[i]
            mac_length += chord * chord
            area += chord
            if i > 0:
                dx = lead[i] - lead[i - 1]
                hyp = math.sqrt(dx * dx + dy * dy)
                if hyp != 0:
                    cos_gamma_lead += dy / hyp
        mac_length *= dy
        area *= dy
        if area > EPSILON:
            mac_length /= area
        else:
            mac_length = 0.0
        cos_gamma_lead /= DIVISIONS_FIN - 1
        self.mac_length = mac_length
        self.cos_gamma_lead = cos_gamma_lead
