"""Pure-Python port of OpenRocket 24.12's structure mass/CG/inertia model.

Computes, from the .ork XML alone (no JVM, no saved simulation):

- structure (dry, motorless) mass, center of mass and moments of inertia,
  exactly as ``MassCalculator.calculateStructure`` does -- including mass/CG
  overrides, nose/transition shoulders, fin tabs and fillets, ring components,
  packed recovery items, and every per-component formula of the Java code
  (bug-for-bug where OpenRocket has quirks);
- burnout totals when a motor's dry (casing) mass and position are supplied,
  reproducing the "Mass" / "CG location" / moment-of-inertia flight-data
  columns at burnout.

Scope note: parallel stages / pods and motor clusters other than ``single``
are not modeled (none exist in the LASC corpus); serial multi-stage rockets
are fully supported.
"""

import logging
import math

from .dragmodel.components import read_ork_xml
from .dragmodel.geometry import (
    elliptical_fin_points,
    mount_points,
    transition_radius_function,
    trapezoid_fin_points,
)

logger = logging.getLogger(__name__)

EPSILON = 1e-8
MIN_MASS = 1e-8  # MassCalculation.MIN_MASS
DEFAULT_RADIUS = 0.025

CROSS_SECTION_VOLUME = {"square": 1.00, "rounded": 0.99, "airfoil": 0.85}

SYMMETRIC_KINDS = ("nosecone", "bodytube", "transition")
FIN_KINDS = ("trapezoidfinset", "freeformfinset", "ellipticalfinset")
RING_KINDS = ("innertube", "tubecoupler", "centeringring", "bulkhead", "engineblock")
MASS_OBJECT_KINDS = ("masscomponent", "parachute", "streamer", "shockcord")
ALL_KINDS = (
    SYMMETRIC_KINDS
    + FIN_KINDS
    + RING_KINDS
    + MASS_OBJECT_KINDS
    + ("launchlug", "railbutton")
)


# ---------------------------------------------------------------------------
# Coordinate / RigidBody arithmetic (util/Coordinate.java, masscalc/RigidBody)
# ---------------------------------------------------------------------------


class CM:
    """A mass-weighted coordinate: (x, y, z, weight=mass)."""

    __slots__ = ("x", "y", "z", "w")

    def __init__(self, x=0.0, y=0.0, z=0.0, w=0.0):
        self.x, self.y, self.z, self.w = x, y, z, w

    def average(self, other):
        """``Coordinate.average``: mass-weighted, with the degenerate rule."""
        total = self.w + other.w
        if abs(total) < EPSILON * EPSILON:
            return CM(
                (self.x + other.x) / 2,
                (self.y + other.y) / 2,
                (self.z + other.z) / 2,
                0.0,
            )
        return CM(
            (self.x * self.w + other.x * other.w) / total,
            (self.y * self.w + other.y * other.w) / total,
            (self.z * self.w + other.z * other.w) / total,
            total,
        )

    def with_weight(self, w):
        return CM(self.x, self.y, self.z, w)

    def with_x(self, x):
        return CM(x, self.y, self.z, self.w)


class Body:
    """A rigid body: CM + diagonal inertia about its own CM."""

    __slots__ = ("cm", "ixx", "iyy", "izz")

    def __init__(self, cm, ixx, iyy, izz):
        self.cm = cm
        self.ixx, self.iyy, self.izz = ixx, iyy, izz


def _rebased_sums(bodies, center):
    """Parallel-axis every body to ``center``; return (Ixx, Iyy) sums."""
    ixx = iyy = 0.0
    for body in bodies:
        dx = body.cm.x - center.x
        dy = body.cm.y - center.y
        dz = body.cm.z - center.z
        m = body.cm.w
        ixx += body.ixx + m * (dy * dy + dz * dz)
        iyy += body.iyy + m * (dx * dx + dz * dz)
    return ixx, iyy


class MassProperties:
    """Result: total mass, CM (rocket frame) and inertias about the CM."""

    def __init__(self, cm, ixx, iyy):
        self.mass = cm.w
        self.cm = cm
        self.cg_x = cm.x
        self.rotational_inertia = ixx  # Ixx (roll)
        self.longitudinal_inertia = iyy  # Iyy = Izz (pitch/yaw)


# ---------------------------------------------------------------------------
# XML parsing helpers
# ---------------------------------------------------------------------------


def _text(tag, name, default=None):
    child = tag.find(name, recursive=False)
    return child.get_text().strip() if child else default


def _float(tag, name, default=0.0):
    text = _text(tag, name, None)
    if text is None:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _radius_spec(tag, name):
    """(value, is_auto) for radius elements that may be ``auto [cached]``."""
    text = _text(tag, name, None)
    if text is None:
        return None, False
    lowered = text.strip().lower()
    if lowered.startswith("auto"):
        rest = lowered[4:].strip()
        return (float(rest) if rest else None), True
    return float(lowered), False


def _material_density(tag, name="material"):
    child = tag.find(name, recursive=False)
    if child is None:
        return 0.0
    try:
        return float(child.get("density", "0"))
    except ValueError:
        return 0.0


def _axial_offset(tag):
    offset_tag = tag.find("axialoffset", recursive=False)
    if offset_tag is not None:
        return offset_tag.get("method", "top"), float(offset_tag.text)
    pos_tag = tag.find("position", recursive=False)
    if pos_tag is None:
        return "top", 0.0
    return pos_tag.get("type", "top"), float(pos_tag.text)


def _relative_position(method, offset, inner_length, outer_length):
    if method == "top":
        return offset
    if method == "middle":
        return offset + (outer_length - inner_length) / 2
    if method == "bottom":
        return offset + (outer_length - inner_length)
    if method == "after":
        return outer_length + offset
    return offset  # "absolute" handled by the caller


