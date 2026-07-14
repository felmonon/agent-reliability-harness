# ARH Policy Specification (schema version 1)

Normative specification of the policy-as-code format. Machine-readable schema:
`schemas/policy.schema.json`. Parser: `Policy.from_dict` in
`src/agent_reliability_harness/models.py`. Rule reference: `docs/rules.md`.
Recipes: `docs/policy-cookbook.md`.

A policy declares **constraints** the trajectory must satisfy — deliberately not
a golden trajectory to match (see `sequence` rationale below).

## Top level

| Field | Type | Required | Default |
|---|---|---|---|
| `schema_version` | string | no | `"1"` (missing = 1; unknown major rejected) |
| `policy_id` | string | **yes** | — |
| `allow_unlisted_tools` | boolean | no | `false` |
| `allowed_tools` | object: tool name → ToolSchema | no | `{}` |
| `budgets` | object | no | `{}` |
| `unsafe_patterns` | array of regex strings | no | `[]` |
| `grounding` | object | no | `{}` |
| `sequence` | object | no | `{}` |
| `error_handling` | object | no | `{}` |
| `completion` | object | no | `{}` |

Sections that are absent are **not applicable**: they produce no findings and are
excluded from scoring (this is what keeps v0.1.x policy scores unchanged).

## `allowed_tools`

Every `tool_call` must name a tool listed here (else **ARH-SCH-001**, error),
unless `allow_unlisted_tools: true`.

Each ToolSchema:

| Field | Type | Default | Behavior |
|---|---|---|---|
| `required_arguments` | name → ArgSpec | `{}` | Missing argument → **ARH-SCH-003**. |
| `optional_arguments` | name → ArgSpec | `{}` | Constraints applied when present. |
| `side_effect` | boolean | `false` | See flow checks below. |
| `max_calls` | int ≥ 0 \| null | null | More calls → **ARH-SEQ-004**. |
| `min_calls` | int ≥ 0 \| null | null | Fewer calls → **ARH-SEQ-005**. `min_calls > max_calls` is rejected at parse time. |

Arguments not declared in either section raise **ARH-SCH-005** (warning).

### ArgSpec: two forms

Legacy form (v0.1.x): a bare type name string —
`"str" | "int" | "float" | "bool" | "list" | "dict" | "any"`.

Object form (v1):

```json
{ "type": "str", "enum": ["low", "high"] }
{ "type": "str", "pattern": "ORD-[0-9]+" }
{ "type": "int", "min": 1, "max": 100 }
```

- `type` (default `"any"`): wrong runtime type → **ARH-SCH-004**. `bool` never
  satisfies `int`/`float`. An unknown declared type name yields the info finding
  **ARH-SCH-006** and skips the check (surface the typo, stay permissive).
- `enum`: value must be a member → else **ARH-SCH-007**.
- `pattern`: **full-match** regular expression over string values (substring
  matches do not pass) → else **ARH-SCH-008**.
- `min` / `max`: numeric bounds (booleans excluded) → else **ARH-SCH-009**.
- Value-constraint checks run only when the type check passes.

## `budgets`

| Field | Finding on breach |
|---|---|
| `max_step_latency_ms` | **ARH-BUD-001** (per offending step; steps without latency are skipped) |
| `max_total_latency_ms` | **ARH-BUD-002** (sum of recorded latencies) |
| `max_total_cost_usd` | **ARH-BUD-003** |
| `max_total_tokens` | **ARH-BUD-004** (sum of input+output tokens over steps that record any) |

**Unverifiable budgets warn, never silently pass:** if `max_total_tokens` is set
but no step records token usage, the warning **ARH-BUD-005** is emitted instead
of a silent pass. (Design rationale: DECISIONS.md ADR-006.)

## `unsafe_patterns`

Case-insensitive regular expressions applied to every text blob the agent
produced or consumed as arguments: `model_response.text`, string `output`
values (including string values inside dict outputs), and string argument
values. Each match → **ARH-SAF-001** (error). An invalid regex raises
`ValueError: policy unsafe_patterns contains an invalid regex: ...` before any
scanning. Patterns are trusted input authored by the policy owner (SECURITY.md).

## `grounding`

