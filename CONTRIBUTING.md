# Contributing

Thanks for helping make agent reliability testing better. This project values
correctness and determinism over feature count — small, well-tested changes
are the norm.

## Development setup

```bash
git clone https://github.com/felmonon/agent-reliability-harness
cd agent-reliability-harness
python -m venv .venv && source .venv/bin/activate   # or: uv venv
python -m pip install -e ".[dev]"
```

## Checks (all must pass)

```bash
python -m unittest discover -s tests      # full test suite
ruff check src tests benchmarks           # lint
mypy src                                  # strict type checking
python benchmarks/run.py                  # benchmark thresholds (P=R=1.0, determinism, perf)
```

CI runs these on Linux/macOS/Windows across Python 3.11-3.13, plus a
sdist/wheel build with a clean-environment install smoke test.

## Hard rules

- **Zero runtime dependencies in the core.** `dependencies = []` stays empty.
  Optional functionality goes behind extras; dev tooling goes in the `dev`
  extra.
- **Determinism.** Core code never reads the network, a clock, environment
  randomness, or anything machine-specific into reports. If your change can
  alter output bytes for identical input, it's a bug.
- **Rule IDs are permanent.** Never rename, reuse, or change the meaning of an
  `ARH-*` rule ID (they are regression fingerprints and documentation
  anchors). New behavior gets a new ID appended to
  `src/agent_reliability_harness/rules.py`; regenerate the reference with
  `python tools/generate_rules_doc.py`.
- **Backward compatibility.** v0.1.x traces, policies, and baselines must keep
  working; `tests/test_compat_golden.py` pins this. Schema changes are
  additive; a breaking change requires a schema major bump plus a migration
  path, documented in COMPATIBILITY.md — discuss in an issue first.
- **Benchmark cases are generated.** Edit
  `benchmarks/tools/generate_cases.py`, then run it; never hand-edit files in
  `benchmarks/cases/` (CI checks they're in sync). `BENCHMARK-RESULTS.md` is
  written only by `python benchmarks/run.py --write` — never by hand.
- **Documented commands must run.** Anything you put in `docs/quickstart.md`
  is executed by `tests/test_docs_examples.py`.
- **Tests fail loudly.** New checks need negative tests and (where input is
  parsed) adversarial tests — see `tests/test_adversarial.py`.

## Commit style

Conventional-ish prefixes: `feat:`, `fix:`, `docs:`, `test:`, `bench:`,
`chore:`. Keep commits coherent; explain *why* in the body when behavior
changes.

## Pull requests

- One logical change per PR.
- State compatibility impact explicitly (or "none").
- Update CHANGELOG.md under `Unreleased`.
- Fill in the PR template; include before/after report output for
  user-visible changes.

## Reporting security issues

See [SECURITY.md](SECURITY.md) — please use private reporting, not public
issues.
