"""Unit tests for the HTTP wrapper.

These exercise the wrapper's own logic only — envelope assembly, CSV inlining,
error classification, isolation and limits — by stubbing the subprocess. They
need no JVM and no OpenRocket jar, so they run in well under a second.

Actually running ork2json is covered by the acceptance suite under ``tests/``,
which boots a real ``OpenRocketSession``.
"""

import asyncio
import json
import subprocess
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="service extras not installed")

import httpx
from fastapi.testclient import TestClient

# Patch the starlette base class, not fastapi.UploadFile: the multipart parser
# instantiates the base, so patching the subclass silently spies on nothing.
from starlette.datastructures import UploadFile

from service import app as service_app


@pytest.fixture(name="client")
def _client():
    return TestClient(service_app.app)


def _upload(payload=b"stub", filename="rocket.ork"):
    return {"file": (filename, payload)}


def _output_dir(cmd):
    return Path(cmd[cmd.index("--output") + 1])


def _stub_run(monkeypatch, *, parameters=None, csvs=None, returncode=0, stderr=""):
    """Replace subprocess.run with one that fakes an ork2json output tree.

    Records every invocation on the returned list so tests can assert on the
    command line and working directory the real CLI would have received.
    """
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append({"cmd": cmd, **kwargs})
        if returncode == 0:
            out_dir = _output_dir(cmd)
            out_dir.mkdir(parents=True, exist_ok=True)
            for name, body in (csvs or {}).items():
                (out_dir / name).write_text(body)
            if parameters is not None:
                (out_dir / "parameters.json").write_text(
                    parameters
                    if isinstance(parameters, str)
                    else json.dumps(parameters)
                )
        return subprocess.CompletedProcess(cmd, returncode, stdout="", stderr=stderr)

    monkeypatch.setattr(service_app.subprocess, "run", fake_run)
    return calls


class TestReadPairs:
    def test_parses_headerless_two_column_csv(self, tmp_path):
        csv_file = tmp_path / "thrust_source.csv"
        csv_file.write_text("0.00000,178.47000\n0.01000,535.42000\n")

        assert service_app._read_pairs(csv_file) == [[0.0, 178.47], [0.01, 535.42]]

    def test_skips_blank_and_whitespace_only_rows(self, tmp_path):
        csv_file = tmp_path / "c.csv"
        csv_file.write_text("0.0,1.0\n\n   ,2.0\n0.1,3.0\n")

        assert service_app._read_pairs(csv_file) == [[0.0, 1.0], [0.1, 3.0]]

    def test_ignores_columns_beyond_the_first_two(self, tmp_path):
        csv_file = tmp_path / "c.csv"
        csv_file.write_text("0.0,1.0,ignored\n")

        assert service_app._read_pairs(csv_file) == [[0.0, 1.0]]

    def test_empty_file_yields_no_pairs(self, tmp_path):
        csv_file = tmp_path / "c.csv"
        csv_file.write_text("")

        assert service_app._read_pairs(csv_file) == []

    def test_non_numeric_cell_raises(self, tmp_path):
        """_convert relies on this surfacing so it can answer parse_failed."""
        csv_file = tmp_path / "c.csv"
        csv_file.write_text("0.0,not-a-number\n")

        with pytest.raises(ValueError):
            service_app._read_pairs(csv_file)


class TestClassify:
    @pytest.mark.parametrize(
        ("stderr", "expected"),
        [
            (
                "ValueError: The file must contain the simulation data.",
                "no_simulation_data",
            ),
            (
                "RocketSerializer only supports .ork files saved in English.",
                "non_english",
            ),
            (
                "This usually means the file is saved in a non-English language",
                "non_english",
            ),
            ("The .ork file or zip archive does not exist.", "invalid_file"),
            ("java.lang.NullPointerException", None),
            ("", None),
        ],
    )
    def test_maps_known_failures(self, stderr, expected):
        assert service_app._classify(stderr) == expected

    def test_first_match_wins_when_several_apply(self):
        combined = (
            "The file must contain the simulation data. "
            "The .ork file or zip archive does not exist."
        )

        assert service_app._classify(combined) == "no_simulation_data"


