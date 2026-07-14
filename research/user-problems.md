# Evidenced User Problems in Agent Evaluation & Testing

Research date: 2026-07-14. Each pain point below is grounded in a specific public source (GitHub issue/discussion, forum thread, or practitioner write-up), collected via primary-source research. The final column maps each problem to the harness capability that addresses it: **policy rules**, **deterministic evaluators**, **regression compare**, **CI gate**, **local-first**, or **future/semantic** (out of deterministic scope; candidate for optional semantic evaluators or roadmap).

Sources with quotes are catalogued in `source-ledger.md`.

---

1. **No first-class trajectory evaluation in mainstream OSS platforms.** A Langfuse user asked for trajectory evaluation "as core" — verifying the agent took the expected path and counting node revisits; the maintainer's answer was effectively roll-your-own eval function or LLM judge.
   Source: https://github.com/orgs/langfuse/discussions/5206
   → **policy rules, deterministic evaluators**

2. **Exact-sequence matching is too strict; unordered matching is too loose.** Agents can succeed via multiple valid paths, so golden-trajectory assertions punish valid behavior, while unordered matching misses order-sensitive bugs. A LangChain forum user had to hand-build a "causal precedence" evaluator because neither `agentevals` strict nor unordered mode fit.
   Sources: https://forum.langchain.com/t/proposal-solving-silent-failures-with-a-causal-precedence-evaluator-for-agent-trajectories/3351 ; https://medium.com/@vinodkrane/chapter-8-agent-evaluation-for-llms-how-to-test-tools-trajectories-and-llm-as-judge-788f6f3e0d52 ; corroborated by Anthropic's guidance that step-sequence checks are "too rigid" (https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
   → **policy rules** (constraints: partial order, allowlists, counts — not golden paths)

