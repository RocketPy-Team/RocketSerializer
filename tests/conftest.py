from pathlib import Path

import pytest

from rocketserializer import ork_extractor
from rocketserializer._helpers import extract_ork_from_zip, parse_ork_file
from rocketserializer.openrocket_runtime import (
    OpenRocketSession,
    select_latest_openrocket_jar,
)

ROOT_DIR = Path(__file__).resolve().parents[1]


def get_settings(filepath, output, ork):
    bs, _ = parse_ork_file(filepath)

    output.mkdir(parents=True, exist_ok=True)

    settings = ork_extractor(
        bs=bs,
        filepath=str(filepath),
        output_folder=str(output),
        ork=ork,
    )
    return settings


with OpenRocketSession(select_latest_openrocket_jar(ROOT_DIR), "OFF") as session:

    # Valetudo 2019
    filepath = ROOT_DIR / "examples" / "ProjetoJupiter--Valetudo--2019" / "rocket.ork"
    filepath = extract_ork_from_zip(filepath, filepath.parent)
    output = ROOT_DIR / "tests" / "acceptance" / "ProjetoJupiter--Valetudo--2019"
    ork = session.load_doc(str(filepath))
    settings1 = get_settings(filepath, output, ork)

    @pytest.fixture()
    def valetudo_settings():
        return settings1

    # NDRT 2020
    filepath = ROOT_DIR / "examples" / "NDRT--Rocket--2020" / "rocket.ork"
    filepath = extract_ork_from_zip(filepath, filepath.parent)
    output = ROOT_DIR / "tests" / "acceptance" / "NDRT--Rocket--2020"
    ork = session.load_doc(str(filepath))
    settings2 = get_settings(filepath, output, ork)

    @pytest.fixture()
    def ndrt_settings():
        return settings2

    # Bella Lui 2020
    filepath = ROOT_DIR / "examples" / "EPFL--BellaLui--2020" / "rocket.ork"
    filepath = extract_ork_from_zip(filepath, filepath.parent)
    output = ROOT_DIR / "tests" / "acceptance" / "EPFL--BellaLui--2020"
    ork = session.load_doc(str(filepath))
    settings3 = get_settings(filepath, output, ork)

    @pytest.fixture()
    def epfl_settings():
        return settings3
