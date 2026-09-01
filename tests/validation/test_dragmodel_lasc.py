"""External validation against the LASC 2026 submission corpus (not shipped).

Point ``ROCKETSERIALIZER_LASC_DATA`` at the LASC-2026-data checkout to enable.
Every ``uptodate`` simulation branch in the corpus must match the drag model
at stored-data precision (files carry 3 decimal places).  ``outdated`` /
``loaded`` / ``cantrun`` sims are skipped: their stored rows were produced by
an older geometry and OpenRocket itself would not reproduce them.
"""

import os

import pytest

from rocketserializer.dragmodel.compare import compare_file

LASC_DATA = os.environ.get("ROCKETSERIALIZER_LASC_DATA")

pytestmark = pytest.mark.skipif(
    LASC_DATA is None, reason="ROCKETSERIALIZER_LASC_DATA not set"
)


def _lasc_ork_files():
    if LASC_DATA is None:
        return []
    import glob

    paths = glob.glob(
        os.path.join(LASC_DATA, "Mission *", "**", "*.ork"), recursive=True
    )
    return sorted(p for p in paths if "__MACOSX" not in p and os.path.isfile(p))


def test_every_uptodate_sim_matches():
    files = _lasc_ork_files()
    assert files, "no .ork files under ROCKETSERIALIZER_LASC_DATA"
    checked = 0
    failures = []
    for path in files:
        try:
            comparisons = compare_file(path, max_rows=200)
        except Exception as error:  # pylint: disable=broad-except
            failures.append("%s: %s" % (path, error))
            continue
        for c in comparisons:
            if c.sim_status != "uptodate":
                continue
            checked += 1
            for column, error in c.max_error.items():
                if error > 2e-3:
                    failures.append(
                        "%s :: %s max|d %s|=%.5f" % (path, c.sim_name, column, error)
                    )
    assert checked > 50, "expected many uptodate branches, got %d" % checked
    assert not failures, "\n".join(failures)
