# GitHub Copilot instructions

Repository-wide custom instructions for GitHub Copilot (chat, code review, and the coding
agent). Path-specific instructions can be added under `.github/instructions/*.instructions.md`
with YAML frontmatter `applyTo:` globs. Keep shared facts consistent with `AGENTS.md` and
`CLAUDE.md`.

## Project

`rocketserializer` converts OpenRocket `.ork` files into RocketPy simulations:
`.ork` → `parameters.json` (+ `thrust_source.csv`, `drag_curve.csv`) → optional RocketPy
Jupyter notebook. Console scripts: `ork2json` and `ork2notebook`.

## How to work in this repo

- Format before committing: `make format` (ruff import-sort + `ruff format`). CI runs
  `ruff format --check`, `ruff check`, and `pylint examples/ rocketserializer/ tests/` — do
  not leave any of them failing.
- Test with `pytest`; CI uses `pytest tests/ -v --timeout=120`. Run a single case with
  `pytest tests/acceptance/test_ork_extractor.py -k valetudo -v`.
- Follow **NumPy-style docstrings** and keep lines ≤ 88 chars.
- Use `logger = logging.getLogger(__name__)` for logging; prefix CLI-facing messages like
  `[ork2json]`.

## Architecture Copilot should know

- `cli.py` orchestrates: unzip `.ork` (it is a zip holding `rocket.ork` XML), enforce the
  **English-only guard**, open `OpenRocketSession`, call `ork_extractor`, write JSON.
- `ork_extractor.py` reads from **two sources at once**: the BeautifulSoup XML tree (`bs`)
  and the live Java OpenRocket document (`ork`). Each component search is wrapped in
  `_safe_search`. Its `settings` dict keys are the downstream contract.
- `components/*.py` — one `search_*` module per rocket part; `drag_curve.py`/`motor.py` also
  write CSVs. `open_rocket_wrangler.py` walks the Java component tree.
- `openrocket_runtime.py` — `OpenRocketSession` manages the JVM (via JPype) and supports both
  `net.sf.openrocket` (legacy) and `info.openrocket` (modern) namespaces.
- `nb_builder.py` — `NotebookBuilder` renders `parameters.json` into a RocketPy notebook.

## Hard constraints (do not violate in suggestions)

- **Java is required** (OpenRocket 23+ → Java 17). Jars live in the repo root; tests use
  `tests/OpenRocket-15.03.jar`.
- **JPype `<1.5` cannot restart a JVM.** Never suggest `shutdownJVM()` in
  `OpenRocketSession.__exit__`, and never open a second `OpenRocketSession` in a test — see
  `tests/conftest.py`, which caches all example settings from one session.
- Acceptance tests compare against committed `examples/<name>/parameters.json` golden files;
  changing extraction output means regenerating and reviewing them.
- Supported inputs: `.ork` in **English**, with **≥1 run simulation**, **single stage /
  motor / nose cone**.
- Do not add new large OpenRocket `.jar` binaries without maintainer approval.
