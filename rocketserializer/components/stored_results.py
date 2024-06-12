import logging
import pickle

import yaml

from .._helpers import _dict_to_string

logger = logging.getLogger(__name__)


def search_stored_results(bs):
    """Search for the stored simulation results in the bs and return the
    settings as a dict.

    Parameters
    ----------
    bs : BeautifulSoup
        BeautifulSoup object of the .ork file.

    Returns
    -------
    settings : dict
        A dict containing the settings for the launch conditions. The keys are:
        "maxaltitude", "maxvelocity", "maxacceleration", "maxmach", "timetoapogee",
        "flighttime", "groundhitvelocity" and "launchrodvelocity".
    """
    settings = {}

    sim = bs.find("simulation")
    sim_data = sim.find("flightdata")
    logger.info("Found the 'flightdata' tag in the 'simulation' tag.")

    name_map = {
        "max_altitude": "maxaltitude",
        "max_velocity": "maxvelocity",
        "max_acceleration": "maxacceleration",
        "max_mach": "maxmach",
        "time_to_apogee": "timetoapogee",
        "flight_time": "flighttime",
        "ground_hit_velocity": "groundhitvelocity",
        "launch_rod_velocity": "launchrodvelocity",
    }

    for key, value in name_map.items():
        settings[key] = float(sim_data.get(value, 0))
        logger.info(f"Retrieved the '{key}' value from the .ork file: {settings[key]}")

    logger.info(
        "The flight data was successfully retrieved:\n%s",
        _dict_to_string(settings, indent=23),
    )
    return settings
