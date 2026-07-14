"""Tests for provider adapters and format detection."""

import json
import unittest
from pathlib import Path

from agent_reliability_harness.adapters import (
    FORMAT_ANTHROPIC_MESSAGES,
    FORMAT_ARH,
    FORMAT_OPENAI_CHAT,
    detect_format,
    normalize,
)
from agent_reliability_harness.models import Policy, Trace
from agent_reliability_harness.validator import validate_trace

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class TestDetectFormat(unittest.TestCase):
    def test_detects_arh(self):
        raw = {"trace_id": "t", "steps": []}
        self.assertEqual(detect_format(raw), FORMAT_ARH)

    def test_detects_openai_chat(self):
        self.assertEqual(detect_format(load("openai_chat_refund.json")), FORMAT_OPENAI_CHAT)

    def test_detects_anthropic_messages(self):
        self.assertEqual(
            detect_format(load("anthropic_messages_refund.json")),
            FORMAT_ANTHROPIC_MESSAGES,
        )

    def test_detects_bare_list_openai(self):
        raw = [{"role": "assistant", "tool_calls": []}]
        self.assertEqual(detect_format(raw), FORMAT_OPENAI_CHAT)

    def test_text_only_defaults_to_openai(self):
        raw = {"messages": [{"role": "user", "content": "hi"}]}
        self.assertEqual(detect_format(raw), FORMAT_OPENAI_CHAT)

    def test_undetectable_raises(self):
        with self.assertRaises(ValueError):
            detect_format({"foo": "bar"})
        with self.assertRaises(ValueError):
            detect_format(42)


class TestOpenAIChatAdapter(unittest.TestCase):
    def test_refund_transcript_maps_fully(self):
        trace_dict = normalize(load("openai_chat_refund.json"), "openai-chat", "fb")
        trace = Trace.from_dict(trace_dict)
        self.assertEqual(trace.trace_id, "openai-refund-001")
        self.assertEqual(trace.source, "openai-chat")
        types = [(s.type, s.tool_name) for s in trace.steps]
        self.assertEqual(
            types,
            [
                ("tool_call", "lookup_order"),
                ("tool_call", "issue_refund"),
                ("model_response", None),
            ],
        )
        lookup = trace.steps[0]
        self.assertEqual(lookup.step_id, "call_lookup1")
        self.assertEqual(lookup.arguments, {"order_id": "ORD-9"})
        self.assertEqual(lookup.output, '{"status": "delivered", "amount": 42.5}')
        self.assertEqual(trace.steps[1].arguments, {"order_id": "ORD-9", "amount": 42.5})
        self.assertIn("refund of $42.50", trace.steps[2].text)

    def test_fallback_trace_id_used(self):
        trace_dict = normalize({"messages": []}, "openai-chat", "my_file")
        self.assertEqual(trace_dict["trace_id"], "my_file")

    def test_edge_cases_recorded_not_dropped(self):
        trace_dict = normalize(load("openai_chat_edge_cases.json"), "openai-chat", "fb")
        trace = Trace.from_dict(trace_dict)
        notes = trace.metadata["adapter"]["notes"]
        issues = {n["issue"] for n in notes}
        self.assertIn("argument_parse_error", issues)
        self.assertIn("unmatched_tool_result", issues)
        self.assertIn("non_object_message", issues)
        # legacy function_call became a step
        self.assertIn("legacy_fn", [s.tool_name for s in trace.steps])
        # unparseable arguments became empty dict (missing-arg findings will fire)
        bad = [s for s in trace.steps if s.step_id == "call_bad"][0]
        self.assertEqual(bad.arguments, {})

    def test_round_trip_validation(self):
        """An adapter-produced trace must be fully validatable."""
        trace_dict = normalize(load("openai_chat_refund.json"), "openai-chat", "fb")
        policy = Policy.from_dict(
            {
                "policy_id": "refund-policy",
                "allowed_tools": {
                    "lookup_order": {"required_arguments": {"order_id": "str"}},
                    "issue_refund": {
                        "required_arguments": {"order_id": "str", "amount": "float"},
                        "side_effect": True,
                    },
                },
                "sequence": {"call_order": ["lookup_order", "issue_refund"]},
                "completion": {"require_final_response": True},
            }
        )
        report = validate_trace(Trace.from_dict(trace_dict), policy)
        self.assertEqual([f for f in report.findings if f.severity == "error"], [])
        self.assertTrue(report.passed)

    def test_rejects_garbage(self):
        with self.assertRaises(ValueError):
            normalize(42, "openai-chat", "fb")
        with self.assertRaises(ValueError):
            normalize({"nope": True}, "openai-chat", "fb")


