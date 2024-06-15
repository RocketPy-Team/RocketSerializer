from pathlib import Path

import pytest

from rocketserializer.nb_builder import NotebookBuilder


@pytest.mark.parametrize(
    "parameters",
    [
        "examples/EPFL--BellaLui--2020/parameters.json",
        "examples/NDRT--Rocket--2020/parameters.json",
        "examples/ProjetoJupiter--Valetudo--2019/parameters.json",
        "examples/WERT--Prometheus--2022/parameters.json",
    ],
)
def test_notebook_builder_class(parameters):
    path = Path(parameters)
    nb_builder = NotebookBuilder(path)
    nb_builder.read()
    nb_builder.build(destination=path.parent)
    assert True
