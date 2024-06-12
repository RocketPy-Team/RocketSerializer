import logging
from pathlib import Path

import yaml

from .._helpers import _dict_to_string

logger = logging.getLogger(__name__)


def search_id_info(bs, filepath):
    """Searches for the identification of the .ork file

    Parameters
    ----------
    bs : BeautifulSoup
        BeautifulSoup object of the .ork file.
    filepath : str
        Path to the .ork file.

    Returns
    -------
    dictionary
        Dictionary with the identification information of the .ork file. The
        keys are: "rocket_name", "comment", "designer", "ork_version" and
        "filepath".
    """
    settings = {}
    settings["rocket_name"] = bs.find("rocket").find("name").text
    logger.info(f"Collected the rocket name: '{settings['rocket_name']}'")

    try:
        settings["comment"] = bs.find("rocket").find("comment").text.replace("\n", "")
        logger.info(f"Collected the comment saved in the file: {settings['comment']}")
    except AttributeError:
        logger.warning("No auxiliary comment was found in the file.")
        settings["comment"] = None
    try:
        settings["designer"] = bs.find("rocket").find("designer").text
        logger.info(f"Collected the designer name: {settings['designer']}")
    except AttributeError:
        logger.warning("No designer name was found in the file.")
        settings["designer"] = None
    # settings["ork_version"] = bs.attrs["creator"]
    settings["filepath"] = Path(filepath).as_posix()

    logger.info(
        "Identification information extracted.\n" + _dict_to_string(settings, indent=23)
    )
    return settings
