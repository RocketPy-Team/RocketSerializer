"""Parse an OpenRocket .ork design into the component model the drag needs.

Pure XML parsing (BeautifulSoup, ``features="xml"``) -- no OpenRocket JVM.
Only drag-relevant, external components are modeled: nose cones, body tubes,
transitions, fin sets (trapezoidal / free-form / elliptical), tube fin sets,
launch lugs and rail buttons.  Internal components (mass objects, inner tubes,
parachutes, ...) do not participate in the aerodynamic build-up and are
skipped.

Positions follow OpenRocket's ``AxialMethod`` semantics; stage children stack
sequentially (each symmetric component starts where the previous one ends).
"""

import logging
import zipfile
from pathlib import Path

from bs4 import BeautifulSoup

from .geometry import (
    CLIPPABLE_SHAPES,
    FinGeometry,
    curve_integral_area,
    elliptical_fin_points,
    integrate_body,
    mount_points,
    transition_radius_function,
    trapezoid_fin_points,
)

logger = logging.getLogger(__name__)

DEFAULT_RADIUS = 0.025  # SymmetricComponent.DEFAULT_RADIUS
DEFAULT_REFERENCE_LENGTH = 0.01  # Rocket.DEFAULT_REFERENCE_LENGTH

#: ExternalComponent.Finish roughness heights in meters, XML literal -> k
FINISH_ROUGHNESS = {
    "rough": 500e-6,
    "roughunfinished": 250e-6,
    "unfinished": 150e-6,
    "normal": 60e-6,
    "smooth": 20e-6,
    "optimum": 5e-6,
    "polished": 2e-6,
    "finishpolished": 0.5e-6,
    "mirror": 0.0,
}


class Component:
    """Base external component: identity, finish and CD-override state."""

    kind = "component"

    def __init__(self, tag):
        self.name = _text(tag, "name", "")
        self.finish = _text(tag, "finish", "normal").lower()
        if self.finish not in FINISH_ROUGHNESS:
            logger.warning("unknown finish %r, using 'normal'", self.finish)
            self.finish = "normal"
        self.cd_override = _float_or_none(tag, "overridecd")
        self.cd_override_subcomponents = (
            _text(tag, "overridesubcomponentscd", "false") == "true"
        )
        self.instance_count = 1
        self.abs_x = 0.0  # absolute X of the component's fore end
        self.length = 0.0
        self.stage = 0


class SymmetricComp(Component):
    """Nose cone, transition or body tube (a surface of revolution)."""

    def __init__(self, tag, kind):
        Component.__init__(self, tag)
        self.kind = kind
        self.length = _float(tag, "length", 0.0)
        self.thickness = _float(tag, "thickness", 0.0)
        self.shape = _text(tag, "shape", None)
        self.shape_param = _float(tag, "shapeparameter", None)
        if kind == "nosecone":
            self.fore_spec = (0.0, False)
            self.aft_spec = _radius_spec(tag, "aftradius")
            if _text(tag, "isflipped", "false") == "true":
                self.fore_spec, self.aft_spec = self.aft_spec, self.fore_spec
            self.clipped = False  # NoseCone.isClipped() is always false
        elif kind == "transition":
            self.fore_spec = _radius_spec(tag, "foreradius")
            self.aft_spec = _radius_spec(tag, "aftradius")
            clipped_text = _text(tag, "shapeclipped", None)
            if clipped_text is None:
                self.clipped = self.shape in CLIPPABLE_SHAPES
            else:
                self.clipped = clipped_text == "true"
        else:  # bodytube
            self.fore_spec = _radius_spec(tag, "radius")
            self.aft_spec = self.fore_spec
            self.clipped = False
        if self.shape_param is None:
            self.shape_param = {"ogive": 1.0, "power": 0.5, "parabolic": 1.0}.get(
                self.shape, 0.0
            )
        # resolved by Rocket._resolve_radii()
        self.fore_radius = None
        self.aft_radius = None
        self._geometry = None

    def radius(self, x):
        """Outer radius at axial position ``x`` from the fore end."""
        if self.kind == "bodytube":
            return self.fore_radius
        return transition_radius_function(
            self.fore_radius,
            self.aft_radius,
            self.length,
            self.shape,
            self.shape_param,
            self.clipped,
        )(x)

    def _integrate(self):
        if self._geometry is None:
            if self.kind == "bodytube":
                r, length = self.fore_radius, self.length
                import math

                self._geometry = (
                    2 * math.pi * r * length,  # wet area (BodyTube analytic)
                    2 * r * length,
                    length / 2,
                    math.pi * r * r * length,
                )
            else:
                self._geometry = integrate_body(self.radius, self.length)
        return self._geometry

    @property
    def wet_area(self):
        return self._integrate()[0]

    @property
    def planform_area(self):
        return self._integrate()[1]

    @property
    def full_volume(self):
        return self._integrate()[3]


