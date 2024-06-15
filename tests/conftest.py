import json
import os

import orhelper
import pytest
from bs4 import BeautifulSoup

from rocketserializer import ork_extractor


def get_settings(filepath, output, ork):
    bs = BeautifulSoup(open(filepath, encoding="utf-8").read(), features="xml")

    if not os.path.exists(output):
        # create the output folder if it doesn't exist
        os.makedirs(output)

    settings = ork_extractor(
        bs=bs,
        filepath=filepath,
        output_folder=output,
        ork=ork,
        eng=None,
    )
    return settings


with orhelper.OpenRocketInstance("tests/OpenRocket-15.03.jar", "OFF") as instance:
    orh = orhelper.Helper(instance)

    # Valetudo 2019
    filepath = "examples/ProjetoJupiter--Valetudo--2019/rocket.ork"
    output = "tests/acceptance/ProjetoJupiter--Valetudo--2019/"
    ork = orh.load_doc(filepath)
    settings1 = get_settings(filepath, output, ork)
    with open(output + "parameters.json", "w", encoding="utf-8") as f:
        json.dump(settings1, f, indent=4, ensure_ascii=False)

    @pytest.fixture()
    def valetudo_settings():
        return settings1

    # NDRT 2020
    filepath = "examples/NDRT--Rocket--2020/rocket.ork"
    output = "tests/acceptance/NDRT--Rocket--2020/"
    ork = orh.load_doc(filepath)
    settings2 = get_settings(filepath, output, ork)
    with open(output + "parameters.json", "w", encoding="utf-8") as f:
        json.dump(settings2, f, indent=4, ensure_ascii=False)

    @pytest.fixture()
    def ndrt_settings():
        return settings2

    # Bella Lui 2020
    filepath = "examples/EPFL--BellaLui--2020/rocket.ork"
    output = "tests/acceptance/EPFL--BellaLui--2020/"
    ork = orh.load_doc(filepath)
    settings3 = get_settings(filepath, output, ork)
    with open(output + "parameters.json", "w", encoding="utf-8") as f:
        json.dump(settings3, f, indent=4, ensure_ascii=False)

    @pytest.fixture()
    def epfl_settings():
        return settings3
