import logging
import os
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


def save_drag_curve(datapoints, data_labels, output_folder):
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
    logger.info(f"Collected altitude vector")

    apogee_index = np.argmax(altitude_vector)
    datapoints = datapoints[:apogee_index]
    logger.info(f"Removed data after apogee")

    # Extract the drag coefficient and Mach number
    cd = [
        float(datapoint.text.split(",")[data_labels.index("Axial drag coefficient")])
        for datapoint in datapoints
    ]
    mach = [
        float(datapoint.text.split(",")[data_labels.index("Mach number")])
        for datapoint in datapoints
    ]
    logger.info(f"Collected drag coefficient and Mach number")

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
    logger.info(f"Successfully created the drag curve")

    # Save to csv file
    path = os.path.join(output_folder, "drag_curve.csv")
    np.savetxt(path, cd, delimiter=",", fmt="%.6f")
    logger.info(f"Successfully saved the drag curve file to: '{Path(path).as_posix()}'")
    return path
