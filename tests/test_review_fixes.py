"""Regression tests for issues raised by the independent v0.2.0 review.

Each test class references the review finding it pins. These tests must
never be weakened: they encode exact failure scenarios demonstrated by
reviewers with working proofs of concept.
"""

import contextlib
import io
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from agent_reliability_harness.cli import main
from agent_reliability_harness.models import ArgSpec, Finding, Policy, Step, Trace, TraceReport
from agent_reliability_harness.regression import compare_reports, evaluate_gate
from agent_reliability_harness.report import render_junit, render_markdown
from agent_reliability_harness.validator import validate_trace


def make_trace(steps):
    return Trace.from_dict(
        {"trace_id": "t", "agent_name": "a", "workflow": "w", "steps": steps}
    )


class TestLooseMatchingDoesNotSwallowRegressions(unittest.TestCase):
    """Review finding (critical): two findings that BOTH carry different
    rule_ids must never loose-match each other, even when a legacy
    (rule_id-less) finding exists elsewhere in the trace."""

    def _report(self, findings):
        return {
            "reports": [
                {
                    "trace_id": "t1",
                    "policy_id": "p",
                    "score": 50.0,
                    "passed": False,
                    "findings": findings,
                }
            ]
        }

    def test_rule_swap_on_same_step_is_new_and_resolved(self):
        baseline = self._report(
            [
                {"severity": "warning", "category": "schema", "message": "legacy", "step_id": "s9"},
                {"severity": "error", "category": "flow", "message": "never retried",
                 "step_id": "s2", "rule_id": "ARH-FLW-001"},
            ]
        )
        candidate = self._report(
            [
                {"severity": "warning", "category": "schema", "message": "legacy", "step_id": "s9"},
                {"severity": "error", "category": "flow", "message": "retry storm",
                 "step_id": "s2", "rule_id": "ARH-FLW-002"},
            ]
        )
        result = compare_reports(baseline, candidate)
        new_ids = [f.rule_id for f in result.new_findings]
        resolved_ids = [f.rule_id for f in result.resolved_findings]
        self.assertEqual(new_ids, ["ARH-FLW-002"])
        self.assertEqual(resolved_ids, ["ARH-FLW-001"])
        passed, reasons = evaluate_gate(result)
        self.assertFalse(passed)
        self.assertTrue(any("ARH-FLW-002" in r for r in reasons))

    def test_tagged_new_finding_never_matches_tagged_resolved(self):
        baseline = self._report(
            [{"severity": "error", "category": "schema", "message": "missing arg",
              "step_id": "s1", "rule_id": "ARH-SCH-003"}]
        )
        candidate = self._report(
            [{"severity": "error", "category": "schema", "message": "wrong type",
              "step_id": "s1", "rule_id": "ARH-SCH-004"}]
        )
        result = compare_reports(baseline, candidate)
        self.assertEqual([f.rule_id for f in result.new_findings], ["ARH-SCH-004"])
        passed, _ = evaluate_gate(result)
        self.assertFalse(passed)

    def test_true_legacy_baseline_still_matches(self):
        baseline = self._report(
            [{"severity": "error", "category": "schema", "message": "old msg", "step_id": "s1"}]
        )
        candidate = self._report(
            [{"severity": "error", "category": "schema", "message": "new msg",
              "step_id": "s1", "rule_id": "ARH-SCH-003"}]
        )
        result = compare_reports(baseline, candidate)
        self.assertEqual(result.new_findings, [])
        self.assertEqual(result.resolved_findings, [])


class TestWarningOnlyTracesNeverFail(unittest.TestCase):
    """Review finding (high): a trace whose only findings are warnings must
    pass; unverifiable budgets are score-neutral warnings."""

    def test_unverifiable_token_budget_alone_passes(self):
        policy = Policy.from_dict({"policy_id": "p", "budgets": {"max_total_tokens": 10}})
        report = validate_trace(
            make_trace([{"step_id": "s1", "type": "model_response", "text": "hi"}]), policy
        )
        self.assertEqual([f.rule_id for f in report.findings], ["ARH-BUD-005"])
        self.assertEqual(report.score, 100.0)
        self.assertTrue(report.passed)

    def test_unverifiable_latency_and_cost_budgets_warn_not_pass_silently(self):
        policy = Policy.from_dict(
            {
                "policy_id": "p",
                "budgets": {
                    "max_total_latency_ms": 1,
                    "max_step_latency_ms": 1,
                    "max_total_cost_usd": 0.01,
                },
            }
        )
        report = validate_trace(
            make_trace([{"step_id": "s1", "type": "model_response", "text": "hi"}]), policy
        )
        rule_ids = sorted(f.rule_id for f in report.findings)
        self.assertEqual(rule_ids, ["ARH-BUD-006", "ARH-BUD-007"])
        self.assertTrue(all(f.severity == "warning" for f in report.findings))
        self.assertTrue(report.passed)

    def test_budgets_still_enforced_when_data_present(self):
        policy = Policy.from_dict(
            {"policy_id": "p", "budgets": {"max_total_latency_ms": 100}}
        )
        report = validate_trace(
            make_trace(
                [{"step_id": "s1", "type": "model_response", "text": "hi", "latency_ms": 500}]
            ),
            policy,
        )
        self.assertEqual([f.rule_id for f in report.findings], ["ARH-BUD-002"])
        self.assertFalse(report.passed)


