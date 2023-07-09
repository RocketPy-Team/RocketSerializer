import json
import pytest


@pytest.mark.parametrize(
    "expected_results_file, fixture",
    [
        (
            "examples/ProjetoJupiter--Valetudo--2019/parameters.json",
            "valetudo_settings",
        ),
        ("examples/NDRT--Rocket--2020/parameters.json", "ndrt_settings"),
        ("examples/EPFL--BellaLui--2020/parameters.json", "epfl_settings"),
    ],
)
def test_ork_extractor(expected_results_file, fixture, request):
    # load the expected results
    with open(expected_results_file, "r") as f:
        expected_results = json.load(f)

    # get the settings from the fixture
    settings = request.getfixturevalue(fixture)

    # assert all the keys are equal
    assert set(settings.keys()) == set(expected_results.keys())

    # remove sensitive keys
    settings, expected_results = remove_sensitive_keys(settings, expected_results)

    # assert all the values are equal
    # for key in settings.keys():
    #     if isinstance(settings[key], dict):
    #         for sub_key in settings[key].keys():
    #             assert settings[key][sub_key] == expected_results[key][sub_key]
    #     else:
    #         assert settings[key] == expected_results[key]


def remove_sensitive_keys(settings, expected):
    """Remove sensitive keys from the settings and expected_results dicts. This
    is important to avoid problems with the paths to the files that are saved
    when the tests are run.

    Parameters
    ----------
    settings : dict
        The
    expected : dict
        _description_

    Returns
    -------
    (settings, expected) : tuple of dicts
        _description_
    """
    settings["id"].pop("filepath")
    settings["id"].pop("comment")
    settings["id"].pop("designer")
    settings["rocket"].pop("drag_curve")
    settings["motors"].pop("thrust_source")

    expected["id"].pop("filepath")
    expected["id"].pop("comment")
    expected["id"].pop("designer")
    expected["rocket"].pop("drag_curve")
    expected["motors"].pop("thrust_source")
    return settings, expected
