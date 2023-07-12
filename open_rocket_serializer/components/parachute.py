import numpy as np
import yaml


def search_parachutes(bs, verbose=False):
    """Search for the parachutes in the bs and return the settings as a dict.

    Parameters
    ----------
    bs : bs4.BeautifulSoup
        The BeautifulSoup object of the .ork file.
    verbose : bool, optional
        Whether or not to print a message of successful execution, by default
        False.

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
    if verbose:
        print(f"[Parachutes] a total of {len(chutes)} detected")

    for idx, chute in enumerate(chutes):
        name = chute.find("name").text

        # parachute settings
        cd = "auto" if "auto" in chute.find("cd").text else float(chute.find("cd").text)
        area = np.pi * float(chute.find("diameter").text) ** 2 / 4
        cds = cd * area

        # deployment settings
        deploy_event = chute.find("deployevent").text
        deploy_delay = float(chute.find("deploydelay").text)
        deploy_altitude = (
            float(chute.find("deployaltitude").text)
            if deploy_event == "altitude"
            else None
        )

        setting = {
            f"name": name,
            f"cd": cd,
            f"cds": cds,
            f"area": area,
            f"deploy_event": deploy_event,
            f"deploy_delay": deploy_delay,
            f"deploy_altitude": deploy_altitude,
        }
        settings[idx] = setting

        if verbose:
            print(
                f"[Parachutes][{idx}] settings defined: \n{yaml.dump(setting, default_flow_style=False)}"
            )

    return settings


# def search_cd_chute_if_auto(bs):
#     return float(
#         next(
#             filter(lambda x: x.text.replace(".", "").isnumeric(), bs.findAll("cd"))
#         ).text
#     )