class TestTelemetryValidation(unittest.TestCase):
    """Review finding (high): negative/non-finite/mistyped telemetry must be
    rejected at parse time, not silently summed."""

    def test_negative_latency_rejected(self):
        with self.assertRaises(ValueError):
            Step.from_dict({"step_id": "s", "type": "tool_call", "latency_ms": -1000})

    def test_negative_cost_rejected(self):
        with self.assertRaises(ValueError):
            Step.from_dict({"step_id": "s", "type": "tool_call", "cost_usd": -10})

    def test_string_latency_rejected(self):
        with self.assertRaises(ValueError):
            Step.from_dict({"step_id": "s", "type": "tool_call", "latency_ms": "slow"})

    def test_nan_latency_rejected(self):
        with self.assertRaises(ValueError):
            Step.from_dict({"step_id": "s", "type": "tool_call", "latency_ms": float("nan")})

    def test_fractional_tokens_rejected(self):
        with self.assertRaises(ValueError):
            Step.from_dict(
                {"step_id": "s", "type": "model_response", "input_tokens": 1.5}
            )

    def test_non_string_text_rejected(self):
        with self.assertRaises(ValueError):
            Step.from_dict({"step_id": "s", "type": "model_response", "text": ["a"]})

    def test_non_string_tool_name_rejected(self):
        with self.assertRaises(ValueError):
            Step.from_dict({"step_id": "s", "type": "tool_call", "tool_name": 42})


class TestNestedSafetyScanning(unittest.TestCase):
    """Review finding (high): unsafe content nested in structured arguments
    or outputs must not evade scanning."""

    POLICY = Policy.from_dict(
        {"policy_id": "p", "allow_unlisted_tools": True,
         "unsafe_patterns": ["\\bpassword\\s*[:=]"]}
    )

    def test_nested_dict_argument_scanned(self):
        trace = make_trace(
            [{"step_id": "s1", "type": "tool_call", "tool_name": "x",
              "arguments": {"payload": {"secret": "password: hunter2"}}}]
        )
        report = validate_trace(trace, self.POLICY)
        self.assertIn("ARH-SAF-001", [f.rule_id for f in report.findings])

    def test_nested_list_output_scanned(self):
        trace = make_trace(
            [{"step_id": "s1", "type": "tool_call", "tool_name": "x",
              "arguments": {},
              "output": {"results": [{"note": "the password: hunter2"}]}}]
        )
        report = validate_trace(trace, self.POLICY)
        self.assertIn("ARH-SAF-001", [f.rule_id for f in report.findings])

    def test_error_string_scanned(self):
        trace = make_trace(
            [{"step_id": "s1", "type": "tool_call", "tool_name": "x",
              "arguments": {}, "error": "dump: password: hunter2"}]
        )
        report = validate_trace(trace, self.POLICY)
        self.assertIn("ARH-SAF-001", [f.rule_id for f in report.findings])


class TestArgSpecHardening(unittest.TestCase):
    """Review findings (medium): pattern regexes validated at parse time,
    NaN cannot bypass ranges, unknown types do not disable value checks."""

    def test_invalid_pattern_rejected_at_policy_parse(self):
        with self.assertRaises(ValueError) as ctx:
            ArgSpec.from_raw({"type": "str", "pattern": "["}, "tool.arg")
        self.assertIn("invalid pattern regex", str(ctx.exception))

    def test_min_greater_than_max_rejected(self):
        with self.assertRaises(ValueError):
            ArgSpec.from_raw({"type": "int", "min": 5, "max": 1}, "tool.arg")

    def test_non_finite_bound_rejected(self):
        with self.assertRaises(ValueError):
            ArgSpec.from_raw({"type": "float", "min": float("inf")}, "tool.arg")

    def test_nan_value_fails_range(self):
        policy = Policy.from_dict(
            {"policy_id": "p", "allowed_tools": {"t": {"required_arguments": {
                "x": {"type": "float", "min": 0, "max": 1}}}}}
        )
        trace = make_trace(
            [{"step_id": "s1", "type": "tool_call", "tool_name": "t",
              "arguments": {"x": float("nan")}}]
        )
        report = validate_trace(trace, policy)
        self.assertIn("ARH-SCH-009", [f.rule_id for f in report.findings])
        self.assertFalse(report.passed)

    def test_unknown_type_still_enforces_enum(self):
        policy = Policy.from_dict(
            {"policy_id": "p", "allowed_tools": {"t": {"required_arguments": {
                "x": {"type": "integer", "enum": ["ok"]}}}}}
        )
        trace = make_trace(
            [{"step_id": "s1", "type": "tool_call", "tool_name": "t",
              "arguments": {"x": "bad"}}]
        )
        report = validate_trace(trace, policy)
        rule_ids = [f.rule_id for f in report.findings]
        self.assertIn("ARH-SCH-006", rule_ids)  # unknown type surfaced
        self.assertIn("ARH-SCH-007", rule_ids)  # enum still enforced
        self.assertFalse(report.passed)


