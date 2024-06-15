import logging

from bs4 import BeautifulSoup

from .._helpers import _dict_to_string

logger = logging.getLogger(__name__)


def search_launch_conditions(bs: BeautifulSoup) -> dict:
    """Searches the launch conditions in the bs object. Returns a dict with the
    settings.

    Returns
    -------
    settings : dict
        A dict containing the settings for the launch conditions.
    """
    settings = {}

    launch_rod_length = float(bs.find("launchrodlength").text)
    launch_rod_angle = float(bs.find("launchrodangle").text)
    launch_rod_direction = float(bs.find("launchroddirection").text)
    logger.info(
        "Collected launch conditions: launch rod length, launch rod angle, "
        "launch rod direction."
    )

    settings = {
        "rail_length": launch_rod_length,
        "inclination": 90 - launch_rod_angle,
        "heading": launch_rod_direction,
    }
    logger.info("Exported launch conditions.\n%s", _dict_to_string(settings, indent=23))
    return settings
