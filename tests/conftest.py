from pathlib import Path

import pytest

from rocketserializer import ork_extractor
from rocketserializer._helpers import extract_ork_from_zip, parse_ork_file
from rocketserializer.openrocket_runtime import (
    OpenRocketSession,
    select_latest_openrocket_jar,
)

ROOT_DIR = Path(__file__).resolve().parents[1]


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


with OpenRocketSession(select_latest_openrocket_jar(ROOT_DIR), "OFF") as session:
    # Valetudo 2019
    valetudo_filepath = (
        ROOT_DIR / "examples" / "ProjetoJupiter--Valetudo--2019" / "rocket.ork"
    )
    valetudo_filepath = extract_ork_from_zip(
        valetudo_filepath, valetudo_filepath.parent
    )
    valetudo_output_dir = (
        ROOT_DIR / "tests" / "acceptance" / "ProjetoJupiter--Valetudo--2019"
    )
    valetudo_doc = session.load_doc(str(valetudo_filepath))
    settings1 = get_settings(valetudo_filepath, valetudo_output_dir, valetudo_doc)

    @pytest.fixture()
    def valetudo_settings():
        return settings1

    # NDRT 2020
    ndrt_filepath = ROOT_DIR / "examples" / "NDRT--Rocket--2020" / "rocket.ork"
    ndrt_filepath = extract_ork_from_zip(ndrt_filepath, ndrt_filepath.parent)
    ndrt_output_dir = ROOT_DIR / "tests" / "acceptance" / "NDRT--Rocket--2020"
    ndrt_doc = session.load_doc(str(ndrt_filepath))
    settings2 = get_settings(ndrt_filepath, ndrt_output_dir, ndrt_doc)

    @pytest.fixture()
    def ndrt_settings():
        return settings2

    # Bella Lui 2020
    epfl_filepath = ROOT_DIR / "examples" / "EPFL--BellaLui--2020" / "rocket.ork"
    epfl_filepath = extract_ork_from_zip(epfl_filepath, epfl_filepath.parent)
    epfl_output_dir = ROOT_DIR / "tests" / "acceptance" / "EPFL--BellaLui--2020"
    epfl_doc = session.load_doc(str(epfl_filepath))
    settings3 = get_settings(epfl_filepath, epfl_output_dir, epfl_doc)

    @pytest.fixture()
    def epfl_settings():
        return settings3