class TestInlineCsv:
    def test_replaces_windows_style_path(self, tmp_path):
        (tmp_path / "thrust_source.csv").write_text("0.0,178.47\n")
        parameters = {
            "motors": {"thrust_source": "examples\\Anonymous--Mu\\thrust_source.csv"}
        }

        service_app._inline_csv(parameters, "motors", "thrust_source", tmp_path)

        assert parameters["motors"]["thrust_source"] == [[0.0, 178.47]]

    def test_replaces_posix_style_path(self, tmp_path):
        (tmp_path / "drag_curve.csv").write_text("0.0175,0.000053\n")
        parameters = {"rocket": {"drag_curve": "examples/Mu/drag_curve.csv"}}

        service_app._inline_csv(parameters, "rocket", "drag_curve", tmp_path)

        assert parameters["rocket"]["drag_curve"] == [[0.0175, 0.000053]]

    def test_nulls_the_key_when_csv_is_missing(self, tmp_path):
        parameters = {"rocket": {"drag_curve": "drag_curve.csv"}}

        service_app._inline_csv(parameters, "rocket", "drag_curve", tmp_path)

        assert parameters["rocket"]["drag_curve"] is None

    def test_leaves_non_string_values_untouched(self, tmp_path):
        parameters = {"motors": {"thrust_source": [[0.0, 1.0]]}}

        service_app._inline_csv(parameters, "motors", "thrust_source", tmp_path)

        assert parameters["motors"]["thrust_source"] == [[0.0, 1.0]]

    def test_tolerates_absent_section(self, tmp_path):
        parameters = {}

        service_app._inline_csv(parameters, "motors", "thrust_source", tmp_path)

        assert parameters == {}

    def test_tolerates_null_section(self, tmp_path):
        """ork_extractor's _safe_search can leave a section null rather than a dict."""
        parameters = {"motors": None}

        service_app._inline_csv(parameters, "motors", "thrust_source", tmp_path)

        assert parameters == {"motors": None}

    def test_tolerates_absent_key(self, tmp_path):
        parameters = {"motors": {"dry_mass": 0}}

        service_app._inline_csv(parameters, "motors", "thrust_source", tmp_path)

        assert parameters == {"motors": {"dry_mass": 0}}


class TestConvertSubprocessContract:
    def test_pins_the_jar_and_runs_inside_the_job_directory(self, monkeypatch):
        calls = _stub_run(monkeypatch, parameters={})

        service_app._convert(b"stub", "rocket.ork")

        cmd = calls[0]["cmd"]
        assert cmd[0] == "ork2json"
        # An unset --ork_jar would make the CLI scan cwd and pick any jar.
        assert cmd[cmd.index("--ork_jar") + 1] == str(service_app.ORK_JAR)
        # cwd contains cli.py's import-time serializer.log write.
        assert calls[0]["cwd"] == _output_dir(cmd).parent
        assert calls[0]["timeout"] == service_app.CONVERT_TIMEOUT_S
        assert calls[0]["check"] is False

    def test_discards_the_job_directory_on_success(self, monkeypatch):
        calls = _stub_run(monkeypatch, parameters={})

        service_app._convert(b"stub", "rocket.ork")

        assert not calls[0]["cwd"].exists()

    def test_discards_the_job_directory_on_failure(self, monkeypatch):
        calls = _stub_run(monkeypatch, returncode=1, stderr="boom")

        service_app._convert(b"stub", "rocket.ork")

        assert not calls[0]["cwd"].exists()

    @pytest.mark.parametrize(
        "filename",
        [
            "../../../etc/passwd",
            "/etc/passwd",
            "..",
            ".",
            "",
            "sub/dir/rocket.ork",
            "C:\\Users\\me\\rocket.ork",
            "..\\..\\rocket.ork",
        ],
    )
    def test_hostile_filenames_stay_inside_the_job_directory(
        self, monkeypatch, filename
    ):
        written = {}

        def fake_run(cmd, **kwargs):
            ork_path = Path(cmd[cmd.index("--filepath") + 1])
            out_dir = _output_dir(cmd)
            written["path"] = ork_path
            written["exists"] = ork_path.is_file()
            written["job_dir"] = out_dir.parent
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "parameters.json").write_text("{}")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(service_app.subprocess, "run", fake_run)

        status, _ = service_app._convert(b"stub", filename)

        assert status == 200
        assert written["exists"], "upload was not written as a regular file"
        assert written["path"].parent == written["job_dir"]
        assert written["path"].resolve().parent == written["job_dir"].resolve()


