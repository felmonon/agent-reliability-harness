"""Adapter for Anthropic Messages API conversations.

Maps an Anthropic-style conversation (list of messages whose ``content`` is
a string or a list of typed blocks) into a canonical ARH trace:

- assistant ``tool_use`` blocks become ``tool_call`` steps (``input`` maps
  to ``arguments``);
- user ``tool_result`` blocks attach their content as the ``output`` of the
  matching tool_call step (via ``tool_use_id``); ``is_error: true`` sets the
  step's ``status`` to ``"error"`` and records the result text as ``error``;
- assistant ``text`` blocks become ``model_response`` steps; a block's
  ``citations`` list (Anthropic citations feature) maps to step citations;
- the top-level ``system`` prompt and user text content are skipped: they
  are inputs to the agent, not agent behavior.

Not carried by this format (documented, not guessed): latency, cost, and
per-message token usage (transcripts do not embed ``usage``). Orphan tool
results are recorded under ``metadata.adapter`` instead of being dropped.
"""

from __future__ import annotations

from typing import Any

SOURCE = "anthropic-messages"


def _result_text(content: Any) -> Any:
    """Flatten a tool_result content payload to a comparable value."""
    if isinstance(content, list):
        texts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        if texts:
            return "\n".join(texts)
    return content


def to_trace_dict(raw: Any, fallback_trace_id: str) -> dict[str, Any]:
    if isinstance(raw, list):
        wrapper: dict[str, Any] = {"messages": raw}
    elif isinstance(raw, dict):
        wrapper = raw
    else:
        raise ValueError(
            f"anthropic-messages input must be an object with 'messages' or a message "
            f"list, got {type(raw).__name__}"
        )
    messages = wrapper.get("messages")
    if not isinstance(messages, list):
        raise ValueError("anthropic-messages input has no 'messages' list")

    steps: list[dict[str, Any]] = []
    step_by_use_id: dict[str, dict[str, Any]] = {}
    adapter_notes: list[dict[str, Any]] = []

    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            adapter_notes.append({"issue": "non_object_message", "message_index": index})
            continue
        role = message.get("role")
        content = message.get("content")
        if role == "assistant":
            if isinstance(content, str):
                if content.strip():
                    steps.append(
                        {
                            "step_id": f"m{index}-text0",
                            "type": "model_response",
                            "text": content,
                        }
                    )
                continue
            if not isinstance(content, list):
                continue
            for block_index, block in enumerate(content):
                if not isinstance(block, dict):
                    adapter_notes.append(
                        {
                            "issue": "non_object_block",
                            "message_index": index,
                            "block_index": block_index,
                        }
                    )
                    continue
                block_type = block.get("type")
                if block_type == "tool_use":
                    step_id = str(block.get("id") or f"m{index}-tool{block_index}")
                    arguments = block.get("input")
                    step: dict[str, Any] = {
                        "step_id": step_id,
                        "type": "tool_call",
                        "tool_name": block.get("name"),
                        "arguments": arguments if isinstance(arguments, dict) else {},
                    }
                    if not isinstance(arguments, dict) and arguments is not None:
                        adapter_notes.append(
                            {
                                "step_id": step_id,
                                "issue": "arguments_not_object",
                                "raw_input": arguments,
                            }
                        )
                    steps.append(step)
                    step_by_use_id[step_id] = step
                elif block_type == "text":
                    text = block.get("text")
                    if isinstance(text, str) and text.strip():
                        step = {
                            "step_id": f"m{index}-text{block_index}",
                            "type": "model_response",
                            "text": text,
                        }
                        citations = block.get("citations")
                        if isinstance(citations, list) and citations:
                            step["citations"] = [
                                c for c in citations if isinstance(c, dict)
                            ]
                        steps.append(step)
        elif role == "user":
            if not isinstance(content, list):
                continue  # plain user text: agent input, skipped
            for block_index, block in enumerate(content):
                if not isinstance(block, dict) or block.get("type") != "tool_result":
                    continue
                use_id = block.get("tool_use_id")
                target = step_by_use_id.get(str(use_id)) if use_id is not None else None
                if target is None:
                    adapter_notes.append(
                        {
                            "issue": "unmatched_tool_result",
                            "message_index": index,
                            "tool_use_id": use_id,
                        }
                    )
                    continue
                result = _result_text(block.get("content"))
                target["output"] = result
                if block.get("is_error") is True:
                    target["status"] = "error"
                    target["error"] = result if isinstance(result, str) else "tool error"

    trace: dict[str, Any] = {
        "schema_version": "1",
        "trace_id": str(wrapper.get("trace_id") or fallback_trace_id),
        "agent_name": str(wrapper.get("agent_name") or "anthropic-agent"),
        "workflow": str(wrapper.get("workflow") or "anthropic-messages-import"),
        "source": SOURCE,
        "steps": steps,
    }
    metadata = dict(wrapper.get("metadata") or {})
    if adapter_notes:
        metadata.setdefault("adapter", {})["notes"] = adapter_notes
    if metadata:
        trace["metadata"] = metadata
    return trace
