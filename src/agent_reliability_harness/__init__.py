"""agent_reliability_harness

A dependency-free, local-first reliability and regression-testing harness
for tool-using AI agents. It validates agent execution traces against
declarative policies (tool-call contracts, trajectory rules, budgets,
unsafe-pattern detection, grounding), and compares candidate runs against a
saved baseline to gate CI on real regressions.

The core is deterministic: no model calls, no network, no clock reads.
"""

from agent_reliability_harness.models import (
    ArgSpec,
    Budgets,
    CompletionPolicy,
    ErrorHandlingPolicy,
    Finding,
    GroundingPolicy,
    Policy,
    SCHEMA_VERSION,
    SequencePolicy,
    Step,
    ToolSchema,
    Trace,
    TraceReport,
)
from agent_reliability_harness.regression import (
    ComparisonResult,
    compare_reports,
    evaluate_gate,
)
from agent_reliability_harness.rules import RULES, Rule
from agent_reliability_harness.validator import validate_trace

__version__ = "0.2.0"

__all__ = [
    "ArgSpec",
    "Budgets",
    "CompletionPolicy",
    "ComparisonResult",
    "ErrorHandlingPolicy",
    "Finding",
    "GroundingPolicy",
    "Policy",
    "RULES",
    "Rule",
    "SCHEMA_VERSION",
    "SequencePolicy",
    "Step",
    "ToolSchema",
    "Trace",
    "TraceReport",
    "compare_reports",
    "evaluate_gate",
    "validate_trace",
    "__version__",
]