class TestSafeName:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("rocket.ork", "rocket.ork"),
            ("sub/dir/rocket.ork", "rocket.ork"),
            ("../../../etc/passwd", "passwd"),
            ("/etc/passwd", "passwd"),
            # Backslash is not a POSIX separator, so Path().name alone would
            # return these whole.
            ("C:\\Users\\me\\rocket.ork", "rocket.ork"),
            ("..\\..\\rocket.ork", "rocket.ork"),
            # Path("..").name is ".." — joining that escapes the job directory.
            ("..", "rocket.ork"),
            (".", "rocket.ork"),
            ("", "rocket.ork"),
            ("/", "rocket.ork"),
        ],
    )
    def test_reduces_to_a_plain_basename(self, raw, expected):
        assert service_app._safe_name(raw) == expected

    @pytest.mark.parametrize("raw", ["..", ".", "", "/", "../..", "a/../.."])
    def test_result_never_escapes_when_joined(self, raw, tmp_path):
        assert (tmp_path / service_app._safe_name(raw)).parent == tmp_path


class TestConvertEnvelope:
    def test_inlines_csvs_strips_filepath_and_keeps_stored_results(self, monkeypatch):
        _stub_run(
            monkeypatch,
            parameters={
                "id": {"filepath": "/tmp/ork-xyz/rocket.ork", "rocket_name": "Mu"},
                "motors": {"thrust_source": "out\\thrust_source.csv"},
                "rocket": {"drag_curve": "out\\drag_curve.csv"},
                "stored_results": {"max_altitude": 3262.1},
            },
            csvs={
                "thrust_source.csv": "0.0,178.47\n",
                "drag_curve.csv": "0.0175,0.000053\n",
            },
        )

        status, body = service_app._convert(b"stub", "rocket.ork")

        assert status == 200
        assert body["parameters"]["motors"]["thrust_source"] == [[0.0, 178.47]]
        assert body["parameters"]["rocket"]["drag_curve"] == [[0.0175, 0.000053]]
        # stored_results is OpenRocket's own numbers, kept for import-fidelity
        # checks against a RocketPy run.
        assert body["parameters"]["stored_results"]["max_altitude"] == 3262.1
        assert "filepath" not in body["parameters"]["id"]
        assert body["parameters"]["id"]["rocket_name"] == "Mu"

    def test_reports_the_serializer_version(self, monkeypatch):
        _stub_run(monkeypatch, parameters={})

        _, body = service_app._convert(b"stub", "rocket.ork")

        assert body["serializer_version"] == service_app.SERIALIZER_VERSION
        assert service_app.ORK_JAR.stem in body["serializer_version"]

    def test_tolerates_null_id_section(self, monkeypatch):
        _stub_run(monkeypatch, parameters={"id": None})

        status, body = service_app._convert(b"stub", "rocket.ork")

        assert status == 200
        assert body["parameters"]["id"] is None


class TestConvertErrors:
    def test_known_failure_becomes_422(self, monkeypatch):
        _stub_run(
            monkeypatch,
            returncode=1,
            stderr="The file must contain the simulation data.",
        )

        status, body = service_app._convert(b"stub", "rocket.ork")

        assert status == 422
        assert body["error"] == "no_simulation_data"

    def test_unknown_failure_becomes_500(self, monkeypatch):
        _stub_run(monkeypatch, returncode=1, stderr="java.lang.NullPointerException")

        status, body = service_app._convert(b"stub", "rocket.ork")

        assert status == 500
        assert body["error"] == "parse_failed"
        assert "NullPointer" in body["detail"]

    def test_stderr_is_truncated(self, monkeypatch):
        _stub_run(monkeypatch, returncode=1, stderr="x" * 9000)

        _, body = service_app._convert(b"stub", "rocket.ork")

        assert len(body["detail"]) == 2000

    def test_exit_zero_without_parameters_json_becomes_500(self, monkeypatch):
        _stub_run(monkeypatch, parameters=None)

        status, body = service_app._convert(b"stub", "rocket.ork")

        assert status == 500
        assert "no parameters.json" in body["detail"]

    def test_malformed_json_becomes_500_not_a_crash(self, monkeypatch):
        _stub_run(monkeypatch, parameters="{not json")

        status, body = service_app._convert(b"stub", "rocket.ork")

        assert status == 500
        assert body["error"] == "parse_failed"

    def test_malformed_csv_becomes_500_not_a_crash(self, monkeypatch):
        _stub_run(
            monkeypatch,
            parameters={"motors": {"thrust_source": "thrust_source.csv"}},
            csvs={"thrust_source.csv": "0.0,not-a-number\n"},
        )

        status, body = service_app._convert(b"stub", "rocket.ork")

        assert status == 500
        assert body["error"] == "parse_failed"

    def test_timeout_becomes_504(self, monkeypatch):
        def fake_run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, service_app.CONVERT_TIMEOUT_S)

        monkeypatch.setattr(service_app.subprocess, "run", fake_run)

        status, body = service_app._convert(b"stub", "rocket.ork")

        assert status == 504
        assert body["error"] == "timeout"


