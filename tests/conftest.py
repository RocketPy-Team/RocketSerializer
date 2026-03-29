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
}


def get_settings(ork_filepath, output_dir, ork_document):
    bs, _ = parse_ork_file(ork_filepath)
    output_dir.mkdir(parents=True, exist_ok=True)
    settings = ork_extractor(
        bs=bs,
        filepath=str(ork_filepath),
        output_folder=str(output_dir),
        ork=ork_document,
    )
    return settings


# Pre-compute all settings at import time using a single OpenRocket session
_cached_settings = {}

with OpenRocketSession(select_latest_openrocket_jar(ROOT_DIR), "OFF") as session:
    for name, rel_path in EXAMPLES.items():
        ork_filepath = ROOT_DIR / rel_path / "rocket.ork"
        ork_filepath = extract_ork_from_zip(ork_filepath, ork_filepath.parent)
        output_dir = ROOT_DIR / "tests" / "acceptance" / Path(rel_path).name
        ork_doc = session.load_doc(str(ork_filepath))
        _cached_settings[name] = get_settings(ork_filepath, output_dir, ork_doc)


# Create fixtures for each example
@pytest.fixture()
def valetudo_settings():
    return _cached_settings["valetudo"]


@pytest.fixture()
def ndrt_settings():
    return _cached_settings["ndrt"]


@pytest.fixture()
def epfl_settings():
    return _cached_settings["epfl"]


@pytest.fixture()
def wert_settings():
    return _cached_settings["wert"]


@pytest.fixture()
def elliptical_fins_settings():
    return _cached_settings["elliptical_fins"]


@pytest.fixture()
def alpha_settings():
    return _cached_settings["alpha"]


@pytest.fixture()
def beta_settings():
    return _cached_settings["beta"]


@pytest.fixture()
def gamma_settings():
    return _cached_settings["gamma"]


@pytest.fixture()
def delta_settings():
    return _cached_settings["delta"]
