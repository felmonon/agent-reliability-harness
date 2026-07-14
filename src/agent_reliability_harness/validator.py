"""Core validation logic.

``validate_trace`` runs up to seven independent deterministic checks against
a trace:

1. **Schema conformance** - every ``tool_call`` step must call a tool listed
   in the policy's ``allowed_tools``, and must supply all of that tool's
   required arguments with the declared type and value constraints.
2. **Budgets** - total/step latency, total cost, and total tokens must stay
   within the policy's ceilings.
3. **Safety** - free-text output (tool outputs and model response text) is
   scanned for disallowed patterns (regexes), e.g. prompt-injection phrases
   or secret-like strings.
4. **Grounding/citations** - for steps flagged ``requires_grounding``, a
   non-empty ``citations`` list is expected; overall coverage is compared
   against the policy's minimum. Citations can additionally be required to
   carry a valid source or http(s) URL.
5. **Sequence** - required tools, forbidden tools, partial-order call
   ordering, and per-tool call-count bounds.
6. **Flow** - error handling (ignored tool errors, retry storms) and
   duplicate side-effect protection.
7. **Completion** - the trace must end with a successful final response
   and/or stay under a maximum step count.

Every check is deterministic: no model calls, no network, no clock reads.
Each check appends zero or more ``Finding`` objects (each carrying a stable
``rule_id``) and contributes to a weighted 0-100 score. The trace "passes"
when there are no ``error``-level findings and the score meets/exceeds
``fail_under`` (default 70).

Scoring compatibility: categories that are not applicable (e.g. no
``sequence`` policy configured) are excluded from the weighted score, so a
v0.1.x policy produces byte-identical scores under this version.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional
from urllib.parse import urlparse

from agent_reliability_harness.models import (
    ArgSpec,
    Finding,
    Policy,
    Step,
    Trace,
    TraceReport,
    TYPE_MAP,
)

DEFAULT_FAIL_UNDER = 70.0

# Category weights; categories with no applicable checks are excluded and the
# remaining weights are renormalized. With only the four v0.1.x categories
# active these weights sum to 1.0, which keeps legacy scores unchanged.
_CATEGORY_WEIGHTS = {
    "schema": 0.3,
    "budget": 0.3,
    "safety": 0.25,
    "grounding": 0.15,
    "sequence": 0.25,
    "flow": 0.2,
    "completion": 0.1,
}


def _canonical_arguments(step: Step) -> str:
    """Stable serialization of a step's arguments for identity comparison."""
    return json.dumps(step.arguments or {}, sort_keys=True, separators=(",", ":"), default=repr)


