import logging
import pickle
import numpy as np
import yaml

from .._helpers import _dict_to_string

logger = logging.getLogger(__name__)


def search_stored_results(bs, datapoints, data_labels, time_vector, burnout_position):
    """Search for the stored simulation results in the bs and return the
    settings as a dict.

    Parameters
    ----------
    bs : BeautifulSoup
        BeautifulSoup object of the .ork file.

    Returns
    -------
    settings : dict
        A dict containing the settings for the launch conditions. The keys are:
        "maxaltitude", "maxvelocity", "maxacceleration", "maxmach", "timetoapogee",
        "flighttime", "groundhitvelocity" and "launchrodvelocity".
    """
    settings = {}
    sim = bs.find("simulation")
    sim_data = sim.find("flightdata")
    logger.info("Found the 'flightdata' tag in the 'simulation' tag.")
    name_map = {
        "max_altitude": "maxaltitude",
        "max_velocity": "maxvelocity",
        "max_acceleration": "maxacceleration",
        "max_mach": "maxmach",
        "time_to_apogee": "timetoapogee",
        "flight_time": "flighttime",
        "ground_hit_velocity": "groundhitvelocity",
        "launch_rod_velocity": "launchrodvelocity",
    }

    for key, value in name_map.items():
        settings[key] = float(sim_data.get(value, 0))
        logger.info(f"Retrieved the '{key}' value from the .ork file: {settings[key]}")
    
    settings["final_latitude"] = __get_parameter(datapoints, data_labels, time_vector, "Latitude", position = "last")
    settings["final_longitude"] = __get_parameter(datapoints, data_labels, time_vector, "Longitude", position="last")
    settings["max_stability_margin"] = __get_parameter(datapoints, data_labels, time_vector, "Stability margin calibers", 
                                           position="max")
    settings["min_stability_margin"] = __get_parameter(datapoints, data_labels, time_vector, "Stability margin calibers", 
                                           position="min")
    settings["burnout_stability_margin"] = __get_parameter(datapoints, data_labels, time_vector, "Stability margin calibers", 
                                               position=burnout_position)
    settings["max_thrust"] = __get_parameter(datapoints, data_labels, time_vector, "Thrust", position="max")
    settings["max_mach_number"] = __get_parameter(datapoints, data_labels, time_vector, "Mach number", position="max")
    
    logger.info(
        "The flight data was successfully retrieved:\n%s",
        _dict_to_string(settings, indent=23),
    )
    return settings

def __get_parameter(datapoints, data_labels, time_vector, label, position):
    """Get the latitude and longitude from the .ork file.
    Parameters
    ----------
    label : str
        Latitude or longitude.
    datapoints : list
        List of datapoints from the .ork file.
    data_labels : list
        List of labels for the datapoints.
    time_vector : list
        The time vector of the simulation.
    position : str or int
        The position to get the value from. Can be "last", "first", "max", "min" or an integer.
    """

    parameter = [
        float(datapoint.text.split(",")[data_labels.index(label)])
        for datapoint in datapoints
    ]
    # convert to numpy array
    parameter= np.array([time_vector, parameter]).T
    # sort by time
    parameter = parameter[parameter[:, 0].argsort()]
    # clip the curve to remove negative values
    parameter[parameter[:, 1] < 0, 1] = 0
    # Assuming parameter is a NumPy array and 'NaN' values are represented as np.nan
    # This will keep rows where the second column is not NaN
    parameter = parameter[~np.isnan(parameter[:, 1])]
    
    if type(position) is str:
        match position:
            case "last":
                return parameter[-1, 1]  # return the end point (final time, final value)
            case "first":
                return parameter[0, 1] # return the first point (initial time, initial value)
            case "max":
                return np.max(parameter[:, 1]) # return the maximum value
            case "min":
                return np.min(parameter[:, 1]) # return the minimum value
    else:
        pass
    if type(position) is np.int64:
        return parameter[position, 1] # return the value at the specified position
    else:
        logger.error("Invalid position parameter")
        return "Error in position parameter"
