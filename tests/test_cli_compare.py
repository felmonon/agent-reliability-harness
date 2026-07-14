"""CLI tests for the extended validate options and the compare subcommand."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from agent_reliability_harness.cli import main

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLES = REPO_ROOT / "samples"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
TRAJ_POLICY = SAMPLES / "policy_trajectory.json"
PASS_TRACE = SAMPLES / "traces" / "refund_workflow_pass.json"
FAIL_TRACE = SAMPLES / "traces" / "refund_workflow_double_refund.json"


def run_cli(args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main(args)
    return code, buf.getvalue()


class TestValidateNewOutputs(unittest.TestCase):
    def test_junit_and_sarif_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            junit = Path(tmp) / "report.xml"
            sarif = Path(tmp) / "report.sarif"
            code, _ = run_cli(
                [
                    "validate",
                    "--policy",
                    str(TRAJ_POLICY),
                    str(PASS_TRACE),
                    str(FAIL_TRACE),
                    "--junit-out",
                    str(junit),
                    "--sarif-out",
                    str(sarif),
                    "--quiet",
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("<testsuites", junit.read_text(encoding="utf-8"))
            sarif_doc = json.loads(sarif.read_text(encoding="utf-8"))
            self.assertEqual(sarif_doc["version"], "2.1.0")
            rule_ids = {r["ruleId"] for r in sarif_doc["runs"][0]["results"]}
            self.assertIn("ARH-FLW-003", rule_ids)  # duplicate refund
            self.assertIn("ARH-SEQ-001", rule_ids)  # missing eligibility check

    def test_trajectory_sample_detects_double_refund(self):
        code, output = run_cli(
            ["validate", "--policy", str(TRAJ_POLICY), str(FAIL_TRACE)]
        )
        self.assertEqual(code, 1)
        self.assertIn("ARH-FLW-003", output.replace("[", " ").replace("]", " ") or output)

    def test_openai_format_flag(self):
        code, output = run_cli(
            [
                "validate",
                "--policy",
                str(TRAJ_POLICY),
                "--format",
                "openai-chat",
                str(FIXTURES / "openai_chat_refund.json"),
            ]
        )
        # trace uses lookup_order/issue_refund but not the required
        # check_refund_eligibility -> fails, proving the adapter fed the rules
        self.assertEqual(code, 1)
        self.assertIn("check_refund_eligibility", output)

    def test_auto_format_detects_openai(self):
        code, output = run_cli(
            [
                "validate",
                "--policy",
                str(TRAJ_POLICY),
                str(FIXTURES / "openai_chat_refund.json"),
            ]
        )
        self.assertEqual(code, 1)
        self.assertIn("openai-refund-001", output)


class TestCompareCli(unittest.TestCase):
    def test_compare_identical_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline.json"
            code, _ = run_cli(
                [
                    "validate",
                    "--policy",
                    str(TRAJ_POLICY),
                    str(PASS_TRACE),
                    "--json-out",
                    str(baseline),
                    "--quiet",
                ]
            )
            self.assertEqual(code, 0)
            code, output = run_cli(
                [
                    "compare",
                    "--baseline",
                    str(baseline),
                    "--policy",
                    str(TRAJ_POLICY),
                    str(PASS_TRACE),
                ]
            )
            self.assertEqual(code, 0)
            self.assertIn("GATE: PASS", output)

    def test_compare_detects_regression_and_writes_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline.json"
            run_cli(
                [
                    "validate",
                    "--policy",
                    str(TRAJ_POLICY),
                    str(PASS_TRACE),
                    "--json-out",
                    str(baseline),
                    "--quiet",
                ]
            )
            cmp_json = Path(tmp) / "compare.json"
            cmp_md = Path(tmp) / "compare.md"
            code, output = run_cli(
                [
                    "compare",
                    "--baseline",
                    str(baseline),
                    "--policy",
                    str(TRAJ_POLICY),
                    str(PASS_TRACE),
                    str(FAIL_TRACE),
                    "--json-out",
                    str(cmp_json),
                    "--md-out",
                    str(cmp_md),
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("GATE: FAIL", output)
            doc = json.loads(cmp_json.read_text(encoding="utf-8"))
            self.assertFalse(doc["gate"]["passed"])
            self.assertEqual(doc["summary"]["traces_added"], 1)
            md = cmp_md.read_text(encoding="utf-8")
            self.assertIn("**Gate: FAIL**", md)

    def test_compare_with_candidate_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline.json"
            candidate = Path(tmp) / "candidate.json"
            run_cli(
                ["validate", "--policy", str(TRAJ_POLICY), str(PASS_TRACE),
                 "--json-out", str(baseline), "--quiet"]
            )
            run_cli(
                ["validate", "--policy", str(TRAJ_POLICY), str(FAIL_TRACE),
                 "--json-out", str(candidate), "--quiet"]
            )
            code, output = run_cli(
                ["compare", "--baseline", str(baseline), "--candidate", str(candidate)]
            )
            self.assertEqual(code, 1)
            self.assertIn("GATE: FAIL", output)

    def test_compare_fail_on_never_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline.json"
            run_cli(
                ["validate", "--policy", str(TRAJ_POLICY), str(PASS_TRACE),
                 "--json-out", str(baseline), "--quiet"]
            )
            code, _ = run_cli(
                [
                    "compare", "--baseline", str(baseline),
                    "--policy", str(TRAJ_POLICY), str(FAIL_TRACE),
                    "--fail-on", "never", "--quiet",
                ]
            )
            self.assertEqual(code, 0)

    def test_compare_candidate_json_out_becomes_next_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline.json"
            next_baseline = Path(tmp) / "next.json"
            run_cli(
                ["validate", "--policy", str(TRAJ_POLICY), str(PASS_TRACE),
                 "--json-out", str(baseline), "--quiet"]
            )
            run_cli(
                [
                    "compare", "--baseline", str(baseline),
                    "--policy", str(TRAJ_POLICY), str(PASS_TRACE),
                    "--candidate-json-out", str(next_baseline), "--quiet",
                ]
            )
            doc = json.loads(next_baseline.read_text(encoding="utf-8"))
            self.assertIn("reports", doc)

    def test_compare_usage_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline.json"
            run_cli(
                ["validate", "--policy", str(TRAJ_POLICY), str(PASS_TRACE),
                 "--json-out", str(baseline), "--quiet"]
            )
            with self.assertRaises(SystemExit):
                run_cli(["compare", "--baseline", str(baseline)])
            with self.assertRaises(SystemExit):
                run_cli(["compare", "--baseline", str(baseline), str(PASS_TRACE)])
            with self.assertRaises(SystemExit):
                run_cli(
                    ["compare", "--baseline", str(baseline), "--candidate",
                     str(baseline), "--policy", str(TRAJ_POLICY), str(PASS_TRACE)]
                )

    def test_compare_rejects_non_report_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            bogus = Path(tmp) / "bogus.json"
            bogus.write_text('{"not": "a report"}', encoding="utf-8")
            with self.assertRaises(SystemExit):
                run_cli(
                    ["compare", "--baseline", str(bogus), "--policy",
                     str(TRAJ_POLICY), str(PASS_TRACE)]
                )


class TestDeterministicOutputs(unittest.TestCase):
    def test_repeat_runs_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            outputs = []
            for run_index in range(2):
                json_out = Path(tmp) / f"r{run_index}.json"
                md_out = Path(tmp) / f"r{run_index}.md"
                junit_out = Path(tmp) / f"r{run_index}.xml"
                sarif_out = Path(tmp) / f"r{run_index}.sarif"
                run_cli(
                    [
                        "validate", "--policy", str(TRAJ_POLICY),
                        str(PASS_TRACE), str(FAIL_TRACE),
                        "--json-out", str(json_out), "--md-out", str(md_out),
                        "--junit-out", str(junit_out), "--sarif-out", str(sarif_out),
                        "--quiet",
                    ]
                )
                outputs.append(
                    tuple(
                        p.read_bytes() for p in (json_out, md_out, junit_out, sarif_out)
                    )
                )
            self.assertEqual(outputs[0], outputs[1])


if __name__ == "__main__":
    unittest.main()
