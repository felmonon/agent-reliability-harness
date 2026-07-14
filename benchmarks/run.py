#!/usr/bin/env python3
"""Benchmark runner: measures detection quality, determinism, and performance.

Usage (from the repo root, package installed):

    python benchmarks/run.py            # run, print metrics, exit 1 on threshold breach
    python benchmarks/run.py --write    # additionally rewrite BENCHMARK-RESULTS.md

Thresholds (a breach fails the run, and CI):

- precision == 1.0 and recall == 1.0 on the seeded case suite
  (all checks are deterministic; anything less is a bug, not noise);
- byte-identical reports across repeated runs;
- median validation time under 50 ms per trace;
- metamorphic invariances hold;
- adapter equivalence holds;
- regression scenarios gate correctly.

See BENCHMARK-METHODOLOGY.md for design and scope limits.
"""

from __future__ import annotations

import argparse
import copy
import json
import platform
import statistics
import sys
import time
import tracemalloc
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = REPO_ROOT / "benchmarks" / "cases"
FIXTURES = REPO_ROOT / "tests" / "fixtures"
RESULTS_MD = REPO_ROOT / "BENCHMARK-RESULTS.md"

sys.path.insert(0, str(REPO_ROOT / "src"))

from agent_reliability_harness import __version__  # noqa: E402
from agent_reliability_harness.adapters import normalize  # noqa: E402
from agent_reliability_harness.models import Policy, Trace  # noqa: E402
from agent_reliability_harness.regression import compare_reports, evaluate_gate  # noqa: E402
from agent_reliability_harness.report import render_json, render_json_str  # noqa: E402
from agent_reliability_harness.validator import validate_trace  # noqa: E402

TIME_BUDGET_MS_PER_TRACE = 50.0


def load_cases():
    cases = []
    for path in sorted(CASES_DIR.glob("*.json")):
        cases.append((path.name, json.loads(path.read_text(encoding="utf-8"))))
    if not cases:
        raise SystemExit(f"no benchmark cases found in {CASES_DIR}")
    return cases


def finding_multiset(report):
    return Counter(
        (f.severity, f.rule_id, f.step_id)
        for f in report.findings
        if f.severity in ("error", "warning")
    )


def expected_multiset(case):
    return Counter(
        (severity, rule_id, step_id)
        for severity, rule_id, step_id in case["expected"]["findings"]
    )


def run_detection(cases):
    per_case = []
    tp = fp = fn = 0
    for _name, case in cases:
        policy = Policy.from_dict(case["policy"])
        trace = Trace.from_dict(case["trace"])
        report = validate_trace(trace, policy)
        expected = expected_multiset(case)
        actual = finding_multiset(report)
        case_tp = sum((expected & actual).values())
        case_fn = sum((expected - actual).values())
        case_fp = sum((actual - expected).values())
        passed_ok = report.passed == case["expected"]["passed"]
        ok = case_fn == 0 and case_fp == 0 and passed_ok
        tp += case_tp
        fn += case_fn
        fp += case_fp
        per_case.append(
            {
                "case": case["case_id"],
                "category": case["category"],
                "ok": ok,
                "tp": case_tp,
                "fp": case_fp,
                "fn": case_fn,
                "expected_passed": case["expected"]["passed"],
                "actual_passed": report.passed,
                "unexpected": sorted(
                    f"{sev}:{rule}:{step}" for sev, rule, step in (actual - expected)
                ),
                "missed": sorted(
                    f"{sev}:{rule}:{step}" for sev, rule, step in (expected - actual)
                ),
            }
        )
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    return {
        "cases": len(per_case),
        "cases_ok": sum(1 for c in per_case if c["ok"]),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "false_positive_findings": fp,
        "false_negative_findings": fn,
        "per_case": per_case,
    }


def run_determinism(cases):
    def render_all():
        reports = []
        for _name, case in cases:
            policy = Policy.from_dict(case["policy"])
            trace = Trace.from_dict(case["trace"])
            reports.append(validate_trace(trace, policy))
        return render_json_str(reports)

    first = render_all()
    second = render_all()
    return {"byte_identical": first == second}


def run_performance(cases, iterations=20):
    parsed = [
        (Policy.from_dict(case["policy"]), Trace.from_dict(case["trace"]))
        for _name, case in cases
    ]
    durations = []
    for _ in range(iterations):
        start = time.perf_counter()
        for policy, trace in parsed:
            validate_trace(trace, policy)
        durations.append((time.perf_counter() - start) * 1000.0 / len(parsed))
    tracemalloc.start()
    for policy, trace in parsed:
        validate_trace(trace, policy)
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "traces": len(parsed),
        "iterations": iterations,
        "median_ms_per_trace": round(statistics.median(durations), 3),
        "p95_ms_per_trace": round(sorted(durations)[int(len(durations) * 0.95) - 1], 3),
        "peak_memory_kb": round(peak / 1024.0, 1),
    }