class FinSet(Component):
    """Trapezoidal, free-form or elliptical fin set."""

    kind = "finset"

    def __init__(self, tag, fin_kind):
        Component.__init__(self, tag)
        self.fin_kind = fin_kind
        self.fin_count = int(_float(tag, "fincount", _float(tag, "instancecount", 1)))
        self.instance_count = self.fin_count
        self.thickness = _float(tag, "thickness", 0.003)
        self.cross_section = _text(tag, "crosssection", "square").lower()
        self.cant = _float(tag, "cant", 0.0)
        if fin_kind == "trapezoidfinset":
            self.root_chord = _float(tag, "rootchord", 0.0)
            self.tip_chord = _float(tag, "tipchord", 0.0)
            self.sweep = _float(tag, "sweeplength", 0.0)
            self.height = _float(tag, "height", 0.0)
            self.length = self.root_chord
        elif fin_kind == "freeformfinset":
            self.points = [
                (float(p["x"]), float(p["y"]))
                for p in tag.find("finpoints").find_all("point")
            ]
            self.length = self.points[-1][0] - self.points[0][0]
        else:  # ellipticalfinset
            self.root_chord = _float(tag, "rootchord", 0.0)
            self.height = _float(tag, "height", 0.0)
            self.length = self.root_chord
        self.parent = None  # set during parsing
        self.rel_x = 0.0  # fin front x in the parent's frame
        self._geometry = None

    @property
    def span(self):
        if self.fin_kind == "trapezoidfinset":
            return self.height
        if self.fin_kind == "ellipticalfinset":
            return self.height
        max_y = max(y for _, y in self.points)
        return max_y - min(self.points[-1][1], 0)

    def fin_points(self, root_points):
        if self.fin_kind == "trapezoidfinset":
            return trapezoid_fin_points(
                self.root_chord, self.tip_chord, self.sweep, self.height, root_points
            )
        if self.fin_kind == "ellipticalfinset":
            points = elliptical_fin_points(self.root_chord, self.height)
        else:
            points = list(self.points)
        # OpenRocket snaps the first/last outline points onto the root curve
        if len(root_points) > 1:
            points[0] = root_points[0]
            points[-1] = root_points[-1]
        return points

    def x_extent(self):
        """(min, max) x of the fin outline in the fin frame (bounding box)."""
        if self.fin_kind == "trapezoidfinset":
            xs = [
                0.0,
                self.sweep,
                self.sweep + self.tip_chord,
                max(self.root_chord, 0.0001),
            ]
        elif self.fin_kind == "freeformfinset":
            xs = [x for x, _ in self.points]
        else:
            xs = [0.0, self.root_chord]
        return min(xs), max(xs)

    def geometry(self):
        """Compute the drag-relevant geometry (cached)."""
        if self._geometry is not None:
            return self._geometry
        parent = self.parent
        # NoseCone extends Transition in OpenRocket, so fins on any non-conical
        # nose cone or transition sample the curved root profile
        curved = parent.kind in ("transition", "nosecone") and (
            parent.shape != "conical"
        )
        x_front = self.rel_x
        x_end = x_front + self.length
        # points relative to (fin front, fin-front radius): the root curve
        y_front = parent.radius(x_front)
        root_rel = mount_points(
            parent.radius, parent.length, x_front, x_end, -x_front, -y_front, curved
        )
        fin_pts = self.fin_points(root_rel)
        # planform area: fin outline (absolute radius) over the mount curve
        upper = [(x, y + y_front) for x, y in fin_pts]
        lower = mount_points(
            parent.radius, parent.length, x_front, x_end, -x_front, 0.0, curved
        )
        area = curve_integral_area(upper + list(reversed(lower)))
        self._geometry = FinGeometry(fin_pts, root_rel, self.span, area)
        return self._geometry


