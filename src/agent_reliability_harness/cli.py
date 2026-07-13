"""argparse-based command line interface.

Example:

    arh validate --policy samples/policy.json samples/traces/*.json \\
        --json-out out/report.json --md-out out/report.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent_reliability_harness.models import Policy, Trace, TraceReport
from agent_reliability_harness.report import render_console, render_json_str, render_markdown
from agent_reliability_harness.validator import DEFAULT_FAIL_UNDER, validate_trace


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: failed to parse JSON from {path}: {exc}") from exc
    except OSError as exc:
        raise SystemExit(f"error: failed to read {path}: {exc}") from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arh",
        description=(
            "Validate agent tool-use traces against a reliability policy: "
            "tool-call schemas, latency/cost budgets, unsafe-pattern "
            "detection, and citation/grounding coverage."
        ),
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
        "--fail-under",
        type=float,
        default=DEFAULT_FAIL_UNDER,
        help=f"Minimum passing score, 0-100 (default: {DEFAULT_FAIL_UNDER})",
    )
    validate_parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Write the full JSON report to this path",
    )
    validate_parser.add_argument(
        "--md-out",
        type=Path,
        default=None,
        help="Write a Markdown report to this path",
    )
    validate_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress console output (still writes --json-out/--md-out if given)",
    )

    return parser


def _run_validate(args: argparse.Namespace) -> int:
    policy_raw = _load_json(args.policy)
    try:
        policy = Policy.from_dict(policy_raw)
    except ValueError as exc:
        raise SystemExit(f"error: invalid policy {args.policy}: {exc}") from exc

    reports: list[TraceReport] = []
    for trace_path in args.traces:
        raw = _load_json(trace_path)
        try:
            trace = Trace.from_dict(raw)
        except ValueError as exc:
            raise SystemExit(f"error: invalid trace {trace_path}: {exc}") from exc
        reports.append(validate_trace(trace, policy, fail_under=args.fail_under))

    if not args.quiet:
        print(render_console(reports))

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(render_json_str(reports), encoding="utf-8")
        if not args.quiet:
            print(f"\nJSON report written to {args.json_out}")

    if args.md_out:
        args.md_out.parent.mkdir(parents=True, exist_ok=True)
        args.md_out.write_text(render_markdown(reports), encoding="utf-8")
        if not args.quiet:
            print(f"Markdown report written to {args.md_out}")

    return 0 if all(r.passed for r in reports) else 1


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate":
        return _run_validate(args)

    parser.error(f"unknown command: {args.command}")
    return 2  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
