# Agent Reliability Harness

A provider-neutral, local-first reliability and regression-testing harness for
tool-using AI agents. It validates recorded agent execution traces against
declarative policies (tool-call contracts, trajectory rules, budgets, unsafe
patterns, grounding), produces deterministic findings with stable rule IDs,
and compares candidate runs against a saved baseline so CI fails only on real
regressions.

The core has **zero runtime dependencies**, makes **no network calls**, sends
**no telemetry**, and produces **byte-identical reports** for identical input.

## Why this exists

An agent can reach the correct final answer while still behaving unreliably.
It may:

- select the wrong tool, or skip a required one;
- use correct tools in the wrong order;
- pass invalid or out-of-range arguments;
- repeat an irreversible action (double refund, duplicate email);
- ignore a tool failure and answer anyway;
- get stuck in a retry storm;
- stop before finishing, or fail to terminate;
- return facts without citations;
- leak secrets or propagate prompt-injection text;
- blow past latency, cost, or token budgets;
- regress silently after a model, prompt, or tool change.

Final-answer evals miss all of this. This harness evaluates the **trajectory**,
and turns each of these concerns into a versioned policy rule with a stable ID.

## 60-second example

```bash
python -m pip install -e .   # not yet on PyPI; install from a checkout

arh validate --policy samples/policy_trajectory.json \
  samples/traces/refund_workflow_pass.json \
  samples/traces/refund_workflow_double_refund.json
```

The second trace ends with a perfectly plausible final answer — and still
fails, because the trajectory was unacceptable:

```text
[FAIL] refund-workflow-1002  (agent=refund-copilot, workflow=refund)
  score=84.5/100  policy=refund-workflow-v1  latency=1300ms  cost=$0.0080
  - [ERROR  ] [flow     ] ARH-FLW-003: duplicate side effect: tool 'issue_refund' was called again with identical arguments after already succeeding (step=s3)
  - [ERROR  ] [sequence ] ARH-SEQ-001: required tool 'check_refund_eligibility' was never called
  - [ERROR  ] [sequence ] ARH-SEQ-004: tool 'issue_refund' was called 2 times, above max_calls of 1
  - [ERROR  ] [sequence ] ARH-SEQ-003: call order violation: first call of 'lookup_order' must precede first call of 'issue_refund' (step=s1)
```

Exit code `0` when everything passes, `1` on failure, `2` on usage errors —
usable as a CI gate as-is.

## Regression gates

Save a baseline once, then gate future runs on *changes*, not absolutes:

```bash
arh validate --policy samples/policy_trajectory.json \
  samples/traces/refund_workflow_pass.json \
  --json-out baseline.json --quiet

arh compare --baseline baseline.json \
  --policy samples/policy_trajectory.json \
  samples/traces/refund_workflow_pass.json \
  samples/traces/refund_workflow_double_refund.json
```

```text
GATE: FAIL
  - 4 new error finding(s): refund-workflow-1002:ARH-FLW-003, refund-workflow-1002:ARH-SEQ-001, refund-workflow-1002:ARH-SEQ-003, refund-workflow-1002:ARH-SEQ-004
  - added trace 'refund-workflow-1002' fails
```

The gate fails on new error findings, pass→fail transitions, and added failing
traces — resolved findings and unchanged failures don't re-alarm. Gate modes:
`--fail-on regressions` (default), `failures`, `never`; add `--max-score-drop`
for score-based gating. See [docs/regression-testing.md](docs/regression-testing.md).

## What it checks

Seven deterministic categories; every finding carries a stable rule ID
(`ARH-<CATEGORY>-<NNN>`), an expected/observed pair, and remediation guidance:

| Category | Rules | Examples |
|---|---|---|
| schema | ARH-SCH-001..010 | unlisted tool, missing/mistyped args, enum/pattern/range violations |
| budget | ARH-BUD-001..005 | step/total latency, cost, token budgets |
| safety | ARH-SAF-001 | prompt-injection phrases, secret-like strings (policy regexes) |
| grounding | ARH-GRD-001..003 | missing citations, low coverage, malformed citation URLs |
| sequence | ARH-SEQ-001..005 | required/forbidden tools, partial-order violations, call counts |
| flow | ARH-FLW-001..003 | ignored tool errors, retry storms, duplicate side effects |
| completion | ARH-CMP-001..002 | missing final response, failure to terminate |

