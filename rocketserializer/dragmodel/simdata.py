"""Extract stored simulation data from an .ork file for drag validation.

OpenRocket serializes each simulation's flight data as a ``<databranch>`` with
a ``types`` attribute naming the columns *in the UI language of the machine
that saved the file*.  Column names are therefore unreliable, but the column
ORDER is fixed per OpenRocket version (priorities are hard-coded), so columns
are resolved positionally from the branch's column count and the file's
``creator`` version:

- 58+ columns, creator 24.12 -> the 24.12 canonical order (extras appended);
- 54 columns, creator 24.12  -> a legacy branch RE-SAVED by 24.12, re-sorted
  into the 24.12 order minus the four columns 24.12 added;
- 54 columns, creator 23.09  -> the 23.09 canonical order;
- creator 22.02              -> the 23.09 order with 4 columns appended.

Files saved by other versions fall back to English column-name matching.
"""

import math
import re

from .components import read_ork_xml

#: semantic name -> 0-based column index in the OpenRocket 24.12 layout
LAYOUT_2412 = {
    "time": 0,
    "aoa": 15,
    "drag_force": 31,
    "cd": 32,
    "friction_cd": 33,
    "pressure_cd": 34,
    "base_cd": 35,
    "axial_cd": 36,
    "air_temperature": 47,
    "air_pressure": 48,
    "air_density": 49,
    "mach": 51,
    "reynolds": 52,
    "ref_length": 53,
    "ref_area": 54,
}

#: same for the 23.09 (and, as a prefix, 22.02) layout
LAYOUT_2309 = {
    "time": 0,
    "aoa": 15,
    "mach": 26,
    "reynolds": 27,
    "drag_force": 29,
    "cd": 30,
    "axial_cd": 31,
    "friction_cd": 32,
    "pressure_cd": 33,
    "base_cd": 34,
    "ref_length": 44,
    "ref_area": 45,
    "air_temperature": 49,
    "air_pressure": 50,
}

#: a 23.09-era branch RE-SAVED by 24.12: columns re-sorted into the 24.12
#: order minus the four columns 24.12 added (ASL, TWR, wind dir, air density)
LAYOUT_2412_54 = {
    "time": 0,
    "aoa": 14,
    "drag_force": 29,
    "cd": 30,
    "friction_cd": 31,
    "pressure_cd": 32,
    "base_cd": 33,
    "axial_cd": 34,
    "air_temperature": 44,
    "air_pressure": 45,
    "mach": 47,
    "reynolds": 48,
    "ref_length": 49,
    "ref_area": 50,
}


class SimBranch:
    """One stored simulation branch: rows keyed by semantic column name."""

    def __init__(
        self, sim_name, sim_status, branch_name, layout, columns, rows, events
    ):
        self.sim_name = sim_name
        self.sim_status = sim_status
        self.branch_name = branch_name
        self.layout = layout
        self.columns = columns
        self.rows = rows  # list of per-row dicts (semantic name -> float)
        self.events = events  # list of (type, time)

    def cutoff_time(self):
        """Last time at which rows are pure ascent-phase Barrowman rows."""
        cutoff = math.inf
        for kind, time in self.events:
            if kind in (
                "recoverydevicedeployment",
                "tumble",
                "stageseparation",
                "groundhit",
            ):
                cutoff = min(cutoff, time)
        return cutoff

    def barrowman_rows(self):
        """Rows usable for drag comparison (before any regime change)."""
        cutoff = self.cutoff_time()
        keep = []
        for row in self.rows:
            t = row.get("time")
            if t is None or math.isnan(t) or t >= cutoff:
                continue
            if any(
                math.isnan(row.get(k, math.nan))
                for k in (
                    "mach",
                    "reynolds",
                    "cd",
                    "friction_cd",
                    "pressure_cd",
                    "base_cd",
                )
            ):
                continue
            keep.append(row)
        return keep


def _parse_float(text):
    text = text.strip()
    if text == "NaN":
        return math.nan
    if text == "Inf":
        return math.inf
    if text == "-Inf":
        return -math.inf
    try:
        return float(text)
    except ValueError:
        return math.nan


def load_sim_branches(path):
    """All simulation branches of an .ork file, positionally resolved.

    Returns ``(creator, branches)``; branches from simulations that use
    extensions (e.g. airbrake plugins) are marked via ``sim_status`` prefixed
    with ``"extension:"`` so callers can exclude them.
    """
    soup = read_ork_xml(path)
    root = soup.find("openrocket")
    creator = root.get("creator", "") if root else ""
    branches = []
    for sim in soup.find_all("simulation"):
        sim_name_tag = sim.find("name", recursive=False)
        sim_name = sim_name_tag.get_text() if sim_name_tag else ""
        status = sim.get("status", "")
        conditions = sim.find("conditions", recursive=False)
        has_extension = sim.find("extension") is not None
        if has_extension:
            status = "extension:" + status
        flightdata = sim.find("flightdata", recursive=False)
        if flightdata is None:
            continue
        for branch in flightdata.find_all("databranch", recursive=False):
            columns = branch.get("types", "").split(",")
            layout = _resolve_layout(creator, len(columns), columns)
            if layout is None:
                continue
            events = []
            for event in branch.find_all("event", recursive=False):
                events.append((event.get("type", ""), float(event.get("time", "nan"))))
            rows = []
            for point in branch.find_all("datapoint", recursive=False):
                values = point.get_text().split(",")
                if len(values) != len(columns):
                    continue
                row = {}
                for name, index in layout.items():
                    if index < len(values):
                        row[name] = _parse_float(values[index])
                rows.append(row)
            branches.append(
                SimBranch(
                    sim_name,
                    status,
                    branch.get("name", ""),
                    layout,
                    columns,
                    rows,
                    events,
                )
            )
        del conditions
    return creator, branches


ENGLISH_NAMES = {
    "Time": "time",
    "Angle of attack": "aoa",
    "Mach number": "mach",
    "Reynolds number": "reynolds",
    "Drag force": "drag_force",
    "Drag coefficient": "cd",
    "Friction drag coefficient": "friction_cd",
    "Pressure drag coefficient": "pressure_cd",
    "Base drag coefficient": "base_cd",
    "Axial drag coefficient": "axial_cd",
    "Reference length": "ref_length",
    "Reference area": "ref_area",
    "Air temperature": "air_temperature",
    "Air pressure": "air_pressure",
    "Air density": "air_density",
}


def _resolve_layout(creator, count, columns):
    version = re.search(r"(\d\d)\.(\d\d)", creator or "")
    version = version.group(0) if version else ""
    # positional resolution only for the versions whose canonical column
    # order is known; anything else falls back to English column names
    if version == "22.02":
        return LAYOUT_2309 if count >= 35 else None
    if version == "23.09" and count == 54:
        return LAYOUT_2309
    if version == "24.12":
        if count == 54:
            # a legacy branch re-saved by 24.12: re-sorted into 24.12 order
            return LAYOUT_2412_54
        if count >= 58:
            return LAYOUT_2412
    layout = {}
    for i, col in enumerate(columns):
        semantic = ENGLISH_NAMES.get(col.strip())
        if semantic:
            layout[semantic] = i
    return layout if "cd" in layout and "mach" in layout else None
