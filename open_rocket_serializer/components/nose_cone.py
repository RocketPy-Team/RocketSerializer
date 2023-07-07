import yaml


def search_nosecone(bs, elements, verbose=False):
    """Search for the nosecone in the bs and return the settings as a dict.

    Parameters
    ----------
    bs : bs4.BeautifulSoup
        The BeautifulSoup object of the .ork file.
    elements : dict
        Dictionary with the elements of the rocket.
    verbose : bool, optional
        Whether or not to print a message of successful execution, by default
        False.

    Returns
    -------
    settings : dict
        Dictionary with the settings for the nosecone. The keys are: "length",
        "kind", "distance_to_cm".
    """
    settings = {}
    nosecone = bs.find("nosecone")  # TODO: allow for multiple nosecones
    name = nosecone.find("name").text if nosecone else "nosecone"

    if not nosecone:
        nosecones = list(
            filter(
                lambda x: x.find("name").text == "Nosecone", bs.findAll("transition")
            )
        )
        if len(nosecones) == 0:
            if verbose:
                print("[Nosecone] Could not fetch the nosecone")
            return settings
        if len(nosecones) > 1:
            if verbose:
                print("[Nosecone] Multiple nosecones found, using only the first one")
        nosecone = nosecones[0]  # only the first nosecone is considered

    length = float(nosecone.find("length").text)
    kind = nosecone.find("shape").text
    distance_to_cm = elements[name]["distance_to_cm"]

    if kind == "haack":
        shape_parameter = float(nosecone.find("shapeparameter").text)
        kind = "Von Karman" if shape_parameter == 0.0 else "lvhaack"
        settings.update({"noseShapeParameter": shape_parameter})

    settings = {
        "length": length,
        "kind": kind,
        "distance_to_cm": distance_to_cm,
    }
    if verbose:
        print(
            f"[Nosecone] Nosecone setting defined: \n{yaml.dump(settings, default_flow_style=False)}"
        )
    return settings
