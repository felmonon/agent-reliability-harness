# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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

- v0.1.x reported type errors for **required** arguments twice (the argument
  was checked in two loops). Each argument is now checked exactly once; the
  duplicate finding is gone. Scores and verdicts are unchanged.

### Compatibility

- v0.1.x trace and policy files produce identical scores, verdicts, and
  finding messages (pinned by golden tests). New report fields are additive.
  `arh compare` accepts v0.1.x baselines via a rule-id-agnostic fallback
  match. Exit codes and console markers are unchanged. See COMPATIBILITY.md.

## [0.1.0] - 2026-07-13

### Added

- Initial release: policy-driven trace validation (tool-call contracts,
  latency/cost budgets, unsafe-pattern detection, citation coverage),
  weighted 0-100 scoring, console/JSON/Markdown reports, `arh validate` CLI,
  35 unit/CLI tests, GitHub Actions CI (Python 3.11/3.12).
