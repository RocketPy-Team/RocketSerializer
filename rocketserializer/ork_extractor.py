import logging

from ._helpers import _dict_to_string
from .components.drag_curve import save_drag_curve
from .components.environment import search_environment
from .components.fins import (
    search_elliptical_fins,
    search_free_form_fins,
    search_trapezoidal_fins,
)
from .components.flight import search_launch_conditions
from .components.id import search_id_info
from .components.motor import __get_motor_mass, generate_thrust_curve, search_motor
from .components.nose_cone import search_nosecone
from .components.open_rocket_wrangler import process_elements_position
from .components.parachute import search_parachutes
from .components.rail_buttons import search_rail_buttons
from .components.rocket import get_rocket_radius, search_rocket
from .components.stored_results import search_stored_results
from .components.transition import search_transitions
from .components.xml_wrangler import process_elements_position_xml

logger = logging.getLogger(__name__)


def ork_extractor(bs, filepath, output_folder, ork=None, eng=None, use_simulation=True):
    """Generates the parameters.json file with the parameters for rocketpy

    Parameters
    ----------
    bs : BeautifulSoup
        BeautifulSoup object of the .ork file.
    filepath : str
        Path to the .ork file.
    output_folder : str
        Path to the output folder.
    ork : orhelper, optional
        An object representing the OpenRocket document.  When None, component
        positions and transition radii are resolved from the XML alone (no
        JVM required).
    eng : str, optional
        Path to a RASP .eng thrust-curve file, used when the .ork contains no
        simulation data.  By default .eng files near the .ork are searched
        and verified against the design's motor digest.
    use_simulation : bool, optional
        When False, any simulation data stored in the file is IGNORED for
        building the rocket: drag comes from the geometry model, thrust from
        an .eng/database motor and mass/CG/inertia from the structure mass
        model — exactly as if the file had never been simulated.  The stored
        simulation results (max altitude etc.) are still extracted, as an
        informational cross-check only.

    Returns
    -------
    dictionary
        Dictionary with the parameters to be used in rocketpy simulations. The
        keys are: "id", "environment", "rocket", "nosecones", "trapezoidal_fins",
        "tails", "parachutes", "rail_buttons", "motors", "flight" and
        "stored_results".
    """
    settings = {}

    def _safe_search(func, default_ret, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error extracting %s: %s", func.__name__, e, exc_info=True)
            return default_ret

    # Initialize some important vectors
    datapoints, data_labels, time_vector = __init_vectors(bs)
    logger.info("Initialized data vectors from the ORK file.")
    has_simulation = use_simulation and len(datapoints) > 0
    if not use_simulation and datapoints:
        logger.info(
            "Simulation data present but ignored (use_simulation=False); "
            "building from geometry, .eng thrust and the mass model."
        )

    ork_motor = resolved_motor = motor_mount = None
    if has_simulation:
        # Retrieve the motor properties from the simulation data
        motors = search_motor(bs, datapoints, data_labels)
        _, _, burnout_position = __get_motor_mass(datapoints, data_labels)
        logger.info("Motor parameters retrieved.")
    else:
        # No simulation data: motor from a matched .eng / motor database
        # pylint: disable=import-outside-toplevel
        from . import nosim

        burnout_position = 0
        ork_motor, resolved_motor = nosim.resolve_motor(bs, filepath, eng_path=eng)
        motor_mount = nosim.motor_mount_geometry(bs, ork_motor) if ork_motor else None
        motors = nosim.build_motors_dict(bs, ork_motor, resolved_motor, motor_mount)
        logger.info("Motor parameters fabricated without simulation data.")

    # Get the first set of parameters
    id_info = search_id_info(bs, filepath)
    logger.info("Metadata parameters retrieved.")

    environment = _safe_search(search_environment, {}, bs)
    logger.info("Environment parameters retrieved.")

    if has_simulation:
        rocket_data = _safe_search(
            search_rocket,
            ({"center_of_mass_without_propellant": 0, "mass": 0, "radius": 0}, 0),
            bs,
            datapoints,
            data_labels,
            burnout_position,
            motor_dry_mass=motors.get("dry_mass", 0.0),
            motor_radius=motors.get("grain_outer_radius", 0.0),
            motor_length=motors.get("grain_initial_height", 0.0),
        )
        rocket, motor_position = rocket_data
        motors["position"] = motor_position
        mass_value = rocket.get("mass")
        if not mass_value or mass_value != mass_value:  # falsy or NaN
            # broken/dead simulation mass columns (seen in real files):
            # recover the rocket's mass properties from the structure model
            # pylint: disable=import-outside-toplevel
            from . import nosim

            logger.warning(
                "Simulation mass data unusable; recovering rocket mass "
                "properties from the structure mass model."
            )
            ork_motor, resolved_motor = nosim.resolve_motor(bs, filepath, eng_path=eng)
            motor_mount = (
                nosim.motor_mount_geometry(bs, ork_motor) if ork_motor else None
            )
            radius_value = rocket.get("radius") or _safe_search(
                get_rocket_radius, 0.0, bs
            )
            fallback = _safe_search(
                nosim.build_rocket_dict,
                None,
                bs,
                ork_motor,
                resolved_motor,
                motor_mount,
                radius_value,
            )
            if fallback:
                rocket = fallback
                if resolved_motor is not None:
                    # keep motors consistent with the recovered structure
                    motors["dry_mass"] = resolved_motor.burnout_mass
            if not motors.get("position"):
                motors["position"] = nosim.build_motors_dict(
                    bs, ork_motor, resolved_motor, motor_mount
                )["position"]
    else:
        from . import nosim  # pylint: disable=import-outside-toplevel

        radius_value = _safe_search(get_rocket_radius, 0.0, bs)
        rocket = _safe_search(
            nosim.build_rocket_dict,
            {
                "center_of_mass_without_propellant": 0,
                "mass": 0,
                "radius": radius_value,
                "inertia": (0, 0, 0),
                "coordinate_system_orientation": "nose_to_tail",
            },
            bs,
            ork_motor,
            resolved_motor,
            motor_mount,
            radius_value,
        )
    logger.info("Rocket parameters retrieved.")

    flight = _safe_search(search_launch_conditions, {}, bs)
    logger.info("Flight conditions retrieved.")

    # process different elements of the rocket
    center_of_dry_mass = rocket.get("center_of_mass_without_propellant", 0)
    rocket_mass = rocket.get("mass", 0)
    rocket_radius = rocket.get("radius", 0)

    if ork is not None:
        elements = _safe_search(
            process_elements_position,
            {},
            ork.getRocket(),
            {},
            center_of_dry_mass,
            rocket_mass,
            top_position=0,
        )
    else:
        elements = _safe_search(process_elements_position_xml, {}, bs)
    logger.info("The elements are:\n%s", _dict_to_string(elements, indent=23))

    nosecones = _safe_search(search_nosecone, [], bs, elements, rocket_radius)
    trapezoidal_fins = _safe_search(search_trapezoidal_fins, [], bs, elements)
    elliptical_fins = _safe_search(search_elliptical_fins, [], bs, elements)
    freeform_fins = _safe_search(search_free_form_fins, {}, bs, elements)
    transitions = _safe_search(search_transitions, [], bs, elements, ork)
    rail_buttons = _safe_search(search_rail_buttons, [], bs, elements)
    parachutes = _safe_search(search_parachutes, [], bs)
    stored_results = _safe_search(
        search_stored_results,
        {},
        bs,
        datapoints,
        data_labels,
        time_vector,
        burnout_position,
    )

    # save everything to a dictionary
    settings["id"] = id_info
    settings["environment"] = environment
    settings["rocket"] = rocket
    settings["nosecones"] = nosecones
    settings["trapezoidal_fins"] = trapezoidal_fins
    settings["elliptical_fins"] = elliptical_fins
    settings["freeform_fins"] = freeform_fins
    settings["tails"] = transitions
    settings["parachutes"] = parachutes
    settings["rail_buttons"] = rail_buttons
    settings["motors"] = motors
    settings["flight"] = flight
    settings["stored_results"] = stored_results

    if has_simulation:
        # get drag and thrust curves from the simulation data
        settings["rocket"]["drag_curve"] = save_drag_curve(
            datapoints, data_labels, output_folder
        )
        logger.info("Drag curve generated.")
        thrust_path = generate_thrust_curve(
            output_folder, datapoints, data_labels, time_vector
        )
        settings["motors"]["thrust_source"] = thrust_path
        logger.info("Thrust curve generated.")
    else:
        # pylint: disable=import-outside-toplevel
        from . import nosim
        from .motors import write_thrust_curve_csv

        settings["rocket"]["drag_curve"] = _safe_search(
            nosim.geometry_drag_curve, None, bs, output_folder
        )
        logger.info("Drag curve computed from geometry.")
        if resolved_motor is not None:
            settings["motors"]["thrust_source"] = write_thrust_curve_csv(
                resolved_motor, output_folder
            )
            logger.info("Thrust curve written from the matched motor file.")
        else:
            settings["motors"]["thrust_source"] = None
            logger.warning(
                "No thrust source available: no matching .eng file or "
                "database motor was found."
            )

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
    # Use only the first databranch (main flight data), not secondary branches
    # which may have different numbers of columns (e.g. recovery events)
    first_branch = bs.find("databranch")
    if first_branch is None:
        logger.info("No simulation data found in the .ork file.")
        return [], [], []
    datapoints = first_branch.find_all("datapoint")
    data_labels = first_branch.attrs["types"].split(",")

    time_vector = [float(datapoint.text.split(",")[0]) for datapoint in datapoints]
    start_pos = 0
    final_pos = len(time_vector)

    # Get the start position, the ignition time.
    for idx, position in enumerate(time_vector):
        if position == 0:
            start_pos = idx
            break

    # Filter the datapoints to get only the ones after the ignition.
    datapoints = datapoints[start_pos:final_pos]
    time_vector = time_vector[start_pos:final_pos]
    logger.info("Successfully initialized vectors with %d datapoints", len(datapoints))
    return datapoints, data_labels, time_vector
