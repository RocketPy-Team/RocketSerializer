"""Unit tests for the drag-model kernels against exact OpenRocket values."""

import math

import pytest

from rocketserializer.dragmodel.buildup import (
    _AXIAL_POLY_1,
    _AXIAL_POLY_2,
    axial_cd,
    base_cd,
    friction_coefficient,
    roughness_correction,
    stagnation_cd,
)
from rocketserializer.dragmodel.interpolators import (
    LinearInterpolator,
    eval_poly,
    poly_interpolator,
)


def test_stagnation_cd():
    # subsonic: 0.85 * (1 + M^2/4 + M^4/40)
    assert stagnation_cd(0.0) == pytest.approx(0.85)
    assert stagnation_cd(1.0) == pytest.approx(0.85 * (1 + 0.25 + 0.025))
    # supersonic branch at M=2
    assert stagnation_cd(2.0) == pytest.approx(
        0.85 * (1.84 - 0.76 / 4 + 0.166 / 16 + 0.035 / 64)
    )


def test_base_cd():
    assert base_cd(0.0) == pytest.approx(0.12)
    assert base_cd(1.0) == pytest.approx(0.25)
    assert base_cd(2.0) == pytest.approx(0.125)


def test_friction_coefficient_branches():
    # low-Reynolds constants
    assert friction_coefficient(0.0, 1e3) == pytest.approx(1.48e-2)
    assert friction_coefficient(0.0, 1e3, perfect_finish=True) == pytest.approx(1.33e-2)
    # turbulent formula at Re=1e7, M=0
    expected = 1.0 / (1.50 * math.log(1e7) - 5.6) ** 2
    assert friction_coefficient(0.0, 1e7) == pytest.approx(expected)
    # supersonic compressibility: c2 only
    m = 1.5
    expected = (1.0 / (1.50 * math.log(1e7) - 5.6) ** 2) / (1 + 0.15 * m**2) ** 0.58
    assert friction_coefficient(m, 1e7) == pytest.approx(expected)


def test_roughness_correction_continuous():
    # continuous across the blend window
    assert roughness_correction(0.9) == pytest.approx(1 - 0.1 * 0.81)
    assert roughness_correction(1.1) == pytest.approx(1 / (1 + 0.18 * 1.21), rel=1e-9)


def test_axial_poly_coefficients_match_openrocket():
    # exact doubles produced by OpenRocket's PolyInterpolator at class load
    assert _AXIAL_POLY_1 == pytest.approx(
        [-22.970602338418814, 10.223272370278785, 0.0, 1.0], rel=1e-12
    )
    assert _AXIAL_POLY_2 == pytest.approx(
        [
            -1.480006750190687,
            6.784940235048049,
            -10.062655893223182,
            4.334008218595031,
            0.7341792753994868,
        ],
        rel=1e-9,
    )


def test_axial_cd_multiplier():
    assert axial_cd(1.0, 0.0) == pytest.approx(1.0)
    assert axial_cd(1.0, 17 * math.pi / 180) == pytest.approx(1.3)
    assert axial_cd(1.0, math.pi / 2) == pytest.approx(0.0, abs=1e-12)
    # known interior value of poly2 (OpenRocket evaluation at aoa=0.5 rad)
    assert axial_cd(1.0, 0.5) == pytest.approx(1.141136518885295, rel=1e-9)
    # sign flip past 90 degrees
    assert axial_cd(1.0, math.pi - 0.1) == pytest.approx(-axial_cd(1.0, 0.1), rel=1e-12)


def test_linear_interpolator_clamps():
    interp = LinearInterpolator([1.0, 2.0], [10.0, 20.0])
    assert interp.get_value(0.0) == 10.0  # constant below
    assert interp.get_value(3.0) == 20.0  # constant above
    assert interp.get_value(1.5) == pytest.approx(15.0)


def test_poly_interpolator_hermite():
    # cubic through f(0)=1, f(1)=2 with zero slopes at both ends
    coeffs = poly_interpolator([0, 1], [0, 1], [], [1, 2, 0, 0])
    assert eval_poly(0.0, coeffs) == pytest.approx(1.0)
    assert eval_poly(1.0, coeffs) == pytest.approx(2.0)
    assert eval_poly(0.5, coeffs) == pytest.approx(1.5)  # Hermite midpoint