class TestAnthropicMessagesAdapter(unittest.TestCase):
    def test_refund_transcript_maps_fully(self):
        trace_dict = normalize(
            load("anthropic_messages_refund.json"), "anthropic-messages", "fb"
        )
        trace = Trace.from_dict(trace_dict)
        self.assertEqual(trace.trace_id, "anthropic-refund-001")
        self.assertEqual(trace.source, "anthropic-messages")
        types = [(s.type, s.tool_name) for s in trace.steps]
        self.assertEqual(
            types,
            [
                ("model_response", None),
                ("tool_call", "lookup_order"),
                ("tool_call", "issue_refund"),
                ("model_response", None),
            ],
        )
        lookup = [s for s in trace.steps if s.tool_name == "lookup_order"][0]
        self.assertEqual(lookup.step_id, "toolu_lookup1")
        self.assertEqual(lookup.arguments, {"order_id": "ORD-9"})
        self.assertEqual(lookup.output, "status: delivered, amount: 42.5")

    def test_is_error_maps_to_error_status(self):
        trace_dict = normalize(
            load("anthropic_messages_tool_error.json"), "anthropic-messages", "fb"
        )
        trace = Trace.from_dict(trace_dict)
        fetch = [s for s in trace.steps if s.tool_name == "fetch_page"][0]
        self.assertEqual(fetch.status, "error")
        self.assertEqual(fetch.error, "HTTP 503 upstream unavailable")

    def test_error_status_drives_flow_rules(self):
        """The adapter's error mapping must feed ARH-FLW-001 end to end."""
        trace_dict = normalize(
            load("anthropic_messages_tool_error.json"), "anthropic-messages", "fb"
        )
        policy = Policy.from_dict(
            {
                "policy_id": "p",
                "allow_unlisted_tools": True,
                "error_handling": {"require_retry_on_error": True},
            }
        )
        report = validate_trace(Trace.from_dict(trace_dict), policy)
        self.assertIn(
            "ARH-FLW-001",
            [f.rule_id for f in report.findings if f.severity == "error"],
        )

    def test_equivalent_transcripts_produce_equivalent_behavior(self):
        """The same conversation via either provider yields the same verdicts."""
        policy = Policy.from_dict(
            {
                "policy_id": "refund-policy",
                "allowed_tools": {
                    "lookup_order": {"required_arguments": {"order_id": "str"}},
                    "issue_refund": {
                        "required_arguments": {"order_id": "str", "amount": "float"},
                        "side_effect": True,
                    },
                },
                "sequence": {"call_order": ["lookup_order", "issue_refund"]},
                "completion": {"require_final_response": True},
            }
        )
        openai_trace = Trace.from_dict(
            normalize(load("openai_chat_refund.json"), "openai-chat", "fb")
        )
        anthropic_trace = Trace.from_dict(
            normalize(load("anthropic_messages_refund.json"), "anthropic-messages", "fb")
        )
        openai_report = validate_trace(openai_trace, policy)
        anthropic_report = validate_trace(anthropic_trace, policy)
        self.assertEqual(openai_report.passed, anthropic_report.passed)
        self.assertEqual(
            sorted(f.rule_id for f in openai_report.findings),
            sorted(f.rule_id for f in anthropic_report.findings),
        )

    def test_rejects_garbage(self):
        with self.assertRaises(ValueError):
            normalize("nope", "anthropic-messages", "fb")


class TestNormalizeDispatch(unittest.TestCase):
    def test_auto_dispatches(self):
        trace_dict = normalize(load("openai_chat_refund.json"), "auto", "fb")
        self.assertEqual(trace_dict["source"], "openai-chat")

    def test_arh_passthrough(self):
        raw = {"trace_id": "t", "agent_name": "a", "workflow": "w", "steps": []}
        self.assertIs(normalize(raw, "arh", "fb"), raw)

    def test_unknown_format_raises(self):
        with self.assertRaises(ValueError):
            normalize({}, "not-a-format", "fb")


if __name__ == "__main__":
    unittest.main()
