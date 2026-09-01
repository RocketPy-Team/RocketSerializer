"""JVM-free motor handling: RASP .eng parsing, OpenRocket digests, matching.

Ports, from OpenRocket 24.12:

- ``RASPMotorLoader`` -- the exact .eng grammar (multi-motor files, comment
  handling, delay parsing, mass fields);
- ``AbstractMotorLoader.finalizeThrustCurve`` / ``calculateMass`` -- the
  implicit (0,0) point rules and the constant-exhaust-velocity mass curve;
- ``MotorDigest`` -- the MD5 digest OpenRocket stores in the .ork's
  ``<digest>`` element, so a team-provided .eng can be verified against the
  design file without Java;
- the motor-matching policy of ``ThrustCurveMotorSetDatabase.findMotors``.

Also provides loading of a pre-exported bundled motor database (JSON produced
once with the JVM by :func:`export_bundled_database`) for commercial motors.
"""

import gzip
import hashlib
import json
import logging
import math
import re
import struct
from pathlib import Path

logger = logging.getLogger(__name__)

PLUGGED_DELAY = math.inf

#: default location of the one-time bundled-DB export (may not exist)
BUNDLED_DB_PATH = Path(__file__).parent / "data" / "openrocket_motors.json.gz"


class EngMotor:
    """One motor block parsed from a RASP .eng file."""

    def __init__(
        self,
        designation,
        diameter,
        length,
        delays,
        propellant_mass,
        total_mass,
        manufacturer,
        time,
        thrust,
        source=None,
    ):
        self.designation = designation  # delay suffix stripped, as OR does
        self.raw_designation = designation
        self.diameter = diameter  # m
        self.length = length  # m
        self.delays = delays
        self.propellant_mass = propellant_mass  # kg
        self.total_mass = total_mass  # kg (loaded)
        self.manufacturer = manufacturer
        self.time = time  # finalized, seconds
        self.thrust = thrust  # finalized, newtons
        self.source = source  # file path, for reporting
        self.mass = _mass_curve(self.time, self.thrust, total_mass, propellant_mass)

    @property
    def burnout_mass(self):
        return self.total_mass - self.propellant_mass

    @property
    def burn_time(self):
        return self.time[-1] if self.time else 0.0

    @property
    def max_thrust(self):
        return max(self.thrust) if self.thrust else 0.0

    def total_impulse(self):
        total = 0.0
        for i in range(len(self.time) - 1):
            total += (
                (self.time[i + 1] - self.time[i])
                * (self.thrust[i] + self.thrust[i + 1])
                / 2
            )
        return total

    def digests(self):
        """All digest variants OpenRocket may have stored for this motor."""
        cg = [self.length / 2] * len(self.time)
        return {
            "rasp": motor_digest(
                [
                    ("TIME_ARRAY", self.time),
                    ("MASS_SPECIFIC", [self.total_mass, self.burnout_mass]),
                    ("FORCE_PER_TIME", self.thrust),
                ]
            ),
            "motor": motor_digest(
                [
                    ("TIME_ARRAY", self.time),
                    ("MASS_PER_TIME", self.mass),
                    ("CG_PER_TIME", cg),
                    ("FORCE_PER_TIME", self.thrust),
                ]
            ),
            "thrust_only": motor_digest(
                [
                    ("TIME_ARRAY", self.time),
                    ("FORCE_PER_TIME", self.thrust),
                ]
            ),
            "mass_per_time": motor_digest(
                [
                    ("TIME_ARRAY", self.time),
                    ("MASS_PER_TIME", self.mass),
                    ("FORCE_PER_TIME", self.thrust),
                ]
            ),
            "cg_per_time": motor_digest(
                [
                    ("TIME_ARRAY", self.time),
                    ("CG_PER_TIME", cg),
                    ("FORCE_PER_TIME", self.thrust),
                ]
            ),
        }


