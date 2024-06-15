import logging
from pathlib import Path

from bs4 import BeautifulSoup

from .._helpers import _dict_to_string

logger = logging.getLogger(__name__)


def search_id_info(bs: BeautifulSoup, filepath: Path) -> dict:
    """Searches for the identification of the .ork file

    Returns
    -------
    dictionary
        Dictionary with the identification information of the .ork file.
    """
    settings = {}
    settings["rocket_name"] = bs.find("rocket").find("name").text
    logger.info("Collected the rocket name: '%s'", settings["rocket_name"])

    try:
        settings["comment"] = bs.find("rocket").find("comment").text.replace("\n", "")
        logger.info("Collected the comment saved in the file: %s", settings["comment"])
    except AttributeError:
        logger.warning("No auxiliary comment was found in the file.")
        settings["comment"] = None
    try:
        settings["designer"] = bs.find("rocket").find("designer").text
        logger.info("Collected the designer name: %s", settings["designer"])
    except AttributeError:
        logger.warning("No designer name was found in the file.")
        settings["designer"] = None
    # settings["ork_version"] = bs.attrs["creator"]
    settings["filepath"] = Path(filepath).as_posix()

    logger.info(
        "Identification information extracted.\n %s",
        _dict_to_string(settings, indent=23),
    )
    return settings
