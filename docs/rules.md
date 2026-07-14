# Rule Reference

All findings carry one of these stable rule IDs. IDs never change meaning;
new rules get new IDs. This file is generated from the rule registry
(`src/agent_reliability_harness/rules.py`); regenerate it with
`python tools/generate_rules_doc.py` after changing the registry.

## Schema (tool-call contracts)

### ARH-SCH-001

**Tool is not allowed by the policy** (default severity: error)

Remediation: Add the tool to policy allowed_tools, or fix the agent's tool selection.

### ARH-SCH-002

**tool_call step has no tool_name** (default severity: error)

Remediation: Ensure the trace exporter records a tool name for every tool_call step.

### ARH-SCH-003

**Required argument is missing** (default severity: error)

Remediation: Fix the agent prompt/tool signature so the required argument is always supplied.

### ARH-SCH-004

**Argument has the wrong type** (default severity: error)

Remediation: Align the agent's argument construction with the declared type in the policy.

### ARH-SCH-005

**Argument is not declared in the policy** (default severity: warning)

Remediation: Declare the argument in the policy (required or optional) or stop passing it.

### ARH-SCH-006

**Policy declares an unknown argument type** (default severity: info)

Remediation: Fix the policy: use one of str, int, float, bool, list, dict, any.

### ARH-SCH-007

**Argument value is not in the allowed enum** (default severity: error)

Remediation: Constrain the agent to the allowed values, or extend the policy enum.

### ARH-SCH-008

**Argument value does not match the required pattern** (default severity: error)

Remediation: Fix the agent's argument formatting to match the policy pattern.

### ARH-SCH-009

**Argument value is outside the allowed numeric range** (default severity: error)

Remediation: Clamp or validate the value in the agent before calling the tool.

### ARH-SCH-010

**Duplicate step_id in trace** (default severity: warning)

Remediation: Make the trace exporter emit unique step IDs; duplicates weaken finding locations.

## Budgets

### ARH-BUD-001

**Step latency exceeds the per-step budget** (default severity: error)

Remediation: Investigate the slow step; raise max_step_latency_ms only if the SLO changed.

### ARH-BUD-002

**Total trace latency exceeds the budget** (default severity: error)

Remediation: Reduce steps or per-step latency; raise max_total_latency_ms only if the SLO changed.

### ARH-BUD-003

**Total trace cost exceeds the budget** (default severity: error)

Remediation: Reduce model/tool usage; raise max_total_cost_usd only if the budget changed.

### ARH-BUD-004

**Total token usage exceeds the budget** (default severity: error)

Remediation: Trim prompts/outputs or reduce steps; raise max_total_tokens only if the budget changed.

### ARH-BUD-005

**Token budget is set but the trace has no token data** (default severity: warning)

Remediation: Record input_tokens/output_tokens in the trace, or remove max_total_tokens.

## Safety

### ARH-SAF-001

**Content matches a disallowed pattern** (default severity: error)

Remediation: Trace content matched an unsafe-pattern regex (e.g. prompt injection or a secret). Sanitize inputs/outputs and add guardrails at the matching step.

## Grounding

### ARH-GRD-001

**Grounding-required response has no citations** (default severity: error)

Remediation: Make the agent attach citations to responses that assert facts.

### ARH-GRD-002

**Citation coverage is below the policy minimum** (default severity: error)

Remediation: Increase grounding coverage or adjust min_citation_coverage if the policy changed.

### ARH-GRD-003

**Citation is malformed or has an invalid URL** (default severity: error)

Remediation: Citations must include a non-empty source or a valid http(s) URL.

## Sequence (trajectory shape)

### ARH-SEQ-001

**Required tool was never called** (default severity: error)

Remediation: The workflow requires this tool; fix agent planning or the policy's required_tools.

### ARH-SEQ-002

**Forbidden tool was called** (default severity: error)

Remediation: The agent must not use this tool in this workflow; remove it from the tool set or fix tool selection.

### ARH-SEQ-003

**Tools were called in the wrong order** (default severity: error)

Remediation: The policy call_order requires the earlier tool's first call to precede the later tool's first call.

### ARH-SEQ-004

**Tool was called more times than max_calls** (default severity: error)

Remediation: Reduce redundant calls (possible loop) or raise max_calls if intended.

### ARH-SEQ-005

**Tool was called fewer times than min_calls** (default severity: error)

Remediation: The workflow expects more calls of this tool; fix agent planning or min_calls.

## Flow (errors and side effects)

### ARH-FLW-001

**Tool error was never retried** (default severity: error)

Remediation: The agent ignored a failed tool call; add retry/error handling.

### ARH-FLW-002

**Retry storm: identical call repeated beyond max_attempts** (default severity: error)

Remediation: Add backoff/branching; the agent is stuck repeating the same call.

### ARH-FLW-003

**Duplicate side-effect call with identical arguments** (default severity: error)

Remediation: A side-effecting tool ran twice with the same arguments after already succeeding; make the action idempotent or fix agent control flow.

## Completion

### ARH-CMP-001

**Trace does not end with a successful final response** (default severity: error)

Remediation: The agent stopped without answering (or errored at the end); ensure a final model_response step.

### ARH-CMP-002

**Trace exceeds the maximum step count** (default severity: error)

Remediation: The agent ran too long (possible failure to terminate); investigate loops.

