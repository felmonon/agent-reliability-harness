"""Tests for v1 argument value constraints (enum/pattern/range) and token budgets."""

import unittest

from agent_reliability_harness.models import ArgSpec, Policy, Trace
from agent_reliability_harness.validator import validate_trace


def make_trace(args, tokens=None):
    step = {
        "step_id": "s1",
        "type": "tool_call",
        "tool_name": "create_ticket",
        "arguments": args,
    }
    steps = [step]
    if tokens is not None:
        steps.append(
            {
                "step_id": "s2",
                "type": "model_response",
                "text": "ok",
                "input_tokens": tokens[0],
                "output_tokens": tokens[1],
            }
        )
    return Trace.from_dict(
        {"trace_id": "t", "agent_name": "a", "workflow": "wf", "steps": steps}
    )


def make_policy(spec, budgets=None):
    raw = {
        "policy_id": "p",
        "allowed_tools": {"create_ticket": {"required_arguments": {"priority": spec}}},
    }
    if budgets:
        raw["budgets"] = budgets
    return Policy.from_dict(raw)


def rule_ids(report, severity="error"):
    return sorted(f.rule_id for f in report.findings if f.severity == severity)


class TestEnum(unittest.TestCase):
    def test_enum_violation(self):
        policy = make_policy({"type": "str", "enum": ["low", "high"]})
        report = validate_trace(make_trace({"priority": "urgent"}), policy)
        self.assertEqual(rule_ids(report), ["ARH-SCH-007"])

    def test_enum_ok(self):
        policy = make_policy({"type": "str", "enum": ["low", "high"]})
        report = validate_trace(make_trace({"priority": "high"}), policy)
        self.assertEqual(rule_ids(report), [])


class TestPattern(unittest.TestCase):
    def test_pattern_violation(self):
        policy = make_policy({"type": "str", "pattern": "P[0-9]"})
        report = validate_trace(make_trace({"priority": "critical"}), policy)
        self.assertEqual(rule_ids(report), ["ARH-SCH-008"])

    def test_pattern_is_fullmatch(self):
        policy = make_policy({"type": "str", "pattern": "P[0-9]"})
        # substring match must NOT be enough
        report = validate_trace(make_trace({"priority": "xP1x"}), policy)
        self.assertEqual(rule_ids(report), ["ARH-SCH-008"])

    def test_pattern_ok(self):
        policy = make_policy({"type": "str", "pattern": "P[0-9]"})
        report = validate_trace(make_trace({"priority": "P2"}), policy)
        self.assertEqual(rule_ids(report), [])


class TestRange(unittest.TestCase):
    def test_below_min(self):
        policy = make_policy({"type": "int", "min": 1, "max": 5})
        report = validate_trace(make_trace({"priority": 0}), policy)
        self.assertEqual(rule_ids(report), ["ARH-SCH-009"])

    def test_above_max(self):
        policy = make_policy({"type": "int", "min": 1, "max": 5})
        report = validate_trace(make_trace({"priority": 9}), policy)
        self.assertEqual(rule_ids(report), ["ARH-SCH-009"])

    def test_in_range(self):
        policy = make_policy({"type": "int", "min": 1, "max": 5})
        report = validate_trace(make_trace({"priority": 3}), policy)
        self.assertEqual(rule_ids(report), [])

    def test_wrong_type_reported_before_constraints(self):
        policy = make_policy({"type": "int", "min": 1})
        report = validate_trace(make_trace({"priority": "one"}), policy)
        self.assertEqual(rule_ids(report), ["ARH-SCH-004"])


class TestLegacyStringSpec(unittest.TestCase):
    def test_legacy_type_string_still_works(self):
        policy = make_policy("str")
        report = validate_trace(make_trace({"priority": "high"}), policy)
        self.assertEqual(rule_ids(report), [])
        report = validate_trace(make_trace({"priority": 3}), policy)
        self.assertEqual(rule_ids(report), ["ARH-SCH-004"])

    def test_argspec_from_raw_rejects_garbage(self):
        with self.assertRaises(ValueError):
            ArgSpec.from_raw(42, "tool.arg")
        with self.assertRaises(ValueError):
            ArgSpec.from_raw({"enum": "not-a-list"}, "tool.arg")
        with self.assertRaises(ValueError):
            ArgSpec.from_raw({"pattern": 5}, "tool.arg")
        with self.assertRaises(ValueError):
            ArgSpec.from_raw({"min": "low"}, "tool.arg")


class TestTokenBudget(unittest.TestCase):
    def test_token_budget_exceeded(self):
        policy = make_policy("str", budgets={"max_total_tokens": 100})
        report = validate_trace(
            make_trace({"priority": "high"}, tokens=(90, 20)), policy
        )
        self.assertIn("ARH-BUD-004", rule_ids(report))
        self.assertEqual(report.total_tokens, 110)

    def test_token_budget_ok(self):
        policy = make_policy("str", budgets={"max_total_tokens": 200})
        report = validate_trace(
            make_trace({"priority": "high"}, tokens=(90, 20)), policy
        )
        self.assertEqual(rule_ids(report), [])

    def test_token_budget_without_data_warns_not_silently_passes(self):
        policy = make_policy("str", budgets={"max_total_tokens": 100})
        report = validate_trace(make_trace({"priority": "high"}), policy)
        warnings = [f.rule_id for f in report.findings if f.severity == "warning"]
        self.assertIn("ARH-BUD-005", warnings)
        self.assertIsNone(report.total_tokens)


class TestCitationValidity(unittest.TestCase):
    def _policy(self):
        return Policy.from_dict(
            {
                "policy_id": "p",
                "grounding": {
                    "require_citations": True,
                    "min_citation_coverage": 1.0,
                    "require_valid_citation_urls": True,
                },
            }
        )

    def _trace(self, citations):
        return Trace.from_dict(
            {
                "trace_id": "t",
                "agent_name": "a",
                "workflow": "wf",
                "steps": [
                    {
                        "step_id": "s1",
                        "type": "model_response",
                        "text": "fact",
                        "requires_grounding": True,
                        "citations": citations,
                    }
                ],
            }
        )

    def test_invalid_url_flagged(self):
        report = validate_trace(self._trace([{"url": "notaurl"}]), self._policy())
        self.assertIn(
            "ARH-GRD-003", [f.rule_id for f in report.findings if f.severity == "error"]
        )

    def test_javascript_scheme_rejected(self):
        report = validate_trace(
            self._trace([{"url": "javascript:alert(1)"}]), self._policy()
        )
        self.assertIn("ARH-GRD-003", [f.rule_id for f in report.findings])

    def test_empty_source_rejected(self):
        report = validate_trace(self._trace([{"source": "  "}]), self._policy())
        self.assertIn("ARH-GRD-003", [f.rule_id for f in report.findings])

    def test_valid_url_ok(self):
        report = validate_trace(
            self._trace([{"url": "https://example.com/doc"}]), self._policy()
        )
        self.assertEqual([f for f in report.findings if f.severity == "error"], [])

    def test_valid_source_ok(self):
        report = validate_trace(
            self._trace([{"source": "crm_lookup:s1"}]), self._policy()
        )
        self.assertEqual([f for f in report.findings if f.severity == "error"], [])

    def test_non_dict_citation_rejected(self):
        report = validate_trace(self._trace(["just-a-string"]), self._policy())
        self.assertIn("ARH-GRD-003", [f.rule_id for f in report.findings])


if __name__ == "__main__":
    unittest.main()