class LaunchLug(Component):
    kind = "launchlug"

    def __init__(self, tag):
        Component.__init__(self, tag)
        self.radius = _float(tag, "radius", 0.0)
        self.length = _float(tag, "length", 0.0)
        self.thickness = _float(tag, "thickness", 0.0)
        self.instance_count = int(_float(tag, "instancecount", 1))
        self.instance_separation = _float(tag, "instanceseparation", 0.0)
        self.inner_radius = max(self.radius - self.thickness, 0.0)


class RailButton(Component):
    kind = "railbutton"

    def __init__(self, tag):
        Component.__init__(self, tag)
        self.outer_diameter = _float(tag, "outerdiameter", 0.0097)
        self.inner_diameter = _float(tag, "innerdiameter", 0.008)
        self.total_height = _float(tag, "height", 0.0097)
        self.base_height = _float(tag, "baseheight", 0.002)
        self.flange_height = _float(tag, "flangeheight", 0.002)
        self.instance_count = int(_float(tag, "instancecount", 1))
        self.instance_separation = _float(tag, "instanceseparation", 0.0)
        self.length = 0.0


class TubeFinSet(Component):
    kind = "tubefinset"

    def __init__(self, tag):
        Component.__init__(self, tag)
        self.fin_count = int(_float(tag, "fincount", _float(tag, "instancecount", 1)))
        self.instance_count = self.fin_count
        self.length = _float(tag, "length", 0.0)
        self.thickness = _float(tag, "thickness", 0.0)
        self.radius_spec = _radius_spec(tag, "radius")
        self.outer_radius = None  # resolved against the parent body radius


SYMMETRIC_KINDS = ("nosecone", "bodytube", "transition")
FIN_KINDS = ("trapezoidfinset", "freeformfinset", "ellipticalfinset")


