# Source Ledger

Every material claim in `competitive-landscape.md` and `user-problems.md` traces to a source below. All sources accessed **2026-07-14** during a four-track primary-source research pass. Snapshot-dependent values (stars, issue open/closed state) reflect that date.

**Integrity note:** while fetching the Arize Phoenix OTEL setup documentation page, the researcher encountered a hidden prompt-injection block embedded in the page content (fake "AI AGENT INSTRUCTION" text attempting to alter agent behavior). It was treated as inert page data and ignored; it does not affect any claim recorded here.

**Bias note:** vendor-authored comparisons (e.g., LangSmith-vs-Langfuse by LangChain; Braintrust's observability-tools article) are used only with an explicit caution label in the research docs, never as sole support for a competitive claim against the vendor's competitor.

| Source URL | Supports claim(s) | Type |
|---|---|---|
| https://github.com/openai/evals | Repo stats; "not accepting evals with custom code" contribution freeze | GitHub repo |
| https://developers.openai.com/api/docs/guides/evals | Hosted Evals platform deprecation: read-only 2026-10-31, shutdown 2026-11-30, "Datasets" replacement | Official docs |
| https://community.openai.com/t/openai-evals-plans-for-future/263156 | Community sentiment: "quite basic and unfortunately not very extendable"; unclear maintenance | Community forum |
| https://github.com/openai/evals/issues/1384 | "Eval-running often hangs on last sample" — open since Oct 2023 | GitHub issue |
| https://developers.openai.com/cookbook/examples/evaluation/getting_started_with_openai_evals | OpenAI Evals usage model | Official docs |
| https://github.com/openai/frontier-evals | frontier-evals is a benchmark-code repo (PaperBench, SWE-Lancer, EVMbench), not a framework | GitHub repo |
| https://openai.com/index/introducing-openai-frontier/ | "OpenAI Frontier" is an enterprise agent platform (2026-02-05), unrelated to evals tooling | Official announcement |
| https://openai.com/careers/research-engineer-frontier-evals-and-environments-san-francisco/ | "Frontier Evals" is an internal research team function | Official careers page |
| https://www.eesel.ai/blog/openai-frontier | Third-party description of OpenAI Frontier platform | Blog |
| https://openai.github.io/openai-agents-python/tracing/ | Agents SDK trace/span model; default export to OpenAI backend; processor extensibility; ZDR limitation | Official docs |
| https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents | Transcript vs outcome; grader taxonomy; pass@k vs pass^k; "too rigid" sequence-check warning; capability vs regression evals | Official engineering blog |
| https://docs.anthropic.com/en/docs/test-and-evaluate/eval-tool | Console Evaluate tool scope (prompt-focused, 5-point grading) | Official docs |
| https://github.com/anthropics/anthropic-cookbook/blob/main/misc/building_evals.ipynb | Eval anatomy; three grading methods | Official cookbook |
| https://github.com/anthropics/claude-cookbooks/issues/761 | Cookbook eval scripts bit-rot on model deprecation (open, 2026-07-07) | GitHub issue |
| https://www.anthropic.com/engineering/building-effective-agents | Anthropic agent-building guidance context | Official engineering blog |
| https://inspect.aisi.org.uk/ | Inspect AI features; provider count; agent support; adoption claims | Official docs |
| https://github.com/UKGovernmentBEIS/inspect_ai | Repo activity; extensibility; issues #4027 (multi_scorer crash), #4026 (silent INCORRECT default), #4017 (duplicated answer), #4003 (trio crash), #3994 (pairwise/Elo request) | GitHub repo + issues |
| https://github.com/UKGovernmentBEIS/inspect_evals | 200+ community benchmark tasks | GitHub repo |
| https://github.com/UKGovernmentBEIS/inspect_evals/issues/442 | Minor-version API change broke dependent eval package | GitHub issue |
| https://github.com/thinking-machines-lab/tinker-cookbook/issues/679 | Integration silently dropping tools/tool_choice in tool-use evals | GitHub issue |
| https://hamel.dev/notes/llm/evals/inspect.html | Practitioner notes on Inspect | Blog |
| https://neurlcreators.substack.com/p/inspect-ai-evaluation-framework-review | Learning curve/overhead; "hold off if you can't support Docker-level isolation" | Blog review |
| https://docs.langchain.com/langsmith/trajectory-evals | agentevals trajectory-match modes (deterministic vs LLM-judge) | Official docs |
| https://docs.langchain.com/langsmith/trace-with-opentelemetry | LANGSMITH_OTEL_ENABLED OTel ingestion | Official docs |
| https://docs.langchain.com/langsmith/self-hosted | Self-host is Enterprise add-on with sales license key; multi-service architecture | Official docs |
| https://www.langchain.com/pricing | Developer/Plus/Enterprise tiers; trace volume pricing | Official pricing |
| https://www.langchain.com/langsmith/evaluation | Evaluator types; CI threshold gating | Official product page |
| https://www.langchain.com/langsmith/observability | SmithDB/trajectory query claims | Official product page |
| https://www.langchain.com/resources/langsmith-vs-langfuse | Insights Agent claims; Langfuse two-score-comparison claim (vendor-biased; labeled) | Vendor comparison |
| https://staxly.dev/platforms/langsmith | Free-tier/single-user and closed-source complaints summary | Third-party review |
| https://forum.langchain.com/t/proposal-solving-silent-failures-with-a-causal-precedence-evaluator-for-agent-trajectories/3351 | Strict match "too rigid" / unordered "too loose"; user hand-built causal-precedence evaluator | Community forum |
| https://github.com/langchain-ai/langsmith-sdk/issues/1074 | evaluate() ~90s/example from silent git shell-outs; closed not_planned Aug 2025 | GitHub issue |
| https://github.com/langchain-ai/agentevals | Deterministic trajectory match (strict/unordered/subset) + LLM judge; closest prior art | GitHub repo |
| https://www.morphllm.com/comparisons/langfuse-vs-langsmith | Cost comparison estimate at 1M events | Third-party comparison |
| https://www.braintrust.dev/ | Positioning; customer list | Official site |
| https://www.braintrust.dev/docs/integrations/sdk-integrations/opentelemetry | OTel ingestion; root-span-only logs gotcha | Official docs |
| https://www.braintrust.dev/docs/best-practices/agents | hooks for intermediate-step scoring; no packaged trajectory matcher | Official docs |
| https://www.braintrust.dev/docs/admin/self-hosting | Hybrid self-host: data plane customer-side, control plane vendor-hosted; BYOC | Official docs |
| https://www.braintrust.dev/docs/evaluate | Code + LLM scorers; experiment lifecycle | Official docs |
| https://www.braintrust.dev/pricing | Starter/Pro/Enterprise; metered data/scores | Official pricing |
| https://github.com/braintrustdata | SDK language coverage (js/python/java/rust) | GitHub org |
| https://github.com/braintrustdata/braintrust-deployment/blob/main/LICENSE | Permissive license only on deployment tooling, not core | GitHub repo |
| https://blog.promptlayer.com/braintrust-vs-langsmith | Braintrust statistical-analysis strength claim (UNVERIFIED vs primary docs; labeled) | Third-party comparison |
| https://mlflow.org/braintrust-alternative | Proprietary/closed-core characterization | Vendor comparison (labeled) |
| https://www.morphllm.com/comparisons/braintrust-alternatives | Lock-in criticism; hybrid self-host dependency | Third-party comparison |
| https://langfuse.com/resources/engineering/best-braintrustdata-alternatives | Braintrust alternative landscape (vendor-authored; labeled) | Vendor comparison |
| https://latitude.so/blog/latitude-vs-braintrust | Braintrust positioning corroboration | Third-party comparison |
| https://langfuse.com/integrations/native/opentelemetry | OTel backend endpoint; ambient-span capture caveat; blocked_instrumentation_scopes | Official docs |
| https://langfuse.com/docs/evaluation/overview | Evaluator types; external score ingestion | Official docs |
| https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge | Judge runs produce traces; field mapping | Official docs |
| https://langfuse.com/pricing-self-host | MIT; self-host all core features free without limitations | Official pricing |
| https://langfuse.com/self-hosting | OSS-only dependencies; Docker Compose to K8s/Terraform | Official docs |
| https://github.com/orgs/langfuse/discussions/5206 | User request for core trajectory evaluation; maintainer punts to DIY/LLM judge | GitHub discussion |
| https://github.com/orgs/langfuse/discussions/6214 | Maintainer declines proprietary LangSmith schema parsing; recommends OTel export | GitHub discussion |
| https://github.com/langfuse/langfuse/issues/11002 | v2→v3 migration fails to start (self-hosted) | GitHub issue |
| https://github.com/langfuse/langfuse/issues/11016 | Redis OOM after minor upgrade 3.130.0→3.137.0 | GitHub issue |
| https://github.com/langfuse/langfuse/issues/10998 | LLM-as-judge uses user message instead of system prompt | GitHub issue |
| https://github.com/langfuse/langfuse/issues/11329 | High latency on trace API (stale) | GitHub issue |
| https://github.com/langfuse/langfuse/issues/11269 | S3 via corporate proxy closed not-planned | GitHub issue |
| https://github.com/langfuse/langfuse/issues/14907 | Open `feat-evals-ci-cd` work — CI gating not yet first-class (2026-07-08) | GitHub issue |
| https://github.com/Arize-ai/phoenix | README: features, license (ELv2, patents), telemetry policy, pip+serve install | GitHub repo |
| https://arize.com/docs/phoenix/self-hosting | Free self-host, no feature limits, air-gappable, nothing sent to Arize | Official docs |
| https://arize.com/docs/phoenix/tracing/how-to-tracing/setup-tracing/setup-using-phoenix-otel | OTel setup (page contained the ignored prompt-injection block noted above) | Official docs |
| https://arize.com/docs/phoenix/tracing/concepts-tracing/otel-openinference/overview | OpenInference on top of OTel; span kinds/attributes | Official docs |
| https://github.com/Arize-ai/openinference | OpenInference instrumentor ecosystem breadth; Apache-2.0 | GitHub repo |
| https://github.com/Arize-ai/phoenix/discussions/10621 | No zero-code/passive tracing path (unanswered) | GitHub discussion |
| https://deepwiki.com/Arize-ai/phoenix/5.1-tracing-and-observability | Phoenix tracing architecture corroboration | Third-party docs |
| https://github.com/promptfoo/promptfoo | Repo scope; OpenAI ownership note; MIT; assertion families | GitHub repo |
| https://github.com/promptfoo/promptfoo-action | CI action: path skip, force-run, repeat/repeat-min-pass, cache, fail-on-threshold | GitHub repo |
| https://www.promptfoo.dev/pricing | Community free tier scope; Enterprise tiers | Official pricing |
| https://www.promptfoo.dev/docs/integrations/github-action/ | GH Action usage | Official docs |
| https://www.promptfoo.dev/docs/guides/evaluate-coding-agents/ | Coding-agent eval guide (2026-07-11); "Assert the path when the path matters"; tier model | Official docs |
| https://github.com/promptfoo/promptfoo/issues/2729 | Temp-0 + seed nondeterminism across users; "hampering trust"; reconfirmed Jan 2026 | GitHub issue |
| https://github.com/promptfoo/promptfoo/issues/9910 | context-recall/context-relevance threshold defaults 0 → silent always-pass | GitHub issue |
| https://github.com/promptfoo/promptfoo/issues/9848 | answer-relevance threshold default 0 → silent always-pass | GitHub issue |
| https://github.com/promptfoo/promptfoo/issues/9968 | Telemetry beacon fires despite PROMPTFOO_DISABLE_TELEMETRY | GitHub issue |
| https://github.com/promptfoo/promptfoo/issues/9895 | Comment-stripping parser bug | GitHub issue |
| https://github.com/promptfoo/promptfoo/issues/9842 | trajectory:tool-args-match wildcard request (exact-match limitation) | GitHub issue |
| https://github.com/promptfoo/promptfoo/issues/9915 | Per-test-case working dir request (agent eval gap) | GitHub issue |
| https://github.com/promptfoo/promptfoo/issues/7528 | npm peer-dependency install friction | GitHub issue |
| https://github.com/giorgiodemarchi/agent-eval-cookbook/blob/main/eval_tools/promptfoo/README.md | OTel spans rendered as trace timelines in promptfoo UI | Community cookbook |
| https://github.com/confident-ai/deepeval | Repo scope; Apache 2.0; @observe tracing | GitHub repo |
| https://deepeval.com/docs/metrics-introduction | Metric catalog; deterministic vs judge split | Official docs |
| https://deepeval.com/docs/metrics-tool-correctness | ToolCorrectnessMetric matching modes | Official docs |
| https://deepeval.com/docs/metrics-task-completion | TaskCompletionMetric requires trace; LLM-judged | Official docs |
| https://deepeval.com/docs/data-privacy | Telemetry limited to metric names; local execution | Official docs |
| https://www.confident-ai.com/ | Cloud counterpart features/tiers | Official site |
| https://github.com/confident-ai/deepeval/issues/2859 | TaskCompletionMetric template interpolation failure (2026-07-07) | GitHub issue |
| https://github.com/confident-ai/deepeval/issues/2817 | ArgumentCorrectnessMetric template variable undefined (2026-06-29) | GitHub issue |
| https://github.com/confident-ai/deepeval/issues/2807 | Wrong Jinja variable passed to template (2026-06-26) | GitHub issue |
| https://github.com/confident-ai/deepeval/issues/2825 | Feature request: deterministic ToolPermissionMetric (authorized tools only) | GitHub issue |
| https://github.com/confident-ai/deepeval/issues/2856 | Feature request: AgentEscalationMetric (agentic safety) | GitHub issue |
| https://github.com/confident-ai/deepeval/issues/2821 | Quickstart LangChain example fails (NoMetricsError) | GitHub issue |
| https://github.com/confident-ai/deepeval/issues/2223 | Multi-turn Task Completion / Tool Correctness request → shipped | GitHub issue |
| https://github.com/confident-ai/deepeval/issues/940 | Docs showed wrong metric on Tool Correctness page (2024) | GitHub issue |
| https://github.com/AgentOps-AI/agentops | README roadmap table: regression testing / CI-CD checks / validators unshipped; session replay features; pricing tiers | GitHub repo |
| https://www.agentops.ai/ | Product positioning; customers; pricing | Official site |
| https://infrabase.ai/agents/agentops | Third-party feature/pricing corroboration | Third-party review |
| https://aimultiple.com/agentic-monitoring | Positioning as observability not eval | Third-party comparison |
| https://www.braintrust.dev/articles/best-ai-observability-tools-2026 | Category positioning of AgentOps vs eval tools (vendor-authored; labeled) | Vendor article |
| https://github.com/open-telemetry/semantic-conventions-genai | Canonical GenAI semconv repo; move from main semconv repo; Development stability | Spec repo |
| https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/gen-ai/gen-ai-spans.md | Inference/embeddings/retrieval/execute_tool span conventions; attributes | Spec |
| https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/gen-ai/gen-ai-agent-spans.md | create_agent/invoke_agent/invoke_workflow/plan span conventions | Spec |
| https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/gen-ai/gen-ai-events.md | inference.operation.details + gen_ai.evaluation.result event schemas | Spec |
| https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/ | Old pages deprecated/moved (redirect confirmation) | Spec (deprecated stub) |
| https://mlflow.org/docs/latest/genai/tracing/opentelemetry/genai-semconv/ | Third-party adoption of GenAI semconv incl. evaluation.result | Official docs (MLflow) |
| https://medium.com/@vinodkrane/chapter-8-agent-evaluation-for-llms-how-to-test-tools-trajectories-and-llm-as-judge-788f6f3e0d52 | Chained nondeterminism; multiple-valid-paths; trajectory-eval cost ("1,000 trajectories… thousands of dollars") | Blog (practitioner) |
| https://news.ycombinator.com/item?id=44712315 | Coding-agent evals "slow and/or expensive and/or high-variance"; full benchmarks infeasible per change (comment 44717734) | HN thread |
| https://news.ycombinator.com/item?id=44717808 | Vibe-check pass vs full-suite regression; evals must be "repeatable and agnostic to who's running them" | HN comment |
| https://news.ycombinator.com/item?id=44729006 | Dataset contamination as the real bottleneck; SWE-bench overestimation (cites arxiv 2506.12286) | HN comment |
| https://medium.com/@alexrodriguesj/testing-llm-prompts-like-code-regression-evals-in-ci-cd-with-promptfoo-5242b4dcb9be | Silent regression shipping: "no diff to review, no test that went red, no signal" | Blog (practitioner) |
| https://futureagi.com/blog/evaluating-tool-calling-agents-2026 | Compound per-step error math (95%^8 ≈ 66%); pass^k practice; BFCL taxonomy framing | Blog (vendor; labeled) |
| https://futureagi.com/blog/evaluate-google-adk-agents | ADK trajectory-match blind spot: loops/redundant calls and per-step grounding missed | Blog (vendor; labeled) |
| https://github.com/Kjdragan/google-adk-tutorial/blob/main/12_evaluation.md | ADK .test.json format; EXACT/IN_ORDER/ANY_ORDER trajectory matching; pytest/CLI harness | Community tutorial |
| https://giovanni-occhipinti.medium.com/bench-measuring-the-state-of-conversational-ai-agents-in-customer-service-fd2271e959f2 | tau-bench pass^k: ~60% drop at pass^8; final-state grading + policy document design | Blog (practitioner) |
| https://www.reddit.com/r/AI_Agents/comments/1tehyvt/i_spent_last_6_months_talking_to_ai_engineering/ | 50+ team interviews: casual prompt-change testing; no reliability ownership | Community (Reddit) |
| https://www.reddit.com/r/LLMDevs/comments/1s8lhxw/how_are_you_testing_ai_agents_beyond_prompt_evals/ | "Prompt evals only cover one slice" — no consensus agent-testing approach | Community (Reddit) |
| https://github.com/hidai25/eval-view | Positioning: merge-time trajectory regression gate is a different job than observability/metric scoring (adoption UNVERIFIED) | GitHub repo README |
| https://github.com/harness-hub/agent-replay | New OSS entrant signaling perceived gap (adoption UNVERIFIED) | GitHub repo |
| https://github.com/beyhangl/evalcraft | New OSS entrant signaling perceived gap (adoption UNVERIFIED) | GitHub repo |
| https://github.com/reaatech/agent-eval-harness | New OSS entrant signaling perceived gap (adoption UNVERIFIED) | GitHub repo |

## Research-and-benchmark background sources (surveyed; informing benchmark design, cited in research summaries)

| Source URL | Supports claim(s) | Type |
|---|---|---|
| https://github.com/THUDM/AgentBench | 8 heterogeneous environments; no unified trajectory schema (cost of fragmentation) | GitHub repo |
| https://gorilla.cs.berkeley.edu/leaderboard.html | BFCL v4 AST / executable / irrelevance-detection taxonomy; multi-turn support | Official leaderboard |
| https://cloud.google.com/blog/products/ai-machine-learning/introducing-agent-evaluation-in-vertex-ai-gen-ai-evaluation-service | Vertex trajectory metrics incl. trajectory_exact_match, in-order match | Official blog |
| https://adk.dev/evaluate/criteria | ADK evaluation criteria incl. trajectory match modes and rubric-based criteria | Official docs |
| https://promptgenius.net/agents/concepts/agent-evaluation | SWE-bench variants; WebArena success rates (14.4% GPT-4 vs 78.2% human) | Third-party summary |

## Verification discipline

- Claims marked **UNVERIFIED** in the research documents were kept marked and were not used as the sole basis for any conclusion.
- Issue numbers were recorded only when the researcher observed the actual issue (title/date/state) on GitHub.
- No private, internal, or inaccessible systems were researched or referenced; all comparisons target publicly documented tools.
