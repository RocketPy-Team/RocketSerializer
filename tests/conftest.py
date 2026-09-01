from pathlib import Path

import pytest

from rocketserializer import ork_extractor
from rocketserializer._helpers import extract_ork_from_zip, parse_ork_file
from rocketserializer.openrocket_runtime import (
    OpenRocketSession,
    select_latest_openrocket_jar,
)

ROOT_DIR = Path(__file__).resolve().parents[1]

# All example rockets to test (name -> relative path from ROOT_DIR)
EXAMPLES = {
    "valetudo": "examples/ProjetoJupiter--Valetudo--2019",
    "ndrt": "examples/NDRT--Rocket--2020",
    "epfl": "examples/EPFL--BellaLui--2020",
    "wert": "examples/WERT--Prometheus--2022",
    "elliptical_fins": "examples/rocket_with_elliptical_fins",
    "alpha": "examples/Anonymous--Alpha",
    "beta": "examples/Anonymous--Beta",
    "gamma": "examples/Anonymous--Gamma",
    "delta": "examples/Anonymous--Delta",
    "epsilon": "examples/Anonymous--Epsilon",
    "zeta": "examples/Anonymous--Zeta",
    "eta": "examples/Anonymous--Eta",
    "theta": "examples/Anonymous--Theta",
    "iota": "examples/Anonymous--Iota",
    "kappa": "examples/Anonymous--Kappa",
    "lambda": "examples/Anonymous--Lambda",
    "mu": "examples/Anonymous--Mu",
    "nu": "examples/Anonymous--Nu",
    "xi": "examples/Anonymous--Xi",
    "omicron": "examples/Anonymous--Omicron",
    "pi": "examples/Anonymous--Pi",
    "rho": "examples/Anonymous--Rho",
    "sigma": "examples/Anonymous--Sigma",
}


def get_settings(ork_path, output_path, ork_document):
    bs, _ = parse_ork_file(ork_path)
    output_path.mkdir(parents=True, exist_ok=True)
    settings = ork_extractor(
        bs=bs,
        filepath=str(ork_path),
        output_folder=str(output_path),
        ork=ork_document,
    )
    return settings


# Pre-compute all settings at import time using a single OpenRocket session.
# When no JVM is available the acceptance fixtures are skipped, but the
# JVM-free test suites (tests/unit, tests/validation) still run.
_cached_settings = {}
_jvm_error = None

try:
    with OpenRocketSession(select_latest_openrocket_jar(ROOT_DIR), "OFF") as session:
        for name, rel_path in EXAMPLES.items():
            ork_filepath = ROOT_DIR / rel_path / "rocket.ork"
            ork_filepath = extract_ork_from_zip(ork_filepath, ork_filepath.parent)
            output_dir = ROOT_DIR / "tests" / "acceptance" / Path(rel_path).name
            ork_doc = session.load_doc(str(ork_filepath))
            _cached_settings[name] = get_settings(ork_filepath, output_dir, ork_doc)
except Exception as _error:  # pylint: disable=broad-except
    _jvm_error = _error


def _cached(name):
    if name not in _cached_settings:
        pytest.skip("OpenRocket JVM unavailable: %s" % _jvm_error)
    return _cached_settings[name]


# Create fixtures for each example
@pytest.fixture()
def valetudo_settings():
    return _cached("valetudo")


@pytest.fixture()
def ndrt_settings():
    return _cached("ndrt")


@pytest.fixture()
def epfl_settings():
    return _cached("epfl")


@pytest.fixture()
def wert_settings():
    return _cached("wert")


@pytest.fixture()
def elliptical_fins_settings():
    return _cached("elliptical_fins")


@pytest.fixture()
def alpha_settings():
    return _cached("alpha")


@pytest.fixture()
def beta_settings():
    return _cached("beta")


@pytest.fixture()
def gamma_settings():
    return _cached("gamma")


@pytest.fixture()
def delta_settings():
    return _cached("delta")


@pytest.fixture()
def epsilon_settings():
    return _cached("epsilon")


@pytest.fixture()
def zeta_settings():
    return _cached("zeta")


@pytest.fixture()
def eta_settings():
    return _cached("eta")


@pytest.fixture()
def theta_settings():
    return _cached("theta")


@pytest.fixture()
def iota_settings():
    return _cached("iota")


@pytest.fixture()
def kappa_settings():
    return _cached("kappa")


@pytest.fixture()
def lambda_settings():
    return _cached("lambda")


@pytest.fixture()
def mu_settings():
    return _cached("mu")


@pytest.fixture()
def nu_settings():
    return _cached("nu")


@pytest.fixture()
def xi_settings():
    return _cached("xi")


@pytest.fixture()
def omicron_settings():
    return _cached("omicron")


@pytest.fixture()
def pi_settings():
    return _cached("pi")


@pytest.fixture()
def rho_settings():
    return _cached("rho")


@pytest.fixture()
def sigma_settings():
    return _cached("sigma")