def run_metamorphic(cases):
    """Invariances that must hold for every case:

    1. renaming the trace_id must not change any finding;
    2. adding unrelated step metadata must not change any finding;
    3. round-tripping the policy through JSON with sorted keys must not
       change any finding (no hidden key-order dependence).
    """
    failures = []
    for name, case in cases:
        policy = Policy.from_dict(case["policy"])
        base_report = validate_trace(Trace.from_dict(case["trace"]), policy)
        base = finding_multiset(base_report)

        renamed = copy.deepcopy(case["trace"])
        renamed["trace_id"] = "renamed-" + renamed["trace_id"]
        if finding_multiset(validate_trace(Trace.from_dict(renamed), policy)) != base:
            failures.append(f"{name}: trace_id rename changed findings")

        with_meta = copy.deepcopy(case["trace"])
        for step in with_meta["steps"]:
            step["metadata"] = {"bench": "noise"}
        if finding_multiset(validate_trace(Trace.from_dict(with_meta), policy)) != base:
            failures.append(f"{name}: step metadata changed findings")

        round_tripped = json.loads(json.dumps(case["policy"], sort_keys=True))
        policy2 = Policy.from_dict(round_tripped)
        if finding_multiset(validate_trace(Trace.from_dict(case["trace"]), policy2)) != base:
            failures.append(f"{name}: policy key order changed findings")
    return {"checks": len(cases) * 3, "failures": failures}


def run_adapter_equivalence():
    """The same conversation via openai-chat and anthropic-messages adapters
    must produce identical rule verdicts under the same policy."""
    policy = Policy.from_dict(
        {
            "policy_id": "adapter-equivalence",
            "allowed_tools": {
                "lookup_order": {"required_arguments": {"order_id": "str"}},
                "issue_refund": {
                    "required_arguments": {"order_id": "str", "amount": "float"},
                    "side_effect": True,
                },
            },
            "sequence": {"call_order": ["lookup_order", "issue_refund"]},
            "completion": {"require_final_response": True},
        }
    )
    openai_raw = json.loads((FIXTURES / "openai_chat_refund.json").read_text(encoding="utf-8"))
    anthropic_raw = json.loads(
        (FIXTURES / "anthropic_messages_refund.json").read_text(encoding="utf-8")
    )
    openai_report = validate_trace(
        Trace.from_dict(normalize(openai_raw, "openai-chat", "a")), policy
    )
    anthropic_report = validate_trace(
        Trace.from_dict(normalize(anthropic_raw, "anthropic-messages", "b")), policy
    )
    openai_rules = sorted(f.rule_id for f in openai_report.findings)
    anthropic_rules = sorted(f.rule_id for f in anthropic_report.findings)
    return {
        "equivalent": openai_rules == anthropic_rules
        and openai_report.passed == anthropic_report.passed,
        "openai_rules": openai_rules,
        "anthropic_rules": anthropic_rules,
    }


def run_regression_scenarios(cases):
    """The regression gate must fail on seeded regressions and pass on no-ops."""
    by_id = {case["case_id"]: case for _name, case in cases}
    base_case = by_id["correct_baseline"]

    def report_json(case):
        case_policy = Policy.from_dict(case["policy"])
        trace = copy.deepcopy(case["trace"])
        trace["trace_id"] = "scenario-trace"
        return render_json([validate_trace(Trace.from_dict(trace), case_policy)])

    baseline = report_json(base_case)
    outcomes = {}
    # no-op: identical run must pass the gate
    passed, _ = evaluate_gate(compare_reports(baseline, report_json(base_case)))
    outcomes["identical_run_passes"] = passed
    # seeded regressions must fail the gate
    for case_id in ("duplicate_side_effect", "incorrect_call_ordering", "secret_exposure"):
        candidate = report_json(by_id[case_id])
        gate_passed, reasons = evaluate_gate(compare_reports(baseline, candidate))
        outcomes[f"{case_id}_gate_fails"] = (not gate_passed) and bool(reasons)
    # a fix must pass the gate (bad baseline -> good candidate)
    bad_baseline = report_json(by_id["duplicate_side_effect"])
    gate_passed, _ = evaluate_gate(compare_reports(bad_baseline, report_json(base_case)))
    outcomes["fix_passes_gate"] = gate_passed
    ok = all(outcomes.values())
    return {"ok": ok, "outcomes": outcomes}


