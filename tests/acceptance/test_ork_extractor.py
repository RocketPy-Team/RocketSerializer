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
        ("examples/WERT--Prometheus--2022/parameters.json", "wert_settings"),
        (
            "examples/rocket_with_elliptical_fins/parameters.json",
            "elliptical_fins_settings",
        ),
        ("examples/Anonymous--Alpha/parameters.json", "alpha_settings"),
        ("examples/Anonymous--Beta/parameters.json", "beta_settings"),
        ("examples/Anonymous--Gamma/parameters.json", "gamma_settings"),
        ("examples/Anonymous--Delta/parameters.json", "delta_settings"),
        ("examples/Anonymous--Epsilon/parameters.json", "epsilon_settings"),
        ("examples/Anonymous--Zeta/parameters.json", "zeta_settings"),
        ("examples/Anonymous--Eta/parameters.json", "eta_settings"),
        ("examples/Anonymous--Theta/parameters.json", "theta_settings"),
        ("examples/Anonymous--Iota/parameters.json", "iota_settings"),
        ("examples/Anonymous--Kappa/parameters.json", "kappa_settings"),
        ("examples/Anonymous--Lambda/parameters.json", "lambda_settings"),
        ("examples/Anonymous--Mu/parameters.json", "mu_settings"),
        ("examples/Anonymous--Nu/parameters.json", "nu_settings"),
        ("examples/Anonymous--Xi/parameters.json", "xi_settings"),
        ("examples/Anonymous--Omicron/parameters.json", "omicron_settings"),
        ("examples/Anonymous--Pi/parameters.json", "pi_settings"),
        ("examples/Anonymous--Rho/parameters.json", "rho_settings"),
        ("examples/Anonymous--Sigma/parameters.json", "sigma_settings"),
    ],
)
def test_ork_extractor(expected_results_file, fixture, request):
    # load the expected results
    with open(expected_results_file, "r", encoding="utf-8") as f:
        expected_results = json.load(f)

    # get the settings from the fixture
    settings = request.getfixturevalue(fixture)

    # assert all the keys are equal
    assert set(settings.keys()) == set(expected_results.keys())

    # remove sensitive keys
    settings, expected_results = remove_sensitive_keys(settings, expected_results)


def remove_sensitive_keys(settings, expected):
    """Remove sensitive keys from the settings and expected_results dicts. This
    is important to avoid problems with the paths to the files that are saved
    when the tests are run.

    Parameters
    ----------
    settings : dict
        The settings extracted by the ork_extractor.
    expected : dict
        The expected settings loaded from parameters.json.

    Returns
    -------
    (settings, expected) : tuple of dicts
        The settings and expected dicts without the sensitive keys.
    """
    for d in [settings, expected]:
        d["id"].pop("filepath", None)
        d["id"].pop("comment", None)
        d["id"].pop("designer", None)
        d["rocket"].pop("drag_curve", None)
        d["motors"].pop("thrust_source", None)
    return settings, expected