# ---------------------------------------------------------------------------
# Component nodes
# ---------------------------------------------------------------------------


class Node:
    """One parsed component with everything the mass model needs."""

    def __init__(self, tag, kind, parent):
        self.tag = tag
        self.kind = kind
        self.parent = parent
        self.children = []
        self.name = _text(tag, "name", "")
        self.stage = parent.stage if parent else 0
        # overrides
        self.override_mass = None
        text = _text(tag, "overridemass", None)
        if text is not None:
            self.override_mass = max(float(text), 0.0)
        self.override_subcomponents_mass = (
            _text(tag, "overridesubcomponentsmass", "false") == "true"
        )
        self.override_cgx = None
        text = _text(tag, "overridecg", None)
        if text is not None:
            self.override_cgx = float(text)
        self.override_subcomponents_cg = (
            _text(tag, "overridesubcomponentscg", "false") == "true"
        )
        if _text(tag, "overridesubcomponents", None) == "true":
            # legacy 15.03-era single flag: applies to mass AND CG overrides
            self.override_subcomponents_mass = True
            self.override_subcomponents_cg = True
        # generic geometry / placement
        self.length = _float(tag, "length", 0.0)
        self.abs_x = 0.0
        self.density = _material_density(tag)
        self.radial_position = _float(tag, "radialposition", 0.0)
        self.radial_direction = math.radians(_float(tag, "radialdirection", 0.0))
        self.instance_count = int(_float(tag, "instancecount", 1))
        self.instance_separation = _float(tag, "instanceseparation", 0.0)
        self.angle_offset = math.radians(_float(tag, "angleoffset", 0.0))

    # populated by the per-kind initializers below
    def is_massive(self):
        return self.kind not in ("rocket", "stage")


def parse_rocket(soup):
    """Parse the full component tree with absolute positions."""
    rocket_tag = soup.find("rocket")
    root = Node(rocket_tag, "rocket", None)
    openrocket_tag = soup.find("openrocket")
    root.creator = openrocket_tag.get("creator", "") if openrocket_tag else ""
    # OpenRocket <= 23.09 adds shoulders to mass/CG but NOT to the unit
    # inertias ("The moments of inertia are not explicitly corrected for the
    # shoulders"); 24.12 corrects the inertias too.
    root.shoulder_moi = not any(v in root.creator for v in ("22.02", "23.09", "15.03"))
    subcomponents = rocket_tag.find("subcomponents", recursive=False)
    stage_tags = (
        subcomponents.find_all("stage", recursive=False) if subcomponents else []
    )
    cursor = 0.0
    for stage_index, stage_tag in enumerate(stage_tags):
        stage = Node(stage_tag, "stage", root)
        stage.stage = stage_index
        stage.abs_x = cursor
        root.children.append(stage)
        stage_sub = stage_tag.find("subcomponents", recursive=False)
        children = stage_sub.find_all(recursive=False) if stage_sub else []
        for child in children:
            if child.name not in SYMMETRIC_KINDS:
                continue
            node = _parse_component(child, stage, stage_index)
            method, offset = _axial_offset(child)
            if method == "absolute":
                node.abs_x = offset
            else:
                node.abs_x = cursor + (offset if method == "after" else 0.0)
            cursor = node.abs_x + node.length
            stage.children.append(node)
            _parse_children(child, node, stage_index)
        stage.length = cursor - stage.abs_x
    _resolve_symmetric_radii(root)
    _resolve_ring_radii(root)
    return root


def _parse_component(tag, parent, stage_index):
    node = Node(tag, tag.name, parent)
    node.stage = stage_index
    if tag.name in SYMMETRIC_KINDS:
        _init_symmetric(node, tag)
    elif tag.name in FIN_KINDS:
        _init_finset(node, tag)
    elif tag.name in RING_KINDS:
        _init_ring(node, tag)
    elif tag.name in MASS_OBJECT_KINDS:
        _init_mass_object(node, tag)
    elif tag.name == "launchlug":
        _init_launch_lug(node, tag)
    elif tag.name == "railbutton":
        _init_rail_button(node, tag)
    return node


def _parse_children(parent_tag, parent_node, stage_index):
    sub = parent_tag.find("subcomponents", recursive=False)
    if sub is None:
        return
    for child in sub.find_all(recursive=False):
        if child.name not in ALL_KINDS or child.name in SYMMETRIC_KINDS:
            continue
        node = _parse_component(child, parent_node, stage_index)
        method, offset = _axial_offset(child)
        if method == "absolute":
            node.abs_x = offset
        else:
            node.abs_x = parent_node.abs_x + _relative_position(
                method, offset, node.length, parent_node.length
            )
        parent_node.children.append(node)
        _parse_children(child, node, stage_index)


# -- per-kind initialization -------------------------------------------------


