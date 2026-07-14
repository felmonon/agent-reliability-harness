# Adapters

Adapters convert provider-native transcripts into the canonical trace format
([TRACE-SPEC.md](../TRACE-SPEC.md)). They are pure functions: deterministic,
no network, and they never drop information silently — anything unmappable is
recorded under `trace.metadata.adapter.notes`.

## Format detection (`--format auto`, the default)

Applied in order:

1. JSON object with a `steps` list → `arh` (canonical, no conversion).
2. Object with a `messages` list (or a bare message list):
   - any assistant message with `tool_calls` or `function_call`, or any
     `role: "tool"` message → `openai-chat`;
   - any message whose `content` is a block list containing `tool_use` /
     `tool_result` → `anthropic-messages`.
3. Text-only message lists default to `openai-chat` (both vendors' text-only
   transcripts normalize identically).
4. Anything else: `error: ... cannot detect trace format`.

Force a format with `--format openai-chat` or `--format anthropic-messages`.

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
