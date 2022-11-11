import numpy as np
import os

def save_drag_curve(datapoints, data_labels, path):
    drag_coefficient = [float(datapoint.text.split(',')[data_labels.index('Axial drag coefficient')]) for datapoint in datapoints]
    mach_number = [float(datapoint.text.split(',')[data_labels.index('Mach number')]) for datapoint in datapoints]

    drag_coefficient = np.array([mach_number, drag_coefficient]).T
    drag_coefficient = drag_coefficient[~np.isnan(drag_coefficient).any(axis=1), :]

    path = os.path.join(path, 'drag_coefficient.csv')
    np.savetxt(path, drag_coefficient, delimiter=",")
    drag_curve_parameters = {
        'dragCoefficientSourcePath': path,
    }
    print(f'[DragCure] Successfully extracted the drag curve: {drag_curve_parameters}')
    return drag_curve_parameters
