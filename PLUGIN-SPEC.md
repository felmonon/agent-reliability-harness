# Evaluator Plugin Specification

**Status: design proposal — not implemented in 0.2.0.**

Nothing in this document ships today. It exists so the interface can be
criticized before code exists, and to record the constraint that keeps the
core honest. Per DECISIONS.md ADR-008, the plugin SDK ships only when a second
real evaluator class exists — we do not build abstractions with a single
implementation.

## Motivation (future)

The built-in deterministic checks cover contract, trajectory, budget, safety,
grounding-shape, and completion rules. Two known needs fall outside them:

1. organization-specific deterministic rules (e.g. state-machine invariants
   over tool outputs);
2. semantic evaluations (factual support, task completion quality), which
   require a model.

## Proposed plugin declaration

A plugin would be a Python object registered under an entry point
(`agent_reliability_harness.evaluators`), declaring:

| Field | Purpose |
|---|---|
| `id` | Stable identifier, namespaced (`myorg.state-invariant`); doubles as the rule-ID prefix for its findings. |
| `version` | Plugin semver, recorded in every report it contributes to. |
| `kind` | `"deterministic"` or `"semantic"` — mandatory, surfaced in reports. |
| `config_schema` | JSON Schema for its policy configuration block. |
| `supported_trace_versions` | e.g. `["1"]`; the runner skips (loudly) on mismatch. |
| `applicable_step_types` | `["tool_call"]`, `["model_response"]`, or both. |
| `evaluate(trace, config) -> list[Finding]` | Pure function of its inputs. |

Every finding must carry: rule ID, severity, message, step ID where
applicable, evidence (what was observed), and remediation guidance — the same
contract as built-in rules.

## Semantic evaluator requirements (from the project charter)

A semantic plugin must additionally declare: provider interface, prompt
version, model version, sampling configuration, structured output schema,
retry/caching behavior, cost reporting, calibration dataset reference,
disagreement handling, and reproducibility metadata. Its tests must run
against a deterministic fake provider.

## The non-negotiable rule

**Semantic judgments are never hidden inside deterministic scores.** Reports
must keep deterministic findings and semantic findings visibly separate
(distinct `kind`, distinct score aggregation, distinct gate configuration). A
CI gate defaults to deterministic findings only; gating on semantic findings
must be an explicit opt-in.

## Shipping criteria

The SDK ships when all of these exist:

1. at least two real evaluator implementations (one deterministic, one
   semantic) built against the interface;
2. plugin findings round-trip through JSON/Markdown/JUnit/SARIF reports and
   regression fingerprints without special cases;
3. a documented template/generator for new plugins;
4. version-skew tests (old plugin + new core, and vice versa).
