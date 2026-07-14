import json
import unittest

from agent_reliability_harness.models import Finding, TraceReport
from agent_reliability_harness.report import (
    render_console,
    render_json,
    render_json_str,
    render_markdown,
)


def make_report(passed=True, findings=None, citation_coverage=0.9):
    return TraceReport(
        trace_id="t1",
        agent_name="agent-x",
        workflow="wf-y",
        policy_id="policy-1",
        findings=findings or [],
        total_latency_ms=1234.0,
        total_cost_usd=0.0456,
        citation_coverage=citation_coverage,
        score=95.5,
        passed=passed,
    )


class TestRenderConsole(unittest.TestCase):
    def test_pass_shows_pass_marker(self):
        text = render_console([make_report(passed=True)])
        self.assertIn("[PASS]", text)
        self.assertIn("t1", text)
        self.assertIn("SUMMARY: 1/1 traces passed", text)

    def test_fail_shows_findings(self):
        finding = Finding(severity="error", category="safety", step_id="s1", message="bad stuff")
        text = render_console([make_report(passed=False, findings=[finding])])
        self.assertIn("[FAIL]", text)
        self.assertIn("bad stuff", text)
        self.assertIn("ERROR", text)


class TestRenderJson(unittest.TestCase):
    def test_structure_and_summary(self):
        data = render_json([make_report(passed=True), make_report(passed=False)])
        self.assertEqual(data["summary"]["total_traces"], 2)
        self.assertEqual(data["summary"]["passed_traces"], 1)
        self.assertEqual(data["summary"]["failed_traces"], 1)
        self.assertEqual(len(data["reports"]), 2)

    def test_json_str_is_valid_json(self):
        text = render_json_str([make_report()])
        parsed = json.loads(text)
        self.assertIn("summary", parsed)
        self.assertIn("reports", parsed)


class TestRenderMarkdown(unittest.TestCase):
    def test_contains_table_and_findings_section(self):
        finding = Finding(severity="warning", category="schema", step_id="s2", message="odd | pipe")
        text = render_markdown([make_report(passed=False, findings=[finding])])
        self.assertIn("# Agent Reliability Harness Report", text)
        self.assertIn("| Trace | Agent | Workflow", text)
        self.assertIn("## Findings: t1", text)
        # pipe characters in messages must be escaped so the table stays valid
        self.assertIn("odd \\| pipe", text)


if __name__ == "__main__":
    unittest.main()
