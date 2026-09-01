"""No-simulation providers: fabricate the sim-derived parameters.json parts.

When a .ork file has no saved simulation (or ork2json runs with --no-jvm),
these providers replace the four data sources that normally come from the
simulation datapoints or the JVM:

- drag curve        -> computed from geometry (``rocketserializer.dragmodel``)
- thrust curve      -> the team's bundled .eng file (verified against the
                       .ork's motor digest when possible) or the pre-exported
                       OpenRocket motor database
- motor masses      -> the .eng/database header (propellant + total mass)
- rocket mass/CG/inertia -> the structure mass model
                       (``rocketserializer.massmodel``) plus the motor casing
                       at burnout, matching OpenRocket's "Mass"/"CG location"
                       columns at burnout
"""

import glob
import logging
import math
import os
from pathlib import Path

import numpy as np

from . import massmodel, motors
from .dragmodel import DragBuildup
from .dragmodel.components import Rocket as DragRocket

logger = logging.getLogger(__name__)


def find_eng_candidates(filepath, extra=None, search_levels=4):
    """All .eng files near the .ork file, searching a few levels up too.

    Team submissions often keep the .eng file in a sibling folder of the
    .ork, so the search walks up to ``search_levels`` parent directories and
    scans each tree (macOS junk filtered).  The walk stops as soon as the
    CURRENT directory looks like a submission root (the LASC layout, either
    "Mission 18- Hadron" or "M018 - Hadron" -- both require the dash so team
    folder names like "Mission7_Nominal" or "M39_Nominal" do not stop it) --
    and never climbs into a user's home directory or a drive root.
    """
    import re

    def is_submission_root(directory):
        return bool(re.match(r"(?i)^(?:mission\s+\d+|m\d+)\s*-", directory.name))

    def is_unsafe_root(directory):
        # never scan a drive root, "Users", or a home directory
        if directory.parent == directory:
            return True
        name = directory.name.lower()
        if name in ("users", "home", "documents", "desktop", "downloads"):
            return True
        return directory == Path.home() or directory == Path.home().parent

    paths = []
    if extra:
        paths.append(Path(extra))
    root = Path(filepath).parent
    roots = [root]
    current = root
    for _ in range(search_levels):
        if is_submission_root(current):
            break
        parent = current.parent
        if parent == current or is_unsafe_root(parent):
            break
        roots.append(parent)
        current = parent
    seen = set()
    for base in roots:
        try:
            found = sorted(base.rglob("*.eng"))
        except OSError:
            continue
        for p in found:
            text = str(p)
            if "__MACOSX" in text or p.name.startswith("._"):
                continue
            if text not in seen:
                seen.add(text)
                paths.append(p)
    return paths


def resolve_motor(soup, filepath, eng_path=None, bundled_db_path=None):
    """Resolve the design's motor to an .eng/database motor, or None.

    All motors referenced by the design are tried (default flight
    configuration first); the (ork motor, candidate) pair with the best match
    wins -- this handles designs whose default config id matches no motor.
    """
    ork_motors = motors.find_ork_motors(soup)
    if not ork_motors:
        logger.warning("[nosim] no <motor> element found in the design")
        return None, None
    candidates = find_eng_candidates(filepath, extra=eng_path)
    bundled = motors.load_bundled_database(bundled_db_path)
    ork_motor, motor, score = ork_motors[0], None, -1
    for candidate_ork in ork_motors:  # default-config motor first: wins ties
        found, found_score = motors.find_best_motor(candidate_ork, candidates, bundled)
        if found is not None and found_score > score:
            ork_motor, motor, score = candidate_ork, found, found_score
    if motor is None:
        logger.warning(
            "[nosim] no thrust source found for motor %s %s (best match "
            "score %s); provide an .eng file with --eng",
            ork_motor.manufacturer,
            ork_motor.designation,
            score,
        )
    else:
        logger.info(
            "[nosim] motor %s resolved from %s (match score %d)",
            ork_motor.designation,
            motor.source,
            score,
        )
    return ork_motor, motor


