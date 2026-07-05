import logging

import numpy as np

from .._helpers import _dict_to_string

logger = logging.getLogger(__name__)


def search_parachutes(bs):
    """Search for the parachutes in the bs and return the settings as a dict.

    Parameters
    ----------
    bs : bs4.BeautifulSoup
        The BeautifulSoup object of the .ork file.

    Returns
    -------
    settings : dict
        A dict containing the settings for the parachutes. The keys are integers
        and the values are dicts containing the settings for each parachute.
        The keys of the parachute dicts are: "name", "cd", "cds", "area",
        "deploy_event", "deploy_delay", "deploy_altitude".
    """
    settings = {}

    chutes = bs.find_all("parachute")
    logger.info("A total of %d parachutes were detected", len(chutes))

    for idx, chute in enumerate(chutes):
        logger.info("Starting to collect the settings of the parachute number %d", idx)
        name = getattr(chute.find("name"), "text", "")

        # parachute settings
        cd = (
            "auto"
            if "auto" in getattr(chute.find("cd"), "text", "")
            else float(getattr(chute.find("cd"), "text", "0"))
        )
        cd = search_cd_chute_if_auto(chute) if cd == "auto" else cd
        area = np.pi * float(getattr(chute.find("diameter"), "text", "0")) ** 2 / 4
        cds = cd * area
        logger.info("Parachute '%s' has a drag coefficient of %f", name, cd)

        # deployment settings
        deploy_event = getattr(chute.find("deployevent"), "text", "")
        deploy_delay = float(getattr(chute.find("deploydelay"), "text", "0"))
        deploy_altitude = (
            float(getattr(chute.find("deployaltitude"), "text", "0"))
            if deploy_event == "altitude"
            else None
        )
        logger.info("Parachute '%s' will deploy at %s", name, deploy_event)

        setting = {
            "name": name,
            "cd": cd,
            "cds": cds,
            "area": area,
            "deploy_event": deploy_event,
            "deploy_delay": deploy_delay,
            "deploy_altitude": deploy_altitude,
        }
        settings[idx] = setting

        logger.info(
            "The Parachute number %d had its settings defined:\n%s",
            idx,
            _dict_to_string(setting, indent=23),
        )
    logger.info("All parachutes settings were collected")
    return settings


def search_cd_chute_if_auto(bs):
    # if the parachute cd is set to "auto", OpenRocket defaults to 0.75 (flat)
    # or 1.5 (dome). Since we cannot easily deduce the type, 0.75 is the
    # most common standard parachute CD in OR.
    logger.warning(
        "cd auto: the cd is set to 0.75 for parachute %s",
        getattr(bs.find("name"), "text", "Unknown"),
    )
    return 0.75
