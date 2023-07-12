import yaml


def search_launch_conditions(bs, verbose=False):
    """Searches the launch conditions in the bs object. Returns a dict with the
    settings.

    Parameters
    ----------
    bs : BeautifulSoup
        The BeautifulSoup object of the open rocket file.
    verbose : bool, optional
        Whether or not to print a message of successful execution, by default
        False.

    Returns
    -------
    settings : dict
        A dict containing the settings for the launch conditions.
    """
    settings = {}

    launch_rod_length = float(bs.find("launchrodlength").text)
    launch_rod_angle = float(bs.find("launchrodangle").text)
    launch_rod_direction = float(bs.find("launchroddirection").text)

    settings = {
        "rail_length": launch_rod_length,
        "inclination": 90 - launch_rod_angle,
        "heading": launch_rod_direction,
    }
    if verbose:
        print(
            f"[Launch Conditions] Launch settings were extracted: \n{yaml.dump(settings, default_flow_style=False)}"
        )
    return settings