def _init_symmetric(node, tag):
    # OpenRocket serializes a filled component as <thickness>filled</thickness>
    thickness_text = (_text(tag, "thickness", "0") or "0").strip().lower()
    node.filled = thickness_text == "filled"
    node.thickness = 0.0 if node.filled else _float(tag, "thickness", 0.0)
    node.shape = _text(tag, "shape", None)
    node.shape_param = _float(
        tag,
        "shapeparameter",
        {"ogive": 1.0, "power": 0.5, "parabolic": 1.0}.get(node.shape, 0.0),
    )
    if node.kind == "nosecone":
        node.fore_spec = (0.0, False)
        node.aft_spec = _radius_spec(tag, "aftradius")
        node.flipped = _text(tag, "isflipped", "false") == "true"
        if node.flipped:
            node.fore_spec, node.aft_spec = node.aft_spec, node.fore_spec
        node.clipped = False
    elif node.kind == "transition":
        node.fore_spec = _radius_spec(tag, "foreradius")
        node.aft_spec = _radius_spec(tag, "aftradius")
        clipped_text = _text(tag, "shapeclipped", None)
        node.clipped = (
            node.shape in ("ellipsoid", "power", "haack")
            if clipped_text is None
            else clipped_text == "true"
        )
    else:  # bodytube
        node.fore_spec = _radius_spec(tag, "radius")
        node.aft_spec = node.fore_spec
        node.clipped = False
    # shoulders (transitions and nose cones)
    for side in ("fore", "aft"):
        setattr(
            node, side + "_shoulder_radius", _float(tag, side + "shoulderradius", 0.0)
        )
        setattr(
            node, side + "_shoulder_length", _float(tag, side + "shoulderlength", 0.0)
        )
        setattr(
            node,
            side + "_shoulder_thickness",
            _float(tag, side + "shoulderthickness", 0.0),
        )
        setattr(
            node,
            side + "_shoulder_capped",
            _text(tag, side + "shouldercapped", "false") == "true",
        )
    if getattr(node, "flipped", False):
        # a flipped nose cone (tail cone) carries its shoulder on the FORE
        # side at runtime, exactly as NoseCone.setFlipped does in OpenRocket
        for field in ("radius", "length", "thickness", "capped"):
            fore = getattr(node, "fore_shoulder_" + field)
            aft = getattr(node, "aft_shoulder_" + field)
            setattr(node, "fore_shoulder_" + field, aft)
            setattr(node, "aft_shoulder_" + field, fore)
    node.fore_radius = None
    node.aft_radius = None


def _init_finset(node, tag):
    node.fin_count = int(_float(tag, "fincount", _float(tag, "instancecount", 1)))
    node.fin_count = min(max(node.fin_count, 1), 8)  # FinSet clamps to 1..8
    node.thickness = _float(tag, "thickness", 0.003)
    node.cross_section = (_text(tag, "crosssection", "square") or "square").lower()
    node.cant = math.radians(_float(tag, "cant", 0.0))
    if node.cant:
        logger.warning(
            "fin set %r has a cant angle; canted-fin root geometry is not "
            "modeled and the fin mass/CG may deviate slightly",
            node.name,
        )
    node.fillet_radius = _float(tag, "filletradius", 0.0)
    node.fillet_density = _material_density(tag, "filletmaterial")
    if node.kind == "trapezoidfinset":
        node.root_chord = _float(tag, "rootchord", 0.0)
        node.tip_chord = _float(tag, "tipchord", 0.0)
        node.sweep = _float(tag, "sweeplength", 0.0)
        node.height = _float(tag, "height", 0.0)
        node.length = node.root_chord
    elif node.kind == "freeformfinset":
        points_tag = tag.find("finpoints")
        node.points = [
            (float(p["x"]), float(p["y"]))
            for p in (points_tag.find_all("point") if points_tag else [])
        ]
        node.length = node.points[-1][0] - node.points[0][0] if node.points else 0.0
    else:  # ellipticalfinset
        node.root_chord = _float(tag, "rootchord", 0.0)
        node.height = _float(tag, "height", 0.0)
        node.length = node.root_chord
    # fin tab: the last <tabposition> wins; relativeto maps onto AxialMethod
    node.tab_height = _float(tag, "tabheight", 0.0)
    node.tab_length = _float(tag, "tablength", 0.0)
    node.tab_position = 0.0
    tabs = tag.find_all("tabposition", recursive=False)
    if tabs:
        last = tabs[-1]
        relative = (last.get("relativeto", "middle") or "middle").lower()
        if "front" in relative or relative == "top":
            method = "top"
        elif "end" in relative or relative == "bottom":
            method = "bottom"
        else:
            method = "middle"
        offset = float(last.get_text())
        node.tab_position = _relative_position(
            method, offset, node.tab_length, node.length
        )
        # NOTE: OpenRocket does NOT clamp the tab position at load time --
        # a slightly negative tab front (seen in real files) is kept as-is


def _init_ring(node, tag):
    node.outer_spec = _radius_spec(tag, "outerradius")
    node.inner_spec = _radius_spec(tag, "innerradius")
    node.thickness = _float(tag, "thickness", 0.0)
    node.outer_radius = None
    node.inner_radius = None
    if node.kind == "bulkhead":
        node.inner_spec = (0.0, False)


def _init_mass_object(node, tag):
    node.packed_length = _float(tag, "packedlength", 0.0)
    node.packed_radius = _radius_spec(tag, "packedradius")[0] or 0.0
    node.length = node.packed_length
    if node.kind == "masscomponent":
        node.mass = _float(tag, "mass", 0.0)
    elif node.kind == "parachute":
        node.diameter = _float(tag, "diameter", 0.0)
        node.line_count = int(_float(tag, "linecount", 0))
        node.line_length = _float(tag, "linelength", 0.0)
        node.line_density = _material_density(tag, "linematerial")
    elif node.kind == "streamer":
        node.strip_length = _float(tag, "striplength", 0.0)
        node.strip_width = _float(tag, "stripwidth", 0.0)
    elif node.kind == "shockcord":
        node.cord_length = _float(tag, "cordlength", 0.0)


def _init_launch_lug(node, tag):
    node.radius = _float(tag, "radius", 0.0)
    node.thickness = _float(tag, "thickness", 0.0)
    node.inner_radius = max(node.radius - node.thickness, 0.0)


def _init_rail_button(node, tag):
    node.outer_diameter = _float(tag, "outerdiameter", 0.0097)
    node.inner_diameter = _float(tag, "innerdiameter", 0.008)
    node.total_height = _float(tag, "height", 0.0097)
    node.base_height = _float(tag, "baseheight", 0.002)
    node.flange_height = _float(tag, "flangeheight", 0.002)
    node.screw_height = _float(tag, "screwheight", 0.0)


# -- radius resolution -------------------------------------------------------


