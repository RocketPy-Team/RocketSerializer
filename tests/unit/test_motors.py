"""Unit tests for the JVM-free motor handling (.eng parsing + digests)."""

import math

import pytest

from rocketserializer.motors import (
    EngMotor,
    _finalize_thrust_curve,
    _mass_curve,
    _parse_delays,
    _remove_delay,
    motor_digest,
)


def test_parse_delays():
    assert _parse_delays("None") == []
    assert _parse_delays("none") == []
    assert _parse_delays("5-10-15-P") == [5.0, 10.0, 15.0, math.inf]
    assert _parse_delays("P") == [math.inf]
    # OpenRocket drops delays >= 99 and non-integer tokens
    assert _parse_delays("100") == []
    assert _parse_delays("5.5") == []


def test_remove_delay():
    assert _remove_delay("F32-5") == "F32"
    assert _remove_delay("1635K445-17A") == "1635K445-17A"  # not a pure delay
    assert _remove_delay("K550-P") == "K550"
    assert _remove_delay("L1031") == "L1031"


def test_finalize_thrust_curve_prepends_zero():
    time, thrust = _finalize_thrust_curve([0.1, 0.5, 1.0], [10.0, 20.0, 0.0])
    assert time[0] == 0.0 and thrust[0] == 0.0
    assert len(time) == 4


def test_finalize_thrust_curve_keeps_nonzero_start():
    time, thrust = _finalize_thrust_curve([0.0, 1.0], [370.0, 370.0])
    assert time == [0.0, 1.0]
    assert thrust == [370.0, 370.0]


def test_mass_curve_burns_propellant_proportionally():
    time = [0.0, 1.0, 2.0]
    thrust = [0.0, 100.0, 0.0]
    mass = _mass_curve(time, thrust, total_mass=2.0, propellant_mass=1.0)
    assert mass[0] == 2.0
    assert mass[-1] == pytest.approx(1.0)
    assert mass[1] == pytest.approx(1.5)  # half the impulse burned


def test_motor_digest_is_deterministic_and_ordered():
    digest = motor_digest(
        [
            ("TIME_ARRAY", [0.0, 1.0]),
            ("FORCE_PER_TIME", [0.0, 100.0]),
        ]
    )
    assert len(digest) == 32
    assert digest == motor_digest(
        [
            ("TIME_ARRAY", [0.0, 1.0]),
            ("FORCE_PER_TIME", [0.0, 100.0]),
        ]
    )
    with pytest.raises(ValueError):
        motor_digest(
            [
                ("FORCE_PER_TIME", [1.0]),
                ("TIME_ARRAY", [0.0]),
            ]
        )


def test_eng_motor_rasp_digest_matches_openrocket():
    """A real .eng motor reproduces the digest OpenRocket stored in the .ork.

    Data: a 106-point thrust curve (0..3.15 s, 30 ms steps) from a real team
    submission; OpenRocket 24.12 stored ``<digest>`` for this motor is the
    asserted MD5.  This pins the whole pipeline: parsing, curve finalization
    and the bit-exact ``MotorDigest`` port.
    """
    time = [round(0.03 * i, 2) for i in range(106)]
    # exact thrust samples from the submission (see husamsal.eng)
    thrust = [
        0.01,
        951.7623,
        963.835,
        975.7692,
        987.5544,
        999.1801,
        1010.6358,
        1021.9109,
        1032.9951,
        1043.8777,
        1054.5483,
        1064.9965,
        1075.212,
        1085.1847,
        1094.9043,
        1104.3611,
        1113.5451,
        1122.4467,
        1131.0566,
        1139.3655,
        1147.3644,
        1155.0447,
        1162.3979,
        1169.4157,
        1176.0905,
        1182.4146,
        1188.3808,
        1193.9823,
        1199.2127,
        1204.0658,
        1208.5361,
        1212.6182,
        1216.3073,
        1219.599,
        1222.4894,
        1224.9749,
        1227.0526,
        1228.7199,
        1229.9748,
        1230.8155,
        1231.2411,
        1231.2509,
        1230.8448,
        1230.0232,
        1228.7869,
        1227.1374,
        1225.0764,
        1222.6062,
        1219.7298,
        1216.4504,
        1212.7716,
        1208.6978,
        1204.2335,
        1199.3839,
        1194.1544,
        1188.551,
        1182.58,
        1176.248,
        1169.5622,
        1162.53,
        1155.159,
        1147.4575,
        1139.4337,
        1131.0964,
        1122.4544,
        1113.517,
        1104.2935,
        1094.7935,
        1085.027,
        1075.0038,
        1064.734,
        1054.228,
        1043.496,
        1032.5486,
        1021.3964,
        1010.0497,
        998.5194,
        986.8161,
        974.9503,
        962.9327,
        950.774,
        938.4845,
        926.0749,
        913.5555,
        900.9366,
        888.2284,
        875.4409,
        862.584,
        849.6676,
        836.7011,
        823.6941,
        810.6557,
        797.5951,
        784.5211,
        771.4422,
        758.3671,
        745.3038,
        732.2603,
        719.2443,
        706.2634,
        693.3248,
        680.4356,
        667.6024,
        654.8317,
        642.13,
        0.0,
    ]
    motor = EngMotor(
        designation="L1031",
        diameter=0.095,
        length=0.471,
        delays=[],
        propellant_mass=2.754322,
        total_mass=5.254322,
        manufacturer="husam",
        time=time,
        thrust=thrust,
    )
    assert motor.digests()["rasp"] == "2e3c9f8facba8acc33662b01b018ad5b"
