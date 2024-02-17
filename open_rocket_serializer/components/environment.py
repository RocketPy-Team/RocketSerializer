import logging

import yaml

from .._helpers import _dict_to_string

logger = logging.getLogger(__name__)


def search_environment(bs):
    """Searches the launch conditions in the bs object. Returns a dict with the
    settings.

    Parameters
    ----------
    bs : BeautifulSoup
        BeautifulSoup object of the .ork file.

    Returns
    -------
    settings : dict
        A dict containing the settings for the launch conditions. The keys are:
        "latitude", "longitude", "elevation", "wind_average", "wind_turbulence",
        "geodetic_method", "base_temperature" and "base_pressure".
    """
    settings = {}

    latitude = float(bs.find("launchlatitude").text)
    longitude = float(bs.find("launchlongitude").text)
    elevation = float(bs.find("launchaltitude").text)
    wind_average = float(bs.find("windaverage").text)
    wind_turbulence = float(bs.find("windturbulence").text)
    geodetic_method = bs.find("geodeticmethod").text
    logger.info(
        "Collected first environment settings: latitude, "
        + "longitude, elevation, wind_average, wind_turbulence, geodetic_method"
    )
    try:
        base_temperature = float(bs.find("basetemperature").text)
        logger.info(
            "The base temperature was found in the .ork file. "
            + f"It is {base_temperature} °C."
        )
    except AttributeError:
        logger.warning(
            "No base temperature was found in the .ork file. "
            + "The base temperature will be set to None."
        )
        base_temperature = None
    try:
        base_pressure = float(bs.find("basepressure").text)
        logger.info(
            "The base pressure was found in the .ork file. "
            + f"It is {base_pressure} Pa."
        )
    except AttributeError:
        logger.warning(
            "No base pressure was found in the .ork file. "
            + "The base pressure will be set to None."
        )
        base_pressure = None
    date = None

    settings = {
        "latitude": latitude,
        "longitude": longitude,
        "elevation": elevation,
        "wind_average": wind_average,
        "wind_turbulence": wind_turbulence,
        "geodetic_method": geodetic_method,
        "base_temperature": base_temperature,
        "base_pressure": base_pressure,
        "date": date,
    }
    logger.info(
        "Successfully extracted all the environment settings.\n"
        + _dict_to_string(settings, indent=23)
    )
    return settings
