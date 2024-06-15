import json
import logging
import os

import nbformat as nbf

logger = logging.getLogger(__name__)


class NotebookBuilder:
    """Class that takes a parameters.json file and creates a jupyter notebook
    using rocketpy simulation on it
    """

    def __init__(self, parameters_json: str) -> None:
        """read the file and process the dictionary do not build anything yet"""
        self.parameters_json = parameters_json
        self.trapezoidal_fins_check = False
        self.elliptical_fins_check = False
        self.__extract_output_folder_from_parameters_json()
        self.read()
        self.process()

    def __extract_output_folder_from_parameters_json(self):
        self.__output_folder = os.path.dirname(self.parameters_json)

    def read(self) -> dict:
        # read the json file and return the dict and save it to self.parameters dict
        # if any problem happens here, already tell the user
        with open(self.parameters_json, "r", encoding="utf-8") as f:
            self.parameters = json.load(f)
        return self.parameters

    def process(self):
        # TODO: read the dict and search for any inconsistencies
        return self.parameters

    def build(self, destination: str):
        if os.path.isdir(destination):
            self.__output_folder = destination
        else:
            raise FileNotFoundError(
                f"Destination folder '{destination}' not found. Please create it "
                "first or verify if it is really a folder."
            )

        nb = nbf.v4.new_notebook()
        nb = self.build_header(nb)
        nb = self.build_imports(nb)
        nb = self.build_environment(nb)
        nb = self.build_motor(nb)
        nb = self.build_rocket(nb)
        nb = self.build_flight(nb)
        nb = self.build_compare_results(nb)
        self.save_notebook(nb, destination)
        logger.info(
            "[NOTEBOOK BUILDER] Notebook successfully built! You can find it at: %s",
            destination,
        )

    def build_header(self, nb: nbf.v4.new_notebook) -> nbf.v4.new_notebook:
        # create the first commentary cell
        text = "# RocketPy Simulation\n"
        text += "This notebook was generated using Rocket-Serializer, a RocketPy"
        text += " tool to convert simulation files to RocketPy simulations\n"
        text += (
            "The notebook was generated using the following parameters file: "
            + f"`{self.parameters_json}`\n"
        )

        nb["cells"] = [nbf.v4.new_markdown_cell(text)]
        logger.info("[NOTEBOOK BUILDER] Header created")
        return nb

    def build_imports(self, nb: nbf.v4.new_notebook) -> nbf.v4.new_notebook:
        # install rocketpy
        text = "%pip install rocketpy<=2.0\n"
        nb["cells"].append(nbf.v4.new_code_cell(text))

        # import classes
        text = (
            "from rocketpy import Environment, SolidMotor, Rocket, Flight, "
            + "TrapezoidalFins, EllipticalFins, RailButtons, NoseCone, Tail, " 
            + "Parachute\n"
        )
        text += "import datetime\n"
        nb["cells"].append(nbf.v4.new_code_cell(text))
        logger.info("[NOTEBOOK BUILDER] Imports section created")
        return nb

    def build_environment(self, nb: nbf.v4.new_notebook) -> nbf.v4.new_notebook:
        # add a markdown cell
        text = "## Environment\n"
        nb["cells"].append(nbf.v4.new_markdown_cell(text))

        # add a code cell
        text = "env = Environment()\n"
        text += (
            f"env.set_location(latitude={self.parameters['environment']['latitude']}, "
            + f"longitude={self.parameters['environment']['longitude']})\n"
        )
        text += f"env.set_elevation({self.parameters['environment']['elevation']})\n"
        nb["cells"].append(nbf.v4.new_code_cell(text))

        # add a markdown cell
        text = "Optionally, you can set the date and atmospheric model\n"
        nb["cells"].append(nbf.v4.new_markdown_cell(text))

        # add a code cell
        text = "tomorrow = datetime.date.today() + datetime.timedelta(days=1)\n"
        text += "env.set_date((tomorrow.year, tomorrow.month, tomorrow.day, 12))\n"
        text += "# env.set_atmospheric_model(type='Forecast', file='GFS')"
        nb["cells"].append(nbf.v4.new_code_cell(text))

        # add a code cell
        text = "env.all_info()\n"
        nb["cells"].append(nbf.v4.new_code_cell(text))

        logger.info("[NOTEBOOK BUILDER] Environment section created")
        return nb

    def build_motor(self, nb: nbf.v4.new_notebook) -> nbf.v4.new_notebook:
        # start section and give comments
        text = "## Motor\n"
        text += "Currently, only Solid Motors are supported by Rocket-Serializer. If "
        text += "you want to use a Liquid/Hybrid motor, please use rocketpy directly.\n"
        nb["cells"].append(nbf.v4.new_markdown_cell(text))

        thrust_source = self.parameters["motors"]["thrust_source"]
        thrust_source = os.path.relpath(thrust_source, self.__output_folder)

        # define the motor
        text = "motor = SolidMotor(\n"
        text += f"    thrust_source='{thrust_source}',\n"
        text += f"    dry_mass={self.parameters['motors']['dry_mass']},\n"
        text += (
            "    center_of_dry_mass_position="
            + f"{self.parameters['motors']['center_of_dry_mass_position']},\n"
        )
        text += (
            "    dry_inertia="
            + f"{'[' + str(self.parameters['motors']['dry_inertia'])[1:-1] + ']'},\n"
        )
        text += (
            "    grains_center_of_mass_position="
            + f"{self.parameters['motors']['grains_center_of_mass_position']},\n"
        )
        grain_outer_radius = self.parameters["motors"]["grain_outer_radius"]
        grain_initial_height = self.parameters["motors"]["grain_initial_height"]
        text += f"    grain_number={self.parameters['motors']['grain_number']},\n"
        text += f"    grain_density={self.parameters['motors']['grain_density']},\n"
        text += f"    grain_outer_radius={grain_outer_radius},\n"
        text += (
            "    grain_initial_inner_radius="
            + f"{self.parameters['motors']['grain_initial_inner_radius']},\n"
        )
        text += f"    grain_initial_height={grain_initial_height},\n"
        text += (
            f"    grain_separation={self.parameters['motors']['grain_separation']},\n"
        )
        text += f"    nozzle_radius={self.parameters['motors']['nozzle_radius']},\n"
        # text += f"    burn_time={self.parameters['motors']['burn_time']},\n"
        text += f"    nozzle_position={self.parameters['motors']['nozzle_position']},\n"
        text += f"    throat_radius={self.parameters['motors']['throat_radius']},\n"
        text += (
            "    reshape_thrust_curve=False,  # Not implemented in Rocket-Serializer\n"
        )
        text += "    interpolation_method='linear',\n"
        text += (
            "    coordinate_system_orientation="
            + f"'{self.parameters['motors']['coordinate_system_orientation']}',\n"
        )
        text += ")\n"
        nb["cells"].append(nbf.v4.new_code_cell(text))

        # see the outputs
        text = "motor.all_info()\n"
        nb["cells"].append(nbf.v4.new_code_cell(text))

        logger.info("[NOTEBOOK BUILDER] Motor section created")
        return nb

    def build_rocket(self, nb: nbf.v4.new_notebook):
        # add a markdown cell
        text = "## Rocket\n"
        text += (
            "Currently, only single stage rockets are supported by Rocket-Serializer\n"
        )
        text += (
            "We will start by defining the aerodynamic surfaces, "
            "and then build the rocket.\n"
        )
        nb["cells"].append(nbf.v4.new_markdown_cell(text))

        self.build_all_aerodynamic_surfaces(nb)

        drag_curve = self.parameters["rocket"]["drag_curve"]
        drag_curve = os.path.relpath(drag_curve, self.__output_folder)

        # define the Rocket
        inertia_string = "[" + str(self.parameters["rocket"]["inertia"])[1:-1] + "]"
        text = "rocket = Rocket(\n"
        text += f"    radius={self.parameters['rocket']['radius']},\n"
        text += f"    mass={self.parameters['rocket']['mass']},\n"
        text += f"    inertia={inertia_string},\n"
        text += f"    power_off_drag='{drag_curve}',\n"
        text += f"    power_on_drag='{drag_curve}',\n"
        text += (
            "    center_of_mass_without_motor="
            + f"{self.parameters['rocket']['center_of_mass_without_propellant']},\n"
        )
        text += (
            "    coordinate_system_orientation="
            + f"'{self.parameters['rocket']['coordinate_system_orientation']}',\n"
        )
        text += ")\n"
        nb["cells"].append(nbf.v4.new_code_cell(text))

        # add surfaces to rocket
        self.add_surfaces_to_rocket(nb)

        # add the motor to the rocket
        text = (
            "rocket.add_motor(motor, position= "
            + f"{self.parameters['motors']['position']})\n"
        )
        nb["cells"].append(nbf.v4.new_code_cell(text))

        # add a code cell
        text = "### Rocket Info\n"
        text += "rocket.all_info()\n"
        nb["cells"].append(nbf.v4.new_code_cell(text))

        logger.info("[NOTEBOOK BUILDER] Rocket section created")
        return nb

    def build_all_aerodynamic_surfaces(
        self, nb: nbf.v4.new_notebook
    ) -> nbf.v4.new_notebook:
        """This is simple: receive the current notebook object, start appending
        cells for each aerodynamic surface and return the notebook object"""
        self.build_nosecones(nb)
        self.build_fins(nb)
        self.build_tails(nb)
        self.build_rail_buttons(nb)
        self.build_parachute(nb)
        logger.info("[NOTEBOOK BUILDER] All aerodynamic surfaces created.")
        return nb

    def add_surfaces_to_rocket(self, nb: nbf.v4.new_notebook) -> nbf.v4.new_notebook:
        # add a markdown cell
        text = "### Adding surfaces to the rocket\n"
        text += "Now that we have all the surfaces, we can add them to the rocket\n"
        nb["cells"].append(nbf.v4.new_markdown_cell(text))
        text = "rocket.add_surfaces("

        # building surfaces and positions text
        surface_text = "surfaces=["
        position_text = "positions=["

        # adding nosecone
        surface_text += "nosecone, "
        position_text += f"{self.parameters['nosecones']['position']}, "

        # checking and adding fins
        # trapezoidal fins
        if self.trapezoidal_fins_check:
            for i in range(len(self.parameters["trapezoidal_fins"])):
                surface_text += f"trapezoidal_fins[{i}], "
                position_text += (
                    f"{self.parameters['trapezoidal_fins'][str(i)]['position']}, "
                )
        # elliptical fins
        if self.elliptical_fins_check:
            for i in range(len(self.parameters["elliptical_fins"])):
                surface_text += f"elliptical_fins[{i}], "
                position_text += (
                    f"{self.parameters['elliptical_fins'][str(i)]['position']}, "
                )
        # free form fins

        # adding tails
        for i in range(len(self.parameters["tails"])):
            surface_text += f"tails[{i}], "
            position_text += f"{self.parameters['tails'][str(i)]['position']}, "

        # closing surfaces and positions text
        surface_text = surface_text[:-2] + "]"
        position_text = position_text[:-2] + "]"
        text += surface_text + ", " + position_text + ")"
        nb["cells"].append(nbf.v4.new_code_cell(text))
        return nb

    def build_nosecones(self, nb: nbf.v4.new_notebook) -> nbf.v4.new_notebook:
        """Generates a section defining the nosecone and returns the notebook."""
        # add a markdown cell
        text = "### Nosecones\n"
        nb["cells"].append(nbf.v4.new_markdown_cell(text))

        # Assumption: only a single nosecone to be added
        text = "nosecone = NoseCone(\n"
        text += f"    length={self.parameters['nosecones']['length']},\n"
        text += f"    kind='{self.parameters['nosecones']['kind']}',\n"
        text += f"    base_radius={self.parameters['rocket']['radius']},\n"
        text += f"    rocket_radius={self.parameters['rocket']['radius']},\n"
        text += (
            f"    name='{self.parameters['nosecones']['length']}',\n"  # TODO: fix this
        )
        text += ")\n"
        nb["cells"].append(nbf.v4.new_code_cell(text))

        logger.info("[NOTEBOOK BUILDER] Nosecone created.")
        return nb

    def build_fins(self, nb: nbf.v4.new_notebook) -> nbf.v4.new_notebook:
        # add a markdown cell
        text = "### Fins\n"
        text += "As rocketpy allows for multiple fins sets, we will create a "
        text += "dictionary with all the fins sets and then add them to the rocket\n"
        nb["cells"].append(nbf.v4.new_markdown_cell(text))

        fin_counter = 0  # count the number of fins
        # trapezoidal fins
        # add a code cell
        if len(self.parameters["trapezoidal_fins"]) > 0:
            self.trapezoidal_fins_check = True
            fin_counter = len(self.parameters["trapezoidal_fins"])
            text = "trapezoidal_fins = {}\n"
            nb["cells"].append(nbf.v4.new_code_cell(text))
            for i in range(len(self.parameters["trapezoidal_fins"])):

                trapezoidal_fins_i = self.parameters["trapezoidal_fins"][str(i)]

                number = trapezoidal_fins_i["number"]
                tip_chord = trapezoidal_fins_i["tip_chord"]
                root_chord = trapezoidal_fins_i["root_chord"]
                span = trapezoidal_fins_i["span"]
                cant_angle = trapezoidal_fins_i["cant_angle"]
                sweep_length = trapezoidal_fins_i["sweep_length"]
                sweep_angle = trapezoidal_fins_i["sweep_angle"]
                radius = self.parameters["rocket"]["radius"]
                name = trapezoidal_fins_i["name"]

                text = f"trapezoidal_fins[{i}] = TrapezoidalFins(\n"
                text += f"    n={number},\n"
                text += f"    root_chord={root_chord},\n"
                text += f"    tip_chord={tip_chord},\n"
                text += f"    span={span},\n"
                text += f"    cant_angle={cant_angle},\n"
                text += f"    sweep_length= {sweep_length},\n"
                text += f"    sweep_angle= {sweep_angle},\n"
                text += f"    rocket_radius={radius},\n"
                text += f"    name='{name}',\n"
                text += ")\n\n"
                nb["cells"].append(nbf.v4.new_code_cell(text))
            logger.info("[NOTEBOOK BUILDER] Trapezoidal fins created.")
        else:
            pass
        # elliptical fins
        # add a code cell
        if len(self.parameters["elliptical_fins"]) > 0:
            self.elliptical_fins_check = True
            fin_counter += len(self.parameters["elliptical_fins"])
            text = "elliptical_fins = {}\n"
            nb["cells"].append(nbf.v4.new_code_cell(text))
            for i in range(len(self.parameters["elliptical_fins"])):

                elliptical_fins_i = self.parameters["elliptical_fins"][str(i)]

                number = elliptical_fins_i["number"]
                root_chord = elliptical_fins_i["root_chord"]
                span = elliptical_fins_i["span"]
                rocket_radius = self.parameters["rocket"]["radius"]
                cant_angle = elliptical_fins_i["cant_angle"]
                name = elliptical_fins_i["name"]

                text = f"elliptical_fins[{i}] = EllipticalFins(\n"
                text += f"    n={number},\n"
                text += f"    root_chord={root_chord},\n"
                text += f"    span={span},\n"
                text += f"    rocket_radius={rocket_radius},\n"
                text += f"    cant_angle={cant_angle},\n"
                text += f"    name='{name}',\n"
                text += ")\n\n"
                nb["cells"].append(nbf.v4.new_code_cell(text))
            logger.info("[NOTEBOOK BUILDER] Elliptical fins created.")
        else:
            pass
        # free form fins
        # checking if fins were added
        try:
            assert fin_counter > 0
            logger.info(
                "[NOTEBOOK BUILDER] %s fins were added to the rocket.", fin_counter
            )
        except AssertionError:
            text = "No fins were added to the rocket. Please add at least one."
            nb["cells"].append(nbf.v4.new_code_cell(text))
            logger.warning("No fins were added to the rocket. Please add at least one.")
            raise Warning("No fins were added to the rocket. Please add at least one.")
        return nb

    def build_tails(self, nb: nbf.v4.new_notebook) -> nbf.v4.new_notebook:
        # add a markdown cell
        text = "### Transitions (Tails)\n"
        text += "As rocketpy allows for multiple tails, we will create a "
        text += "dictionary with all the tails and then add them to the rocket\n"
        nb["cells"].append(nbf.v4.new_markdown_cell(text))

        # add a code cell
        text = "tails = {}\n"
        nb["cells"].append(nbf.v4.new_code_cell(text))
        for i in range(len(self.parameters["tails"])):

            tail_i = self.parameters["tails"][str(i)]

            top_radius = tail_i["top_radius"]
            bottom_radius = tail_i["bottom_radius"]
            length = tail_i["length"]
            rocket_radius = self.parameters["rocket"]["radius"]
            name = tail_i["name"]

            text = f"tails[{i}] = Tail(\n"
            text += f"    top_radius={top_radius},\n"
            text += f"    bottom_radius={bottom_radius},\n"
            text += f"    length={length},\n"
            text += f"    rocket_radius={rocket_radius},\n"
            text += f"    name='{name}',\n"
            text += ")\n"
            nb["cells"].append(nbf.v4.new_code_cell(text))

        logger.info("[NOTEBOOK BUILDER] Tails created.")
        return nb

    def build_rail_buttons(self, nb: nbf.v4.new_notebook) -> nbf.v4.new_notebook:
        logger.info("rail buttons not implemented yet")
        return nb

    def build_parachute(self, nb: nbf.v4.new_notebook) -> nbf.v4.new_notebook:
        # add a markdown cell
        text = "### Parachutes\n"
        text += "As rocketpy allows for multiple parachutes, we will create a "
        text += "dictionary with all the parachutes and then add them to the rocket\n"
        nb["cells"].append(nbf.v4.new_markdown_cell(text))

        # add a code cell
        text = "parachutes = {}\n"
        nb["cells"].append(nbf.v4.new_code_cell(text))
        for i in range(len(self.parameters["parachutes"])):

            parachute_i = self.parameters["parachutes"][str(i)]
            cd_s = parachute_i["cd"]*parachute_i["area"]
            deploy_event = parachute_i["deploy_event"]

            # evaluating trigger
            if deploy_event == "apogee":
                trigger = "apogee"
            elif deploy_event == "altitude":
                trigger = float(parachute_i["deploy_altitude"])
            else:
                logger.warning("Invalid deploy event for parachute %d", i)
                raise ValueError("Invalid deploy event for parachute %d", i)
            # adding parameters
            name = parachute_i["name"]
            text = f"parachutes[{i}] = Parachute(\n"
            text += f"    name='{name}',\n"
            text += f"    cd_s={cd_s:.3f},\n"
            # adding trigger
            if isinstance(trigger, str):
                text += f"    trigger='{trigger}',\n"
            else:
                text += f"    trigger={trigger:.3f},\n"

            text += f"    sampling_rate=100, \n"
            text += ")\n"
            nb["cells"].append(nbf.v4.new_code_cell(text))
        
        text = "Adding parachutes to the rocket\n"
        nb["cells"].append(nbf.v4.new_markdown_cell(text))
        text = "rocket.parachutes = parachutes\n"
        nb["cells"].append(nbf.v4.new_code_cell(text))

        logger.info("[NOTEBOOK BUILDER] Parachutes created.")
        return nb

    def build_flight(self, nb: nbf.v4.new_notebook) -> nbf.v4.new_notebook:
        """Generates a section defining the flight and returns the notebook."""
        # add a markdown cell
        text = "## Flight\n"
        text += "We will now create the flight simulation. Let's go!\n"
        nb["cells"].append(nbf.v4.new_markdown_cell(text))

        # add a code cell
        text = "flight = Flight(\n"
        text += "    rocket=rocket,\n"
        text += "    environment=env,\n"
        text += f"    rail_length={self.parameters['flight']['rail_length']},\n"
        text += f"    inclination={self.parameters['flight']['inclination']},\n"
        text += f"    heading={self.parameters['flight']['heading']},\n"
        text += "    terminate_on_apogee=False,\n"
        text += "    max_time=600,\n"
        text += ")"
        nb["cells"].append(nbf.v4.new_code_cell(text))

        # add a code cell
        text = "flight.all_info()\n"
        nb["cells"].append(nbf.v4.new_code_cell(text))

        logger.info("[NOTEBOOK BUILDER] Flight section created.")
        return nb

    def build_compare_results(self, nb: nbf.v4.new_notebook) -> nbf.v4.new_notebook:
        # pylint: disable=line-too-long
        # add a markdown cell
        text = "## Compare Results\n"
        text += "We will now compare the results of the simulation with the "
        text += "parameters used to create it. Let's go!\n"
        nb["cells"].append(nbf.v4.new_markdown_cell(text))

        # add a code cell
        text = "### OpenRocket vs RocketPy Parameters\n"
        time_to_apogee = self.parameters["stored_results"]["time_to_apogee"]
        # time to apogee
        text += f"time_to_apogee_ork = {time_to_apogee}\n"
        text += "time_to_apogee_rpy = flight.apogee_time\n"
        text += r'print(f"Time to apogee (OpenRocket): {time_to_apogee_ork:.3f} s")'
        text += "\n"
        text += r'print(f"Time to apogee (RocketPy):   {time_to_apogee_rpy:.3f} s")'
        text += "\n"
        text += "apogee_difference = time_to_apogee_rpy - time_to_apogee_ork"
        text += "\n"
        text += "error = abs((apogee_difference)/time_to_apogee_rpy)*100"
        text += "\n"
        text += r'print(f"Time to apogee difference:   {error:.3f} %")'
        text += "\n\n"

        # Flight time
        flight_time_ork = self.parameters["stored_results"]["flight_time"]
        text += f"flight_time_ork = {flight_time_ork}\n"
        text += "flight_time_rpy = flight.t_final\n"
        text += r'print(f"Flight time (OpenRocket): {flight_time_ork:.3f} s")'
        text += "\n"
        text += r'print(f"Flight time (RocketPy):   {flight_time_rpy:.3f} s")'
        text += "\n"
        text += "flight_time_difference = flight_time_rpy - flight_time_ork\n"
        text += (
            "error_flight_time = abs((flight_time_difference)/flight_time_rpy)*100\n"
        )
        text += r'print(f"Flight time difference:   {error_flight_time:.3f} %")'
        text += "\n\n"

        # Ground hit velocity
        ground_hit_velocity_ork = self.parameters["stored_results"][
            "ground_hit_velocity"
        ]
        text += f"ground_hit_velocity_ork = {ground_hit_velocity_ork}\n"
        text += "ground_hit_velocity_rpy = flight.impact_velocity\n"
        text += r'print(f"Ground hit velocity (OpenRocket): {ground_hit_velocity_ork:.3f} m/s")'
        text += "\n"
        text += r'print(f"Ground hit velocity (RocketPy):   {ground_hit_velocity_rpy:.3f} m/s")'
        text += "\n"
        text += "ground_hit_velocity_difference = ground_hit_velocity_rpy - ground_hit_velocity_ork\n"
        text += "error_ground_hit_velocity = abs((ground_hit_velocity_difference)/ground_hit_velocity_rpy)*100\n"
        text += r'print(f"Ground hit velocity difference:   {error_ground_hit_velocity:.3f} %")'
        text += "\n\n"

        # Launch rod velocity
        launch_rod_velocity_ork = self.parameters["stored_results"][
            "launch_rod_velocity"
        ]
        text += f"launch_rod_velocity_ork = {launch_rod_velocity_ork}\n"
        text += "launch_rod_velocity_rpy = flight.out_of_rail_velocity\n"
        text += r'print(f"Launch rod velocity (OpenRocket): {launch_rod_velocity_ork:.3f} m/s")'
        text += "\n"
        text += r'print(f"Launch rod velocity (RocketPy):   {launch_rod_velocity_rpy:.3f} m/s")'
        text += "\n"
        text += "launch_rod_velocity_difference = launch_rod_velocity_rpy - launch_rod_velocity_ork\n"
        text += "error_launch_rod_velocity = abs((launch_rod_velocity_difference)/launch_rod_velocity_rpy)*100\n"
        text += r'print(f"Launch rod velocity difference:   {error_launch_rod_velocity:.3f} %")'
        text += "\n\n"

        # Max acceleration
        max_acceleration_ork = self.parameters["stored_results"]["max_acceleration"]
        text += f"max_acceleration_ork = {max_acceleration_ork}\n"
        text += "max_acceleration_rpy = flight.max_acceleration\n"
        text += (
            r'print(f"Max acceleration (OpenRocket): {max_acceleration_ork:.3f} m/s²")'
        )
        text += "\n"
        text += (
            r'print(f"Max acceleration (RocketPy):   {max_acceleration_rpy:.3f} m/s²")'
        )
        text += "\n"
        text += "max_acceleration_difference = max_acceleration_rpy - max_acceleration_ork\n"
        text += "error_max_acceleration = abs((max_acceleration_difference)/max_acceleration_rpy)*100\n"
        text += (
            r'print(f"Max acceleration difference:   {error_max_acceleration:.3f} %")'
        )
        text += "\n\n"

        # Max altitude
        max_altitude_ork = self.parameters["stored_results"]["max_altitude"]
        text += f"max_altitude_ork = {max_altitude_ork}\n"
        text += "max_altitude_rpy = flight.apogee - flight.env.elevation\n"
        text += r'print(f"Max altitude (OpenRocket): {max_altitude_ork:.3f} m")'
        text += "\n"
        text += r'print(f"Max altitude (RocketPy):   {max_altitude_rpy:.3f} m")'
        text += "\n"
        text += "max_altitude_difference = max_altitude_rpy - max_altitude_ork\n"
        text += (
            "error_max_altitude = abs((max_altitude_difference)/max_altitude_rpy)*100\n"
        )
        text += r'print(f"Max altitude difference:   {error_max_altitude:.3f} %")'
        text += "\n\n"

        # Max Mach
        max_mach_ork = self.parameters["stored_results"]["max_mach"]
        text += f"max_mach_ork = {max_mach_ork}\n"
        text += "max_mach_rpy = flight.max_mach_number \n"
        text += r'print(f"Max Mach (OpenRocket): {max_mach_ork:.3f}")'
        text += "\n"
        text += r'print(f"Max Mach (RocketPy):   {max_mach_rpy:.3f}")'
        text += "\n"
        text += "max_mach_difference = max_mach_rpy - max_mach_ork\n"
        text += "error_max_mach = abs((max_mach_difference)/max_mach_rpy)*100\n"
        text += r'print(f"Max Mach difference:   {error_max_mach:.3f} %")'
        text += "\n\n"

        # Max velocity
        max_velocity_ork = self.parameters["stored_results"]["max_velocity"]
        text += f"max_velocity_ork = {max_velocity_ork}\n"
        text += "max_velocity_rpy = flight.max_speed\n"
        text += r'print(f"Max velocity (OpenRocket): {max_velocity_ork:.3f} m/s")'
        text += "\n"
        text += r'print(f"Max velocity (RocketPy):   {max_velocity_rpy:.3f} m/s")'
        text += "\n"
        text += "max_velocity_difference = max_velocity_rpy - max_velocity_ork\n"
        text += (
            "error_max_velocity = abs((max_velocity_difference)/max_velocity_rpy)*100\n"
        )
        text += r'print(f"Max velocity difference:   {error_max_velocity:.3f} %")'
        text += "\n\n"

        # Max thrust
        max_thrust_ork = self.parameters["stored_results"]["max_thrust"]
        text += f"max_thrust_ork = {max_thrust_ork}\n"
        text += "max_thrust_rpy = flight.rocket.motor.thrust.max\n"
        text += r'print(f"Max thrust (OpenRocket): {max_thrust_ork:.3f} N")'
        text += "\n"
        text += r'print(f"Max thrust (RocketPy):   {max_thrust_rpy:.3f} N")'
        text += "\n"
        text += "max_thrust_difference = max_thrust_rpy - max_thrust_ork\n"
        text += "error_max_thrust = abs((max_thrust_difference)/max_thrust_rpy)*100\n"
        text += r'print(f"Max thrust difference:   {error_max_thrust:.3f} %")'
        text += "\n\n"

        # # Burnout stability margin
        burnout_stability_margin_ork = self.parameters["stored_results"][
            "burnout_stability_margin"
        ]
        text += f"burnout_stability_margin_ork = {burnout_stability_margin_ork}\n"
        text += "burnout_stability_margin_rpy = flight.stability_margin(flight.rocket.motor.burn_out_time)\n"
        text += r'print(f"Burnout stability margin (OpenRocket): {burnout_stability_margin_ork:.3f}")'
        text += "\n"
        text += r'print(f"Burnout stability margin (RocketPy):   {burnout_stability_margin_rpy:.3f}")'
        text += "\n"
        text += "burnout_stability_margin_difference = burnout_stability_margin_rpy - burnout_stability_margin_ork\n"
        text += "error_burnout_stability_margin = abs((burnout_stability_margin_difference)/burnout_stability_margin_rpy)*100\n"
        text += r'print(f"Burnout stability margin difference:   {error_burnout_stability_margin:.3f} %")'
        text += "\n\n"

        # # Max stability margin
        max_stability_margin_ork = self.parameters["stored_results"][
            "max_stability_margin"
        ]
        text += f"max_stability_margin_ork = {max_stability_margin_ork}\n"
        text += "max_stability_margin_rpy = flight.max_stability_margin\n"
        text += r'print(f"Max stability margin (OpenRocket): {max_stability_margin_ork:.3f}")'
        text += "\n"
        text += r'print(f"Max stability margin (RocketPy):   {max_stability_margin_rpy:.3f}")'
        text += "\n"
        text += "max_stability_margin_difference = max_stability_margin_rpy - max_stability_margin_ork\n"
        text += "error_max_stability_margin = abs((max_stability_margin_difference)/max_stability_margin_rpy)*100\n"
        text += r'print(f"Max stability margin difference:   {error_max_stability_margin:.3f} %")'
        text += "\n\n"

        # Min stability margin
        min_stability_margin_ork = self.parameters["stored_results"][
            "min_stability_margin"
        ]
        text += f"min_stability_margin_ork = {min_stability_margin_ork}\n"
        text += "min_stability_margin_rpy = flight.min_stability_margin\n"
        text += r'print(f"Min stability margin (OpenRocket): {min_stability_margin_ork:.3f}")'
        text += "\n"
        text += r'print(f"Min stability margin (RocketPy):   {min_stability_margin_rpy:.3f}")'
        text += "\n"
        text += "min_stability_margin_difference = min_stability_margin_rpy - min_stability_margin_ork\n"
        text += "error_min_stability_margin = abs((min_stability_margin_difference)/min_stability_margin_rpy)*100\n"
        text += r'print(f"Min stability margin difference:   {error_min_stability_margin:.3f} %")'
        text += "\n\n"

        nb["cells"].append(nbf.v4.new_code_cell(text))

        logger.info("[NOTEBOOK BUILDER] Compare Results section created.")
        return nb

    def save_notebook(self, nb: nbf.v4.new_notebook, destination: str) -> None:
        """Writes the .ipynb file to the destination folder. Also applies black
        formatting to the file to improve readability."""
        out_file = os.path.join(destination, "simulation.ipynb")

        nbf.write(nb, out_file)
        logger.info("[NOTEBOOK BUILDER] Notebook saved to '%s'", out_file)

        # apply black formatting after saving (requires black[jupyter])
        os.system(f"black {out_file}")
        logger.info("[NOTEBOOK BUILDER] Black formatting applied to the final notebook")