def _symmetric_nodes(root):
    result = []
    for stage in root.children:
        result.extend(c for c in stage.children if c.kind in SYMMETRIC_KINDS)
    return result


def _resolve_symmetric_radii(root):
    comps = _symmetric_nodes(root)
    for i, comp in enumerate(comps):
        comp.fore_radius = _resolve_radius(comp.fore_spec, comps, i, True)
        comp.aft_radius = _resolve_radius(comp.aft_spec, comps, i, False)
        if comp.kind == "bodytube":
            comp.aft_radius = comp.fore_radius
        comp.radius_fn = _radius_function(comp)


def _resolve_radius(spec, comps, index, prefer_previous):
    value, auto = spec if isinstance(spec, tuple) else (spec, False)
    if not auto:
        return value if value is not None else DEFAULT_RADIUS
    if value is not None:
        return value  # cached "auto <value>" written by OpenRocket
    order = [index - 1, index + 1] if prefer_previous else [index + 1, index - 1]
    for j in order:
        if 0 <= j < len(comps):
            neighbor = comps[j].aft_spec if j < index else comps[j].fore_spec
            nv, nauto = neighbor if isinstance(neighbor, tuple) else (neighbor, False)
            if nv is not None:
                return nv
    return DEFAULT_RADIUS


def _radius_function(comp):
    if comp.kind == "bodytube":
        radius = comp.fore_radius

        def constant(_x):
            return radius

        return constant
    return transition_radius_function(
        comp.fore_radius,
        comp.aft_radius,
        comp.length,
        comp.shape,
        comp.shape_param,
        comp.clipped,
    )


def _inner_radius_at(comp, x):
    """Parent's inner radius at ``x`` (clamped into the parent span)."""
    x = min(max(x, 0.0), comp.length)
    if comp.kind == "bodytube":
        if getattr(comp, "filled", False):
            return 0.0
        return max(comp.fore_radius - comp.thickness, 0.0)
    return max(comp.radius_fn(x) - comp.thickness, 0.0)


def _resolve_ring_radii(root):
    def walk(node):
        for child in node.children:
            if child.kind in RING_KINDS:
                _resolve_one_ring(child)
            walk(child)

    walk(root)


def _resolve_one_ring(ring):
    parent = ring.parent
    rel_x = ring.abs_x - parent.abs_x
    outer, outer_auto = ring.outer_spec
    if outer_auto and outer is None:
        if parent.kind in SYMMETRIC_KINDS:
            outer = min(
                _inner_radius_at(parent, rel_x),
                _inner_radius_at(parent, rel_x + ring.length),
            )
        elif parent.kind in RING_KINDS:
            outer = parent.inner_radius if parent.inner_radius is not None else 0.0
        else:
            outer = 0.0
    ring.outer_radius = outer if outer is not None else 0.0

    if ring.kind == "bulkhead":
        ring.inner_radius = 0.0
    elif ring.kind == "centeringring":
        inner, inner_auto = ring.inner_spec
        if inner_auto and inner is None:
            inner = 0.0
            for sibling in parent.children:
                if sibling.kind != "innertube":
                    continue
                sib_rel0 = sibling.abs_x - parent.abs_x
                sib_rel1 = sib_rel0 + sibling.length
                ring_rel0 = rel_x
                ring_rel1 = rel_x + ring.length
                if ring_rel1 < sib_rel0 or ring_rel0 > sib_rel1:
                    continue
                outer_r = sibling.outer_spec[0] or 0.0
                inner = max(inner, outer_r)
            inner = min(inner, ring.outer_radius)
        ring.inner_radius = inner if inner is not None else 0.0
    elif ring.kind in ("innertube", "tubecoupler", "engineblock"):
        # ThicknessRingComponent: inner = outer - thickness
        ring.inner_radius = max(ring.outer_radius - ring.thickness, 0.0)
    else:
        inner, _ = ring.inner_spec
        ring.inner_radius = inner or 0.0


# ---------------------------------------------------------------------------
# Per-component mass properties (component frame)
# ---------------------------------------------------------------------------


def _ring_mass(outer, inner, length, density):
    return math.pi * max(outer * outer - inner * inner, 0.0) * length * density


def _ring_long_unit(outer, inner, length):
    return (3 * (inner * inner + outer * outer) + length * length) / 12


def _ring_rot_unit(outer, inner):
    return (inner * inner + outer * outer) / 2


def component_mass_properties(node):
    """(cg: CM in component frame, rot_unit, long_unit) for one component."""
    handler = _HANDLERS.get(node.kind)
    if handler is None:
        return CM(), 0.0, 0.0
    return handler(node)


def _props_symmetric(node):
    if node.kind == "bodytube":
        outer = node.fore_radius
        inner = (
            0.0 if getattr(node, "filled", False) else max(outer - node.thickness, 0.0)
        )
        volume = math.pi * (outer * outer - inner * inner) * node.length
        mass = volume * node.density
        return (
            CM(node.length / 2, 0, 0, mass),
            _ring_rot_unit(outer, inner),
            _ring_long_unit(outer, inner, node.length),
        )
    volume, cgx, rot_unit, long_unit = _integrate_symmetric(node)
    parts = _shoulder_parts(node)
    if parts:
        volumes = [volume] + [p[0] for p in parts]
        cgxs = [cgx] + [p[1] for p in parts]
        total_volume = sum(volumes)
        total_mass = total_volume * node.density
        if total_mass < EPSILON:
            return CM(), 0.0, 0.0
        cg_x = sum(v * x for v, x in zip(volumes, cgxs)) / total_volume
        if _shoulder_moi_enabled(node):
            # 24.12+: shoulders enter the unit inertias too
            rot_mois = [rot_unit * volume] + [p[2] * p[0] for p in parts]
            long_mois = [long_unit * volume] + [p[3] * p[0] for p in parts]
            long_total = sum(
                moi + (cg_x - x) ** 2 * v for moi, x, v in zip(long_mois, cgxs, volumes)
            )
            rot_unit = sum(rot_mois) / total_volume
            long_unit = long_total / total_volume
        # <= 23.09: inertias keep the shoulder-less integration values
        return CM(cg_x, 0, 0, total_mass), rot_unit, long_unit
    mass = volume * node.density
    return CM(cgx, 0, 0, mass), rot_unit, long_unit


