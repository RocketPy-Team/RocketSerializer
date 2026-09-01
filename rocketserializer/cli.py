import json
import logging
import os
from pathlib import Path

import click

from ._helpers import extract_ork_from_zip, parse_ork_file
from .nb_builder import NotebookBuilder
from .openrocket_runtime import OpenRocketSession, select_latest_openrocket_jar
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
@click.option(
    "--eng",
    type=click.Path(),
    default=None,
    required=False,
    help="A RASP .eng thrust file to use when the .ork has no simulation.",
)
@click.option(
    "--no-jvm",
    is_flag=True,
    default=False,
    help="Never start the OpenRocket JVM: positions, drag, thrust and mass "
    "are computed from the XML/geometry (and .eng files) alone.",
)
@click.option(
    "--no-sim-data",
    is_flag=True,
    default=False,
    help="Ignore any simulation data stored in the file: drag, thrust and "
    "mass are always computed from the geometry, .eng files and the mass "
    "model (implies --no-jvm). Stored results are kept as a cross-check.",
)
@click.option("--verbose", is_flag=True, default=False, help="Enable verbose logging")
def ork2json(
    filepath,
    output=None,
    ork_jar=None,
    encoding="utf-8",
    eng=None,
    no_jvm=False,
    no_sim_data=False,
    verbose=False,
):
    """Generates a .json file from the .ork file.
    The .json file will be generated in the output folder using the information
    of the .ork file.

    Files without simulation data (or runs with --no-jvm) are handled without
    OpenRocket: the drag curve is computed from the geometry, the thrust curve
    comes from a bundled .eng file (verified against the design's motor
    digest) or the motor database export, and the rocket's mass, center of
    mass and inertia come from the built-in structure mass model.  Non-English
    files are supported for OpenRocket 22.02/23.09/24.12 (the simulation
    column labels are resolved positionally).

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
    eng : str, optional
        Path to a RASP .eng file for the no-simulation thrust source.
    no_jvm : bool, optional
        Force the JVM-free path even when simulation data is present.
    verbose : bool, optional
        If True, the log level will be set to DEBUG. Default is False.

    Raises
    ------
    ValueError
        In case the simulation columns cannot be resolved (unknown OpenRocket
        version saved in a non-English language).
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
    has_simulation = len(datapoints) > 0 and not no_sim_data

    if has_simulation:
        # parse_ork_file already remapped non-English labels positionally for
        # known OpenRocket versions; this residual guard fires only for
        # unknown versions saved in a non-English language
        data_labels = bs.find("databranch").attrs["types"].split(",")
        if "CG location" not in data_labels:
            message = (
                "[ork2json] Could not resolve the simulation data columns.\n"
                "The file's column labels are not in English and its "
                "OpenRocket version's column order is unknown (supported: "
                "22.02, 23.09, 24.12).\n"
                "Please open the file in OpenRocket, change the language to "
                "English (Edit > Preferences > General > Language), re-run "
                "the simulation, and save again."
            )
            logger.error(message)
            raise ValueError(message)
    else:
        logger.warning(
            "[ork2json] Simulation data %s. Using the JVM-free path: "
            "geometry drag, .eng thrust and the built-in mass model.",
            "ignored (--no-sim-data)" if no_sim_data else "not present",
        )

    use_jvm = has_simulation and not no_jvm
    if use_jvm:
        if not ork_jar:
            ork_jar = select_latest_openrocket_jar(Path.cwd())
            logger.info(
                "[ork2json] Found OpenRocket .jar file: '%s'", ork_jar.as_posix()
            )
        else:
            ork_jar = Path(ork_jar)

        if not ork_jar.exists():
            raise FileNotFoundError(
                "[ork2json] The specified OpenRocket .jar file does not exist: "
                f"'{ork_jar.as_posix()}'"
            )

    if not output:
        # get the same folder as the .ork file
        output = os.path.dirname(filepath)
        logger.warning(
            "[ork2json] Output folder not specified. Using '%s' instead.",
            Path(output).as_posix(),
        )

    # create the output folder (including parents) if it does not exist
    Path(output).mkdir(parents=True, exist_ok=True)

    if use_jvm:
        with OpenRocketSession(ork_jar, log_level="OFF") as instance:
            ork = instance.load_doc(str(filepath))
            settings = ork_extractor(
                bs=bs,
                filepath=str(filepath),
                output_folder=output,
                ork=ork,
                eng=eng,
            )
    else:
        settings = ork_extractor(
            bs=bs,
            filepath=str(filepath),
            output_folder=output,
            ork=None,
            eng=eng,
            use_simulation=not no_sim_data,
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
@click.option("--eng", type=click.Path(), default=None, required=False)
@click.option("--no-jvm", is_flag=True, default=False)
@click.option("--no-sim-data", is_flag=True, default=False)
@click.option("--verbose", is_flag=True, default=False, help="Enable verbose logging")
def ork2notebook(
    filepath,
    output,
    ork_jar=None,
    encoding="utf-8",
    eng=None,
    no_jvm=False,
    no_sim_data=False,
    verbose=False,
):  # pylint: disable=unused-argument
    """Generates a .ipynb file from the .ork file.

    Notes
    -----
    Under the hood, this function uses the `ork2json` function to generate the
    parameters.json file and then uses the `NotebookBuilder` class to generate
    the .ipynb file.
    """
    if not output:
        filepath = Path(filepath)
        output = filepath.parent
        logger.warning(
            "[ork2notebook] Output folder not specified. Using '%s' instead.",
            Path(output).as_posix(),
        )
    args = [
        "--filepath",
        str(filepath),
        "--output",
        str(output),
        "--encoding",
        str(encoding),
    ]
    if verbose:
        args.append("--verbose")
    if ork_jar:
        args.extend(["--ork_jar", str(ork_jar)])
    if eng:
        args.extend(["--eng", str(eng)])
    if no_jvm:
        args.append("--no-jvm")
    if no_sim_data:
        args.append("--no-sim-data")

    ork2json(args, standalone_mode=False)

    instance = NotebookBuilder(parameters_json=os.path.join(output, "parameters.json"))
    instance.build(destination=output)


@cli.command("ork2dragcurve")
@click.option(
    "--filepath", type=click.Path(), required=True, help="The path to the .ork file."
)
@click.option(
    "--output", type=click.Path(), required=False, help="The path to the output folder."
)
@click.option(
    "--mach-max", type=float, default=3.0, help="Maximum Mach number of the curve."
)
@click.option("--verbose", is_flag=True, default=False, help="Enable verbose logging")
def ork2dragcurve(filepath, output=None, mach_max=3.0, verbose=False):
    """Computes the OpenRocket drag curve from the .ork design alone.

    Reimplements OpenRocket 24.12's zero-lift drag build-up in pure Python --
    no Java and no saved simulation are needed.  Writes ``drag_curve.csv``
    (Mach, Cd at zero angle of attack, sea-level ISA Reynolds) to the output
    folder.

    Notes
    -----
    Unlike ``ork2json``'s drag curve, which reads the simulation datapoints
    stored in the file, this command evaluates the drag model directly from
    the geometry, so it also works for .ork files without any simulation run.
    """
    # local import: keeps the JVM-dependent commands untouched
    # pylint: disable=import-outside-toplevel
    import numpy as np

    from .dragmodel import DragBuildup, load_rocket

    if verbose:
        logger.setLevel(logging.DEBUG)

    filepath = Path(filepath)
    if not output:
        output = filepath.parent
        logger.warning(
            "[ork2dragcurve] Output folder not specified. Using '%s' instead.",
            Path(output).as_posix(),
        )
    rocket = load_rocket(filepath)
    buildup = DragBuildup(rocket)
    machs = [round(0.01 * i, 2) for i in range(1, int(mach_max * 100) + 1)]
    machs, cds = buildup.drag_curve(machs)
    path = os.path.join(output, "drag_curve.csv")
    np.savetxt(path, np.array([machs, cds]).T, delimiter=",", fmt="%.6f")
    logger.info(
        "[ork2dragcurve] Drag curve of '%s' saved to '%s'.",
        rocket.name,
        Path(path).as_posix(),
    )
    print(f"[ork2dragcurve] Success! Drag curve saved to {Path(path).as_posix()}")
