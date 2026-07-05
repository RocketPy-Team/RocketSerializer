# AGENTS.md

Cross-tool instructions for AI coding agents (Google Antigravity, Cursor, OpenAI Codex,
and any agent that follows the `AGENTS.md` convention). Claude Code has its own richer
copy in `CLAUDE.md`; GitHub Copilot reads `.github/copilot-instructions.md`. Keep the
three in sync when you change shared facts.

## Project

`rocketserializer` converts OpenRocket `.ork` files into RocketPy simulations:
`.ork` → `parameters.json` (+ `thrust_source.csv`, `drag_curve.csv`) → optional RocketPy
Jupyter notebook. Two console scripts are exposed: `ork2json` and `ork2notebook`
(see `[project.scripts]` in `pyproject.toml`).

## Setup & commands

- Install: `make install`
- Format (always run before committing): `make format` — `ruff check --select I --fix` then `ruff format .`
- Lint: `make lint` — `ruff check` + `pylint examples/ rocketserializer/ tests/`
- Test: `make tests` (`pytest`); CI uses `pytest tests/ -v --timeout=120`
- One test: `pytest tests/acceptance/test_ork_extractor.py -k valetudo -v`
- Run CLI: `ork2json --filepath "examples/EPFL--BellaLui--2020/rocket.ork" --verbose`

## Prerequisites (non-obvious)

- **Java is required** — OpenRocket runs in a JVM via JPype. OpenRocket 23+ needs Java 17;
  older jars need Java 8. `rocketserializer/openrocket_runtime.py` auto-detects a JDK on
  Windows.
- **OpenRocket jars live in the repo root** (`OpenRocket-22.02.jar`, `OpenRocket-23.09.jar`);
  tests use `tests/OpenRocket-15.03.jar`. They are large binaries — do not add new ones
  without maintainer sign-off.

## Architecture (big picture)

- `rocketserializer/cli.py` — Click CLI. Validates input, unzips the `.ork` (it is a zip
  containing `rocket.ork` XML), enforces the **English-only guard**, opens an
  `OpenRocketSession`, calls `ork_extractor`, writes `parameters.json`. `ork2notebook`
  calls `ork2json` then `NotebookBuilder`.
- `rocketserializer/ork_extractor.py` — the core. Reads from **two sources at once**: the
  BeautifulSoup XML tree (`bs`, for simulation datapoints/numbers) and the live Java
  OpenRocket document (`ork`, for geometry/positions). Each component search is wrapped in
  `_safe_search` so one failure doesn't abort the run. Produces the `settings` dict.
- `rocketserializer/components/*.py` — one module per rocket concern, each with `search_*`
  functions. `drag_curve.py` and `motor.py` also write CSVs. `open_rocket_wrangler.py`
  traverses the Java component tree.
- `rocketserializer/openrocket_runtime.py` — `OpenRocketSession` context manager (JVM
  lifecycle, jar selection, Java-version compatibility). Handles both legacy
  `net.sf.openrocket` and modern `info.openrocket` package namespaces.
- `rocketserializer/nb_builder.py` — `NotebookBuilder` turns `parameters.json` into a
  RocketPy notebook via `nbformat`.

## Critical constraints

- **JPype is pinned `<1.5` and cannot restart a JVM in one process.** Never call
  `shutdownJVM()` in `OpenRocketSession.__exit__`, and never open a second session inside a
  test — `tests/conftest.py` opens one session and caches all example settings.
- Acceptance tests compare full extraction output against committed
  `examples/<name>/parameters.json` golden files. If you intentionally change output,
  regenerate and review those files.
- Supported inputs only: `.ork` saved in **English**, containing **≥1 run simulation**,
  with a **single stage, single motor, single nose cone**.

## Conventions

- Formatter/linter: **ruff** (line length 88, black-compatible) + **pylint** (disables in
  `pyproject.toml`).
- Docstrings: **NumPy style** (Parameters / Returns / Raises).
- Every module uses `logger = logging.getLogger(__name__)`; CLI messages are prefixed like
  `[ork2json]`.

## Skills

Reusable, task-specific playbooks live in `.agents/skills/` (Antigravity) and mirror the
Claude Code skills in `.claude/skills/`. See them for deeper guidance on RocketPy, the
OpenRocket/JPype interop, adding a new component extractor, and Python conventions.