Full reference: [docs/rules.md](docs/rules.md). Ordering rules are a
deliberate **partial order** (constraints), not an exact golden-trajectory
match — agents can legitimately reach a goal via different paths.

## Trace formats

`arh validate` accepts (auto-detected, or forced with `--format`):

- **arh** — the canonical JSON trace format ([TRACE-SPEC.md](TRACE-SPEC.md));
- **openai-chat** — OpenAI Chat Completions message lists with `tool_calls`;
- **anthropic-messages** — Anthropic Messages conversations with
  `tool_use`/`tool_result` blocks.

Adapters never guess: fields a transcript format cannot carry (latency, cost,
tokens) are left unset, which marks the dependent checks *not applicable*
instead of silently passing them. Unparseable input is recorded in the trace's
metadata, not dropped. See [docs/adapters.md](docs/adapters.md).

## Reports

Console, JSON (doubles as the regression baseline), Markdown (PR-comment
ready), JUnit XML, and SARIF 2.1.0 (GitHub code-scanning annotations). All
renderers are deterministic: identical input produces byte-identical output —
no timestamps, no randomness, no clock reads.

## CI

```yaml
- uses: felmonon/agent-reliability-harness@main
  with:
    policy: policies/agent-policy.json
    traces: traces/*.json
    baseline: baselines/main.json   # optional: gate on regressions
```

The action writes JSON/Markdown/JUnit/SARIF reports, appends the Markdown
summary to the workflow step summary, and fails according to the gate. It uses
no secrets and is fork-safe. Full reference and SARIF/JUnit upload examples:
[docs/ci.md](docs/ci.md).

## Design principles

- **Zero runtime dependencies.** `pip install` adds nothing to your
  application's dependency graph.
- **Deterministic core.** No model calls, no network, no telemetry, no clock
  reads. Semantic (model-graded) evaluation is a planned, clearly separated
  optional extra — never hidden inside deterministic scores ([ROADMAP.md](ROADMAP.md)).
- **Additive schema evolution.** v0.1.x traces, policies, and baselines work
  unchanged; unknown major schema versions are rejected loudly
  ([COMPATIBILITY.md](COMPATIBILITY.md)).
- **Evidence over claims.** The benchmark suite seeds 34 known failure cases
  and measures detection: currently 34/34, precision 1.0, recall 1.0, 0 false
  positives/negatives, byte-identical repeat runs, ~0.03 ms per trace. Those
  numbers cover *seeded, deterministically detectable* failures only — scope
  and limits are documented in [BENCHMARK-METHODOLOGY.md](BENCHMARK-METHODOLOGY.md),
  results in [BENCHMARK-RESULTS.md](BENCHMARK-RESULTS.md).

## Documentation

| Doc | What it covers |
|---|---|
| [docs/quickstart.md](docs/quickstart.md) | Five minutes from install to a regression gate |
| [docs/concepts.md](docs/concepts.md) | Traces, policies, findings, scores, baselines |
| [docs/policy-cookbook.md](docs/policy-cookbook.md) | Copy-paste recipes for every rule type |
| [docs/adapters.md](docs/adapters.md) | OpenAI/Anthropic transcript ingestion, field mapping |
| [docs/regression-testing.md](docs/regression-testing.md) | Baselines, fingerprints, gates |
| [docs/ci.md](docs/ci.md) | GitHub Action reference and workflows |
| [docs/rules.md](docs/rules.md) | Every rule ID with remediation |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Error messages and fixes |
| [TRACE-SPEC.md](TRACE-SPEC.md) / [POLICY-SPEC.md](POLICY-SPEC.md) | Normative formats |
| [ARCHITECTURE.md](ARCHITECTURE.md) / [DECISIONS.md](DECISIONS.md) | Design and ADRs |

## Compatibility

v0.1.x trace and policy files produce identical scores, verdicts, and finding
messages under this version (pinned by golden tests). New fields are additive.
Details: [COMPATIBILITY.md](COMPATIBILITY.md).

## Development

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m unittest discover -s tests   # 165+ tests
ruff check src tests benchmarks
mypy src                               # strict
python benchmarks/run.py               # thresholds enforced
```

CI runs the suite on Linux/macOS/Windows across Python 3.11-3.13, plus
packaging checks. Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Author

[Felmon Fekadu](https://felmon.tech/proof)
[GitHub](https://github.com/felmonon)

## License

MIT
