import logging

from .._helpers import _dict_to_string

logger = logging.getLogger(__name__)


def is_sub_component(ork):
    """Determines whether the given object `ork` is a sub-component of another
    object in a hierarchical structure.

    Parameters:
    -----------
    ork: net.sf.openrocket.rocketcomponent
        The object to be checked.

    Returns:
    --------
    bool
        True if `ork` is a sub-component (at least two levels below the root
        object), False otherwise.
    """
    i = 0
    root = ork.getRoot()
    while ork != root:
        ork = ork.getParent()
        if root != ork.getParent():
            i += 1
    return i > 1  # if i > 1, then ork is a sub-component


def calculate_distance_to_cg(ork, rocket_cg, top_position):
    if is_sub_component(ork) == True:
        try:
            element_position = ork.getRelativePosition().toString()
        except AttributeError:
            # "object has no attribute 'getRelativePosition'"
            element_position = "Top of the parent component"
        try:
            relative_position = top_position + ork.getPositionValue()
        except AttributeError:
            # "object has no attribute 'getPositionValue'"
            relative_position = top_position

        if element_position == "Bottom of the parent component":
            relative_position += ork.getParent().getLength()
        elif element_position == "Middle of the parent component":
            relative_position += ork.getParent().getLength() / 2
    else:
        relative_position = top_position + ork.getLength()

    if (rocket_cg - relative_position) < 0:
        relative_position -= ork.getLength()

    distance_to_cg = rocket_cg - (relative_position)
    return distance_to_cg


def process_elements_position(ork, elements, rocket_cg, rocket_mass, top_position=0):
    element = {
        "length": ork.getLength(),
        "CM": ork.getCG().x,
        "distance_to_cm": calculate_distance_to_cg(ork, rocket_cg, top_position),
    }
    logger.info("Starting to process '%s'", ork.getName())

    elements[ork.getName()] = element
    i = 0

    while True:
        if i >= ork.getChildCount():
            logger.info("No more children for '%s'", ork.getName())
            break

        try:
            child = ork.getChild(i)
            new_elements = process_elements_position(
                child, {}, rocket_cg, rocket_mass, top_position
            )
            elements.update(new_elements)
            logger.info("Child '%s' processed", child.getName())

            if not is_sub_component(child):
                top_position += child.getLength()
                logger.info("The child '%s' is not a sub-component", child.getName())

            i += 1
            logger.info("Moving to the next child")

        except Exception as e:
            if "IndexOutOfBoundsException" in str(e):
                logger.warning(
                    "Index out of bounds - likely no more children to process."
                )
                break
            else:
                logger.error(
                    "Error while processing the position of the elements: %s",
                    e,
                    exc_info=True,
                )
                logger.info(
                    "The elements are:\n%s",
                    _dict_to_string(elements, indent=23),
                )
                print(e)
                break  # Exit the loop if an unexpected error occurs

    logger.info("Finished processing '%s'", ork.getName())
    return elements
