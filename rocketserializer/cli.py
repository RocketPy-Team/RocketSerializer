import json
import logging
import os
from pathlib import Path

import click
import orhelper
from bs4 import BeautifulSoup
from orhelper import OrLogLevel

from rocketserializer.nb_builder import NotebookBuilder

from ._helpers import extract_ork_from_zip, parse_ork_file
from .ork_extractor import ork_extractor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y.%b.%d %H:%M:%S",
    filename="serializer.log",
    filemode="w",
)
logger = logging.getLogger(__name__)

# define the logger handler for the console (useful for the command line interface)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console.setFormatter(formatter)
logger.addHandler(console)


@click.group()
@click.version_option()
def cli():
    """Rocket files Serializer.
    This library has as objective to convert .ork file into parameters
    that rocketpy is able to use for simulating the rocket. It will be generated
    a .json file which you can use with a template simulation to execute the
    simulation for your rocket.

    Examples
    --------
    To easily use the library, you can use the command line interface. For
    example, to generate a .json file from a .ork file, you can use the
    following command:
    >>> serializer ork2json("rocket.ork", "rocket", "motor.eng")

    If you want to use the library with Python, you can import the library and
    use the functions directly. For example, to generate a .json file from a
    .ork file, you can use the following code:

    >>> from rocketserializer import ork2json
    >>> ork2json("rocket.ork", "rocket", "motor.eng")

    If you want to convert a .ork file to a .py file, you can use the following
    command:

    >>> serializer ork2py("rocket.ork", "rocket", "motor.eng")

    Finally, if you want to convert a .ork file to a .ipynb file, you can use:

    >>> serializer ork2ipynb("rocket.ork", "rocket", "motor.eng")
    """


