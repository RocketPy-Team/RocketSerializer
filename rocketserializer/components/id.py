import logging
from pathlib import Path

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
    rocket_tag = bs.find("rocket")
    if rocket_tag:
        settings["rocket_name"] = getattr(rocket_tag.find("name"), "text", "")
        logger.info("Collected the rocket name: '%s'", settings["rocket_name"])

        comment_tag = rocket_tag.find("comment")
        if comment_tag and comment_tag.text:
            settings["comment"] = comment_tag.text.replace("\n", "")
            logger.info(
                "Collected the comment saved in the file: %s", settings["comment"]
            )
        else:
            logger.warning("No auxiliary comment was found in the file.")
            settings["comment"] = None

        designer_tag = rocket_tag.find("designer")
        if designer_tag and designer_tag.text:
            settings["designer"] = designer_tag.text
            logger.info("Collected the designer name: %s", settings["designer"])
        else:
            logger.warning("No designer name was found in the file.")
            settings["designer"] = None
    else:
        settings["rocket_name"] = ""
        settings["comment"] = None
        settings["designer"] = None
    # settings["ork_version"] = bs.attrs["creator"]
    settings["filepath"] = Path(filepath).as_posix()

    logger.info(
        "Identification information extracted.\n %s",
        _dict_to_string(settings, indent=23),
    )
    return settings
