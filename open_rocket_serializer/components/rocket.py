import logging

import numpy as np

from .._helpers import _dict_to_string
from ..components.nose_cone import search_nosecone

logger = logging.getLogger(__name__)


def search_rocket(bs, datapoints, data_labels, ork, burnout_position):
    settings = {}

    # get radius
    settings["radius"] = get_rocket_radius(bs)
    logger.info("Collected rocket radius.")

    # get mass
    cg_location_vector = [
        float(datapoint.text.split(",")[data_labels.index("CG location")])
        for datapoint in datapoints
    ]
    settings["mass"] = get_mass(datapoints, data_labels, burnout_position)
    logger.info("Collected rocket mass.")

    # get inertias
    inertia_z, inertia_i = get_inertias(data_labels, burnout_position, datapoints)
    settings["inertia"] = (inertia_i, inertia_i, inertia_z)
    logger.info("Collected rocket inertia.")

    # get center of mass
    center_of_dry_mass = cg_location_vector[burnout_position]
    center_of_mass = cg_location_vector[0]
    rocket_dry_mass = settings["mass"]
    propellant_mass = get_mass(datapoints, data_labels, 0) - rocket_dry_mass

    center_of_propellant_mass = (
        center_of_mass * (rocket_dry_mass + propellant_mass)
        - rocket_dry_mass * center_of_dry_mass
    ) / propellant_mass
    motor_position = center_of_propellant_mass
    settings["center_of_mass_without_propellant"] = center_of_dry_mass
    logger.info("Collected rocket center of mass.")

    # get coordinate system orientation
    settings["coordinate_system_orientation"] = "nose_to_tail"

    logger.info(
        "All the Rocket information was collected:\n%s",
        _dict_to_string(settings, indent=23),
    )
    return settings, motor_position


def get_rocket_radius(bs):
    # TODO: Improve this. Usually breaks when the rocket has more than one tube.
    # logger.warning(
    #     "This function usually breaks when the rocket has more than one tube."
    # )
    bodytubes = bs.findAll("bodytube") # if there is no bodytubes (len == 0), there is no rocket
    logger.info(f"A total of {len(bodytubes)} bodytubes were detected")

    radius_vector = [i.find("radius").text for i in bodytubes]
    logger.info("rocket radius founded: {}".format(radius_vector))

    if 'auto' in radius_vector:
        if len(radius_vector) == 1:
            radius = search_nosecone(bs, elements_use="n")
            return radius
        else:
            radius_vector_float = []
            for i in radius_vector:
                if i != 'auto':
                    radius_vector_float.append(float(i))
            radius = max(radius_vector_float)
            return radius
    else:
        radius = max([float(i) for i in radius_vector])
        return radius


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
    logger.info(
        "The moment of inertia of the rocket is: %f (longitudinal) and %f (rotational)",
        longitudinal,
        rotational,
    )
    return longitudinal, rotational
