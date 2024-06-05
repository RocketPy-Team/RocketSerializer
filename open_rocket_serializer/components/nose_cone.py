import logging

from .._helpers import _dict_to_string

logger = logging.getLogger(__name__)


def search_nosecone(bs, elements):
    """Search for the nosecone in the bs and return the settings as a dict.

    Parameters
    ----------
    bs : bs4.BeautifulSoup
        The BeautifulSoup object of the .ork file.
    elements : dict
        Dictionary with the elements of the rocket.

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
    base_radius = float(nosecone.find("aftradius").text)
    position = elements[name]["position"]

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
        "position": position,
    }
    logger.info("Nosecone setting defined:\n" + _dict_to_string(settings, indent=23))
    return settings
