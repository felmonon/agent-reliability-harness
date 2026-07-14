# Policy Cookbook

Copy-paste recipes. Every snippet is a fragment of a policy JSON file; combine
them under one `policy_id`. Normative reference: [POLICY-SPEC.md](../POLICY-SPEC.md).

## Allowlist a toolset

Any tool not listed is an error (`ARH-SCH-001`):

```json
{
  "policy_id": "support-agent-v1",
  "allow_unlisted_tools": false,
  "allowed_tools": {
    "crm_lookup":  { "required_arguments": { "account_id": "str" } },
    "create_ticket": {
      "required_arguments": { "title": "str", "priority": "str" },
      "optional_arguments": { "assignee": "str" }
    }
  }
}
```

Set `"allow_unlisted_tools": true` to only contract the tools you list.

## Require workflow tools

Every listed tool must be called at least once (`ARH-SEQ-001`):

```json
{ "sequence": { "required_tools": ["lookup_order", "check_refund_eligibility"] } }
```

## Forbid a tool

Each call to a listed tool is an error (`ARH-SEQ-002`):

```json
{ "sequence": { "forbidden_tools": ["delete_order", "wire_transfer"] } }
```

## Enforce call order (partial order)

```json
{ "sequence": { "call_order": ["lookup_order", "check_refund_eligibility", "issue_refund"] } }
```

Semantics: for each pair of listed tools that were **both called**, the
earlier-listed tool's **first call** must precede the later-listed tool's
first call (`ARH-SEQ-003`). Uncalled tools don't violate order; later repeat
calls of an earlier tool are fine. This is intentionally *not* an exact
golden-trajectory match: agents may legitimately interleave extra steps, and
exact matching punishes valid paths. Combine with `required_tools` when
presence itself is mandatory.

## Constrain argument values

Beyond types, constrain values (`ARH-SCH-007/008/009`):

```json
{
  "allowed_tools": {
    "notify_customer": {
      "required_arguments": {
        "channel": { "type": "str", "enum": ["email", "sms"] }
      }
    },
    "lookup_order": {
      "required_arguments": {
        "order_id": { "type": "str", "pattern": "ORD-[0-9]+" }
      }
    },
    "issue_refund": {
      "required_arguments": {
        "amount": { "type": "float", "min": 0.01, "max": 500 }
      }
    }
  }
}
```

`pattern` is a **full match** (the entire value must match). The legacy bare
string form (`"order_id": "str"`) still works for type-only checks.

## Protect side effects from duplicates

```json
{
  "allowed_tools": {
    "issue_refund": {
      "required_arguments": { "order_id": "str", "amount": "float" },
      "side_effect": true,
      "max_calls": 1
    }
  }
}
```

A `side_effect` tool called again with **identical arguments after already
succeeding** is a duplicate (`ARH-FLW-003`). Retrying after a *failed* attempt
is allowed. `max_calls`/`min_calls` bound total calls per tool
(`ARH-SEQ-004/005`) regardless of arguments.

## Require retries, cap retry storms

```json
{ "error_handling": { "require_retry_on_error": true, "max_attempts": 3 } }
```

- A `tool_call` with `status: "error"` never followed by another call to the
  same tool → ignored error (`ARH-FLW-001`).
- The same tool called with byte-identical arguments more than `max_attempts`
  times → retry storm (`ARH-FLW-002`).

## Require completion

```json
{ "completion": { "require_final_response": true, "max_steps": 20 } }
```

The trace must end with a successful, non-empty `model_response`
(`ARH-CMP-001`) and stay under `max_steps` (`ARH-CMP-002` — catches agents
that fail to terminate).

## Budgets

```json
{
  "budgets": {
    "max_total_latency_ms": 8000,
    "max_step_latency_ms": 2500,
    "max_total_cost_usd": 0.25,
    "max_total_tokens": 6000
  }
}
```

Rules `ARH-BUD-001..004`. Note: any budget the trace cannot demonstrate
compliance with produces a score-neutral **warning** instead of a silent
pass: `ARH-BUD-005` (token budget, no token data), `ARH-BUD-006` (latency
budget, no latency data), `ARH-BUD-007` (cost budget, no cost data) — a budget the trace cannot demonstrate compliance with is not
"met". Record `input_tokens`/`output_tokens` on steps, or remove the budget.

## Unsafe content patterns

```json
{
  "unsafe_patterns": [
    "ignore (all|any|the) (previous|prior|above) instructions",
    "\\bpassword\\s*[:=]",
    "\\bapi[_-]?key\\b"
  ]
}
```

Case-insensitive regexes scanned over model text, string tool outputs/output
values, and string tool arguments (`ARH-SAF-001`). Patterns are **trusted
input** authored by you — an invalid regex fails validation with a precise
error, and you should not run policies from untrusted sources
(see [SECURITY.md](../SECURITY.md)).

## Grounding and citations

```json
{
  "grounding": {
    "require_citations": true,
    "min_citation_coverage": 0.9,
    "require_valid_citation_urls": true
  }
}
```

Steps marked `"requires_grounding": true` must carry citations
(`ARH-GRD-001`), coverage must meet the minimum (`ARH-GRD-002`), and with
`require_valid_citation_urls` each citation needs a non-empty `source` or a
valid http(s) `url` (`ARH-GRD-003` — also rejects `javascript:`/`ftp:` schemes).
