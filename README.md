# Rocket Serializer

Rocket Serializer is a Python library that provides serialization capabilities
for OpenRocket files. It allows you to read OpenRocket files using a simple and
intuitive command line interface.

## Installation

You can install Rocket Serializer using pip:

```shell
pip install rocket-serializer
```

## Requirements

### Java

You need Java to be installed on your system to use Rocket Serializer.
We recommend downloading Java 17, which is required to run OpenRocket-23.09.

https://www.oracle.com/java/technologies/downloads/

### OpenRocket

You also need to download the OpenRocket JAR file. You can download it from the
following link:

https://openrocket.info/downloads.html?vers=23.09#content-JAR

Each version of OpenRocket has its own jar file, and it is important to use the
correct java version to run the jar file.

### Python Packages

Once you download the package `rocket-serializer`, the following dependencies
will be automatically installed:

- bs4
- click
- lxml
- numpy
- orhelper
- pyyaml
- rocketpy
- nbformat

## Usage - command line interface

To use Rocket Serializer, you just need to use the cli option of the library.
Here's an example:

```bash
rocket-serializer ork2json --filepath path/to/input.ork --output path/to/output
```

The options are the following:

- `--filepath`: The .ork file to be serialized.
- `--output` : Path to the output folder. If not set, the output will be saved in the same folder os the filepath.
- `--eng` : Path to the engine file. If not set, the library will get the thrust curve from the OpenRocket file.
- `--ork_jar` : Specify the path to the OpenRocket jar file. If not set, the library will try to find the jar file in the current directory.
- `--verbose` : If you want to see the progress of the serialization, set this option to True. By default, it is set to False.

### Limitations

This code won't work for your rocket if it has any of the following features:

- Your file wasn't saved in English
- Your file doesn't contain simulation data
- Your rocket has more than one stage
- Your rocket has more than one engine
- Your rocket has more than one nosecone

### Deserialization

Still to be done.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.

## Contact

For any inquiries or feedback, please email us at [rocketpyteam@gmail.com](mailto:rocketpyteam@gmail.com).
If you find any bug or if you want to request new features, please open an issue
on GitHub.

## Contributors

This project is maintained by the RocketPy Team, a group of students and
software developers from all over the world.. The main contributors to this
project are:

- Patrick Sampaio Brandão
- Franz Masatoshi Yuri
- Guilherme Fernandes Alves

## How to Contribute

The 3 main ways of contributing to this project are:

1. Reporting bugs and suggesting new features by opening issues on GitHub.
2. Submitting .ork files that can be used to test the library.
3. Developing new features and fixing bugs by opening pull requests on GitHub.

## More Information

For more information, please visit the [RocketPy Team GitHub repository](https://github.com/RocketPy-Team/OpenRocketSerializer).