# ---------------------------------------------------------------------------
# 1. Schema
# ---------------------------------------------------------------------------


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
                    rule_id="ARH-SCH-002",
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
                    rule_id="ARH-SCH-001",
                    message=f"tool '{tool_name}' is not in the allowed_tools policy",
                    expected="a tool from the policy allowed_tools list",
                    observed=f"call to '{tool_name}'",
                )
            )
            continue

        arguments = step.arguments or {}
        step_ok = True

        required_specs = {
            name: ArgSpec.from_raw(spec, f"{tool_name}.{name}")
            for name, spec in schema.required_arguments.items()
        }
        optional_specs = {
            name: ArgSpec.from_raw(spec, f"{tool_name}.{name}")
            for name, spec in schema.optional_arguments.items()
        }

        for arg_name, spec in required_specs.items():
            if arg_name not in arguments:
                findings.append(
                    Finding(
                        severity="error",
                        category="schema",
                        step_id=step.step_id,
                        rule_id="ARH-SCH-003",
                        message=(
                            f"tool '{tool_name}' call is missing required "
                            f"argument '{arg_name}'"
                        ),
                        expected=f"argument '{arg_name}' present",
                        observed="argument absent",
                    )
                )
                step_ok = False

        all_specs = {**required_specs, **optional_specs}
        for arg_name, arg_value in arguments.items():
            if arg_name in all_specs:
                step_ok &= _check_arg_value(
                    tool_name, step, arg_name, all_specs[arg_name], arg_value, findings
                )
            else:
                findings.append(
                    Finding(
                        severity="warning",
                        category="schema",
                        step_id=step.step_id,
                        rule_id="ARH-SCH-005",
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


def _check_arg_value(
    tool_name: str,
    step: Step,
    arg_name: str,
    spec: ArgSpec,
    arg_value: Any,
    findings: list[Finding],
) -> bool:
    """Type + value-constraint check for a single argument. Returns ok."""
    arg_type = spec.type
    expected = TYPE_MAP.get(arg_type)
    if expected is None:
        # Unknown declared type in the policy itself; treat permissively but
        # surface it so the policy author can fix it.
        findings.append(
            Finding(
                severity="info",
                category="schema",
                step_id=step.step_id,
                rule_id="ARH-SCH-006",
                message=(
                    f"policy declares unknown type '{arg_type}' for "
                    f"'{tool_name}.{arg_name}'; skipping type check"
                ),
            )
        )
        return True
    if expected != (object,):
        if isinstance(arg_value, bool) and expected != (bool,):
            # bool is a subclass of int in Python; don't let a bool satisfy "int".
            type_ok = False
        else:
            type_ok = isinstance(arg_value, expected)
        if not type_ok:
            findings.append(
                Finding(
                    severity="error",
                    category="schema",
                    step_id=step.step_id,
                    rule_id="ARH-SCH-004",
                    message=(
                        f"tool '{tool_name}' argument '{arg_name}' expected type "
                        f"'{arg_type}' but got '{type(arg_value).__name__}'"
                    ),
                    expected=f"type '{arg_type}'",
                    observed=f"type '{type(arg_value).__name__}'",
                )
            )
            return False

    ok = True
    if spec.enum is not None and arg_value not in spec.enum:
        findings.append(
            Finding(
                severity="error",
                category="schema",
                step_id=step.step_id,
                rule_id="ARH-SCH-007",
                message=(
                    f"tool '{tool_name}' argument '{arg_name}' value {arg_value!r} "
                    f"is not one of the allowed values {spec.enum!r}"
                ),
                expected=f"one of {spec.enum!r}",
                observed=repr(arg_value),
            )
        )
        ok = False
    if spec.pattern is not None and isinstance(arg_value, str):
        if re.fullmatch(spec.pattern, arg_value) is None:
            findings.append(
                Finding(
                    severity="error",
                    category="schema",
                    step_id=step.step_id,
                    rule_id="ARH-SCH-008",
                    message=(
                        f"tool '{tool_name}' argument '{arg_name}' value {arg_value!r} "
                        f"does not match required pattern '{spec.pattern}'"
                    ),
                    expected=f"full match of pattern '{spec.pattern}'",
                    observed=repr(arg_value),
                )
            )
            ok = False
    if isinstance(arg_value, (int, float)) and not isinstance(arg_value, bool):
        if spec.min_value is not None and arg_value < spec.min_value:
            findings.append(
                Finding(
                    severity="error",
                    category="schema",
                    step_id=step.step_id,
                    rule_id="ARH-SCH-009",
                    message=(
                        f"tool '{tool_name}' argument '{arg_name}' value {arg_value} "
                        f"is below the allowed minimum {spec.min_value}"
                    ),
                    expected=f">= {spec.min_value}",
                    observed=str(arg_value),
                )
            )
            ok = False
        if spec.max_value is not None and arg_value > spec.max_value:
            findings.append(
                Finding(
                    severity="error",
                    category="schema",
                    step_id=step.step_id,
                    rule_id="ARH-SCH-009",
                    message=(
                        f"tool '{tool_name}' argument '{arg_name}' value {arg_value} "
                        f"is above the allowed maximum {spec.max_value}"
                    ),
                    expected=f"<= {spec.max_value}",
                    observed=str(arg_value),
                )
            )
            ok = False
    return ok


# ---------------------------------------------------------------------------
# 2. Budgets
# ---------------------------------------------------------------------------


def _check_budgets(
    trace: Trace, policy: Policy
) -> tuple[list[Finding], float, bool, float, float, Optional[int]]:
    findings: list[Finding] = []
    budgets = policy.budgets
    applicable = any(
        v is not None
        for v in (
            budgets.max_total_latency_ms,
            budgets.max_step_latency_ms,
            budgets.max_total_cost_usd,
            budgets.max_total_tokens,
        )
    )

    total_latency = sum(s.latency_ms or 0.0 for s in trace.steps)
    total_cost = sum(s.cost_usd or 0.0 for s in trace.steps)
    token_values = [
        (s.input_tokens or 0) + (s.output_tokens or 0)
        for s in trace.steps
        if s.input_tokens is not None or s.output_tokens is not None
    ]
    total_tokens: Optional[int] = sum(token_values) if token_values else None

    if not applicable:
        return findings, 100.0, False, total_latency, total_cost, total_tokens

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
                        rule_id="ARH-BUD-001",
                        message=(
                            f"step latency {step.latency_ms:.0f}ms exceeds "
                            f"max_step_latency_ms budget of "
                            f"{budgets.max_step_latency_ms:.0f}ms"
                        ),
                        expected=f"<= {budgets.max_step_latency_ms:.0f}ms",
                        observed=f"{step.latency_ms:.0f}ms",
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
                    rule_id="ARH-BUD-002",
                    message=(
                        f"total trace latency {total_latency:.0f}ms exceeds "
                        f"max_total_latency_ms budget of "
                        f"{budgets.max_total_latency_ms:.0f}ms"
                    ),
                    expected=f"<= {budgets.max_total_latency_ms:.0f}ms",
                    observed=f"{total_latency:.0f}ms",
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
                    rule_id="ARH-BUD-003",
                    message=(
                        f"total trace cost ${total_cost:.4f} exceeds "
                        f"max_total_cost_usd budget of "
                        f"${budgets.max_total_cost_usd:.4f}"
                    ),
                    expected=f"<= ${budgets.max_total_cost_usd:.4f}",
                    observed=f"${total_cost:.4f}",
                )
            )
        else:
            checks_passed += 1

    if budgets.max_total_tokens is not None:
        checks_total += 1
        if total_tokens is None:
            # A budget the trace cannot demonstrate compliance with must not
            # silently pass.
            findings.append(
                Finding(
                    severity="warning",
                    category="budget",
                    step_id=None,
                    rule_id="ARH-BUD-005",
                    message=(
                        "policy sets max_total_tokens but the trace records no "
                        "token usage; the token budget cannot be verified"
                    ),
                    expected="steps with input_tokens/output_tokens recorded",
                    observed="no token data in trace",
                    remediation="Record token usage in the trace or remove max_total_tokens.",
                )
            )
        elif total_tokens > budgets.max_total_tokens:
            findings.append(
                Finding(
                    severity="error",
                    category="budget",
                    step_id=None,
                    rule_id="ARH-BUD-004",
                    message=(
                        f"total token usage {total_tokens} exceeds "
                        f"max_total_tokens budget of {budgets.max_total_tokens}"
                    ),
                    expected=f"<= {budgets.max_total_tokens} tokens",
                    observed=f"{total_tokens} tokens",
                )
            )
        else:
            checks_passed += 1

    score = 100.0 * checks_passed / checks_total if checks_total else 100.0
    return findings, score, True, total_latency, total_cost, total_tokens


