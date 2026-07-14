# Product Specification (v0.2.0)

Shipped features only. Each section states the user problem, behavior, surface,
formats, compatibility, security, tests, acceptance, and non-goals. Normative
details live in TRACE-SPEC.md and POLICY-SPEC.md. Future work: ROADMAP.md.

---

## 1. Canonical trace schema (v1)

- **Problem:** trajectory checks need one normalized, versioned representation of
  what an agent did.
- **Behavior:** a trace is `{trace_id, agent_name, workflow, steps[]}` plus
  optional `schema_version`, `source`, `metadata`. Steps are `tool_call` or
  `model_response` with optional latency/cost/tokens/status/error/citations.
  Missing `schema_version` means `"1"`; unknown major versions are rejected with a
  precise error. v0.1.x files are a strict subset — no migration needed.
- **Surface:** `Trace.from_dict`, `Step.from_dict`; JSON Schema `schemas/trace.schema.json`.
- **Compatibility:** additive only. **Security:** trace content is treated as data,
  never executed. **Tests:** `tests/test_models.py`, `tests/test_adversarial.py`,
  `tests/test_schemas.py`. **Acceptance:** all v0.1 samples parse and score identically
  (`tests/test_compat_golden.py`). **Non-goals:** span trees / multi-agent handoffs (v2).

## 2. Policy schema (v1): policy-as-code trajectory rules

- **Problem:** teams need to declare expected agent behavior without pinning a
  brittle golden trajectory.
- **Behavior:** sections `allowed_tools` (arg specs: legacy type strings or
  `{type, enum, pattern, min, max}`; `side_effect`, `min_calls`, `max_calls`),
  `budgets` (latency/step-latency/cost/tokens), `unsafe_patterns`, `grounding`
  (citations, coverage, URL validity), `sequence` (required/forbidden tools,
  partial-order `call_order`), `error_handling` (`require_retry_on_error`,
  `max_attempts`), `completion` (`require_final_response`, `max_steps`),
  `allow_unlisted_tools`. Malformed policies fail with field-precise `ValueError`s.
- **Surface:** `Policy.from_dict`; JSON Schema `schemas/policy.schema.json`; POLICY-SPEC.md.
- **Compatibility:** v0.1 policies produce byte-identical scores (inapplicable new
  categories renormalize out). **Tests:** `tests/test_argspec.py`,
  `tests/test_trajectory_rules.py`, `tests/test_adversarial.py`.
  **Acceptance:** every rule has a seeded benchmark case. **Non-goals:** custom
  evaluator plugins (PLUGIN-SPEC.md, design only).

## 3. Deterministic evaluators + rule registry

- **Problem:** findings must be repeatable, explainable, and stable across runs.
- **Behavior:** seven check categories (schema, budget, safety, grounding,
  sequence, flow, completion). No model calls, network, clock, or randomness.
  Every finding carries a stable rule ID (`ARH-SCH-001` … `ARH-CMP-002`,
  registry in `src/agent_reliability_harness/rules.py`, reference in
  `docs/rules.md`), severity, message, optional expected/observed/remediation.
- **Surface:** `validate_trace(trace, policy, fail_under)` → `TraceReport`.
- **Compatibility:** rule IDs never change meaning; retired IDs never reused.
- **Tests:** `tests/test_validator.py`, `tests/test_trajectory_rules.py`;
  benchmark thresholds enforce P=R=1.0 on seeded cases.
- **Non-goals:** semantic judgments (never hidden inside deterministic scores).

## 4. Regression engine (`arh compare`)

- **Problem:** teams need CI to fail on *meaningful regressions*, not on
  pre-existing failures or measured-value noise.
- **Behavior:** compares two validation reports; fingerprints findings as
  `(trace_id, rule_id, category, step_id)` (messages excluded — they contain
  measured values); reports new/resolved findings, pass↔fail transitions,
  added/removed traces, score/latency/cost deltas. Gates: `regressions` (default:
  new error findings, pass→fail, added failing traces, optional
  `--max-score-drop`), `failures`, `never`. Legacy v0.1 baselines without
  `rule_id` match via a second, looser pass.
- **Surface:** `arh compare --baseline R [--candidate R | --policy P traces...]`
  `[--fail-on ...] [--max-score-drop N] [--json-out] [--md-out]
  [--candidate-json-out]`; API `compare_reports`, `evaluate_gate`.
- **Tests:** `tests/test_regression.py`, `tests/test_cli_compare.py`,
  `benchmarks/run.py` regression scenarios. **Acceptance:** identical runs pass;
  seeded regressions fail; fixes pass. **Non-goals:** multi-run statistical
  analysis (pass^k) — planned.

## 5. Provider adapters

- **Problem:** teams already have OpenAI/Anthropic transcripts; they should not
  re-instrument to try the harness.
- **Behavior:** `--format auto|arh|openai-chat|anthropic-messages` with
  deterministic detection. OpenAI: `tool_calls`/legacy `function_call`/`role:
  "tool"` mapping, JSON argument parsing (failures recorded, not dropped).
  Anthropic: `tool_use`/`tool_result` blocks, `is_error → status: "error"`,
  text-block citations. Both record unmappable input under
  `metadata.adapter.notes`. Fields the formats cannot carry (latency, cost,
  tokens) stay unset so dependent checks are *not applicable* rather than
  silently passed (documented in `docs/adapters.md`).
- **Tests:** `tests/test_adapters.py` with realistic fixtures; benchmark adapter-
  equivalence check (same conversation, both formats → identical verdicts).
- **Non-goals:** OTel GenAI, LangGraph (planned; fixtures required first).

## 6. Reports

- **Behavior:** console (human), JSON (machine; doubles as the baseline format),
  Markdown (PR comment), JUnit XML (CI test publishing), SARIF 2.1.0 (code
  scanning, with rule metadata, levels, artifact locations, partial
  fingerprints). All renderers byte-deterministic; findings sorted stably;
  no timestamps anywhere.
- **Surface:** `--json-out/--md-out/--junit-out/--sarif-out`; API `render_*`.
- **Tests:** `tests/test_report.py`, `tests/test_report_formats.py`,
  determinism tests in `tests/test_cli_compare.py`. **Non-goals:** HTML report (planned).

## 7. CLI

- **Behavior:** `arh validate` and `arh compare`; `arh --version`. Exit codes:
  `0` pass/gate pass; `1` at least one failure / gate failure / invalid input
  file (with an `error: ...` message); `2` command-line usage errors (argparse).
  All error messages name the offending file/field.
- **Tests:** `tests/test_cli.py`, `tests/test_cli_compare.py`, `tests/test_adversarial.py`.

## 8. GitHub Action (`action.yml`)

- **Behavior:** composite action; installs the package from the action path, runs
  validate (+ compare when `baseline` input set), writes JSON/MD/JUnit/SARIF,
  appends Markdown to the step summary, exposes report paths as outputs, fails
  per the gate. Uses no secrets; safe on forks; no network beyond pip install.
- **Docs:** `docs/ci.md` (includes SARIF upload and artifact examples).
- **Acceptance:** CI smoke jobs exercise the same command paths on 3 OSes.

## 9. Benchmarks

- **Behavior:** 34 seeded, reviewable cases + deterministic generator + runner
  with CI-failing thresholds (precision/recall 1.0, byte-determinism, <50 ms/trace,
  metamorphic invariances, adapter equivalence, regression scenarios).
  `BENCHMARK-RESULTS.md` is generated only by the runner.
- **Fairness:** no comparative numbers against other tools without identical
  published conditions (BENCHMARK-METHODOLOGY.md).
