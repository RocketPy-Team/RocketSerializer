"""Unit tests for the structure mass model (analytic cases, no JVM)."""

import math

import pytest
from bs4 import BeautifulSoup

from rocketserializer.massmodel import structure_mass_properties

BODY_TUBE_ROCKET = """<?xml version='1.0' encoding='utf-8'?>
<openrocket version="1.10" creator="OpenRocket 24.12">
<rocket><name>t</name><subcomponents><stage><name>s</name><subcomponents>
<bodytube><name>tube</name><finish>normal</finish>
<material type="bulk" density="1000.0">m</material>
<length>1.0</length><thickness>0.002</thickness><radius>0.05</radius>
</bodytube>
</subcomponents></stage></subcomponents></rocket></openrocket>"""


def _soup(xml):
    return BeautifulSoup(xml, features="xml")


def test_body_tube_mass_and_cg():
    properties = structure_mass_properties(_soup(BODY_TUBE_ROCKET))
    outer, inner, length, rho = 0.05, 0.048, 1.0, 1000.0
    expected = math.pi * (outer**2 - inner**2) * length * rho
    assert properties.mass == pytest.approx(expected, rel=1e-12)
    assert properties.cg_x == pytest.approx(0.5, abs=1e-12)
    # thin tube: Iyy ~ m L^2 / 12 dominates
    expected_iyy = expected * (3 * (outer**2 + inner**2) + length**2) / 12
    assert properties.longitudinal_inertia == pytest.approx(expected_iyy, rel=1e-9)
    expected_ixx = expected * (outer**2 + inner**2) / 2
    assert properties.rotational_inertia == pytest.approx(expected_ixx, rel=1e-9)


def test_mass_override_replaces_component_mass():
    xml = BODY_TUBE_ROCKET.replace(
        "<length>1.0</length>",
        "<overridemass>9.9</overridemass>"
        "<overridesubcomponentsmass>false</overridesubcomponentsmass>"
        "<length>1.0</length>",
    )
    properties = structure_mass_properties(_soup(xml))
    assert properties.mass == pytest.approx(9.9)
    assert properties.cg_x == pytest.approx(0.5)  # CG unchanged


def test_cg_override_is_relative_to_component_start():
    xml = BODY_TUBE_ROCKET.replace(
        "<length>1.0</length>",
        "<overridecg>0.2</overridecg>"
        "<overridesubcomponentscg>false</overridesubcomponentscg>"
        "<length>1.0</length>",
    )
    properties = structure_mass_properties(_soup(xml))
    assert properties.cg_x == pytest.approx(0.2)


def test_filled_thickness_literal():
    # OpenRocket serializes filled components as <thickness>filled</thickness>
    xml = BODY_TUBE_ROCKET.replace(
        "<thickness>0.002</thickness>", "<thickness>filled</thickness>"
    )
    properties = structure_mass_properties(_soup(xml))
    expected = math.pi * 0.05**2 * 1.0 * 1000.0
    assert properties.mass == pytest.approx(expected, rel=1e-12)


def test_mass_component_and_parachute():
    xml = BODY_TUBE_ROCKET.replace(
        "</bodytube>",
        """<subcomponents>
        <masscomponent><name>brick</name>
        <axialoffset method="top">0.1</axialoffset>
        <packedlength>0.2</packedlength><packedradius>0.02</packedradius>
        <mass>1.5</mass></masscomponent>
        <parachute><name>chute</name>
        <axialoffset method="top">0.5</axialoffset>
        <packedlength>0.1</packedlength><packedradius>0.03</packedradius>
        <material type="surface" density="0.067">nylon</material>
        <diameter>1.0</diameter><linecount>6</linecount>
        <linelength>1.0</linelength>
        <linematerial type="line" density="0.001">line</linematerial>
        </parachute></subcomponents></bodytube>""",
    )
    properties = structure_mass_properties(_soup(xml))
    tube = math.pi * (0.05**2 - 0.048**2) * 1.0 * 1000.0
    chute = math.pi * 0.5**2 * 0.067 + 6 * 1.0 * 0.001
    assert properties.mass == pytest.approx(tube + 1.5 + chute, rel=1e-9)
