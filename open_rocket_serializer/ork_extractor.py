from .components.drag_curve import save_drag_curve
from .components.environment import search_environment
from .components.fins import search_trapezoidal_fins
from .components.flight import search_launch_conditions
from .components.id import search_id_info
from .components.motor import __get_motor_mass, generate_thrust_curve, search_motor
from .components.nose_cone import search_nosecone
from .components.open_rocket_wrangler import process_elements_position
from .components.parachute import search_parachutes
from .components.rocket import search_rocket
from .components.transition import search_transitions


def ork_extractor(bs, filepath, output_folder, ork, eng, verbose=False):
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
        OpenRocket object.
    eng : str
        Engine file name.
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
    # TODO: create a list of assumptions
    settings = {}

    # Initialize some important vectors
    datapoints, data_labels, time_vector = __init_vectors(bs)

    # Retrieve the motor properties
    motors = search_motor(bs, datapoints, data_labels, time_vector, verbose=False)
    _, _, burnout_position = __get_motor_mass(datapoints, data_labels)

    # Get the first set of parameters
    id_info = search_id_info(bs, filepath, verbose=False)
    environment = search_environment(bs, verbose=False)
    rocket = search_rocket(
        bs, datapoints, data_labels, ork, burnout_position, verbose=False
    )
    flight = search_launch_conditions(bs, verbose=False)

    # process different elements of the rocket
    empty_rocket_cm = rocket["center_of_mass_without_propellant"]
    rocket_mass = rocket["mass"]
    rocket_radius = rocket["radius"]
    elements = process_elements_position(
        ork.getRocket(), {}, empty_rocket_cm, rocket_mass, top_position=0
    )
    nosecones = search_nosecone(bs, elements, verbose=False)
    trapezoidal_fins = search_trapezoidal_fins(bs, elements)
    transitions = search_transitions(bs, elements, ork, rocket_radius, verbose)
    parachutes = search_parachutes(bs, verbose=False)

    # save everything to a dictionary
    settings["id"] = id_info
    settings["environment"] = environment
    settings["rocket"] = rocket
    settings["nosecones"] = nosecones
    settings["trapezoidal_fins"] = trapezoidal_fins
    settings["tails"] = transitions
    settings["parachutes"] = parachutes
    settings["rail_buttons"] = {}  # TODO: implement rail buttons
    settings["motors"] = motors
    settings["flight"] = flight
    settings["stored_results"] = {}  # TODO: implement stored results

    # get drag curves
    settings["rocket"]["drag_curve"] = save_drag_curve(
        datapoints, data_labels, output_folder
    )
    # get thrust curve
    thrust_path = eng or generate_thrust_curve(
        output_folder, datapoints, data_labels, time_vector
    )
    settings["motors"]["thrust_source"] = thrust_path

    if verbose:
        print(
            "[ork_extractor] Extraction complete. A dictionary with the "
            + "parameters was generated and returned."
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
    return datapoints, data_labels, time_vector
