# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

`rocketserializer` converts OpenRocket `.ork` files into RocketPy simulations. The
pipeline is: `.ork` file → `parameters.json` (+ `thrust_source.csv`, `drag_curve.csv`)
→ optional RocketPy Jupyter notebook. It ships two console scripts, `ork2json` and
`ork2notebook`, registered in `pyproject.toml` under `[project.scripts]`.

## Commands

Use the `Makefile` targets (they encode the exact flags CI uses):

- Install dev environment: `make install` (installs `requirements.in`, `requirements-dev.txt`, then `pip install -e .`)
- Format code: `make format` (`ruff check --select I --fix` then `ruff format .`)
- Lint: `make lint` (runs `make ruff-lint` = `ruff check`, then `make pylint` = `pylint examples/ rocketserializer/ tests/`)
- Tests: `make tests` (= `pytest`)

Direct pytest usage:

- Run one test file: `pytest tests/acceptance/test_ork_extractor.py -v`
- Run one parametrized case: `pytest tests/acceptance/test_ork_extractor.py -k valetudo -v`
- Match CI exactly: `pytest tests/ -v --timeout=120` (a hung JVM otherwise stalls the run)

Run the CLI against the bundled examples (smoke test, see `run-tests.ps1` / `run-tests.sh`):

```bash
ork2json --filepath "examples/EPFL--BellaLui--2020/rocket.ork" --verbose
ork2notebook --filepath "examples/NDRT--Rocket--2020/rocket.ork"
```

CI mirrors these in `.github/workflows/`: `linter.yml` runs `ruff format --check`,
`ruff check`, and `pylint`; `test-pytest.yaml` runs pytest on Ubuntu + Windows,
Python 3.9/3.11, with Java 17 (Temurin).

## Runtime prerequisites (non-obvious)

- **Java is required.** OpenRocket runs inside a JVM via JPype. OpenRocket 23+ needs
  Java 17; older jars run on Java 8. `openrocket_runtime.ensure_java_compatibility()`
  auto-detects and, on Windows only, will point `JAVA_HOME`/`PATH` at a suitable JDK
  found under `C:/Program Files/Java` etc.
- **OpenRocket jars live in the repo root** (`OpenRocket-22.02.jar`, `OpenRocket-23.09.jar`).
  The CLI picks the newest matching `OpenRocket*.jar` in the cwd via
  `select_latest_openrocket_jar()` unless `--ork_jar` is given. Tests use
  `tests/OpenRocket-15.03.jar`. These jars are large binaries — do not commit new ones
  without discussion.

## Architecture

The conversion has two orchestration layers and a component layer.

**1. CLI orchestration — `rocketserializer/cli.py`**
`ork2json` validates the file, extracts the `.ork` (it is really a zip containing a
`rocket.ork` XML — see `_helpers.extract_ork_from_zip`), parses it with BeautifulSoup,
enforces the **English-only guard** (checks that `CG location` is among the databranch
labels; otherwise detects the language and raises), opens an `OpenRocketSession`, calls
`ork_extractor`, and writes `parameters.json`. `ork2notebook` calls `ork2json`
programmatically (`standalone_mode=False`) then runs `NotebookBuilder`.

**2. Extraction orchestration — `rocketserializer/ork_extractor.py`**
`ork_extractor()` is the heart of the project. It pulls from **two data sources at once**:
- `bs` — the BeautifulSoup tree of the `.ork` XML, used for simulation datapoints and
  most numeric parameters.
- `ork` — the *live Java OpenRocket document* (loaded via `OpenRocketSession.load_doc`),
  used where geometry/positions are only available through the OpenRocket API (notably
  `components/open_rocket_wrangler.process_elements_position`).

Every component search is wrapped in a local `_safe_search()` that logs and returns a
default on failure, so one broken component never aborts the whole extraction. It
assembles a `settings` dict whose top-level keys are the contract with everything
downstream: `id`, `environment`, `rocket`, `nosecones`, `trapezoidal_fins`,
`elliptical_fins`, `tails`, `parachutes`, `rail_buttons`, `motors`, `flight`,
`stored_results`.

**3. Component layer — `rocketserializer/components/`**
One module per rocket concern, each exposing `search_*` functions (e.g.
`search_motor`, `search_nosecone`, `search_trapezoidal_fins`, `search_parachutes`,
`search_environment`, `search_launch_conditions`, `search_stored_results`). `drag_curve.py`
and `motor.py` also *write CSV files* (`drag_curve.csv`, `thrust_source.csv`) into the
output folder and store their paths in the settings dict. `open_rocket_wrangler.py` holds
the Java-tree traversal helpers (`is_sub_component`, `parent_is_a_stage`,
`process_elements_position`) that walk the OpenRocket component hierarchy.

**4. Notebook generation — `rocketserializer/nb_builder.py`**
`NotebookBuilder` reads a `parameters.json` and emits a `.ipynb` via `nbformat`, one
`build_*` method per section (header, imports, environment, motor, rocket, flight,
compare_results). It maps the settings dict onto the RocketPy API.

### The JVM singleton constraint (critical for tests)

JPype is pinned `jpype1<1.5` and **cannot restart a JVM within one process**. Therefore:
- `OpenRocketSession.__exit__` deliberately does **not** call `shutdownJVM()` — doing so
  would break any later session in the same process (notebooks, subsequent CLI calls).
- `tests/conftest.py` opens **one** `OpenRocketSession` at import time and pre-computes
  every example's settings into `_cached_settings`, exposing them as per-example fixtures.
  Do not open a second session in a test.

`OpenRocketSession` also resolves both the legacy (`net.sf.openrocket`) and modern
(`info.openrocket`) Java package layouts, so support new jars by extending
`_resolve_packages()` rather than assuming one namespace.

## Test strategy

Tests live under `tests/{unit,integration,acceptance}`. Acceptance tests
(`test_ork_extractor.py`) run the full extraction on ~23 example rockets and compare
against committed `examples/<name>/parameters.json` golden files. When you intentionally
change extraction output, regenerate and review those golden files.

## Code style

- Formatting/linting is **ruff** (line length 88; `ruff format` = black-compatible; import
  sorting via `ruff check --select I`). `pylint` runs with the disables listed in
  `pyproject.toml` (`[tool.pylint]`).
- Docstrings are **NumPy style** (Parameters / Returns / Raises sections) — match the
  existing modules.
- Logging: every module uses `logger = logging.getLogger(__name__)`; user-facing CLI
  messages are prefixed like `[ork2json]`. `--verbose` raises the log level to DEBUG.

## Known limitations (enforced or assumed by the code)

- `.ork` file must be saved in **English** and contain **at least one run simulation**.
- Only a **single stage, single motor, and single nose cone** are supported.