# ---------------------------------------------------------------------------
# 3. Safety
# ---------------------------------------------------------------------------


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

    try:
        compiled = [re.compile(p, re.IGNORECASE) for p in policy.unsafe_patterns]
    except re.error as exc:
        raise ValueError(f"policy unsafe_patterns contains an invalid regex: {exc}") from exc

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
                            rule_id="ARH-SAF-001",
                            message=(
                                f"content matches disallowed pattern "
                                f"'{raw_pattern}': ...{match.group(0)!r}..."
                            ),
                            expected=f"no content matching '{raw_pattern}'",
                            observed=f"match {match.group(0)!r}",
                        )
                    )

    if total_checks == 0:
        return findings, 100.0, False

    score = 100.0 * max(0, total_checks - violations) / total_checks
    return findings, score, True


# ---------------------------------------------------------------------------
# 4. Grounding
# ---------------------------------------------------------------------------


def _citation_is_valid(citation: Any) -> bool:
    """A citation must be an object with a non-empty source or valid http(s) URL."""
    if not isinstance(citation, dict):
        return False
    url = citation.get("url")
    if url is not None:
        if not isinstance(url, str):
            return False
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    source = citation.get("source")
    return isinstance(source, str) and bool(source.strip())


def _check_grounding(
    trace: Trace, policy: Policy
) -> tuple[list[Finding], float, bool, float | None]:
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
            if grounding.require_valid_citation_urls:
                for index, citation in enumerate(step.citations):
                    if not _citation_is_valid(citation):
                        findings.append(
                            Finding(
                                severity="error",
                                category="grounding",
                                step_id=step.step_id,
                                rule_id="ARH-GRD-003",
                                message=(
                                    f"citation #{index + 1} is malformed: expected an "
                                    "object with a non-empty 'source' or a valid "
                                    "http(s) 'url'"
                                ),
                                expected="citation with non-empty source or valid http(s) url",
                                observed=repr(citation),
                            )
                        )
        else:
            findings.append(
                Finding(
                    severity="warning" if not grounding.require_citations else "error",
                    category="grounding",
                    step_id=step.step_id,
                    rule_id="ARH-GRD-001",
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
                rule_id="ARH-GRD-002",
                message=(
                    f"citation coverage {coverage:.0%} is below the policy "
                    f"minimum of {grounding.min_citation_coverage:.0%}"
                ),
                expected=f">= {grounding.min_citation_coverage:.0%}",
                observed=f"{coverage:.0%}",
            )
        )

    if grounding.min_citation_coverage > 0:
        score = 100.0 * min(1.0, coverage / grounding.min_citation_coverage)
    else:
        score = 100.0 * coverage
    score = max(0.0, min(100.0, score))
    return findings, score, True, coverage


