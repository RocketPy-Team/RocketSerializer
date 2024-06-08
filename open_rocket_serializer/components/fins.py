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
    fins = bs.findAll("trapezoidfinset")
    logger.info(f"A total of {len(fins)} trapezoidal fin sets were detected")

    if len(fins) == 0:
        logger.info(
            f"Since no trapezoidal fins were detected, returning empty dictionary"
        )
        return settings

    for idx, fin in enumerate(fins):
        logger.info(
            "Starting collecting the settings for the trapezoidal fin set number "
            + f"'{idx}'"
        )
        label = fin.find("name").text
        try:

            def get_element_by_name(name):
                for element in elements.values():
                    if element["name"] == name:
                        return element
                return None

            element = get_element_by_name(label)
            logger.info(f"Found the element '{label}' in the elements dictionary.")
        except KeyError:
            message = (
                f"Couldn't find the element '{label}' in the elements dictionary."
                + "in the elements dictionary. It is possible that the "
                + "process_elements_position() function got an error."
            )
            logger.error(message)
            raise KeyError(message)

        n_fin = int(fin.find("fincount").text)
        logger.info(f"Number of fins retrieved: {n_fin}")

        root_chord = float(fin.find("rootchord").text)
        logger.info(f"Root chord retrieved: {root_chord}")

        tip_chord = float(fin.find("tipchord").text)
        logger.info(f"Tip chord retrieved: {tip_chord}")

        span = float(fin.find("height").text)
        logger.info(f"Span retrieved: {span}")

        sweep_length = (
            float(fin.find("sweeplength").text) if fin.find("sweeplength") else None
        )
        sweep_angle = (
            float(fin.find("sweepangle").text) if fin.find("sweepangle") else None
        )
        logger.info(f"Sweep angle and length retrieved: {sweep_length}")

        cant_angle = float(fin.find("cant").text)
        logger.info(f"Cant angle retrieved: {cant_angle}")

        section = fin.find("crosssection").text
        logger.info(f"Crosssection format retrieved")

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
            f"Trapezoidal fin set number '{idx}' was defined:\n"
            + _dict_to_string(fin_settings, indent=23)
        )
    logger.info(f"Finished collecting all the trapezoidal fins.")
    return settings


# TODO: what if the fins are not trapezoidal?
# freeformfinset and tubefinset
