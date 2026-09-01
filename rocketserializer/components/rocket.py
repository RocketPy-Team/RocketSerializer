import logging

from .._helpers import _dict_to_string

logger = logging.getLogger(__name__)


def search_rocket(
    bs,
    datapoints,
    data_labels,
    burnout_position,
    motor_dry_mass=0.0,
    motor_radius=0.0,
    motor_length=0.0,
):
    """Rocket mass properties WITHOUT the motor, from the simulation columns.

    The simulation's "Mass" / "CG location" / inertia columns include the
    motor; RocketPy's ``Rocket`` expects motor-less values (the motor is added
    separately with its own dry mass).  The motor's burnout (casing) mass is
    therefore subtracted here, using the motor as an on-axis cylinder at the
    propellant position -- previously the casing was double-counted (once in
    ``rocket.mass`` and once in ``motors.dry_mass``).
    """
    settings = {}

    # get radius
    settings["radius"] = get_rocket_radius(bs)
    logger.info("Collected rocket radius.")

    # simulation values at burnout (they still include the motor casing)
    cg_location_vector = [
        float(datapoint.text.split(",")[data_labels.index("CG location")])
        for datapoint in datapoints
    ]
    burnout_mass = get_mass(datapoints, data_labels, burnout_position)
    inertia_z, inertia_i = get_inertias(data_labels, burnout_position, datapoints)

    # get center of mass
    center_of_dry_mass = cg_location_vector[burnout_position]
    center_of_mass = cg_location_vector[0]
    propellant_mass = get_mass(datapoints, data_labels, 0) - burnout_mass

    center_of_propellant_mass = (
        center_of_mass * (burnout_mass + propellant_mass)
        - burnout_mass * center_of_dry_mass
    ) / propellant_mass
    motor_position = center_of_propellant_mass

    # subtract the motor casing to obtain motor-less structure values
    structure_mass = burnout_mass - motor_dry_mass
    if motor_dry_mass > 0 and structure_mass > 0:
        structure_cg = (
            burnout_mass * center_of_dry_mass - motor_dry_mass * motor_position
        ) / structure_mass
        casing_iyy = motor_dry_mass * (3 * motor_radius**2 + motor_length**2) / 12
        casing_ixx = motor_dry_mass * motor_radius**2 / 2
        inertia_i = (
            inertia_i
            - casing_iyy
            - motor_dry_mass * (motor_position - center_of_dry_mass) ** 2
            - structure_mass * (structure_cg - center_of_dry_mass) ** 2
        )
        inertia_z = inertia_z - casing_ixx
        inertia_i = max(inertia_i, 0.0)
        inertia_z = max(inertia_z, 0.0)
    else:
        structure_cg = center_of_dry_mass

    settings["mass"] = structure_mass
    settings["inertia"] = (inertia_i, inertia_i, inertia_z)
    settings["center_of_mass_without_propellant"] = structure_cg
    logger.info("Collected rocket mass, inertia and center of mass.")

    # get coordinate system orientation
    settings["coordinate_system_orientation"] = "nose_to_tail"

    logger.info(
        "All the Rocket information was collected:\n%s",
        _dict_to_string(settings, indent=23),
    )
    return settings, motor_position


def get_rocket_radius(bs):
    # We want to take the maximum radius of the rocket
    tubes = bs.find_all("bodytube")
    noses = bs.find_all("nosecone")
    transitions = bs.find_all("transition")

    tubes_radius = [
        getattr(i.find("radius"), "text", "") for i in tubes if i.find("radius")
    ]
    noses_radius = [
        getattr(i.find("aftradius"), "text", "") for i in noses if i.find("aftradius")
    ]

    # Also collect radii from transitions (foreradius and aftradius)
    transition_radius = []
    for t in transitions:
        fore = t.find("foreradius")
        aft = t.find("aftradius")
        if fore:
            transition_radius.append(fore.text)
        if aft:
            transition_radius.append(aft.text)

    all_radius = tubes_radius + noses_radius + transition_radius

    # We need to convert to float, but removing the "auto" string first
    all_radius = [i.replace("auto ", "") for i in all_radius]
    all_radius = [i for i in all_radius if i != "auto"]
    all_radius = [float(i) for i in all_radius]

    if not all_radius:
        logger.warning("No radius found for the rocket. Defaulting to 0.")
        return 0.0

    rocket_radius = max(all_radius)
    logger.info("The maximum radius of the rocket is: %f", rocket_radius)
    return rocket_radius


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