# ---------------------------------------------------------------------------
# 5. Sequence (trajectory shape)
# ---------------------------------------------------------------------------


def _check_sequence(trace: Trace, policy: Policy) -> tuple[list[Finding], float, bool]:
    findings: list[Finding] = []
    sequence = policy.sequence

    count_constrained = {
        name: schema
        for name, schema in policy.allowed_tools.items()
        if schema.max_calls is not None or schema.min_calls is not None
    }
    if sequence.is_empty() and not count_constrained:
        return findings, 100.0, False

    tool_calls = [s for s in trace.steps if s.type == "tool_call" and s.tool_name]
    call_counts: dict[str, int] = {}
    first_call_index: dict[str, int] = {}
    first_call_step: dict[str, str] = {}
    for index, step in enumerate(tool_calls):
        name = step.tool_name or ""
        call_counts[name] = call_counts.get(name, 0) + 1
        if name not in first_call_index:
            first_call_index[name] = index
            first_call_step[name] = step.step_id

    checks_total = 0
    checks_passed = 0

    for tool in sequence.required_tools:
        checks_total += 1
        if call_counts.get(tool, 0) >= 1:
            checks_passed += 1
        else:
            findings.append(
                Finding(
                    severity="error",
                    category="sequence",
                    step_id=None,
                    rule_id="ARH-SEQ-001",
                    message=f"required tool '{tool}' was never called",
                    expected=f"at least one call to '{tool}'",
                    observed="0 calls",
                )
            )

    for tool in sequence.forbidden_tools:
        checks_total += 1
        if call_counts.get(tool, 0) == 0:
            checks_passed += 1
        else:
            for step in tool_calls:
                if step.tool_name == tool:
                    findings.append(
                        Finding(
                            severity="error",
                            category="sequence",
                            step_id=step.step_id,
                            rule_id="ARH-SEQ-002",
                            message=f"forbidden tool '{tool}' was called",
                            expected=f"no calls to '{tool}'",
                            observed=f"{call_counts[tool]} call(s)",
                        )
                    )

    order = sequence.call_order
    for i in range(len(order)):
        for j in range(i + 1, len(order)):
            earlier, later = order[i], order[j]
            if earlier not in first_call_index or later not in first_call_index:
                continue
            checks_total += 1
            if first_call_index[earlier] < first_call_index[later]:
                checks_passed += 1
            else:
                findings.append(
                    Finding(
                        severity="error",
                        category="sequence",
                        step_id=first_call_step[later],
                        rule_id="ARH-SEQ-003",
                        message=(
                            f"call order violation: first call of '{earlier}' must "
                            f"precede first call of '{later}'"
                        ),
                        expected=f"'{earlier}' before '{later}'",
                        observed=(
                            f"'{later}' first at position "
                            f"{first_call_index[later] + 1}, '{earlier}' first at "
                            f"position {first_call_index[earlier] + 1}"
                        ),
                    )
                )

    for tool, schema in sorted(count_constrained.items()):
        count = call_counts.get(tool, 0)
        if schema.max_calls is not None:
            checks_total += 1
            if count <= schema.max_calls:
                checks_passed += 1
            else:
                findings.append(
                    Finding(
                        severity="error",
                        category="sequence",
                        step_id=None,
                        rule_id="ARH-SEQ-004",
                        message=(
                            f"tool '{tool}' was called {count} times, above "
                            f"max_calls of {schema.max_calls}"
                        ),
                        expected=f"<= {schema.max_calls} call(s)",
                        observed=f"{count} call(s)",
                    )
                )
        if schema.min_calls is not None:
            checks_total += 1
            if count >= schema.min_calls:
                checks_passed += 1
            else:
                findings.append(
                    Finding(
                        severity="error",
                        category="sequence",
                        step_id=None,
                        rule_id="ARH-SEQ-005",
                        message=(
                            f"tool '{tool}' was called {count} times, below "
                            f"min_calls of {schema.min_calls}"
                        ),
                        expected=f">= {schema.min_calls} call(s)",
                        observed=f"{count} call(s)",
                    )
                )

    score = 100.0 * checks_passed / checks_total if checks_total else 100.0
    return findings, score, checks_total > 0


