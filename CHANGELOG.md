# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.1] - 2026-07-14

### Fixed

- Modernized packaging license metadata to the PEP 639/SPDX form
  (`license = "MIT"`, `license-files = ["LICENSE"]`) and removed the
  deprecated license classifier; builds no longer emit setuptools license
  deprecation warnings.
- Converted README documentation links to absolute GitHub URLs so they work
  from the PyPI long-description renderer.
- Corrected stale compatibility language that incorrectly claimed every
  v0.1 score remained identical despite the documented nested-safety-scan
  fix (70.0 -> 70.83 for one sample; verdict unchanged).


## [0.2.0] - 2026-07-14

### Added

- **Trajectory rules** (`sequence`): required tools, forbidden tools,
  partial-order `call_order`, per-tool `min_calls`/`max_calls`
  (`ARH-SEQ-001..005`).
- **Flow rules** (`error_handling`, `side_effect`): ignored tool errors,
  retry storms, duplicate side-effect protection (`ARH-FLW-001..003`).
- **Completion rules** (`completion`): required final response, max step
  count (`ARH-CMP-001..002`).
- **Argument value constraints**: `enum`, full-match `pattern`, numeric
  `min`/`max` on tool arguments (`ARH-SCH-007..009`), alongside the legacy
  bare type-name form.
- **Token budgets** (`budgets.max_total_tokens`, `ARH-BUD-004`) with an
  explicit warning when the trace carries no token data (`ARH-BUD-005`)
  instead of a silent pass.
- **Citation validity** (`grounding.require_valid_citation_urls`,
  `ARH-GRD-003`) and step-level `status`/`error`, `input_tokens`/
  `output_tokens`, and `metadata` trace fields.
- **Stable rule IDs** (`ARH-*`) on every finding, plus `expected`/`observed`/
  `remediation` evidence fields and a generated rule reference
  (`docs/rules.md`).
- **Regression engine**: `arh compare` diffs a candidate run against a
  baseline report (new/resolved findings, pass/fail transitions,
  score/latency/cost deltas) with gate modes `regressions` (default),
  `failures`, `never`, and `--max-score-drop`.
- **Adapters**: `--format openai-chat` (Chat Completions `tool_calls`
  transcripts) and `--format anthropic-messages` (`tool_use`/`tool_result`
  conversations), with deterministic auto-detection and lossless handling of
  unmappable input via `metadata.adapter.notes`.
- **Reports**: JUnit XML (`--junit-out`) and SARIF 2.1.0 (`--sarif-out`)
  renderers; rule IDs shown in console and Markdown output; JSON reports
  carry `schema_version`.
- **Schema versioning**: traces/policies accept `schema_version` (major `1`);
  unknown major versions are rejected with a precise error.
- **JSON Schemas** for trace, policy, and report formats (`schemas/`).
- **Benchmark suite**: 34 seeded failure cases with a generator, a runner
  enforcing thresholds (precision/recall 1.0, byte-identical determinism,
  <50 ms/trace, metamorphic invariances, adapter equivalence, regression
  scenarios), plus `BENCHMARK-METHODOLOGY.md` and generated
  `BENCHMARK-RESULTS.md`.
- **GitHub Action** (`action.yml`): validate + optional baseline compare,
  step-summary reports, SARIF/JUnit outputs, fork-safe, no secrets.
- **CI**: 3-OS × Python 3.11-3.13 matrix, ruff, strict mypy, benchmark
  thresholds, packaging build with clean-environment install check.
- Documentation set (`docs/`), specs (`SPEC.md`, `TRACE-SPEC.md`,
  `POLICY-SPEC.md`, `ARCHITECTURE.md`, and more), and community files.

### Fixed

- **(review)** Regression loose-matching could silently cancel two findings
  with *different* rule IDs on the same step whenever any legacy finding was
  present, hiding real regressions from the CI gate. Loose matching now
  applies only when at least one side of a pair lacks a `rule_id`.
- **(review)** Safety scanning now recurses into nested lists/dicts and the
  step `error` string; unsafe content one level deep no longer evades
  detection.
- **(review)** Warning-only traces can no longer fail: unverifiable budget
  warnings (ARH-BUD-005, new ARH-BUD-006 latency, new ARH-BUD-007 cost) are
  score-neutral.
- **(review)** Malformed telemetry (negative/non-finite/mistyped latency,
  cost, tokens; non-string text/tool_name/error) is rejected at parse time.
- **(review)** `ArgSpec` patterns are compiled at policy load (precise error
  instead of a traceback), `min > max` and non-finite bounds are rejected,
  NaN values can no longer bypass range constraints, and unknown declared
  types no longer disable enum/pattern/range checks.
- **(review)** JUnit output strips XML-1.0-illegal control characters so
  strict CI consumers can always parse it; Markdown reports escape
  trace-derived fields in table cells.
- **(review)** The GitHub Action passes all inputs via `env:` bindings
  instead of interpolating `${{ inputs.* }}` into the script, closing a
  shell-injection vector.
- **(review)** CLI: `--fail-under` is bounds-checked (usage error, exit 2);
  pathologically nested JSON fails with a clean message instead of a
  `RecursionError` traceback; the module docstring documents real exit
  codes.

- v0.1.x reported type errors for **required** arguments twice (the argument
  was checked in two loops). Each argument is now checked exactly once; the
  duplicate finding is gone. Scores and verdicts are unchanged.

### Compatibility

- v0.1.x trace and policy files remain accepted; verdicts and finding
  messages are preserved. The documented nested-safety-scan fix changes one
  sample score from 70.0 to 70.83 (verdict unchanged). New report fields are
  additive.
  `arh compare` accepts v0.1.x baselines via a rule-id-agnostic fallback
  match. Exit codes and console markers are unchanged. See COMPATIBILITY.md.

## [0.1.0] - 2026-07-13

### Added

- Initial release: policy-driven trace validation (tool-call contracts,
  latency/cost budgets, unsafe-pattern detection, citation coverage),
  weighted 0-100 scoring, console/JSON/Markdown reports, `arh validate` CLI,
  35 unit/CLI tests, GitHub Actions CI (Python 3.11/3.12).