# ---------------------------------------------------------------------------
# RASP parsing (RASPMotorLoader)
# ---------------------------------------------------------------------------


def parse_eng(path):
    """Parse a RASP .eng file into a list of :class:`EngMotor`.

    Follows OpenRocket's grammar exactly: leading ';' comment lines, a 7-field
    header, then time/thrust pairs; a line starting with ';' ends a motor and
    a file may contain several motor blocks (e.g. one per grain variant).
    Header-less data-only files yield an empty list.
    """
    text = Path(path).read_text(encoding="ISO-8859-1")
    lines = text.splitlines()
    motors = []
    i = 0
    n = len(lines)
    while i < n:
        # comment block
        while i < n and (not lines[i].strip() or lines[i].lstrip()[0] == ";"):
            i += 1
        if i >= n:
            break
        header = lines[i].split()
        i += 1
        if len(header) < 7:
            logger.warning(
                "%s: header line has %d fields, expected >= 7 - skipping block",
                path,
                len(header),
            )
            # skip to next comment line
            while i < n and (not lines[i].strip() or lines[i].lstrip()[0] != ";"):
                i += 1
            continue
        try:
            diameter = float(header[1]) / 1000.0
            length = float(header[2]) / 1000.0
            delays = _parse_delays(header[3])
            prop_mass = float(header[4])
            total_mass = float(header[5])
        except ValueError:
            logger.warning(
                "%s: malformed header %r - skipping block", path, " ".join(header[:7])
            )
            while i < n and (not lines[i].strip() or lines[i].lstrip()[0] != ";"):
                i += 1
            continue
        designation = _remove_delay(header[0])
        manufacturer = " ".join(header[6:])
        time, thrust = [], []
        bad = False
        while i < n:
            stripped = lines[i].strip()
            if stripped and stripped[0] == ";":
                break  # terminator (retained as next block's comment)
            i += 1
            if not stripped:
                continue
            tokens = stripped.split()
            if len(tokens) != 2:
                bad = True
                break
            try:
                time.append(float(tokens[0]))
                thrust.append(float(tokens[1]))
            except ValueError:
                bad = True
                break
        if bad or len(time) < 2 or prop_mass > total_mass:
            logger.warning("%s: invalid data block for %r - skipped", path, designation)
            continue
        _sort_by_time(time, thrust)
        time, thrust = _finalize_thrust_curve(time, thrust)
        motors.append(
            EngMotor(
                designation,
                diameter,
                length,
                delays,
                prop_mass,
                total_mass,
                manufacturer,
                time,
                thrust,
                source=str(path),
            )
        )
    return motors


def _parse_delays(field):
    if field.lower() == "none":
        return []
    delays = []
    for token in re.split(r"[-,]+", field):
        if token.lower() in ("p", "plugged"):
            delays.append(PLUGGED_DELAY)
        elif re.fullmatch(r"[0-9]+", token):
            value = float(token)
            if value < 99:
                delays.append(value)
    delays.sort()
    return delays


def _remove_delay(designation):
    """``AbstractMotorLoader.removeDelay``: strip a trailing -<delay> suffix."""
    if re.fullmatch(r".*-([0-9]+|[pP])", designation):
        return designation[: designation.rindex("-")]
    return designation


def _sort_by_time(time, thrust):
    # repeated adjacent swaps, as AbstractMotorLoader.sortLists
    changed = True
    while changed:
        changed = False
        for i in range(len(time) - 1):
            if time[i + 1] < time[i]:
                time[i], time[i + 1] = time[i + 1], time[i]
                thrust[i], thrust[i + 1] = thrust[i + 1], thrust[i]
                changed = True


def _java_equals(a, b, eps=1e-8):
    absb = abs(b)
    if absb < eps / 2:
        return abs(a) < eps / 2
    return abs(a - b) < eps * absb


