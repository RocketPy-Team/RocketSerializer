import yaml


def search_environment(bs, verbose=False):
    """Searches the launch conditions in the bs object. Returns a dict with the
    settings.

    Parameters
    ----------
    bs : BeautifulSoup
        BeautifulSoup object of the .ork file.
    verbose : bool, optional
        Whether or not to print a message of successful execution, by default
        False.

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
    try:
        base_temperature = float(bs.find("basetemperature").text)
    except AttributeError:
        base_temperature = None
    try:
        base_pressure = float(bs.find("basepressure").text)
    except AttributeError:
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
    if verbose:
        print(
            f"[Environment] The environment settings were extracted."
            + f" \n{yaml.dump(settings, default_flow_style=False)}"
        )
    return settings
