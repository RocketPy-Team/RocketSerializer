"""Minimal HTTP wrapper around the ``ork2json`` CLI.

Design note — one subprocess per request, deliberately:

``rocketserializer`` embeds a JVM in-process via jpype, and
``OpenRocketSession.__exit__`` never calls ``shutdownJVM()`` because jpype1<1.5
cannot restart a JVM once stopped. If the JVM is already running,
``__enter__`` logs a warning and *silently keeps the previous classpath* — so a
long-lived worker would eventually parse files against the wrong OpenRocket
version. A fresh process per job also contains JVM segfaults (which would
otherwise take the server down with them) and gives ``cli.py``'s import-time
``serializer.log`` write somewhere disposable to land.

The service holds no state and touches no storage: upload in, JSON out, temp
directory discarded.
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import shutil
import subprocess
import tempfile
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

ORK_JAR = Path(os.environ.get("ORK_JAR", "/opt/openrocket/OpenRocket-23.09.jar"))
CONVERT_TIMEOUT_S = int(os.environ.get("CONVERT_TIMEOUT_S", "120"))
CONVERT_CONCURRENCY = int(os.environ.get("CONVERT_CONCURRENCY", "2"))
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(32 * 1024 * 1024)))

try:
    _PKG_VERSION = pkg_version("rocketserializer")
except PackageNotFoundError:  # editable install without metadata
    _PKG_VERSION = "unknown"

# Recorded on every import so a bad parse can be traced back to the exact
# parser that produced it.
SERIALIZER_VERSION = f"{_PKG_VERSION}+{ORK_JAR.stem}"

# ork2json surfaces user-fixable problems as ValueError text. Map the known
# ones to stable codes so the caller can show a real message instead of a
# stack trace. Order matters: first match wins.
_USER_ERRORS = (
    ("must contain the simulation data", "no_simulation_data"),
    ("saved in English", "non_english"),
    ("non-English", "non_english"),
    ("does not exist", "invalid_file"),
)

app = FastAPI(title="ork-serializer", version=SERIALIZER_VERSION)

_slots = asyncio.Semaphore(CONVERT_CONCURRENCY)

# Module-level so it isn't a function call in an argument default (ruff B008).
_UPLOAD = File(...)


def _read_pairs(path: Path) -> list[list[float]]:
    """Parse a headerless two-column CSV into ``[[x, y], ...]``."""
    pairs: list[list[float]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.reader(handle):
            if len(row) >= 2 and row[0].strip():
                pairs.append([float(row[0]), float(row[1])])
    return pairs


def _classify(stderr: str) -> str | None:
    for needle, code in _USER_ERRORS:
        if needle in stderr:
            return code
    return None


def _inline_csv(parameters: dict, section: str, key: str, out_dir: Path) -> None:
    """Replace a CSV path in ``parameters`` with its parsed contents.

    ork2json writes sibling CSVs and references them by *host* relative path
    (backslash-separated when produced on Windows), so the raw parameters.json
    is not self-contained. Inlining here means the caller receives one object
    that already matches its own schema, with no file lifecycle to manage.
    """
    # ork_extractor wraps every component lookup in _safe_search and falls back
    # to defaults, so a section can legitimately come back null rather than as
    # a dict. Chaining .get() through that would raise AttributeError.
    block = parameters.get(section)
    if not isinstance(block, dict):
        return

    value = block.get(key)
    if not isinstance(value, str):
        return

    csv_path = out_dir / Path(value.replace("\\", "/")).name
    block[key] = _read_pairs(csv_path) if csv_path.exists() else None


def _safe_name(filename: str) -> str:
    """Reduce a client-supplied filename to a plain basename.

    ``Path(...).name`` alone is not enough: it returns ``".."`` unchanged, so
    ``job_dir / ".."`` would escape to the parent directory, and it does not
    split on backslashes under POSIX, so a Windows client's ``C:\\a\\b.ork``
    would arrive whole.
    """
    name = Path(filename.replace("\\", "/")).name
    if name in {"", ".", ".."}:
        return "rocket.ork"
    return name


def _convert(ork_bytes: bytes, filename: str) -> tuple[int, dict]:
    """Run ork2json in an isolated temp directory. Returns (status, body)."""
    job_dir = Path(tempfile.mkdtemp(prefix="ork-"))
    try:
        ork_path = job_dir / _safe_name(filename)
        ork_path.write_bytes(ork_bytes)
        out_dir = job_dir / "out"

        try:
            result = subprocess.run(
                [
                    "ork2json",
                    "--filepath",
                    str(ork_path),
                    "--output",
                    str(out_dir),
                    "--ork_jar",
                    str(ORK_JAR),
                ],
                # cwd matters: cli.py writes serializer.log into the working
                # directory at import time, and an unset --ork_jar would make
                # it scan cwd for a jar.
                cwd=job_dir,
                capture_output=True,
                text=True,
                timeout=CONVERT_TIMEOUT_S,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return 504, {
                "error": "timeout",
                "detail": f"conversion exceeded {CONVERT_TIMEOUT_S}s",
            }

        if result.returncode != 0:
            code = _classify(result.stderr)
            if code:
                return 422, {"error": code, "detail": result.stderr.strip()[-2000:]}
            return 500, {
                "error": "parse_failed",
                "detail": result.stderr.strip()[-2000:],
            }

        params_path = out_dir / "parameters.json"
        if not params_path.exists():
            return 500, {
                "error": "parse_failed",
                "detail": "ork2json exited 0 but wrote no parameters.json",
            }

        # Malformed output is a parse failure, not a crash: a non-numeric CSV
        # cell or truncated JSON must not surface as an unhandled traceback.
        try:
            parameters = json.loads(params_path.read_text(encoding="utf-8"))
            _inline_csv(parameters, "motors", "thrust_source", out_dir)
            _inline_csv(parameters, "rocket", "drag_curve", out_dir)
        except (ValueError, OSError) as exc:
            return 500, {
                "error": "parse_failed",
                "detail": f"unreadable ork2json output: {exc}",
            }

        # Absolute host paths leak the temp directory; the caller has no use
        # for them.
        if isinstance(parameters.get("id"), dict):
            parameters["id"].pop("filepath", None)

        return 200, {
            "serializer_version": SERIALIZER_VERSION,
            "parameters": parameters,
        }
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "serializer_version": SERIALIZER_VERSION,
        "jar_present": ORK_JAR.exists(),
    }


@app.post("/convert")
async def convert(file: UploadFile = _UPLOAD) -> JSONResponse:
    too_large = JSONResponse(
        status_code=413,
        content={
            "error": "too_large",
            "detail": f"upload exceeds {MAX_UPLOAD_BYTES} bytes",
        },
    )

    # Reject on the declared size before reading, so an oversized body is not
    # pulled into memory just to be discarded. The post-read check stays as a
    # fallback for clients that send no size.
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        return too_large

    ork_bytes = await file.read()

    if not ork_bytes:
        return JSONResponse(
            status_code=422, content={"error": "invalid_file", "detail": "empty upload"}
        )
    if len(ork_bytes) > MAX_UPLOAD_BYTES:
        return too_large

    # Each job boots a JVM and loads OpenRocket's full preset database, so
    # unbounded concurrency would thrash the box rather than go faster.
    async with _slots:
        status, body = await asyncio.to_thread(
            _convert, ork_bytes, file.filename or "rocket.ork"
        )

    return JSONResponse(status_code=status, content=body)