def _finalize_thrust_curve(time, thrust):
    """``AbstractMotorLoader.finalizeThrustCurve``: the implicit-point rules."""
    if not time:
        return time, thrust
    if not _java_equals(time[0], 0.0):
        time = [0.0] + time
        thrust = [0.0] + thrust
    if len(time) > 1 and _java_equals(time[0], 0.0) and _java_equals(time[1], 0.0):
        del time[0], thrust[0]
    # remove duplicate identical points
    i = 0
    while i < len(time) - 1:
        if _java_equals(time[i], time[i + 1]) and _java_equals(
            thrust[i], thrust[i + 1]
        ):
            del time[i + 1], thrust[i + 1]
        else:
            i += 1
    # equal-time final pair: drop whichever has zero thrust
    if len(time) >= 2 and _java_equals(time[-1], time[-2]):
        if _java_equals(thrust[-1], 0.0):
            del time[-1], thrust[-1]
        elif _java_equals(thrust[-2], 0.0):
            del time[-2], thrust[-2]
    return time, thrust


def _mass_curve(time, thrust, total_mass, propellant_mass):
    """``AbstractMotorLoader.calculateMass``: burn proportional to impulse."""
    if len(time) < 2:
        return [total_mass] * len(time)
    deltas = [
        0.5 * (thrust[i] + thrust[i + 1]) * (time[i + 1] - time[i])
        for i in range(len(time) - 1)
    ]
    total_impulse = sum(deltas)
    scale = propellant_mass / total_impulse if total_impulse > 0 else 0.0
    mass = [total_mass]
    for delta in deltas:
        mass.append(max(mass[-1] - delta * scale, 0.0))
    return mass


# ---------------------------------------------------------------------------
# MotorDigest (bit-exact port)
# ---------------------------------------------------------------------------

_DIGEST_TYPES = {
    "TIME_ARRAY": (0, 1000),
    "MASS_SPECIFIC": (1, 10000),
    "MASS_PER_TIME": (2, 10000),
    "CG_SPECIFIC": (3, 1000),
    "CG_PER_TIME": (4, 1000),
    "FORCE_PER_TIME": (5, 1000),
}


def _next_epsilon(value):
    # Java: v + Math.signum(v) * 1e-11  (signum(0) == 0)
    if value == 0.0:
        return value
    return value + math.copysign(1e-11, value)


def motor_digest(updates):
    """``MotorDigest``: MD5 over quantized big-endian int32 streams."""
    md5 = hashlib.md5()
    last_order = -1
    for name, values in updates:
        order, multiplier = _DIGEST_TYPES[name]
        if order <= last_order:
            raise ValueError("digest updates must be in enum order")
        last_order = order
        values = list(values)
        md5.update(struct.pack(">i", order))
        md5.update(struct.pack(">i", len(values)))
        for value in values:
            quantized = _next_epsilon(_next_epsilon(value) * multiplier)
            # Java Math.round(double) == floor(x + 0.5), then (int) truncation
            # of the long keeps the low 32 bits (two's complement)
            rounded = int(math.floor(quantized + 0.5)) & 0xFFFFFFFF
            if rounded >= 2**31:
                rounded -= 2**32
            md5.update(struct.pack(">i", rounded))
    return md5.hexdigest()


# ---------------------------------------------------------------------------
# .ork motor description + matching
# ---------------------------------------------------------------------------


class OrkMotor:
    """The motor reference stored in a .ork ``<motor>`` element."""

    def __init__(self, tag):
        def text(name, default=""):
            child = tag.find(name, recursive=False)
            return child.get_text().strip() if child else default

        self.config_id = tag.get("configid", "")
        self.manufacturer = text("manufacturer")
        self.digest = text("digest")
        self.designation = text("designation")
        self.diameter = float(text("diameter", "0") or 0)
        self.length = float(text("length", "0") or 0)
        self.motor_type = text("type")


