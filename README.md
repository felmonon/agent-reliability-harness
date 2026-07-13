# Agent Reliability Harness

A small, policy-driven evaluator for agent execution traces.

It checks whether an agent used approved tools correctly, stayed within latency and cost budgets, avoided disallowed content patterns, and cited supporting sources when a response required grounding.

The project is a company-specific engineering sample for applied AI and forward-deployed roles. The sample workflows are synthetic and do not use Cohere systems, customer data, or proprietary APIs.

## Why this exists

A production agent can complete the apparent task and still be unsafe or expensive:

- it may call a tool that is not approved for the workflow;
- required tool arguments may be missing or use the wrong type;
- latency or token cost may exceed the service budget;
- a prompt-injection string may enter the trace;
- a factual response may be returned without evidence.

This harness turns those concerns into versioned policy and repeatable checks.

## Example

```bash
python -m pip install -e .

arh validate \
  --policy samples/policy.json \
  samples/traces/*.json \
  --json-out report.json \
  --md-out report.md
```

The included samples produce:

- one passing lead-qualification trace;
- one renewal workflow that exceeds latency and cost budgets;
- one support-escalation trace with an unapproved tool, missing citations, a prompt-injection phrase, and a password-like string.

Example summary:

```text
[PASS] lead-qualification-0001  score=100.0/100
[FAIL] renewal-workflow-0007    score=80.0/100
[FAIL] support-escalation-0042  score=70.0/100

SUMMARY: 1/3 traces passed, average score 83.3/100
```

## What it evaluates

### Tool-call contracts

Each allowed tool has required and optional arguments with primitive type declarations. The validator reports:

- tools that are not permitted by the workflow policy;
- missing required arguments;
- incorrect argument types;
- undeclared arguments.

### Performance and cost budgets

Policies can define:

- maximum total trace latency;
- maximum latency for an individual step;
- maximum total cost.

### Safety patterns

Policies contain case-insensitive regular expressions for content that should never appear in a tool argument, model response, or tool output. The included policy demonstrates checks for prompt-injection language and password-like strings.

### Grounding coverage

Model responses can be marked `requires_grounding`. The harness measures the percentage of those responses that contain citations and compares it with the policy threshold.

## Input format

Trace:

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

Policy:

```json
{
  "policy_id": "enterprise-agent-default-v1",
  "allowed_tools": {
    "lookup_account": {
      "required_arguments": { "account_id": "str" }
    }
  },
  "budgets": {
    "max_total_latency_ms": 6000,
    "max_step_latency_ms": 2500,
    "max_total_cost_usd": 0.25
  },
  "grounding": {
    "require_citations": true,
    "min_citation_coverage": 0.75
  }
}
```

See `samples/` for complete examples.

## Reports and exit codes

The CLI prints a concise terminal report and can also write JSON and Markdown.

- Exit `0`: every trace passed.
- Exit `1`: at least one trace failed.
- Exit `2`: invalid CLI usage.

This makes the tool usable in CI as an agent-quality gate.

## Design decisions

- **Standard library only at runtime.** The CLI can be used without adding an evaluation framework to the application dependency graph.
- **Typed dataclasses.** Invalid trace structure fails early with a useful message.
- **Independent checks.** Schema, budget, safety, and grounding checks are evaluated separately and combined into a weighted score.
- **Synthetic examples.** The repository demonstrates enterprise workflow concerns without exposing private data.
- **Machine- and reviewer-readable output.** JSON supports automation; Markdown and console output support review.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

The test suite currently contains 35 unit and CLI tests. GitHub Actions runs the suite on Python 3.11 and 3.12.

## Possible extensions

- JSON Schema or Pydantic tool contracts;
- provider adapters for real agent tracing systems;
- semantic safety evaluators in addition to regex policies;
- per-tool latency and cost budgets;
- OpenTelemetry export;
- a small web interface for comparing multiple runs.

## Author

[Felmon Fekadu](https://felmon.tech/proof)  
[GitHub](https://github.com/felmonon)

## License

MIT
