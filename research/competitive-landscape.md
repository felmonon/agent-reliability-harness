# Competitive Landscape: Public Agent-Evaluation Ecosystem

Research date: 2026-07-14. All claims are drawn from primary sources (official documentation, GitHub repositories/issues, release notes, pricing pages) accessed on that date; exact URLs are inline and catalogued in `source-ledger.md`. Snapshot numbers (stars, issue states) will drift. Items that could not be verified against a primary source are marked **UNVERIFIED**. No comparison in this document refers to private or internal systems.

Scope note: this document compares publicly documented tools only, for the purpose of positioning a local-first, policy-driven trajectory/regression harness (`agent-reliability-harness`). It is research input, not marketing.

---

## 1. OpenAI Evals

- **Intended user:** Prompt engineers/researchers benchmarking model outputs against OpenAI models; originally built for OpenAI's internal model regression testing.
- **Job-to-be-done:** Run static, dataset-driven evals (input → completion → grade) against OpenAI models via API.
- **Trace model:** Minimal — input, completion, and grading result per sample. A "Completion Function Protocol" exists for chained/tool-using agents but is a thin wrapper, not a first-class trajectory format.
- **Evaluator model:** Deterministic classes (`Match`, string/regex) plus YAML-configured model-graded (LLM judge) evals.
- **Trajectory support:** Weak/bolted-on (completion functions only).
- **Datasets/experiments:** Registry of YAML-defined evals with JSONL samples; requires Git-LFS.
- **Regression comparison:** None built-in beyond manually re-running and comparing scores.
- **CI integration:** Possible via `oaieval` CLI but not designed for it; no native CI templates.
- **Extensibility:** Restricted — README states "we are currently not accepting evals with custom code," only model-graded YAML evals (https://github.com/openai/evals).
- **Providers:** OpenAI models only (`OPENAI_API_KEY`).
- **Local/offline:** Runs locally but every eval call hits the OpenAI API; not offline.
- **Report formats:** JSONL logs; optional Snowflake logging; W&B community integration. Dashboard functionality lives only in the hosted platform.
- **Install complexity:** Low (`pip install evals`) plus Git-LFS friction for data.
- **Strengths:** Brand recognition; large registry of benchmark YAML definitions; simple mental model for single-turn evals.
- **Recurring complaints:** Issue #1384 "Eval-running often hangs on last sample," open since Oct 2023 with reports through 2025 (https://github.com/openai/evals/issues/1384). A 2023 community thread calls the repo "quite basic and unfortunately not very extendable" with unclear maintenance (https://community.openai.com/t/openai-evals-plans-for-future/263156).
- **Limitations:** Not built for multi-step agent trajectories or tool-use policy checks. Critically, **OpenAI's hosted Evals platform is being deprecated**: read-only for existing users on 2026-10-31, shutdown 2026-11-30, with "Datasets" as the recommended replacement (https://developers.openai.com/api/docs/guides/evals). Custom-code contribution path is frozen.
- **What we should NOT copy:** Trace format as an afterthought bolted onto a single-turn loop; a hosted platform as the only serious UI; restricting extensibility once a registry model exists.

Sources: https://github.com/openai/evals ; https://developers.openai.com/api/docs/guides/evals ; https://community.openai.com/t/openai-evals-plans-for-future/263156 ; https://github.com/openai/evals/issues/1384 ; https://developers.openai.com/cookbook/examples/evaluation/getting_started_with_openai_evals

---

## 2. "OpenAI Frontier Evals"

**Not a coherent public product as of mid-2026.** The name conflates two distinct, real things:

- **`github.com/openai/frontier-evals`** — a real public repo (MIT, created Mar 2025): "Code for evals measuring frontier model capabilities," containing PaperBench, SWE-Lancer, and EVMbench project folders, each with an isolated `uv`-managed environment. It is a collection of specific capability-benchmark code, **not** a general reusable eval framework or CLI product (https://github.com/openai/frontier-evals).
- **"OpenAI Frontier"** — an unrelated enterprise agent-deployment/management platform announced 2026-02-05 ("helps enterprises build, deploy, and manage AI agents"); no public evaluation-tool surface (https://openai.com/index/introducing-openai-frontier/).
- A job posting ("Research Engineer, Frontier Evals & Environments") references an internal team building capability benchmarks (GDPval, SWE-bench Verified, MLE-bench, PaperBench, SWE-Lancer) — an internal research function, not a shipped external product (https://openai.com/careers/research-engineer-frontier-evals-and-environments-san-francisco/).

Any claim that "OpenAI Frontier Evals" is a general trace-testing product with a defined trace/evaluator model, CI integration, or install flow is **UNVERIFIED** and must not be asserted. It is not a comparison target for this project.

Sources: https://github.com/openai/frontier-evals ; https://openai.com/index/introducing-openai-frontier/ ; https://openai.com/careers/research-engineer-frontier-evals-and-environments-san-francisco/ ; https://www.eesel.ai/blog/openai-frontier

---

## 3. OpenAI Agents SDK — Tracing

- **Intended user:** Developers building agents on the OpenAI Agents SDK who need runtime observability/debugging.
- **Job-to-be-done:** Capture a structured record of an agent run (LLM calls, tool calls, handoffs, guardrails, custom events) for the OpenAI Traces dashboard.
- **Trace model:** Well-defined: `Trace` (workflow_name, trace_id, group_id, metadata) composed of nested `Span`s (agent_span, generation_span, function_span, guardrail_span, handoff_span, transcription_span, speech_span, custom_span) with start/end timestamps and parent/child relationships (https://openai.github.io/openai-agents-python/tracing/).
- **Evaluator model:** None — tracing is pure observability; no pass/fail scorer.
- **Trajectory support:** Strong for *capturing* trajectories; zero for *evaluating* them.
- **Datasets/experiments / regression / statistics:** None native.
- **CI integration:** Not designed for CI; tracing is a runtime feature.
- **Extensibility:** Strong — custom trace processors (`add_trace_processor`, `set_trace_processors`); 20+ third-party integrations (Langfuse, Braintrust, Arize-Phoenix, MLflow, Datadog, W&B, etc.) consume this span model.
- **Providers:** OpenAI natively; others via adapter, but traces still route to OpenAI's dashboard with an OpenAI tracing key.
- **Local/offline:** Default exporter sends to OpenAI's backend; fully replaceable via `set_trace_processors()`, but local-only is not the default. Tracing is unavailable under Zero Data Retention policies.
- **Report formats:** Structured spans to dashboard or custom processor; no static report file format.
- **Install complexity:** Trivial (bundled in `openai-agents`, on by default).
- **Strengths:** Clean trace/span data model; processor extensibility; de facto standard shape for agent traces given vendor adoption.
- **Recurring complaints:** Not researched at issue level in this pass — **UNVERIFIED**.
- **Limitations:** Tracing ≠ evaluation: no policy/assertion language, no regression diffing.
- **What we should NOT copy:** Defaulting trace export to a vendor backend (a local-first tool must default local-only). The clean separation of tracing from evaluation is worth *keeping*, not avoiding.

Sources: https://openai.github.io/openai-agents-python/tracing/

---

## 4. Anthropic — Published Evaluation Guidance

- **What it is:** Not a shipped eval product. Three artifacts: (a) Claude Console "Evaluate" tool — a prompt-engineering UI with `{{variable}}` test rows, side-by-side prompt-version comparison, and 5-point human grading (https://docs.anthropic.com/en/docs/test-and-evaluate/eval-tool); (b) cookbook `building_evals.ipynb` — input/output/golden-answer/score anatomy and three grading methods (code-based, model-based, human); (c) the engineering post "Demystifying evals for AI agents" (2026-01-09) — the most relevant primary source for trajectory testing (https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents).
- **Key concepts from (c):** formal vocabulary (task/trial, grader/assertion, **transcript** = complete record incl. tool calls, **outcome** = final environment state, distinct from transcript); capability vs regression evals (regression suites should sit near 100% pass); `pass@k` vs `pass^k` statistics for nondeterminism; grader taxonomy with tradeoffs — code-based graders are "Fast, Cheap, Objective, Reproducible" but "Brittle to valid variations."
- **Directly relevant warning:** "There is a common instinct to check that agents followed very specific steps like a sequence of tool calls in the right order. We've found this approach too rigid... it's often better to grade what the agent produced, not the path it took." This argues for *constraint-based* policies (allowlists, partial order, budgets, invariants) over golden-trajectory exact matching.
- **Trajectory support / datasets / regression / CI / providers / install:** N/A — guidance only; the post's appendix defers tooling to third parties (Harbor, Braintrust, LangSmith/Langfuse, Arize Phoenix/AX).
- **Recurring complaints:** N/A (not a tool). Related cookbook repo shows eval-example bit-rot as models change, e.g. issue #761 "Evaluation scripts still use assistant message prefill and fail on claude-sonnet-4-6" (opened 2026-07-07, open) (https://github.com/anthropics/claude-cookbooks/issues/761).
- **What we should apply (nothing to copy code-wise):** keep transcript-grading and outcome-grading separate; avoid rigid step-sequence assertions; build repeat-trial statistics (pass@k/pass^k) into the roadmap early.

Sources: https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents ; https://docs.anthropic.com/en/docs/test-and-evaluate/eval-tool ; https://github.com/anthropics/anthropic-cookbook/blob/main/misc/building_evals.ipynb ; https://github.com/anthropics/claude-cookbooks/issues/761 ; https://www.anthropic.com/engineering/building-effective-agents

---

## 5. Inspect AI (UK AISI)

- **Intended user:** AI safety researchers, frontier labs, eval engineers running large-scale reproducible evaluations; docs state adoption by "Anthropic, DeepMind, and Grok" (https://inspect.aisi.org.uk/).
- **Job-to-be-done:** Compose and run reproducible LLM evaluations (datasets + solvers + scorers), including full agent loops and sandboxed capability evals.
- **Trace model:** Full eval logs per sample/trial (message history, tool calls, scores), viewable via `inspect view`; dataframe extraction for analysis.
- **Evaluator model:** Deterministic scorers (`includes()`, exact/regex) and model-graded (`model_graded_qa()`); fully pluggable scorer API.
- **Trajectory support:** Strong, first-class: built-in `react()` agent, multi-agent primitives, "Agent Bridge" to evaluate external agents (Claude Code, Codex CLI, Gemini CLI).
- **Datasets/experiments:** Strong — `hf_dataset()`, CSV/JSON, `FieldSpec`; companion `inspect_evals` repo with 200+ benchmark tasks.
- **Regression comparison:** Not a first-class "diff two runs" command in the docs reviewed; buildable on structured logs — **UNVERIFIED** whether a dedicated regression-diff CLI exists.
- **Statistical analysis:** "Analysis" docs section; pairwise comparison/Elo is a community feature request (issue #3994, opened 2026-05-20), not built in.
- **CI integration:** Plain CLI usable in CI; no dedicated GitHub Action found (**UNVERIFIED** beyond CLI feasibility).
- **Extensibility:** Very strong (extensions for model APIs, sandboxes, approvers, hooks, filesystems).
- **Providers:** 20+ built-in (OpenAI, Anthropic, Google, HF, vLLM/SGLang, Azure, AWS, Mistral, xAI...).
- **Local/offline:** Strong — local inference supported; sandboxing via Docker/Kubernetes/Modal/Proxmox/Vagrant.
- **Report formats:** Structured eval logs; `inspect view` web UI; VS Code extension.
- **Install complexity:** `pip install inspect-ai`; agentic/sandboxed evals additionally require Docker or similar, which raises the bar. Third-party review: "Hold off if... you can't support even Docker-level isolation yet" (https://neurlcreators.substack.com/p/inspect-ai-evaluation-framework-review).
- **Strengths:** Most mature OSS framework for agent/tool-use evals; big benchmark library; genuinely local-capable; active maintenance.
- **Recurring complaints (UKGovernmentBEIS/inspect_ai unless noted):** #4027 `multi_scorer()` runtime crash "Object score does not have registry info" (2026-05-24); #4026 `model_graded_qa`/`model_graded_fact` **silently default to INCORRECT** when the judge's verdict doesn't match the grade regex (2026-05-24); #4017 duplicated final answer in grader prompts (2026-05-22); #4003 logging crash under trio (2026-05-21); external adapter silently dropping `tools` (thinking-machines-lab/tinker-cookbook#679); minor-version API change broke dependent evals (inspect_evals#442).
- **Limitations:** Real setup/runtime overhead; documented silent grading failures; API churn between point releases; steep learning curve; heavyweight for validating already-recorded traces.
- **What we should NOT copy:** Docker/K8s as a baseline dependency for trace checking; breaking internal APIs in minor releases; silent-failure defaults in model-graded scoring (fail loudly instead).

Sources: https://inspect.aisi.org.uk/ ; https://github.com/UKGovernmentBEIS/inspect_ai ; https://github.com/UKGovernmentBEIS/inspect_evals ; https://github.com/UKGovernmentBEIS/inspect_evals/issues/442 ; https://github.com/thinking-machines-lab/tinker-cookbook/issues/679 ; https://hamel.dev/notes/llm/evals/inspect.html ; https://neurlcreators.substack.com/p/inspect-ai-evaluation-framework-review

---

## 6. LangSmith (LangChain)

- **Intended user:** Teams building LLM/agent apps (LangChain/LangGraph-first, framework-agnostic via SDK/OTel) needing observability + pre-deployment eval + deployment management.
- **Job-to-be-done:** Trace, debug, and continuously evaluate agents; deploy/manage them.
- **Trace model:** Native LangChain/LangGraph callbacks plus OpenTelemetry ingestion (`LANGSMITH_OTEL_ENABLED=true`); "SmithDB" ClickHouse backend markets trajectory queries as first-class (https://docs.langchain.com/langsmith/trace-with-opentelemetry).
- **Evaluator model:** Deterministic (custom Python/pytest), LLM-as-judge, embedding similarity.
- **Trajectory support:** Via the separate OSS **`agentevals`** package: (1) deterministic trajectory match — strict/exact order, unordered, or subset vs a reference trajectory; (2) LLM-as-judge over the full trajectory (https://github.com/langchain-ai/agentevals ; https://docs.langchain.com/langsmith/trajectory-evals). Documented user gap: strict match is "too rigid," unordered "too loose"; no built-in partial-order/causal-precedence evaluator — a user built one manually (https://forum.langchain.com/t/proposal-solving-silent-failures-with-a-causal-precedence-evaluator-for-agent-trajectories/3351).
- **Datasets/experiments:** Native datasets, offline/online eval, side-by-side comparison views.
- **Regression comparison:** Comparison dashboards across experiments; CI can fail on score-threshold breach.
- **Statistical analysis:** "Insights Agent" auto-analysis claims — **UNVERIFIED** beyond vendor marketing.
- **CI integration:** pytest/Vitest integration, GitHub workflows.
- **Extensibility:** Python/JS SDKs; works with OpenAI SDK, Anthropic SDK, Vercel AI SDK, LlamaIndex, custom stacks.
- **Providers:** Any via SDK/OTel; deepest for LangChain/LangGraph.
- **Local/offline:** Free tier is cloud SaaS only. **Self-hosting is an Enterprise-only add-on requiring a sales-issued license key** (multi-service: frontend, backend, ClickHouse, Postgres, Redis, blob storage) (https://docs.langchain.com/langsmith/self-hosted). No documented offline mode for non-Enterprise users.
- **Report formats:** Web dashboards, comparison views, alerting.
- **Install complexity:** Trivial for SaaS; high and sales-gated for self-host.
- **Pricing/license:** Closed source. Developer free: 5k traces/mo, 1 seat; Plus $39/seat/mo, 10k traces then $2.50/1k overage; Enterprise custom (https://www.langchain.com/pricing).
- **Strengths:** Deep LangChain/LangGraph integration; OTel ingestion; annotation/human-review workflows; `agentevals` is the closest public prior art to deterministic trajectory matching.
- **Recurring complaints:** langsmith-sdk issue #1074 — `evaluate()` took up to 90s/example because the SDK silently shelled out to `git` for metadata; complaints across 2024, closed "not_planned" Aug 2025 (https://github.com/langchain-ai/langsmith-sdk/issues/1074). Comparison articles flag single-user free tier and Enterprise-gated self-hosting; one estimate: ~$2,514/mo at 1M events on Plus vs ~$101/mo Langfuse self-hosted (https://www.morphllm.com/comparisons/langfuse-vs-langsmith).
- **Limitations:** No self-host path for individuals/small teams; volume pricing; trajectory evaluators require reference trajectories rather than declarative policies.
- **What we should NOT copy:** Hidden background operations in the eval hot path; gating self-hosting/offline behind sales contact.

Sources: https://docs.langchain.com/langsmith/trajectory-evals ; https://docs.langchain.com/langsmith/trace-with-opentelemetry ; https://docs.langchain.com/langsmith/self-hosted ; https://www.langchain.com/pricing ; https://www.langchain.com/langsmith/evaluation ; https://forum.langchain.com/t/proposal-solving-silent-failures-with-a-causal-precedence-evaluator-for-agent-trajectories/3351 ; https://github.com/langchain-ai/langsmith-sdk/issues/1074 ; https://github.com/langchain-ai/agentevals ; https://www.morphllm.com/comparisons/langfuse-vs-langsmith

---

## 7. Braintrust

- **Intended user:** AI-native product teams (Notion, Stripe, Zapier, Vercel, Ramp cited as customers) wanting one workflow from playground → offline eval → CI gate → production monitoring (https://www.braintrust.dev/).
- **Job-to-be-done:** Unified eval/observability loop for production AI.
- **Trace model:** OpenTelemetry-native ingestion (`BraintrustSpanProcessor`, OTLP `/otel` endpoint) with `braintrust.*` span attributes. Documented gotcha: only root spans appear in the logs table; child-only traces silently vanish from the UI (https://www.braintrust.dev/docs/integrations/sdk-integrations/opentelemetry).
- **Evaluator model:** Code-based scorers + LLM-as-judge, recommended together.
- **Trajectory support:** No dedicated deterministic trajectory-match primitive; guidance uses `hooks` for intermediate-step scoring; "agentic evaluation" is a customer pattern (Notion), not a packaged evaluator (https://www.braintrust.dev/docs/best-practices/agents).
- **Datasets/experiments:** Full lifecycle: playground → immutable experiment snapshots → CI → production scoring → feedback into datasets.
- **Regression comparison:** Positioned explicitly as regression detection before production.
- **Statistical analysis:** Third-party claims of statistical-significance testing — **UNVERIFIED** against primary docs.
- **CI integration:** Dedicated GitHub Action.
- **Extensibility:** SDKs for JavaScript, Python, Java, Rust (per GitHub org repos).
- **Providers:** Any via OTel/SDK.
- **Local/offline:** **Hybrid only** — self-hosted "data plane" (Postgres, Redis, S3, Brainstore) in customer infra while the control plane (UI, auth, org metadata) remains Braintrust-hosted; a cloud dependency persists even when "self-hosted"; BYOC alternative operated by Braintrust (https://www.braintrust.dev/docs/admin/self-hosting).
- **Report formats:** Web dashboards, custom charts (Pro+), experiment diff views.
- **Install complexity:** SaaS easy; self-host moderate-to-high and not independent.
- **Pricing/license:** Proprietary, closed-source core (permissive license only on deployment/Terraform tooling). Starter $0 ($10 credits, 1GB processed data, 10k scores, 14-day retention); Pro $249/mo; Enterprise custom (https://www.braintrust.dev/pricing).
- **Strengths:** Unified iterate→experiment→CI→production loop; strong dataset/experiment tooling; broad SDK language coverage.
- **Recurring complaints:** Visible community complaint signal is thin (**UNVERIFIED** breadth); independent comparisons consistently flag vendor lock-in (proprietary core; hybrid self-host still cloud-dependent).
- **Limitations:** Not usable air-gapped even self-hosted; no first-class deterministic trajectory matcher.
- **What we should NOT copy:** Marketing "self-hosted" while requiring a hosted control plane; metering processed-data GB/score counts for a CLI-first workflow.

Sources: https://www.braintrust.dev/docs/integrations/sdk-integrations/opentelemetry ; https://www.braintrust.dev/docs/best-practices/agents ; https://www.braintrust.dev/docs/admin/self-hosting ; https://www.braintrust.dev/docs/evaluate ; https://www.braintrust.dev/pricing ; https://github.com/braintrustdata ; https://github.com/braintrustdata/braintrust-deployment/blob/main/LICENSE ; comparison context: https://blog.promptlayer.com/braintrust-vs-langsmith ; https://mlflow.org/braintrust-alternative ; https://langfuse.com/resources/engineering/best-braintrustdata-alternatives

---

## 8. Langfuse

- **Intended user:** Teams wanting open-source, self-hostable LLM/agent observability + eval without vendor lock-in.
- **Job-to-be-done:** Observability, prompt management, datasets, and evaluation in one self-hostable platform.
- **Trace model:** Native SDKs (Python v3, JS/TS) plus an OpenTelemetry backend at `/api/public/otel` (OTLP); OpenLLMetry/OpenLIT extend language coverage. Friction: OTel auto-instrumentation captures *all* ambient spans (HTTP, auth libs); filtering requires manually enumerating `blocked_instrumentation_scopes`, no regex (https://langfuse.com/integrations/native/opentelemetry).
- **Evaluator model:** LLM-as-judge (each judge execution itself produces a debuggable trace) + code evaluators + external score ingestion (https://langfuse.com/docs/evaluation/overview).
- **Trajectory support:** No first-class trajectory evaluator. Discussion #5206 asked for trajectory evaluation "as core" (expected path, node revisit counts); maintainer answer was effectively roll-your-own eval function or LLM judge (https://github.com/orgs/langfuse/discussions/5206).
- **Datasets/experiments:** Datasets + experiments via UI/SDK; judges auto-run on new experiment runs.
- **Regression comparison:** "Score Analytics" trends; a LangSmith-authored comparison claims a two-score comparison limit — vendor-biased, treat cautiously (**UNVERIFIED** independently).
- **CI integration:** In progress — open issues labeled `feat-evals-ci-cd` as of Jul 2026 (e.g., #14907, opened 2026-07-08); not yet first-class.
- **Extensibility:** MIT license, broad framework integrations, OTel backend.
- **Providers:** Any via OTel/SDKs.
- **Local/offline:** **Strong.** MIT-licensed; "Self-host all core Langfuse features for free without any limitations"; depends only on OSS components (Postgres, Redis, ClickHouse, S3-compatible storage); Docker Compose for local, K8s/Terraform for production (https://langfuse.com/pricing-self-host ; https://langfuse.com/self-hosting).
- **Report formats:** Web dashboards, score analytics, exportable datasets.
- **Install complexity:** Low for local Docker Compose; higher for HA multi-service production.
- **Pricing/license:** MIT; cloud free tier to 50k units/mo; Self-Hosted Enterprise custom (RBAC/audit/retention add-ons).
- **Strengths:** True MIT open source with no self-host feature gating; native OTel backend; large community (24.4k stars at snapshot); fast-moving issue tracker.
- **Recurring complaints (langfuse/langfuse):** #11002 "fails to start during v2 → v3 migration" (2025-12-09, open); #11016 Redis OOM after minor upgrade 3.130.0→3.137.0; #10998 LLM-as-judge uses user message instead of system prompt; #11329 high latency on trace API (stale); #11269 S3 via corporate proxy closed "not planned."
- **Limitations:** No deterministic trajectory policy primitive; analytics depth contested; self-host major-version migrations have caused real outages; requires a database stack (not a single-binary/CLI experience).
- **What we should NOT copy:** Over-broad automatic capture without easy filtering; upgrade paths that can fail to start; declining vendor-schema ingestion is *defensible* (see discussion #6214 recommending OTel export instead) — the lesson is to normalize via documented formats, not scrape proprietary ones.

Sources: https://langfuse.com/integrations/native/opentelemetry ; https://langfuse.com/docs/evaluation/overview ; https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge ; https://langfuse.com/pricing-self-host ; https://langfuse.com/self-hosting ; https://github.com/orgs/langfuse/discussions/5206 ; https://github.com/orgs/langfuse/discussions/6214 ; https://github.com/langfuse/langfuse/issues (#11002, #11016, #10998, #11329, #11269, #14907)

---

## 9. Arize Phoenix

- **Intended user:** Developers/teams (including solo, notebook-first) wanting a free, privacy-preserving, air-gappable OSS observability+eval platform, with an upgrade path to the commercial Arize AX.
- **Job-to-be-done:** Tracing, datasets/experiments, and evals for LLM apps with genuine local operation.
- **Trace model:** Built on OpenTelemetry with the **OpenInference** semantic-convention layer (Apache-2.0, separate repo): AI-specific span kinds (LLM, Tool, Agent, Retriever) and attributes (`llm.input_messages`, `llm.token_count.total`). Broadest auto-instrumentor ecosystem observed: LangChain, LangGraph, LlamaIndex, AutoGen, CrewAI, BeeAI, Vercel AI SDK, OpenAI, Bedrock, Anthropic, Groq, LiteLLM, Google ADK, Pydantic AI, DSPy, MCP, and more, across Python/JS/Java/Go (https://github.com/Arize-ai/openinference).
- **Evaluator model:** LLM-as-judge (`arize-phoenix-evals`) + code-based evaluators.
- **Trajectory support:** No explicit deterministic trajectory-match primitive documented in the sources reviewed — **UNVERIFIED** whether one exists deeper in evals docs.
- **Datasets/experiments:** Native versioned Datasets and Experiments, non-gated.
- **Regression comparison / statistics:** General experiment tracking; no statistical-significance feature found (**UNVERIFIED**/likely absent).
- **CI integration:** `@arizeai/phoenix-cli` exists for fetching traces/datasets/experiments for coding agents; a dedicated CI gate was not confirmed.
- **Extensibility:** Python/TS/Java/Go instrumentors; MCP server package; in-product PXI debugging agent.
- **Providers:** All major providers/frameworks via OpenInference.
- **Local/offline:** **Strongest of the platforms reviewed:** `pip install arize-phoenix && phoenix serve`, runs locally/notebook/container; "free to self-host with no feature limitations"; "nothing is sent to Arize and can be fully air-gapped"; telemetry is basic web analytics only, disableable via `PHOENIX_TELEMETRY_ENABLED=false` (https://arize.com/docs/phoenix/self-hosting ; https://github.com/Arize-ai/phoenix).
- **Report formats:** Web UI, GraphQL API, CLI-fetchable data.
- **Install complexity:** Lowest of the four platforms (pip + one command).
- **Pricing/license:** **Elastic License 2.0** (source-available, not OSI open source) with patent-protected portions — free to self-host but with redistribution restrictions; distinct from Langfuse's MIT (https://github.com/Arize-ai/phoenix).
- **Strengths:** Real zero-server local-first operation; broadest OTel/OpenInference instrumentation; explicit air-gap support.
- **Recurring complaints:** Discussion #10621 (unanswered): no zero-code/proxy-free way to trace a raw model server (llama.cpp) — instrumentation always requires code changes or a proxy. Broader issue-level complaint sampling was not completed in this pass (flagged gap).
- **Limitations:** ELv2 license implications for redistribution; trajectory-evaluator gap; no passive capture.
- **What we should NOT copy:** Nothing structurally bad identified; the caution is labeling — don't call a source-available license "open source." The pip-install-and-run model and real air-gap support are worth emulating.
- **Research note:** one Phoenix OTEL setup docs page contained an apparent embedded prompt-injection block (fake "AI AGENT INSTRUCTION" text); it was treated as inert page content and ignored.

Sources: https://github.com/Arize-ai/phoenix ; https://arize.com/docs/phoenix/self-hosting ; https://arize.com/docs/phoenix/tracing/how-to-tracing/setup-tracing/setup-using-phoenix-otel ; https://arize.com/docs/phoenix/tracing/concepts-tracing/otel-openinference/overview ; https://github.com/Arize-ai/openinference ; https://github.com/Arize-ai/phoenix/discussions/10621

---

## 10. Promptfoo

- **Intended user:** App developers and red-teamers; YAML-first and not Python-specific. Organizationally now part of OpenAI; "remains open source and MIT licensed."
- **Job-to-be-done:** Declarative prompt/model/provider matrix testing plus red-teaming/vulnerability scanning; agent/coding-agent evaluation is a newer documented extension.
- **Trace model:** No first-class canonical trace object in the config schema; custom providers return output + metadata; OpenTelemetry ingestion renders trace timelines in the UI; a `trajectory:*` assertion family exists (e.g. `trajectory:tool-args-match`).
- **Evaluator model:** Strong deterministic assertion library (`equals`, `contains`, `regex`, `javascript`, ...) + LLM-graded assertions (`llm-rubric`, `factuality`, `context-recall`, ...).
- **Trajectory support:** Documented for coding agents (guide published 2026-07-11; "Assert the path when the path matters"); current tool-args matching appears exact-match-only — open issue #9842 requests wildcard support (https://github.com/promptfoo/promptfoo/issues/9842).
- **Datasets/experiments:** CSV, Google Sheets, HuggingFace datasets as test cases.
- **Regression comparison:** Built around before/after comparison for CI with an interactive diff viewer.
- **CI integration:** The most mature of the tools reviewed: `promptfoo/promptfoo-action` with path-based skip logic, `force-run`, `repeat` + `repeat-min-pass` flake tolerance, caching, `fail-on-threshold` (https://github.com/promptfoo/promptfoo-action).
- **Extensibility:** Custom providers (`file://` JS/Python), custom assertions, red-team plugins, MCP-based agent testing.
- **Providers:** Dozens (OpenAI, Anthropic, Azure, Bedrock, Ollama, ...) plus coding-agent providers (Codex SDK, Claude Agent SDK, OpenCode SDK).
- **Local/offline:** CLI runs and caches locally; community tier supports self-host.
- **Report formats:** Local web viewer, before/after diffs, JSON/CSV export, PR comments.
- **Install complexity:** Low-moderate: `npm install -g promptfoo` (Node ^20.20 or ≥22.22) or `npx`; the Node runtime is friction for Python-first teams.
- **Pricing/license:** MIT core, free Community tier (all eval features, 10k red-team probes/mo); paid Enterprise/On-Prem tiers.
- **Strengths:** Best-in-class CI ergonomics; huge provider/red-team catalog; large community (23k+ stars); dataset breadth.
- **Recurring complaints (promptfoo/promptfoo):** #9910 "context-recall and context-relevance default threshold to 0, silently always pass" and #9848 same for answer-relevance (Jun 2026) — silent-pass footgun class; #9968 telemetry beacon fires even with `PROMPTFOO_DISABLE_TELEMETRY` set (2026-07-04); #2729 temperature-0 + seed still nondeterministic across users, "hampering trust in the tool," reconfirmed Jan 2026; #7528 npm peer-dependency install friction; #9895 comment-stripping parse bug; #9842/#9915 open agent-eval gaps.
- **Limitations:** Node-only runtime; trajectory features layered onto a matrix-testing core; assertion-safety not designed defensively (threshold defaults).
- **What we should NOT copy:** Silent-pass-by-default thresholds; telemetry that ignores opt-out flags; Node-only distribution for a Python-centric audience.

Sources: https://github.com/promptfoo/promptfoo ; https://github.com/promptfoo/promptfoo-action ; https://www.promptfoo.dev/pricing ; https://www.promptfoo.dev/docs/integrations/github-action/ ; https://www.promptfoo.dev/docs/guides/evaluate-coding-agents/ ; issues: https://github.com/promptfoo/promptfoo/issues/9968 , /9910 , /9848 , /9895 , /9842 , /9915 , /7528 , /2729

---

## 11. DeepEval

- **Intended user:** Python AI engineers wanting pytest-native LLM/agent evaluation in existing test suites and CI.
- **Job-to-be-done:** Unit-test-style LLM evaluation with a large catalog (50+) of metrics across RAG, agents, chatbots, safety.
- **Trace model:** `@observe()` decorator builds a trace tree over nested functions; some metrics (`TaskCompletionMetric`) require full-trace instrumentation; OTel export exists.
- **Evaluator model:** Deterministic metrics (Tool Correctness with exact/parameterized matching; JSON Correctness) + a majority of LLM-as-judge metrics (G-Eval, DAG, Task Completion, Faithfulness, ...).
- **Trajectory support:** The most differentiated among code-first OSS tools: six agentic metrics — Task Completion, Argument Correctness, Tool Correctness, Step Efficiency, Plan Adherence, Plan Quality; `ToolCorrectnessMetric` compares `tools_called` vs `expected_tools` with configurable strictness; multi-turn variants shipped after issue #2223 (https://deepeval.com/docs/metrics-tool-correctness).
- **Datasets/experiments:** `EvaluationDataset`/`Golden`, `evals_iterator()`, synthetic data generation; Confident AI cloud optional.
- **Regression comparison:** pytest thresholds fail the build; iteration-comparison dashboards live in the paid Confident AI cloud, not the OSS core.
- **CI integration:** Native pytest (`deepeval test run`) — zero special action needed.
- **Extensibility:** G-Eval rubrics, DAG composite metrics, `BaseMetric` subclassing.
- **Providers:** Judge-model agnostic; integrations for OpenAI Agents SDK, LangChain, LangGraph, Pydantic AI, CrewAI, Anthropic, AWS AgentCore, LlamaIndex.
- **Local/offline:** Core runs locally; login "highly recommended" but not required; cloud opt-in.
- **Report formats:** CLI/pytest output; optional cloud dashboards.
- **Install complexity:** Low (`pip install deepeval`, Python ≥3.9).
- **Pricing/license:** Apache 2.0 OSS; Confident AI cloud has free + paid tiers.
- **Strengths:** Deepest agentic metric set; pytest-native CI; Apache 2.0; strong framework integrations.
- **Recurring complaints (confident-ai/deepeval):** three template-rendering bugs in the flagship agentic metrics within ~2 weeks — #2859 `TaskCompletionMetric` "Missing variable... 'tools_called_formatted'" (2026-07-07); #2817 `ArgumentCorrectnessMetric` "'stringified_tools_called' is undefined" (2026-06-29); #2807 wrong Jinja variable passed (2026-06-26). Also #2821 quickstart example fails with `NoMetricsError`; #940 wrong metric shown in docs (2024). Open feature requests show unmet demand for deterministic policy checks: #2825 "ToolPermissionMetric — deterministic check that an agent only called authorized tools" (2026-07-01) and #2856 "AgentEscalationMetric."
- **Limitations:** Flagship agent metrics depend on LLM judges (cost/nondeterminism at CI scale); fragile string-templated internals; no OSS diff/regression UI.
- **What we should NOT copy:** Building critical trajectory metrics on fragile string templating (validate internal contracts with typed schemas/tests); auto-inferring tasks via LLM for pass/fail policy gates (explicit declared expectations for policy; LLM inference only for open-ended quality).

Sources: https://github.com/confident-ai/deepeval ; https://deepeval.com/docs/metrics-introduction ; https://deepeval.com/docs/metrics-tool-correctness ; https://deepeval.com/docs/metrics-task-completion ; https://deepeval.com/docs/data-privacy ; issues: https://github.com/confident-ai/deepeval/issues/2859 , /2856 , /2825 , /2821 , /2817 , /2807 , /2223 , /940

---

## 12. AgentOps

- **Intended user:** Developers on agent frameworks (CrewAI, AutoGen/AG2, LangChain, OpenAI Agents SDK, Agno, Camel AI) wanting production observability.
- **Job-to-be-done:** Observability/DevTool platform: session replay, cost tracking, debugging "from prototype to production." Evaluation is secondary.
- **Trace model:** Session-centric runs capturing LLM calls, tool invocations, decision points; "Time Travel Debugging"; visual multi-agent graphs.
- **Evaluator model:** Weakest of the tools reviewed — the README's own roadmap marks most eval capabilities unshipped: "🚧 Success validators (external)", "🔜 Regression testing", "🔜 CI/CD integration checks", "🔜 Agent controllers/skill tests", "🔜 Faulty reasoning detection" (https://github.com/AgentOps-AI/agentops).
- **Trajectory support:** Session replay/visualization for inspection; no declarative pass/fail trajectory assertions.
- **Datasets/experiments:** Not dataset-driven; centered on live/replayed sessions.
- **Regression comparison:** Explicitly unshipped (roadmap).
- **CI integration:** Explicitly unshipped (roadmap).
- **Extensibility:** Two-line SDK instrumentation; many framework integrations.
- **Providers:** 400+ LLMs claimed for cost tracking.
- **Local/offline:** Hosted SaaS dashboard by default; self-hosting listed under paid Enterprise features; SDK itself is MIT.
- **Report formats:** Web dashboard (replay, cost graphs, graphs).
- **Install complexity:** Low (`pip install agentops`).
- **Pricing/license:** MIT SDK/app; Basic free tier capped at 5,000 events/month; Pro from $40/mo; Enterprise custom (self-host, SOC-2/HIPAA).
- **Strengths:** Framework integration breadth; genuinely useful production replay debugging; enterprise adoption for observability.
- **Recurring complaints/limitations:** The vendor's own roadmap table documents the gaps; third-party comparisons position it as production observability, not evaluation; one trajectory-scoring comparison doesn't list it at all.
- **What we should NOT copy:** Hosted dashboard with event-count paywalls for CI-shaped workloads; leaving CI/regression as a permanent roadmap item; self-hosting gated behind Enterprise pricing.

Sources: https://github.com/AgentOps-AI/agentops ; https://www.agentops.ai/ ; https://infrabase.ai/agents/agentops ; https://aimultiple.com/agentic-monitoring ; https://www.braintrust.dev/articles/best-ai-observability-tools-2026

---

## 13. OpenTelemetry Generative-AI Semantic Conventions

- **What/where:** GenAI semconv moved out of the main semconv repo into **`open-telemetry/semantic-conventions-genai`**; old `opentelemetry.io/docs/specs/semconv/gen-ai/` pages are deprecated stubs. Treat the new repo as canonical (https://github.com/open-telemetry/semantic-conventions-genai).
- **Stability:** Essentially everything is **"Development" status** (not Stable) except a few shared attributes (`error.type`, `server.address`, `server.port`). Breaking changes are expected; consumers should pin a semconv version.
- **Span model:** Inference (`{operation} {model}` naming), embeddings, retrieval, create_agent, invoke_agent (client/internal), invoke_workflow, plan, and **Execute tool span** (`execute_tool {gen_ai.tool.name}`). Primary discriminator: `gen_ai.operation.name` (values include `chat`, `execute_tool`, `invoke_agent`, `plan`, memory ops...).
- **Key attributes:** `gen_ai.provider.name` (well-known values incl. `openai`, `anthropic`, `aws.bedrock`, `cohere`, ...); request/response params; `gen_ai.usage.input_tokens`/`output_tokens`; `gen_ai.conversation.id`; `gen_ai.agent.*`; tool attributes `gen_ai.tool.name` (Required), `gen_ai.tool.call.id`, `gen_ai.tool.type` (`function`/`extension`/`datastore`), and **Opt-In** `gen_ai.tool.call.arguments` / `gen_ai.tool.call.result`. Message content (`gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.system_instructions`) is Opt-In (PII) and follows a published role/parts JSON Schema — the closest thing to a canonical message/tool-call format in the spec.
- **Events:** `gen_ai.client.inference.operation.details` (detailed content logging via Logs API) and `gen_ai.evaluation.result` (`gen_ai.evaluation.name`, `score.label`, `score.value`, `explanation`, `error.type`, `gen_ai.response.id`) — a standard, interoperable shape for evaluation verdicts that MLflow already adopts.
- **Ingestion guidance for a harness:** group spans by `trace_id`, order by start time; switch on `gen_ai.operation.name`; extract tool name/args/result from `execute_tool` spans and correlate via parent-span-id plus `tool.call.id` in `gen_ai.output.messages`; use `gen_ai.conversation.id` only when present (never synthesize); treat Opt-In fields as possibly absent and **fail clearly** when a check needs missing data (never silently pass); pin the semconv version.
- **Implication for this project:** an OTel GenAI adapter is feasible and valuable but must be version-pinned and defensive because the conventions are Development-status; emitting `gen_ai.evaluation.result`-shaped verdicts is a good interoperability target.

Sources: https://github.com/open-telemetry/semantic-conventions-genai ; https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/gen-ai/gen-ai-spans.md ; .../gen-ai-agent-spans.md ; .../gen-ai-events.md ; https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/ (deprecated redirect) ; https://mlflow.org/docs/latest/genai/tracing/opentelemetry/genai-semconv/

---

## Cross-Cutting Synthesis

1. **The gap is real and specific.** No reviewed public tool ships a *local-first, deterministic, declarative policy engine over recorded tool-use traces with baseline regression gating*. The closest prior art: LangChain `agentevals` (deterministic strict/unordered/subset trajectory match, but reference-trajectory-based, no policy language, no baseline diff artifacts) and DeepEval's agentic metrics (largely LLM-judged, with users actively requesting deterministic policy checks — deepeval #2825). Langfuse maintainers punt trajectory evaluation to roll-your-own (discussion #5206). Observability platforms (LangSmith, Langfuse, Phoenix, AgentOps) observe; they do not gate merges on trajectory policy.
2. **Constraint-based beats golden-path.** Anthropic's engineering guidance explicitly warns exact tool-sequence checks are "too rigid"; the LangChain forum documents strict-vs-unordered being simultaneously too rigid and too loose. A policy language of allowlists, partial ordering, counts, budgets, retry/side-effect rules addresses the documented middle ground.
3. **Determinism is a differentiator with evidence.** Nondeterministic graders and even nondeterministic "deterministic" configs (promptfoo #2729) erode trust; Inspect #4026 shows silent fail-defaulting in model graders. A no-LLM, byte-stable evaluation core is defensible and cheap.
4. **Fail loudly.** Silent-pass threshold defaults (promptfoo #9910/#9848) and silent INCORRECT defaults (Inspect #4026) are the most damaging bug class in this space. Missing data required by a policy check must produce a finding, not a pass.
5. **Local-first must be literal.** Zero telemetry (promptfoo #9968 shows opt-outs failing), zero vendor control plane (Braintrust hybrid self-host), zero license keys (LangSmith Enterprise self-host), zero heavyweight runtime deps (Inspect's Docker; promptfoo's Node).
6. **Stability is a feature.** Version churn breaking downstream users (Inspect #4027, inspect_evals #442; Langfuse v2→v3 migration failures; DeepEval template breakage ×3) argues for versioned schemas, additive changes, and migration support.
7. **Interoperate via documented formats.** OTel GenAI semconv (Development status; pin versions) and provider transcript formats (OpenAI chat, Anthropic messages) are the sane ingestion targets; scraping proprietary vendor schemas is a maintenance trap (langfuse discussion #6214).
8. **Repeat-run statistics matter.** pass@k/pass^k framing (Anthropic; tau-bench) exposes reliability that single runs hide; a regression harness should eventually support multi-run consistency reporting (roadmap, not v1).
9. **Do not benchmark against moving/deprecated targets.** OpenAI's hosted Evals platform sunsets Nov 2026; "OpenAI Frontier Evals" is not a coherent public product. Comparisons must name specific, verifiable, current tools.
