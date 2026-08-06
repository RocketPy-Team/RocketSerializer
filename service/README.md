# ork-serializer service

A thin HTTP wrapper around the `ork2json` CLI, packaged so callers don't need
Java, a JVM, or a 70 MB OpenRocket jar in their own image.

Nothing under `rocketserializer/` is modified — this directory is additive.

## API

### `GET /health`

```json
{ "status": "ok", "serializer_version": "0.2.0+OpenRocket-23.09", "jar_present": true }
```

### `POST /convert`

`multipart/form-data` with a single `file` field containing a `.ork`.

**200** — the parameters, self-contained:

```json
{
  "serializer_version": "0.2.0+OpenRocket-23.09",
  "parameters": {
    "environment": { ... },
    "rocket":  { "drag_curve": [[0.0175, 0.00005], ...], ... },
    "motors":  { "thrust_source": [[0.0, 178.47], ...], ... },
    "stored_results": { "max_altitude": 3262.1, "time_to_apogee": 25.555, ... },
    ...
  }
}
```

The `thrust_source` and `drag_curve` CSVs that `ork2json` writes as sibling
files are parsed and **inlined**, and the absolute `id.filepath` is stripped.
Raw `parameters.json` references those CSVs by host-relative path
(backslash-separated when produced on Windows), so it is not usable on its own.

`stored_results` carries OpenRocket's own simulation numbers through
unchanged. Diffing them against a RocketPy run of the same imported design is
the cheapest available check on whether a parse was faithful.

**Errors** — all shaped `{"error": "<code>", "detail": "..."}`:

| Status | Code | Meaning |
|---|---|---|
| 413 | `too_large` | Upload over `MAX_UPLOAD_BYTES` |
| 422 | `no_simulation_data` | `.ork` has no saved simulation — user must run one in OpenRocket first |
| 422 | `non_english` | `.ork` saved in a non-English locale |
| 422 | `invalid_encoding` | Not an OpenRocket archive, or a `.ork` saved in a non-UTF-8 encoding |
| 422 | `invalid_file` | Empty or unreadable upload |
| 500 | `parse_failed` | Anything else; `detail` is the tail of stderr |
| 504 | `timeout` | Exceeded `CONVERT_TIMEOUT_S` |

## Configuration

| Env var | Default | Notes |
|---|---|---|
| `ORK_JAR` | `/opt/openrocket/OpenRocket-23.09.jar` | Pinned; also forms `serializer_version` |
| `CONVERT_TIMEOUT_S` | `120` | Per-conversion subprocess timeout |
| `CONVERT_CONCURRENCY` | `2` | Simultaneous conversions |
| `MAX_UPLOAD_BYTES` | `33554432` | Sample `.ork` files run 400 KB–1.1 MB |

## Latency

Expect **5–20 s** per conversion. The cost is fixed startup, not file size:
`OpenRocketSession.__enter__` boots a JVM, then calls `blockUntilLoaded()` on
OpenRocket's preset and motor loaders — the full component database, every
time. Callers should treat this as a slow endpoint and set timeouts above 30 s.

## Why a subprocess per request

`rocketserializer` runs the JVM in-process through jpype:

- `OpenRocketSession.__exit__` deliberately never calls `shutdownJVM()`
  (jpype1<1.5 cannot restart one), so a process gets exactly one JVM.
- If a JVM is already running, `__enter__` logs a warning and **reuses the
  existing classpath**. A warm worker would silently parse against a stale
  OpenRocket version.
- A JVM crash kills the host process rather than raising to Python.
- `cli.py` calls `logging.basicConfig(filename="serializer.log")` at import,
  writing into the working directory — concurrent jobs would collide.

Each request therefore gets a fresh process and a fresh temp directory, both
discarded on completion.

## Local development

```bash
pip install -r requirements.in -r service/requirements.txt
pip install -e .
ORK_JAR=$PWD/OpenRocket-23.09.jar uvicorn service.app:app --reload

curl -sS -F file=@examples/Anonymous--Mu/rocket.ork localhost:8000/convert | jq .
```

## Tests

```bash
pytest service/ -q
```

`service/test_app.py` stubs the subprocess, so it needs no JVM and no jar — it
covers envelope assembly, CSV inlining and error classification only.

It deliberately lives here rather than under `tests/`: `tests/conftest.py`
opens an `OpenRocketSession` at *import* time and pre-extracts all 23 examples,
so anything placed there inherits a multi-minute JVM startup it doesn't need.

**Consequence:** CI runs `pytest tests/ -v`, so these tests do not run in CI.
Closing that gap needs two one-line changes — `pytest tests/ service/` in
`.github/workflows/test-pytest.yaml`, and `fastapi`/`httpx`/`python-multipart`
in `requirements-dev.txt`. Both are left out here to keep the diff additive.

## Build and deploy

```bash
docker build -f service/Dockerfile -t ork-serializer .        # from repo root
docker network create ork-net                                 # once, on the host
CONTAINER_NAME=ork-serializer-staging IMAGE_TAG=<sha> \
  docker compose -f service/docker-compose.yml up -d
```

**Architecture matters here.** `jpype1` is pinned `<1.5`, which predates
aarch64 wheels, so on arm64 (Apple Silicon) pip compiles it from source — hence
the `build-essential` step. On amd64 a prebuilt wheel exists and that step is a
no-op. A build on an Apple Silicon laptop produces an **arm64 image that will
not run on an amd64 host**, so target the deployment architecture explicitly:

```bash
docker buildx build --platform linux/amd64 -f service/Dockerfile -t ork-serializer .
```