@cli.command("ork2json")
@click.option(
    "--filepath", type=click.Path(), required=True, help="The path to the .ork file."
)
@click.option(
    "--output", type=click.Path(), required=False, help="The path to the output folder."
)
@click.option(
    "--eng",
    type=str,
    default=None,
    required=False,
    help="The path to the .eng file, if necessary.",
)
@click.option(
    "--ork_jar",
    type=click.Path(),
    default=None,
    required=False,
    help="The path to the OpenRocket .jar file.",
)
@click.option("--encoding", type=str, default="utf-8", required=False)
@click.option("--verbose", type=bool, default=False, required=False)
def ork2json(
    filepath, output=None, eng=None, ork_jar=None, encoding="utf-8", verbose=False
):
    """Generates a .json file from the .ork file.
    The .json file will be generated in the output folder using the information
    of the .ork file. It is possible to specify the .eng file to extract the
    thrust curve from it. If the .eng file is not specified, the thrust curve
    will be extracted from the .ork file.

    Parameters
    ----------
    filepath : str
        The path to the .ork file.
    output : str
        The path to the output folder.
    eng : str, optional
        The path to the .eng file. If unspecified, the thrust curve will be
        extracted from the .ork file. If specified, the thrust curve will be
        extracted from the .eng file.
    ork_jar : str, optional
        The path to the OpenRocket .jar file. If unspecified, the .jar file
        will be searched in the current directory.

    Raises
    ------
    ValueError
        In case the .ork file does not contain the simulation data.
    ValueError
        In case the .ork file is not in English.

    Examples
    --------
    >>> serializer ork2json("rocket.ork", "rocket", "motor.eng")
    """
    log_level = logging.DEBUG if verbose else logging.WARNING
    logger.setLevel(log_level)

    filepath = Path(filepath)

    if not filepath.exists():
        error = "[ork2json] The .ork file or zip archive does not exist. Please specify a valid path."
        logger.error(error)
        raise FileNotFoundError(error)

    if filepath.suffix.lower() == ".ork":
        extract_dir = filepath.parent
        filepath = extract_ork_from_zip(filepath, extract_dir)
        logger.info(f"[ork2json] Extracted .ork file to: '{filepath.as_posix()}'")

    bs, datapoints = parse_ork_file(filepath)

    if len(datapoints) == 0:
        error_msg = (
            "[ork2json] The file must contain the simulation data.\n"
            + "Open the .ork file and run the simulation first."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    data_labels = bs.find("databranch").attrs["types"].split(",")
    if "CG location" not in data_labels:
        message = (
            "[ork2json] The file must contain the simulation data.\n"
            + "Open the .ork file and run the simulation first."
        )
        logger.error(message)
        raise ValueError(message)

    if not ork_jar:
        # get any .jar file in the current directory that starts with "OpenRocket"
        ork_jar = [
            f for f in os.listdir() if f.startswith("OpenRocket") and f.endswith(".jar")
        ]
        if len(ork_jar) == 0:
            raise ValueError(
                "[ork2json] It was impossible to find the OpenRocket .jar file in the current directory.\n"
                + "Please specify the path to the .jar file."
            )
        ork_jar = ork_jar[0]
        logger.info(
            f"[ork2json] Found OpenRocket .jar file: '{Path(ork_jar).as_posix()}'"
        )

    if not output:
        # get the same folder as the .ork file
        output = os.path.dirname(filepath)
        logger.warning(
            f"[ork2json] Output folder not specified. Using '{Path(output).as_posix()}' instead."
        )

    # orhelper options are: OFF, ERROR, WARN, INFO, DEBUG, TRACE and ALL
    # log_level = "OFF" if verbose else "OFF"
    # TODO: even if the log level is set to OFF, the orhelper still prints msgs

    with orhelper.OpenRocketInstance(ork_jar, log_level="OFF") as instance:
        # create the output folder if it does not exist
        if os.path.exists(output) is False:
            os.mkdir(output)

        orh = orhelper.Helper(instance)
        ork = orh.load_doc(str(filepath))

        settings = ork_extractor(
            bs=bs,
            filepath=str(filepath),
            output_folder=output,
            ork=ork,
            eng=eng,
        )

        with open(
            os.path.join(output, "parameters.json"), "w", encoding=encoding
        ) as convert_file:
            convert_file.write(
                json.dumps(settings, indent=4, sort_keys=True, ensure_ascii=False)
            )
            logger.info(
                f"[ork2json] The file 'parameters.json' was saved to: '{Path(output).as_posix()}'"
            )
            logger.info(
                f"[ork2json] Operation completed successfully. You can now use the 'parameters.json' file to run a simulation."
            )


# @cli.command("ork2py")
# @click.option("--filepath", type=str, required=True)
# @click.option("--output", type=str, required=False)
# @click.option("--eng", type=str, default=None, required=False)
# @click.option("--ork_jar", type=str, default=None, required=False)
# def ork2py(
#     filepath,
#     output,
#     eng=None,
#     ork_jar=None,
# ):
#     """Generates a .py file with rocketpy from the .ork file.

#     Parameters
#     ----------
#     filepath : _type_
#         _description_
#     output : _type_
#         _description_
#     eng : _type_, optional
#         _description_, by default None
#     ork_jar : _type_, optional
#         _description_, by default None

#     Returns
#     -------
#     _type_
#         _description_
#     """
#     get_dict = ork2json(filepath, output, eng, ork_jar)


@cli.command("ork2ipynb")
@click.option("--filepath", type=str, required=True)
@click.option("--output", type=str, required=False)
@click.option("--eng", type=str, default=None, required=False)
@click.option("--ork_jar", type=str, default=None, required=False)
def ork2ipynb(filepath, output, eng=None, ork_jar=None):
    """Generates a .ipynb file from the .ork file.

    Notes
    -----
    Under the hood, this function uses the `ork2json` function to generate the
    parameters.json file and then uses the `NotebookBuilder` class to generate
    the .ipynb file.
    """
    ork2json(
        [
            "--filepath",
            filepath,
            "--output",
            output,
            "--eng",
            eng,
            "--ork_jar",
            ork_jar,
        ],
        standalone_mode=True,
    )
    instance = NotebookBuilder(parameters_json=os.path.join(output, "parameters.json"))
    instance.build(destination=output)