def find_ork_motors(soup):
    """Unique motors referenced by the design, default flight config first."""
    default_config = None
    rocket_tag = soup.find("rocket")
    if rocket_tag is not None:
        for config in rocket_tag.find_all("motorconfiguration", recursive=False):
            if config.get("default") == "true":
                default_config = config.get("configid")
                break
    seen = {}
    for tag in soup.find_all("motor"):
        motor = OrkMotor(tag)
        key = motor.digest or (motor.designation, motor.diameter)
        if key not in seen:
            seen[key] = motor
    result = list(seen.values())
    if default_config:
        result.sort(key=lambda m: 0 if m.config_id == default_config else 1)
    return result


def _fuzzy(name):
    return re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()


def match_score(ork_motor, candidate):
    """Match quality of an .eng/DB motor against a .ork motor reference.

    Digest match (any variant) is authoritative (score 100).  Otherwise:
    designation exact = 4, fuzzy substring = 2; diameter within 1 mm = 2;
    length within 2 mm = 1.
    """
    if ork_motor.digest:
        if isinstance(candidate, EngMotor):
            if ork_motor.digest in candidate.digests().values():
                return 100
        elif ork_motor.digest == getattr(candidate, "digest", None):
            return 100
    score = 0
    ork_designation = _remove_delay(ork_motor.designation)
    cand_designation = getattr(candidate, "designation", "")
    if _fuzzy(ork_designation) == _fuzzy(cand_designation):
        score += 4
    elif _fuzzy(ork_designation) and (
        _fuzzy(ork_designation) in _fuzzy(cand_designation)
        or _fuzzy(cand_designation) in _fuzzy(ork_designation)
    ):
        score += 2
    if abs(ork_motor.diameter - candidate.diameter) <= 0.001 + 1e-9:
        score += 2
    if abs(ork_motor.length - candidate.length) <= 0.002 + 1e-9:
        score += 1
    return score


def find_best_motor(ork_motor, eng_paths, bundled_db=None, minimum_score=4):
    """Resolve a .ork motor reference to the best candidate.

    Two phases: team-provided .eng files first (lenient -- they were bundled
    with the design on purpose), then the pre-exported OpenRocket motor
    database with strict rules (exact digest, or exact designation plus
    matching diameter) so that the 1400+ database motors cannot shadow or
    dilute a team file.

    Returns ``(motor, score)`` or ``(None, best_rejected_score)``.
    """
    candidates = []
    for path in eng_paths:
        try:
            candidates.extend(parse_eng(path))
        except OSError as error:
            logger.warning("cannot read %s: %s", path, error)

    best, best_score = None, -1
    runner_up_score = -1
    for candidate in candidates:
        score = match_score(ork_motor, candidate)
        if score > best_score:
            best, best_score, runner_up_score = candidate, score, best_score
        elif score > runner_up_score:
            runner_up_score = score
    if best is not None and best_score >= minimum_score:
        return best, best_score
    if (
        best is not None
        and best_score >= 2
        and runner_up_score < best_score
        and abs(ork_motor.diameter - best.diameter) <= 0.0015
        and abs(ork_motor.length - best.length) <= 0.003
    ):
        # dimensions match and no competing team file: accept a renamed
        # motor file (e.g. a re-exported .eng with a new designation)
        logger.warning(
            "accepting dimension-only motor match %s for %s (designations "
            "differ: %r vs %r)",
            getattr(best, "source", "?"),
            ork_motor.designation,
            getattr(best, "designation", "?"),
            ork_motor.designation,
        )
        return best, best_score

    # database phase: strict
    db_best, db_score = None, -1
    for candidate in bundled_db or []:
        score = match_score(ork_motor, candidate)
        if score > db_score:
            db_best, db_score = candidate, score
    if db_best is not None and (
        db_score >= 100  # digest match
        or (
            db_score >= 6
            and _fuzzy(db_best.designation)
            == _fuzzy(_remove_delay(ork_motor.designation))
        )
    ):
        return db_best, db_score
    return None, max(best_score, db_score)