# ---------------------------------------------------------------------------
# 6. Flow (error handling + side effects)
# ---------------------------------------------------------------------------


def _check_flow(trace: Trace, policy: Policy) -> tuple[list[Finding], float, bool]:
    findings: list[Finding] = []
    error_handling = policy.error_handling
    side_effect_tools = {
        name for name, schema in policy.allowed_tools.items() if schema.side_effect
    }
    if error_handling.is_empty() and not side_effect_tools:
        return findings, 100.0, False

    tool_calls = [s for s in trace.steps if s.type == "tool_call" and s.tool_name]

    checks_total = 0
    checks_passed = 0

    if error_handling.require_retry_on_error:
        for index, step in enumerate(tool_calls):
            if step.status != "error":
                continue
            checks_total += 1
            retried = any(
                later.tool_name == step.tool_name for later in tool_calls[index + 1 :]
            )
            if retried:
                checks_passed += 1
            else:
                findings.append(
                    Finding(
                        severity="error",
                        category="flow",
                        step_id=step.step_id,
                        rule_id="ARH-FLW-001",
                        message=(
                            f"tool '{step.tool_name}' failed and was never retried"
                        ),
                        expected=f"a later retry call to '{step.tool_name}'",
                        observed="no later call to the failed tool",
                    )
                )

    groups: dict[tuple[str, str], list[Step]] = {}
    for step in tool_calls:
        key = (step.tool_name or "", _canonical_arguments(step))
        groups.setdefault(key, []).append(step)

    if error_handling.max_attempts is not None:
        for (tool, _args), steps in sorted(groups.items()):
            checks_total += 1
            if len(steps) <= error_handling.max_attempts:
                checks_passed += 1
            else:
                offending = steps[error_handling.max_attempts]
                findings.append(
                    Finding(
                        severity="error",
                        category="flow",
                        step_id=offending.step_id,
                        rule_id="ARH-FLW-002",
                        message=(
                            f"retry storm: tool '{tool}' was called {len(steps)} "
                            f"times with identical arguments, above max_attempts "
                            f"of {error_handling.max_attempts}"
                        ),
                        expected=f"<= {error_handling.max_attempts} identical attempts",
                        observed=f"{len(steps)} identical attempts",
                    )
                )

    if side_effect_tools:
        for (tool, _args), steps in sorted(groups.items()):
            if tool not in side_effect_tools:
                continue
            checks_total += 1
            succeeded = False
            duplicates: list[Step] = []
            for step in steps:
                if succeeded:
                    duplicates.append(step)
                elif step.status == "ok":
                    succeeded = True
            if not duplicates:
                checks_passed += 1
            else:
                for step in duplicates:
                    findings.append(
                        Finding(
                            severity="error",
                            category="flow",
                            step_id=step.step_id,
                            rule_id="ARH-FLW-003",
                            message=(
                                f"duplicate side effect: tool '{tool}' was called "
                                "again with identical arguments after already "
                                "succeeding"
                            ),
                            expected="one successful call per unique argument set",
                            observed=f"{len(duplicates) + 1} calls with identical arguments",
                        )
                    )

    score = 100.0 * checks_passed / checks_total if checks_total else 100.0
    return findings, score, checks_total > 0


