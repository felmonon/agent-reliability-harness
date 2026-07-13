"""Core validation logic.

``validate_trace`` runs four independent checks against a trace:

1. **Schema conformance** - every ``tool_call`` step must call a tool listed
   in the policy's ``allowed_tools``, and must supply all of that tool's
   required arguments with the declared type.
2. **Budgets** - total/step latency and total cost must stay within the
   policy's ceilings.
3. **Safety** - free-text output (tool outputs and model response text) is
   scanned for disallowed patterns (regexes), e.g. prompt-injection phrases
   or secret-like strings.
4. **Grounding/citations** - for steps flagged ``requires_grounding``, a
   non-empty ``citations`` list is expected; overall coverage is compared
   against the policy's minimum.

Each check appends zero or more ``Finding`` objects and contributes to a
weighted 0-100 score. The trace "passes" when there are no ``error``-level
findings and the score meets/exceeds ``fail_under`` (default 70).
"""

from __future__ import annotations

import re
from typing import Any

from agent_reliability_harness.models import (
    Finding,
    Policy,
    Step,
    Trace,
    TraceReport,
    TYPE_MAP,
)

DEFAULT_FAIL_UNDER = 70.0

# Category weights must sum to 1.0; a category with no applicable checks
# (e.g. no tool calls, or no grounding-required steps) is excluded and the
# remaining weights are renormalized.
_CATEGORY_WEIGHTS = {
    "schema": 0.3,
    "budget": 0.3,
    "safety": 0.25,
    "grounding": 0.15,
}


def _check_schema(trace: Trace, policy: Policy) -> tuple[list[Finding], float, bool]:
    """Validate tool_call steps against policy.allowed_tools.

    Returns (findings, category_score_0_100, applicable).
    """
    findings: list[Finding] = []
    tool_calls = [s for s in trace.steps if s.type == "tool_call"]
    if not tool_calls:
        return findings, 100.0, False

    total_checks = 0
    passed_checks = 0
    for step in tool_calls:
        total_checks += 1
        tool_name = step.tool_name
        if not tool_name:
            findings.append(
                Finding(
                    severity="error",
                    category="schema",
                    step_id=step.step_id,
                    message="tool_call step has no 'tool_name'",
                )
            )
            continue

        schema = policy.allowed_tools.get(tool_name)
        if schema is None:
            if policy.allow_unlisted_tools:
                passed_checks += 1
                continue
            findings.append(
                Finding(
                    severity="error",
                    category="schema",
                    step_id=step.step_id,
                    message=f"tool '{tool_name}' is not in the allowed_tools policy",
                )
            )
            continue

        arguments = step.arguments or {}
        step_ok = True

        for arg_name, arg_type in schema.required_arguments.items():
            if arg_name not in arguments:
                findings.append(
                    Finding(
                        severity="error",
                        category="schema",
                        step_id=step.step_id,
                        message=(
                            f"tool '{tool_name}' call is missing required "
                            f"argument '{arg_name}'"
                        ),
                    )
                )
                step_ok = False
                continue
            step_ok &= _check_arg_type(
                trace, tool_name, step, arg_name, arg_type, arguments[arg_name], findings
            )

        all_declared = {**schema.required_arguments, **schema.optional_arguments}
        for arg_name, arg_value in arguments.items():
            if arg_name in all_declared:
                arg_type = all_declared[arg_name]
                step_ok &= _check_arg_type(
                    trace, tool_name, step, arg_name, arg_type, arg_value, findings
                )
            else:
                findings.append(
                    Finding(
                        severity="warning",
                        category="schema",
                        step_id=step.step_id,
                        message=(
                            f"tool '{tool_name}' call has undeclared argument "
                            f"'{arg_name}'"
                        ),
                    )
                )

        if step_ok:
            passed_checks += 1

    score = 100.0 * passed_checks / total_checks if total_checks else 100.0
    return findings, score, True