# ---------------------------------------------------------------------------
# Bundled motor database (one-time JVM export)
# ---------------------------------------------------------------------------


class DbMotor:
    """A motor from the pre-exported bundled OpenRocket database."""

    def __init__(self, record):
        self.designation = record["designation"]
        self.manufacturer = record["manufacturer"]
        self.digest = record["digest"]
        self.diameter = record["diameter_m"]
        self.length = record["length_m"]
        self.time = record["time_s"]
        self.thrust = record["thrust_n"]
        self.mass = record["mass_kg"]
        self.source = "bundled-db:%s %s" % (self.manufacturer, self.designation)

    @property
    def total_mass(self):
        return self.mass[0] if self.mass else 0.0

    @property
    def burnout_mass(self):
        return self.mass[-1] if self.mass else 0.0

    @property
    def propellant_mass(self):
        return self.total_mass - self.burnout_mass

    @property
    def burn_time(self):
        return self.time[-1] if self.time else 0.0

    @property
    def max_thrust(self):
        return max(self.thrust) if self.thrust else 0.0


def load_bundled_database(path=None):
    """Load the pre-exported bundled motor DB; [] if not available."""
    path = Path(path) if path else BUNDLED_DB_PATH
    if not path.exists():
        return []
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as file:
        data = json.load(file)
    return [DbMotor(record) for record in data["motors"]]


def export_bundled_database(jar_path, out_path):
    """One-time JVM export of OpenRocket's bundled motor database to JSON.

    Requires Java; every other function in this module is JVM-free.
    """
    # pylint: disable=import-outside-toplevel
    from .openrocket_runtime import OpenRocketSession

    records = []
    with OpenRocketSession(jar_path) as session:
        application = session.openrocket_core.startup.Application
        database = application.getMotorSetDatabase()
        for motor_set in database.getMotorSets():
            for motor in motor_set.getMotors():
                cg = motor.getCGPoints()
                records.append(
                    {
                        "digest": str(motor.getDigest()),
                        "manufacturer": str(motor.getManufacturer().getDisplayName()),
                        "designation": str(motor.getDesignation()),
                        "type": str(motor.getMotorType().name()),
                        "diameter_m": float(motor.getDiameter()),
                        "length_m": float(motor.getLength()),
                        "delays": [
                            "P" if math.isinf(float(d)) else float(d)
                            for d in motor.getStandardDelays()
                        ],
                        "time_s": [float(t) for t in motor.getTimePoints()],
                        "thrust_n": [float(f) for f in motor.getThrustPoints()],
                        "cg_x_m": [
                            float(
                                getattr(c, "x", None)
                                if not hasattr(c, "getX")
                                else c.getX()
                            )
                            for c in cg
                        ],
                        "mass_kg": [
                            float(
                                getattr(c, "weight", None)
                                if not hasattr(c, "getWeight")
                                else c.getWeight()
                            )
                            for c in cg
                        ],
                    }
                )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if out_path.suffix == ".gz" else open
    with opener(out_path, "wt", encoding="utf-8") as file:
        json.dump({"format": 1, "motors": records}, file)
    return len(records)


def write_thrust_curve_csv(motor, folder_path):
    """Write ``thrust_source.csv`` from an .eng/DB motor (RocketPy format).

    Mirrors the sim-based ``generate_thrust_curve`` post-processing: negative
    thrust clipped, near-zero rows dropped, ``%1.5f`` formatting.
    """
    import os

    import numpy as np

    data = np.array([motor.time, motor.thrust], dtype=float).T
    data[:, 1] = np.clip(data[:, 1], 0.0, None)
    data = data[data[:, 1] > 0.0001, :]
    path = os.path.join(folder_path, "thrust_source.csv")
    np.savetxt(path, data, delimiter=",", fmt="%1.5f")
    return path
