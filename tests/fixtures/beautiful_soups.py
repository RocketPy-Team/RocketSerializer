import pytest
from bs4 import BeautifulSoup


@pytest.fixture
def bs_epfl_bellalui_2020():
    path = "examples/EPFL--BellaLui--2020/rocket.ork"
    with open(path, encoding="utf-8") as file:
        bs = BeautifulSoup(file, features="xml")
    return bs


@pytest.fixture
def bs_ndrt_rocket_2020():
    path = "examples/NDRT--Rocket--2020/rocket.ork"
    with open(path, encoding="utf-8") as file:
        bs = BeautifulSoup(file, features="xml")
    return bs


@pytest.fixture
def bs_projeto_jupiter_valetudo_2019():
    path = "examples/ProjetoJupiter--Valetudo--2019/rocket.ork"
    with open(path, encoding="utf-8") as file:
        bs = BeautifulSoup(file, features="xml")
    return bs


@pytest.fixture
def bs_wert_prometheus_2022():
    path = "examples/WERT--Prometheus--2022/rocket.ork"
    with open(path, encoding="utf-8") as file:
        bs = BeautifulSoup(file, features="xml")
    return bs
