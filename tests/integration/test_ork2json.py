import pytest
from click.testing import CliRunner
from rocketserializer.cli import cli

@pytest.fixture
def runner():
    return CliRunner()

def test_ork2json(runner):
    result = runner.invoke(cli, [
        'ork2json',
        '--filepath', 'examples/ProjetoJupiter--Valetudo--2019/rocket.ork',
        '--output', 'examples/ProjetoJupiter--Valetudo--2019/rocket.json',
        '--eng', 'eng',
        '--ork_jar', 'tests/OpenRocket-15.03.jar',
        '--encoding', 'utf-8',
        '--verbose', False
    ])
    assert result.exit_code == 0

# @pytest.mark.parametrize(
#     "filepath, output, eng, ork_jar, encoding, verbose",
#     [
#         (
#             "examples/ProjetoJupiter--Valetudo--2019/rocket.ork",
#             "examples/ProjetoJupiter--Valetudo--2019/rocket.json",
#             "eng",
#             "tests/OpenRocket-15.03.jar",
#             "utf-8",
#             False,
#         ),
#         (
#             "examples/NDRT--Rocket--2020/rocket.ork",
#             "examples/NDRT--Rocket--2020/rocket.json",
#             "eng",
#             "tests/OpenRocket-15.03.jar",
#             "utf-8",
#             False,
#         ),
#         (
#             "examples/EPFL--BellaLui--2020/rocket.ork",
#             "examples/EPFL--BellaLui--2020/rocket.json",
#             "eng",
#             "tests/OpenRocket-15.03.jar",
#             "utf-8",
#             False,
#         ),
#     ],
# )
# def test_ork2json_parametrized(runner, filepath, output, eng, ork_jar, encoding, verbose):
#     result = runner.invoke(cli, [
#         'ork2json',
#         '--filepath', filepath,
#         '--output', output,
#         '--eng', eng,
#         '--ork_jar', ork_jar,
#         '--encoding', encoding,
#         '--verbose', verbose
#     ])
#     assert result.exit_code == 0
