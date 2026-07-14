"""Typed dataclasses for traces, policies, findings, and reports.

All parsing from raw JSON (``dict``) into these dataclasses is intentionally
defensive: missing optional fields fall back to sane defaults, and malformed
required fields raise ``ValueError`` with a message that points at the
offending step, so a bad input file fails fast and legibly instead of
crashing deep inside the validator.

Schema versioning
-----------------
Traces and policies carry an optional ``schema_version`` field. Version
``"1"`` is the current canonical version. Files without a
``schema_version`` are treated as version ``"1"`` (the v0.1.x format is a
strict subset of v1, so no migration is required). Unknown *major* versions
are rejected with a precise error instead of being silently misread.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

#: Current canonical schema version for traces, policies, and reports.
SCHEMA_VERSION = "1"


def _check_schema_version(raw: dict[str, Any], kind: str) -> str:
    """Validate ``schema_version`` if present; return the effective version."""
    version = raw.get("schema_version")
    if version is None:
        return SCHEMA_VERSION
    version = str(version)
    major = version.split(".", 1)[0]
    if major != SCHEMA_VERSION:
        raise ValueError(
            f"{kind} declares unsupported schema_version '{version}' "
            f"(this build supports major version '{SCHEMA_VERSION}')"
        )
    return version


# --------------------------------------------------------------------------
# Trace side: what an agent actually did during a run.
# --------------------------------------------------------------------------

#: Valid values for Step.status.
STEP_STATUSES = ("ok", "error")


@dataclass
class Step:
    """A single step in an agent execution trace.

    A step is either a ``tool_call`` (the agent invoked an external tool
    with some arguments) or a ``model_response`` (the agent/model emitted
    text, optionally grounded with citations).
    """

    step_id: str
    type: str  # "tool_call" | "model_response"
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None
    text: str | None = None
    citations: list[dict[str, Any]] = field(default_factory=list)
    latency_ms: float | None = None
    cost_usd: float | None = None
    requires_grounding: bool = False
    output: Any = None
    # --- v1 additions (all optional; absent in v0.1.x traces) ---
    status: str = "ok"  # "ok" | "error"
    error: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> Step:
        if not isinstance(raw, dict):
            raise ValueError(f"step must be an object, got {type(raw).__name__}")
        if "step_id" not in raw:
            raise ValueError("step is missing required field 'step_id'")
        if "type" not in raw:
            raise ValueError(f"step '{raw['step_id']}' is missing required field 'type'")
        step_type = raw["type"]
        if step_type not in ("tool_call", "model_response"):
            raise ValueError(
                f"step '{raw['step_id']}' has unknown type '{step_type}' "
                "(expected 'tool_call' or 'model_response')"
            )
        step_id = str(raw["step_id"])

        status = raw.get("status")
        if status is None:
            status = "error" if raw.get("error") else "ok"
        if status not in STEP_STATUSES:
            raise ValueError(
                f"step '{step_id}' has invalid status '{status}' "
                f"(expected one of {list(STEP_STATUSES)})"
            )

        def _opt_int(key: str) -> int | None:
            value = raw.get(key)
            if value is None:
                return None
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(
                    f"step '{step_id}' field '{key}' must be a number, "
                    f"got {type(value).__name__}"
                )
            if isinstance(value, float) and not value.is_integer():
                raise ValueError(
                    f"step '{step_id}' field '{key}' must be an integer token count, "
                    f"got {value}"
                )
            if not math.isfinite(float(value)) or value < 0:
                raise ValueError(f"step '{step_id}' field '{key}' must be a finite number >= 0")
            return int(value)

        def _opt_metric(key: str) -> float | None:
            value = raw.get(key)
            if value is None:
                return None
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(
                    f"step '{step_id}' field '{key}' must be a number, "
                    f"got {type(value).__name__}"
                )
            if not math.isfinite(float(value)) or value < 0:
                raise ValueError(f"step '{step_id}' field '{key}' must be a finite number >= 0")
            return float(value)

        def _opt_str(key: str) -> str | None:
            value = raw.get(key)
            if value is None:
                return None
            if not isinstance(value, str):
                raise ValueError(
                    f"step '{step_id}' field '{key}' must be a string, "
                    f"got {type(value).__name__}"
                )
            return value

        arguments = raw.get("arguments")
        if arguments is not None and not isinstance(arguments, dict):
            raise ValueError(
                f"step '{step_id}' field 'arguments' must be an object, "
                f"got {type(arguments).__name__}"
            )

        metadata = raw.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise ValueError(f"step '{step_id}' field 'metadata' must be an object")

        return Step(
            step_id=step_id,
            type=step_type,
            tool_name=_opt_str("tool_name"),
            arguments=arguments,
            text=_opt_str("text"),
            citations=list(raw.get("citations") or []),
            latency_ms=_opt_metric("latency_ms"),
            cost_usd=_opt_metric("cost_usd"),
            requires_grounding=bool(raw.get("requires_grounding", False)),
            output=raw.get("output"),
            status=status,
            error=_opt_str("error"),
            input_tokens=_opt_int("input_tokens"),
            output_tokens=_opt_int("output_tokens"),
            metadata=dict(metadata),
        )


@dataclass
class Trace:
    """A full agent execution trace: an ordered list of steps."""

    trace_id: str
    agent_name: str
    workflow: str
    steps: list[Step] = field(default_factory=list)
    # --- v1 additions ---
    schema_version: str = SCHEMA_VERSION
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> Trace:
        if not isinstance(raw, dict):
            raise ValueError(f"trace must be an object, got {type(raw).__name__}")
        version = _check_schema_version(raw, "trace")
        for required in ("trace_id", "agent_name", "workflow", "steps"):
            if required not in raw:
                raise ValueError(f"trace is missing required field '{required}'")
        if not isinstance(raw["steps"], list):
            raise ValueError("trace field 'steps' must be a list")
        steps = [Step.from_dict(s) for s in raw["steps"]]
        metadata = raw.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise ValueError("trace field 'metadata' must be an object")
        return Trace(
            trace_id=str(raw["trace_id"]),
            agent_name=str(raw["agent_name"]),
            workflow=str(raw["workflow"]),
            steps=steps,
            schema_version=version,
            source=raw.get("source"),
            metadata=dict(metadata),
        )


# --------------------------------------------------------------------------
# Policy side: what the agent is *allowed* to do.
# --------------------------------------------------------------------------

#: Supported primitive type names in tool argument schemas, mapped to the
#: Python type(s) accepted for a value of that declared type.
TYPE_MAP: dict[str, tuple[type, ...]] = {
    "str": (str,),
    "int": (int,),
    "float": (int, float),
    "bool": (bool,),
    "list": (list,),
    "dict": (dict,),
    "any": (object,),
}


@dataclass
class ArgSpec:
    """Constraint specification for a single tool argument.

    The legacy form is a bare type-name string (``"str"``); the v1 form is an
    object with a ``type`` plus optional value constraints::

        {"type": "str", "enum": ["low", "high"]}
        {"type": "str", "pattern": "^ACC-[0-9]+$"}
        {"type": "int", "min": 1, "max": 100}
    """

    type: str = "any"
    enum: list[Any] | None = None
    pattern: str | None = None
    min_value: float | None = None
    max_value: float | None = None

    @staticmethod
    def from_raw(raw: Any, context: str) -> ArgSpec:
        if isinstance(raw, str):
            return ArgSpec(type=raw)
        if isinstance(raw, ArgSpec):
            return raw
        if isinstance(raw, dict):
            enum = raw.get("enum")
            if enum is not None and not isinstance(enum, list):
                raise ValueError(f"policy argument '{context}': 'enum' must be a list")
            pattern = raw.get("pattern")
            if pattern is not None:
                if not isinstance(pattern, str):
                    raise ValueError(f"policy argument '{context}': 'pattern' must be a string")
                try:
                    re.compile(pattern)
                except re.error as exc:
                    raise ValueError(
                        f"policy argument '{context}': invalid pattern regex: {exc}"
                    ) from exc
            for bound in ("min", "max"):
                value = raw.get(bound)
                if value is not None and (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(float(value))
                ):
                    raise ValueError(
                        f"policy argument '{context}': '{bound}' must be a finite number"
                    )
            min_value = raw.get("min")
            max_value = raw.get("max")
            if min_value is not None and max_value is not None and min_value > max_value:
                raise ValueError(
                    f"policy argument '{context}': min ({min_value}) exceeds max ({max_value})"
                )
            return ArgSpec(
                type=str(raw.get("type", "any")),
                enum=enum,
                pattern=pattern,
                min_value=raw.get("min"),
                max_value=raw.get("max"),
            )
        raise ValueError(
            f"policy argument '{context}' must be a type-name string or an object, "
            f"got {type(raw).__name__}"
        )


@dataclass
class ToolSchema:
    """Allowed schema for a single tool that the agent may call.

    ``required_arguments`` / ``optional_arguments`` values may be legacy
    type-name strings or v1 :class:`ArgSpec` objects; both are accepted and
    normalized at validation time.
    """

    required_arguments: dict[str, Any] = field(default_factory=dict)
    optional_arguments: dict[str, Any] = field(default_factory=dict)
    # --- v1 additions ---
    side_effect: bool = False
    max_calls: int | None = None
    min_calls: int | None = None

    @staticmethod
    def from_dict(raw: dict[str, Any], tool_name: str = "?") -> ToolSchema:
        if not isinstance(raw, dict):
            raise ValueError(f"policy tool '{tool_name}' schema must be an object")

        def _args(key: str) -> dict[str, ArgSpec]:
            section = raw.get(key) or {}
            if not isinstance(section, dict):
                raise ValueError(f"policy tool '{tool_name}' field '{key}' must be an object")
            return {
                name: ArgSpec.from_raw(spec, f"{tool_name}.{name}")
                for name, spec in section.items()
            }

        def _opt_count(key: str) -> int | None:
            value = raw.get(key)
            if value is None:
                return None
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(
                    f"policy tool '{tool_name}' field '{key}' must be a non-negative integer"
                )
            return value

        max_calls = _opt_count("max_calls")
        min_calls = _opt_count("min_calls")
        if max_calls is not None and min_calls is not None and min_calls > max_calls:
            raise ValueError(
                f"policy tool '{tool_name}': min_calls ({min_calls}) exceeds "
                f"max_calls ({max_calls})"
            )
        return ToolSchema(
            required_arguments=_args("required_arguments"),
            optional_arguments=_args("optional_arguments"),
            side_effect=bool(raw.get("side_effect", False)),
            max_calls=max_calls,
            min_calls=min_calls,
        )


@dataclass
class Budgets:
    """Latency, cost, and token ceilings for a trace."""

    max_total_latency_ms: float | None = None
    max_step_latency_ms: float | None = None
    max_total_cost_usd: float | None = None
    # --- v1 additions ---
    max_total_tokens: int | None = None

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> Budgets:
        if not isinstance(raw, dict):
            raise ValueError("policy field 'budgets' must be an object")
        max_total_tokens = raw.get("max_total_tokens")
        if max_total_tokens is not None and (
            isinstance(max_total_tokens, bool)
            or not isinstance(max_total_tokens, int)
            or max_total_tokens < 0
        ):
            raise ValueError("policy budget 'max_total_tokens' must be a non-negative integer")
        return Budgets(
            max_total_latency_ms=raw.get("max_total_latency_ms"),
            max_step_latency_ms=raw.get("max_step_latency_ms"),
            max_total_cost_usd=raw.get("max_total_cost_usd"),
            max_total_tokens=max_total_tokens,
        )


@dataclass
class GroundingPolicy:
    """Citation / grounding coverage requirements."""

    require_citations: bool = False
    min_citation_coverage: float = 0.0
    # --- v1 additions ---
    require_valid_citation_urls: bool = False

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> GroundingPolicy:
        if not isinstance(raw, dict):
            raise ValueError("policy field 'grounding' must be an object")
        return GroundingPolicy(
            require_citations=bool(raw.get("require_citations", False)),
            min_citation_coverage=float(raw.get("min_citation_coverage", 0.0)),
            require_valid_citation_urls=bool(raw.get("require_valid_citation_urls", False)),
        )


def _str_list(raw: dict[str, Any], key: str, context: str) -> list[str]:
    value = raw.get(key) or []
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError(f"policy field '{context}.{key}' must be a list of tool-name strings")
    return list(value)


@dataclass
class SequencePolicy:
    """Trajectory constraints on which tools are called and in what order.

    - ``required_tools``: every listed tool must be called at least once.
    - ``forbidden_tools``: listed tools must never be called.
    - ``call_order``: a partial-order constraint. For every pair of listed
      tools that were *both* called, the first call of the earlier-listed
      tool must precede the first call of the later-listed tool. Tools that
      were never called do not violate the order (use ``required_tools`` to
      also require presence). This is deliberately a partial order, not an
      exact-trajectory match.
    """

    required_tools: list[str] = field(default_factory=list)
    forbidden_tools: list[str] = field(default_factory=list)
    call_order: list[str] = field(default_factory=list)

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> SequencePolicy:
        if not isinstance(raw, dict):
            raise ValueError("policy field 'sequence' must be an object")
        policy = SequencePolicy(
            required_tools=_str_list(raw, "required_tools", "sequence"),
            forbidden_tools=_str_list(raw, "forbidden_tools", "sequence"),
            call_order=_str_list(raw, "call_order", "sequence"),
        )
        overlap = set(policy.required_tools) & set(policy.forbidden_tools)
        if overlap:
            raise ValueError(
                "policy sequence lists the same tool(s) as required and forbidden: "
                + ", ".join(sorted(overlap))
            )
        seen: set[str] = set()
        for tool in policy.call_order:
            if tool in seen:
                raise ValueError(f"policy sequence.call_order lists '{tool}' more than once")
            seen.add(tool)
        return policy

    def is_empty(self) -> bool:
        return not (self.required_tools or self.forbidden_tools or len(self.call_order) >= 2)


@dataclass
class ErrorHandlingPolicy:
    """How the agent is required to react to tool failures.

    - ``require_retry_on_error``: a tool_call whose status is ``error`` must
      be followed later in the trace by another call to the same tool.
    - ``max_attempts``: the same tool must not be called with byte-identical
      arguments more than this many times (retry-storm guard).
    """

    require_retry_on_error: bool = False
    max_attempts: int | None = None

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> ErrorHandlingPolicy:
        if not isinstance(raw, dict):
            raise ValueError("policy field 'error_handling' must be an object")
        max_attempts = raw.get("max_attempts")
        if max_attempts is not None and (
            isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1
        ):
            raise ValueError("policy error_handling.max_attempts must be an integer >= 1")
        return ErrorHandlingPolicy(
            require_retry_on_error=bool(raw.get("require_retry_on_error", False)),
            max_attempts=max_attempts,
        )

    def is_empty(self) -> bool:
        return not self.require_retry_on_error and self.max_attempts is None


@dataclass
class CompletionPolicy:
    """Task-completion requirements for the trace as a whole.

    - ``require_final_response``: the trace must end with a successful,
      non-empty ``model_response`` step.
    - ``max_steps``: the trace must not exceed this many steps (guards
      against agents that fail to terminate).
    """

    require_final_response: bool = False
    max_steps: int | None = None

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> CompletionPolicy:
        if not isinstance(raw, dict):
            raise ValueError("policy field 'completion' must be an object")
        max_steps = raw.get("max_steps")
        if max_steps is not None and (
            isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps < 1
        ):
            raise ValueError("policy completion.max_steps must be an integer >= 1")
        return CompletionPolicy(
            require_final_response=bool(raw.get("require_final_response", False)),
            max_steps=max_steps,
        )

    def is_empty(self) -> bool:
        return not self.require_final_response and self.max_steps is None


@dataclass
class Policy:
    """A complete reliability policy that traces are validated against."""

    policy_id: str
    allowed_tools: dict[str, ToolSchema] = field(default_factory=dict)
    budgets: Budgets = field(default_factory=Budgets)
    unsafe_patterns: list[str] = field(default_factory=list)
    grounding: GroundingPolicy = field(default_factory=GroundingPolicy)
    allow_unlisted_tools: bool = False
    # --- v1 additions ---
    schema_version: str = SCHEMA_VERSION
    sequence: SequencePolicy = field(default_factory=SequencePolicy)
    error_handling: ErrorHandlingPolicy = field(default_factory=ErrorHandlingPolicy)
    completion: CompletionPolicy = field(default_factory=CompletionPolicy)

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> Policy:
        if not isinstance(raw, dict):
            raise ValueError(f"policy must be an object, got {type(raw).__name__}")
        version = _check_schema_version(raw, "policy")
        if "policy_id" not in raw:
            raise ValueError("policy is missing required field 'policy_id'")
        allowed_tools_raw = raw.get("allowed_tools") or {}
        if not isinstance(allowed_tools_raw, dict):
            raise ValueError("policy field 'allowed_tools' must be an object")
        allowed_tools = {
            name: ToolSchema.from_dict(schema, tool_name=name)
            for name, schema in allowed_tools_raw.items()
        }
        unsafe_patterns = raw.get("unsafe_patterns") or []
        if not isinstance(unsafe_patterns, list) or not all(
            isinstance(p, str) for p in unsafe_patterns
        ):
            raise ValueError("policy field 'unsafe_patterns' must be a list of regex strings")
        return Policy(
            policy_id=str(raw["policy_id"]),
            allowed_tools=allowed_tools,
            budgets=Budgets.from_dict(raw.get("budgets") or {}),
            unsafe_patterns=list(unsafe_patterns),
            grounding=GroundingPolicy.from_dict(raw.get("grounding") or {}),
            allow_unlisted_tools=bool(raw.get("allow_unlisted_tools", False)),
            schema_version=version,
            sequence=SequencePolicy.from_dict(raw.get("sequence") or {}),
            error_handling=ErrorHandlingPolicy.from_dict(raw.get("error_handling") or {}),
            completion=CompletionPolicy.from_dict(raw.get("completion") or {}),
        )


# --------------------------------------------------------------------------
# Output side: findings and the per-trace report.
# --------------------------------------------------------------------------

Severity = str  # "error" | "warning" | "info"


@dataclass
class Finding:
    """A single issue (or informational note) surfaced by the validator."""

    severity: Severity
    category: str  # "schema" | "budget" | "safety" | "grounding" | "sequence" | "flow" | "completion"
    message: str
    step_id: str | None = None
    # --- v1 additions ---
    rule_id: str = ""
    expected: str | None = None
    observed: str | None = None
    remediation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "step_id": self.step_id,
            "rule_id": self.rule_id,
        }
        if self.expected is not None:
            data["expected"] = self.expected
        if self.observed is not None:
            data["observed"] = self.observed
        if self.remediation is not None:
            data["remediation"] = self.remediation
        return data


@dataclass
class TraceReport:
    """Result of validating a single trace against a policy."""

    trace_id: str
    agent_name: str
    workflow: str
    policy_id: str
    findings: list[Finding]
    total_latency_ms: float
    total_cost_usd: float
    citation_coverage: float | None
    score: float
    passed: bool
    # --- v1 additions ---
    total_tokens: int | None = None
    source_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "trace_id": self.trace_id,
            "agent_name": self.agent_name,
            "workflow": self.workflow,
            "policy_id": self.policy_id,
            "score": round(self.score, 2),
            "passed": self.passed,
            "total_latency_ms": self.total_latency_ms,
            "total_cost_usd": self.total_cost_usd,
            "citation_coverage": (
                round(self.citation_coverage, 4)
                if self.citation_coverage is not None
                else None
            ),
            "findings": [f.to_dict() for f in self.findings],
        }
        if self.total_tokens is not None:
            data["total_tokens"] = self.total_tokens
        if self.source_path is not None:
            data["source_path"] = self.source_path
        return data

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "warning")