class TestJUnitWellFormedness(unittest.TestCase):
    """Review finding (medium): control characters must not produce invalid
    XML that strict JUnit consumers reject."""

    def test_control_characters_round_trip(self):
        report = TraceReport(
            trace_id="t\x00\x01\x1fid",
            agent_name="a\x07gent",
            workflow="w",
            policy_id="p",
            findings=[
                Finding(severity="error", category="safety",
                        message="bad \x00 content \x1b here", step_id="s\x011",
                        rule_id="ARH-SAF-001")
            ],
            total_latency_ms=1.0,
            total_cost_usd=0.0,
            citation_coverage=None,
            score=0.0,
            passed=False,
        )
        xml = render_junit([report])
        root = ET.fromstring(xml)  # must be well-formed XML 1.0
        self.assertEqual(root.get("failures"), "1")


class TestMarkdownCellEscaping(unittest.TestCase):
    """Review finding (low): trace-derived fields must not break Markdown
    tables or inject rendering artifacts into PR summaries."""

    def test_pipes_and_newlines_in_trace_fields_escaped(self):
        report = TraceReport(
            trace_id="evil | ![x](http://evil/x.png) |",
            agent_name="a|b\nc",
            workflow="w|f",
            policy_id="p",
            findings=[],
            total_latency_ms=1.0,
            total_cost_usd=0.0,
            citation_coverage=None,
            score=100.0,
            passed=True,
        )
        md = render_markdown([report])
        table_lines = [line for line in md.splitlines() if line.startswith("|") and "evil" in line]
        self.assertEqual(len(table_lines), 1)
        # the row must still have exactly the 8 expected columns
        self.assertEqual(table_lines[0].count(" | "), 7)


class TestCliInputHardening(unittest.TestCase):
    """Review findings (low): fail-under bounds and deep-nesting handling."""

    def _write(self, tmp, name, content):
        path = Path(tmp) / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_fail_under_out_of_bounds_is_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy = self._write(tmp, "p.json", '{"policy_id": "p"}')
            trace = self._write(
                tmp, "t.json",
                '{"trace_id": "t", "agent_name": "a", "workflow": "w", "steps": []}',
            )
            for bad in ("-1", "101", "nan"):
                with self.assertRaises(SystemExit) as ctx:
                    with contextlib.redirect_stderr(io.StringIO()):
                        main(["validate", "--policy", str(policy), str(trace),
                              "--fail-under", bad])
                self.assertEqual(ctx.exception.code, 2)

    def test_fail_under_bounds_enforced_in_api(self):
        policy = Policy.from_dict({"policy_id": "p"})
        trace = make_trace([])
        for bad in (-1, 101, float("nan")):
            with self.assertRaises(ValueError):
                validate_trace(trace, policy, fail_under=bad)

    def test_deeply_nested_json_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy = self._write(tmp, "p.json", '{"policy_id": "p"}')
            evil = self._write(tmp, "evil.json", "[" * 100000 + "]" * 100000)
            with self.assertRaises(SystemExit) as ctx:
                main(["validate", "--policy", str(policy), str(evil)])
            self.assertIn("nested too deeply", str(ctx.exception))


class TestCanonicalArgumentsDeterminism(unittest.TestCase):
    """Review finding (medium): non-JSON argument values passed via the
    Python API must not produce address-bearing reprs in identity keys."""

    def test_non_json_values_use_stable_fallback(self):
        from agent_reliability_harness.validator import _canonical_arguments

        class Opaque:
            pass

        step_a = Step(step_id="a", type="tool_call", tool_name="t",
                      arguments={"x": Opaque()})
        step_b = Step(step_id="b", type="tool_call", tool_name="t",
                      arguments={"x": Opaque()})
        self.assertEqual(_canonical_arguments(step_a), _canonical_arguments(step_b))
        self.assertNotIn("0x", _canonical_arguments(step_a))


if __name__ == "__main__":
    unittest.main()
