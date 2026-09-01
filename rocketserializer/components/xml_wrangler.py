"""JVM-free replacement for ``process_elements_position``.

Reproduces the exact ``elements`` dict the JVM wrangler builds -- same Java
simple-class-name ``type`` strings, same ``name``/``length`` values and the
same (quirky) position accumulation:

- a STAGE child's position = the running top position (which accumulates the
  lengths of ALL previous siblings, including skipped parachutes and mass
  components) + any explicit stacking gap — that is OpenRocket's sequential
  nose/tube/tail stack;
- an INTERNAL child (fins, rings, rail buttons, ... inside a body tube) is
  positioned INDEPENDENTLY by its own axial offset within its parent —
  sibling lengths must NOT accumulate (the JVM wrangler got this wrong and
  shifted e.g. a fin set aft by every inner tube/mass component declared
  before it; M059's fins landed 0.55 m past the rocket's tail);
- a Stage's position is its incoming top position + its own length;
- Parachute and MassComponent subtrees are skipped entirely (but their
  lengths still advance the running top position at stage level).
"""

import logging

logger = logging.getLogger(__name__)

JAVA_TYPES = {
    "rocket": "Rocket",
    "stage": "AxialStage",
    "nosecone": "NoseCone",
    "bodytube": "BodyTube",
    "transition": "Transition",
    "trapezoidfinset": "TrapezoidFinSet",
    "freeformfinset": "FreeformFinSet",
    "ellipticalfinset": "EllipticalFinSet",
    "tubefinset": "TubeFinSet",
    "launchlug": "LaunchLug",
    "railbutton": "RailButton",
    "innertube": "InnerTube",
    "tubecoupler": "TubeCoupler",
    "centeringring": "CenteringRing",
    "bulkhead": "Bulkhead",
    "engineblock": "EngineBlock",
    "shockcord": "ShockCord",
    "streamer": "Streamer",
    "parachute": "Parachute",
    "masscomponent": "MassComponent",
}

#: subtrees the JVM wrangler skips entirely
_SKIPPED = ("parachute", "masscomponent")


def _text(tag, name, default=None):
    child = tag.find(name, recursive=False)
    # NOTE: no strip -- Java keeps component names verbatim (some real files
    # have trailing spaces in <name>, and downstream matching is name-based)
    return child.get_text() if child else default


def _float(tag, name, default=0.0):
    text = _text(tag, name, None)
    if text is None:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _component_length(tag):
    """``RocketComponent.getLength()`` from the XML."""
    kind = tag.name
    if kind in ("trapezoidfinset", "ellipticalfinset"):
        return _float(tag, "rootchord", 0.0)
    if kind == "freeformfinset":
        points_tag = tag.find("finpoints")
        points = points_tag.find_all("point") if points_tag else []
        if len(points) >= 2:
            return float(points[-1]["x"]) - float(points[0]["x"])
        return 0.0
    if kind == "railbutton":
        return 0.0
    if kind in ("parachute", "masscomponent", "shockcord", "streamer"):
        return _float(tag, "packedlength", 0.0)
    return _float(tag, "length", 0.0)


def _axial_offset(tag):
    offset_tag = tag.find("axialoffset", recursive=False)
    if offset_tag is not None:
        return offset_tag.get("method", "top"), float(offset_tag.text)
    pos_tag = tag.find("position", recursive=False)
    if pos_tag is None:
        return "top", 0.0
    return pos_tag.get("type", "top"), float(pos_tag.text)


def _position_in_parent(tag, own_length, parent_length, parent_abs):
    """Resolved axial position of a child within its parent's frame."""
    method, offset = _axial_offset(tag)
    if method == "top":
        return offset
    if method == "middle":
        return offset + (parent_length - own_length) / 2
    if method == "bottom":
        return offset + (parent_length - own_length)
    if method == "absolute":
        return offset - parent_abs
    if method == "after":
        return parent_length + offset
    return offset


def _children_of(tag):
    sub = tag.find("subcomponents", recursive=False)
    if sub is None:
        return []
    return [c for c in sub.find_all(recursive=False) if c.name in JAVA_TYPES]


def process_elements_position_xml(soup):
    """Build the ``elements`` dict from the XML alone (no JVM)."""
    rocket_tag = soup.find("rocket")
    elements = {}

    def add(kind, name, length, position):
        element = {
            "type": JAVA_TYPES[kind],
            "name": name,
            "length": length,
            "position": position,
        }
        key = hash(frozenset(element.items()))
        elements[key] = element

    def walk(tag, parent_top, parent_length, parent_abs):
        """Internal (non-stage-level) components: element + recursion.

        Each is positioned independently inside its parent by its own axial
        offset — no sibling accumulation. Children then position relative to
        THIS component's resolved top."""
        if tag.name in _SKIPPED:
            return
        length = _component_length(tag)
        rel = _position_in_parent(tag, length, parent_length, parent_abs)
        own_top = parent_top + rel
        add(tag.name, _text(tag, "name", ""), length, own_top)
        own_abs = parent_abs + rel
        for child in _children_of(tag):
            walk(child, own_top, length, own_abs)

    add("rocket", _text(rocket_tag, "name", ""), _rocket_length(rocket_tag), 0.0)
    top = 0.0
    for stage_tag in _children_of(rocket_tag):
        if stage_tag.name != "stage":
            continue
        stage_length = _stage_length(stage_tag)
        add("stage", _text(stage_tag, "name", ""), stage_length, top + stage_length)
        cursor_abs = top  # true absolute position of the stacking cursor
        child_top = top  # the wrangler's running top position
        for child in _children_of(stage_tag):
            length = _component_length(child)
            method, offset = _axial_offset(child)
            if method == "absolute":
                child_abs = offset
            else:
                child_abs = cursor_abs + (offset if method == "after" else 0.0)
            # stage children: the wrangler's position equals its running top
            # (plus any explicit stacking gap)
            position = child_top + (child_abs - cursor_abs)
            add(child.name, _text(child, "name", ""), length, position)
            for grandchild in _children_of(child):
                walk(grandchild, position, length, child_abs)
            cursor_abs = child_abs + length
            child_top += length
        top += stage_length
    return elements


def _stage_length(stage_tag):
    cursor = 0.0
    for child in _children_of(stage_tag):
        method, offset = _axial_offset(child)
        length = _component_length(child)
        if method == "absolute":
            cursor = offset + length
        else:
            cursor += (offset if method == "after" else 0.0) + length
    return cursor


def _rocket_length(rocket_tag):
    return sum(_stage_length(s) for s in _children_of(rocket_tag) if s.name == "stage")
