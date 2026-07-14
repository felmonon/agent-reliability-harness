# Architecture

## Module map

```
src/agent_reliability_harness/
├── models.py        # typed dataclasses + defensive JSON parsing:
│                    #   Trace/Step, Policy (+ ToolSchema/ArgSpec/Budgets/
│                    #   GroundingPolicy/SequencePolicy/ErrorHandlingPolicy/
│                    #   CompletionPolicy), Finding, TraceReport
├── rules.py         # stable rule registry (ARH-* ids, severity, remediation)
├── validator.py     # the seven deterministic checks + scoring + validate_trace()
├── regression.py    # baseline-vs-candidate diff, fingerprints, gates, renderers
├── report.py        # console / JSON / Markdown / JUnit XML / SARIF renderers
├── cli.py           # argparse CLI: `arh validate`, `arh compare`
└── adapters/
    ├── __init__.py          # format registry, detect_format(), normalize()
    ├── openai_chat.py       # OpenAI Chat Completions transcripts -> trace v1
    └── anthropic_messages.py# Anthropic Messages conversations   -> trace v1
```

Supporting assets: `schemas/` (JSON Schema for trace/policy/report),
`samples/`, `benchmarks/` (seeded cases + generator + threshold-enforcing
runner), `tools/generate_rules_doc.py` (docs/rules.md is generated from the
registry), `action.yml` (composite GitHub Action).

## Data flow

```
 capture / import trace                (user's agent stack, any provider)
          │
          ▼
 adapters.normalize()                  --format auto|arh|openai-chat|anthropic-messages
          │                            unmappable input -> metadata.adapter.notes
          ▼
 models.Trace.from_dict()              schema_version check, field-precise errors
 models.Policy.from_dict()            (same for the policy file)
          │
          ▼
 validator.validate_trace()            7 deterministic checks:
          │                            schema · budget · safety · grounding ·
          │                            sequence · flow · completion
          ▼
 TraceReport (findings w/ rule IDs, score, verdict)
          │
          ├────────────► report.render_console/json/markdown/junit/sarif
          │                            (byte-deterministic)
          ▼
 regression.compare_reports(baseline, candidate)
          │                            fingerprint: (trace_id, rule_id,
          │                             category, step_id); messages excluded
          ▼
 regression.evaluate_gate()            regressions | failures | never
          │
          ▼
 exit code 0/1                         (CI gate; GitHub Action wraps this)
```

## Design principles

1. **Deterministic core.** No network, no clock reads, no randomness, no model
   calls, no telemetry anywhere in `src/`. Identical inputs produce
   byte-identical reports (enforced by tests and benchmark thresholds). The
   JUnit `time` attribute is the trace's recorded latency, not wall time.
2. **Provider neutrality by isolation.** Provider-specific knowledge lives only
   in `adapters/`. The validator sees canonical traces exclusively; nothing in
   the core imports an adapter.
3. **Additive-only schema evolution.** v1 extends v0.1.x without changing any
   existing field's meaning. Missing `schema_version` = `"1"`; unknown major
   versions are rejected loudly. A future breaking major bump ships a migration.
4. **Score stability via renormalization.** Category weights
   (schema .3, budget .3, safety .25, grounding .15, sequence .25, flow .2,
   completion .1) are renormalized over *applicable* categories only. A legacy
   policy never activates the new categories, so its scores are unchanged.
5. **Severity vs score are distinct.** Any error-severity finding fails the
   trace regardless of score; warnings/infos never fail it alone. The 0-100
   score exists for trend/regression comparison, not as the pass criterion.
6. **Fail loudly, never silently.** Unverifiable constraints warn
   (ARH-BUD-005); malformed input errors name the file and field; invalid policy
   regexes raise before scanning.
7. **Evidence-first.** Every capability claim maps to a test or benchmark
   (ACCEPTANCE-TESTS.md). BENCHMARK-RESULTS.md is machine-generated only.

## Dependency policy

- **Runtime: zero dependencies.** Standard library only (`dataclasses`, `re`,
  `json`, `argparse`, `xml.sax.saxutils`, `urllib.parse`). This is a deliberate
  differentiator: installable anywhere, air-gapped, no dependency conflicts with
  the application under test.
- **Dev extras (`pip install -e ".[dev]"`):** `mypy` (strict), `ruff`,
  `jsonschema` (schema tests only; suite skips gracefully without it), `build`.
- Optional future extras (semantic evaluators, OTel adapter) must be separate
  extras and must not leak imports into the core (ROADMAP.md).
