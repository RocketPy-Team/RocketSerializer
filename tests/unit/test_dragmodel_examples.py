"""Acceptance: replay stored sim rows of shipped example rockets, no JVM.

Only examples whose stored data the drag model is expected to reproduce are
used: simple single-body designs (no boosters/pods) saved by OpenRocket
versions whose drag model matches 22.02+.  Each stored ascent datapoint's
(Mach, Reynolds, AoA) is replayed and the drag-coefficient columns compared;
stored values carry 3 decimal places, so 2e-3 absolute is a strict bound.
"""

import math
from pathlib import Path

import pytest

from rocketserializer.dragmodel.buildup import DragBuildup
from rocketserializer.dragmodel.components import load_rocket
from rocketserializer.dragmodel.simdata import load_sim_branches

EXAMPLES = Path(__file__).parent.parent.parent / "examples"

MATCHING_EXAMPLES = [
    "Anonymous--Alpha",
    "Anonymous--Sigma",
    "NDRT--Rocket--2020",
]


@pytest.mark.parametrize("example", MATCHING_EXAMPLES)
def test_replayed_drag_matches_stored_sim(example):
    path = EXAMPLES / example / "rocket.ork"
    rocket = load_rocket(path)
    buildup = DragBuildup(rocket)
    _, branches = load_sim_branches(path)
    rows_checked = 0
    for branch in branches:
        if branch.sim_status.startswith("extension:"):
            continue
        for row in branch.barrowman_rows()[::5]:
            aoa = row.get("aoa", 0.0)
            if math.isnan(aoa):
                aoa = 0.0
            result = buildup.evaluate(row["mach"], row["reynolds"], aoa)
            assert result.cd == pytest.approx(row["cd"], abs=2e-3)
            assert result.friction == pytest.approx(row["friction_cd"], abs=2e-3)
            assert result.pressure == pytest.approx(row["pressure_cd"], abs=2e-3)
            assert result.base == pytest.approx(row["base_cd"], abs=2e-3)
            rows_checked += 1
    assert rows_checked > 50
