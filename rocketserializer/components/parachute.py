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

    chutes = bs.findAll("parachute")
    logger.info("A total of %d parachutes were detected", len(chutes))

    for idx, chute in enumerate(chutes):
        logger.info("Starting to collect the settings of the parachute number %d", idx)
        name = chute.find("name").text

        # parachute settings
        cd = "auto" if "auto" in chute.find("cd").text else float(chute.find("cd").text)
        cd = search_cd_chute_if_auto(chute) if cd == "auto" else cd
        area = np.pi * float(chute.find("diameter").text) ** 2 / 4
        cds = cd * area
        logger.info("Parachute '%s' has a drag coefficient of %f", name, cd)

        # deployment settings
        deploy_event = chute.find("deployevent").text
        deploy_delay = float(chute.find("deploydelay").text)
        deploy_altitude = (
            float(chute.find("deployaltitude").text)
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
    # if the parachute cd is st to "auto", then look for the cd in the next tag
    # return float(
    #     next(
    #         filter(lambda x: x.text.replace(".", "").isnumeric(), bs.findAll("cd"))
    #     ).text
    # )

    # TODO: for the future, we need to check if the ork object has a drag coefficient

    # simply return 1.0
    logger.warning(
        "cd auto: the cd is set to 1.0 for parachute %s", bs.find("name").text
    )
    return 1.0
