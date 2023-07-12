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
            "object has no attribute 'getRelativePosition'"
            element_position = "Top of the parent component"
        try:
            relative_position = top_position + ork.getPositionValue()
        except AttributeError:
            "object has no attribute 'getPositionValue'"
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

    elements[ork.getName()] = element
    has_child = True
    i = 0
    while has_child:
        try:
            new_elements = process_elements_position(
                ork.getChild(i), {}, rocket_cg, rocket_mass, top_position
            )
            elements.update(new_elements)
            if is_sub_component(ork.getChild(i)) == False:
                top_position += ork.getChild(i).getLength()
            i += 1
        except Exception:
            # you are getting a java.lang.IndexOutOfBoundsException because
            # you are trying to access a child that does not exist
            has_child = False
    return elements
