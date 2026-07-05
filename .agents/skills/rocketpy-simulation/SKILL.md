---
name: rocketpy-simulation
description: Understand how generated parameters.json maps onto the RocketPy API (Environment, SolidMotor/Motor, Rocket, Flight) and how nb_builder.py assembles a runnable RocketPy notebook. Use when editing nb_builder.py, changing what a component contributes to the notebook, debugging a generated simulation, or aligning output with a RocketPy version.
---

# RocketPy simulation mapping

`rocketserializer` produces inputs for **RocketPy** (`rocketpy>=1.1.0`). The generated
notebook (`nb_builder.NotebookBuilder`) reads `parameters.json` and constructs a standard
RocketPy simulation. Keep the mapping below in mind when changing extraction or the builder.

## The RocketPy objects the notebook builds
The `build_*` methods in `NotebookBuilder` map settings sections onto RocketPy classes:

- `build_environment` → `Environment` (latitude, longitude, elevation, date, atmospheric
  model). Fed by `settings["environment"]` + `settings["flight"]`.
- `build_motor` → a motor object (e.g. `SolidMotor`) using `settings["motors"]`, with
  `thrust_source` pointing at the generated `thrust_source.csv`.
- `build_rocket` → `Rocket` with mass/inertia/radius from `settings["rocket"]`, the
  `power_off`/`power_on` drag from the generated `drag_curve.csv`, then aerodynamic surfaces
  added via `add_nose`, `add_trapezoidal_fins` / `add_elliptical_fins`, `add_tail`, and
  parachutes via `add_parachute`, plus rail buttons.
- `build_flight` → `Flight` (rocket + environment + rail length + inclination + heading).
- `build_compare_results` → compares RocketPy output against `settings["stored_results"]`
  (the values OpenRocket itself computed), which is how a user sanity-checks the conversion.

## Practical guidance
- The builder is a **codegen** step: each method appends notebook cells (`nbf.v4`), so you
  are writing Python *source strings* that must run under the pinned `rocketpy` version.
  When you reference a RocketPy method/argument, verify it exists in that version's API
  rather than assuming.
- Coordinate systems and positions matter: RocketPy places surfaces relative to a reference
  (nose tip / center of dry mass). The positions come from `open_rocket_wrangler` — if a
  surface lands in the wrong place in the simulation, suspect the position map, not RocketPy.
- `stored_results` are the ground truth from OpenRocket (apogee, max velocity, etc.). Use
  them to validate: a good conversion makes the RocketPy `Flight` results land close to the
  stored ones.

## When aligning with RocketPy
If a generated notebook fails to run, first reproduce with an example
(`ork2notebook --filepath "examples/NDRT--Rocket--2020/rocket.ork"`) and open the notebook.
Fix the offending `build_*` method's emitted code, not the extraction, unless the underlying
parameter is genuinely wrong in `parameters.json`.
