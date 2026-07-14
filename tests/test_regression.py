"""Tests for baseline-versus-candidate comparison and the CI gate."""

import unittest

from agent_reliability_harness.models import Policy, Trace
from agent_reliability_harness.regression import (
    compare_reports,
    evaluate_gate,
    render_compare_console,
    render_compare_json,
    render_compare_markdown,
)
from agent_reliability_harness.report import render_json
from agent_reliability_harness.validator import validate_trace

POLICY = Policy.from_dict(
    {
        "policy_id": "p",
        "allow_unlisted_tools": False,
        "allowed_tools": {
            "search": {"required_arguments": {"query": "str"}},
            "send": {"required_arguments": {"to": "str"}, "side_effect": True},
        },
        "sequence": {"call_order": ["search", "send"]},
    }
)


def run(steps, trace_id="t1"):
    trace = Trace.from_dict(
        {"trace_id": trace_id, "agent_name": "a", "workflow": "wf", "steps": steps}
    )
    return validate_trace(trace, POLICY)


GOOD_STEPS = [
    {"step_id": "s1", "type": "tool_call", "tool_name": "search", "arguments": {"query": "q"}},
    {"step_id": "s2", "type": "tool_call", "tool_name": "send", "arguments": {"to": "a@b.c"}},
    {"step_id": "s3", "type": "model_response", "text": "done"},
]

BAD_STEPS = [
    {"step_id": "s1", "type": "tool_call", "tool_name": "send", "arguments": {"to": "a@b.c"}},
    {"step_id": "s2", "type": "tool_call", "tool_name": "search", "arguments": {"query": "q"}},
    {"step_id": "s3", "type": "model_response", "text": "done"},
]


class TestCompareReports(unittest.TestCase):
    def test_identical_runs_have_no_changes(self):
        base = render_json([run(GOOD_STEPS)])
        cand = render_json([run(GOOD_STEPS)])
        result = compare_reports(base, cand)
        self.assertEqual(result.summary()["new_findings"], 0)
        self.assertEqual(result.summary()["resolved_findings"], 0)
        self.assertEqual(result.summary()["pass_to_fail"], 0)
        passed, reasons = evaluate_gate(result)
        self.assertTrue(passed)
        self.assertEqual(reasons, [])

    def test_regression_detected(self):
        base = render_json([run(GOOD_STEPS)])
        cand = render_json([run(BAD_STEPS)])
        result = compare_reports(base, cand)
        summary = result.summary()
        self.assertEqual(summary["pass_to_fail"], 1)
        self.assertGreaterEqual(summary["new_error_findings"], 1)
        new_rule_ids = {f.rule_id for f in result.new_error_findings}
        self.assertIn("ARH-SEQ-003", new_rule_ids)
        passed, reasons = evaluate_gate(result)
        self.assertFalse(passed)
        self.assertTrue(any("pass to fail" in r for r in reasons))

    def test_fix_detected_as_resolved(self):
        base = render_json([run(BAD_STEPS)])
        cand = render_json([run(GOOD_STEPS)])
        result = compare_reports(base, cand)
        self.assertEqual(result.summary()["fail_to_pass"], 1)
        self.assertGreaterEqual(result.summary()["resolved_findings"], 1)
        passed, _ = evaluate_gate(result)
        self.assertTrue(passed)

    def test_added_failing_trace_fails_gate(self):
        base = render_json([run(GOOD_STEPS)])
        cand = render_json([run(GOOD_STEPS), run(BAD_STEPS, trace_id="t2")])
        result = compare_reports(base, cand)
        self.assertEqual(result.summary()["traces_added"], 1)
        passed, reasons = evaluate_gate(result)
        self.assertFalse(passed)
        self.assertTrue(any("added trace 't2' fails" in r for r in reasons))

    def test_removed_trace_reported_but_does_not_fail_gate(self):
        base = render_json([run(GOOD_STEPS), run(GOOD_STEPS, trace_id="t2")])
        cand = render_json([run(GOOD_STEPS)])
        result = compare_reports(base, cand)
        self.assertEqual(result.summary()["traces_removed"], 1)
        passed, _ = evaluate_gate(result)
        self.assertTrue(passed)

    def test_max_score_drop_gate(self):
        base = render_json([run(GOOD_STEPS)])
        cand = render_json([run(BAD_STEPS)])
        result = compare_reports(base, cand)
        passed, reasons = evaluate_gate(result, max_score_drop=0.5)
        self.assertFalse(passed)
        self.assertTrue(any("score dropped" in r for r in reasons))

    def test_fail_on_failures_mode(self):
        base = render_json([run(BAD_STEPS)])
        cand = render_json([run(BAD_STEPS)])
        result = compare_reports(base, cand)
        # no regression relative to baseline...
        passed_reg, _ = evaluate_gate(result, fail_on="regressions")
        self.assertTrue(passed_reg)
        # ...but candidate still fails in absolute terms
        passed_abs, reasons = evaluate_gate(result, fail_on="failures")
        self.assertFalse(passed_abs)
        self.assertTrue(any("failing traces" in r for r in reasons))

    def test_fail_on_never_mode(self):
        base = render_json([run(GOOD_STEPS)])
        cand = render_json([run(BAD_STEPS)])
        result = compare_reports(base, cand)
        passed, reasons = evaluate_gate(result, fail_on="never")
        self.assertTrue(passed)
        self.assertEqual(reasons, [])

    def test_unknown_gate_mode_raises(self):
        base = render_json([run(GOOD_STEPS)])
        result = compare_reports(base, base)
        with self.assertRaises(ValueError):
            evaluate_gate(result, fail_on="bogus")