def write_results(md_path, detection, determinism, performance, metamorphic,
                  adapters_result, regression, environment):
    lines = []
    lines.append("# Benchmark Results")
    lines.append("")
    lines.append("Generated by `python benchmarks/run.py --write`. "
                 "Do not edit by hand; rerun the benchmark instead.")
    lines.append("")
    lines.append("## Environment")
    lines.append("")
    for key, value in environment.items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## Detection quality (seeded failure suite)")
    lines.append("")
    lines.append(f"- cases: {detection['cases']} "
                 f"({detection['cases_ok']} fully correct)")
    lines.append(f"- expected findings detected (TP): {detection['tp']}")
    lines.append(f"- false positives (FP): {detection['fp']}")
    lines.append(f"- false negatives (FN): {detection['fn']}")
    lines.append(f"- precision: {detection['precision']:.4f}")
    lines.append(f"- recall: {detection['recall']:.4f}")
    lines.append("")
    lines.append("Scope note: these numbers measure detection of *seeded, "
                 "deterministically detectable* failure modes as defined in "
                 "BENCHMARK-METHODOLOGY.md. They are not a claim about "
                 "semantic failures (fabricated tool output, unsupported "
                 "claims), which are out of scope for the deterministic core.")
    lines.append("")
    lines.append("| Case | Category | Result | TP | FP | FN |")
    lines.append("|---|---|---|---|---|---|")
    for entry in detection["per_case"]:
        status = "ok" if entry["ok"] else "FAIL"
        lines.append(
            f"| {entry['case']} | {entry['category']} | {status} | "
            f"{entry['tp']} | {entry['fp']} | {entry['fn']} |"
        )
    lines.append("")
    lines.append("## Determinism")
    lines.append("")
    lines.append(f"- repeated full-suite runs byte-identical: "
                 f"{determinism['byte_identical']}")
    lines.append("")
    lines.append("## Performance")
    lines.append("")
    lines.append(f"- traces per run: {performance['traces']}; "
                 f"iterations: {performance['iterations']}")
    lines.append(f"- median validation time: "
                 f"{performance['median_ms_per_trace']} ms/trace "
                 f"(budget: {TIME_BUDGET_MS_PER_TRACE} ms)")
    lines.append(f"- p95: {performance['p95_ms_per_trace']} ms/trace")
    lines.append(f"- peak traced memory for one full-suite pass: "
                 f"{performance['peak_memory_kb']} KB")
    lines.append("")
    lines.append("## Metamorphic invariances")
    lines.append("")
    lines.append(f"- checks: {metamorphic['checks']}; "
                 f"failures: {len(metamorphic['failures'])}")
    for failure in metamorphic["failures"]:
        lines.append(f"  - {failure}")
    lines.append("")
    lines.append("## Adapter equivalence")
    lines.append("")
    lines.append(f"- openai-chat and anthropic-messages transcripts of the same "
                 f"conversation produce identical verdicts: "
                 f"{adapters_result['equivalent']}")
    lines.append("")
    lines.append("## Regression gate scenarios")
    lines.append("")
    for key, value in regression["outcomes"].items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                        help="rewrite BENCHMARK-RESULTS.md with this run's numbers")
    parser.add_argument("--iterations", type=int, default=20)
    args = parser.parse_args()

    cases = load_cases()
    detection = run_detection(cases)
    determinism = run_determinism(cases)
    performance = run_performance(cases, iterations=args.iterations)
    metamorphic = run_metamorphic(cases)
    adapters_result = run_adapter_equivalence()
    regression = run_regression_scenarios(cases)

    environment = {
        "harness version": __version__,
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
    }

    print(json.dumps({
        "detection": {k: v for k, v in detection.items() if k != "per_case"},
        "determinism": determinism,
        "performance": performance,
        "metamorphic": {"checks": metamorphic["checks"],
                        "failures": metamorphic["failures"]},
        "adapter_equivalence": adapters_result["equivalent"],
        "regression_scenarios": regression["outcomes"],
    }, indent=2))

    failures = []
    if detection["precision"] < 1.0:
        failures.append(f"precision {detection['precision']:.4f} < 1.0")
    if detection["recall"] < 1.0:
        failures.append(f"recall {detection['recall']:.4f} < 1.0")
    if detection["cases_ok"] != detection["cases"]:
        bad = [c["case"] for c in detection["per_case"] if not c["ok"]]
        failures.append(f"cases with wrong verdicts/findings: {bad}")
    if not determinism["byte_identical"]:
        failures.append("reports are not byte-identical across runs")
    if performance["median_ms_per_trace"] > TIME_BUDGET_MS_PER_TRACE:
        failures.append(
            f"median {performance['median_ms_per_trace']}ms/trace exceeds "
            f"{TIME_BUDGET_MS_PER_TRACE}ms budget"
        )
    if metamorphic["failures"]:
        failures.append(f"metamorphic failures: {metamorphic['failures']}")
    if not adapters_result["equivalent"]:
        failures.append("adapter verdicts diverge for the same conversation")
    if not regression["ok"]:
        failures.append(f"regression scenarios failed: {regression['outcomes']}")

    if args.write:
        write_results(RESULTS_MD, detection, determinism, performance,
                      metamorphic, adapters_result, regression, environment)
        print(f"\nwrote {RESULTS_MD}")

    if failures:
        print("\nBENCHMARK THRESHOLD FAILURES:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print("\nall benchmark thresholds met")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
