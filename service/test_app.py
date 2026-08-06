"""Tests for the HTTP wrapper.

These cover only the wrapper's own logic — envelope assembly, CSV inlining and
error classification — by stubbing the subprocess. Actually running ork2json
needs a JVM and the OpenRocket jar, which the acceptance suite already covers.
"""

import json
import subprocess

import pytest

pytest.importorskip("fastapi", reason="service extras not installed")

from fastapi.testclient import TestClient

from service import app as service_app


@pytest.fixture(name="client")
def _client():
    return TestClient(service_app.app)


def test_health_reports_version(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["serializer_version"].startswith(service_app._PKG_VERSION)


def test_read_pairs_parses_headerless_csv(tmp_path):
    csv_file = tmp_path / "thrust_source.csv"
    csv_file.write_text("0.00000,178.47000\n0.01000,535.42000\n\n")

    assert service_app._read_pairs(csv_file) == [[0.0, 178.47], [0.01, 535.42]]


@pytest.mark.parametrize(
    ("stderr", "expected"),
    [
        (
            "ValueError: The file must contain the simulation data.",
            "no_simulation_data",
        ),
        ("RocketSerializer only supports .ork files saved in English.", "non_english"),
        ("The .ork file or zip archive does not exist.", "invalid_file"),
        ("java.lang.NullPointerException", None),
    ],
)
def test_classify_maps_known_failures(stderr, expected):
    assert service_app._classify(stderr) == expected


def test_inline_csv_replaces_windows_path(tmp_path):
    (tmp_path / "thrust_source.csv").write_text("0.0,178.47\n")
    parameters = {
        "motors": {"thrust_source": "examples\\Anonymous--Mu\\thrust_source.csv"}
    }

    service_app._inline_csv(parameters, "motors", "thrust_source", tmp_path)

    assert parameters["motors"]["thrust_source"] == [[0.0, 178.47]]


def test_inline_csv_nulls_missing_file(tmp_path):
    parameters = {"rocket": {"drag_curve": "drag_curve.csv"}}

    service_app._inline_csv(parameters, "rocket", "drag_curve", tmp_path)

    assert parameters["rocket"]["drag_curve"] is None


def test_convert_inlines_csvs_and_strips_filepath(monkeypatch, client):
    def fake_run(cmd, **kwargs):
        out_dir = _output_dir(cmd)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "thrust_source.csv").write_text("0.0,178.47\n")
        (out_dir / "drag_curve.csv").write_text("0.0175,0.000053\n")
        (out_dir / "parameters.json").write_text(
            json.dumps(
                {
                    "id": {"filepath": "/tmp/ork-xyz/rocket.ork"},
                    "motors": {"thrust_source": "out\\thrust_source.csv"},
                    "rocket": {"drag_curve": "out\\drag_curve.csv"},
                    "stored_results": {"max_altitude": 3262.1},
                }
            )
        )
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(service_app.subprocess, "run", fake_run)

    body = client.post("/convert", files={"file": ("rocket.ork", b"stub")}).json()

    assert body["parameters"]["motors"]["thrust_source"] == [[0.0, 178.47]]
    assert body["parameters"]["rocket"]["drag_curve"] == [[0.0175, 0.000053]]
    assert body["parameters"]["stored_results"]["max_altitude"] == 3262.1
    assert "filepath" not in body["parameters"]["id"]


def test_convert_maps_missing_simulation_to_422(monkeypatch, client):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd, 1, stdout="", stderr="The file must contain the simulation data."
        )

    monkeypatch.setattr(service_app.subprocess, "run", fake_run)

    response = client.post("/convert", files={"file": ("rocket.ork", b"stub")})

    assert response.status_code == 422
    assert response.json()["error"] == "no_simulation_data"


def test_convert_times_out(monkeypatch, client):
    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, service_app.CONVERT_TIMEOUT_S)

    monkeypatch.setattr(service_app.subprocess, "run", fake_run)

    response = client.post("/convert", files={"file": ("rocket.ork", b"stub")})

    assert response.status_code == 504
    assert response.json()["error"] == "timeout"


def test_convert_rejects_empty_upload(client):
    response = client.post("/convert", files={"file": ("rocket.ork", b"")})

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_file"


def _output_dir(cmd):
    from pathlib import Path

    return Path(cmd[cmd.index("--output") + 1])