class TestHttpLayer:
    def test_health_reports_version_and_jar_presence(self, client):
        body = client.get("/health").json()

        assert body["status"] == "ok"
        assert body["serializer_version"] == service_app.SERIALIZER_VERSION
        assert body["jar_present"] is service_app.ORK_JAR.exists()

    def test_convert_returns_the_envelope(self, monkeypatch, client):
        _stub_run(monkeypatch, parameters={"stored_results": {"max_altitude": 1.0}})

        response = client.post("/convert", files=_upload())

        assert response.status_code == 200
        assert response.json()["parameters"]["stored_results"]["max_altitude"] == 1.0

    def test_empty_upload_is_rejected(self, client):
        response = client.post("/convert", files=_upload(payload=b""))

        assert response.status_code == 422
        assert response.json()["error"] == "invalid_file"

    def test_oversized_upload_is_rejected(self, monkeypatch, client):
        monkeypatch.setattr(service_app, "MAX_UPLOAD_BYTES", 10)

        response = client.post("/convert", files=_upload(payload=b"x" * 64))

        assert response.status_code == 413
        assert response.json()["error"] == "too_large"

    def test_oversized_upload_is_rejected_before_the_body_is_read(
        self, monkeypatch, client
    ):
        """The declared size must short-circuit, or an oversized body lands in
        memory purely to be thrown away."""
        monkeypatch.setattr(service_app, "MAX_UPLOAD_BYTES", 10)
        reads = []
        original_read = UploadFile.read

        async def spy(self, *args, **kwargs):
            reads.append(True)
            return await original_read(self, *args, **kwargs)

        monkeypatch.setattr(UploadFile, "read", spy)

        response = client.post("/convert", files=_upload(payload=b"x" * 64))

        assert response.status_code == 413
        assert reads == [], "body was read despite an oversized declared size"

    def test_missing_file_field_is_a_validation_error(self, client):
        response = client.post("/convert")

        assert response.status_code == 422

    def test_timeout_surfaces_as_504(self, monkeypatch, client):
        def fake_run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, service_app.CONVERT_TIMEOUT_S)

        monkeypatch.setattr(service_app.subprocess, "run", fake_run)

        response = client.post("/convert", files=_upload())

        assert response.status_code == 504
        assert response.json()["error"] == "timeout"


class TestConcurrencyCap:
    def test_in_flight_conversions_never_exceed_the_configured_limit(self, monkeypatch):
        """Each job boots a JVM and loads the full preset DB, so the cap is load-bearing.

        Driven through ASGITransport rather than TestClient: TestClient's
        blocking portal serialises calls made from several threads, which would
        mask the semaphore rather than exercise it.
        """
        lock = threading.Lock()
        state = {"live": 0, "peak": 0}

        def fake_run(cmd, **kwargs):
            with lock:
                state["live"] += 1
                state["peak"] = max(state["peak"], state["live"])
            time.sleep(0.05)
            with lock:
                state["live"] -= 1
            out_dir = _output_dir(cmd)
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "parameters.json").write_text("{}")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(service_app.subprocess, "run", fake_run)

        async def scenario():
            transport = httpx.ASGITransport(app=service_app.app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://serializer"
            ) as async_client:
                return await asyncio.gather(
                    *(async_client.post("/convert", files=_upload()) for _ in range(8))
                )

        responses = asyncio.run(scenario())

        assert all(r.status_code == 200 for r in responses)
        assert state["peak"] > 0, "fake subprocess never ran"
        assert state["peak"] <= service_app.CONVERT_CONCURRENCY