class Rocket:
    """The drag-relevant model of one .ork design."""

    def __init__(self, soup):
        rocket_tag = soup.find("rocket")
        self.name = _text(rocket_tag, "name", "")
        self.reference_type = _text(rocket_tag, "referencetype", "maximum")
        # OpenRocket serializes the custom length as <customreference>
        self.custom_ref_length = _float(
            rocket_tag,
            "customreference",
            _float(rocket_tag, "customreferencelength", None),
        )
        self.perfect_finish = False  # not serialized; OR default
        self.stages = []  # list of lists of SymmetricComp (document order)
        self.stage_overrides = []  # per stage: (cd_override, subcomponents flag)
        self.symmetric = []  # flattened, in order
        self.others = []  # fins, lugs, rail buttons, tube fins

        subcomponents = rocket_tag.find("subcomponents", recursive=False)
        stage_tags = subcomponents.find_all("stage", recursive=False)
        x_cursor = 0.0
        for stage_index, stage_tag in enumerate(stage_tags):
            stage_comps = []
            self.stage_overrides.append(
                (
                    _float(stage_tag, "overridecd", None),
                    _text(stage_tag, "overridesubcomponentscd", "false") == "true",
                )
            )
            stage_sub = stage_tag.find("subcomponents", recursive=False)
            children = [] if stage_sub is None else stage_sub.find_all(recursive=False)
            for child in children:
                if child.name not in SYMMETRIC_KINDS:
                    continue
                comp = SymmetricComp(child, child.name)
                comp.stage = stage_index
                method, offset = _axial_offset(child)
                if method == "absolute":
                    comp.abs_x = offset
                else:
                    # stage children stack sequentially ("after" the previous
                    # sibling), possibly with an explicit gap/overlap offset
                    comp.abs_x = x_cursor + (offset if method == "after" else 0.0)
                x_cursor = comp.abs_x + comp.length
                stage_comps.append(comp)
                self.symmetric.append(comp)
                self._parse_children(child, comp, stage_index)
            self.stages.append(stage_comps)
        self._resolve_radii()
        for other in self.others:
            if isinstance(other, TubeFinSet):
                self._resolve_tube_fin_radius(other)

    # -- parsing helpers ---------------------------------------------------

    def _parse_children(self, parent_tag, parent_comp, stage_index):
        sub = parent_tag.find("subcomponents", recursive=False)
        if sub is None:
            return
        for child in sub.find_all(recursive=False):
            if child.name in FIN_KINDS:
                comp = FinSet(child, child.name)
            elif child.name == "launchlug":
                comp = LaunchLug(child)
            elif child.name == "railbutton":
                comp = RailButton(child)
            elif child.name == "tubefinset":
                comp = TubeFinSet(child)
            else:
                continue
            comp.stage = stage_index
            comp.parent = parent_comp
            method, offset = _axial_offset(child)
            if method == "absolute":
                comp.abs_x = offset  # rocket-frame position
                comp.rel_x = comp.abs_x - parent_comp.abs_x
            else:
                comp.rel_x = _relative_position(
                    method, offset, comp.length, parent_comp.length
                )
                comp.abs_x = parent_comp.abs_x + comp.rel_x
            self.others.append(comp)

    def _resolve_radii(self):
        """Resolve ``auto`` radii using cached values or neighbor radii."""
        comps = self.symmetric
        for i, comp in enumerate(comps):
            comp.fore_radius = _resolve_radius(
                comp.fore_spec, comps, i, prefer_previous=True
            )
            comp.aft_radius = _resolve_radius(
                comp.aft_spec, comps, i, prefer_previous=False
            )
            if comp.kind == "bodytube":
                comp.aft_radius = comp.fore_radius

    def _resolve_tube_fin_radius(self, tube_fin):
        value, auto = tube_fin.radius_spec
        body_radius = tube_fin.parent.fore_radius
        if not auto:
            tube_fin.outer_radius = value
            return
        import math

        n = tube_fin.fin_count
        if n < 3:
            tube_fin.outer_radius = body_radius
        else:
            s = math.sin(math.pi / n)
            tube_fin.outer_radius = body_radius * s / (1 - s)

    # -- derived quantities ------------------------------------------------

    def active_symmetric(self, active_stages=None):
        return [
            c
            for c in self.symmetric
            if active_stages is None or c.stage in active_stages
        ]

    def active_others(self, active_stages=None):
        return [
            c for c in self.others if active_stages is None or c.stage in active_stages
        ]

    def length_aerodynamic(self, active_stages=None):
        """X-span of the bounding box of the active aerodynamic components."""
        lo, hi = None, None
        for comp in self.active_symmetric(active_stages) + self.active_others(
            active_stages
        ):
            x0 = comp.abs_x
            x1 = comp.abs_x + comp.length
            if isinstance(comp, FinSet):
                ext_lo, ext_hi = comp.x_extent()
                x0 = comp.abs_x + min(ext_lo, 0.0)
                x1 = comp.abs_x + ext_hi
            separation = getattr(comp, "instance_separation", 0.0)
            if comp.instance_count > 1 and separation:
                # line-instanced components (rail buttons, launch lugs)
                span = (comp.instance_count - 1) * separation
                x0 += min(0.0, span)
                x1 += max(0.0, span)
            lo = x0 if lo is None else min(lo, x0)
            hi = x1 if hi is None else max(hi, x1)
        if lo is None:
            return 0.0
        return hi - lo

    def reference_length(self, active_stages=None):
        """``ReferenceType`` policy: nosecone / maximum / custom."""
        comps = self.active_symmetric(active_stages)
        if self.reference_type == "custom" and self.custom_ref_length:
            return self.custom_ref_length
        if self.reference_type == "nosecone":
            for comp in comps:
                for r in (comp.fore_radius, comp.aft_radius):
                    if r >= 0.0005:
                        return 2 * r
            return DEFAULT_REFERENCE_LENGTH
        ref = 0.0
        for comp in comps:
            ref = max(ref, comp.fore_radius, comp.aft_radius)
        ref *= 2
        if ref < 0.001:
            ref = DEFAULT_REFERENCE_LENGTH
        return ref


