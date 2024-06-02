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
    level = 0
    root = ork.getRoot()
    while ork != root:
        ork = ork.getParent()
        level += 1
    return level > 1


def parent_is_a_stage(ork) -> bool:
    # Verify if the parent of the object is a Stage or not.
    try:
        parent = ork.getParent()
    except AttributeError:
        return False

    return parent.getClass().getSimpleName() in ["Stage", "AxialStage"]


def calculate_distance_to_the_nose_tip(ork, top_position: float):
    # NOTE: Always considering the nose tip as the reference point, it's the 0.

    if ork.getClass().getSimpleName() in ["Rocket"]:
        return 0

    if is_sub_component(ork) == True:
        try:
            distance_to_nose = top_position + ork.getPositionValue()
        except AttributeError:
            # "object has no attribute 'getPositionValue'"
            if parent_is_a_stage(ork):
                distance_to_nose = top_position
            else:
                distance_to_nose = top_position + ork.getPosition().x
    else:
        distance_to_nose = top_position + ork.getLength()
    return distance_to_nose


def process_elements_position(
    ork, elements, center_of_dry_mass, rocket_mass, top_position=0
):
    if ork.getClass().getSimpleName() in ["Parachute", "MassComponent"]:
        # These classes are irrelevant for our work
        return elements

    element = {
        "type": ork.getClass().getSimpleName(),
        "name": ork.getName(),
        "length": ork.getLength(),
        "position": calculate_distance_to_the_nose_tip(ork, top_position),
    }
    logger.info(
        "Starting to process element '%s' of type '%s'",
        ork.getName(),
        ork.getClass().getSimpleName(),
    )

    elements[ork.getName()] = element
    i = 0

    while True:
        if i >= ork.getChildCount():
            logger.info("No more children for '%s'", ork.getName())
            break

        try:
            child = ork.getChild(i)
            new_elements = process_elements_position(
                child, {}, center_of_dry_mass, rocket_mass, top_position
            )
            elements.update(new_elements)
            logger.info("Child '%s' processed", child.getName())

            top_position += child.getLength()

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
