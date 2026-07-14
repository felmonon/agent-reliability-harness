"""argparse-based command line interface.

Examples:

    arh validate --policy samples/policy.json samples/traces/*.json \\
        --json-out out/report.json --md-out out/report.md

    arh compare --baseline baseline.json --candidate candidate.json \\
        --fail-on regressions --md-out compare.md

Exit codes:

- ``0``: validation passed / regression gate passed;
- ``1``: at least one trace failed, the gate failed, or an input file was
  invalid (reported as a clean ``error: ...`` message);
- ``2``: command-line usage errors (argparse).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from agent_reliability_harness import __version__
from agent_reliability_harness.adapters import FORMAT_AUTO, FORMATS, normalize
from agent_reliability_harness.models import Policy, Trace, TraceReport
from agent_reliability_harness.regression import (
    GATE_CHOICES,
    compare_reports,
    evaluate_gate,
    render_compare_console,
    render_compare_json_str,
    render_compare_markdown,
)
from agent_reliability_harness.report import (
    render_console,
    render_json,
    render_json_str,
    render_junit,
    render_markdown,
    render_sarif_str,
)
from agent_reliability_harness.validator import DEFAULT_FAIL_UNDER, validate_trace


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: failed to parse JSON from {path}: {exc}") from exc
    except RecursionError:
        raise SystemExit(
            f"error: JSON in {path} is nested too deeply to parse safely"
        ) from None
    except OSError as exc:
        raise SystemExit(f"error: failed to read {path}: {exc}") from exc


def _usage_error(message: str) -> SystemExit:
    """A misuse of CLI flags/arguments: print to stderr, exit with code 2."""
    print(f"error: {message}", file=sys.stderr)
    return SystemExit(2)


def _fail_under_value(text: str) -> float:
    try:
        value = float(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid number: {text!r}") from exc
    if value != value or not (0.0 <= value <= 100.0):  # NaN-safe bounds check
        raise argparse.ArgumentTypeError("fail-under must be between 0 and 100")
    return value


def _write_text(path: Path, content: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"error: failed to write {path}: {exc}") from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arh",
        description=(
            "Validate agent tool-use traces against a reliability policy "
            "(tool-call schemas, trajectory rules, budgets, unsafe patterns, "
            "grounding) and compare runs against a saved baseline."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate", help="Validate one or more trace files against a policy"
    )
    validate_parser.add_argument(
        "traces",
        nargs="+",
        type=Path,
        help="Path(s) to trace JSON file(s) to validate",
    )
    validate_parser.add_argument(
        "--policy",
        type=Path,
        required=True,
        help="Path to the policy JSON file",
    )
    validate_parser.add_argument(
        "--format",
        choices=(FORMAT_AUTO, *FORMATS),
        default=FORMAT_AUTO,
        help=(
            "Trace input format. 'auto' (default) detects between the canonical "
            "'arh' format, 'openai-chat' message lists, 'anthropic-messages' "
            "conversations, and 'cohere-chat' message lists."
        ),
    )
    validate_parser.add_argument(
        "--fail-under",
        type=_fail_under_value,
        default=DEFAULT_FAIL_UNDER,
        help=f"Minimum passing score, 0-100 (default: {DEFAULT_FAIL_UNDER})",
    )
    validate_parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help=(
            "Write the full JSON report to this path (also serves as the "
            "regression baseline consumed by 'arh compare')"
        ),
    )
    validate_parser.add_argument(
        "--md-out",
        type=Path,
        default=None,
        help="Write a Markdown report to this path",
    )
    validate_parser.add_argument(
        "--junit-out",
        type=Path,
        default=None,
        help="Write a JUnit XML report to this path",
    )
    validate_parser.add_argument(
        "--sarif-out",
        type=Path,
        default=None,
        help="Write a SARIF 2.1.0 report to this path",
    )
    validate_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress console output (still writes report files if requested)",
    )

    compare_parser = subparsers.add_parser(
        "compare",
        help=(
            "Compare a candidate run against a saved baseline report and "
            "apply a regression gate"
        ),
    )
    compare_parser.add_argument(
        "--baseline",
        type=Path,
        required=True,
        help="Baseline JSON report (produced by 'arh validate --json-out')",
    )
    compare_parser.add_argument(
        "--candidate",
        type=Path,
        default=None,
        help=(
            "Candidate JSON report to compare. Alternatively pass --policy and "
            "trace files to validate the candidate in one step."
        ),
    )
    compare_parser.add_argument(
        "traces",
        nargs="*",
        type=Path,
        help="Candidate trace file(s) (requires --policy; cannot be combined with --candidate)",
    )
    compare_parser.add_argument(
        "--policy",
        type=Path,
        default=None,
        help="Policy for validating candidate traces (with trace arguments)",
    )
    compare_parser.add_argument(
        "--format",
        choices=(FORMAT_AUTO, *FORMATS),
        default=FORMAT_AUTO,
        help="Trace input format for candidate traces (default: auto)",
    )
    compare_parser.add_argument(
        "--fail-under",
        type=_fail_under_value,
        default=DEFAULT_FAIL_UNDER,
        help=(
            "Minimum passing score for candidate traces when validating with "
            f"--policy (default: {DEFAULT_FAIL_UNDER})"
        ),
    )
    compare_parser.add_argument(
        "--fail-on",
        choices=GATE_CHOICES,
        default="regressions",
        help=(
            "Gate mode: 'regressions' (default) fails on new error findings, "
            "pass->fail transitions, and added failing traces; 'failures' fails "
            "on any candidate failure; 'never' always exits 0."
        ),
    )
    compare_parser.add_argument(
        "--max-score-drop",
        type=float,
        default=None,
        help=(
            "With --fail-on regressions: also fail if any trace's score drops "
            "by more than this many points"
        ),
    )
    compare_parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Write the comparison JSON to this path",
    )
    compare_parser.add_argument(
        "--md-out",
        type=Path,
        default=None,
        help="Write a Markdown comparison (suitable for a PR comment) to this path",
    )
    compare_parser.add_argument(
        "--candidate-json-out",
        type=Path,
        default=None,
        help=(
            "When validating candidate traces with --policy, also write the "
            "candidate validation report here (the next baseline)"
        ),
    )
    compare_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress console output (still writes report files if requested)",
    )

    return parser


def _validate_traces(
    trace_paths: list[Path], policy: Policy, fmt: str, fail_under: float
) -> list[TraceReport]:
    reports: list[TraceReport] = []
    for trace_path in trace_paths:
        raw = _load_json(trace_path)
        try:
            canonical = normalize(raw, fmt, fallback_trace_id=trace_path.stem)
            trace = Trace.from_dict(canonical)
        except ValueError as exc:
            raise SystemExit(f"error: invalid trace {trace_path}: {exc}") from exc
        try:
            report = validate_trace(trace, policy, fail_under=fail_under)
        except ValueError as exc:
            raise SystemExit(f"error: validating {trace_path}: {exc}") from exc
        report.source_path = str(trace_path)
        reports.append(report)
    return reports


def _load_policy(path: Path) -> Policy:
    policy_raw = _load_json(path)
    try:
        return Policy.from_dict(policy_raw)
    except ValueError as exc:
        raise SystemExit(f"error: invalid policy {path}: {exc}") from exc


def _run_validate(args: argparse.Namespace) -> int:
    policy = _load_policy(args.policy)
    reports = _validate_traces(args.traces, policy, args.format, args.fail_under)

    if not args.quiet:
        print(render_console(reports))

    if args.json_out:
        _write_text(args.json_out, render_json_str(reports))
        if not args.quiet:
            print(f"\nJSON report written to {args.json_out}")

    if args.md_out:
        _write_text(args.md_out, render_markdown(reports))
        if not args.quiet:
            print(f"Markdown report written to {args.md_out}")

    if args.junit_out:
        _write_text(args.junit_out, render_junit(reports))
        if not args.quiet:
            print(f"JUnit report written to {args.junit_out}")

    if args.sarif_out:
        _write_text(args.sarif_out, render_sarif_str(reports, __version__))
        if not args.quiet:
            print(f"SARIF report written to {args.sarif_out}")

    return 0 if all(r.passed for r in reports) else 1


def _run_compare(args: argparse.Namespace) -> int:
    baseline_json = _load_json(args.baseline)

    if args.candidate is not None and (args.traces or args.policy):
        raise _usage_error(
            "pass either --candidate REPORT or --policy POLICY with trace files, "
            "not both"
        )

    if args.candidate is not None:
        candidate_json = _load_json(args.candidate)
    elif args.traces:
        if args.policy is None:
            raise _usage_error(
                "candidate trace files require --policy (or use --candidate with a "
                "pre-computed report)"
            )
        policy = _load_policy(args.policy)
        reports = _validate_traces(args.traces, policy, args.format, args.fail_under)
        candidate_json = render_json(reports)
        if args.candidate_json_out:
            _write_text(args.candidate_json_out, render_json_str(reports))
            if not args.quiet:
                print(f"Candidate report written to {args.candidate_json_out}")
    else:
        raise _usage_error(
            "nothing to compare; pass --candidate REPORT or --policy POLICY with "
            "candidate trace files"
        )

    try:
        result = compare_reports(baseline_json, candidate_json)
        gate_passed, gate_reasons = evaluate_gate(
            result, fail_on=args.fail_on, max_score_drop=args.max_score_drop
        )
    except ValueError as exc:
        raise SystemExit(f"error: {exc}") from exc

    if not args.quiet:
        print(render_compare_console(result, gate_passed, gate_reasons))

    if args.json_out:
        _write_text(args.json_out, render_compare_json_str(result, gate_passed, gate_reasons))
        if not args.quiet:
            print(f"\nComparison JSON written to {args.json_out}")

    if args.md_out:
        _write_text(args.md_out, render_compare_markdown(result, gate_passed, gate_reasons))
        if not args.quiet:
            print(f"Comparison Markdown written to {args.md_out}")

    return 0 if gate_passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate":
        return _run_validate(args)
    if args.command == "compare":
        return _run_compare(args)

    parser.error(f"unknown command: {args.command}")
    return 2  # pragma: no cover - parser.error() exits with code 2


if __name__ == "__main__":
    sys.exit(main())
