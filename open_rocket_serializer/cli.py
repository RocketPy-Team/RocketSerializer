import json
import os

import click
import orhelper
from bs4 import BeautifulSoup
from orhelper import OrLogLevel

from .ork_extractor import ork_extractor


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

    >>> from open_rocket_serializer import ork2json
    >>> ork2json("rocket.ork", "rocket", "motor.eng")

    If you want to convert a .ork file to a .py file, you can use the following
    command:

    >>> serializer ork2py("rocket.ork", "rocket", "motor.eng")

    Finally, if you want to convert a .ork file to a .ipynb file, you can use:

    >>> serializer ork2ipynb("rocket.ork", "rocket", "motor.eng")
    """


@cli.command("ork2json")
@click.option("--filepath", type=str, required=True, help="The path to the .ork file.")
@click.option(
    "--output", type=str, required=False, help="The path to the output folder."
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
    type=str,
    default=None,
    required=False,
    help="The path to the OpenRocket .jar file.",
)
@click.option("--verbose", type=bool, default=False, required=False)
def ork2json(filepath, output=None, eng=None, ork_jar=None, verbose=False):
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

    # first check if the file exists
    if os.path.exists(filepath) is False:
        raise ValueError(
            "The .ork file does not exist.\n" + "Please specify a valid path."
        )

    try:
        bs = BeautifulSoup(open(filepath, encoding="utf-8").read(), features="xml")
    except UnicodeDecodeError:
        raise ValueError(
            "The .ork file is not in UTF-8.\n"
            + "Please open the .ork file in a text editor and save it as UTF-8."
            + "Also, you should check if your .ork file is really a xml file or "
            + "a zip file. If it is a zip file, you should unzip it first."
        )

    datapoints = bs.findAll("datapoint")

    if len(datapoints) == 0:
        raise ValueError(
            "The file must contain the simulation data.\n"
            + "Open the .ork file and run the simulation first."
        )

    data_labels = bs.find("databranch").attrs["types"].split(",")
    if "CG location" not in data_labels:
        raise ValueError(
            "The file must be in English.\n"
            + "Open the .ork file and change the language to English."
        )

    if not ork_jar:
        # get any .jar file in the current directory that starts with "OpenRocket"
        ork_jar = [
            f for f in os.listdir() if f.startswith("OpenRocket") and f.endswith(".jar")
        ]
        if len(ork_jar) == 0:
            raise ValueError(
                "It was impossible to find the OpenRocket .jar file in the current directory.\n"
                + "Please specify the path to the .jar file."
            )
        ork_jar = ork_jar[0]
        # print to the user that the .jar file was found, and show the name of the file
        if verbose:
            print(f"[ork2json] Found OpenRocket .jar file: {ork_jar}")

    if not output:
        # get the same folder as the .ork file
        output = os.path.dirname(filepath)
        if verbose:
            print(f"[ork2json] Output folder not specified. Using {output} instead.")

    # orhelper options are: OFF, ERROR, WARN, INFO, DEBUG, TRACE and ALL
    log_level = "OFF" if verbose else "OFF"
    # TODO: even if the log level is set to OFF, the orhelper still prints msgs

    with orhelper.OpenRocketInstance(ork_jar, log_level=log_level) as instance:
        # create the output folder if it does not exist
        if os.path.exists(output) is False:
            os.mkdir(output)

        orh = orhelper.Helper(instance)
        ork = orh.load_doc(filepath)

        settings = ork_extractor(
            bs=bs,
            filepath=filepath,
            output_folder=output,
            ork=ork,
            eng=eng,
            verbose=verbose,
        )

        with open(os.path.join(output, "parameters.json"), "w") as convert_file:
            convert_file.write(
                json.dumps(settings, indent=4, sort_keys=True, ensure_ascii=False)
            )
            if verbose:
                print(f"[ork2json] parameters.json file saved in {output}")

    return None


@cli.command("ork2py")
@click.option("--filepath", type=str, required=True)
@click.option("--output", type=str, required=False)
@click.option("--eng", type=str, default=None, required=False)
@click.option("--ork_jar", type=str, default=None, required=False)
def ork2py(
    filepath,
    output,
    eng=None,
    ork_jar=None,
):
    """Generates a .py file with rocketpy from the .ork file.

    Parameters
    ----------
    filepath : _type_
        _description_
    output : _type_
        _description_
    eng : _type_, optional
        _description_, by default None
    ork_jar : _type_, optional
        _description_, by default None

    Returns
    -------
    _type_
        _description_
    """
    get_dict = ork2json(filepath, output, eng, ork_jar)
    return None


@cli.command("ork2ipynb")
@click.option("--filepath", type=str, required=True)
@click.option("--output", type=str, required=False)
@click.option("--eng", type=str, default=None, required=False)
@click.option("--ork_jar", type=str, default=None, required=False)
def ork2ipynb(filepath, output, eng=None, ork_jar=None):
    get_dict = ork2json(filepath, output, eng, ork_jar)
    return None
