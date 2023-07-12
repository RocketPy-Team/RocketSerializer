import yaml


def search_trapezoidal_fins(bs, elements, verbose=False):
    """Search for trapezoidal fins in the bs and return the settings as a dict.
    It is flexible in the sense that it can handle multiple trapezoidal fin sets.

    Parameters
    ----------
    bs : BeautifulSoup
        The BeautifulSoup object of the open rocket file.
    elements : dict
        Dictionary with the settings for the elements of the rocket.
    verbose : bool, optional
        Whether or not to print a message of successful execution, by default
        False.

    Returns
    -------
    settings : dict
        Dictionary with the settings for the trapezoidal fins. The keys are
        integers and the values are dicts containing the settings for each
        trapezoidal fin set. The keys of the trapezoidal fin set dicts are:
        "name", "number", "root_chord", "tip_chord", "span", "distance_to_cm",
        "sweep_length", "sweep_angle", "cant_angle", "section".
    """
    settings = {}
    fins = bs.findAll("trapezoidfinset")
    if verbose:
        print(f"[Trapezoidal Fins] - {len(fins)} trapezoidal fin set detected")

    if len(fins) == 0:
        return settings

    for idx, fin in enumerate(fins):
        label = fin.find("name").text
        try:
            element = elements[label]
        except KeyError:
            raise KeyError(
                f"[Trapezoidal Fins][{idx}] Couldn't find the element '{label}' "
                + "in the elements dictionary. It is possible that the "
                + "process_elements_position() function got an error."
            )

        n_fin = int(fin.find("fincount").text)
        root_chord = float(fin.find("rootchord").text)
        tip_chord = float(fin.find("tipchord").text)
        span = float(fin.find("height").text)
        sweep_length = (
            float(fin.find("sweeplength").text) if fin.find("sweeplength") else None
        )
        sweep_angle = (
            float(fin.find("sweepangle").text) if fin.find("sweepangle") else None
        )
        fin_distance_to_cm = element["distance_to_cm"]
        cant_angle = float(fin.find("cant").text)
        section = fin.find("crosssection").text

        # save to a dictionary
        fin_settings = {
            f"name": label,
            f"number": n_fin,
            f"root_chord": root_chord,
            f"tip_chord": tip_chord,
            f"span": span,
            f"distance_to_cm": fin_distance_to_cm,
            f"sweep_length": sweep_length,
            f"sweep_angle": sweep_angle,
            f"cant_angle": cant_angle,
            f"section": section,
        }

        settings[idx] = fin_settings

        if verbose:
            print(
                f"[Trapezoidal Fins][{idx}] setting: \n{yaml.dump(fin_settings, default_flow_style=False)}"
            )
    if verbose:
        print(f"[Trapezoidal Fins] Finished searching for trapezoidal fins.")
    return settings
