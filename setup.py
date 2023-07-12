__author__ = "RocketPy Team"
__credits__ = [
    "Patrick Sampaio Brandão",
    "Franz Masatoshi Yuri",
    "Guilherme Fernandes Alves",
]
__license__ = "MIT"
__author_email__ = "rocketpyteam@gmail.com"
__copyright__ = "RocketPy Team, 20XX, all rights reserved."

from setuptools import setup

setup(
    name="rocket-serializer",
    version="0.0.1",
    packages=["open_rocket_serializer", "open_rocket_serializer.components"],
    include_package_data=True,
    install_requires=["bs4", "click", "lxml", "numpy", "orhelper", "pyyaml"],
    entry_points="""
        [console_scripts]
        rocket-serializer=open_rocket_serializer.cli:cli
        ork2json=open_rocket_serializer.cli:ork2json
        ork2py=open_rocket_serializer.cli:ork2py
        ork2ipynb=open_rocket_serializer.cli:ork2ipynb
    """,
    author=__author__,
    author_email=__author_email__,
    credits=__credits__,
    license=__license__,
    description="A serializer for OpenRocket files",
    homepage="https://github.com/RocketPy-Team/OpenRocketSerializer",
)
