# Regression Testing

The regression engine answers: *did this change (model, prompt, tool, policy)
make the agent worse, and exactly how?*

## Workflow

1. **Create a baseline** from a known-good run. The plain JSON validation
   report *is* the baseline format — no extra artifact:

   ```bash
   arh validate --policy policy.json traces/*.json --json-out baselines/main.json
   ```

2. **Commit the baseline** (it's deterministic, so diffs are meaningful).

3. **Compare candidates** — either validate in one step:

   ```bash
   arh compare --baseline baselines/main.json --policy policy.json traces/*.json
   ```

   or compare two pre-computed reports:

   ```bash
   arh compare --baseline baselines/main.json --candidate report.json
   ```

4. **Read the diff**: new findings, resolved findings, pass→fail /
   fail→pass transitions, per-trace score/latency/cost deltas, added/removed
   traces. `--json-out` and `--md-out` write machine- and PR-friendly reports.

## Finding fingerprints

A finding's identity is `(trace_id, rule_id, category, step_id)`.
**Messages are deliberately excluded**: they contain measured values
("latency 5700ms exceeds...") that legitimately vary between runs; including
them would make every run look like a regression. This is also why stable
trace IDs and step IDs matter — see [adapters.md](adapters.md) for imported
transcripts.

Duplicate findings are handled as multisets: two identical findings in the
candidate vs. one in the baseline = one new finding.

## Gate modes

| Mode | Fails when |
|---|---|
| `--fail-on regressions` (default) | new **error** findings, any pass→fail transition, any *added* trace that fails, or (with `--max-score-drop N`) any per-trace score drop over N points |
| `--fail-on failures` | any candidate trace fails, baseline ignored (absolute gate) |
| `--fail-on never` | never — report-only mode |

Notes: new *warning* findings never fail the default gate; removed traces are
reported but don't fail it; resolved findings and pre-existing failures don't
re-alarm.

## Updating the baseline

When a candidate is accepted, promote it:

```bash
arh compare --baseline baselines/main.json --policy policy.json traces/*.json --candidate-json-out baselines/next.json
mv baselines/next.json baselines/main.json
```

(Or simply re-run `arh validate --json-out baselines/main.json`.)

## v0.1.x baselines

Baselines produced by v0.1.x have no `rule_id` on findings. `arh compare`
falls back to matching on `(trace_id, category, step_id)` for those, so
upgrading does not flood you with false new/resolved findings. Regenerate the
baseline once after upgrading to get full-precision fingerprints
([COMPATIBILITY.md](../COMPATIBILITY.md)).

## What compare does not do (yet)

- No multi-run statistical analysis: it diffs one candidate run against one
  baseline. Agent nondeterminism (pass^k-style consistency measurement)
  requires running your agent multiple times and is on the
  [roadmap](../ROADMAP.md) — until then, a common pattern is validating N
  recorded runs of the same scenario as N traces.
- No flaky-scenario detection or confidence intervals.
- It never re-runs your agent; it only evaluates recorded traces.
