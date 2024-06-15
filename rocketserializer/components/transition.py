import logging

from .._helpers import _dict_to_string

logger = logging.getLogger(__name__)


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
    transitions = bs.findAll("transition")
    logger.info("A total of %d transitions were found", len(transitions))

    transitions_ork = [
        ele
        for ele in ork.getRocket().getChild(0).getChildren()
        if ele.getClass().getSimpleName() == "Transition"
    ]  # TODO: only works for a single stage rocket.

    for idx, transition in enumerate(transitions):
        logger.info("Starting to collect the settings of the transition number %d", idx)

        label = transition.find("name").text
        logger.info("Collected the name of the transition number %d", idx)

        transition_ork = transitions_ork[idx]
        top_radius = float(transition_ork.getForeRadius())
        bottom_radius = (
            transition.find("aftradius").text
            if "auto" in transition.find("aftradius").text
            else float(transition.find("aftradius").text)
        )
        length = float(transition.find("length").text)
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
