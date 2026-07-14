---
name: Bug report
about: A reproducible problem with validation, comparison, adapters, or reports
labels: bug
---

## What happened

<!-- What did you run, what did you expect, what did you get? -->

## Reproduction

Minimal trace + policy that reproduce it (redact sensitive content — trace
snippets end up in public issues):

```json
// policy.json
```

```json
// trace.json
```

Command and full output (including the exit code):

```bash
arh validate --policy policy.json trace.json; echo "exit=$?"
```

## Environment

- harness version (`arh --version`):
- Python version / OS:

## Determinism note

If the behavior differs between identical runs, say so explicitly — identical
input is guaranteed to produce byte-identical reports, so nondeterminism is
always a high-priority bug.
