# Benchmark Methodology

This document defines what the benchmark suite measures, how the numbers in
`BENCHMARK-RESULTS.md` are produced, and — just as importantly — what the
numbers do **not** claim.

## Design goal

The benchmark exists to *disprove* our own claims. The harness claims to
deterministically detect specific reliability failure modes in agent traces.
So the benchmark seeds exactly those failure modes into otherwise-valid
traces, by construction, and checks that the harness reports each seeded
failure — and nothing else.

## Structure

- `benchmarks/cases/*.json` — 34 static, reviewable cases. Each case contains
  a policy, a trace, a description of the seeded mutation, and the expected
  outcome: the pass/fail verdict plus the exact multiset of expected
  error/warning findings as `(severity, rule_id, step_id)` triples.
- `benchmarks/tools/generate_cases.py` — the deterministic generator. Every
  case is a single named mutation (or a small named set) of one valid base
  refund workflow, so expectations are known by construction, not by running
  the tool on itself and recording the answer.
- `benchmarks/run.py` — the runner. Exit code 1 if any threshold is breached,
  so CI fails on benchmark regressions.

## Covered failure modes

Tool selection: wrong tool, forbidden tool, missing required tool, unlisted
tool (and the allow-unlisted control). Arguments: missing required, wrong
type, enum violation, pattern violation, range violation, undeclared
argument. Ordering: partial-order violation, correct-answer-but-unacceptable-
trajectory. Side effects and retries: duplicate side effect, retry storm,
ignored tool error, legitimate retry (control). Completion: premature
termination, errored final response, failure to terminate, empty trace.
Grounding: missing citations, coverage below minimum, malformed citation,
non-http(s) scheme. Safety: secret exposure, prompt-injection propagation
through tool output into tool arguments. Budgets: total/step latency, cost,
tokens, and the unverifiable-token-budget warning. Structure: duplicate step
IDs.

## Explicitly out of scope (and why)

These failure modes from the project charter are **not** claimed and **not**
measured, because they cannot be decided deterministically from a single
recorded trace:

- **fabricated tool outputs / unsupported claims / factual grounding** —
  require semantic judgment; planned as optional, clearly-labeled semantic
  evaluators (see ROADMAP.md), never hidden inside deterministic scores;
- **nondeterministic agent behavior / flaky scenarios** — require multiple
  runs of the *agent* (pass^k-style analysis); the harness evaluates recorded
  traces and compares runs, it does not execute agents;
- **multi-agent handoff failures and state-machine invariants** — the v1
  trace schema has no handoff/span-tree model; deferred (see ROADMAP.md);
- **"succeeded only by accident"** — partially covered: the
  `correct_answer_bad_trajectory` case shows a right answer failing on
  trajectory rules; intent-level judgment remains out of scope.

## Metrics and thresholds

For every case, expected vs. actual findings are compared as multisets of
`(severity, rule_id, step_id)`; info-severity findings are excluded.

- **TP** — expected finding present; **FN** — expected finding absent;
  **FP** — actual error/warning finding not expected.
- **precision** = TP/(TP+FP), **recall** = TP/(TP+FN).
- Threshold: precision = 1.0 and recall = 1.0. All checks are deterministic;
  on seeded synthetic cases anything less than perfect is a bug, not noise.
  This threshold is honest *because* the cases are synthetic and seeded: it
  is a correctness test of the detector, not a claim about real-world traces.
- **Determinism** — the full-suite JSON report must be byte-identical across
  repeated runs (threshold: exact equality). CLI-level byte-determinism is
  additionally covered in the unit suite.
- **Performance** — median wall time per trace across 20 full-suite
  iterations, plus tracemalloc peak. Threshold: median < 50 ms/trace.
- **Metamorphic invariances** — for every case: renaming the trace ID,
  adding unrelated step metadata, and round-tripping the policy through
  sorted-key JSON must not change any finding.
- **Adapter equivalence** — the same conversation recorded as an OpenAI chat
  transcript and an Anthropic messages transcript must produce identical rule
  verdicts under the same policy.
- **Regression scenarios** — identical runs must pass the gate; seeded
  regressions (duplicate side effect, order violation, secret exposure) must
  fail it; a fix over a bad baseline must pass it.

## Fairness rules for external comparisons

`BENCHMARK-RESULTS.md` contains **no numbers for other tools**. We do not
publish comparative numbers unless the same cases, the same hardware, and an
equivalent policy expressed in the other tool's native configuration are used
and published for review. Capability differences against other tools are
documented qualitatively, with sources, in `research/competitive-landscape.md`.

## Reproducing

```bash
python -m pip install -e .
python benchmarks/tools/generate_cases.py   # no-op unless the generator changed
python benchmarks/run.py --write            # rewrites BENCHMARK-RESULTS.md
```

Numbers vary with hardware; thresholds are set loosely enough to hold on any
recent machine and in CI.

## Known limitations of the current suite

- All 34 cases derive from a single refund workflow and one base policy
  family. This is sufficient for detector-correctness claims (the checks are
  structural, not domain-specific) but is not evidence of real-world
  precision across diverse workloads. Adding independently authored
  workflows is tracked in ROADMAP.md.
- 6 of the 34 cases are expected-pass controls; 28 seed failures. The
  precision figure therefore leans on the exactness requirement (no
  unexpected findings in ANY case) rather than a large clean corpus.
- The 50 ms/trace performance threshold is a catastrophic-regression guard,
  not a competitive benchmark; measured medians are ~3 orders of magnitude
  below it.