def _check_arg_type(
    trace: Trace,
    tool_name: str,
    step: Step,
    arg_name: str,
    arg_type: str,
    arg_value: Any,
    findings: list[Finding],
) -> bool:
    expected = TYPE_MAP.get(arg_type)
    if expected is None:
        # Unknown declared type in the policy itself; treat permissively but
        # surface it so the policy author can fix it.
        findings.append(
            Finding(
                severity="info",
                category="schema",
                step_id=step.step_id,
                message=(
                    f"policy declares unknown type '{arg_type}' for "
                    f"'{tool_name}.{arg_name}'; skipping type check"
                ),
            )
        )
        return True
    if expected == (object,):
        return True
    if isinstance(arg_value, bool) and expected != (bool,):
        # bool is a subclass of int in Python; don't let a bool satisfy "int".
        ok = False
    else:
        ok = isinstance(arg_value, expected)
    if not ok:
        findings.append(
            Finding(
                severity="error",
                category="schema",
                step_id=step.step_id,
                message=(
                    f"tool '{tool_name}' argument '{arg_name}' expected type "
                    f"'{arg_type}' but got '{type(arg_value).__name__}'"
                ),
            )
        )
    return ok


def _check_budgets(trace: Trace, policy: Policy) -> tuple[list[Finding], float, bool, float, float]:
    findings: list[Finding] = []
    budgets = policy.budgets
    applicable = any(
        v is not None
        for v in (
            budgets.max_total_latency_ms,
            budgets.max_step_latency_ms,
            budgets.max_total_cost_usd,
        )
    )

    total_latency = sum(s.latency_ms or 0.0 for s in trace.steps)
    total_cost = sum(s.cost_usd or 0.0 for s in trace.steps)

    if not applicable:
        return findings, 100.0, False, total_latency, total_cost

    checks_total = 0
    checks_passed = 0

    if budgets.max_step_latency_ms is not None:
        for step in trace.steps:
            if step.latency_ms is None:
                continue
            checks_total += 1
            if step.latency_ms > budgets.max_step_latency_ms:
                findings.append(
                    Finding(
                        severity="error",
                        category="budget",
                        step_id=step.step_id,
                        message=(
                            f"step latency {step.latency_ms:.0f}ms exceeds "
                            f"max_step_latency_ms budget of "
                            f"{budgets.max_step_latency_ms:.0f}ms"
                        ),
                    )
                )
            else:
                checks_passed += 1

    if budgets.max_total_latency_ms is not None:
        checks_total += 1
        if total_latency > budgets.max_total_latency_ms:
            findings.append(
                Finding(
                    severity="error",
                    category="budget",
                    step_id=None,
                    message=(
                        f"total trace latency {total_latency:.0f}ms exceeds "
                        f"max_total_latency_ms budget of "
                        f"{budgets.max_total_latency_ms:.0f}ms"
                    ),
                )
            )
        else:
            checks_passed += 1

    if budgets.max_total_cost_usd is not None:
        checks_total += 1
        if total_cost > budgets.max_total_cost_usd:
            findings.append(
                Finding(
                    severity="error",
                    category="budget",
                    step_id=None,
                    message=(
                        f"total trace cost ${total_cost:.4f} exceeds "
                        f"max_total_cost_usd budget of "
                        f"${budgets.max_total_cost_usd:.4f}"
                    ),
                )
            )
        else:
            checks_passed += 1

    score = 100.0 * checks_passed / checks_total if checks_total else 100.0
    return findings, score, True, total_latency, total_cost


def _iter_text_blobs(step: Step) -> list[str]:
    blobs: list[str] = []
    if step.text:
        blobs.append(step.text)
    if isinstance(step.output, str):
        blobs.append(step.output)
    elif isinstance(step.output, dict):
        for value in step.output.values():
            if isinstance(value, str):
                blobs.append(value)
    if isinstance(step.arguments, dict):
        for value in step.arguments.values():
            if isinstance(value, str):
                blobs.append(value)
    return blobs


