import pytest

from rocketserializer.components.flight import search_launch_conditions


@pytest.mark.parametrize(
    "bs_fixture",
    [
        "bs_epfl_bellalui_2020",
        "bs_ndrt_rocket_2020",
        "bs_projeto_jupiter_valetudo_2019",
        "bs_wert_prometheus_2022",
    ],
)
def test_search_launch_conditions(bs_fixture, request):
    bs = request.getfixturevalue(bs_fixture)
    result = search_launch_conditions(bs)
    obtained_keys = result.keys()
    expected_keys = [
        "rail_length",
        "inclination",
        "heading",
    ]

    assert list(obtained_keys).sort() == expected_keys.sort()

    assert isinstance(result, dict)
    assert isinstance(result["rail_length"], (float, int))
    assert isinstance(result["inclination"], (float, int))
    assert isinstance(result["heading"], (float, int))

    assert result["rail_length"] >= 0
    assert result["inclination"] >= 0 and result["inclination"] <= 90
    assert result["heading"] >= 0 and result["heading"] <= 360
