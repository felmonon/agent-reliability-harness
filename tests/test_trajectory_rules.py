"""Tests for the v1 trajectory checks: sequence, flow, and completion."""

import unittest

from agent_reliability_harness.models import Policy, Trace
from agent_reliability_harness.validator import validate_trace


def make_trace(steps, trace_id="t1"):
    return Trace.from_dict(
        {"trace_id": trace_id, "agent_name": "a", "workflow": "wf", "steps": steps}
    )


def tool(step_id, name, args=None, status=None, error=None):
    step = {
        "step_id": step_id,
        "type": "tool_call",
        "tool_name": name,
        "arguments": args or {},
    }
    if status:
        step["status"] = status
    if error:
        step["error"] = error
    return step


def response(step_id, text="done", status=None):
    step = {"step_id": step_id, "type": "model_response", "text": text}
    if status:
        step["status"] = status
    return step


def make_policy(**overrides):
    base = {
        "policy_id": "trajectory-test",
        "allow_unlisted_tools": True,
        "allowed_tools": {},
    }
    base.update(overrides)
    return Policy.from_dict(base)


def rule_ids(report, severity=None):
    return sorted(
        f.rule_id
        for f in report.findings
        if severity is None or f.severity == severity
    )


class TestSequenceRequiredForbidden(unittest.TestCase):
    def test_required_tool_missing_is_error(self):
        policy = make_policy(sequence={"required_tools": ["lookup"]})
        report = validate_trace(policy=policy, trace=make_trace([response("s1")]))
        self.assertIn("ARH-SEQ-001", rule_ids(report, "error"))
        self.assertFalse(report.passed)

    def test_required_tool_present_passes(self):
        policy = make_policy(sequence={"required_tools": ["lookup"]})
        report = validate_trace(policy=policy, trace=make_trace([tool("s1", "lookup")]))
        self.assertEqual(rule_ids(report, "error"), [])
        self.assertTrue(report.passed)

    def test_forbidden_tool_called_is_error_per_call(self):
        policy = make_policy(sequence={"forbidden_tools": ["wire_money"]})
        trace = make_trace([tool("s1", "wire_money"), tool("s2", "wire_money")])
        report = validate_trace(trace, policy)
        seq2 = [f for f in report.findings if f.rule_id == "ARH-SEQ-002"]
        self.assertEqual(len(seq2), 2)
        self.assertEqual({f.step_id for f in seq2}, {"s1", "s2"})

    def test_required_and_forbidden_overlap_rejected_at_parse(self):
        with self.assertRaises(ValueError):
            make_policy(sequence={"required_tools": ["x"], "forbidden_tools": ["x"]})


class TestSequenceCallOrder(unittest.TestCase):
    def test_correct_order_passes(self):
        policy = make_policy(sequence={"call_order": ["search", "summarize", "send"]})
        trace = make_trace(
            [tool("s1", "search"), tool("s2", "summarize"), tool("s3", "send")]
        )
        report = validate_trace(trace, policy)
        self.assertEqual(rule_ids(report, "error"), [])

    def test_inverted_order_is_error(self):
        policy = make_policy(sequence={"call_order": ["search", "send"]})
        trace = make_trace([tool("s1", "send"), tool("s2", "search")])
        report = validate_trace(trace, policy)
        self.assertEqual(rule_ids(report, "error"), ["ARH-SEQ-003"])
        finding = [f for f in report.findings if f.rule_id == "ARH-SEQ-003"][0]
        self.assertEqual(finding.step_id, "s1")  # first call of the later tool

    def test_partial_order_ignores_uncalled_tools(self):
        policy = make_policy(sequence={"call_order": ["a", "b", "c"]})
        trace = make_trace([tool("s1", "a"), tool("s2", "c")])  # b never called
        report = validate_trace(trace, policy)
        self.assertEqual(rule_ids(report, "error"), [])

    def test_non_adjacent_inversion_detected(self):
        policy = make_policy(sequence={"call_order": ["a", "b", "c"]})
        trace = make_trace([tool("s1", "c"), tool("s2", "a"), tool("s3", "b")])
        report = validate_trace(trace, policy)
        violations = [f for f in report.findings if f.rule_id == "ARH-SEQ-003"]
        # a<c and b<c both violated; a<b holds
        self.assertEqual(len(violations), 2)

    def test_only_first_calls_are_ordered(self):
        # later repeat calls of an earlier tool do not violate the order
        policy = make_policy(sequence={"call_order": ["search", "send"]})
        trace = make_trace(
            [tool("s1", "search"), tool("s2", "send"), tool("s3", "search")]
        )
        report = validate_trace(trace, policy)
        self.assertEqual(rule_ids(report, "error"), [])

    def test_duplicate_call_order_entry_rejected(self):
        with self.assertRaises(ValueError):
            make_policy(sequence={"call_order": ["a", "a"]})