def _check_safety(trace: Trace, policy: Policy) -> tuple[list[Finding], float, bool]:
    findings: list[Finding] = []
    if not policy.unsafe_patterns:
        return findings, 100.0, False

    compiled = [re.compile(p, re.IGNORECASE) for p in policy.unsafe_patterns]

    total_checks = 0
    violations = 0
    for step in trace.steps:
        for blob in _iter_text_blobs(step):
            total_checks += 1
            for pattern, raw_pattern in zip(compiled, policy.unsafe_patterns):
                match = pattern.search(blob)
                if match:
                    violations += 1
                    findings.append(
                        Finding(
                            severity="error",
                            category="safety",
                            step_id=step.step_id,
                            message=(
                                f"content matches disallowed pattern "
                                f"'{raw_pattern}': ...{match.group(0)!r}..."
                            ),
                        )
                    )

    if total_checks == 0:
        return findings, 100.0, False

    score = 100.0 * max(0, total_checks - violations) / total_checks
    return findings, score, True


def _check_grounding(trace: Trace, policy: Policy) -> tuple[list[Finding], float, bool, float | None]:
    findings: list[Finding] = []
    grounding = policy.grounding

    grounded_candidates = [
        s for s in trace.steps if s.type == "model_response" and s.requires_grounding
    ]
    if not grounded_candidates:
        return findings, 100.0, False, None

    cited = 0
    for step in grounded_candidates:
        if step.citations:
            cited += 1
        else:
            findings.append(
                Finding(
                    severity="warning" if not grounding.require_citations else "error",
                    category="grounding",
                    step_id=step.step_id,
                    message=(
                        "model_response requires grounding but has no citations"
                    ),
                )
            )

    coverage = cited / len(grounded_candidates)

    if coverage < grounding.min_citation_coverage:
        findings.append(
            Finding(
                severity="error",
                category="grounding",
                step_id=None,
                message=(
                    f"citation coverage {coverage:.0%} is below the policy "
                    f"minimum of {grounding.min_citation_coverage:.0%}"
                ),
            )
        )

    if grounding.min_citation_coverage > 0:
        score = 100.0 * min(1.0, coverage / grounding.min_citation_coverage)
    else:
        score = 100.0 * coverage
    score = max(0.0, min(100.0, score))
    return findings, score, True, coverage


def validate_trace(
    trace: Trace, policy: Policy, fail_under: float = DEFAULT_FAIL_UNDER
) -> TraceReport:
    """Validate a single trace against a policy and produce a report."""

    schema_findings, schema_score, schema_applicable = _check_schema(trace, policy)
    (
        budget_findings,
        budget_score,
        budget_applicable,
        total_latency,
        total_cost,
    ) = _check_budgets(trace, policy)
    safety_findings, safety_score, safety_applicable = _check_safety(trace, policy)
    (
        grounding_findings,
        grounding_score,
        grounding_applicable,
        citation_coverage,
    ) = _check_grounding(trace, policy)

    applicability = {
        "schema": (schema_applicable, schema_score),
        "budget": (budget_applicable, budget_score),
        "safety": (safety_applicable, safety_score),
        "grounding": (grounding_applicable, grounding_score),
    }
    active_weight_total = sum(
        _CATEGORY_WEIGHTS[cat] for cat, (applicable, _) in applicability.items() if applicable
    )
    if active_weight_total == 0:
        overall_score = 100.0
    else:
        overall_score = sum(
            _CATEGORY_WEIGHTS[cat] * score
            for cat, (applicable, score) in applicability.items()
            if applicable
        ) / active_weight_total

    findings = [
        *schema_findings,
        *budget_findings,
        *safety_findings,
        *grounding_findings,
    ]
    has_errors = any(f.severity == "error" for f in findings)
    passed = (not has_errors) and overall_score >= fail_under

    return TraceReport(
        trace_id=trace.trace_id,
        agent_name=trace.agent_name,
        workflow=trace.workflow,
        policy_id=policy.policy_id,
        findings=findings,
        total_latency_ms=total_latency,
        total_cost_usd=total_cost,
        citation_coverage=citation_coverage,
        score=overall_score,
        passed=passed,
    )
