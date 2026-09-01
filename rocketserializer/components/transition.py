import logging

from .._helpers import _dict_to_string

logger = logging.getLogger(__name__)


def _find_transitions_recursive(component):
    """Recursively find all Transition components in the OpenRocket model."""
    results = []
    if component.getClass().getSimpleName() == "Transition":
        results.append(component)
    for i in range(component.getChildCount()):
        child = component.getChild(i)
        results.extend(_find_transitions_recursive(child))
    return results


def _parse_radius(text, resolved=None):
    """Parse a radius that may be ``auto`` or ``auto <cached value>``.

    OpenRocket re-resolves automatic radii at load time, so when a resolved
    value (from the neighboring components) is available it wins; the value
    cached after the ``auto`` keyword is used otherwise, and a bare ``auto``
    (written by old OpenRocket versions) falls back to the resolved value or
    0.0.
    """
    text = (text or "0").strip().lower()
    if text.startswith("auto"):
        if resolved is not None:
            return resolved
        rest = text[4:].strip()
        return float(rest) if rest else 0.0
    return float(text)


def _resolved_transition_radii(bs):
    """Neighbor-resolved (fore, aft) radii per transition, in document order.

    Uses the drag model's symmetric-component parser, which resolves
    ``auto`` radii the way OpenRocket does (from the adjacent components).
    Returns None when the design cannot be parsed.
    """
    try:
        # pylint: disable=import-outside-toplevel
        from ..dragmodel.components import Rocket as _DragRocket

        parsed = _DragRocket(bs)
        return [
            (c.fore_radius, c.aft_radius)
            for c in parsed.symmetric
            if c.kind == "transition"
        ]
    except Exception:  # pylint: disable=broad-except
        logger.warning("could not resolve transition radii from neighbors")
        return None


def search_transitions(bs, elements, ork):
    """Search for the transitions in the bs and return the settings as a dict.

    Parameters
    ----------
    bs : bs4.BeautifulSoup
        The BeautifulSoup object of the .ork file.
    elements : dict
        Dictionary with the elements of the rocket.
    ork : orhelper
        orhelper object of the open rocket file.

    Returns
    -------
    settings : dict
        Dictionary with the settings for the transitions. The keys are integers
        and the values are dicts containing the settings for each transition.
        The keys of the transition dicts are: "name", "top_radius",
        "bottom_radius", "length", "position".
    """
    settings = {}
    transitions = bs.find_all("transition")
    logger.info("A total of %d transitions were found", len(transitions))

    # Recursively search for Transition components in the Java model
    # (JVM-free mode passes ork=None and relies on the XML radii below)
    transitions_ork = _find_transitions_recursive(ork.getRocket()) if ork else []

    if len(transitions_ork) != len(transitions):
        logger.warning(
            "Mismatch between BS4 transitions (%d) and Java transitions (%d). "
            "Will match by name.",
            len(transitions),
            len(transitions_ork),
        )

    resolved_radii = None
    for idx, transition in enumerate(transitions):
        logger.info("Starting to collect the settings of the transition number %d", idx)

        label = getattr(transition.find("name"), "text", "")
        logger.info("Collected the name of the transition number %d", idx)

        # Try to find matching Java transition by name or index
        transition_ork = None
        for t_ork in transitions_ork:
            if str(t_ork.getName()) == label:
                transition_ork = t_ork
                break
        if transition_ork is None and idx < len(transitions_ork):
            transition_ork = transitions_ork[idx]

        if transition_ork is not None:
            top_radius = float(transition_ork.getForeRadius())
            bottom_radius = float(transition_ork.getAftRadius())
        else:
            logger.warning(
                "Could not find Java transition for '%s', using radii from XML.",
                label,
            )
            if resolved_radii is None:
                resolved_radii = _resolved_transition_radii(bs) or []
            resolved = (
                resolved_radii[idx] if idx < len(resolved_radii) else (None, None)
            )
            fore_tag = transition.find("foreradius")
            fore_text = fore_tag.text if fore_tag else "0"
            top_radius = _parse_radius(fore_text, resolved[0])

            aft_tag = transition.find("aftradius")
            aft_text = aft_tag.text if aft_tag else "0"
            bottom_radius = _parse_radius(aft_text, resolved[1])

        length = float(getattr(transition.find("length"), "text", "0"))
        logger.info("Collected the dimensions of the transition number %d", idx)

        def get_position(name, length):
            count = 0
            lower_name = name.lower()
            position = None
            for element in elements.values():
                if (
                    element["name"].lower() == lower_name
                    and element["length"] == length
                ):
                    count += 1
                    position = element["position"]
            if count > 1:
                logger.warning(
                    "Multiple transitions with the same name and length, "
                    "using the last one found."
                )
            elif count == 0:
                logger.error(
                    "No element with the name %s and length %f was found",
                    name,
                    length,
                )
            return position

        transition_setting = {
            "name": label,
            "top_radius": top_radius,
            "bottom_radius": bottom_radius,
            "length": length,
            "position": get_position(label, length),
        }
        settings[idx] = transition_setting
        logger.info(
            "The transition number %d was defined with the following settings:\n%s",
            idx,
            _dict_to_string(transition_setting, indent=23),
        )

    logger.info("All the %d transition settings were defined", len(transitions))
    return settings