3. **Users are asking eval tools for deterministic policy checks.** Open DeepEval feature requests: "ToolPermissionMetric — deterministic check that an agent only called authorized tools" (#2825) and an escalation-safety metric (#2856). This is direct demand for policy-as-code over trajectories.
   Sources: https://github.com/confident-ai/deepeval/issues/2825 ; https://github.com/confident-ai/deepeval/issues/2856
   → **policy rules, deterministic evaluators**

4. **Silent-pass defaults destroy trust in eval results.** Promptfoo's `context-recall`, `context-relevance`, and `answer-relevance` assertions defaulted their threshold to 0 and "silently always pass" when no threshold is set.
   Sources: https://github.com/promptfoo/promptfoo/issues/9910 ; https://github.com/promptfoo/promptfoo/issues/9848
   → **deterministic evaluators** (design rule: missing data or config required by a check yields a finding, never a silent pass)

5. **Silent fail-defaults in model graders are just as bad.** Inspect AI's `model_graded_qa`/`model_graded_fact` silently record INCORRECT when the judge's output doesn't match the grade regex — a correctness bug in the grading layer itself.
   Source: https://github.com/UKGovernmentBEIS/inspect_ai/issues/4026
   → **deterministic evaluators** (no hidden model judgments inside deterministic scores)

6. **Nondeterminism persists even at temperature 0, breaking reproducibility.** The same promptfoo config (temp 0, fixed seed) produced different failing cases for different users; reconfirmed a year later ("when I set temperature to 0.1 it is sent, when set to 0 or 0.0 it is not"). "This is quite a big issue, because is hampering trust in the tool."
   Source: https://github.com/promptfoo/promptfoo/issues/2729
   → **deterministic evaluators, regression compare** (evaluate recorded traces deterministically; compare runs explicitly instead of assuming replays match)

7. **Chained nondeterminism makes single-run agent evals misleading.** "An agent making 10–20 tool calls chains that randomness — small differences in step 3 cascade into wildly different step 7 decisions... you need many samples to get stable metrics."
   Source: https://medium.com/@vinodkrane/chapter-8-agent-evaluation-for-llms-how-to-test-tools-trajectories-and-llm-as-judge-788f6f3e0d52
   → **regression compare** now (explicit baseline vs candidate); **future/semantic** (multi-run pass^k consistency reporting)

8. **Reliability collapses under repeat-trial measurement.** tau-bench's pass^k metric shows even strong models drop ~60% in task success when required to succeed 8/8 times; practitioners recommend a dedicated consistency slice ("run 30 hard cases k times each").
   Sources: https://giovanni-occhipinti.medium.com/bench-measuring-the-state-of-conversational-ai-agents-in-customer-service-fd2271e959f2 ; https://futureagi.com/blog/evaluating-tool-calling-agents-2026
   → **future/semantic** (pass^k roadmap); **regression compare** (per-scenario status tracking is the prerequisite)

9. **Per-step "green" hides end-to-end failure.** "A 95-percent per-step agent over eight steps lands near 66 percent [end-to-end]... Two thirds of sessions ending structurally wrong while every individual step scores green... is the default math."
   Source: https://futureagi.com/blog/evaluating-tool-calling-agents-2026
   → **policy rules** (whole-trajectory invariants: completion, ordering, side-effect rules — not per-step spot checks)

10. **Silent regressions ship because prompt changes have no failing test.** "Someone edits a prompt to fix one bad answer. It ships. Three other cases that used to work now fail, and nobody notices until a user complains. There was no diff to review, no test that went red."
    Source: https://medium.com/@alexrodriguesj/testing-llm-prompts-like-code-regression-evals-in-ci-cd-with-promptfoo-5242b4dcb9be
    → **regression compare, CI gate**

11. **"Vibe checks" pass while the full suite regresses.** "There were multiple situations where a tweak to a prompt passed an initial vibe check, but when run against the full eval suite, clearly performed worse... evals don't have to [be] sophisticated, just repeatable and agnostic to who's running them."
    Source: https://news.ycombinator.com/item?id=44717808
    → **regression compare, CI gate, deterministic evaluators**

12. **Full-benchmark evals are too slow/expensive/variant to run per change.** "Thorough evaluation tasks tend to be slow and/or expensive and/or display a high degree of variance... You could run a whole benchmark like SWE Bench... on every change but it quickly becomes infeasible." Also: "Running 1,000 agent trajectories for an eval suite can cost thousands of dollars."
    Sources: https://news.ycombinator.com/item?id=44712315 (comment 44717734) ; https://medium.com/@vinodkrane/chapter-8-agent-evaluation-for-llms-how-to-test-tools-trajectories-and-llm-as-judge-788f6f3e0d52
    → **deterministic evaluators, local-first** (no-LLM checks over recorded traces cost ~nothing and run in CI on every PR)

13. **Trace/tooling lock-in: users want portable formats, maintainers refuse proprietary schemas.** Langfuse maintainer on ingesting LangSmith traces: "parsing non-OSS vendor specific schemas... is not a good idea for long-term maintainability... Is there a way to directly export OTel traces?"
    Source: https://github.com/orgs/langfuse/discussions/6214
    → **local-first** (provider-neutral canonical trace spec + adapters for *documented* formats: OpenAI chat, Anthropic messages, OTel GenAI later)

14. **Merge-gating on trajectories is a different job than observability or metric scoring — and mostly unserved.** New OSS projects position themselves exactly there: "a merge-time regression gate, which is a different job from observability (Langfuse, LangSmith) or metric scoring (promptfoo, DeepEval, Braintrust)." Their existence signals a perceived gap (adoption UNVERIFIED).
    Source: https://github.com/hidai25/eval-view (README); related: https://github.com/harness-hub/agent-replay , https://github.com/beyhangl/evalcraft , https://github.com/reaatech/agent-eval-harness
    → **regression compare, CI gate**

15. **Declarative trajectory matchers have documented blind spots: loops and per-step grounding.** Google ADK/Vertex EXACT/IN_ORDER/ANY_ORDER matching plus response scoring can all pass while the agent "loops redundantly (calling the same tool three times)" — "the eval suite missed it because it only graded the final response and trajectory. Not per-step output, not loop count."
    Source: https://futureagi.com/blog/evaluate-google-adk-agents ; ADK format background: https://github.com/Kjdragan/google-adk-tutorial/blob/main/12_evaluation.md
    → **policy rules** (max_calls / retry-storm / duplicate-side-effect rules are precisely the missing checks)

16. **Flagship agentic metrics break on fragile internals.** DeepEval's Task Completion / Argument Correctness metrics failed three separate times in ~2 weeks on internal Jinja template variable mismatches (`tools_called_formatted`, `stringified_tools_called`).
    Sources: https://github.com/confident-ai/deepeval/issues/2859 ; /issues/2817 ; /issues/2807
    → **deterministic evaluators** (typed, schema-validated internal contracts; no string templating in the evaluation path)

17. **Telemetry opt-outs that don't work undermine "local" claims.** Promptfoo's telemetry beacon still fired with `PROMPTFOO_DISABLE_TELEMETRY` set.
    Source: https://github.com/promptfoo/promptfoo/issues/9968
    → **local-first** (zero telemetry, zero network calls in the core; verifiable)

18. **Hidden operations in the eval hot path.** LangSmith's `evaluate()` silently shelled out to `git` per example, inflating single-example evals to ~90 seconds; unresolved for ~a year, closed "not_planned."
    Source: https://github.com/langchain-ai/langsmith-sdk/issues/1074
    → **local-first, deterministic evaluators** (no hidden subprocess/network work; performance is measured and published)

19. **CI-for-evals is still being built in major platforms.** Langfuse has open, labeled feature work (`feat-evals-ci-cd`, e.g. #14907, 2026-07-08) — CI gating is not yet first-class there; AgentOps lists "Regression testing" and "CI/CD integration checks" as unshipped roadmap items in its own README.
    Sources: https://github.com/langfuse/langfuse/issues/14907 ; https://github.com/AgentOps-AI/agentops
    → **CI gate** (day-one feature, not roadmap)

20. **Nobody owns agent reliability; prompt changes are tested casually.** From 50+ practitioner interviews: "most agent failures are not model failures; prompt changes are often tested way more casually than normal code changes; almost nobody fully agrees on who owns agent reliability."
    Source: https://www.reddit.com/r/AI_Agents/comments/1tehyvt/i_spent_last_6_months_talking_to_ai_engineering/
    → **CI gate, regression compare** (make reliability a reviewable artifact in the PR workflow)

21. **Teams feel prompt evals cover only one slice of agent testing.** "How are you testing AI agents beyond prompt evals? ... it kinda feels like prompt evals only cover one slice of the problem." No consensus tooling exists.
    Source: https://www.reddit.com/r/LLMDevs/comments/1s8lhxw/how_are_you_testing_ai_agents_beyond_prompt_evals/
    → **policy rules, deterministic evaluators** (trajectory-level behavior checks are the missing slice)

22. **Public benchmark contamination makes "we score X on SWE-bench" claims unreliable.** "The problem is acquiring or building a high-quality, non-contaminated dataset... swebench... is most likely overestimating your agent's actual capabilities" (citing arxiv.org/abs/2506.12286).
    Source: https://news.ycombinator.com/item?id=44729006
    → **deterministic evaluators** (our benchmark uses synthetic seeded traces with known ground truth — no contamination; also a reason to avoid unverifiable capability claims)

---

## Aggregate mapping

| Harness capability | Pain points addressed |
|---|---|
| Policy rules (declarative trajectory constraints) | 1, 2, 3, 9, 15, 21 |
| Deterministic evaluators (no-LLM, fail-loud, typed) | 1, 3, 4, 5, 6, 11, 12, 16, 18, 21, 22 |
| Regression compare (baseline vs candidate) | 6, 7, 8, 10, 11, 14, 20 |
| CI gate (exit codes, reports, PR artifacts) | 10, 11, 12, 14, 19, 20 |
| Local-first (zero deps/telemetry/network) | 12, 13, 17, 18 |
| Future/semantic (LLM-judged quality, pass^k multi-run) | 7, 8 |

Pain points 7 and 8 are only partially addressable deterministically; multi-run consistency (pass^k) and semantic judgment remain explicitly future work and must not be claimed as current capabilities.