class TestLegacyBaselineCompatibility(unittest.TestCase):
    def test_v01_baseline_without_rule_ids_matches_loosely(self):
        base = render_json([run(BAD_STEPS)])
        # simulate a v0.1.x baseline: findings have no rule_id key
        for entry in base["reports"]:
            for finding in entry["findings"]:
                finding.pop("rule_id", None)
        cand = render_json([run(BAD_STEPS)])
        result = compare_reports(base, cand)
        self.assertEqual(result.summary()["new_findings"], 0)
        self.assertEqual(result.summary()["resolved_findings"], 0)
        passed, _ = evaluate_gate(result)
        self.assertTrue(passed)


class TestCompareInputValidation(unittest.TestCase):
    def test_not_a_report_raises(self):
        with self.assertRaises(ValueError):
            compare_reports({"foo": 1}, {"reports": []})
        with self.assertRaises(ValueError):
            compare_reports({"reports": []}, [1, 2, 3])  # type: ignore[arg-type]

    def test_duplicate_trace_ids_rejected(self):
        report = render_json([run(GOOD_STEPS), run(GOOD_STEPS)])
        with self.assertRaises(ValueError):
            compare_reports(report, render_json([run(GOOD_STEPS)]))


class TestCompareRenderers(unittest.TestCase):
    def test_renderers_are_deterministic(self):
        base = render_json([run(GOOD_STEPS)])
        cand = render_json([run(BAD_STEPS)])
        result1 = compare_reports(base, cand)
        result2 = compare_reports(base, cand)
        g1 = evaluate_gate(result1)
        g2 = evaluate_gate(result2)
        self.assertEqual(
            render_compare_json(result1, *g1), render_compare_json(result2, *g2)
        )
        self.assertEqual(
            render_compare_console(result1, *g1), render_compare_console(result2, *g2)
        )
        self.assertEqual(
            render_compare_markdown(result1, *g1), render_compare_markdown(result2, *g2)
        )

    def test_markdown_contains_gate_and_findings(self):
        base = render_json([run(GOOD_STEPS)])
        cand = render_json([run(BAD_STEPS)])
        result = compare_reports(base, cand)
        passed, reasons = evaluate_gate(result)
        md = render_compare_markdown(result, passed, reasons)
        self.assertIn("**Gate: FAIL**", md)
        self.assertIn("ARH-SEQ-003", md)
        self.assertIn("pass->fail", md)


if __name__ == "__main__":
    unittest.main()
