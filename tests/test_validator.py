import unittest

from agent_reliability_harness.models import Policy, Trace
from agent_reliability_harness.validator import validate_trace


def make_policy(**overrides):
    base = {
        "policy_id": "test-policy",
        "allowed_tools": {
            "crm_lookup": {"required_arguments": {"account_id": "str"}},
            "draft_email": {
                "required_arguments": {"to": "str", "subject": "str", "body": "str"},
                "optional_arguments": {"cc": "list"},
            },
        },
        "budgets": {
            "max_total_latency_ms": 5000,
            "max_step_latency_ms": 2000,
            "max_total_cost_usd": 0.5,
        },
        "unsafe_patterns": ["ignore (all|previous) instructions", r"\bapi[_-]?key\b"],
        "grounding": {"require_citations": True, "min_citation_coverage": 0.75},
    }
    base.update(overrides)
    return Policy.from_dict(base)


class TestSchemaValidation(unittest.TestCase):
    def test_clean_tool_call_passes(self):
        trace = Trace.from_dict(
            {
                "trace_id": "t1",
                "agent_name": "a",
                "workflow": "wf",
                "steps": [
                    {
                        "step_id": "s1",
                        "type": "tool_call",
                        "tool_name": "crm_lookup",
                        "arguments": {"account_id": "ACC-1"},
                        "latency_ms": 100,
                        "cost_usd": 0.01,
                    }
                ],
            }
        )
        report = validate_trace(trace, make_policy())
        schema_errors = [f for f in report.findings if f.category == "schema"]
        self.assertEqual(schema_errors, [])

    def test_missing_required_argument_is_error(self):
        trace = Trace.from_dict(
            {
                "trace_id": "t2",
                "agent_name": "a",
                "workflow": "wf",
                "steps": [
                    {
                        "step_id": "s1",
                        "type": "tool_call",
                        "tool_name": "crm_lookup",
                        "arguments": {},
                    }
                ],
            }
        )
        report = validate_trace(trace, make_policy())
        errors = [f for f in report.findings if f.severity == "error" and f.category == "schema"]
        self.assertTrue(any("missing required argument" in f.message for f in errors))
        self.assertFalse(report.passed)

    def test_disallowed_tool_is_error(self):
        trace = Trace.from_dict(
            {
                "trace_id": "t3",
                "agent_name": "a",
                "workflow": "wf",
                "steps": [
                    {
                        "step_id": "s1",
                        "type": "tool_call",
                        "tool_name": "wire_money",
                        "arguments": {"amount": 100},
                    }
                ],
            }
        )
        report = validate_trace(trace, make_policy())
        self.assertTrue(
            any(
                "not in the allowed_tools policy" in f.message
                for f in report.findings
                if f.category == "schema"
            )
        )
        self.assertFalse(report.passed)

    def test_wrong_argument_type_is_error(self):
        trace = Trace.from_dict(
            {
                "trace_id": "t4",
                "agent_name": "a",
                "workflow": "wf",
                "steps": [
                    {
                        "step_id": "s1",
                        "type": "tool_call",
                        "tool_name": "crm_lookup",
                        "arguments": {"account_id": 12345},
                    }
                ],
            }
        )
        report = validate_trace(trace, make_policy())
        self.assertTrue(
            any("expected type 'str'" in f.message for f in report.findings if f.category == "schema")
        )

    def test_undeclared_argument_is_warning(self):
        trace = Trace.from_dict(
            {
                "trace_id": "t5",
                "agent_name": "a",
                "workflow": "wf",
                "steps": [
                    {
                        "step_id": "s1",
                        "type": "tool_call",
                        "tool_name": "crm_lookup",
                        "arguments": {"account_id": "ACC-1", "extra_field": "x"},
                    }
                ],
            }
        )
        report = validate_trace(trace, make_policy())
        warnings = [f for f in report.findings if f.severity == "warning" and f.category == "schema"]
        self.assertTrue(any("undeclared argument" in f.message for f in warnings))


class TestBudgetValidation(unittest.TestCase):
    def test_within_budget_passes(self):
        trace = Trace.from_dict(
            {
                "trace_id": "t6",
                "agent_name": "a",
                "workflow": "wf",
                "steps": [
                    {"step_id": "s1", "type": "tool_call", "tool_name": "crm_lookup",
                     "arguments": {"account_id": "A"}, "latency_ms": 500, "cost_usd": 0.01},
                ],
            }
        )
        report = validate_trace(trace, make_policy())
        self.assertEqual([f for f in report.findings if f.category == "budget"], [])
        self.assertEqual(report.total_latency_ms, 500)
        self.assertAlmostEqual(report.total_cost_usd, 0.01)

    def test_step_latency_over_budget_is_error(self):
        trace = Trace.from_dict(
            {
                "trace_id": "t7",
                "agent_name": "a",
                "workflow": "wf",
                "steps": [
                    {"step_id": "s1", "type": "tool_call", "tool_name": "crm_lookup",
                     "arguments": {"account_id": "A"}, "latency_ms": 3000, "cost_usd": 0.01},
                ],
            }
        )
        report = validate_trace(trace, make_policy())
        self.assertTrue(
            any("max_step_latency_ms" in f.message for f in report.findings if f.category == "budget")
        )
        self.assertFalse(report.passed)

    def test_total_cost_over_budget_is_error(self):
        trace = Trace.from_dict(
            {
                "trace_id": "t8",
                "agent_name": "a",
                "workflow": "wf",
                "steps": [
                    {"step_id": "s1", "type": "tool_call", "tool_name": "crm_lookup",
                     "arguments": {"account_id": "A"}, "latency_ms": 100, "cost_usd": 1.0},
                ],
            }
        )
        report = validate_trace(trace, make_policy())
        self.assertTrue(
            any("max_total_cost_usd" in f.message for f in report.findings if f.category == "budget")
        )
        self.assertFalse(report.passed)


