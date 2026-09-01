import logging

from .._helpers import _dict_to_string

logger = logging.getLogger(__name__)


def search_trapezoidal_fins(bs, elements):
    """Search for trapezoidal fins in the bs and return the settings as a dict.
    It is flexible in the sense that it can handle multiple trapezoidal fin sets.

    Parameters
    ----------
    bs : BeautifulSoup
        The BeautifulSoup object of the open rocket file.
    elements : dict
        Dictionary with the settings for the elements of the rocket.

    Returns
    -------
    settings : dict
        Dictionary with the settings for the trapezoidal fins. The keys are
        integers and the values are dicts containing the settings for each
        trapezoidal fin set. The keys of the trapezoidal fin set dicts are:
        "name", "number", "root_chord", "tip_chord", "span", "position",
        "sweep_length", "sweep_angle", "cant_angle", "section".
    """
    settings = {}
    fins = bs.find_all("trapezoidfinset")
    logger.info("A total of %d trapezoidal fin sets were detected", len(fins))

    if len(fins) == 0:
        logger.info("No trapezoidal fins were detected, returning empty dictionary")
        return settings

    for idx, fin in enumerate(fins):
        logger.info(
            "Starting collecting the settings for the trapezoidal fin set number '%d'",
            idx,
        )
        label = getattr(fin.find("name"), "text", "")
        try:

            def get_element_by_name(name):
                for element in elements.values():
                    if element["name"] == name:
                        return element
                return None

            element = get_element_by_name(label)
            logger.info("Found the element '%s' in the elements dictionary.", label)
        except KeyError:
            message = (
                f"Couldn't find the element '{label}' in the elements dictionary. It is"
                " possible that the process_elements_position() function got an error."
            )
            logger.error(message)
            raise KeyError(message)

        n_fin = int(getattr(fin.find("fincount"), "text", "0"))
        logger.info("Number of fins retrieved: %d", n_fin)

        root_chord = float(getattr(fin.find("rootchord"), "text", "0"))
        logger.info("Root chord retrieved: %f", root_chord)

        tip_chord = float(getattr(fin.find("tipchord"), "text", "0"))
        logger.info("Tip chord retrieved: %f", tip_chord)

        span = float(getattr(fin.find("height"), "text", "0"))
        logger.info("Span retrieved: %f", span)

        sweep_length = (
            float(getattr(fin.find("sweeplength"), "text", "0"))
            if fin.find("sweeplength")
            else None
        )
        sweep_angle = (
            float(getattr(fin.find("sweepangle"), "text", "0"))
            if fin.find("sweepangle")
            else None
        )
        logger.info(
            "Sweep length and angle retrieved: %s, %s", sweep_length, sweep_angle
        )

        cant_angle = float(getattr(fin.find("cant"), "text", "0"))
        logger.info("Cant angle retrieved: %f", cant_angle)

        section = getattr(fin.find("crosssection"), "text", "")
        logger.info("Crosssection format retrieved")

        fin_settings = {
            "name": label,
            "number": n_fin,
            "root_chord": root_chord,
            "tip_chord": tip_chord,
            "span": span,
            "position": element["position"],
            "sweep_length": sweep_length,
            "sweep_angle": sweep_angle,
            "cant_angle": cant_angle,
            "section": section,
        }

        settings[idx] = fin_settings

        logger.info(
            "Trapezoidal fin set number '%d' was defined:\n%s",
            idx,
            _dict_to_string(fin_settings, indent=23),
        )

    logger.info("Finished collecting all the trapezoidal fins.")
    return settings


