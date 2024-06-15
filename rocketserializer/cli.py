import json
import logging
import os
from pathlib import Path

import click
import orhelper

from ._helpers import extract_ork_from_zip, parse_ork_file
from .nb_builder import NotebookBuilder
from .ork_extractor import ork_extractor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y.%b.%d %H:%M:%S",
    filename="serializer.log",
    filemode="w",
)
logger = logging.getLogger(__name__)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console.setFormatter(formatter)
logger.addHandler(console)


@click.group()
@click.version_option()
def cli():
    """RocketSerializer.
    This library has as objective to convert .ork files into parameters.json, so
    that they can be used in rocketpy simulations. It also provides the option
    to convert the parameters.json file into a .ipynb file, so that the user can
    run the simulation using Jupyter Notebooks.

    Examples
    --------
    To easily use the library, you can use the command line interface. For
    example, to generate a .json file from a .ork file, you can use the
    following command on your terminal:
    >>> ork2json("rocket.ork", "rocket", "motor.eng")

    If you want to use the library with Python, you can import the library and
    use the functions directly. For example, to generate a .json file from a
    .ork file, you can use the following code:

    >>> from rocketserializer import ork2json
    >>> ork2json([ "--filepath", "rocket.ork", "--eng", "motor.eng"])

    If you want to convert a .ork file to a Jupyter Notebook, you can use the
    following command on your terminal:

    >>> ork2notebook("rocket.ork", "rocket", "motor.eng")
    """


@cli.command("ork2json")
@click.option(
    "--filepath", type=click.Path(), required=True, help="The path to the .ork file."
)
@click.option(
    "--output", type=click.Path(), required=False, help="The path to the output folder."
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
def ork2json(filepath, output=None, ork_jar=None, encoding="utf-8", verbose=False):
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
    ork_jar : str, optional
        The path to the OpenRocket .jar file. If unspecified, the .jar file
        will be searched in the current directory.
    encoding : str, optional
        The encoding of the .json file. Default is 'utf-8'.
    verbose : bool, optional
        If True, the log level will be set to DEBUG. Default is False.

    Raises
    ------
    ValueError
        In case the .ork file does not contain the simulation data.
    ValueError
        In case the .ork file is not in English.
    """
    log_level = logging.DEBUG if verbose else logging.WARNING
    logger.setLevel(log_level)

    filepath = Path(filepath)

    if not filepath.exists():
        error = (
            "[ork2json] The .ork file or zip archive does not exist. "
            "Please specify a valid path."
        )
        logger.error(error)
        raise FileNotFoundError(error)

    if filepath.suffix.lower() == ".ork":
        extract_dir = filepath.parent
        filepath = extract_ork_from_zip(filepath, extract_dir)
        logger.info("[ork2json] Extracted .ork file to: %s", filepath.as_posix())

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
                "[ork2json] It was not possible to find the OpenRocket .jar file in "
                "the current directory. Please specify the path to the .jar file."
            )
        ork_jar = ork_jar[0]
        logger.info(
            "[ork2json] Found OpenRocket .jar file: '%s'", Path(ork_jar).as_posix()
        )

    if not output:
        # get the same folder as the .ork file
        output = os.path.dirname(filepath)
        logger.warning(
            "[ork2json] Output folder not specified. Using '%s' instead.",
            Path(output).as_posix(),
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
        )

        with open(
            os.path.join(output, "parameters.json"), "w", encoding=encoding
        ) as convert_file:
            convert_file.write(
                json.dumps(settings, indent=4, sort_keys=True, ensure_ascii=False)
            )
            logger.info(
                "[ork2json] The file 'parameters.json' was saved to: '%s'",
                Path(output).as_posix(),
            )
            logger.info(
                "[ork2json] Operation completed successfully. You can now use "
                "the 'parameters.json' file to run a simulation."
            )


@cli.command("ork2notebook")
@click.option("--filepath", type=str, required=True)
@click.option("--output", type=str, required=False)
@click.option("--ork_jar", type=str, default=None, required=False)
@click.option("--encoding", type=str, default="utf-8", required=False)
@click.option("--verbose", type=bool, default=False, required=False)
def ork2notebook(filepath, output, ork_jar=None, encoding="utf-8", verbose=False):
    """Generates a .ipynb file from the .ork file.

    Notes
    -----
    Under the hood, this function uses the `ork2json` function to generate the
    parameters.json file and then uses the `NotebookBuilder` class to generate
    the .ipynb file.
    """
    if not output:
        output = os.path.dirname(filepath)
        logger.warning(
            "[ork2notebook] Output folder not specified. Using '%s' instead.",
            Path(output).as_posix(),
        )
    ork2json(
        [
            "--filepath",
            filepath,
            "--output",
            output,
            "--ork_jar",
            ork_jar,
            "--encoding",
            encoding,
            "--verbose",
            verbose,
        ],
        standalone_mode=False,
    )

    instance = NotebookBuilder(parameters_json=os.path.join(output, "parameters.json"))
    instance.build(destination=output)
