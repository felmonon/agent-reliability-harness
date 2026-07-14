"""Tests for JUnit XML and SARIF renderers: structure, escaping, determinism."""

import json
import unittest
import xml.etree.ElementTree as ET

from agent_reliability_harness.models import Finding, TraceReport
from agent_reliability_harness.report import (
    render_junit,
    render_sarif,
    render_sarif_str,
)


def make_report(trace_id="t1", passed=True, findings=None, source_path=None):
    return TraceReport(
        trace_id=trace_id,
        agent_name="agent-x",
        workflow="wf-y",
        policy_id="policy-1",
        findings=findings or [],
        total_latency_ms=1234.0,
        total_cost_usd=0.0456,
        citation_coverage=None,
        score=95.5 if passed else 40.0,
        passed=passed,
        source_path=source_path,
    )


def bad_finding(rule_id="ARH-SCH-001", severity="error", message="tool 'x' is bad <&>"):
    return Finding(
        severity=severity,
        category="schema",
        message=message,
        step_id="s1",
        rule_id=rule_id,
    )


class TestJUnit(unittest.TestCase):
    def test_valid_xml_with_counts(self):
        xml = render_junit([make_report(), make_report("t2", passed=False, findings=[bad_finding()])])
        root = ET.fromstring(xml)
        self.assertEqual(root.tag, "testsuites")
        self.assertEqual(root.get("tests"), "2")
        self.assertEqual(root.get("failures"), "1")
        cases = root.findall("./testsuite/testcase")
        self.assertEqual(len(cases), 2)
        failures = root.findall("./testsuite/testcase/failure")
        self.assertEqual(len(failures), 1)
        self.assertIn("ARH-SCH-001", failures[0].text)

    def test_xml_escaping(self):
        xml = render_junit(
            [make_report("t<&>", passed=False, findings=[bad_finding(message='msg with "quotes" & <tags>')])]
        )
        root = ET.fromstring(xml)  # must parse despite hostile characters
        case = root.find("./testsuite/testcase")
        self.assertEqual(case.get("name"), "t<&>")

    def test_deterministic(self):
        reports = [make_report("t2", passed=False, findings=[bad_finding()])]
        self.assertEqual(render_junit(reports), render_junit(reports))


class TestSarif(unittest.TestCase):
    def test_structure(self):
        sarif = render_sarif(
            [make_report("t1", passed=False, findings=[bad_finding()], source_path="traces/a.json")],
            tool_version="0.2.0",
        )
        self.assertEqual(sarif["version"], "2.1.0")
        run = sarif["runs"][0]
        driver = run["tool"]["driver"]
        self.assertEqual(driver["name"], "agent-reliability-harness")
        self.assertEqual(driver["version"], "0.2.0")
        rule_ids = [r["id"] for r in driver["rules"]]
        self.assertEqual(rule_ids, ["ARH-SCH-001"])
        result = run["results"][0]
        self.assertEqual(result["ruleId"], "ARH-SCH-001")
        self.assertEqual(result["level"], "error")
        self.assertEqual(
            result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"],
            "traces/a.json",
        )
        self.assertEqual(result["locations"][0]["logicalLocations"][0]["name"], "s1")
        self.assertIn("partialFingerprints", result)

    def test_rule_index_consistency(self):
        findings = [bad_finding("ARH-SCH-001"), bad_finding("ARH-SEQ-003")]
        sarif = render_sarif([make_report("t1", passed=False, findings=findings)], "0.2.0")
        driver_rules = sarif["runs"][0]["tool"]["driver"]["rules"]
        for result in sarif["runs"][0]["results"]:
            index = result["ruleIndex"]
            self.assertEqual(driver_rules[index]["id"], result["ruleId"])

    def test_unknown_rule_falls_back(self):
        finding = Finding(severity="warning", category="custom", message="hand-made")
        sarif = render_sarif([make_report("t1", findings=[finding])], "0.2.0")
        self.assertEqual(sarif["runs"][0]["results"][0]["ruleId"], "ARH-000")

    def test_severity_level_mapping(self):
        findings = [
            bad_finding(severity="error"),
            bad_finding("ARH-SCH-005", severity="warning"),
            bad_finding("ARH-SCH-006", severity="info"),
        ]
        sarif = render_sarif([make_report("t1", findings=findings)], "0.2.0")
        levels = sorted(r["level"] for r in sarif["runs"][0]["results"])
        self.assertEqual(levels, ["error", "note", "warning"])

    def test_windows_path_normalized(self):
        sarif = render_sarif(
            [make_report("t1", findings=[bad_finding()], source_path="traces\\a.json")],
            "0.2.0",
        )
        uri = sarif["runs"][0]["results"][0]["locations"][0]["physicalLocation"][
            "artifactLocation"
        ]["uri"]
        self.assertEqual(uri, "traces/a.json")

    def test_deterministic_and_json_serializable(self):
        reports = [make_report("t1", passed=False, findings=[bad_finding()])]
        s1 = render_sarif_str(reports, "0.2.0")
        s2 = render_sarif_str(reports, "0.2.0")
        self.assertEqual(s1, s2)
        json.loads(s1)


if __name__ == "__main__":
    unittest.main()
