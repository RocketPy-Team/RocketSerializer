"""Canonical flight-data column lists and locale-independent label remapping.

OpenRocket writes the ``types`` attribute of each ``<databranch>`` using the
UI language of the machine that saved the file, but the column ORDER is fixed
per OpenRocket version.  ``canonicalize_types`` rewrites a non-English label
list to the canonical English one positionally, so every downstream consumer
that looks columns up by their English name works on any locale.

Layout rules (empirically verified across the LASC 2026 corpus):

- creator 24.12, >= 58 columns: the 24.12 order; extras beyond 58 are
  user/plugin columns and are kept verbatim;
- creator 24.12, exactly 54 columns: a legacy branch re-saved by 24.12 --
  the 24.12 order minus the four columns 24.12 added;
- creator 23.09, exactly 54 columns: the 23.09 order;
- creator 22.02: the 23.09 order with 4 columns appended.

Anything else is left untouched (the caller's English-only guard then fires).
"""

CANONICAL_2412 = [
    "Time",
    "Altitude",
    "Altitude above sea level",
    "Vertical velocity",
    "Total velocity",
    "Vertical acceleration",
    "Total acceleration",
    "Position East of launch",
    "Position North of launch",
    "Lateral distance",
    "Lateral direction",
    "Lateral velocity",
    "Lateral acceleration",
    "Latitude",
    "Longitude",
    "Angle of attack",
    "Roll rate",
    "Pitch rate",
    "Yaw rate",
    "Vertical orientation (zenith)",
    "Lateral orientation (azimuth)",
    "Mass",
    "Motor mass",
    "Longitudinal moment of inertia",
    "Rotational moment of inertia",
    "Gravitational acceleration",
    "CP location",
    "CG location",
    "Stability margin calibers",
    "Thrust",
    "Thrust-to-weight ratio",
    "Drag force",
    "Drag coefficient",
    "Friction drag coefficient",
    "Pressure drag coefficient",
    "Base drag coefficient",
    "Axial drag coefficient",
    "Normal force coefficient",
    "Pitch moment coefficient",
    "Yaw moment coefficient",
    "Side force coefficient",
    "Roll moment coefficient",
    "Roll forcing coefficient",
    "Roll damping coefficient",
    "Pitch damping coefficient",
    "Wind velocity",
    "Wind direction",
    "Air temperature",
    "Air pressure",
    "Air density",
    "Speed of sound",
    "Mach number",
    "Reynolds number",
    "Reference length",
    "Reference area",
    "Simulation time step",
    "Computation time",
    "Coriolis acceleration",
]

CANONICAL_2309 = [
    "Time",
    "Altitude",
    "Vertical velocity",
    "Vertical acceleration",
    "Total velocity",
    "Total acceleration",
    "Position East of launch",
    "Position North of launch",
    "Lateral distance",
    "Lateral direction",
    "Lateral velocity",
    "Lateral acceleration",
    "Latitude",
    "Longitude",
    "Gravitational acceleration",
    "Angle of attack",
    "Roll rate",
    "Pitch rate",
    "Yaw rate",
    "Mass",
    "Motor mass",
    "Longitudinal moment of inertia",
    "Rotational moment of inertia",
    "CP location",
    "CG location",
    "Stability margin calibers",
    "Mach number",
    "Reynolds number",
    "Thrust",
    "Drag force",
    "Drag coefficient",
    "Axial drag coefficient",
    "Friction drag coefficient",
    "Pressure drag coefficient",
    "Base drag coefficient",
    "Normal force coefficient",
    "Pitch moment coefficient",
    "Yaw moment coefficient",
    "Side force coefficient",
    "Roll moment coefficient",
    "Roll forcing coefficient",
    "Roll damping coefficient",
    "Pitch damping coefficient",
    "Coriolis acceleration",
    "Reference length",
    "Reference area",
    "Vertical orientation (zenith)",
    "Lateral orientation (azimuth)",
    "Wind velocity",
    "Air temperature",
    "Air pressure",
    "Speed of sound",
    "Simulation time step",
    "Computation time",
]

#: a 23.09-era branch re-saved by 24.12: 24.12 order minus its 4 new columns
CANONICAL_2412_54 = [
    c
    for c in CANONICAL_2412
    if c
    not in (
        "Altitude above sea level",
        "Thrust-to-weight ratio",
        "Wind direction",
        "Air density",
    )
]

_APPENDED_2202 = [
    "Air density",
    "Altitude above sea level",
    "Thrust-to-weight ratio",
    "Wind direction",
]


def canonical_labels(creator, columns):
    """The canonical English label list for a branch, or None if unknown.

    Parameters
    ----------
    creator : str
        The ``creator`` attribute of the ``<openrocket>`` root element.
    columns : list of str
        The branch's current (possibly localized) column labels.
    """
    import re

    match = re.search(r"(\d\d)\.(\d\d)", creator or "")
    version = match.group(0) if match else ""
    count = len(columns)
    if version == "22.02" and count >= 58:
        return CANONICAL_2309 + _APPENDED_2202 + columns[58:]
    if version == "23.09" and count == 54:
        return list(CANONICAL_2309)
    if version == "24.12":
        if count == 54:
            return list(CANONICAL_2412_54)
        if count >= 58:
            # extras beyond 58 are custom-expression/plugin columns whose
            # names are user-defined -- keep them verbatim
            return CANONICAL_2412 + columns[58:]
    return None


def canonicalize_types(soup, branch):
    """Rewrite a non-English branch ``types`` attribute in place.

    No-op for English branches (detected by the presence of "CG location"),
    so files that work today are byte-identical.  Returns True if remapped.
    """
    columns = branch.get("types", "").split(",")
    if "CG location" in columns:
        return False
    root = soup.find("openrocket")
    creator = root.get("creator", "") if root else ""
    canonical = canonical_labels(creator, columns)
    if canonical is None:
        return False
    branch["types"] = ",".join(canonical)
    return True
