# Quickstart

Five minutes from install to a working regression gate. Every command below is
executed by the test suite (`tests/test_docs_examples.py`), so it cannot drift
from the code.

## 1. Install

Not yet on PyPI — install from a checkout (or straight from GitHub):

```bash
python -m pip install -e .
```

Zero runtime dependencies are added. Verify:

```bash
arh --version
```

## 2. Validate the samples

```bash
arh validate --policy samples/policy_trajectory.json samples/traces/refund_workflow_pass.json samples/traces/refund_workflow_double_refund.json
```

You get one `[PASS]` and one `[FAIL]`, and the process exits `1` (any failing
trace fails the run — CI-friendly). The failing trace produced a perfectly
plausible final answer; it fails on the *trajectory*: the refund fired before
the lookup, the eligibility check never ran, and the refund was issued twice.

## 3. Read a finding

Add `--json-out` to keep a machine-readable report:

```bash
arh validate --policy samples/policy_trajectory.json samples/traces/refund_workflow_double_refund.json --json-out report.json --quiet
```

Each finding is precise, located, and stable across runs:

```json
{
  "severity": "error",
  "category": "sequence",
  "message": "required tool 'check_refund_eligibility' was never called",
  "step_id": null,
  "rule_id": "ARH-SEQ-001",
  "expected": "at least one call to 'check_refund_eligibility'",
  "observed": "0 calls"
}
```

- `rule_id` — stable identifier ([full reference](rules.md)); never changes
  meaning across releases; used for regression fingerprints.
- `expected` / `observed` — what the policy wanted vs. what the trace did.
- `step_id` — the offending step, when the finding is step-local.

## 4. Write your first policy

A policy is JSON (see the [cookbook](policy-cookbook.md) and
[POLICY-SPEC.md](../POLICY-SPEC.md)). A minimal one:

```json
{
  "policy_id": "my-agent-v1",
  "allowed_tools": {
    "search":     { "required_arguments": { "query": "str" } },
    "send_email": { "required_arguments": { "to": "str" }, "side_effect": true }
  },
  "sequence": { "call_order": ["search", "send_email"] },
  "completion": { "require_final_response": true }
}
```

## 5. Create a baseline

```bash
arh validate --policy samples/policy_trajectory.json samples/traces/refund_workflow_pass.json --json-out baseline.json --quiet
```

The JSON report *is* the baseline — there is no separate format. Commit it.

## 6. Compare a candidate run

```bash
arh compare --baseline baseline.json --policy samples/policy_trajectory.json samples/traces/refund_workflow_pass.json samples/traces/refund_workflow_double_refund.json --md-out compare.md
```

Exit code `1`: the gate failed because the candidate introduced new error
findings. `compare.md` is a PR-comment-ready summary. Identical runs pass;
pre-existing failures don't re-alarm. Details: [regression-testing.md](regression-testing.md).

## 7. Gate CI

```yaml
# .github/workflows/agent-reliability.yml
name: Agent reliability
on: [pull_request]
jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - uses: felmonon/agent-reliability-harness@main
        with:
          policy: samples/policy_trajectory.json
          traces: samples/traces/refund_workflow_pass.json
          baseline: baseline.json
```

More workflows (SARIF annotations, JUnit publishing): [ci.md](ci.md).

## Importing real transcripts

Already logging OpenAI or Anthropic conversations? Point `arh validate` at
them directly — the format is auto-detected:

```bash
arh validate --policy samples/policy_trajectory.json --format openai-chat tests/fixtures/openai_chat_refund.json
```

(Exits `1`: that transcript skips the required eligibility check — the rules
run identically on imported transcripts.) See [adapters.md](adapters.md) for
what each format can and cannot carry.
