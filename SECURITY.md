# Security

## Threat model

**Traces are untrusted data.** Traces routinely contain hostile content — the
whole point of the safety checks is to find prompt-injection strings, secrets,
and unsafe text inside them. The harness treats all trace content strictly as
data: nothing from a trace is ever executed, evaluated, templated into code, or
sent anywhere. Injection strings simply become findings
(see `tests/test_adversarial.py::TestHostileContent`, including the
`prompt_injection_string_is_data_not_directive` test and hostile
unicode/control-character rendering tests for every report format; XML output
is escaped via `xml.sax.saxutils`).

**Policies are trusted input.** `unsafe_patterns` and ArgSpec `pattern` entries
are compiled with Python's `re` module. A pathological regex can be slow
(ReDoS-style backtracking). Policies are configuration authored by the same
team that runs the harness — do **not** run policies from untrusted sources.
Invalid regexes fail loudly with a precise `ValueError` before any scanning.

**No network, no telemetry, no clocks.** The core makes zero network calls,
collects zero telemetry, and reads no clocks or environment state during
evaluation. Determinism is enforced by tests and benchmark thresholds. The
GitHub Action's only network activity is `pip install` of the action's own
checkout; it requires no secrets and is safe on forks.

**Reports can leak trace content.** Findings quote matched content (e.g. the
string that matched a secret pattern) and tool arguments. If your traces
contain sensitive data, treat JSON/Markdown/JUnit/SARIF outputs with the same
sensitivity as the traces themselves — redact traces before evaluation or
restrict artifact visibility before uploading reports to CI systems.

**Filesystem writes** are limited to the exact paths passed via
`--json-out/--md-out/--junit-out/--sarif-out/--candidate-json-out` (parent
directories are created).

## Supported versions

| Version | Supported |
|---|---|
| 0.2.x | yes |
| 0.1.x | fixes ship in 0.2.x only |

## Reporting a vulnerability

Use GitHub's **private vulnerability reporting** on
`felmonon/agent-reliability-harness` (Security tab → "Report a vulnerability").
Please do not open public issues for suspected vulnerabilities. There is no
dedicated security email. You can expect an acknowledgment within a week; fixes
are released as patch versions with a changelog entry.