def _shoulder_moi_enabled(node):
    while node.parent is not None:
        node = node.parent
    return getattr(node, "shoulder_moi", True)


def _integrate_symmetric(node):
    """``SymmetricComponent.calculateProperties``: hollow 128-frustum sums.

    Returns (volume, cg_x, rotational_unit_inertia, longitudinal_unit_inertia)
    with the unit inertias about the CG (per kg).
    """
    length = node.length
    if length < EPSILON:
        return 0.0, length / 2, 0.0, 0.0
    radius = node.radius_fn
    filled = getattr(node, "filled", False)
    thickness = max(node.fore_radius, node.aft_radius) if filled else node.thickness
    volume = full_volume = cgx = rot_i = long_i = 0.0
    for n in range(128):
        x1 = n * length / 128
        x2 = (n + 1) * length / 128
        step = x2 - x1
        r1o, r2o = radius(x1), radius(x2)
        hyp = math.hypot(r2o - r1o, step)
        height = thickness * hyp / step
        if filled:
            r1i = r2i = 0.0
        else:
            r1i = max(r1o - height, 0.0)
            r2i = max(r2o - height, 0.0)
        full_v, full_cg = _frustum_cg(step, r1o, r2o)
        inner_v, inner_cg = _frustum_cg(step, r1i, r2i)
        dv = full_v - inner_v
        if dv > 0:
            dcg = (full_cg * full_v - inner_cg * inner_v) / dv
        else:
            dcg = step / 2
        cgx += dv * (x1 + dcg)
        ixx = (
            _frustum_rot_unit(r1o, r2o) * full_v - _frustum_rot_unit(r1i, r2i) * inner_v
        )
        iyy = _frustum_long_moi(step, r1o, r2o, full_v, full_cg) - _frustum_long_moi(
            step, r1i, r2i, inner_v, inner_cg
        )
        iyy += dv * (x1 + dcg) ** 2
        volume += dv
        full_volume += full_v
        rot_i += ixx
        long_i += iyy
    if volume > 0:
        rot_i /= volume
        long_i /= volume
    volume *= math.pi / 3
    cgx *= math.pi / 3
    rot_i *= 3.0 / 10.0
    if volume < 1e-10:
        return 0.0, length / 2, 0.0, 0.0
    cg_x = cgx / volume
    long_i -= cg_x * cg_x
    return volume, cg_x, rot_i, long_i


def _frustum_cg(length, r1, r2):
    """``calculateCG``: (3/pi-scaled volume, cg from fore end)."""
    volume = length * (r1 * r1 + r1 * r2 + r2 * r2)
    if volume < EPSILON:
        return volume, length / 2
    cg = (
        length
        * (r1 * r1 + 2 * r1 * r2 + 3 * r2 * r2)
        / (4 * (r1 * r1 + r1 * r2 + r2 * r2))
    )
    return volume, cg


def _frustum_rot_unit(r1, r2):
    """``calculateUnitRotMOI`` (10/3-scaled)."""
    if abs(r1 - r2) < EPSILON:
        return 10 * r1 * r1 / 6
    return (r2**5 - r1**5) / (r2**3 - r1**3)


def _cone_long_moi(h, r):
    m = r * r * h
    return 3 * m * (r * r / 20 + h * h / 5)


def _frustum_long_moi(length, r1, r2, volume, cg):
    """``calculateLongMOI``: about the frustum CG (3/pi-scaled units)."""
    if abs(r1 - r2) < EPSILON:
        return volume * (3 * r1 * r1 + length * length) / 12
    shift_cg = cg
    if r1 > r2:
        r1, r2 = r2, r1
        shift_cg = length - cg
    h2 = length * r2 / (r2 - r1)
    h1 = h2 * r1 / r2
    return (
        _cone_long_moi(h2, r2) - _cone_long_moi(h1, r1) - (h1 + shift_cg) ** 2 * volume
    )


def _shoulder_parts(node):
    """Transition/nose shoulder + cap contributions.

    Returns a list of (volume, cg_x, rot_unit, long_unit) parts, empty when
    the component has no shoulders (the MINFEATURE = 1 mm gate).
    """
    if node.kind not in ("nosecone", "transition"):
        return []
    fore_len = node.fore_shoulder_length
    aft_len = node.aft_shoulder_length
    if fore_len <= 0.001 and aft_len <= 0.001:
        return []
    parts = []
    length = node.length
    if node.fore_shoulder_capped:
        thickness = node.fore_shoulder_thickness
        inner = max(node.fore_shoulder_radius - thickness, 0.0)
        volume = _ring_mass(inner, 0.0, thickness, 1.0)
        parts.append(
            (
                volume,
                (-fore_len + (thickness - fore_len)) / 2,
                _ring_rot_unit(inner, 0.0),
                _ring_long_unit(inner, 0.0, thickness),
            )
        )
    if fore_len > 0.001:
        outer = node.fore_shoulder_radius
        inner = max(outer - node.fore_shoulder_thickness, 0.0)
        volume = _ring_mass(outer, inner, fore_len, 1.0)
        parts.append(
            (
                volume,
                -fore_len / 2,
                _ring_rot_unit(outer, inner),
                _ring_long_unit(outer, inner, fore_len),
            )
        )
    if aft_len > 0.001:
        outer = node.aft_shoulder_radius
        inner = max(outer - node.aft_shoulder_thickness, 0.0)
        volume = _ring_mass(outer, inner, aft_len, 1.0)
        parts.append(
            (
                volume,
                length + aft_len / 2,
                _ring_rot_unit(outer, inner),
                _ring_long_unit(outer, inner, aft_len),
            )
        )
    if node.aft_shoulder_capped:
        thickness = node.aft_shoulder_thickness
        inner = max(node.aft_shoulder_radius - thickness, 0.0)
        volume = _ring_mass(inner, 0.0, thickness, 1.0)
        # NOTE: OpenRocket (bug, present in 24.12 and master) uses the FORE
        # shoulder thickness as the disc length of the AFT cap's MOI.
        parts.append(
            (
                volume,
                (2 * (length + aft_len) - thickness) / 2,
                _ring_rot_unit(inner, 0.0),
                _ring_long_unit(inner, 0.0, node.fore_shoulder_thickness),
            )
        )
    return parts


