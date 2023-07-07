def is_sub_component(ork):
    i = 0
    root = ork.getRoot()
    while ork != ork.getRoot():
        ork = ork.getParent()
        if root != ork.getParent():
            i += 1
    return True if i >= 2 else False


def calculate_distance_to_cg(ork, rocket_cg, top_position):
    if is_sub_component(ork) == True:
        element_position = ork.getRelativePosition().toString()
        relative_position = top_position + ork.getPositionValue()

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
            has_child = False
    return elements
