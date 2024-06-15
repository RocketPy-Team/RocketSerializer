import pytest

from rocketserializer.components.environment import search_environment


@pytest.mark.parametrize(
    "bs_fixture",
    [
        "bs_epfl_bellalui_2020",
        "bs_ndrt_rocket_2020",
        "bs_projeto_jupiter_valetudo_2019",
        "bs_wert_prometheus_2022",
    ],
)
def test_search_environment(bs_fixture, request):
    bs = request.getfixturevalue(bs_fixture)
    result = search_environment(bs)
    obtained_keys = result.keys()
    expected_keys = [
        "latitude",
        "longitude",
        "elevation",
        "wind_average",
        "wind_turbulence",
        "geodetic_method",
        "base_temperature",
        "base_pressure",
        "date",
    ]

    assert list(obtained_keys).sort() == expected_keys.sort()

    assert isinstance(result, dict)
    assert isinstance(result["latitude"], (float, int))
    assert isinstance(result["longitude"], (float, int))
    assert isinstance(result["elevation"], (float, int))
    assert isinstance(result["wind_average"], (float, int))
    assert isinstance(result["wind_turbulence"], (float, int))
    assert isinstance(result["geodetic_method"], str)
    assert isinstance(result["base_temperature"], (float, int, type(None)))
    assert isinstance(result["base_pressure"], (float, int, type(None)))
    assert isinstance(result["date"], (str, type(None)))

    assert result["latitude"] >= -90 and result["latitude"] <= 90
    assert result["longitude"] >= -180 and result["longitude"] <= 180
    assert result["elevation"] >= 0
    assert result["geodetic_method"] in ["wgs84", "spherical"]
