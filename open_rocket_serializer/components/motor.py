import numpy as np
import os
import yaml

def search_motor(burnout_time, propelant_mass, motor_radius, motor_length):
    inner_radius = motor_radius / 2
    grain_volume = np.pi * (motor_radius**2 - inner_radius**2) * motor_length
    grain_density = propelant_mass / grain_volume

    motor_configuration = {
            'burnOut': burnout_time,
            'grainDensity': float(grain_density),
            'grainInitialInnerRadius': inner_radius,
            'grainOuterRadius': motor_radius,
            'grainInitialHeight': motor_length,
            'nozzleRadius': 1.5*inner_radius,
            'throatRadius': inner_radius,
    }
    print(f'[Motor] Successfully configured motor| Configuration: \n{yaml.dump(motor_configuration, default_flow_style=False)}')

    return motor_configuration

def generate_thrust_curve(path, datapoints, data_labels, burnout_position, time_vect):
    thrust_vect = [float(datapoint.text.split(',')[data_labels.index('Thrust')]) for datapoint in datapoints]
    thrust_vect = np.array([time_vect[0: burnout_position], thrust_vect[0: burnout_position]]).T
    thrust_source_name = os.path.join(path, 'thrust_source.csv')
    np.savetxt(thrust_source_name, thrust_vect, delimiter=",")
    return thrust_source_name