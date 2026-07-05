---
name: add-component-extractor
description: Add or modify a rocket component extractor in the serialization pipeline (motor, fins, nose cone, parachute, transition, environment, flight, stored results, etc.). Use when a parameter is missing from parameters.json, when supporting a new OpenRocket feature, or when editing anything under rocketserializer/components/ or ork_extractor.py.
---

# Adding a component extractor

The serializer builds `parameters.json` in `ork_extractor.ork_extractor()` by calling one
`search_*` function per rocket concern from `rocketserializer/components/`. To add or extend
a component, follow the existing pattern exactly.

## Anatomy of a component module
Each `components/<thing>.py`:
- Starts with `import logging` and `logger = logging.getLogger(__name__)`.
- Exposes `search_<thing>(bs, ...)` returning a **dict or list of dicts** (never prints;
  logs instead).
- Uses NumPy-style docstrings (Parameters / Returns).
- Reads scalars from the BeautifulSoup tree `bs`; reads geometry/positions from the
  `elements` map produced by `open_rocket_wrangler.process_elements_position` (which needs
  the Java `ork` document). See `nose_cone.py` and `fins.py` for the `elements` pattern.

## Wiring it into the pipeline
In `ork_extractor.py`:
1. Import your function at the top with the other `from .components.<x> import ...` lines.
2. Call it through the local `_safe_search(func, default_ret, *args)` wrapper so a failure
   logs and returns the default instead of aborting the whole extraction. Choose a sensible
   default (`{}`, `[]`, or a minimal dict) matching the shape callers expect.
3. Assign the result into `settings["<key>"]`. The top-level keys are a **contract** with
   `nb_builder.py` and the acceptance golden files — don't rename existing keys casually.

Current keys: `id`, `environment`, `rocket`, `nosecones`, `trapezoidal_fins`,
`elliptical_fins`, `tails`, `parachutes`, `rail_buttons`, `motors`, `flight`,
`stored_results` (plus `rocket.drag_curve` and `motors.thrust_source` which point to CSVs
written into the output folder).

## If the notebook must use the new value
Add/adjust the matching `build_*` method in `nb_builder.NotebookBuilder` so the value flows
into the generated RocketPy notebook. The builder reads only from `parameters.json`.

## Validate the change
1. `make format && make lint`
2. Run the pipeline on an example that exercises the component:
   `ork2json --filepath "examples/EPFL--BellaLui--2020/rocket.ork" --verbose`
   and inspect the resulting `parameters.json`.
3. `pytest tests/acceptance/test_ork_extractor.py -v`. Acceptance tests compare against
   committed `examples/<name>/parameters.json`. If your change **intentionally** alters
   output, regenerate those golden files and review the diff carefully before committing.
4. Add unit coverage under `tests/unit/` when practical.

## Remember the input limitations
The pipeline assumes a single stage, single motor, and single nose cone, and English-only
`.ork` files with at least one run simulation. Don't silently break these assumptions.
