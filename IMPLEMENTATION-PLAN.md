# Implementation Plan

## Scope decision (Phase 6)

The 0.2.0 vertical slice was chosen to demonstrate the full product thesis end
to end — import → normalize → validate → compare → report → gate — without
attempting the long-term platform in one rewrite:

1. canonical versioned trace schema (v1, additive over v0.1.x);
2. upgraded policy schema (sequence / error_handling / completion / ArgSpec
   constraints / side effects / call counts / token budgets);
3. deterministic trajectory rules with stable rule IDs;
4. baseline-vs-candidate regression comparison with CI gates;
5. two real provider adapters (openai-chat, anthropic-messages) with fixtures;
6. JSON, Markdown, JUnit, SARIF reports;
7. GitHub Action integration;
8. seeded benchmark suite with CI-enforced thresholds;
9. documentation set (specs + user guides);
10. migration-free backward compatibility for current users.

Deliberately excluded from this slice (recorded before implementation):
plugin SDK (ADR-008), OTel ingestion (ADR-005), semantic evaluators, HTML
report, web UI, pass^k analysis — see ROADMAP.md.

## Delivered vs planned

All ten slice items shipped. Deviations from the original sketch:

- **Two adapters instead of one.** Both target formats are publicly documented
  and share fixtures; the pair enables the adapter-equivalence benchmark, which
  is itself evidence for provider neutrality.
- **`docs/rules.md` is generated** (`tools/generate_rules_doc.py`) rather than
  hand-written, so rule docs cannot drift from the registry.
- One v0.1 bug was fixed rather than preserved (duplicate findings for
  wrong-typed required arguments; ADR-007).

## Commit sequence on `feat/v0.2-trajectory-regression`

| Commit | Content |
|---|---|
| `dc07ab7` | Phase-1 research: competitive landscape, user problems, capability matrix, source ledger |
| `3618e66` | Core implementation: trajectory rules, regression engine, adapters, JUnit/SARIF, rule IDs, 160-test suite, golden compatibility pins |
| `242d09b` | Benchmark suite + thresholds, JSON Schemas, GitHub Action, expanded CI matrix, pyproject 0.2.0 |
| (subsequent) | Specs and product docs (this file and siblings), user guides, OSS hygiene files, verifier-review fixes |

Baseline recorded before any change: v0.1.0 at `d6ed36e`, 35 tests green,
sample run 1/3 pass avg 83.33 exit 1 — preserved by golden tests.

## Remaining to 0.2.0 tag (ordered)

1. user docs + README + OSS hygiene files (in progress, parallel track);
2. full quality-gate pass: 3-OS/3-Python CI, packaging build + clean-venv
   install, docs-example tests;
3. Phase-9 independent verifier reviews (methodology, architecture,
   compatibility, security, benchmark fairness, FP/FN risk, DX, docs,
   packaging, complexity); resolve all critical/high findings and rerun
   affected tests;
4. final report. **No push, merge, publish, or release without explicit
   authorization.**

## Post-0.2.0 milestones

See ROADMAP.md. Order: 0.2.x hardening from early-user feedback → 0.3 (OTel
GenAI adapter pinned to a semconv release; plugin SDK if a second evaluator
class materializes; HTML report) → 0.4 (optional semantic extra with fake-
provider tests; pass^k consistency analysis) → trace v2 exploration
(multi-agent handoffs, span parent/child).
