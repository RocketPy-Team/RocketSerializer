---
name: python-conventions
description: Python style, tooling, and testing conventions for this repo — ruff/black formatting, pylint config, NumPy docstrings, logging, and the pytest layout (unit/integration/acceptance) with the single-JVM constraint. Use before writing or reviewing any Python change here so it passes CI on the first try.
---

# Python conventions

## Formatting & linting (must pass CI)
- **ruff** is the formatter and primary linter. Line length **88**, black-compatible.
  - Format: `make format` = `ruff check --select I --fix` (import sort) + `ruff format .`
  - Lint: `make ruff-lint` = `ruff check .`
- **pylint** also runs: `make pylint` = `pylint examples/ rocketserializer/ tests/`. The
  disabled checks are in `pyproject.toml` `[tool.pylint]` (e.g. missing docstrings,
  too-many-locals/arguments, `raise-missing-from`, `fixme`). Don't re-enable them ad hoc.
- CI (`.github/workflows/linter.yml`) runs `ruff format --check`, `ruff check`, and pylint
  on Python 3.9. Run `make lint` locally first.
- Supported Python: 3.8–3.12 (`requires-python = ">= 3.8"`). Don't use syntax newer than 3.8.

## Docstrings & logging
- **NumPy-style docstrings** with `Parameters` / `Returns` / `Raises` sections — match the
  existing modules (`_helpers.py`, `ork_extractor.py`).
- Every module defines `logger = logging.getLogger(__name__)`. Log instead of `print`.
  User-facing CLI messages are prefixed with the command name, e.g. `[ork2json] ...`.
- Public functions raise precise exceptions with actionable messages (`FileNotFoundError`,
  `ValueError`); the CLI surfaces them.

## Testing
- Layout: `tests/unit/`, `tests/integration/`, `tests/acceptance/`.
- Run: `make tests` (`pytest`); CI: `pytest tests/ -v --timeout=120` (the `--timeout` guards
  against a hung JVM). One case: `pytest tests/acceptance/test_ork_extractor.py -k valetudo -v`.
- **Single-JVM rule:** JPype (`<1.5`) can't restart a JVM in-process, so `tests/conftest.py`
  opens exactly one `OpenRocketSession` and caches every example's settings as fixtures.
  Never open another session in a test.
- **Acceptance tests are golden-file comparisons** against `examples/<name>/parameters.json`.
  Intentional output changes require regenerating and reviewing those files.

## Dependencies
Runtime deps are in `requirements.in` (consumed by `pyproject.toml` dynamic dependencies);
dev tools in `requirements-dev.txt`. Add runtime deps to `requirements.in`, not directly to
`pyproject.toml`.
