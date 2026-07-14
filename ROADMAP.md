# Roadmap

Everything below is **planned, not implemented**, unless it links to shipped
code. Order reflects current intent and may change with user feedback; nothing
here is a commitment to a date.

## 0.2.x — hardening (current line)

- Resolve independent-review findings; act on early-user issues.
- Additional adapter fixtures from real-world transcripts as they arrive.

## 0.3 — ingestion and reporting breadth

- **OpenTelemetry GenAI adapter** (planned): ingest OTLP/JSON spans using the
  GenAI semantic conventions, pinned to a specific `semantic-conventions-genai`
  release because the conventions are Development-status (ADR-005). Includes
  documented attribute mapping and skip-loudly behavior for absent Opt-In
  fields (`gen_ai.tool.call.arguments` etc.).
- **Evaluator plugin SDK** (planned): ships only per the criteria in
  PLUGIN-SPEC.md — a second real evaluator class must exist first (ADR-008).
- **HTML report** (planned): a static, self-contained debugging page
  (trajectory timeline, findings with evidence, baseline diff) — a debugging
  interface, not a dashboard.
- **LangGraph adapter** (planned, contingent on realistic fixtures and stable
  documented format).

## 0.4 — semantics and statistics

- **Optional semantic evaluators** (planned): factual support, task
  completion, argument appropriateness — as a separate extra
  (`pip install agent-reliability-harness[semantic]`), never in the
  deterministic core, with provider interface, prompt/model versioning,
  structured outputs, cost reporting, calibration set, and deterministic
  fake-provider tests. Reports and gates keep semantic findings visibly
  separate (PLUGIN-SPEC.md).
- **pass^k consistency analysis** (planned): compare k runs of the same
  scenario set to expose flaky agent behavior invisible to single runs
  (motivated by tau-bench's pass^k findings, `research/user-problems.md`);
  extends `arh compare` to accept multiple candidate reports.
- **Flaky-scenario detection** across historical baselines (planned).

## Trace v2 exploration (no timeline)

- Multi-agent handoffs, span parent/child relationships, artifacts and side
  effect declarations, redacted-field markers. Requires a major schema bump and
  therefore an automated migration (COMPATIBILITY.md).

## Explicitly out of scope — permanently

- Hosted dashboards, SaaS control planes, or any server component.
- Telemetry of any kind (ADR-009).
- Running/orchestrating/sandboxing agents; the harness evaluates recorded
  traces and compares runs.
- LLM-as-judge inside the deterministic core.
- Publishing comparative benchmark numbers against other tools without
  identical, published conditions (BENCHMARK-METHODOLOGY.md).
