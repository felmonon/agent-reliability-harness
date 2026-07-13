"""Typed dataclasses for traces, policies, findings, and reports.

All parsing from raw JSON (``dict``) into these dataclasses is intentionally
defensive: missing optional fields fall back to sane defaults, and malformed
required fields raise ``ValueError`` with a message that points at the
offending step, so a bad input file fails fast and legibly instead of
crashing deep inside the validator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# --------------------------------------------------------------------------
# Trace side: what an agent actually did during a run.
# --------------------------------------------------------------------------


@dataclass
class Step:
    """A single step in an agent execution trace.

    A step is either a ``tool_call`` (the agent invoked an external tool
    with some arguments) or a ``model_response`` (the agent/model emitted
    text, optionally grounded with citations).
    """

    step_id: str
    type: str  # "tool_call" | "model_response"
    tool_name: Optional[str] = None
    arguments: Optional[dict[str, Any]] = None
    text: Optional[str] = None
    citations: list[dict[str, Any]] = field(default_factory=list)
    latency_ms: Optional[float] = None
    cost_usd: Optional[float] = None
    requires_grounding: bool = False
    output: Any = None

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> "Step":
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
        return Step(
            step_id=str(raw["step_id"]),
            type=step_type,
            tool_name=raw.get("tool_name"),
            arguments=raw.get("arguments"),
            text=raw.get("text"),
            citations=list(raw.get("citations") or []),
            latency_ms=raw.get("latency_ms"),
            cost_usd=raw.get("cost_usd"),
            requires_grounding=bool(raw.get("requires_grounding", False)),
            output=raw.get("output"),
        )


@dataclass
class Trace:
    """A full agent execution trace: an ordered list of steps."""

    trace_id: str
    agent_name: str
    workflow: str
    steps: list[Step] = field(default_factory=list)

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> "Trace":
        for required in ("trace_id", "agent_name", "workflow", "steps"):
            if required not in raw:
                raise ValueError(f"trace is missing required field '{required}'")
        steps = [Step.from_dict(s) for s in raw["steps"]]
        return Trace(
            trace_id=str(raw["trace_id"]),
            agent_name=str(raw["agent_name"]),
            workflow=str(raw["workflow"]),
            steps=steps,
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
class ToolSchema:
    """Allowed schema for a single tool that the agent may call."""

    required_arguments: dict[str, str] = field(default_factory=dict)
    optional_arguments: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> "ToolSchema":
        return ToolSchema(
            required_arguments=dict(raw.get("required_arguments") or {}),
            optional_arguments=dict(raw.get("optional_arguments") or {}),
        )


@dataclass
class Budgets:
    """Latency and cost ceilings for a trace."""

    max_total_latency_ms: Optional[float] = None
    max_step_latency_ms: Optional[float] = None
    max_total_cost_usd: Optional[float] = None

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> "Budgets":
        return Budgets(
            max_total_latency_ms=raw.get("max_total_latency_ms"),
            max_step_latency_ms=raw.get("max_step_latency_ms"),
            max_total_cost_usd=raw.get("max_total_cost_usd"),
        )


@dataclass
class GroundingPolicy:
    """Citation / grounding coverage requirements."""

    require_citations: bool = False
    min_citation_coverage: float = 0.0

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> "GroundingPolicy":
        return GroundingPolicy(
            require_citations=bool(raw.get("require_citations", False)),
            min_citation_coverage=float(raw.get("min_citation_coverage", 0.0)),
        )


@dataclass
class Policy:
    """A complete reliability policy that traces are validated against."""

    policy_id: str
    allowed_tools: dict[str, ToolSchema] = field(default_factory=dict)
    budgets: Budgets = field(default_factory=Budgets)
    unsafe_patterns: list[str] = field(default_factory=list)
    grounding: GroundingPolicy = field(default_factory=GroundingPolicy)
    allow_unlisted_tools: bool = False

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> "Policy":
        if "policy_id" not in raw:
            raise ValueError("policy is missing required field 'policy_id'")
        allowed_tools = {
            name: ToolSchema.from_dict(schema)
            for name, schema in (raw.get("allowed_tools") or {}).items()
        }
        return Policy(
            policy_id=str(raw["policy_id"]),
            allowed_tools=allowed_tools,
            budgets=Budgets.from_dict(raw.get("budgets") or {}),
            unsafe_patterns=list(raw.get("unsafe_patterns") or []),
            grounding=GroundingPolicy.from_dict(raw.get("grounding") or {}),
            allow_unlisted_tools=bool(raw.get("allow_unlisted_tools", False)),
        )


# --------------------------------------------------------------------------
# Output side: findings and the per-trace report.
# --------------------------------------------------------------------------

Severity = str  # "error" | "warning" | "info"


@dataclass
class Finding:
    """A single issue (or informational note) surfaced by the validator."""

    severity: Severity
    category: str  # "schema" | "budget" | "safety" | "grounding"
    message: str
    step_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "step_id": self.step_id,
        }


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
    citation_coverage: Optional[float]
    score: float
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
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

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "warning")