def search_elliptical_fins(bs, elements):
    """Search for elliptical fins in the bs and return the settings as a dict.
    It is flexible in the sense that it can handle multiple elliptical fin sets.

    Parameters
    ----------
    bs : BeautifulSoup
        The BeautifulSoup object of the open rocket file.
    elements : dict
        Dictionary with the settings for the elements of the rocket.

    Returns
    -------
    settings : dict
        Dictionary with the settings for the elliptical fins. The keys are
        integers and the values are dicts containing the settings for each
        elliptical fin set. The keys of the elliptical fin set dicts are:
        "name", "number", "root_chord", "span", "position", "cant_angle",
        "section".
    """
    settings = {}
    fins = bs.find_all("ellipticalfinset")
    logger.info("A total of %d elliptical fin sets were detected", len(fins))

    if len(fins) == 0:
        logger.info(
            "Since no elliptical fins were detected, returning empty dictionary"
        )
        return settings

    for idx, fin in enumerate(fins):
        logger.info(
            "Starting collecting the settings for the elliptical fin set number '%d'",
            idx,
        )
        label = getattr(fin.find("name"), "text", "")
        try:

            def get_element_by_name(name):
                for element in elements.values():
                    if element["name"] == name:
                        return element
                return None

            element = get_element_by_name(label)
            logger.info("Found the element '%s' in the elements dictionary.", label)
        except KeyError:
            message = (
                f"Couldn't find the element '{label}' in the elements dictionary. It is"
                " possible that the process_elements_position() function got an error."
            )
            logger.error(message)
            raise KeyError(message)

        n_fin = int(getattr(fin.find("fincount"), "text", "0"))
        logger.info("Number of fins retrieved: %d", n_fin)

        root_chord = float(getattr(fin.find("rootchord"), "text", "0"))
        logger.info("Root chord retrieved: %f", root_chord)

        span = float(getattr(fin.find("height"), "text", "0"))
        logger.info("Span retrieved: %f", span)

        cant_angle = float(getattr(fin.find("cant"), "text", "0"))
        logger.info("Cant angle retrieved: %f", cant_angle)

        section = getattr(fin.find("crosssection"), "text", "")
        logger.info("Crosssection format retrieved")

        fin_settings = {
            "name": label,
            "number": n_fin,
            "root_chord": root_chord,
            "span": span,
            "position": element["position"],
            "cant_angle": cant_angle,
            "section": section,
        }

        settings[idx] = fin_settings

        logger.info(
            "Elliptical fin set number '%d' was defined:\n%s",
            idx,
            _dict_to_string(fin_settings, indent=23),
        )

    logger.info("Finished collecting all the elliptical fins.")
    return settings


def search_free_form_fins(bs, elements):
    """Search for freeform fins in the bs and return the settings as a dict.

    Parameters
    ----------
    bs : bs4.BeautifulSoup
        The BeautifulSoup object of the open rocket file.
    elements : dict
        Dictionary with the settings for the elements of the rocket.

    Returns
    -------
    settings : dict
        Dictionary with the settings for the freeform fins. The keys are
        integers and the values are dicts containing the settings for each
        freeform fin set. The keys of the freeform fin set dicts are: "name",
        "number", "shape_points", "position", "cant_angle", "section".

    Notes
    -----
    OpenRocket's ``<finpoints>`` use the same convention RocketPy's
    ``FreeFormFins`` expects: origin at the root-chord leading edge, x
    positive toward the tail, y positive away from the body.
    """
    settings = {}
    fins = bs.find_all("freeformfinset")
    logger.info("A total of %d freeform fin sets were detected", len(fins))

    for idx, fin in enumerate(fins):
        label = getattr(fin.find("name"), "text", "")

        element = None
        for candidate in elements.values():
            if candidate["name"] == label:
                element = candidate
                break
        if element is None:
            logger.error(
                "Couldn't find the element '%s' in the elements dictionary; "
                "the freeform fin set position will be missing.",
                label,
            )

        n_fin = int(getattr(fin.find("fincount"), "text", "0"))
        cant_angle = float(getattr(fin.find("cant"), "text", "0") or "0")
        section = getattr(fin.find("crosssection"), "text", "")

        finpoints = fin.find("finpoints")
        shape_points = [
            [float(point["x"]), float(point["y"])]
            for point in (finpoints.find_all("point") if finpoints else [])
        ]
        if len(shape_points) < 3:
            logger.error(
                "Freeform fin set '%s' has %d shape points (need at least 3); "
                "skipping it.",
                label,
                len(shape_points),
            )
            continue

        fin_settings = {
            "name": label,
            "number": n_fin,
            "shape_points": shape_points,
            "position": element["position"] if element else None,
            "cant_angle": cant_angle,
            "section": section,
        }
        settings[idx] = fin_settings
        logger.info(
            "Freeform fin set number '%d' was defined:\n%s",
            idx,
            _dict_to_string(fin_settings, indent=23),
        )

    logger.info("Finished collecting all the freeform fins.")
    return settings


# TODO: support for tubefinset (low priority)
