# ARH Trace Specification (schema version 1)

Normative specification of the canonical trace format consumed by the
validator. Machine-readable schema: `schemas/trace.schema.json`
(JSON Schema draft 2020-12). Parser: `Trace.from_dict` / `Step.from_dict` in
`src/agent_reliability_harness/models.py`.

## Versioning

- `schema_version` (string, optional). **Missing means `"1"`.** The v0.1.x
  format is a strict subset of v1, so pre-versioning files parse unchanged and
  need no migration.
- Only the major version (text before the first `.`) is interpreted. An unknown
  major is rejected at parse time with:
  `trace declares unsupported schema_version 'X' (this build supports major version '1')`.
- v1 evolution is additive-only. A future incompatible change bumps the major
  version and ships a documented migration (COMPATIBILITY.md).

## Trace object

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `schema_version` | string | no | `"1"` | See Versioning. |
| `trace_id` | string | **yes** | — | Stable identifier; the regression fingerprint key. Must be unique within a report (duplicates rejected by `arh compare`). |
| `agent_name` | string | **yes** | — | Descriptive label. |
| `workflow` | string | **yes** | — | Workflow/task label (JUnit classname uses `agent_name.workflow`). |
| `steps` | array of Step | **yes** | — | Execution-ordered list (see Ordering). |
| `source` | string | no | absent | Provenance, e.g. `"openai-chat"` when produced by an adapter. |
| `metadata` | object | no | `{}` | Free-form extension point. Adapters record unmappable input under `metadata.adapter.notes`. Unknown top-level keys are permitted and ignored. |

## Step object

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `step_id` | string | **yes** | — | Identifier; see Stable identifiers. |
| `type` | `"tool_call"` \| `"model_response"` | **yes** | — | Anything else is rejected with a step-precise error. |
| `tool_name` | string \| null | no | null | Tool invoked (tool_call). A tool_call without one raises finding ARH-SCH-002. |
| `arguments` | object \| null | no | null | Tool-call arguments. Must be an object when present. |
| `text` | string \| null | no | null | Response text (model_response). |
| `citations` | array of object | no | `[]` | Each citation should carry a non-empty `source` and/or a valid http(s) `url` (checked when the policy sets `require_valid_citation_urls`). |
| `latency_ms` | number ≥ 0 \| null | no | null | Recorded step latency. Absent latency ⇒ the step is skipped by per-step latency checks and contributes 0 to the total. |
| `cost_usd` | number ≥ 0 \| null | no | null | Recorded step cost. |
| `requires_grounding` | boolean | no | false | Marks a model_response that must carry citations. |
| `output` | any | no | null | Tool result. String values and string values of dict outputs are scanned by safety patterns. |
| `status` | `"ok"` \| `"error"` | no | see below | Step outcome. |
| `error` | string \| null | no | null | Error description. |
| `input_tokens` / `output_tokens` | integer ≥ 0 \| null | no | null | Token usage; negative or non-numeric values are rejected. |
| `metadata` | object | no | `{}` | Free-form extension point. |

### Status / error semantics

If `status` is absent, it defaults to `"error"` when a non-empty `error` field
is present, otherwise `"ok"`. An explicit `status` outside `{"ok","error"}` is
rejected at parse time. `status: "error"` drives the flow checks
(ARH-FLW-001 retry requirement; an errored earlier side-effect call permits a
retry without a duplicate finding) and disqualifies a final response
(ARH-CMP-001).

## Ordering semantics

`steps` is the agent's execution order. All positional rules use list position:

- `sequence.call_order` compares the positions of the **first** call of each
  listed tool;
- retry checks look for a same-tool call **later** in the list;
- duplicate-side-effect checks flag identical calls **after** the first
  successful one;
- completion checks inspect the **last** step.

## Stable identifiers

`step_id` should be unique within a trace: findings, SARIF logical locations,
and regression fingerprints all point at step IDs. Duplicate IDs are not a
parse error (real exporters emit them) but raise the lint finding
**ARH-SCH-010** (warning) because they weaken finding locations.

## Deterministic normalization

Parsing is pure: no clocks, no environment, no randomness. Argument identity
(for retry-storm and duplicate-side-effect grouping) is the canonical JSON
serialization with sorted keys, so key order never affects results
(verified by the benchmark's metamorphic invariance checks).

## Examples

Minimal v0.1.x-compatible trace (still valid v1):

```json
{
  "trace_id": "lead-qualification-0001",
  "agent_name": "sales-ops-copilot",
  "workflow": "lead-qualification",
  "steps": [
    {
      "step_id": "s1",
      "type": "tool_call",
      "tool_name": "lookup_account",
      "arguments": { "account_id": "acct_demo_42" },
      "latency_ms": 240,
      "cost_usd": 0.001
    }
  ]
}
```

v1 trace using the additive fields:

```json
{
  "schema_version": "1",
  "trace_id": "refund-workflow-1001",
  "agent_name": "refund-copilot",
  "workflow": "refund",
  "source": "openai-chat",
  "steps": [
    {
      "step_id": "call_lookup1",
      "type": "tool_call",
      "tool_name": "lookup_order",
      "arguments": { "order_id": "ORD-1042" },
      "status": "error",
      "error": "upstream timeout",
      "latency_ms": 1800,
      "input_tokens": 150,
      "output_tokens": 0
    },
    {
      "step_id": "s2",
      "type": "model_response",
      "text": "The order service is unavailable; I will retry.",
      "metadata": { "model": "example-model-1" }
    }
  ]
}
```

Complete runnable examples: `samples/traces/`.