Applies to `model_response` steps with `requires_grounding: true`; if none
exist the category is not applicable.

| Field | Default | Behavior |
|---|---|---|
| `require_citations` | false | Uncited grounded step → **ARH-GRD-001** (error if true, warning if false). |
| `min_citation_coverage` | 0.0 | cited/grounded below this fraction → **ARH-GRD-002**. |
| `require_valid_citation_urls` | false | Each citation must be an object with a valid http(s) `url` (scheme + host) or a non-empty `source` → else **ARH-GRD-003**. |

## `sequence`

| Field | Behavior |
|---|---|
| `required_tools` | Each listed tool must be called ≥ 1 time → else **ARH-SEQ-001**. |
| `forbidden_tools` | Any call to a listed tool → **ARH-SEQ-002** (one finding per call). Overlap with `required_tools` is rejected at parse time. |
| `call_order` | Partial-order constraint, see below → violations are **ARH-SEQ-003**. Duplicate entries rejected at parse time. |

### `call_order` is a partial order, not a golden trajectory

For every pair of listed tools that were **both called**, the **first** call of
the earlier-listed tool must precede the **first** call of the later-listed
tool. Tools never called are vacuously fine (use `required_tools` to require
presence). Repeat calls after the first are unconstrained. Unlisted tools may
appear anywhere.

Rationale: exact-trajectory matching punishes valid alternative solutions —
Anthropic's eval guidance calls step-sequence assertions "too rigid", and
LangChain users have had to hand-build precedence evaluators because
strict/unordered matching is the only choice
(`research/user-problems.md`). Constraints express what actually matters
("lookup before refund") while leaving the rest of the trajectory free.

## `error_handling`

| Field | Behavior |
|---|---|
| `require_retry_on_error` | Every tool_call with `status: "error"` must be followed later by another call to the same tool → else **ARH-FLW-001**. |
| `max_attempts` (int ≥ 1) | More than `max_attempts` calls of the same tool with **byte-identical canonical arguments** → **ARH-FLW-002** (retry storm), anchored at the first excess attempt. Different arguments never count toward the same group. |

## Side effects (flow)

For every tool with `side_effect: true`: after a **successful** call, any
further call with identical canonical arguments → **ARH-FLW-003** (duplicate
side effect), one finding per duplicate. A retry after a *failed* attempt is
allowed. Argument identity uses sorted-key JSON serialization.

## `completion`

| Field | Behavior |
|---|---|
| `require_final_response` | The last step must be a `model_response` with `status: "ok"` and non-empty text → else **ARH-CMP-001** (also fired by an empty trace). |
| `max_steps` (int ≥ 1) | More steps → **ARH-CMP-002**. |

## Structure lint

Independent of policy content: duplicate `step_id`s raise **ARH-SCH-010**
(warning). Lint findings never affect the score.

## Scoring model

- Category weights: schema 0.3, budget 0.3, safety 0.25, grounding 0.15,
  sequence 0.25, flow 0.2, completion 0.1.
- Only **applicable** categories participate; weights are renormalized over the
  applicable set. Applicability: schema — trace has tool calls; budget — any
  budget set; safety — patterns set and text blobs exist; grounding — grounded
  steps exist; sequence — sequence rules or call-count bounds configured;
  flow — error-handling rules or side-effect tools produced ≥ 1 check;
  completion — completion rules set.
- Each category scores `100 × passed_checks / total_checks`.
- **Pass criterion:** no error-severity findings **and** score ≥ `fail_under`
  (default 70; CLI `--fail-under`). Errors always fail regardless of score;
  warnings/infos never fail alone.

## Validation errors

Malformed policies raise `ValueError` naming the exact field, e.g.
`policy tool 'x': min_calls (3) exceeds max_calls (1)`,
`policy sequence.call_order lists 'a' more than once`,
`policy error_handling.max_attempts must be an integer >= 1`,
`policy argument 'tool.arg': 'enum' must be a list`.
The CLI wraps these as `error: invalid policy <path>: <detail>` (exit 1).

## Full example

`samples/policy_trajectory.json` exercises every section; the benchmark policy
in `benchmarks/tools/generate_cases.py` additionally uses `max_total_tokens`
and `min_calls`/`max_calls`.
