# Compatibility

The compatibility contract for 0.2.0 relative to 0.1.x, and the policy going
forward.

## Preserved from v0.1.x (verified)

- **Trace and policy files work unchanged.** The v0.1.x formats are strict
  subsets of schema v1; a missing `schema_version` means `"1"`. No migration
  step exists because none is needed.
- **Identical scores and verdicts.** New check categories (sequence, flow,
  completion) are *not applicable* for policies that don't configure them, and
  the score renormalizes over applicable categories only — so a v0.1.x policy
  yields byte-identical scores. Pinned by `tests/test_compat_golden.py`
  (sample scores 100.0 / 80.0 / 70.0, verdicts, and finding messages) and
  `tests/test_trajectory_rules.py::TestLegacyScoreCompatibility`.
- **Finding messages** for all v0.1.x checks are unchanged (golden-tested).
- **Console markers** (`[PASS]`, `[FAIL]`, `[safety   ]` category blocks,
  summary line) remain; see "Changed additively" for the one console addition.
- **Exit codes:** `0` all passed; `1` at least one trace failed (and now also:
  regression gate failed / invalid input file with an `error:` message);
  `2` command-line usage errors.
- **Python API:** all v0.1.x constructors and signatures still work —
  `Trace`, `Step`, `Policy`, `ToolSchema` (string arg specs still accepted),
  `Budgets`, `GroundingPolicy`, `Finding`, `TraceReport`, `validate_trace`.
  All new dataclass fields have defaults; the entire original test suite (35
  tests) runs unmodified.

## Changed additively in 0.2.0

- `Finding` gains `rule_id` (always set by the validator), and optional
  `expected` / `observed` / `remediation`; `Finding.to_dict()` includes them.
- JSON report gains top-level `"schema_version": "1"` and per-report
  `total_tokens` / `source_path` (only when set).
- Console findings now include the rule ID
  (`- [ERROR  ] [safety   ] ARH-SAF-001: ...`); the Markdown findings table
  gains a Rule column. Byte-level v0.1 console/markdown output is therefore
  *not* preserved — human-oriented formats are not a stability surface.
  JSON remains additive-only.
- New CLI surface: `arh validate --format/--junit-out/--sarif-out`,
  `arh compare`, `arh --version`.

## Behavior fix (deliberate, documented)

v0.1.0 reported a **duplicate finding** when a *required* argument had a wrong
type (the argument was checked in two loops). 0.2.0 reports it once. Scores and
verdicts are unaffected (the step already counted as failed once). Recorded in
CHANGELOG.md and DECISIONS.md ADR-007.

## Legacy baselines in `arh compare`

Baselines produced by v0.1.x have findings without `rule_id`. The comparison
first matches on the full fingerprint `(trace_id, rule_id, category, step_id)`,
then runs a second pass ignoring `rule_id` when legacy findings are involved —
so upgrading the harness does not spuriously report every finding as
new+resolved. Covered by
`tests/test_regression.py::TestLegacyBaselineCompatibility`. Regenerating the
baseline once with 0.2.0 upgrades fingerprints to rule-ID precision.

## Versioning policy

- **SemVer** for the package. Public API = documented CLI surface, JSON report
  structure (additive within a major), trace/policy schema semantics, rule IDs.
- **Rule IDs are permanent:** they never change meaning and are never reused;
  retiring a rule retires its ID.
- **Schema majors:** an incompatible trace/policy/report change bumps the
  schema major; the release that does so must ship an automated migration path
  and reject unknown majors precisely (already enforced by the parsers).
- Minor releases must keep the golden compatibility tests green; changing them
  requires a documented breaking-change decision first.