# -- fins ---------------------------------------------------------------------


def _rotate_x(cm, angle):
    if angle == 0.0:
        return cm
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    return CM(cm.x, cm.y * cos_a - cm.z * sin_a, cm.y * sin_a + cm.z * cos_a, cm.w)


def _curve_integral(points):
    """``FinSet.calculateCurveIntegral``: area + centroid of a closed curve."""
    centroid = CM()
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        area = (x2 - x1) * (y1 + y2) * 0.5
        if _java_equals_rel(0.0, area):
            continue
        common = 1.0 / (3 * (y2 + y1))
        x_ctr = common * (x1 * (2 * y1 + y2) + x2 * (2 * y2 + y1))
        y_ctr = common * (y2 * y1 + y2 * y2 + y1 * y1)
        centroid = centroid.average(CM(x_ctr, y_ctr, 0, area))
    if centroid.w < 0:
        centroid = CM(centroid.x, -centroid.y, centroid.z, abs(centroid.w))
    return centroid


def _java_equals_rel(a, b, eps=EPSILON):
    absb = abs(b)
    if absb < eps / 2:
        return abs(a) < eps / 2
    return abs(a - b) < eps * absb


def _fin_geometry(node):
    """(fin_points, root_points_rel, span, fin_front_x, fin_front_y)."""
    parent = node.parent
    curved = parent.kind in ("transition", "nosecone") and (parent.shape != "conical")
    x_front = node.abs_x - parent.abs_x
    x_end = x_front + node.length
    y_front = parent.radius_fn(x_front)
    root_rel = mount_points(
        parent.radius_fn, parent.length, x_front, x_end, -x_front, -y_front, curved
    )
    if node.kind == "trapezoidfinset":
        fin_points = trapezoid_fin_points(
            node.root_chord, node.tip_chord, node.sweep, node.height, root_rel
        )
        span = node.height
    elif node.kind == "ellipticalfinset":
        fin_points = elliptical_fin_points(node.root_chord, node.height)
        if len(root_rel) > 1:
            fin_points[0] = root_rel[0]
            fin_points[-1] = root_rel[-1]
        span = node.height
    else:
        fin_points = list(node.points)
        if len(root_rel) > 1:
            fin_points[0] = root_rel[0]
            fin_points[-1] = root_rel[-1]
        max_y = max(y for _, y in fin_points)
        span = max_y - min(fin_points[-1][1], 0)
    return fin_points, root_rel, span, x_front, y_front


def _props_finset(node):
    parent = node.parent
    if parent.kind not in SYMMETRIC_KINDS:
        return CM(), 0.0, 0.0
    fin_points, root_rel, span, x_front, y_front = _fin_geometry(node)

    # planform centroid: fin outline (centerline frame) + reversed mount curve
    upper = [(x, y + y_front) for x, y in fin_points]
    curved = parent.kind in ("transition", "nosecone") and (parent.shape != "conical")
    lower = mount_points(
        parent.radius_fn,
        parent.length,
        x_front,
        x_front + node.length,
        -x_front,
        0.0,
        curved,
    )
    wetted = _curve_integral(upper + list(reversed(lower)))
    area = wetted.w
    wetted_volume = (
        area * node.thickness * CROSS_SECTION_VOLUME.get(node.cross_section, 1.0)
    )
    fin_mass = wetted_volume * node.density

    # tab
    tab = CM()
    tab_volume = 0.0
    if node.tab_height * node.tab_length >= 1e-8:
        tab = _tab_centroid(node, x_front, y_front, root_rel, curved)
        tab_volume = tab.w * node.thickness
    tab_mass = tab_volume * node.density

    # fillet
    fillet = CM()
    fillet_volume = 0.0
    if node.fillet_radius > 0:
        fillet = _fillet_centroid(node, root_rel, x_front, y_front)
        fillet_volume = fillet.w
    fillet_mass = fillet_volume * node.fillet_density

    each_mass = fin_mass + tab_mass + fillet_mass
    # Java re-weights each centroid with its MASS before averaging
    each_cm = (
        wetted.with_weight(fin_mass)
        .average(tab.with_weight(tab_mass))
        .average(fillet.with_weight(fillet_mass))
        .with_weight(each_mass)
    )
    if node.fin_count == 1:
        cm = _rotate_x(each_cm, node.angle_offset)
    else:
        cm = CM(each_cm.x, 0.0, each_cm.z, each_mass * node.fin_count)

    # unit inertias (FinSet.java 806-884)
    w = node.length
    h = span
    if h * w == 0:
        w2 = h2 = area
    else:
        w2 = w * area / h if h else area
        h2 = h * area / w if w else area
    long_unit = (h2 + 2 * w2) / 24
    rot_h2 = h * area / w if w else area
    rot_unit = rot_h2 / 12
    if node.fin_count > 1:
        body_radius = y_front
        long_unit += (math.sqrt(h2) / 2 + body_radius) ** 2 / 2
        rot_unit += (math.sqrt(rot_h2) / 2 + body_radius) ** 2
    return cm, rot_unit, long_unit


