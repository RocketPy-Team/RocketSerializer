"""Faithful ports of OpenRocket's two interpolator utilities.

``LinearInterpolator`` reproduces ``util/LinearInterpolator.java``: piecewise
linear between sorted knots, **constant** extrapolation outside the knot range,
duplicate x overwrites.  ``poly_interpolator`` reproduces
``util/PolyInterpolator.java``: a polynomial matching function values and
derivatives at given points (used for the CD->CA multiplier and the
conical/ogive transonic pressure-drag curve).
"""

import bisect


class LinearInterpolator:
    """Piecewise-linear interpolator with constant extrapolation.

    Mirrors OpenRocket's ``LinearInterpolator`` (TreeMap-backed): below the
    first knot the first value is returned, above the last knot the last value.
    """

    def __init__(self, x_points=None, y_points=None):
        self._map = {}
        if x_points is not None:
            for x, y in zip(x_points, y_points):
                self._map[x] = y
        self._rebuild()

    def _rebuild(self):
        self._xs = sorted(self._map)
        self._ys = [self._map[x] for x in self._xs]

    def add_point(self, x, y):
        """Add a knot (duplicate x overwrites, as in the Java TreeMap)."""
        self._map[x] = y
        self._rebuild()

    def add_points(self, x_points, y_points):
        for x, y in zip(x_points, y_points):
            self._map[x] = y
        self._rebuild()

    def get_value(self, x):
        """Interpolated value at ``x``, clamped to the end values outside."""
        xs = self._xs
        if not xs:
            raise ValueError("empty interpolator")
        if x <= xs[0]:
            return self._ys[0]
        if x >= xs[-1]:
            return self._ys[-1]
        i = bisect.bisect_left(xs, x)
        if xs[i] == x:
            return self._ys[i]
        x1, x2 = xs[i - 1], xs[i]
        y1, y2 = self._ys[i - 1], self._ys[i]
        return (x - x1) / (x2 - x1) * (y2 - y1) + y1

    def x_points(self):
        """The knot x-coordinates in ascending order."""
        return list(self._xs)


def poly_interpolator(value_xs, deriv_xs=(), deriv2_xs=(), values=()):
    """Solve for the polynomial matching values/derivatives at given points.

    Port of ``PolyInterpolator``: the polynomial order equals the total number
    of constraints.  ``values`` lists the constraint values in the same order
    as the constraint points (all function values first, then first
    derivatives, then second derivatives).

    Returns the coefficients highest power first, as the Java class does.
    """
    groups = [list(value_xs), list(deriv_xs), list(deriv2_xs)]
    n = sum(len(g) for g in groups)
    values = list(values)
    if len(values) != n:
        raise ValueError("constraint count mismatch")

    # Build the constraint matrix exactly like PolyInterpolator.java:
    # coefficients ordered highest power first; a j-th-derivative row at point
    # p has entries p^(n-1-j-col) * falling-factorial(col) for col <= n-1-j.
    matrix = [[0.0] * n for _ in range(n)]
    mul = [1.0] * n
    row = 0
    for j, group in enumerate(groups):
        if j > 0:
            # update falling-factorial multipliers when moving to derivative j
            for i in range(n):
                mul[i] *= n - i - j
        for p in group:
            x = 1.0
            for col in range(n - 1 - j, -1, -1):
                matrix[row][col] = x * mul[col]
                x *= p
            row += 1

    return _solve(matrix, values)


def _solve(matrix, rhs):
    """Solve the linear system by Gaussian elimination with partial pivoting."""
    n = len(rhs)
    a = [list(r) + [v] for r, v in zip(matrix, rhs)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if a[pivot][col] == 0.0:
            raise ValueError("singular constraint matrix")
        a[col], a[pivot] = a[pivot], a[col]
        for r in range(col + 1, n):
            f = a[r][col] / a[col][col]
            for c in range(col, n + 1):
                a[r][c] -= f * a[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        s = a[r][n] - sum(a[r][c] * x[c] for c in range(r + 1, n))
        x[r] = s / a[r][r]
    return x


def eval_poly(x, coefficients):
    """Evaluate a highest-power-first polynomial, as ``PolyInterpolator.eval``.

    The Java implementation accumulates powers from the constant term up; the
    same order is kept here.
    """
    v = 1.0
    result = 0.0
    for i in range(len(coefficients) - 1, -1, -1):
        result += coefficients[i] * v
        v *= x
    return result
