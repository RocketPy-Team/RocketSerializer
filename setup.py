from setuptools import setup

setup(
    name="rocket-serializer",
    version="1.0",
    packages=["open_rocket_serializer", "open_rocket_serializer.components"],
    include_package_data=True,
    install_requires=["click"],
    entry_points="""
        [console_scripts]
        serializer=open_rocket_serializer.cli:cli
    """,
)
