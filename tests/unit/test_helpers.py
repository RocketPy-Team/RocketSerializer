from pathlib import Path

import pytest

from rocketserializer._helpers import parse_ork_file


@pytest.mark.parametrize(
    "filepath",
    [
        "examples/ProjetoJupiter--Valetudo--2019/rocket.ork",
        "examples/NDRT--Rocket--2020/rocket.ork",
        "examples/EPFL--BellaLui--2020/rocket.ork",
    ],
)
def test_parse_ork_file(filepath: str):
    filepath = Path(filepath)
    bs, datapoints = parse_ork_file(filepath)
    assert bs
    assert datapoints
