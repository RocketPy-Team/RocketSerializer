"""Compare the drag build-up against the simulation data stored in .ork files.

For every stored ascent-phase datapoint the stored ``(Mach, Reynolds, AoA)``
is replayed through :class:`DragBuildup` and the computed friction / pressure
/ base / total / axial drag coefficients are compared against the stored
columns.  Values in files saved by OpenRocket <= 24.12 carry only three
decimal places, so the stored CD has a ~5e-4 quantization floor and the
rounded Mach/Reynolds/AoA inputs can propagate up to ~1e-3 more on steep
curve regions -- agreement within ~1e-3 per column is an exact match.

Only ``uptodate`` simulations are meaningful references: branches whose
status is ``outdated``/``loaded``/``cantrun`` store data produced by an
older geometry that OpenRocket itself would no longer reproduce.  The LASC
corpus exercises only the subsonic/transonic envelope (max stored Mach
~0.99); the supersonic kernels are pinned by unit tests instead.

Usage::

    python -m rocketserializer.dragmodel.compare file1.ork [file2.ork ...]
    python -m rocketserializer.dragmodel.compare --glob "Mission */**/*.ork"
"""

import argparse
import glob as globmod
import math
import sys

from .buildup import DragBuildup
from .components import load_rocket
from .simdata import load_sim_branches

COMPARED = ("cd", "friction_cd", "pressure_cd", "base_cd", "axial_cd")


class BranchComparison:
    """Error statistics for one simulation branch."""

    def __init__(self, path, sim_name, sim_status, rows_compared):
        self.path = path
        self.sim_name = sim_name
        self.sim_status = sim_status
        self.rows_compared = rows_compared
        self.max_error = {name: 0.0 for name in COMPARED}
        self.sum_error = {name: 0.0 for name in COMPARED}
        self.worst_row = None
        self.ref_area_relative_error = None

    def record(self, row, computed):
        # Override CD appears only in the stored total, never in the stored
        # friction/pressure/base split -- computed.cd already includes it.
        stored_axial = row.get("axial_cd", math.nan)
        errors = {
            "cd": computed.cd - row["cd"],
            "friction_cd": computed.friction - row["friction_cd"],
            "pressure_cd": computed.pressure - row["pressure_cd"],
            "base_cd": computed.base - row["base_cd"],
            "axial_cd": (computed.cd_axial - stored_axial)
            if not math.isnan(stored_axial)
            else 0.0,
        }
        for name in COMPARED:
            err = abs(errors[name])
            self.sum_error[name] += err
            if err > self.max_error[name]:
                self.max_error[name] = err
                if name == "cd":
                    self.worst_row = (
                        row.get("time"),
                        row["mach"],
                        row["cd"],
                        computed.cd,
                    )

    def mean_error(self, name):
        if self.rows_compared == 0:
            return 0.0
        return self.sum_error[name] / self.rows_compared


def compare_file(path, tangent_ogive_zero_sinphi=False, max_rows=None):
    """Compare every usable simulation branch of one .ork file.

    Returns a list of :class:`BranchComparison` (empty when the file has no
    usable sim data).
    """
    _creator, branches = load_sim_branches(path)
    rocket = load_rocket(path)
    results = []
    buildup = None
    for branch in branches:
        if branch.sim_status.startswith("extension:"):
            continue  # plugin-modified drag (e.g. airbrakes): not comparable
        rows = branch.barrowman_rows()
        if not rows:
            continue
        if max_rows and len(rows) > max_rows:
            step = len(rows) / float(max_rows)
            rows = [rows[int(i * step)] for i in range(max_rows)]
        if buildup is None:
            buildup = DragBuildup(
                rocket, tangent_ogive_zero_sinphi=tangent_ogive_zero_sinphi
            )
        comparison = BranchComparison(
            path, branch.sim_name, branch.sim_status, len(rows)
        )
        stored_ref_area = next(
            (
                r["ref_area"]
                for r in rows
                if not math.isnan(r.get("ref_area", math.nan))
            ),
            None,
        )
        if stored_ref_area:
            comparison.ref_area_relative_error = (
                buildup.ref_area - stored_ref_area
            ) / stored_ref_area
        for row in rows:
            aoa = row.get("aoa", 0.0)
            if math.isnan(aoa):
                aoa = 0.0
            computed = buildup.evaluate(row["mach"], row["reynolds"], aoa)
            comparison.record(row, computed)
        results.append(comparison)
    return results


def format_report(comparisons):
    lines = []
    header = "%-52s %-10s %5s | %9s %9s %9s %9s %9s" % (
        "file :: simulation",
        "status",
        "rows",
        "max|dCD|",
        "max|dCf|",
        "max|dCp|",
        "max|dCb|",
        "max|dCa|",
    )
    lines.append(header)
    lines.append("-" * len(header))
    for c in comparisons:
        name = "%s :: %s" % (c.path, c.sim_name)
        if len(name) > 52:
            name = "..." + name[-49:]
        lines.append(
            "%-52s %-10s %5d | %9.5f %9.5f %9.5f %9.5f %9.5f"
            % (
                name,
                c.sim_status[:10],
                c.rows_compared,
                c.max_error["cd"],
                c.max_error["friction_cd"],
                c.max_error["pressure_cd"],
                c.max_error["base_cd"],
                c.max_error["axial_cd"],
            )
        )
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", help=".ork files to compare")
    parser.add_argument("--glob", help="glob pattern for .ork files")
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="subsample each branch to at most this many rows",
    )
    args = parser.parse_args(argv)
    paths = list(args.files)
    if args.glob:
        import os

        paths += [
            p
            for p in globmod.glob(args.glob, recursive=True)
            if "__MACOSX" not in p and os.path.isfile(p)
        ]
    all_comparisons = []
    failures = []
    for path in paths:
        try:
            all_comparisons += compare_file(path, max_rows=args.max_rows)
        except Exception as error:  # pylint: disable=broad-except
            failures.append((path, "%s: %s" % (type(error).__name__, error)))
    print(format_report(all_comparisons))
    if failures:
        print("\nfailed files:")
        for path, message in failures:
            print("  %s: %s" % (path, message))
    return 0


if __name__ == "__main__":
    sys.exit(main())