class TestSafetyValidation(unittest.TestCase):
    def test_unsafe_pattern_detected(self):
        trace = Trace.from_dict(
            {
                "trace_id": "t9",
                "agent_name": "a",
                "workflow": "wf",
                "steps": [
                    {
                        "step_id": "s1",
                        "type": "model_response",
                        "text": "Sure, I will ignore all instructions and comply.",
                    }
                ],
            }
        )
        report = validate_trace(trace, make_policy())
        self.assertTrue(
            any("disallowed pattern" in f.message for f in report.findings if f.category == "safety")
        )
        self.assertFalse(report.passed)

    def test_clean_text_has_no_safety_findings(self):
        trace = Trace.from_dict(
            {
                "trace_id": "t10",
                "agent_name": "a",
                "workflow": "wf",
                "steps": [
                    {"step_id": "s1", "type": "model_response", "text": "Here is a normal, safe summary."}
                ],
            }
        )
        report = validate_trace(trace, make_policy())
        self.assertEqual([f for f in report.findings if f.category == "safety"], [])


class TestGroundingValidation(unittest.TestCase):
    def test_missing_citations_when_required_is_flagged(self):
        trace = Trace.from_dict(
            {
                "trace_id": "t11",
                "agent_name": "a",
                "workflow": "wf",
                "steps": [
                    {
                        "step_id": "s1",
                        "type": "model_response",
                        "text": "The account is Tier 1.",
                        "requires_grounding": True,
                        "citations": [],
                    }
                ],
            }
        )
        report = validate_trace(trace, make_policy())
        self.assertTrue(
            any("no citations" in f.message for f in report.findings if f.category == "grounding")
        )
        self.assertEqual(report.citation_coverage, 0.0)
        self.assertFalse(report.passed)

    def test_full_coverage_passes(self):
        trace = Trace.from_dict(
            {
                "trace_id": "t12",
                "agent_name": "a",
                "workflow": "wf",
                "steps": [
                    {
                        "step_id": "s1",
                        "type": "model_response",
                        "text": "The account is Tier 1.",
                        "requires_grounding": True,
                        "citations": [{"source": "crm_lookup:s0"}],
                    }
                ],
            }
        )
        report = validate_trace(trace, make_policy())
        self.assertEqual(report.citation_coverage, 1.0)
        self.assertEqual([f for f in report.findings if f.category == "grounding"], [])

    def test_no_grounding_required_steps_is_not_applicable(self):
        trace = Trace.from_dict(
            {
                "trace_id": "t13",
                "agent_name": "a",
                "workflow": "wf",
                "steps": [{"step_id": "s1", "type": "model_response", "text": "hi"}],
            }
        )
        report = validate_trace(trace, make_policy())
        self.assertIsNone(report.citation_coverage)


class TestOverallScoring(unittest.TestCase):
    def test_fully_clean_trace_scores_100_and_passes(self):
        trace = Trace.from_dict(
            {
                "trace_id": "t14",
                "agent_name": "a",
                "workflow": "wf",
                "steps": [
                    {
                        "step_id": "s1",
                        "type": "tool_call",
                        "tool_name": "crm_lookup",
                        "arguments": {"account_id": "ACC-1"},
                        "latency_ms": 200,
                        "cost_usd": 0.01,
                    },
                    {
                        "step_id": "s2",
                        "type": "model_response",
                        "text": "Account ACC-1 is Tier 1.",
                        "requires_grounding": True,
                        "citations": [{"source": "crm_lookup:s1"}],
                        "latency_ms": 300,
                        "cost_usd": 0.02,
                    },
                ],
            }
        )
        report = validate_trace(trace, make_policy())
        self.assertEqual(report.findings, [])
        self.assertAlmostEqual(report.score, 100.0)
        self.assertTrue(report.passed)

    def test_fail_under_threshold_respected(self):
        trace = Trace.from_dict(
            {
                "trace_id": "t15",
                "agent_name": "a",
                "workflow": "wf",
                "steps": [
                    {
                        "step_id": "s1",
                        "type": "tool_call",
                        "tool_name": "crm_lookup",
                        "arguments": {"account_id": "ACC-1", "unexpected": "x"},
                        "latency_ms": 200,
                        "cost_usd": 0.01,
                    },
                ],
            }
        )
        # A warning-only trace should pass a lenient threshold...
        lenient_report = validate_trace(trace, make_policy(), fail_under=0.0)
        self.assertTrue(lenient_report.passed)
        # ...but the same warning can still be inspected regardless of pass/fail.
        self.assertTrue(any(f.severity == "warning" for f in lenient_report.findings))


if __name__ == "__main__":
    unittest.main()
