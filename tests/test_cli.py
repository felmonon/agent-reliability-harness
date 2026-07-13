import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from agent_reliability_harness.cli import main

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = REPO_ROOT / "samples"
POLICY_PATH = SAMPLES_DIR / "policy.json"
PASS_TRACE = SAMPLES_DIR / "traces" / "lead_qualification_pass.json"
BUDGET_TRACE = SAMPLES_DIR / "traces" / "renewal_workflow_budget_violation.json"
UNSAFE_TRACE = SAMPLES_DIR / "traces" / "support_escalation_unsafe.json"


class TestCliValidate(unittest.TestCase):
    def test_passing_trace_exits_zero(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["validate", "--policy", str(POLICY_PATH), str(PASS_TRACE)])
        self.assertEqual(code, 0)
        self.assertIn("[PASS]", buf.getvalue())

    def test_failing_trace_exits_nonzero(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["validate", "--policy", str(POLICY_PATH), str(BUDGET_TRACE)])
        self.assertEqual(code, 1)
        self.assertIn("[FAIL]", buf.getvalue())

    def test_unsafe_trace_flagged(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["validate", "--policy", str(POLICY_PATH), str(UNSAFE_TRACE)])
        self.assertEqual(code, 1)
        output = buf.getvalue()
        self.assertIn("[safety   ]", output)
        self.assertIn("not in the allowed_tools policy", output)

    def test_batch_validate_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            json_out = Path(tmp) / "report.json"
            md_out = Path(tmp) / "report.md"
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main(
                    [
                        "validate",
                        "--policy",
                        str(POLICY_PATH),
                        str(PASS_TRACE),
                        str(BUDGET_TRACE),
                        str(UNSAFE_TRACE),
                        "--json-out",
                        str(json_out),
                        "--md-out",
                        str(md_out),
                        "--quiet",
                    ]
                )
            self.assertEqual(code, 1)
            self.assertEqual(buf.getvalue(), "")

            data = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(data["summary"]["total_traces"], 3)
            self.assertEqual(data["summary"]["passed_traces"], 1)

            md_text = md_out.read_text(encoding="utf-8")
            self.assertIn("# Agent Reliability Harness Report", md_text)

    def test_missing_policy_file_errors_cleanly(self):
        buf = io.StringIO()
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stdout(buf):
                main(["validate", "--policy", "/nonexistent/policy.json", str(PASS_TRACE)])


if __name__ == "__main__":
    unittest.main()