def _tab_centroid(node, x_front, y_front, root_rel, curved):
    parent = node.parent
    x_tab_front = node.tab_position
    x_tab_trail = node.tab_position + node.tab_length
    upper = mount_points(
        parent.radius_fn,
        parent.length,
        x_front + x_tab_front,
        x_front + x_tab_trail,
        -x_front,
        0.0,
        curved,
    )
    # tab points in fin frame (y relative to the fin-front radius)
    y_tab_front = parent.radius_fn(x_front + x_tab_front) - y_front
    y_tab_trail = parent.radius_fn(x_front + x_tab_trail) - y_front
    y_bottom = min(y_tab_front, y_tab_trail) - node.tab_height
    tab_points = [
        (x_tab_front, y_tab_front),
        (x_tab_front, y_bottom),
        (x_tab_trail, y_bottom),
        (x_tab_trail, y_tab_trail),
    ]
    inner_root = [(x, y) for x, y in root_rel if x_tab_front < x < x_tab_trail]
    lower = tab_points + list(reversed([tab_points[0]] + inner_root))
    lower = [(x, y + y_front) for x, y in lower]  # to centerline frame
    return _curve_integral(upper + list(reversed(lower)))


def _fillet_centroid(node, root_rel, x_front, y_front):
    """``calculateFilletVolumeCentroid`` (volume as weight, per fin)."""
    parent = node.parent
    if node.fillet_radius <= 0 or parent.kind not in SYMMETRIC_KINDS:
        return CM()
    centroid = CM()
    fillet = node.fillet_radius
    for (x1, y1), (x2, y2) in zip(root_rel, root_rel[1:]):
        x_avg = (x1 + x2) / 2  # fin-frame midpoint
        # QUIRK preserved: OpenRocket samples the parent radius with the
        # FIN-frame coordinate (FinSet.calculateFilletVolumeCentroid)
        body_radius = parent.radius_fn(x_avg)
        hyp = fillet + body_radius
        try:
            inner_arc = math.asin(fillet / hyp)
            outer_arc = math.acos(fillet / hyp)
            triangle = math.tan(outer_arc) * fillet * fillet / 2
            area = (
                triangle
                - outer_arc * fillet * fillet / 2
                - inner_arc * body_radius * body_radius / 2
            )
        except ValueError:
            area = 0.0
        if math.isnan(area):
            area = 0.0
        area *= 2  # both sides of the fin
        y_centroid = body_radius + fillet / 5
        segment_length = math.hypot(x2 - x1, y2 - y1)
        centroid = centroid.average(CM(x_avg, y_centroid, 0, segment_length * area))
    if node.fin_count == 1:
        centroid = _rotate_x(centroid, node.angle_offset)
    else:
        centroid = CM(centroid.x, 0.0, 0.0, centroid.w)
    return centroid


# -- other components ---------------------------------------------------------


def _props_launch_lug(node):
    volume = (
        node.length
        * math.pi
        * (node.radius**2 - node.inner_radius**2)
        * node.instance_count
    )
    mass = volume * node.density
    parent = node.parent
    parent_radius = (
        parent.radius_fn(node.abs_x - parent.abs_x)
        if parent.kind in SYMMETRIC_KINDS
        else 0.0
    )
    standoff = parent_radius + node.radius
    cm = CM(
        node.length / 2 + node.instance_separation * (node.instance_count - 1) / 2,
        math.cos(node.angle_offset) * standoff,
        math.sin(node.angle_offset) * standoff,
        mass,
    )
    return (
        cm,
        _ring_rot_unit(node.radius, node.inner_radius),
        _ring_long_unit(node.radius, node.inner_radius, node.length),
    )


def _props_rail_button(node):
    od2 = (node.outer_diameter / 2) ** 2
    id2 = (node.inner_diameter / 2) ** 2
    inner_height = node.total_height - node.flange_height - node.base_height
    volume = (
        math.pi * od2 * node.flange_height
        + math.pi * id2 * inner_height
        + math.pi * od2 * node.base_height
        + (2.0 / 3.0) * math.pi * od2 * node.screw_height
    ) * node.instance_count
    mass = volume * node.density
    # pi-and-rho-factored part masses for the height CM
    m_base = od2 * node.base_height
    m_inner = id2 * inner_height
    m_flange = od2 * node.flange_height
    m_screw = (2.0 / 3.0) * od2 * node.screw_height
    total = m_base + m_inner + m_flange + m_screw
    if total > 0:
        height_cm = (
            m_base * node.base_height / 2
            + m_inner * (node.base_height + inner_height / 2)
            + m_flange * (node.total_height - node.flange_height / 2)
            + m_screw * (node.total_height + 4 * node.screw_height / (3 * math.pi))
        ) / total
    else:
        height_cm = 0.0
    parent = node.parent
    parent_radius = (
        parent.radius_fn(node.abs_x - parent.abs_x)
        if parent.kind in SYMMETRIC_KINDS
        else 0.0
    )
    standoff = parent_radius + height_cm
    cm = CM(
        node.instance_separation * (node.instance_count - 1) / 2,
        math.cos(node.angle_offset) * standoff,
        math.sin(node.angle_offset) * standoff,
        mass,
    )
    return cm, 0.0, 0.0


def _props_ring(node):
    instance_mass = _ring_mass(
        node.outer_radius, node.inner_radius, node.length, node.density
    )
    mass = instance_mass * node.instance_count
    if node.instance_count == 1:
        cm = CM(node.length / 2, 0, 0, mass)
    else:
        # line instances at (i * separation, 0, 0)
        acc = CM()
        for i in range(node.instance_count):
            acc = acc.average(CM(i * node.instance_separation, 0, 0, instance_mass))
        cm = CM(acc.x + node.length / 2, acc.y, acc.z, mass)
    return (
        cm,
        _ring_rot_unit(node.outer_radius, node.inner_radius),
        _ring_long_unit(node.outer_radius, node.inner_radius, node.length),
    )


