import yaml


def search_id_info(bs, filepath, verbose=False):
    """Searches for the identification of the .ork file

    Parameters
    ----------
    bs : BeautifulSoup
        BeautifulSoup object of the .ork file.
    filepath : str
        Path to the .ork file.
    verbose : bool, optional
        Whether or not to print a message of successful execution, by default
        False.

    Returns
    -------
    dictionary
        Dictionary with the identification information of the .ork file. The
        keys are: "rocket_name", "comment", "designer", "ork_version" and
        "filepath".
    """
    settings = {}
    settings["rocket_name"] = bs.find("rocket").find("name").text
    try:
        settings["comment"] = bs.find("rocket").find("comment").text
    except AttributeError:
        settings["comment"] = None
    try:
        settings["designer"] = bs.find("rocket").find("designer").text
    except AttributeError:
        settings["designer"] = None
    # settings["ork_version"] = bs.attrs["creator"]
    settings["filepath"] = filepath

    if verbose:
        print(
            "[Identification] Identification information extracted."
            + f"\n{yaml.dump(settings, default_flow_style=False)}"
        )

    return settings
