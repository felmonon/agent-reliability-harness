import unittest

from agent_reliability_harness.models import Policy, Step, Trace


class TestStepFromDict(unittest.TestCase):
    def test_minimal_tool_call(self):
        step = Step.from_dict(
            {"step_id": "s1", "type": "tool_call", "tool_name": "crm_lookup", "arguments": {"account_id": "A1"}}
        )
        self.assertEqual(step.step_id, "s1")
        self.assertEqual(step.tool_name, "crm_lookup")
        self.assertEqual(step.arguments, {"account_id": "A1"})
        self.assertEqual(step.citations, [])
        self.assertFalse(step.requires_grounding)

    def test_missing_step_id_raises(self):
        with self.assertRaises(ValueError):
            Step.from_dict({"type": "tool_call"})

    def test_missing_type_raises(self):
        with self.assertRaises(ValueError):
            Step.from_dict({"step_id": "s1"})

    def test_unknown_type_raises(self):
        with self.assertRaises(ValueError):
            Step.from_dict({"step_id": "s1", "type": "bogus"})

    def test_model_response_defaults(self):
        step = Step.from_dict({"step_id": "s2", "type": "model_response", "text": "hello"})
        self.assertEqual(step.text, "hello")
        self.assertIsNone(step.tool_name)


class TestTraceFromDict(unittest.TestCase):
    def test_full_trace(self):
        raw = {
            "trace_id": "t1",
            "agent_name": "agent",
            "workflow": "wf",
            "steps": [
                {"step_id": "s1", "type": "tool_call", "tool_name": "x", "arguments": {}},
                {"step_id": "s2", "type": "model_response", "text": "hi"},
            ],
        }
        trace = Trace.from_dict(raw)
        self.assertEqual(trace.trace_id, "t1")
        self.assertEqual(len(trace.steps), 2)

    def test_missing_field_raises(self):
        with self.assertRaises(ValueError):
            Trace.from_dict({"trace_id": "t1", "agent_name": "a", "workflow": "wf"})


class TestPolicyFromDict(unittest.TestCase):
    def test_full_policy(self):
        raw = {
            "policy_id": "p1",
            "allowed_tools": {
                "crm_lookup": {"required_arguments": {"account_id": "str"}},
            },
            "budgets": {"max_total_latency_ms": 1000},
            "unsafe_patterns": ["foo"],
            "grounding": {"require_citations": True, "min_citation_coverage": 0.5},
        }
        policy = Policy.from_dict(raw)
        self.assertEqual(policy.policy_id, "p1")
        self.assertIn("crm_lookup", policy.allowed_tools)
        self.assertEqual(policy.budgets.max_total_latency_ms, 1000)
        self.assertEqual(policy.unsafe_patterns, ["foo"])
        self.assertTrue(policy.grounding.require_citations)

    def test_missing_policy_id_raises(self):
        with self.assertRaises(ValueError):
            Policy.from_dict({})

    def test_defaults_are_permissive(self):
        policy = Policy.from_dict({"policy_id": "p2"})
        self.assertEqual(policy.allowed_tools, {})
        self.assertEqual(policy.unsafe_patterns, [])
        self.assertFalse(policy.grounding.require_citations)


if __name__ == "__main__":
    unittest.main()
