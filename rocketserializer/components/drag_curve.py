import logging
import os
from pathlib import Path
from typing import Union

import numpy as np

logger = logging.getLogger(__name__)


def __collect_altitude_vector(
    datapoints: list[float], data_labels: list[str]
) -> list[float]:
    return [
        float(datapoint.text.split(",")[data_labels.index("Altitude")])
        for datapoint in datapoints
    ]


def __remove_data_after_apogee(datapoints: list[float], altitude_vector: list[float]):
    apogee_index = np.argmax(altitude_vector)
    return datapoints[:apogee_index]


def __extract_drag_and_mach(
    datapoints: list[float], data_labels: list[str]
) -> np.ndarray:
    cd = [
        float(datapoint.text.split(",")[data_labels.index("Axial drag coefficient")])
        for datapoint in datapoints
    ]
    mach = [
        float(datapoint.text.split(",")[data_labels.index("Mach number")])
        for datapoint in datapoints
    ]
    return np.array([mach, cd]).T


def __process_drag_data(cd: np.ndarray) -> np.ndarray:
    cd = cd[~np.isnan(cd).any(axis=1), :]  # Remove NaN values
    cd = cd[cd[:, 0].argsort()]  # Sort by Mach number
    cd = np.unique(cd, axis=0)  # Remove duplicate Mach numbers
    cd = cd[cd[:, 1] > 0, :]  # Remove values when the drag is lower than 0
    return cd


def __save_to_csv(cd: np.ndarray, output_folder: Union[Path, str]) -> str:
    path = os.path.join(output_folder, "drag_curve.csv")
    np.savetxt(path, cd, delimiter=",", fmt="%.6f")
    logger.info(
        "Successfully saved the drag curve file to: '%s'", Path(path).as_posix()
    )
    return path


def save_drag_curve(
    datapoints: list[float], data_labels: list[str], output_folder: Union[Path, str]
) -> str:
    """Extracts the drag curve from the data and saves it to a csv file."""

    altitude_vector = __collect_altitude_vector(datapoints, data_labels)
    logger.info("Collected altitude vector")

    datapoints = __remove_data_after_apogee(datapoints, altitude_vector)
    logger.info("Removed data after apogee")

    cd = __extract_drag_and_mach(datapoints, data_labels)
    logger.info("Collected drag coefficient and Mach number")

    cd = __process_drag_data(cd)
    logger.info("Successfully created the drag curve")

    return __save_to_csv(cd, output_folder)
