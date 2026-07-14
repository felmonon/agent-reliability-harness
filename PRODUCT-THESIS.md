# Product Thesis

## Position

> The most rigorous local-first policy and trajectory-regression harness for tool-using agents.

One job, done exceptionally well: given one or more recorded agent traces, determine
exactly how the agent violated expected behavior, whether the new run regressed
against a baseline, and what changed.

## Target user

An engineer building production agents that use tools, APIs, retrieval, browsers,
code execution, or databases — and who must answer, in CI, the question
"did my model/prompt/tool/policy change break agent behavior?" without shipping
trace data to a vendor or paying per-eval model costs.

## The painful problem

An agent can reach the correct final answer while behaving unreliably: wrong tool,
wrong order, wrong arguments, duplicated irreversible actions, ignored tool errors,
leaked secrets, blown budgets, silent early termination. Final-answer evals do not
see any of this. Worse, a prompt tweak that passes a spot check can regress other
behaviors with "no diff to review, no test that went red, no signal at all"
(see `research/user-problems.md`, items on silent regressions and compound
per-step error math).

## Current alternatives and their gaps

Full profiles with sources: `research/competitive-landscape.md`;
evidence of user pain: `research/user-problems.md`; feature matrix:
`research/capability-matrix.csv`. Summary of the gap this project fills:

- **LangChain `agentevals`** has deterministic trajectory-match modes
  (strict/unordered/subset) but no policy language (no argument constraints,
  budgets, side-effect or retry rules), no baseline/regression diffing, and no CI
  gate artifacts. A LangChain forum user had to hand-build a "causal precedence"
  evaluator because strict matching is too rigid and unordered too loose.
- **Langfuse / LangSmith / Braintrust / Arize Phoenix** are observability and
  experimentation platforms, not merge gates. Langfuse maintainers directed a user
  asking for core trajectory evaluation to roll their own (discussion #5206).
  LangSmith self-hosting is Enterprise-gated; Braintrust "self-hosting" retains a
  hosted control plane.
- **Promptfoo** has the best CI ergonomics but trajectory assertions are young
  (wildcard arg matching still a feature request, #9842) and it has documented
  silent-pass threshold footguns (#9910, #9848) and telemetry opt-out issues (#9968).
- **DeepEval** has the deepest agent-metric list, but flagship trajectory metrics
  are LLM-judge-based (non-deterministic, costly in CI) and repeatedly broke on
  internal template bugs (#2859, #2817, #2807). Users are asking it for exactly the
  deterministic tool-permission checks this harness ships (#2825).
- **Inspect AI** is a full eval platform (excellent, heavyweight): running agentic
  evals needs sandboxing infra; it evaluates by executing tasks, not by validating
  already-recorded traces against a policy.
- **OpenAI Evals** is effectively frozen for custom code and its hosted platform is
  being sunset (Oct/Nov 2026). "OpenAI Frontier Evals" is not a coherent public
  product to compare against.

No public tool combines: declarative trajectory *policy* (not golden trajectories)
+ deterministic verdicts + baseline regression diff + CI gate + zero-dependency
local operation.

## Unique advantage

1. **Zero-runtime-dependency deterministic core.** `pip install`, no Docker, no
   Node, no vendor account, no model calls, no network, no clock reads, no
   telemetry. Reports are byte-identical across runs (measured, enforced in CI).
2. **Policy-as-code constraints instead of brittle golden trajectories.**
   Anthropic's own eval guidance warns that checking "a sequence of tool calls in
   the right order ... is too rigid" (`research/competitive-landscape.md`,
   Anthropic section). ARH policies express *constraints*: allow/forbid lists,
   partial-order `call_order` (first-call precedence, uncalled tools vacuous),
   call-count bounds, argument value constraints, retry and duplicate-side-effect
   rules, budgets, completion requirements. Many valid trajectories pass; the
   specific violations engineers care about fail.
3. **Stable rule IDs (`ARH-*`) on every finding**, giving deterministic regression
   fingerprints, SARIF code-scanning annotations, and documentation links.
4. **Two-command regression gate.** `arh validate --json-out baseline.json`, then
   `arh compare --baseline baseline.json ...` reports new/resolved findings,
   pass→fail transitions, score/latency/cost deltas, and fails CI only on
   configurable, meaningful regressions.
5. **CI-native artifacts.** JSON, Markdown, JUnit XML, SARIF; a composite GitHub
   Action that needs no secrets and is fork-safe.

## Why this repository can win

The surface is small enough to be provably correct: ~3.4k lines of typed,
dependency-free Python (docstrings included); every claim is backed by a seeded public benchmark
(`benchmarks/`, 34 cases) that would expose false positives or misses, and the
benchmark thresholds run in CI so the claims cannot silently rot.

## Explicit non-goals

- Hosted dashboards, web UI, or any server component.
- LLM-as-judge inside the deterministic core (semantic evaluators, if ever added,
  will be a clearly separated optional extra — see PLUGIN-SPEC.md, ROADMAP.md).
- Running, orchestrating, or sandboxing agents. The harness evaluates recorded traces.
- Replacing observability platforms (Langfuse/Phoenix are complementary).
- OpenTelemetry ingestion in v0.2 (GenAI semconv is Development-status; planned).
- Telemetry of any kind, ever.

## Adoption wedge

A team with existing OpenAI Chat Completions or Anthropic Messages transcripts can
get a useful failure report in under five minutes (`docs/quickstart.md`) and a CI
regression gate with one copy-paste workflow (`docs/ci.md`) — no re-instrumentation,
no account, no new trace format required (adapters + `--format auto`).

## Long-term direction (planned, not implemented)

Ordered in `ROADMAP.md`: OpenTelemetry GenAI adapter (pinned semconv version);
evaluator plugin SDK once a second evaluator class proves the interface; optional
semantic evaluators (factual support, task completion) as a separate extra with
deterministic fake-provider tests; pass^k multi-run consistency analysis; trace v2
with multi-agent handoffs.

## Measurable definition of "best"

Enforced by `benchmarks/run.py` (CI-failing thresholds) and CI jobs:

- precision = 1.0 and recall = 1.0 on the 34-case seeded failure suite
  (deterministic checks on seeded cases must be perfect; measured: 34/34, 0 FP, 0 FN);
- byte-identical reports across repeated runs (measured: true);
- median validation < 50 ms/trace (measured: ~0.03 ms/trace);
- clean install and first useful result in under five minutes on a fresh machine;
- provider-neutral behavior: the same conversation via the OpenAI and Anthropic
  adapters yields identical verdicts (measured: true).

Scope caveat: these numbers prove detector correctness on seeded, deterministically
detectable failures — they are not a claim about semantic failure modes
(BENCHMARK-METHODOLOGY.md, "Explicitly out of scope").

## Evidence users need this

From `research/user-problems.md` (each with source URL there): Langfuse discussion
#5206 (trajectory evaluation requested as core, answered "roll your own");
DeepEval #2825 (deterministic tool-permission metric requested); promptfoo #9842
(trajectory arg-matching flexibility requested); LangChain forum #3351 (hand-built
causal-precedence evaluator); eval-view positioning ("merge-time regression gate is
a different job from observability"); promptfoo #2729 (nondeterminism at
temperature 0 undermines trust — determinism must come from the checker);
Anthropic and ADK documentation gaps around loop detection and per-step grounding.
