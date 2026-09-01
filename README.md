<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./static/LogoWhiteonTransparentBG-ByRocketeersForRocketeers.png">
  <source media="(prefers-color-scheme: light)" srcset="./static/LogoBlackonTransparentBG-ByRocketeersForRocketeers.png">
  <img alt="RocketPy Logo" src="https://raw.githubusercontent.com/RocketPy-Team/RocketPy/master/docs/static/RocketPy_Logo_black.png">
</picture>

<br>

[![Documentation Status](https://readthedocs.org/projects/rocketpyalpha/badge/?version=latest)](https://docs.rocketpy.org/en/latest/?badge=latest)
[![Chat on Discord](https://img.shields.io/discord/765037887016140840?logo=discord)](https://discord.gg/b6xYnNh)
[![Sponsor RocketPy](https://img.shields.io/static/v1?label=Sponsor&message=%E2%9D%A4&logo=GitHub&color=%23fe8e86)](https://github.com/sponsors/RocketPy-Team)
[![Instagram](https://img.shields.io/badge/Instagram-E4405F?style=flat&logo=instagram&logoColor=white)](https://www.instagram.com/rocketpyteam)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=flat&logo=linkedin&logoColor=white)](https://www.linkedin.com/company/rocketpy)

<br>

# Rocket Serializer

`rocketserializer` is a Python library that provides serialization capabilities
for OpenRocket files. It allows you to read OpenRocket files (.ork) using a
simple and intuitive command line interface. After serializing the file, you
can use the data to create your RocketPy simulation.

## Example

<img src="./static/demo_2.gif" width="100%" />

## Installation

You can install `rocketserializer` using pip:

```shell
pip install rocketserializer
```

## Requirements

### Java

You need Java to be installed on your system to use `rocketserializer`.
We recommend downloading Java 17, which is required to run recent OpenRocket
JARs (for example OpenRocket-24.12).

https://www.oracle.com/java/technologies/downloads/

### OpenRocket

You also need to download the OpenRocket JAR file. You can download it from the
following link:

https://openrocket.info/downloads.html

Each version of OpenRocket has its own jar file, and it is important to use the
correct java version to run the jar file.

### Python Packages

Once you download the `rocketserializer` package, the following dependencies
will be automatically installed:

- bs4
- click>=8.0.0
- lxml
- numpy
- jpype1<1.5
- pyyaml
- rocketpy>=1.1.0
- nbformat>=5.2.0

## Usage - command line interface

The `rocketserializer` package will automatically install 2 command-line-interface (cli)
options, here's an example:

### Serialization

To create a `parameters.json` file from an OpenRocket file, use the following command:

```bash
ork2json --filepath your_rocket.ork
```

Or, for a more verbose output, you can use the following command:

```bash
ork2json --filepath your_rocket.ork --verbose True
```

The options are the following:

- `--filepath`: The .ork file to be serialized.
- `--output` : Path to the output folder. If not set, the output will be saved in the same folder as the `filepath`.
- `--ork_jar` : Specify the path to the OpenRocket jar file. If not set, the library will use the newest `OpenRocket*.jar` found in the current directory.
- `--encoding` : The encoding of the .ork file. By default, it is set to `utf-8`.
- `--verbose` : If you want to see the progress of the serialization, set this option to True. By default, it is set to False.

Only  the `--filepath` option is mandatory.

### Creating a simulation notebook

```bash
ork2notebook --filepath your_rocket.ork
```

The options are pretty much the same as the serialization command!

### Computing the drag curve without OpenRocket (no Java, no simulation)

```bash
ork2dragcurve --filepath your_rocket.ork
```

Writes `drag_curve.csv` (Mach, Cd) computed by a pure-Python re-implementation
of OpenRocket 24.12's zero-lift drag build-up (`rocketserializer.dragmodel`).
Unlike `ork2json`'s drag curve, it does not read simulation datapoints from
the file — it evaluates the drag model directly from the geometry, so it works
for `.ork` files saved in any language and **without any simulation run**.
The model reproduces OpenRocket's stored `Drag coefficient`,
`Friction/Pressure/Base drag coefficient` and `Axial drag coefficient`
columns to within their serialized precision for every up-to-date simulation
of every 22.02/23.09/24.12 file it has been tested against.

### Serializing without a simulation (and without Java)

`ork2json` no longer requires a saved simulation or an English-language file:

- **Files without simulation data** are handled automatically with no JVM:
  the drag curve is computed from the geometry (`rocketserializer.dragmodel`),
  the thrust curve comes from a bundled `.eng` file found next to the `.ork`
  (verified against the design's motor `<digest>`) or from the pre-exported
  OpenRocket motor database (`rocketserializer/data/openrocket_motors.json.gz`,
  1418 commercial motors), and the rocket's mass, center of mass and inertia
  come from a pure-Python port of OpenRocket's mass model
  (`rocketserializer.massmodel`).
- **Non-English files** (OpenRocket 22.02 / 23.09 / 24.12) work through the
  normal simulation path: the localized simulation column labels are resolved
  positionally, since OpenRocket's column order is fixed per version.
- `--no-jvm` forces the JVM-free path even when a simulation is present;
  `--eng path/to/motor.eng` pins the thrust source explicitly.

### Limitations

- Serial multi-stage designs are supported for mass/drag; pods, boosters and
  motor clusters are not.
- Only a single motor (the default flight configuration) is serialized.
- Component *presets* (e.g. manufacturer parachutes) are not resolved; their
  packed dimensions fall back to the stored values.
- If the design's motor is custom, has no bundled `.eng`, and no simulation
  was run, the output has `"thrust_source": null`.

## Roadmap

- 2024 June : First public release, start receiving feedback from the community.

Before the first public release, we will listen to the community's feedback before defining the roadmap for the next releases.

## Contact

If you find any bug or if you want to request new features, please open an issue
on GitHub.
In case you don't have a GitHub account, you can reach out to us on RocketPy's
Discord server.

## How to Contribute

The 3 main ways of contributing to this project are:

1. **Reporting bugs and suggesting new features.**
    - Use GitHub, preferably, to report bugs and suggest new features.
    - In case you don't have a GitHub account, you can reach out to us on RocketPy's Discord server
2. **Sharing .ork files that can be used to test the library.**
    - If you have a .ork file that is not working with the library, please share it with us.
    - If you have a .ork file that is working with the library, please share it with us.
    - If you allow us to use and share your .ork file, we can add it to the test suite.
3. **Developing new features and fixing bugs thorough pull requests on GitHub.**
    - If you want to develop new features, you are more than welcome to do so.
    - Please reach out to the maintainers to discuss the new feature before starting the development.
