import logging

import yaml

from .._helpers import _dict_to_string

logger = logging.getLogger(__name__)


def search_transitions(bs, elements, ork, rocket_radius):
    """Search for the transitions in the bs and return the settings as a dict.

    Parameters
    ----------
    bs : bs4.BeautifulSoup
        The BeautifulSoup object of the .ork file.
    elements : dict
        Dictionary with the elements of the rocket.
    ork : orhelper
        orhelper object of the open rocket file.
    rocket_radius : float
        The radius of the rocket.

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
    logger.info(f"A total of {len(transitions)} transitions were found")

    transitions_ork = [
        ele
        for ele in ork.getRocket().getChild(0).getChildren()
        if ele.getClass().getSimpleName() == "Transition"
    ]

    for idx, transition in enumerate(transitions):
        logger.info(f"Starting to collect the settings of the transition number {idx}")

        label = transition.find("name").text
        logger.info(f"Collected the name of the transition number {idx}")

        transition_ork = transitions_ork[idx]
        top_radius = float(transition_ork.getForeRadius())
        bottom_radius = (
            transition.find("aftradius").text
            if "auto" in transition.find("aftradius").text
            else float(transition.find("aftradius").text)
        )
        length = float(transition.find("length").text)
        logger.info(f"Collected the dimensions of the transition number {idx}")

        transition_setting = {
            "name": label,
            "top_radius": top_radius,
            "bottom_radius": bottom_radius,
            "length": length,
            "position": elements[label]["position"],
        }
        settings[idx] = transition_setting
        logger.info(
            f"The transition number {idx} was defined with the following settings:\n"
            + _dict_to_string(transition_setting, indent=23)
        )

    logger.info(f"All the {len(transitions)} transition settings were defined")
    return settings
