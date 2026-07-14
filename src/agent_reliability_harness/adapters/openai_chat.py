"""Adapter for OpenAI Chat Completions message lists.

Maps an OpenAI-style conversation transcript into a canonical ARH trace:

- each entry of an assistant message's ``tool_calls`` becomes a
  ``tool_call`` step (arguments JSON-decoded from ``function.arguments``);
- legacy single ``function_call`` fields are mapped the same way;
- ``role: "tool"`` messages attach their ``content`` as the ``output`` of
  the matching tool_call step (via ``tool_call_id``);
- non-empty assistant text ``content`` becomes a ``model_response`` step;
- ``system`` and ``user`` messages are skipped: they are inputs to the
  agent, not agent behavior. (Policy safety checks scan agent-produced
  content; if you need to scan user input, include it in the canonical
  format directly.)

Not carried by this format (documented, not guessed): latency, cost, token
usage per message, citations, and step status (the Chat Completions
transcript has no error channel for tool results, so ``status`` is always
``"ok"``). Unparseable ``function.arguments`` and orphan tool results are
recorded under ``metadata.adapter`` instead of being dropped.
"""

from __future__ import annotations

import json
from typing import Any

SOURCE = "openai-chat"


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
    step: dict[str, Any] = {
        "step_id": step_id,
        "type": "tool_call",
        "tool_name": name,
        "arguments": arguments,
    }
    return step


def to_trace_dict(raw: Any, fallback_trace_id: str) -> dict[str, Any]:
    if isinstance(raw, list):
        wrapper: dict[str, Any] = {"messages": raw}
    elif isinstance(raw, dict):
        wrapper = raw
    else:
        raise ValueError(
            f"openai-chat input must be an object with 'messages' or a message list, "
            f"got {type(raw).__name__}"
        )
    messages = wrapper.get("messages")
    if not isinstance(messages, list):
        raise ValueError("openai-chat input has no 'messages' list")

    steps: list[dict[str, Any]] = []
    step_by_call_id: dict[str, dict[str, Any]] = {}
    adapter_notes: list[dict[str, Any]] = []

    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            adapter_notes.append({"issue": "non_object_message", "message_index": index})
            continue
        role = message.get("role")
        if role == "assistant":
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
            function_call = message.get("function_call")
            if isinstance(function_call, dict):
                step_id = f"m{index}-function"
                step = _tool_call_step(function_call, step_id, adapter_notes)
                steps.append(step)
                step_by_call_id[step_id] = step
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                steps.append(
                    {
                        "step_id": f"m{index}-response",
                        "type": "model_response",
                        "text": content,
                    }
                )
        elif role == "tool":
            call_id = message.get("tool_call_id")
            target = step_by_call_id.get(str(call_id)) if call_id is not None else None
            content = message.get("content")
            if target is None:
                adapter_notes.append(
                    {
                        "issue": "unmatched_tool_result",
                        "message_index": index,
                        "tool_call_id": call_id,
                    }
                )
            else:
                target["output"] = content
        # system/user/developer messages: agent inputs, intentionally skipped.

    trace: dict[str, Any] = {
        "schema_version": "1",
        "trace_id": str(wrapper.get("trace_id") or fallback_trace_id),
        "agent_name": str(wrapper.get("agent_name") or "openai-chat-agent"),
        "workflow": str(wrapper.get("workflow") or "openai-chat-import"),
        "source": SOURCE,
        "steps": steps,
    }
    metadata = dict(wrapper.get("metadata") or {})
    if adapter_notes:
        metadata.setdefault("adapter", {})["notes"] = adapter_notes
    if metadata:
        trace["metadata"] = metadata
    return trace
