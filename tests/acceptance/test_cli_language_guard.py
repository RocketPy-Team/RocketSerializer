from pathlib import Path

import pytest

from rocketserializer.cli import ork2json


def test_team15_german_file_fails_with_clear_message():
    team15_ork = Path("examples/databank/Team15/rocket.ork")

    with pytest.raises(ValueError) as exc_info:
        ork2json(
            [
                "--filepath",
                str(team15_ork),
                "--output",
                "examples/databank/Team15/rocket",
                "--verbose",
                "False",
            ],
            standalone_mode=False,
        )

    message = str(exc_info.value)
    assert "saved in German" in message
    assert "only supports .ork files saved in English" in message
