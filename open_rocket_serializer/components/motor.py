import logging
import os
from pathlib import Path

import numpy as np

from .._helpers import _dict_to_string

logger = logging.getLogger(__name__)


def search_motor(bs, datapoints, data_labels):
    """Search for the motor properties in the .ork file. The only property that
    is not included is the thrust curve, which is generated in the
    generate_thrust_curve function. Only rocketpy.SolidMotor class would be able
    to use the information from this function to create a motor object.

    Parameters
    ----------
    bs : bs4.BeautifulSoup
        The BeautifulSoup object of the .ork file.
    datapoints : list
        The datapoints from the .ork file.
    data_labels : list
        The labels of the datapoints.
    time_vector : list
        The time vector of the simulation.

    Returns
    -------
    settings : dict
        Dictionary with the motor properties. The keys are: "burn_time",
        "grain_density", "grain_initial_inner_radius", "grain_outer_radius",
        "grain_initial_height", "nozzle_radius", "throat_radius", "dry_mass",
        "dry_inertia", "center_of_dry_mass", "grains_center_of_mass_position",
        "grain_number", "grain_separation", "nozzle_position" and
        "coordinate_system_orientation".
    """
    settings = {}

    # retrieve motor geometry
    motor_length = float(bs.find("motormount").find("length").text)
    motor_radius = float(bs.find("motormount").find("diameter").text) / 2
    logger.info("Collected motor geometry: motor length and motor radius.")

    # get motor mass properties
    total_propellant_mass, motor_dry_mass, burnout_position = __get_motor_mass(
        datapoints, data_labels
    )
    motor_dry_mass = 0  # If NOTE: dry inertia is 0, this should ALWAYS be 0 too.
    center_of_dry_mass = 0
    dry_inertia = (0, 0, 0)  # impossible to retrieve from .ork file

    # define grains properties
    grain_number = 1
    grain_separation = 0
    grain_initial_inner_radius = motor_radius / 2
    grain_outer_radius = motor_radius
    grain_initial_height = motor_length
    grain_volume = (
        np.pi
        * (grain_outer_radius**2 - grain_initial_inner_radius**2)
        * grain_initial_height
    ) / grain_number
    grain_density = total_propellant_mass / (grain_volume * grain_number)
    grains_center_of_mass_position = 0
    logger.info("Calculated motor mass properties.")

    # get nozzle properties (impossible to retrieve from .ork file)
    throat_radius = 1.0 * grain_initial_inner_radius
    nozzle_radius = 1.5 * grain_initial_inner_radius
    nozzle_position = -motor_length / 2

    # set other motor properties
    coordinate_system_orientation = "nozzle_to_combustion_chamber"

    settings = {
        "grain_density": grain_density,
        "grain_initial_inner_radius": grain_initial_inner_radius,
        "grain_outer_radius": motor_radius,
        "grain_initial_height": motor_length,
        "nozzle_radius": nozzle_radius,
        "throat_radius": throat_radius,
        "dry_mass": motor_dry_mass,
        "dry_inertia": dry_inertia,
        "center_of_dry_mass_position": center_of_dry_mass,
        "grains_center_of_mass_position": grains_center_of_mass_position,
        "grain_number": grain_number,
        "grain_separation": grain_separation,
        "nozzle_position": nozzle_position,
        "coordinate_system_orientation": coordinate_system_orientation,
    }
    logger.info(
        f"Successfully configured the motor.\n" + _dict_to_string(settings, indent=23)
    )
    return settings


def generate_thrust_curve(
    folder_path, datapoints, data_labels, time_vector, verbose=False
):
    """Generate the thrust curve from the .ork file.

    Parameters
    ----------
    folder_path : str
        The path to the folder where the thrust curve should be saved. This
        needs to be a folder that already exists.
    datapoints : list
        List of datapoints from the .ork file.
    data_labels : list
        List of labels for the datapoints.
    time_vector : list
        The time vector of the simulation.

    Returns
    -------
    source_name : str
        The path to the thrust curve.
    """
    thrust = [
        float(datapoint.text.split(",")[data_labels.index("Thrust")])
        for datapoint in datapoints
    ]
    logger.info("Collected thrust vector")

    # convert to numpy array
    thrust = np.array([time_vector, thrust]).T

    # sort by time
    thrust = thrust[thrust[:, 0].argsort()]
    logger.info("The thrust points were sorted to be in ascending order")

    # clip the thrust curve to remove negative values
    thrust[thrust[:, 1] < 0, 1] = 0
    logger.info("Successfully clipped the thrust curve to remove negative values")

    # remove any items with thrust lower than 0.0001 N
    thrust = thrust[thrust[:, 1] > 0.0001, :]
    logger.info("Successfully created the thrust curve")

    # save to a csv file
    source_name = os.path.join(folder_path, "thrust_source.csv")
    np.savetxt(source_name, thrust, delimiter=",", fmt="%1.5f")

    logger.info(
        f"Successfully saved the thrust curve to: '{Path(source_name).as_posix()}'"
    )
    return source_name


def __get_motor_mass(datapoints, data_labels):
    """Get the motor mass from the .ork file.

    Parameters
    ----------
    datapoints : list
        List of datapoints from the .ork file.
    data_labels : list
        List of labels for the datapoints.

    Returns
    -------
    total_propellant_mass : float
        Total propellant mass, in kg.
    motor_dry_mass : float
        Motor dry mass, in kg. It is the minimum value of the motor mass. This
        corresponds to the mass of the motor without the propellant.
    burnout_position : int
        The index of the burnout position in the datapoints list.
    """
    if "Propellant mass" in data_labels:
        prop_mass_vector = [
            float(datapoint.text.split(",")[data_labels.index("Propellant mass")])
            for datapoint in datapoints
        ]
        motor_dry_mass = min(prop_mass_vector)
        logger.info("The motor dry mass is %.3f kg.", motor_dry_mass)
    elif "Motor mass" in data_labels:
        motor_mass = np.array(
            [
                float(datapoint.text.split(",")[data_labels.index("Motor mass")])
                for datapoint in datapoints
            ]
        )
        motor_dry_mass = min(motor_mass)
        prop_mass_vector = motor_mass - motor_dry_mass
        prop_mass_vector = list(prop_mass_vector)
        logger.info("The motor dry mass is %.3f kg.", motor_dry_mass)

    normalize = np.array(prop_mass_vector)
    normalize = normalize - normalize[np.argmin(normalize)]
    prop_mass_vector = list(normalize)
    total_propellant_mass = prop_mass_vector[0]
    burnout_position = np.argwhere(np.array(prop_mass_vector) == 0)[0][0]
    # q: why is it important to normalize the propellant mass vector?
    # a: to ensure that we are using the propellant mass, without the motor mass.
    #    Also, to ensure the final propellant mass is zero.

    logger.info(
        "The total propellant mass is %.3f kg. The motor dry mass is %.3f kg.",
        total_propellant_mass,
        motor_dry_mass,
    )
    return total_propellant_mass, motor_dry_mass, burnout_position
