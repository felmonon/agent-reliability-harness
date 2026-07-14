"""Stable rule registry.

Every finding produced by the validator carries a stable ``rule_id`` from
this registry. Rule IDs are part of the public contract: they are used for
regression fingerprinting, SARIF rule metadata, CI annotations, and
documentation links, and they never change meaning across releases. New
rules append new IDs; retired rules are never reused.
"""

from __future__ import annotations

from dataclasses import dataclass

DOCS_BASE_URL = "https://github.com/felmonon/agent-reliability-harness/blob/main/docs/rules.md"


@dataclass(frozen=True)
class Rule:
    """Metadata for one validation rule."""

    rule_id: str
    category: str
    summary: str
    default_severity: str
    remediation: str

    @property
    def help_uri(self) -> str:
        return f"{DOCS_BASE_URL}#{self.rule_id.lower()}"


_RULES = [
    # --- schema: tool-call contract conformance -------------------------
    Rule("ARH-SCH-001", "schema", "Tool is not allowed by the policy", "error",
         "Add the tool to policy allowed_tools, or fix the agent's tool selection."),
    Rule("ARH-SCH-002", "schema", "tool_call step has no tool_name", "error",
         "Ensure the trace exporter records a tool name for every tool_call step."),
    Rule("ARH-SCH-003", "schema", "Required argument is missing", "error",
         "Fix the agent prompt/tool signature so the required argument is always supplied."),
    Rule("ARH-SCH-004", "schema", "Argument has the wrong type", "error",
         "Align the agent's argument construction with the declared type in the policy."),
    Rule("ARH-SCH-005", "schema", "Argument is not declared in the policy", "warning",
         "Declare the argument in the policy (required or optional) or stop passing it."),
    Rule("ARH-SCH-006", "schema", "Policy declares an unknown argument type", "info",
         "Fix the policy: use one of str, int, float, bool, list, dict, any."),
    Rule("ARH-SCH-007", "schema", "Argument value is not in the allowed enum", "error",
         "Constrain the agent to the allowed values, or extend the policy enum."),
    Rule("ARH-SCH-008", "schema", "Argument value does not match the required pattern", "error",
         "Fix the agent's argument formatting to match the policy pattern."),
    Rule("ARH-SCH-009", "schema", "Argument value is outside the allowed numeric range", "error",
         "Clamp or validate the value in the agent before calling the tool."),
    Rule("ARH-SCH-010", "schema", "Duplicate step_id in trace", "warning",
         "Make the trace exporter emit unique step IDs; duplicates weaken finding locations."),
    # --- budget: latency / cost / tokens --------------------------------
    Rule("ARH-BUD-001", "budget", "Step latency exceeds the per-step budget", "error",
         "Investigate the slow step; raise max_step_latency_ms only if the SLO changed."),
    Rule("ARH-BUD-002", "budget", "Total trace latency exceeds the budget", "error",
         "Reduce steps or per-step latency; raise max_total_latency_ms only if the SLO changed."),
    Rule("ARH-BUD-003", "budget", "Total trace cost exceeds the budget", "error",
         "Reduce model/tool usage; raise max_total_cost_usd only if the budget changed."),
    Rule("ARH-BUD-004", "budget", "Total token usage exceeds the budget", "error",
         "Trim prompts/outputs or reduce steps; raise max_total_tokens only if the budget changed."),
    Rule("ARH-BUD-005", "budget", "Token budget is set but the trace has no token data", "warning",
         "Record input_tokens/output_tokens in the trace, or remove max_total_tokens."),
    # --- safety: disallowed content -------------------------------------
    Rule("ARH-SAF-001", "safety", "Content matches a disallowed pattern", "error",
         "Trace content matched an unsafe-pattern regex (e.g. prompt injection or a secret). "
         "Sanitize inputs/outputs and add guardrails at the matching step."),
    # --- grounding: citations --------------------------------------------
    Rule("ARH-GRD-001", "grounding", "Grounding-required response has no citations", "error",
         "Make the agent attach citations to responses that assert facts."),
    Rule("ARH-GRD-002", "grounding", "Citation coverage is below the policy minimum", "error",
         "Increase grounding coverage or adjust min_citation_coverage if the policy changed."),
    Rule("ARH-GRD-003", "grounding", "Citation is malformed or has an invalid URL", "error",
         "Citations must include a non-empty source or a valid http(s) URL."),
    # --- sequence: trajectory shape --------------------------------------
    Rule("ARH-SEQ-001", "sequence", "Required tool was never called", "error",
         "The workflow requires this tool; fix agent planning or the policy's required_tools."),
    Rule("ARH-SEQ-002", "sequence", "Forbidden tool was called", "error",
         "The agent must not use this tool in this workflow; remove it from the tool set "
         "or fix tool selection."),
    Rule("ARH-SEQ-003", "sequence", "Tools were called in the wrong order", "error",
         "The policy call_order requires the earlier tool's first call to precede the "
         "later tool's first call."),
    Rule("ARH-SEQ-004", "sequence", "Tool was called more times than max_calls", "error",
         "Reduce redundant calls (possible loop) or raise max_calls if intended."),
    Rule("ARH-SEQ-005", "sequence", "Tool was called fewer times than min_calls", "error",
         "The workflow expects more calls of this tool; fix agent planning or min_calls."),
    # --- flow: error handling and side effects ---------------------------
    Rule("ARH-FLW-001", "flow", "Tool error was never retried", "error",
         "The agent ignored a failed tool call; add retry/error handling."),
    Rule("ARH-FLW-002", "flow", "Retry storm: identical call repeated beyond max_attempts", "error",
         "Add backoff/branching; the agent is stuck repeating the same call."),
    Rule("ARH-FLW-003", "flow", "Duplicate side-effect call with identical arguments", "error",
         "A side-effecting tool ran twice with the same arguments after already succeeding; "
         "make the action idempotent or fix agent control flow."),
    # --- completion: task termination -------------------------------------
    Rule("ARH-CMP-001", "completion", "Trace does not end with a successful final response", "error",
         "The agent stopped without answering (or errored at the end); ensure a final "
         "model_response step."),
    Rule("ARH-CMP-002", "completion", "Trace exceeds the maximum step count", "error",
         "The agent ran too long (possible failure to terminate); investigate loops."),
]

RULES: dict[str, Rule] = {rule.rule_id: rule for rule in _RULES}

#: Fallback rule id for findings constructed without one (e.g. by external code).
UNKNOWN_RULE_ID = "ARH-000"


def get_rule(rule_id: str) -> Rule:
    """Look up a rule; unknown IDs return a generic placeholder rule."""
    return RULES.get(
        rule_id,
        Rule(UNKNOWN_RULE_ID, "unknown", "Unregistered finding", "warning",
             "This finding was produced outside the built-in rule registry."),
    )
