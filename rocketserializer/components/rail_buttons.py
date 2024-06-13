import logging

logger = logging.getLogger(__name__)


def search_rail_buttons(bs, elements: dict) -> dict:

    lugs_elements = []
    for value in elements.values():
        if value["type"] in ["LaunchLug", "RailButton"]:
            lugs_elements.append(value)

    if len(lugs_elements) < 2 or not lugs_elements:
        logger.info("Could not fetch a pair of rail buttons")
        return {}

    lugs_elements.sort(key=lambda x: x["position"])
    # We only need the 2 buttons closest to the nozzle.
    lugs_elements = lugs_elements[-2:]

    upper_position = lugs_elements[0]["position"]
    lower_position = lugs_elements[1]["position"]
    name = str(lugs_elements[0]["name"])

    angular_position = 0.0
    lugs = bs.findAll("launchlug")
    for lug in lugs:
        if lug.find("name").text == name:
            angular_position = float(lug.find("radialdirection").text)
            break

    return {
        "name": str(name),
        "upper_position": upper_position,
        "lower_position": lower_position,
        "distance": lower_position - upper_position,
        "angular_position": angular_position,
    }
