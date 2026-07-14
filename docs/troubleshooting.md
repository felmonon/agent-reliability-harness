# Troubleshooting

## Exit codes

| Code | Meaning |
|---|---|
| 0 | validation passed / gate passed |
| 1 | at least one trace failed / gate failed |
| 2 | usage or input error (bad flags, unreadable/invalid files) |

## Common errors

All input errors exit with code 2 and a message starting `error:` — no Python
tracebacks for bad input. If you ever see a traceback, that's a bug; please
report it.

### `error: failed to parse JSON from <path>: ...`

The file isn't valid JSON (truncated write, trailing comma, empty file). The
message includes the line/column from the JSON parser.

### `error: invalid trace <path>: trace is missing required field '...'`

Canonical traces require `trace_id`, `agent_name`, `workflow`, and `steps`.
If you meant to pass a provider transcript, check `--format` / auto-detection.

### `error: invalid trace <path>: trace declares unsupported schema_version '...'`

The file declares a schema major version this build doesn't support. This
build supports major version `1` (and files with no `schema_version` at all).
Upgrade the harness rather than editing the version field.

### `error: invalid policy <path>: ...`

Policy validation is strict and points at the offending field, e.g.
`policy error_handling.max_attempts must be an integer >= 1` or
`policy sequence lists the same tool(s) as required and forbidden: ...`.

### `error: validating <path>: policy unsafe_patterns contains an invalid regex: ...`

One of your `unsafe_patterns` isn't a valid Python regex. The regex error is
included verbatim.

### `error: invalid trace <path>: cannot detect trace format: ...`

Auto-detection needs an object with `steps` (canonical), an object with
`messages`, or a bare message list. Force `--format` if your wrapper differs.

### `error: baseline report is not a validation report: ...`

`arh compare --baseline` expects the JSON written by
`arh validate --json-out`, not a trace or policy file.

### `... report contains duplicate trace_id '...'`

Regression comparison needs unique trace IDs per report. Give imported
transcripts distinct `trace_id`s (or distinct file names — the file stem is
the fallback ID).

## Why did my token budget produce a warning?

`ARH-BUD-005`: the policy sets `max_total_tokens`, but the trace records no
`input_tokens`/`output_tokens` on any step, so compliance cannot be verified.
The harness warns instead of silently passing. Either record token usage in
your traces (note: the openai-chat/anthropic-messages transcript formats don't
carry it) or remove the budget from the policy.

## Why did a trace pass despite warnings?

Only `error`-severity findings fail a trace. Warnings (undeclared arguments,
duplicate step IDs, unverifiable budgets) surface hygiene issues without
breaking CI. Tighten by fixing the underlying issue — warning rules are listed
in [rules.md](rules.md).

## macOS: "command not found: arh" right after install

Your shell may be caching an old PATH: `hash -r` (bash) or `rehash` (zsh), or
re-activate the virtualenv.
