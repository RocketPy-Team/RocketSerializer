import logging

from ._helpers import _dict_to_string
from .components.drag_curve import save_drag_curve
from .components.environment import search_environment
from .components.fins import search_elliptical_fins, search_trapezoidal_fins
from .components.flight import search_launch_conditions
from .components.id import search_id_info
from .components.motor import __get_motor_mass, generate_thrust_curve, search_motor
from .components.nose_cone import search_nosecone
from .components.open_rocket_wrangler import process_elements_position
from .components.parachute import search_parachutes
from .components.rail_buttons import search_rail_buttons
from .components.rocket import search_rocket
from .components.stored_results import search_stored_results
from .components.transition import search_transitions

logger = logging.getLogger(__name__)


def ork_extractor(bs, filepath, output_folder, ork):
    """Generates the parameters.json file with the parameters for rocketpy

    Parameters
    ----------
    bs : BeautifulSoup
        BeautifulSoup object of the .ork file.
    filepath : str
        Path to the .ork file.
    output_folder : str
        Path to the output folder.
    ork : orhelper
        An object representing the OpenRocket document.
    verbose : bool, optional
        Whether or not to print a message of successful execution, by default
        False.

    Returns
    -------
    dictionary
        Dictionary with the parameters to be used in rocketpy simulations. The
        keys are: "id", "environment", "rocket", "nosecones", "trapezoidal_fins",
        "tails", "parachutes", "rail_buttons", "motors", "flight" and
        "stored_results".
    """
    settings = {}

    # Initialize some important vectors
    datapoints, data_labels, time_vector = __init_vectors(bs)
    logger.info("Initialized data vectors from the ORK file.")

    # Retrieve the motor properties
    motors = search_motor(bs, datapoints, data_labels)
    _, _, burnout_position = __get_motor_mass(datapoints, data_labels)
    logger.info("Motor parameters retrieved.")

    # Get the first set of parameters
    id_info = search_id_info(bs, filepath)
    logger.info("Metadata parameters retrieved.")

    environment = search_environment(bs)
    logger.info("Environment parameters retrieved.")

    rocket, motor_position = search_rocket(
        bs, datapoints, data_labels, burnout_position
    )
    motors["position"] = motor_position
    logger.info("Rocket parameters retrieved.")

    flight = search_launch_conditions(bs)
    logger.info("Flight conditions retrieved.")

    # process different elements of the rocket
    center_of_dry_mass = rocket["center_of_mass_without_propellant"]
    rocket_mass = rocket["mass"]
    rocket_radius = rocket["radius"]

    elements = process_elements_position(
        ork.getRocket(), {}, center_of_dry_mass, rocket_mass, top_position=0
    )
    logger.info("The elements are:\n%s", _dict_to_string(elements, indent=23))

    nosecones = search_nosecone(bs, elements, rocket_radius)
    trapezoidal_fins = search_trapezoidal_fins(bs, elements)
    elliptical_fins = search_elliptical_fins(bs, elements)
    transitions = search_transitions(bs, elements, ork)
    rail_buttons = search_rail_buttons(bs, elements)
    parachutes = search_parachutes(bs)
    stored_results = search_stored_results(
        bs, datapoints, data_labels, time_vector, burnout_position
    )

    # save everything to a dictionary
    settings["id"] = id_info
    settings["environment"] = environment
    settings["rocket"] = rocket
    settings["nosecones"] = nosecones
    settings["trapezoidal_fins"] = trapezoidal_fins
    settings["elliptical_fins"] = elliptical_fins
    settings["tails"] = transitions
    settings["parachutes"] = parachutes
    settings["rail_buttons"] = rail_buttons
    settings["motors"] = motors
    settings["flight"] = flight
    settings["stored_results"] = stored_results

    # get drag curves
    settings["rocket"]["drag_curve"] = save_drag_curve(
        datapoints, data_labels, output_folder
    )
    logger.info("Drag curve generated.")

    # get thrust curve
    thrust_path = generate_thrust_curve(
        output_folder, datapoints, data_labels, time_vector
    )
    settings["motors"]["thrust_source"] = thrust_path
    logger.info("Thrust curve generated.")

    logger.info(
        "Extraction completed. A dictionary with all the parameters was generated."
    )
    logger.info(
        "Dictionary with the parameters:\n%s", _dict_to_string(settings, indent=23)
    )

    return settings


def __init_vectors(bs):
    """Initializes the vectors with the data from the .ork file.

    Parameters
    ----------
    bs : BeautifulSoup
        BeautifulSoup object of the .ork file.

    Returns
    -------
    datapoints : list
        The datapoints.
    data_labels : list
        The names of each data column.
    time_vector : list
        The time vector.
    """
    datapoints = bs.findAll("datapoint")
    data_labels = bs.find("databranch").attrs["types"].split(",")

    time_vector = [float(datapoint.text.split(",")[0]) for datapoint in datapoints]
    start_pos = 0
    final_pos = len(time_vector) - 1

    # Get the start position, the ignition time.
    for idx, position in enumerate(time_vector):
        if position == 0:
            start_pos = idx

    # Filter the datapoints to get only the ones after the ignition.
    datapoints = datapoints[start_pos:final_pos]
    time_vector = time_vector[start_pos:final_pos]
    logger.info("Successfully initialized vectors with %d datapoints", len(datapoints))
    return datapoints, data_labels, time_vector
