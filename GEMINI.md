# GEMINI.md — Google Antigravity rules

Antigravity reads this file as the highest-priority workspace rule. The full,
tool-neutral guidance lives in **[`AGENTS.md`](./AGENTS.md)** — read it first; everything
there applies here. This file only adds Antigravity-specific notes.

## Antigravity-specific notes

- **Skills** for this workspace live in `.agents/skills/<name>/SKILL.md`. Antigravity
  semantic-matches a prompt against each skill's `description` frontmatter and only then
  loads the body. Use them for RocketPy, OpenRocket/JPype interop, adding a component
  extractor, and Python conventions.
- **Always run `make format` and `make lint`** before proposing a diff; CI (`ruff format
  --check`, `ruff check`, `pylint`) will reject unformatted code.
- **Verify with the real pipeline**, not just unit tests: run
  `ork2json --filepath "examples/EPFL--BellaLui--2020/rocket.ork" --verbose` and confirm a
  valid `parameters.json` is produced. This requires a working Java (17) install — see
  `AGENTS.md`.
- **Do not restart the JVM.** JPype is pinned `<1.5`; one JVM per process. Never add
  `shutdownJVM()` and never open a second `OpenRocketSession` in a test.
- **Never commit new OpenRocket `.jar` files** or regenerated golden `parameters.json`
  without flagging it explicitly — the jars are large binaries and the JSON files are test
  oracles.
