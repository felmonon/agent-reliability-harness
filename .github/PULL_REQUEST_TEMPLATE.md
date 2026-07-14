## What and why

<!-- Link the issue. Explain the user-visible behavior change. -->

## Compatibility impact

<!-- "None" or the exact impact on trace/policy/report formats, scores,
     verdicts, rule IDs, exit codes. Breaking changes need prior discussion. -->

## Evidence

- [ ] `python -m unittest discover -s tests` passes
- [ ] `ruff check src tests benchmarks` and `mypy src` pass
- [ ] `python benchmarks/run.py` passes (regenerated cases via the generator
      if rules changed)
- [ ] Docs updated (and doc commands still pass `tests/test_docs_examples.py`)
- [ ] CHANGELOG.md updated under Unreleased

<!-- For user-visible output changes, paste before/after report snippets. -->
