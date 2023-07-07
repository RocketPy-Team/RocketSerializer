import yaml


def search_transitions(bs, elements, ork, rocket_radius, verbose=False):
    """Search for the transitions in the bs and return the settings as a dict.

    Parameters
    ----------
    bs : bs4.BeautifulSoup
        The BeautifulSoup object of the .ork file.
    elements : dict
        Dictionary with the elements of the rocket.
    ork : orhelper
        orhelper object of the open rocket file.
    rocket_radius : float
        The radius of the rocket.

    Returns
    -------
    settings : dict
        Dictionary with the settings for the transitions. The keys are integers
        and the values are dicts containing the settings for each transition.
        The keys of the transition dicts are: "name", "top_radius",
        "bottom_radius", "length", "distance_to_cm".
    """
    settings = {}
    transitions = bs.findAll("transition")
    top_radius = rocket_radius  # TODO: this is not so good, but it works for now
    if verbose:
        print(f"[Transitions] {len(transitions)} transitions were found")

    for idx, transition in enumerate(transitions):
        label = transition.find("name").text
        transition_ork = [ele for ele in ork.getRocket().getChild(0).getChildren()][-1]
        top_radius = float(transition_ork.getForeRadius())
        bottom_radius = (
            transition.find("aftradius").text
            if "auto" in transition.find("aftradius").text
            else float(transition.find("aftradius").text)
        )
        length = float(transition.find("length").text)

        transition_setting = {
            f"name": label,
            f"top_radius": top_radius,
            f"bottom_radius": bottom_radius,
            f"length": length,
            f"distance_to_cm": elements[label]["distance_to_cm"],
        }
        settings[idx] = transition_setting

        if verbose:
            print(
                f"[Transitions][{idx}] setting defined: \n{yaml.dump(transition_setting, default_flow_style=False)}"
            )
    return settings