class TestSequenceCallCounts(unittest.TestCase):
    def test_max_calls_exceeded(self):
        policy = make_policy(
            allowed_tools={"search": {"max_calls": 2}}, allow_unlisted_tools=True
        )
        trace = make_trace(
            [tool("s1", "search"), tool("s2", "search"), tool("s3", "search")]
        )
        report = validate_trace(trace, policy)
        self.assertIn("ARH-SEQ-004", rule_ids(report, "error"))

    def test_min_calls_not_met(self):
        policy = make_policy(
            allowed_tools={"verify": {"min_calls": 1}}, allow_unlisted_tools=True
        )
        report = validate_trace(make_trace([response("s1")]), policy)
        self.assertIn("ARH-SEQ-005", rule_ids(report, "error"))

    def test_min_greater_than_max_rejected_at_parse(self):
        with self.assertRaises(ValueError):
            make_policy(allowed_tools={"x": {"min_calls": 3, "max_calls": 1}})

    def test_counts_within_bounds_pass(self):
        policy = make_policy(
            allowed_tools={"search": {"min_calls": 1, "max_calls": 3}},
            allow_unlisted_tools=True,
        )
        trace = make_trace([tool("s1", "search"), tool("s2", "search")])
        report = validate_trace(trace, policy)
        self.assertEqual(rule_ids(report, "error"), [])


class TestFlowErrorHandling(unittest.TestCase):
    def test_ignored_error_is_flagged(self):
        policy = make_policy(error_handling={"require_retry_on_error": True})
        trace = make_trace(
            [tool("s1", "fetch", status="error", error="timeout"), response("s2")]
        )
        report = validate_trace(trace, policy)
        self.assertEqual(rule_ids(report, "error"), ["ARH-FLW-001"])

    def test_retried_error_passes(self):
        policy = make_policy(error_handling={"require_retry_on_error": True})
        trace = make_trace(
            [
                tool("s1", "fetch", status="error", error="timeout"),
                tool("s2", "fetch"),
                response("s3"),
            ]
        )
        report = validate_trace(trace, policy)
        self.assertEqual(rule_ids(report, "error"), [])

    def test_error_field_implies_error_status(self):
        policy = make_policy(error_handling={"require_retry_on_error": True})
        trace = make_trace([tool("s1", "fetch", error="boom"), response("s2")])
        report = validate_trace(trace, policy)
        self.assertEqual(rule_ids(report, "error"), ["ARH-FLW-001"])

    def test_retry_storm_flagged_at_first_excess_attempt(self):
        policy = make_policy(error_handling={"max_attempts": 2})
        trace = make_trace(
            [
                tool("s1", "fetch", {"url": "x"}),
                tool("s2", "fetch", {"url": "x"}),
                tool("s3", "fetch", {"url": "x"}),
            ]
        )
        report = validate_trace(trace, policy)
        storms = [f for f in report.findings if f.rule_id == "ARH-FLW-002"]
        self.assertEqual(len(storms), 1)
        self.assertEqual(storms[0].step_id, "s3")

    def test_different_arguments_do_not_count_as_storm(self):
        policy = make_policy(error_handling={"max_attempts": 2})
        trace = make_trace(
            [
                tool("s1", "fetch", {"url": "a"}),
                tool("s2", "fetch", {"url": "b"}),
                tool("s3", "fetch", {"url": "c"}),
            ]
        )
        report = validate_trace(trace, policy)
        self.assertEqual(rule_ids(report, "error"), [])


