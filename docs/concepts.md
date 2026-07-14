# Concepts

## The problem: trajectories, not answers

A tool-using agent can produce the right final answer through an unacceptable
path: refunding twice, skipping a verification step, ignoring a failed tool
call, or leaking a secret along the way. Final-answer evaluation cannot see
any of that. The harness evaluates the **recorded trajectory** — every tool
call and response — against an explicit policy.

## Traces and steps

A **trace** is one recorded agent run: `trace_id`, `agent_name`, `workflow`,
and an ordered list of **steps**. A step is either a `tool_call` (tool name +
arguments + optional output/status/error) or a `model_response` (text +
optional citations). Steps carry optional latency, cost, and token counts.
Normative spec: [TRACE-SPEC.md](../TRACE-SPEC.md). Traces come from your own
logging (canonical format) or from provider transcripts via
[adapters](adapters.md).

## Policies

A **policy** declares what a correct run looks like: which tools are allowed
and with what argument contracts, which are required or forbidden, their
relative order, retry/side-effect rules, completion requirements, budgets,
unsafe content patterns, and grounding requirements. Policies are versioned
JSON (see [POLICY-SPEC.md](../POLICY-SPEC.md)) and belong in your repo, next
to your prompts.

## Checks and categories

Validation runs seven independent deterministic check categories: `schema`,
`budget`, `safety`, `grounding`, `sequence`, `flow`, `completion`. A category
that the policy doesn't configure (or the trace can't exercise) is **not
applicable** — it neither passes nor fails, and its score weight is
redistributed. That's why a v0.1.x policy scores identically under v0.2.0.

## Findings, severities, and the score

Checks emit **findings**: `error` (fails the trace), `warning` (surfaced, does
not fail), `info` (advisory). Each finding has a stable `rule_id`
([reference](rules.md)), a message, an optional `step_id`, and
`expected`/`observed` evidence.

Separately, each applicable category yields a 0-100 score; the weighted
average is the trace **score**. A trace passes when it has **no error
findings** and its score is at or above `--fail-under` (default 70). The score
is a trend signal; the error findings are the contract.

## Ordering: constraints, not golden paths

`sequence.call_order` is a **partial order**: for each pair of listed tools
that were both called, the earlier-listed tool's *first* call must precede the
later one's. Tools not called don't violate order (use `required_tools` to
force presence). This deliberately avoids exact-trajectory matching, which
punishes legitimate alternative paths.

## Baselines and gates

Any JSON validation report doubles as a **baseline**. `arh compare` diffs a
candidate run against it: new findings, resolved findings, pass/fail
transitions, score/latency/cost deltas. The **gate** decides the exit code —
by default it fails only on *regressions* (new error findings, pass→fail,
added failing traces), so a known-failing suite doesn't re-alarm on every run.
Details: [regression-testing.md](regression-testing.md).

## Determinism

The core never calls a model, the network, a clock, or a random source.
Identical input produces byte-identical reports — verified by tests and the
benchmark suite. This is what makes findings diffable, cacheable, and
trustworthy as CI signal. Semantic (model-graded) evaluation is planned as an
explicitly separated optional layer ([ROADMAP.md](../ROADMAP.md)); it will
never be blended into deterministic scores.
