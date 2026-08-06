from rocketserializer.cli import ork2json

# NOTE: Only works if you comment the decorators in the ork2json function.
# NOTE: use this to run the python debugger
# NOTE: restart the jupyter kernel if needed, so JVEM can restart

if __name__ == "__main__":
    ork2json(
        [
            "--filepath",
            "examples/ProjetoJupiter--Valetudo--2019/rocket.ork",
        ],
        standalone_mode=False,
    )