def _axial_offset(tag):
    """The (method, offset) pair of a component's axial position element."""
    offset_tag = tag.find("axialoffset", recursive=False)
    if offset_tag is not None:
        return offset_tag.get("method", "top"), float(offset_tag.text)
    pos_tag = tag.find("position", recursive=False)
    if pos_tag is None:
        return "top", 0.0
    return pos_tag.get("type", "top"), float(pos_tag.text)


def _relative_position(method, offset, inner_length, outer_length):
    """Child fore-end x relative to the parent fore end (``AxialMethod``)."""
    if method == "top":
        return offset
    if method == "middle":
        return offset + (outer_length - inner_length) / 2
    if method == "bottom":
        return offset + (outer_length - inner_length)
    if method == "after":
        return outer_length + offset
    logger.warning("unsupported axial method %r, treating as 'top'", method)
    return offset


def _radius_spec(tag, name):
    """Parse a radius element that may be ``auto``/``auto <value>``."""
    child = tag.find(name, recursive=False)
    if child is None:
        return (None, True)
    text = child.get_text().strip().lower()
    if text.startswith("auto"):
        rest = text[4:].strip()
        return (float(rest) if rest else None, True)
    return (float(text), False)


def _resolve_radius(spec, comps, index, prefer_previous):
    if isinstance(spec, tuple):
        value, auto = spec
    else:  # nose cone fore radius: plain 0.0
        return spec
    if not auto:
        return value
    # automatic radius: OpenRocket re-resolves it from the neighbor at load
    # time, so an EXPLICIT neighbor radius beats the cached "auto <value>"
    # (old OpenRocket versions cached stale defaults); the cached value is
    # the fallback when the neighbor is itself automatic or absent
    order = [index - 1, index + 1] if prefer_previous else [index + 1, index - 1]
    neighbor_cached = None
    for j in order:
        if 0 <= j < len(comps):
            neighbor = comps[j]
            r = neighbor.aft_spec if j < index else neighbor.fore_spec
            if isinstance(r, tuple):
                if not r[1] and r[0] is not None:
                    return r[0]  # explicit neighbor radius
                if neighbor_cached is None and r[0] is not None:
                    neighbor_cached = r[0]
            elif r is not None:
                return r
    if value is not None:
        return value  # cached "auto <value>" written by OpenRocket at save time
    if neighbor_cached is not None:
        return neighbor_cached
    return DEFAULT_RADIUS


def _text(tag, name, default=None):
    child = tag.find(name, recursive=False)
    if child is None:
        return default
    return child.get_text().strip()


def _float(tag, name, default=None):
    text = _text(tag, name, None)
    if text is None:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _float_or_none(tag, name):
    return _float(tag, name, None)


def read_ork_xml(path):
    """Read an .ork file (zip container or plain XML) into BeautifulSoup."""
    path = Path(path)
    try:
        with zipfile.ZipFile(path) as archive:
            inner = next(
                (n for n in archive.namelist() if n.endswith(".ork")),
                archive.namelist()[0],
            )
            data = archive.read(inner)
    except zipfile.BadZipFile:
        data = path.read_bytes()
    return BeautifulSoup(data, features="xml")


def load_rocket(path):
    """Load a .ork design file into a :class:`Rocket` model."""
    return Rocket(read_ork_xml(path))
