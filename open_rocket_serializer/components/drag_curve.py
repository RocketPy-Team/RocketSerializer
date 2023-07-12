import os

import numpy as np


def save_drag_curve(datapoints, data_labels, output_folder, verbose=False):
    """Extracts the drag curve from the data and saves it to a csv file.

    Parameters
    ----------
    datapoints : list
        The datapoints.
    data_labels : list of str
        The labels of the data.
    path : str
        Path to the folder where the drag curve should be saved. This needs to
        be a folder that already exists.
    verbose : bool, optional
        Whether or not to print a message of successful execution, by default
        False.

    Returns
    -------
    path : str
        The path to the drag curve.
    """
    # Remove the data after apogee
    altitude_vector = [
        float(datapoint.text.split(",")[data_labels.index("Altitude")])
        for datapoint in datapoints
    ]
    apogee_index = np.argmax(altitude_vector)
    datapoints = datapoints[:apogee_index]

    # Extract the drag coefficient and Mach number
    cd = [
        float(datapoint.text.split(",")[data_labels.index("Axial drag coefficient")])
        for datapoint in datapoints
    ]
    mach = [
        float(datapoint.text.split(",")[data_labels.index("Mach number")])
        for datapoint in datapoints
    ]

    # Convert to numpy array
    cd = np.array([mach, cd]).T
    # Remove NaN values to avoid errors
    cd = cd[~np.isnan(cd).any(axis=1), :]
    # Sort by Mach number
    cd = cd[cd[:, 0].argsort()]
    # Remove duplicate Mach numbers
    cd = np.unique(cd, axis=0)
    # Remove values when the drag is lower than 0
    cd = cd[cd[:, 1] > 0, :]

    # Save to csv file
    path = os.path.join(output_folder, "drag_curve.csv")
    np.savetxt(path, cd, delimiter=",", fmt="%.6f")

    if verbose:
        print(f"[Drag Curve] Successfully extracted the drag curve: {path}")
    return path