# ---------------------------------------------------------------------------
# 7. Completion
# ---------------------------------------------------------------------------


def _check_completion(trace: Trace, policy: Policy) -> tuple[list[Finding], float, bool]:
    findings: list[Finding] = []
    completion = policy.completion
    if completion.is_empty():
        return findings, 100.0, False

    checks_total = 0
    checks_passed = 0

    if completion.require_final_response:
        checks_total += 1
        last = trace.steps[-1] if trace.steps else None
        if (
            last is not None
            and last.type == "model_response"
            and last.status == "ok"
            and bool((last.text or "").strip())
        ):
            checks_passed += 1
        else:
            observed = "trace has no steps"
            if last is not None:
                if last.type != "model_response":
                    observed = f"last step is a '{last.type}'"
                elif last.status != "ok":
                    observed = "final model_response has status 'error'"
                else:
                    observed = "final model_response has empty text"
            findings.append(
                Finding(
                    severity="error",
                    category="completion",
                    step_id=last.step_id if last is not None else None,
                    rule_id="ARH-CMP-001",
                    message=(
                        "trace does not end with a successful, non-empty "
                        "model_response"
                    ),
                    expected="final step: model_response with status 'ok' and non-empty text",
                    observed=observed,
                )
            )

    if completion.max_steps is not None:
        checks_total += 1
        if len(trace.steps) <= completion.max_steps:
            checks_passed += 1
        else:
            findings.append(
                Finding(
                    severity="error",
                    category="completion",
                    step_id=None,
                    rule_id="ARH-CMP-002",
                    message=(
                        f"trace has {len(trace.steps)} steps, above the "
                        f"max_steps limit of {completion.max_steps}"
                    ),
                    expected=f"<= {completion.max_steps} steps",
                    observed=f"{len(trace.steps)} steps",
                )
            )

    score = 100.0 * checks_passed / checks_total if checks_total else 100.0
    return findings, score, checks_total > 0


# ---------------------------------------------------------------------------
# Trace structure lint (does not affect the score)
# ---------------------------------------------------------------------------


def _lint_structure(trace: Trace) -> list[Finding]:
    findings: list[Finding] = []
    seen: dict[str, int] = {}
    for step in trace.steps:
        seen[step.step_id] = seen.get(step.step_id, 0) + 1
    for step_id, count in seen.items():
        if count > 1:
            findings.append(
                Finding(
                    severity="warning",
                    category="schema",
                    step_id=step_id,
                    rule_id="ARH-SCH-010",
                    message=(
                        f"step_id '{step_id}' appears {count} times in the trace; "
                        "step IDs should be unique"
                    ),
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


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
        total_tokens,
    ) = _check_budgets(trace, policy)
    safety_findings, safety_score, safety_applicable = _check_safety(trace, policy)
    (
        grounding_findings,
        grounding_score,
        grounding_applicable,
        citation_coverage,
    ) = _check_grounding(trace, policy)
    sequence_findings, sequence_score, sequence_applicable = _check_sequence(trace, policy)
    flow_findings, flow_score, flow_applicable = _check_flow(trace, policy)
    completion_findings, completion_score, completion_applicable = _check_completion(
        trace, policy
    )

    applicability = {
        "schema": (schema_applicable, schema_score),
        "budget": (budget_applicable, budget_score),
        "safety": (safety_applicable, safety_score),
        "grounding": (grounding_applicable, grounding_score),
        "sequence": (sequence_applicable, sequence_score),
        "flow": (flow_applicable, flow_score),
        "completion": (completion_applicable, completion_score),
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
        *sequence_findings,
        *flow_findings,
        *completion_findings,
        *_lint_structure(trace),
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
        total_tokens=total_tokens,
    )
