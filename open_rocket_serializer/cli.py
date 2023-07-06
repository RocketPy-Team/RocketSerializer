import json
import os

import click
import numpy as np
import orhelper
import yaml
from bs4 import BeautifulSoup

from open_rocket_serializer.components.drag_curve import save_drag_curve
from open_rocket_serializer.components.fins import search_trapezoidal_fins
from open_rocket_serializer.components.motor import generate_thrust_curve, search_motor
from open_rocket_serializer.components.nose_cone import search_nosecone
from open_rocket_serializer.components.open_rocket_wrangler import (
    process_elements_position,
)
from open_rocket_serializer.components.parachute import search_parachute
from open_rocket_serializer.components.transition import search_transitions


def generate(bs, eng, path, ork, team_name):
    # TODO: create a list of assumptions

    settings = {}
    datapoints = bs.findAll("datapoint")
    data_labels = bs.find("databranch").attrs["types"].split(",")

    time_vector = [float(datapoint.text.split(",")[0]) for datapoint in datapoints]
    starting_pos = 0
    final_pos = len(time_vector) - 1
    for idx, position in enumerate(time_vector):
        if position == 0:
            starting_pos = idx
    datapoints = datapoints[starting_pos:final_pos]
    time_vector = time_vector[starting_pos:final_pos]

    cg_location_vector = [
        float(datapoint.text.split(",")[data_labels.index("CG location")])
        for datapoint in datapoints
    ]
    altitude_vector = [
        float(datapoint.text.split(",")[data_labels.index("Altitude")])
        for datapoint in datapoints
    ]
    apogee_index = np.argmax(altitude_vector)
    mass = [
        float(datapoint.text.split(",")[data_labels.index("Mass")])
        for datapoint in datapoints
    ]

    if "Propellant mass" in data_labels:
        propellant_mass_vector = [
            float(datapoint.text.split(",")[data_labels.index("Propellant mass")])
            for datapoint in datapoints
        ]
    elif "Motor mass" in data_labels:
        motor_mass = np.array(
            [
                float(datapoint.text.split(",")[data_labels.index("Motor mass")])
                for datapoint in datapoints
            ]
        )
        propellant_mass_vector = motor_mass - min(motor_mass)
        propellant_mass_vector = list(propellant_mass_vector)

    normalize_propellant_mass_vect = np.array(propellant_mass_vector)
    normalize_propellant_mass_vect = (
        normalize_propellant_mass_vect
        - normalize_propellant_mass_vect[np.argmin(normalize_propellant_mass_vect)]
    )
    propellant_mass_vector = list(normalize_propellant_mass_vect)
    propellant_mass = propellant_mass_vector[0]
    burnout_position = np.argwhere(np.array(propellant_mass_vector) == 0)[0][0]

    rocket_mass = mass[0] - propellant_mass_vector[0]
    empty_rocket_cm = cg_location_vector[burnout_position]
    elements = process_elements_position(
        ork.getRocket(), {}, empty_rocket_cm, rocket_mass, top_position=0
    )
    rocket_radius = (
        ork.getRocket().getChild(0).getChild(1).getAftRadius()
    )  # Improve this

    last_element = [key for key in elements.keys()][-1]

    longitudinal_moment_of_inertia = [
        float(
            datapoint.text.split(",")[
                data_labels.index("Longitudinal moment of inertia")
            ]
        )
        for datapoint in datapoints
    ][burnout_position]
    rotational_moment_of_inertia = [
        float(
            datapoint.text.split(",")[data_labels.index("Rotational moment of inertia")]
        )
        for datapoint in datapoints
    ][burnout_position]

    ## Motor
    motor_cm = (
        empty_rocket_cm
        - (cg_location_vector[0] * mass[0] - empty_rocket_cm * rocket_mass)
        / propellant_mass
    )
    nozzle_cm = (
        elements[last_element]["DistanceToCG"] - elements[last_element]["length"]
    )
    burnout_time = time_vector[burnout_position]
    motor_length = float(bs.find("motormount").find("length").text)
    motor_radius = float(bs.find("motormount").find("diameter").text) / 2
    thrust_source_path = eng or generate_thrust_curve(
        path, datapoints, data_labels, burnout_position, time_vector
    )

    settings.update(save_drag_curve(datapoints[0:apogee_index], data_labels, path))
    settings.update(search_nosecone(bs, elements))
    settings.update(search_trapezoidal_fins(bs, elements, idx))
    settings.update(search_parachute(bs))
    settings.update(search_transitions(bs, elements, ork, rocket_radius))
    settings.update(
        search_motor(burnout_time, propellant_mass, motor_radius, motor_length)
    )

    additional_parameters = {
        "rocketMass": float(rocket_mass),
        "elevation": 160,
        "date": "2022-10-14 14:00:00",
        "emptyRocketCm": empty_rocket_cm,
        "radius": float(rocket_radius),
        "MotorCm": float(motor_cm),
        "distanceRocketNozzle": nozzle_cm,
        "inertiaI": longitudinal_moment_of_inertia,
        "inertiaZ": rotational_moment_of_inertia,
        "railLength": 12,
        "inclination": 84,
        "heading": 133,
        "thrustSource": thrust_source_path,
        "latitude": 39.3897,
        "longitude": -8.28896388889,
        "distanceRocketPropellant": float(motor_cm),
        "railButtonDistToCM1": 0.2,
        "railButtonDistToCM2": -0.5,
        "name": team_name,
    }
    settings.update(additional_parameters)
    print(
        f"[AdditionalParameters] Configuration: \n{yaml.dump(additional_parameters, default_flow_style=False)}"
    )

    with open(os.path.join(path, "parameters.json"), "w") as convert_file:
        convert_file.write(json.dumps(settings, indent=4, sort_keys=True))


@click.group()
@click.version_option()
def cli():
    """Open Rocket Serializer.
    This library has as objective to convert .ork file into parameters
    that rocketpy is able to use for simulating the rocket. It will
    be generated a .json file which you can use with a template simulation
    to execute the simulation on your rocket.
    """


@cli.group()
def serializer():
    """Serializes open rocket file into a rocketpy parameters."""


@cli.command("generate_json")
@click.option("--path", type=str, default="GeneratedSimulations")
@click.option("--team_name", type=str, default="Team")
@click.option("--ork", type=str, default="rocket.ork")
@click.option("--eng", type=str, default="")
@click.option("--ork_jar", type=str, default="")
def generate_json(path, team_name, ork, eng, ork_jar):
    bs = BeautifulSoup(open(ork).read(), features="html.parser")
    datapoints = bs.findAll("datapoint")

    if len(datapoints) == 0:
        raise Exception(
            "The file must contain the simulation data.\n"
            + "Open the .ork file and run the simulation first."
        )

    data_labels = bs.find("databranch").attrs["types"].split(",")
    if "CG location" not in data_labels:
        raise Exception(
            "The file must be in English.\n"
            + "Open the .ork file and change the language to English."
        )

    with orhelper.OpenRocketInstance(ork_jar) as instance:
        if os.path.exists(path) is False:
            os.mkdir(path)
        path = os.path.join(path, team_name)
        if os.path.exists(path) is False:
            os.mkdir(path)

        orh = orhelper.Helper(instance)
        ork = orh.load_doc(ork)

        generate(bs, eng, path, ork, team_name)
