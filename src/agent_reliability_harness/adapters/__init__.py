"""Provider adapters: convert provider-native transcripts into canonical traces.

Adapters are pure, deterministic functions from a provider-native JSON
document to a canonical ARH trace ``dict`` (see TRACE-SPEC.md). They never
call a network, never read a clock, and never drop information silently:
anything an adapter cannot map is recorded under
``trace["metadata"]["adapter"]`` so the loss is visible.

Supported formats:

- ``arh``: the canonical trace format (no conversion).
- ``openai-chat``: an OpenAI Chat Completions message list with
  ``tool_calls`` / ``role: "tool"`` messages.
- ``anthropic-messages``: an Anthropic Messages API conversation with
  ``tool_use`` / ``tool_result`` content blocks.

Fields the source format does not carry (see docs/adapters.md for the full
support matrix) are left unset, which automatically marks the dependent
policy checks (e.g. latency budgets) as not applicable instead of silently
passing them.
"""

from __future__ import annotations

from typing import Any, Callable

from agent_reliability_harness.adapters import anthropic_messages, openai_chat

FORMAT_ARH = "arh"
FORMAT_OPENAI_CHAT = "openai-chat"
FORMAT_ANTHROPIC_MESSAGES = "anthropic-messages"
FORMAT_AUTO = "auto"

FORMATS = (FORMAT_ARH, FORMAT_OPENAI_CHAT, FORMAT_ANTHROPIC_MESSAGES)

_ADAPTERS: dict[str, Callable[[Any, str], dict[str, Any]]] = {
    FORMAT_OPENAI_CHAT: openai_chat.to_trace_dict,
    FORMAT_ANTHROPIC_MESSAGES: anthropic_messages.to_trace_dict,
}


def detect_format(raw: Any) -> str:
    """Deterministically detect the trace format of a parsed JSON document.

    Detection rules, applied in order:

    1. An object with a ``steps`` list is the canonical ``arh`` format.
    2. An object with a ``messages`` list (or a bare message list) is
       inspected message by message:
       a. any ``role: "assistant"`` message with ``tool_calls`` or
          ``function_call``, or any ``role: "tool"`` message -> ``openai-chat``;
       b. any message whose ``content`` is a list containing ``tool_use`` /
          ``tool_result`` typed blocks -> ``anthropic-messages``.
    3. A plain-text-only message list defaults to ``openai-chat`` (both
       vendors' text-only transcripts are structurally identical; the
       resulting canonical trace is the same either way).

    Raises ``ValueError`` for anything else.
    """
    if isinstance(raw, dict) and isinstance(raw.get("steps"), list):
        return FORMAT_ARH
    messages: Any = None
    if isinstance(raw, dict) and isinstance(raw.get("messages"), list):
        messages = raw["messages"]
    elif isinstance(raw, list):
        messages = raw
    if messages is None:
        raise ValueError(
            "cannot detect trace format: expected an object with 'steps' (arh), "
            "an object with 'messages', or a bare message list"
        )
    for message in messages:
        if not isinstance(message, dict):
            continue
        if message.get("role") == "tool" or "tool_calls" in message or "function_call" in message:
            return FORMAT_OPENAI_CHAT
        content = message.get("content")
        if isinstance(content, list) and any(
            isinstance(block, dict) and block.get("type") in ("tool_use", "tool_result")
            for block in content
        ):
            return FORMAT_ANTHROPIC_MESSAGES
    return FORMAT_OPENAI_CHAT


def normalize(raw: Any, fmt: str, fallback_trace_id: str) -> dict[str, Any]:
    """Convert a provider-native document into a canonical trace dict.

    ``fmt`` may be a concrete format name or ``"auto"`` for detection.
    ``fallback_trace_id`` is used when the source document carries no trace
    identifier (typically the source file stem).
    """
    if fmt == FORMAT_AUTO:
        fmt = detect_format(raw)
    if fmt == FORMAT_ARH:
        if not isinstance(raw, dict):
            raise ValueError("arh-format trace must be a JSON object")
        return raw
    adapter = _ADAPTERS.get(fmt)
    if adapter is None:
        raise ValueError(f"unknown trace format '{fmt}' (expected one of {FORMATS})")
    return adapter(raw, fallback_trace_id)
