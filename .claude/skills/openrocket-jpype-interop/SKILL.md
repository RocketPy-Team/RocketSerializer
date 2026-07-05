---
name: openrocket-jpype-interop
description: Work with the OpenRocket Java library through JPype — start/stop the JVM, load .ork documents, traverse the rocket component tree, and read data from both the XML (BeautifulSoup) and the live Java object. Use when touching openrocket_runtime.py, open_rocket_wrangler.py, ork_extractor.py, the JVM/Java setup, or anything that calls into net.sf.openrocket / info.openrocket.
---

# OpenRocket ↔ JPype interop

## The two-source model
`ork_extractor(bs, filepath, output_folder, ork)` reads from **two sources
simultaneously** — always know which one a given value comes from:

- `bs` — a `BeautifulSoup` tree of the `.ork` XML (`_helpers.parse_ork_file`). Source of
  the simulation **datapoints** and most numeric parameters. Access via `bs.find(...)`,
  `bs.find_all("datapoint")`, and `bs.find("databranch").attrs["types"]` (the comma-joined
  column labels).
- `ork` — the **live Java OpenRocket document** (`OpenRocketSession.load_doc`). Source of
  **geometry and component positions** that the XML doesn't expose cleanly. Reached via
  `ork.getRocket()` and traversed in `components/open_rocket_wrangler.py`.

When adding an extractor, prefer `bs` for scalar/sim data and only reach into `ork` when the
value requires walking the component hierarchy.

## The JVM lifecycle (read before changing session code)
JPype is pinned **`jpype1<1.5`**, which **cannot restart a JVM in one process**. Consequences:

- `OpenRocketSession.__exit__` must **not** call `jpype.shutdownJVM()`. It only disposes AWT
  windows. The JVM is cleaned up by JPype's atexit hook.
- Never open a second `OpenRocketSession` in a test. `tests/conftest.py` opens **one**
  session at import time and caches every example's settings in `_cached_settings`.
- To use the session: `with OpenRocketSession(jar_path, log_level="OFF") as s: doc = s.load_doc(path)`.

## Package namespaces
OpenRocket moved from `net.sf.openrocket` (legacy, ≤ ~22) to `info.openrocket` (modern).
`OpenRocketSession._resolve_packages()` tries legacy first, then modern, returning
`(core, swing)`. If you support a new jar and a symbol is missing, extend that method rather
than hard-coding a namespace anywhere else.

## Java version compatibility
`ensure_java_compatibility(jar_path)` picks the minimum Java: OpenRocket 23+ → Java 17,
else Java 8. On Windows it auto-discovers a JDK under `C:/Program Files/Java` (and Adoptium
/ AdoptOpenJDK) and sets `JAVA_HOME`/`PATH`. On other OSes it only warns — the user must
provide a compatible JVM. Jar version is parsed from the filename by `_jar_version_tuple`.

## Traversing the component tree
`open_rocket_wrangler.py` helpers: `is_sub_component(ork)` (depth > 1 from root),
`parent_is_a_stage(ork)` (parent class is `Stage`/`AxialStage`), and
`process_elements_position(...)` which builds the position map used by fins, nose cone,
transitions, and rail buttons. Component Java classes are identified by
`ork.getClass().getSimpleName()`.

## Gotchas
- Java calls raise `jpype.JException` (plus `AttributeError`/`TypeError`/`RuntimeError` when
  internals change between versions). Catch these narrowly — see `_block_loader`.
- The `.ork` file is a **zip** containing `rocket.ork` (XML). `extract_ork_from_zip` handles
  both the zipped and already-extracted cases (it catches `BadZipFile`).
