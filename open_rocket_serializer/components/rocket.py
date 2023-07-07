# radius,
# mass,
# inertia,

# center_of_mass_without_motor,
# coordinate_system_orientation="tail_to_nose", done

import numpy as np


def search_rocket(bs, datapoints, data_labels, ork, burnout_position, verbose=False):
    settings = {}

    # get radius
    settings["radius"] = get_rocket_radius(ork)

    # get mass
    cg_location_vector = [
        float(datapoint.text.split(",")[data_labels.index("CG location")])
        for datapoint in datapoints
    ]
    settings["mass"] = get_mass(datapoints, data_labels, burnout_position)

    # get inertias
    inertia_z, inertia_i = get_inertias(data_labels, burnout_position, datapoints)
    settings["inertia"] = (inertia_i, inertia_i, inertia_z)

    # get center of mass
    empty_rocket_cm = cg_location_vector[burnout_position]
    # TODO: needs correction bc the motor's structure is also included
    settings["center_of_mass_without_propellant"] = empty_rocket_cm

    # get coordinate system orientation
    # TODO: check if it can be different from tail_to_nose in some cases
    settings["coordinate_system_orientation"] = "tail_to_nose"

    return settings


def get_rocket_radius(ork):
    # TODO: Improve this. Usually breaks when the rocket has more than one tube.
    return ork.getRocket().getChild(0).getChild(1).getAftRadius()


def get_mass(datapoints, data_labels, burnout_position):
    mass_vector = [
        float(datapoint.text.split(",")[data_labels.index("Mass")])
        for datapoint in datapoints
    ]
    return mass_vector[burnout_position]


def get_inertias(data_labels, burnout_position, datapoints):
    """Get the moment of inertia of the rocket in the longitudinal and rotational
    axis. The moment of inertia is calculated at the burnout position. This
    means that the motor is included in the calculation, but the propellant mass
    is not.

    Parameters
    ----------
    data_labels : list
        List of strings with the labels of the data.
    burnout_position : int
        The index of the burnout position in the data.
    datapoints : list
        List of datapoints available in the .ork file.

    Returns
    -------
    (longitudinal, rotational) : tuple of floats
        The moment of inertia of the rocket in the longitudinal and rotational
        axis, respectively.
    """
    longitudinal = [
        float(
            datapoint.text.split(",")[
                data_labels.index("Longitudinal moment of inertia")
            ]
        )
        for datapoint in datapoints
    ][burnout_position]
    rotational = [
        float(
            datapoint.text.split(",")[data_labels.index("Rotational moment of inertia")]
        )
        for datapoint in datapoints
    ][burnout_position]
    return longitudinal, rotational