def _props_mass_object(node):
    if node.kind == "masscomponent":
        mass = node.mass
    elif node.kind == "parachute":
        area = math.pi * (node.diameter / 2) ** 2
        mass = area * node.density + (
            node.line_count * node.line_length * node.line_density
        )
    elif node.kind == "streamer":
        mass = node.strip_length * node.strip_width * node.density
    else:  # shockcord
        mass = node.density * node.cord_length
    shift_y = node.radial_position * math.cos(node.radial_direction)
    shift_z = node.radial_position * math.sin(node.radial_direction)
    cm = CM(node.length / 2, shift_y, shift_z, mass)
    radius = node.packed_radius
    rot_unit = radius * radius / 2
    long_unit = (3 * radius * radius + node.length * node.length) / 12
    return cm, rot_unit, long_unit


_HANDLERS = {
    "nosecone": _props_symmetric,
    "transition": _props_symmetric,
    "bodytube": _props_symmetric,
    "trapezoidfinset": _props_finset,
    "freeformfinset": _props_finset,
    "ellipticalfinset": _props_finset,
    "launchlug": _props_launch_lug,
    "railbutton": _props_rail_button,
    "innertube": _props_ring,
    "tubecoupler": _props_ring,
    "centeringring": _props_ring,
    "bulkhead": _props_ring,
    "engineblock": _props_ring,
    "masscomponent": _props_mass_object,
    "parachute": _props_mass_object,
    "streamer": _props_mass_object,
    "shockcord": _props_mass_object,
}


# ---------------------------------------------------------------------------
# MassCalculation port
# ---------------------------------------------------------------------------


class _Calculation:
    """Mirror of ``MassCalculation``: running CM + per-component bodies."""

    def __init__(self):
        self.cm = CM()
        self.bodies = []

    def add_mass(self, point):
        if self.cm.w < MIN_MASS:
            self.cm = point
        else:
            self.cm = self.cm.average(point)

    def merge(self, other):
        self.add_mass(other.cm)
        self.bodies.extend(other.bodies)


def _calculate_structure(node, active_stages):
    """``MassCalculation.calculateStructure`` for one component subtree."""
    calc = _Calculation()
    children = _Calculation()
    for child in node.children:
        child_calc = _calculate_structure(child, active_stages)
        children.merge(child_calc)

    active = active_stages is None or node.stage in active_stages
    if node.kind == "rocket":
        active = True
    if active:
        if node.is_massive():
            local_cm, rot_unit, long_unit = component_mass_properties(node)
        else:
            local_cm, rot_unit, long_unit = CM(), 0.0, 0.0
        comp_cm = CM(node.abs_x + local_cm.x, local_cm.y, local_cm.z, local_cm.w)
        comp_zero_x = node.abs_x
        if node.override_mass is not None:
            if not node.is_massive():
                comp_cm = children.cm
            comp_cm = comp_cm.with_weight(node.override_mass)
            if node.override_subcomponents_mass:
                children.cm = children.cm.with_weight(0.0)
                # QUIRK: children's bodies keep their full inertia
        if node.override_cgx is not None:
            comp_cm = comp_cm.with_x(comp_zero_x + node.override_cgx)
            if node.override_subcomponents_cg:
                children.cm = children.cm.with_x(comp_cm.x)
        calc.add_mass(comp_cm)
        calc.bodies.append(
            Body(
                comp_cm,
                rot_unit * comp_cm.w,
                long_unit * comp_cm.w,
                long_unit * comp_cm.w,
            )
        )
    calc.merge(children)
    return calc


def structure_mass_properties(source, active_stages=None, shoulder_moi=None):
    """Structure (dry, motorless) mass properties of a .ork design.

    Parameters
    ----------
    source : path-like or BeautifulSoup or Node
        The design to analyze.
    active_stages : set of int, optional
        Stage indices considered active (default: all).
    shoulder_moi : bool, optional
        Force the shoulder-inertia convention (default: auto-detect from the
        file's creator version -- 24.12+ includes shoulders in the inertias).

    Returns
    -------
    MassProperties
    """
    if isinstance(source, Node):
        root = source
    else:
        soup = source if hasattr(source, "find_all") else read_ork_xml(source)
        root = parse_rocket(soup)
    if shoulder_moi is not None:
        root.shoulder_moi = shoulder_moi
    calc = _calculate_structure(root, active_stages)
    ixx, iyy = _rebased_sums(calc.bodies, calc.cm)
    return MassProperties(calc.cm, ixx, iyy)


def burnout_mass_properties(
    structure, motor_mass, motor_cm_x, motor_radius, motor_length
):
    """Combine structure properties with a motor at burnout (casing only).

    Reproduces ``RigidBody.add``: mass-weighted CM, then parallel-axis both
    bodies to the combined CM.  The motor is a filled cylinder on the axis.
    """
    if motor_mass <= 0:
        return structure
    motor_cm = CM(motor_cm_x, 0, 0, motor_mass)
    motor_ixx = (motor_radius**2 / 2) * motor_mass
    motor_iyy = ((3 * motor_radius**2 + motor_length**2) / 12) * motor_mass
    combined = structure.cm.average(motor_cm)
    bodies = [
        Body(
            structure.cm,
            structure.rotational_inertia,
            structure.longitudinal_inertia,
            structure.longitudinal_inertia,
        ),
        Body(motor_cm, motor_ixx, motor_iyy, motor_iyy),
    ]
    ixx, iyy = _rebased_sums(bodies, combined)
    return MassProperties(combined, ixx, iyy)