class TestFlowSideEffects(unittest.TestCase):
    def _policy(self):
        return make_policy(
            allowed_tools={
                "send_email": {
                    "required_arguments": {"to": "str"},
                    "side_effect": True,
                }
            }
        )

    def test_duplicate_side_effect_flagged(self):
        trace = make_trace(
            [
                tool("s1", "send_email", {"to": "a@b.c"}),
                tool("s2", "send_email", {"to": "a@b.c"}),
            ]
        )
        report = validate_trace(trace, self._policy())
        dups = [f for f in report.findings if f.rule_id == "ARH-FLW-003"]
        self.assertEqual(len(dups), 1)
        self.assertEqual(dups[0].step_id, "s2")

    def test_retry_after_error_is_allowed(self):
        trace = make_trace(
            [
                tool("s1", "send_email", {"to": "a@b.c"}, status="error", error="smtp 500"),
                tool("s2", "send_email", {"to": "a@b.c"}),
            ]
        )
        report = validate_trace(trace, self._policy())
        self.assertEqual(rule_ids(report, "error"), [])

    def test_different_arguments_are_not_duplicates(self):
        trace = make_trace(
            [
                tool("s1", "send_email", {"to": "a@b.c"}),
                tool("s2", "send_email", {"to": "x@y.z"}),
            ]
        )
        report = validate_trace(trace, self._policy())
        self.assertEqual(rule_ids(report, "error"), [])


class TestCompletion(unittest.TestCase):
    def test_missing_final_response_flagged(self):
        policy = make_policy(completion={"require_final_response": True})
        trace = make_trace([tool("s1", "search")])
        report = validate_trace(trace, policy)
        self.assertEqual(rule_ids(report, "error"), ["ARH-CMP-001"])

    def test_empty_final_text_flagged(self):
        policy = make_policy(completion={"require_final_response": True})
        trace = make_trace([response("s1", text="  ")])
        report = validate_trace(trace, policy)
        self.assertEqual(rule_ids(report, "error"), ["ARH-CMP-001"])

    def test_errored_final_response_flagged(self):
        policy = make_policy(completion={"require_final_response": True})
        trace = make_trace([response("s1", text="done", status="error")])
        report = validate_trace(trace, policy)
        self.assertEqual(rule_ids(report, "error"), ["ARH-CMP-001"])

    def test_empty_trace_flagged(self):
        policy = make_policy(completion={"require_final_response": True})
        report = validate_trace(make_trace([]), policy)
        self.assertEqual(rule_ids(report, "error"), ["ARH-CMP-001"])

    def test_max_steps_exceeded(self):
        policy = make_policy(completion={"max_steps": 2})
        trace = make_trace([tool("s1", "a"), tool("s2", "a"), response("s3")])
        report = validate_trace(trace, policy)
        self.assertEqual(rule_ids(report, "error"), ["ARH-CMP-002"])

    def test_good_completion_passes(self):
        policy = make_policy(
            completion={"require_final_response": True, "max_steps": 10}
        )
        trace = make_trace([tool("s1", "a"), response("s2", text="answer")])
        report = validate_trace(trace, policy)
        self.assertEqual(rule_ids(report, "error"), [])
        self.assertTrue(report.passed)


class TestStructureLint(unittest.TestCase):
    def test_duplicate_step_ids_warn(self):
        policy = make_policy()
        trace = make_trace([response("dup"), response("dup")])
        report = validate_trace(trace, policy)
        warnings = [f for f in report.findings if f.rule_id == "ARH-SCH-010"]
        self.assertEqual(len(warnings), 1)
        self.assertTrue(report.passed)  # warning only


class TestLegacyScoreCompatibility(unittest.TestCase):
    def test_new_categories_inapplicable_for_legacy_policy(self):
        """A v0.1.x policy must produce the same score as before."""
        legacy_policy = Policy.from_dict(
            {
                "policy_id": "legacy",
                "allowed_tools": {"crm_lookup": {"required_arguments": {"account_id": "str"}}},
                "budgets": {"max_total_latency_ms": 5000},
            }
        )
        trace = make_trace(
            [
                {
                    "step_id": "s1",
                    "type": "tool_call",
                    "tool_name": "crm_lookup",
                    "arguments": {"account_id": "A"},
                    "latency_ms": 100,
                }
            ]
        )
        report = validate_trace(trace, legacy_policy)
        self.assertAlmostEqual(report.score, 100.0)
        self.assertTrue(report.passed)


if __name__ == "__main__":
    unittest.main()
