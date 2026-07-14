"""Golden compatibility tests: v0.1.x sample inputs must produce identical
scores, pass/fail decisions, and finding messages under this version.

These pins are the backward-compatibility contract for the 0.2.0 release.
If one of these tests fails, either a compatibility break was introduced
(fix it) or a deliberate, documented break was made (update COMPATIBILITY.md
and the changelog first, then this test).
"""

import unittest
from pathlib import Path

import json

from agent_reliability_harness.models import Policy, Trace
from agent_reliability_harness.validator import validate_trace

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLES = REPO_ROOT / "samples"

#: (trace file, expected score, expected passed) as produced by v0.1.0.
GOLDEN = [
    ("lead_qualification_pass.json", 100.0, True),
    ("renewal_workflow_budget_violation.json", 80.0, False),
    ("support_escalation_unsafe.json", 70.0, False),
]


class TestGoldenSamples(unittest.TestCase):
    def setUp(self):
        raw = json.loads((SAMPLES / "policy.json").read_text(encoding="utf-8"))
        self.policy = Policy.from_dict(raw)

    def test_sample_scores_and_verdicts_unchanged(self):
        for filename, expected_score, expected_passed in GOLDEN:
            with self.subTest(trace=filename):
                raw = json.loads(
                    (SAMPLES / "traces" / filename).read_text(encoding="utf-8")
                )
                report = validate_trace(Trace.from_dict(raw), self.policy)
                self.assertAlmostEqual(report.score, expected_score, places=2)
                self.assertEqual(report.passed, expected_passed)

    def test_finding_messages_stable_for_unsafe_sample(self):
        raw = json.loads(
            (SAMPLES / "traces" / "support_escalation_unsafe.json").read_text(
                encoding="utf-8"
            )
        )
        report = validate_trace(Trace.from_dict(raw), self.policy)
        messages = "\n".join(f.message for f in report.findings)
        self.assertIn("not in the allowed_tools policy", messages)
        self.assertIn("disallowed pattern", messages)
        self.assertIn("no citations", messages)

    def test_every_builtin_finding_has_a_registered_rule_id(self):
        from agent_reliability_harness.rules import RULES

        for filename, _, _ in GOLDEN:
            raw = json.loads(
                (SAMPLES / "traces" / filename).read_text(encoding="utf-8")
            )
            report = validate_trace(Trace.from_dict(raw), self.policy)
            for finding in report.findings:
                self.assertIn(finding.rule_id, RULES, finding.message)


if __name__ == "__main__":
    unittest.main()
