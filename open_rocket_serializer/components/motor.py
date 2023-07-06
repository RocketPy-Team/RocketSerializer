import numpy as np
import os
import yaml


def search_motor(burnout_time, propellant_mass, motor_radius, motor_length):
    inner_radius = motor_radius / 2
    grain_volume = np.pi * (motor_radius**2 - inner_radius**2) * motor_length
    grain_density = propellant_mass / grain_volume

    settings = {  # TODO: adjust to new rocketpy v1.0.0 version
        "burnOut": burnout_time,
        "grainDensity": float(grain_density),
        "grainInitialInnerRadius": inner_radius,
        "grainOuterRadius": motor_radius,
        "grainInitialHeight": motor_length,
        "nozzleRadius": 1.5 * inner_radius,
        "throatRadius": inner_radius,
    }
    print(
        f"[Motor] Successfully configured motor: \n{yaml.dump(settings, default_flow_style=False)}"
    )

    return settings


def generate_thrust_curve(path, datapoints, data_labels, burnout_position, time_vector):
    thrust = [
        float(datapoint.text.split(",")[data_labels.index("Thrust")])
        for datapoint in datapoints
    ]
    thrust = np.array([time_vector[0:burnout_position], thrust[0:burnout_position]]).T
    source_name = os.path.join(path, "thrust_source.csv")
    np.savetxt(source_name, thrust, delimiter=",", fmt="%1.5f")
    print(f"[Thrust] Successfully generated thrust curve: {source_name}")
    return source_name
