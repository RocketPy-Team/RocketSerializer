import logging

from .._helpers import _dict_to_string

logger = logging.getLogger(__name__)


def search_nosecone(bs, elements, rocket_radius: float):
    """Search for the nosecone in the bs and return the settings as a dict.

    Parameters
    ----------
    bs : bs4.BeautifulSoup
        The BeautifulSoup object of the .ork file.
    elements : dict
        Dictionary with the elements of the rocket.
    rocket_radius : float
        The radius of the rocket.

    Returns
    -------
    settings : dict
        Dictionary with the settings for the nosecone.
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
            logger.info("Could not fetch a nosecone")
            return settings
        if len(nosecones) > 1:
            logger.info("Multiple nosecones found, using only the first one")
        nosecone = nosecones[0]  # only the first nosecone is considered

    length = float(nosecone.find("length").text)
    kind = nosecone.find("shape").text
    base_radius = nosecone.find("aftradius").text
    try:
        base_radius = float(base_radius)
    except ValueError:
        if "auto" in base_radius:
            # TODO: this is a temporary fix, we should look to the next component radius
            base_radius = rocket_radius

    def get_position(name, length):
        count = 0
        for element in elements.values():
            if element["name"] == name and element["length"] == length:
                count += 1
                position = element["position"]
        if count > 1:
            logger.warning(
                "Multiple nosecones with the same name and length, "
                "using the last one found."
            )
        return position

    logger.info(
        f"Collected the dimensions of the nosecone: length, shape and position."
    )

    if kind == "haack":
        logger.info("Nosecone is a haack nosecone, searching for the shape parameter")

        shape_parameter = float(nosecone.find("shapeparameter").text)
        kind = "Von Karman" if shape_parameter == 0.0 else "lvhaack"
        settings.update({"noseShapeParameter": shape_parameter})
        logger.info(f"Shape parameter of the nosecone: {shape_parameter}")

    settings = {
        "name": name,
        "kind": kind,
        "length": length,
        "base_radius": base_radius,
        "position": get_position(name, length),
    }
    logger.info("Nosecone setting defined:\n" + _dict_to_string(settings, indent=23))
    return settings