def geometry_drag_curve(soup, output_folder):
    """Compute drag_curve.csv (Mach, Cd) from the geometry alone."""
    buildup = DragBuildup(DragRocket(soup))
    machs, cds = buildup.drag_curve()
    data = np.array([machs, cds]).T
    path = os.path.join(output_folder, "drag_curve.csv")
    np.savetxt(path, data, delimiter=",", fmt="%.6f")
    logger.info("[nosim] geometry drag curve saved to %s", path)
    return path


def motor_mount_geometry(soup, ork_motor):
    """(mount_abs_x, mount_length, overhang) of the motor mount, or None.

    The mount is the component whose <motormount> contains the design's
    <motor> element.
    """
    root = massmodel.parse_rocket(soup)

    def walk(node):
        mount = node.tag.find("motormount", recursive=False)
        if mount is not None and mount.find("motor") is not None:
            overhang_tag = mount.find("overhang", recursive=False)
            overhang = float(overhang_tag.get_text()) if overhang_tag else 0.0
            return node.abs_x, node.length, overhang
        for child in node.children:
            found = walk(child)
            if found:
                return found
        return None

    for stage in root.children:
        for comp in stage.children:
            found = walk(comp)
            if found:
                return found
    return None


def build_motors_dict(soup, ork_motor, motor, mount):
    """The ``motors`` section, mirroring motor.py's grain fabrication."""
    motor_radius = (ork_motor.diameter / 2) if ork_motor else 0.0
    motor_length = ork_motor.length if ork_motor else 0.0
    propellant_mass = motor.propellant_mass if motor else 0.0
    casing_mass = motor.burnout_mass if motor else 0.0

    grain_inner = motor_radius / 2
    grain_outer = motor_radius
    grain_height = motor_length
    grain_volume = (
        math.pi * (grain_outer**2 - grain_inner**2) * grain_height
    ) or float("nan")
    grain_density = (
        propellant_mass / grain_volume
        if grain_volume and not math.isnan(grain_volume)
        else 0.0
    )

    position = None
    if mount is not None and motor_length:
        mount_x, mount_length, overhang = mount
        motor_fore = mount_x + mount_length - motor_length + overhang
        position = motor_fore + motor_length / 2  # .eng CG = motor midpoint

    return {
        "grain_density": grain_density,
        "grain_initial_inner_radius": grain_inner,
        "grain_outer_radius": grain_outer,
        "grain_initial_height": grain_height,
        "nozzle_radius": 1.5 * grain_inner,
        "throat_radius": 1.0 * grain_inner,
        "dry_mass": casing_mass,
        "dry_inertia": (0, 0, 0),
        "center_of_dry_mass_position": 0,
        "grains_center_of_mass_position": 0,
        "grain_number": 1,
        "grain_separation": 0,
        "nozzle_position": -motor_length / 2,
        "coordinate_system_orientation": "nozzle_to_combustion_chamber",
        "position": position,
    }


def build_rocket_dict(soup, ork_motor, motor, mount, rocket_radius):
    """The ``rocket`` section: motor-less structure mass properties.

    RocketPy's ``Rocket`` takes the mass WITHOUT the motor -- the motor's
    casing mass is carried by ``motors.dry_mass`` and added by RocketPy when
    the motor is attached, so it must NOT be included here.
    """
    del ork_motor, motor, mount  # kept for signature stability
    properties = massmodel.structure_mass_properties(soup)
    return {
        "radius": rocket_radius,
        "mass": properties.mass,
        "inertia": (
            properties.longitudinal_inertia,
            properties.longitudinal_inertia,
            properties.rotational_inertia,
        ),
        "center_of_mass_without_propellant": properties.cg_x,
        "coordinate_system_orientation": "nose_to_tail",
    }
