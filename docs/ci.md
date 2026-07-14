# CI Integration

## GitHub Action

The repo root ships a composite action (`action.yml`). It installs the harness
from the action checkout, validates traces, optionally compares against a
baseline, appends a Markdown summary to the workflow step summary, and exits
according to the gate. It uses **no secrets** and makes **no network calls**
beyond `pip install`, so it is safe on fork PRs.

### Inputs

| Input | Required | Default | Meaning |
|---|---|---|---|
| `policy` | yes | – | Path to the policy JSON |
| `traces` | yes | – | Space-separated trace paths/globs |
| `format` | no | `auto` | `auto` \| `arh` \| `openai-chat` \| `anthropic-messages` |
| `baseline` | no | `""` | Baseline report; when set, gates via `arh compare` |
| `fail-on` | no | `regressions` | `regressions` \| `failures` \| `never` |
| `max-score-drop` | no | `""` | Per-trace score-drop limit for the regressions gate |
| `fail-under` | no | `70.0` | Minimum passing score for validate |
| `output-dir` | no | `arh-reports` | Where report artifacts are written |

### Outputs

| Output | Meaning |
|---|---|
| `json-report` | JSON validation report (usable as the next baseline) |
| `sarif-report` | SARIF 2.1.0 report |
| `junit-report` | JUnit XML report |
| `compare-report` | Comparison JSON (only when `baseline` was set) |

### Minimal gate

```yaml
name: Agent reliability
on: [pull_request]
jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - uses: felmonon/agent-reliability-harness@v0.2.1
        with:
          policy: policies/agent-policy.json
          traces: traces/*.json
```

### Regression gate with a committed baseline

```yaml
      - uses: felmonon/agent-reliability-harness@v0.2.1
        id: arh
        with:
          policy: policies/agent-policy.json
          traces: traces/*.json
          baseline: baselines/main.json
          max-score-drop: "5"
```

### Code-scanning annotations (SARIF)

```yaml
      - uses: felmonon/agent-reliability-harness@v0.2.1
        id: arh
        continue-on-error: true
        with:
          policy: policies/agent-policy.json
          traces: traces/*.json
      - uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: ${{ steps.arh.outputs.sarif-report }}
      - name: Enforce gate
        if: steps.arh.outcome == 'failure'
        run: exit 1
```

Findings appear as code-scanning alerts, located on the trace files.

### JUnit publishing and artifacts

```yaml
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: arh-reports
          path: arh-reports/
```

Any JUnit-consuming publisher (e.g. `mikepenz/action-junit-report`) can read
`${{ steps.arh.outputs.junit-report }}`.

### PR summaries

The action always appends the Markdown report (and the comparison, when a
baseline is set) to `$GITHUB_STEP_SUMMARY` — visible on the workflow run page
with no extra permissions. For a sticky PR comment, feed the generated
Markdown to any comment action; the report is plain Markdown by design.

## Any other CI

The CLI is the integration surface: exit `0` pass, `1` fail, `2` usage error.

```bash
pip install agent-reliability-harness  # once published; today: pip install git+https://github.com/felmonon/agent-reliability-harness
arh validate --policy policy.json traces/*.json --junit-out report.xml
```

Reports are byte-deterministic, so they cache and diff cleanly.
