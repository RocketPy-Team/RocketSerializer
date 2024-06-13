from rocketserializer.cli import ork2json

# NOTE: Only works if you comment the decorators in the ork2json function.
# NOTE: use this to run the python debugger
# NOTE: restart the jupyter kernel if needed, so JVEM can restart

ork2json(
    "examples/databank/Team24/rocket.ork",
)
