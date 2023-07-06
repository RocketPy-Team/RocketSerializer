from setuptools import setup

setup(
    name="rocket-serializer",
    version="0.0.1",
    packages=["open_rocket_serializer", "open_rocket_serializer.components"],
    include_package_data=True,
    install_requires=["bs4", "click", "lxml", "numpy", "orhelper", "pyyaml"],
    entry_points="""
        [console_scripts]
        serializer=open_rocket_serializer.cli:cli
    """,
)
