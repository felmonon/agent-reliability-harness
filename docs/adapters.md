# Adapters

Adapters convert provider-native transcripts into the canonical trace format
([TRACE-SPEC.md](../TRACE-SPEC.md)). They are pure functions: deterministic,
no network, and they never drop information silently — anything unmappable is
recorded under `trace.metadata.adapter.notes`.

## Format detection (`--format auto`, the default)

Applied in order:

1. JSON object with a `steps` list → `arh` (canonical, no conversion).
2. Object with a `messages` list (or a bare message list) is first scanned in
   full for Cohere-only markers → `cohere-chat`. Cohere shares the
   `tool_calls` / `role: "tool"` wire shape with OpenAI, so this scan must
   run before the per-message rules below. Markers: `tool_plan` on an
   assistant message, an assistant message-level `citations` list, or
   `document` typed tool-result content blocks.
3. Otherwise, message by message:
   - any assistant message with `tool_calls` or `function_call`, or any
     `role: "tool"` message → `openai-chat`;
   - any message whose `content` is a block list containing `tool_use` /
     `tool_result` → `anthropic-messages`.
4. Text-only message lists default to `openai-chat` (all three vendors'
   text-only transcripts normalize identically).
5. Anything else: `error: ... cannot detect trace format`.

Force a format with `--format openai-chat`, `--format anthropic-messages`,
or `--format cohere-chat`.

## openai-chat

Input: an OpenAI Chat Completions message list (`{"messages": [...]}` or a
bare list).

| Transcript element | Canonical mapping |
|---|---|
| assistant `tool_calls[i]` | `tool_call` step; `step_id` = call id; `function.arguments` JSON-decoded into `arguments` |
| legacy `function_call` | `tool_call` step (`step_id` = `m<i>-function`) |
| `role: "tool"` message | `output` of the matching step via `tool_call_id` |
| assistant text `content` | `model_response` step |
| `system` / `user` messages | skipped (agent inputs, not agent behavior) |

**Cannot carry** (left unset → dependent checks become *not applicable*, they
do not silently pass): `latency_ms`, `cost_usd`, token counts, citations, and
step `status` — the format has no error channel for tool results, so status is
always `"ok"` (flow rules that need error status won't trigger on this format).

Edge handling: unparseable `function.arguments` → empty `arguments` plus an
`argument_parse_error` note (missing-argument findings will fire); orphan tool
results and non-object messages → recorded as notes.

## anthropic-messages

Input: an Anthropic Messages conversation (`{"messages": [...]}`), content as
strings or typed block lists.

| Transcript element | Canonical mapping |
|---|---|
| assistant `tool_use` block | `tool_call` step; `step_id` = block id; `input` → `arguments` |
| user `tool_result` block | `output` of the matching step via `tool_use_id` |
| `tool_result` with `is_error: true` | step `status` = `"error"`, result text → `error` |
| assistant `text` block | `model_response` step; block `citations` → step citations |
| top-level `system`, user text | skipped |

**Cannot carry**: `latency_ms`, `cost_usd`, token counts (transcripts don't
embed `usage`). It *does* carry tool errors via `is_error`, so
`error_handling` rules work on this format.

## cohere-chat

Input: a Cohere Chat API v2 message list (`{"messages": [...]}` or a bare
list), per [Cohere's tool use docs](https://docs.cohere.com/docs/tool-use-overview).

| Transcript element | Canonical mapping |
|---|---|
| assistant `tool_plan` | `model_response` step (`step_id` = `m<i>-plan`, `metadata.source_field` = `"tool_plan"`) — model-generated text stays visible to safety checks |
| assistant `tool_calls[i]` | `tool_call` step; `step_id` = call id; `function.arguments` JSON-decoded into `arguments` (same wire shape as OpenAI) |
| `role: "tool"` message | `output` of the matching step via `tool_call_id`; `document` content blocks are flattened to their `document.data` payloads joined in order |
| assistant text `content` (string or `text` blocks) | `model_response` step |
| assistant message-level `citations` | citations on that message's `model_response` step (passed through as-is) |
| `system` / `user` messages | skipped (agent inputs, not agent behavior) |

**Cannot carry** (left unset → dependent checks become *not applicable*):
`latency_ms`, `cost_usd`, token counts, and step `status` — the transcript
has no error channel for tool results, so status is always `"ok"`.

Edge handling: unparseable `function.arguments` → empty `arguments` plus an
`argument_parse_error` note; orphan tool results, non-object messages,
non-`document` tool content blocks, and `document` blocks without string
`data` → recorded as notes. Valid `document.data` payloads are still
recovered from a partially-malformed block list.

## Trace identity

Wrap transcripts to control identity — top-level keys pass through:

```json
{
  "trace_id": "prod-session-4211",
  "agent_name": "support-agent",
  "workflow": "refund",
  "messages": [ ... ]
}
```

Without a `trace_id`, the source **file stem** is used (e.g.
`session_04.json` → `session_04`). Stable trace IDs matter: regression
fingerprints start with the trace ID ([regression-testing.md](regression-testing.md)).

## Equivalence guarantee

The benchmark suite verifies that the same conversation recorded as an OpenAI
transcript and an Anthropic transcript produces identical rule verdicts under
the same policy (see BENCHMARK-RESULTS.md, "Adapter equivalence").
