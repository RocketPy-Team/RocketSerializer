import numpy as np
import yaml


def search_parachute(bs):
    chute_parameters = {}

    def search_cd_chute_if_auto(bs):
        return float(
            next(
                filter(lambda x: x.text.replace(".", "").isnumeric(), bs.findAll("cd"))
            ).text
        )

    chutes = bs.findAll("parachute")
    print(f"[AddParachutes]- {len(chutes)} detected")

    for idx, main_chute in enumerate(
        filter(lambda x: "Main" in x.find("name").text, chutes)
    ):
        main_cds = (
            "auto"
            if "auto" in main_chute.find("cd").text
            else float(main_chute.find("cd").text)
        )
        main_deploy_delay = float(main_chute.find("deploydelay").text)
        main_deploy_altitude = float(main_chute.find("deployaltitude").text)
        main_area = np.pi * float(main_chute.find("diameter").text) ** 2 / 4
        main_parameter = {
            f"MainCds{idx}": main_cds * main_area,
            f"MainDeployDelay{idx}": main_deploy_delay,
            f"MainDeployAltitude{idx}": main_deploy_altitude,
        }
        print(
            f"[AddParachute][Main][{idx}] Configuration: \n{yaml.dump(main_parameter, default_flow_style=False)}"
        )
        chute_parameters.update(main_parameter)

    for idx, drogue in enumerate(
        filter(lambda x: "Drogue" in x.find("name").text, chutes)
    ):
        drogue_cds = (
            search_cd_chute_if_auto(bs)
            if drogue.find("cd").text == "auto"
            else float(drogue.find("cd").text)
        )
        drogue_deploy_delay = float(drogue.find("deploydelay").text)
        drogue_area = np.pi * float(drogue.find("diameter").text) ** 2 / 4
        drogue_parameter = {
            f"DrogueCds{idx}": drogue_area * drogue_cds,
            f"DrogueDeployDelay{idx}": drogue_deploy_delay,
        }
        chute_parameters.update(drogue_parameter)
        print(
            f"[AddParachute][Drogue][{idx}] Configuration: \n{yaml.dump(drogue_parameter, default_flow_style=False)}"
        )

    return chute_parameters
