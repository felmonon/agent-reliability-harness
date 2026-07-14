"""Adapter for Cohere Chat API v2 message lists.

Maps a Cohere v2 conversation transcript (https://docs.cohere.com/reference/chat)
into a canonical ARH trace:

- an assistant message's ``tool_plan`` becomes a ``model_response`` step
  (it is model-generated text and must be visible to safety checks; the
  step's ``metadata.source_field`` marks it as a plan, not a final answer);
- each entry of an assistant message's ``tool_calls`` becomes a
  ``tool_call`` step (arguments JSON-decoded from ``function.arguments``,
  the same wire shape as OpenAI tool calls);
- ``role: "tool"`` messages attach their content as the ``output`` of the
  matching tool_call step (via ``tool_call_id``); Cohere ``document``
  content blocks are flattened to their ``document.data`` payloads;
- assistant text ``content`` (a string or ``text`` typed blocks) becomes a
  ``model_response`` step; a message-level ``citations`` list (Cohere's
  built-in citation feature) maps to that step's citations;
- ``system`` and ``user`` messages are skipped: they are inputs to the
  agent, not agent behavior.

Not carried by this format (documented, not guessed): latency, cost, token
usage per message, and step status (the transcript has no error channel for
tool results, so ``status`` is always ``"ok"``). Unparseable
``function.arguments``, orphan tool results, and malformed content blocks
are recorded under ``metadata.adapter`` instead of being dropped.
"""

from __future__ import annotations

import json
from typing import Any

SOURCE = "cohere-chat"


def _tool_call_step(
    call: dict[str, Any], step_id: str, adapter_notes: list[dict[str, Any]]
) -> dict[str, Any]:
    function = call.get("function") or {}
    name = function.get("name") or call.get("name")
    raw_arguments = function.get("arguments", call.get("arguments"))
    arguments: dict[str, Any] = {}
    if isinstance(raw_arguments, dict):
        arguments = raw_arguments
    elif isinstance(raw_arguments, str) and raw_arguments.strip():
        try:
            parsed = json.loads(raw_arguments)
            if isinstance(parsed, dict):
                arguments = parsed
            else:
                adapter_notes.append(
                    {
                        "step_id": step_id,
                        "issue": "arguments_not_object",
                        "raw_arguments": raw_arguments,
                    }
                )
        except json.JSONDecodeError as exc:
            adapter_notes.append(
                {
                    "step_id": step_id,
                    "issue": "argument_parse_error",
                    "error": str(exc),
                    "raw_arguments": raw_arguments,
                }
            )
    return {
        "step_id": step_id,
        "type": "tool_call",
        "tool_name": name,
        "arguments": arguments,
    }


def _tool_result_value(
    content: Any, message_index: int, adapter_notes: list[dict[str, Any]]
) -> Any:
    """Flatten a Cohere tool message content payload to a comparable value.

    Cohere v2 tool results are either a plain string or a list of
    ``{"type": "document", "document": {"data": ...}}`` blocks. Document
    ``data`` payloads are joined in order; malformed blocks are recorded.
    """
    if not isinstance(content, list):
        return content
    parts: list[str] = []
    for block_index, block in enumerate(content):
        if not isinstance(block, dict) or block.get("type") != "document":
            adapter_notes.append(
                {
                    "issue": "unrecognized_tool_content_block",
                    "message_index": message_index,
                    "block_index": block_index,
                }
            )
            continue
        document = block.get("document")
        data = document.get("data") if isinstance(document, dict) else None
        if isinstance(data, str):
            parts.append(data)
        else:
            adapter_notes.append(
                {
                    "issue": "document_block_missing_data",
                    "message_index": message_index,
                    "block_index": block_index,
                }
            )
    if parts:
        return "\n".join(parts)
    return content


def _assistant_text(content: Any) -> str | None:
    """Extract assistant text from a string or ``text`` typed block list."""
    if isinstance(content, str):
        return content if content.strip() else None
    if isinstance(content, list):
        texts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        joined = "\n".join(text for text in texts if isinstance(text, str) and text.strip())
        return joined if joined else None
    return None


def to_trace_dict(raw: Any, fallback_trace_id: str) -> dict[str, Any]:
    if isinstance(raw, list):
        wrapper: dict[str, Any] = {"messages": raw}
    elif isinstance(raw, dict):
        wrapper = raw
    else:
        raise ValueError(
            f"cohere-chat input must be an object with 'messages' or a message list, "
            f"got {type(raw).__name__}"
        )
    messages = wrapper.get("messages")
    if not isinstance(messages, list):
        raise ValueError("cohere-chat input has no 'messages' list")

    steps: list[dict[str, Any]] = []
    step_by_call_id: dict[str, dict[str, Any]] = {}
    adapter_notes: list[dict[str, Any]] = []

    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            adapter_notes.append({"issue": "non_object_message", "message_index": index})
            continue
        role = message.get("role")
        if role == "assistant":
            tool_plan = message.get("tool_plan")
            if isinstance(tool_plan, str) and tool_plan.strip():
                steps.append(
                    {
                        "step_id": f"m{index}-plan",
                        "type": "model_response",
                        "text": tool_plan,
                        "metadata": {"source_field": "tool_plan"},
                    }
                )
            tool_calls = message.get("tool_calls")
            if isinstance(tool_calls, list):
                for call_index, call in enumerate(tool_calls):
                    if not isinstance(call, dict):
                        adapter_notes.append(
                            {
                                "issue": "non_object_tool_call",
                                "message_index": index,
                                "tool_call_index": call_index,
                            }
                        )
                        continue
                    step_id = str(call.get("id") or f"m{index}-tool{call_index}")
                    step = _tool_call_step(call, step_id, adapter_notes)
                    steps.append(step)
                    step_by_call_id[step_id] = step
            text = _assistant_text(message.get("content"))
            if text is not None:
                step = {
                    "step_id": f"m{index}-response",
                    "type": "model_response",
                    "text": text,
                }
                citations = message.get("citations")
                if isinstance(citations, list) and citations:
                    step["citations"] = [c for c in citations if isinstance(c, dict)]
                steps.append(step)
        elif role == "tool":
            call_id = message.get("tool_call_id")
            target = step_by_call_id.get(str(call_id)) if call_id is not None else None
            if target is None:
                adapter_notes.append(
                    {
                        "issue": "unmatched_tool_result",
                        "message_index": index,
                        "tool_call_id": call_id,
                    }
                )
            else:
                target["output"] = _tool_result_value(
                    message.get("content"), index, adapter_notes
                )
        # system/user messages: agent inputs, intentionally skipped.

    trace: dict[str, Any] = {
        "schema_version": "1",
        "trace_id": str(wrapper.get("trace_id") or fallback_trace_id),
        "agent_name": str(wrapper.get("agent_name") or "cohere-chat-agent"),
        "workflow": str(wrapper.get("workflow") or "cohere-chat-import"),
        "source": SOURCE,
        "steps": steps,
    }
    metadata = dict(wrapper.get("metadata") or {})
    if adapter_notes:
        metadata.setdefault("adapter", {})["notes"] = adapter_notes
    if metadata:
        trace["metadata"] = metadata
    return trace
