import json
import os
from datetime import datetime, timedelta
from multiprocessing.sharedctypes import Value

import nbformat
import numpy as np
import orhelper
from bs4 import BeautifulSoup

flight_parameters = {}


def generate(ork_file, nb_file, eng_file, open_rocket_instance):
    nb = nbformat.read(nb_file, nbformat.NO_CONVERT)

    main_code = f'Main = Calisto.addParachute(\n    "Main",\n    CdS=parameters["MainCds{idx}"],\n    trigger=mainTrigger,\n    samplingRate=105,\n    lag=parameters["MainDeployDelay{idx}"],\n    noise=(0, 8.3, 0.5),\n)'
    main_trigger = f'def mainTrigger(p, y):\n    # p = pressure\n    # y = [x, y, z, vx, vy, vz, e0, e1, e2, e3, w1, w2, w3]\n    # activate main when vz < 0 m/s and z < 800 + 1400 m (+1400 due to surface elevation).\n    return True if y[5] < 0 and y[2] < parameters["MainDeployAltitude{idx}"] + parameters["elevation"] else False'
    chute_cell_code += f"{main_trigger}\n\n{main_code}\n\n"

    for idx, drogue in enumerate(
        filter(lambda x: "Drogue" in x.find("name").text, chutes)
    ):
        drogue_cds = (
            search_cd_chute_if_auto(bs)
            if drogue.find("cd").text == "auto"
            else float(drogue.find("cd").text)
        )
        drogue_deploy_delay = float(drogue.find("deploydelay").text)
        drogue_code = f'Drogue = Calisto.addParachute(\n    "Drogue",\n    CdS=parameters["DrogueCds{idx}"],\n    trigger=drogueTrigger,\n    samplingRate=105,\n    lag=parameters["DrogueDeployDelay{idx}"],\n    noise=(0, 8.3, 0.5),\n)'
        drogue_area = np.pi * float(drogue.find("diameter").text) ** 2 / 4

        drogue_trigger = "def drogueTrigger(p, y):\n    # p = pressure\n    # y = [x, y, z, vx, vy, vz, e0, e1, e2, e3, w1, w2, w3]\n    # activate drogue when vz < 0 m/s.\n    return True if y[5] < 0 else False\n\n\n"
        chute_cell_code += f"{drogue_trigger}\n\n{drogue_code}\n"
        flight_parameters.update(
            {
                f"DrogueCds{idx}": drogue_area * drogue_cds,
                f"DrogueDeployDelay{idx}": drogue_deploy_delay,
            }
        )

    # TODO: rail_button, tuple for launch date

    nb["cells"][4][
        "source"
    ] = f'%matplotlib widget\n\nimport json\n\nparameters = json.loads(open("parameters.json").read())'
    nb["cells"][15]["source"] = generate_motor_code(
        path,
        burnout_position,
        burnout_time,
        thrust_vect,
        time_vector,
        propelant_mass,
        motor_radius,
        tube_length,
    )
    nb["cells"][20][
        "source"
    ] = f'Calisto = Rocket(\n    motor=Pro75M1670,\n    radius=parameters["radius"],\n    mass=parameters["rocketMass"],\n    inertiaI=parameters["inertiaI"],\n    inertiaZ=parameters["inertiaZ"],\n    distanceRocketNozzle=parameters["distanceRocketNozzle"],\n    distanceRocketPropellant=parameters["MotorCm"],\n    powerOffDrag="drag_coefficient.csv",\n    powerOnDrag="drag_coefficient.csv",\n)\n\nCalisto.setRailButtons([0.2, -0.5])'

    nb["cells"][23]["source"] = f"{nosecone}\n\n{trapezoidal_fin}\n\n{tail}"

    nb["cells"][27]["source"] = chute_cell_code

    nb["cells"][7][
        "source"
    ] = f'Env = Environment(\n    railLength=parameters["railLength"], latitude=39.3897, longitude=-8.28896388889, elevation=parameters["elevation"]\n)'
    nb["cells"][30][
        "source"
    ] = f'TestFlight = Flight(rocket=Calisto, environment=Env, inclination=parameters["inclination"], heading=parameters["heading"])'
    print(np.max(altitude_vector))

    with open(f"{path}parameters.json", "w") as convert_file:
        convert_file.write(json.dumps(flight_parameters))

    nbformat.write(nb, f"{path}Simulation.ipynb")


def trapezoidal_fin_code(fin, element, idx):
    trapezoidal_fin = f'Calisto.addTrapezoidalFins(parameters["finN{idx}"], rootChord=parameters["finRootChord{idx}"], tipChord=parameters["finTipChord{idx}"], span=parameters["finSpan{idx}"], distanceToCM=parameters["finDistanceToCm{idx}"], sweepAngle=parameters.get("finSweepAngle{idx}"), sweepLength=parameters.get("finSweepLength{idx}"))\n\n'
    return trapezoidal_fin


def generate_nosecone_code(bs, cm):
    nosecone = f'NoseCone = Calisto.addNose(length=parameters["noseLength"], kind=parameters["noseShape"], distanceToCM=parameters["noseDistanceToCM"])'
    return nosecone


def generate_motor_code(
    path,
    burnout_position,
    burnout_time,
    thrust_vect,
    time_vector,
    propelant_mass,
    motor_radius,
    motor_height,
):
    code = f'Pro75M1670 = SolidMotor(\n    thrustSource="thrust_source.csv",\n    burnOut=parameters["burnOut"],\n    grainNumber=1,\n    grainSeparation=0,\n    grainDensity=parameters["grainDensity"],\n    grainOuterRadius=parameters["grainOuterRadius"],\n    grainInitialInnerRadius=parameters["grainInitialInnerRadius"],\n    grainInitialHeight=parameters["grainInitialHeight"],\n    nozzleRadius=parameters["nozzleRadius"],\n    throatRadius=parameters["throatRadius"],\n    interpolationMethod="linear",\n)'
    return code


with orhelper.OpenRocketInstance() as instance:
    nb_file = "./docs/notebooks/getting_started.ipynb"
    generate(ork_file, nb_file, eng_file, instance)
