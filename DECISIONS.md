# Architecture Decision Records

Short-form ADRs. Status of all: **accepted** (0.2.0) unless noted.

## ADR-001: Keep the zero-runtime-dependency deterministic core

The v0.1 stdlib-only core is a real differentiator: installs in seconds
anywhere (air-gapped included), no dependency conflicts with the application
under test, no Docker/Node (contrast: Inspect AI's sandbox requirement,
promptfoo's Node runtime — `research/competitive-landscape.md`). All new
features (trajectory rules, regression, adapters, SARIF/JUnit) were built
stdlib-only. Optional capabilities go in extras (`[dev]` today) and must never
leak imports into the core.

## ADR-002: Partial-order `call_order`, not exact trajectory match

Exact/golden-trajectory matching is the dominant public approach (ADK/Vertex
EXACT/IN_ORDER/ANY_ORDER, agentevals strict/unordered) and its rigidity is a
documented pain: Anthropic's eval guidance calls step-sequence checks "too
rigid"; a LangChain forum user hand-built a causal-precedence evaluator because
strict was too rigid and unordered too loose (`research/user-problems.md`).
`call_order` therefore constrains only first-call precedence between pairs of
tools that were both called; presence is a separate rule (`required_tools`).
Consequence: many valid trajectories pass, and the policy encodes only the
constraints that matter.

## ADR-003: Stable rule IDs are the regression fingerprint

Fingerprint = `(trace_id, rule_id, category, step_id)`. Messages are excluded
deliberately: they embed measured values (latency, cost, counts) that vary
legitimately between runs and would make every rerun look like a regression.
Rule IDs are permanent (never renamed, never reused), which also powers SARIF
rule metadata and documentation links. Legacy (rule-ID-less) baselines match
via a second, looser pass (COMPATIBILITY.md).

## ADR-004: The JSON validation report *is* the baseline format

`arh compare` consumes exactly what `arh validate --json-out` writes. One
format, one schema (`schemas/report.schema.json`), no separate baseline
artifact to version or migrate, and any historical report can serve as a
baseline retroactively.

## ADR-005: Adapters chosen by documented-format availability; OTel deferred

openai-chat and anthropic-messages transcripts are stable, publicly documented,
and constructible as realistic fixtures. The OpenTelemetry GenAI semantic
conventions are the strategically right long-term ingestion target but are
explicitly **Development** stability and recently moved to a dedicated repo
(`semantic-conventions-genai`) — building against them now means chasing
breaking changes (`research/competitive-landscape.md`, OTel section). Deferred
to 0.3 with a pinned semconv version. Adapters must document unmapped fields
and record unmappable input in `metadata.adapter.notes` instead of dropping it.

## ADR-006: Unverifiable budgets warn; nothing silently passes

If a policy sets `max_total_tokens` but the trace records no token usage, the
harness emits ARH-BUD-005 (warning) instead of passing the check. Direct lesson
from promptfoo's silent-pass-on-missing-threshold bug class (#9910, #9848 —
`research/user-problems.md`): a check the input cannot demonstrate compliance
with must be visible, not green.

## ADR-007: Fix the v0.1 duplicate-finding bug instead of preserving it

v0.1 checked required arguments in two loops and emitted duplicate findings for
a wrong-typed required argument. Preserving a bug for byte-compatibility of an
incorrect output would poison regression fingerprints going forward. Fixed;
scores/verdicts unaffected; documented in CHANGELOG.md and COMPATIBILITY.md.

## ADR-008: Plugin SDK deferred (no single-implementation abstractions)

The evaluator interface (PLUGIN-SPEC.md) stays a design document until a second
real evaluator class exists. Building the abstraction now would freeze an
untested interface and add surface without users.

## ADR-009: No telemetry, ever

The tool's trust proposition is local-first determinism. Zero network calls at
runtime, zero usage collection, no opt-out flags because there is nothing to
opt out of. Evidence that half-honored opt-outs destroy trust: promptfoo #9968
(`research/user-problems.md`). This is a permanent commitment, restated in
SECURITY.md and ROADMAP.md.

## ADR-010: Rule IDs shown in human output (console/Markdown)

Console and Markdown formats gained rule IDs in 0.2.0, breaking byte-level
v0.1 console output. Human-oriented formats are explicitly not a stability
surface (COMPATIBILITY.md); machine formats (JSON) evolve additively only. The
debugging value of visible rule IDs outweighs cosmetic stability.
