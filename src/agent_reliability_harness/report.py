"""Rendering of TraceReport objects to console text, JSON, and Markdown."""

from __future__ import annotations

import json
from typing import Any

from agent_reliability_harness.models import Finding, TraceReport

_SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def _sorted_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: (_SEVERITY_ORDER.get(f.severity, 9), f.category, f.step_id or ""))


def render_console(reports: list[TraceReport]) -> str:
    """Render a batch of reports as a human-readable console summary."""
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("AGENT RELIABILITY HARNESS - VALIDATION REPORT")
    lines.append("=" * 72)

    for report in reports:
        status = "PASS" if report.passed else "FAIL"
        lines.append("")
        lines.append(f"[{status}] {report.trace_id}  (agent={report.agent_name}, workflow={report.workflow})")
        lines.append(
            f"  score={report.score:.1f}/100  policy={report.policy_id}  "
            f"latency={report.total_latency_ms:.0f}ms  cost=${report.total_cost_usd:.4f}"
        )
        if report.citation_coverage is not None:
            lines.append(f"  citation_coverage={report.citation_coverage:.0%}")
        if not report.findings:
            lines.append("  no findings")
        else:
            for finding in _sorted_findings(report.findings):
                loc = f" (step={finding.step_id})" if finding.step_id else ""
                lines.append(
                    f"  - [{finding.severity.upper():7}] [{finding.category:9}] "
                    f"{finding.message}{loc}"
                )

    lines.append("")
    lines.append("-" * 72)
    total = len(reports)
    passed = sum(1 for r in reports if r.passed)
    avg_score = sum(r.score for r in reports) / total if total else 0.0
    lines.append(f"SUMMARY: {passed}/{total} traces passed, average score {avg_score:.1f}/100")
    lines.append("-" * 72)
    return "\n".join(lines)


def render_json(reports: list[TraceReport]) -> dict[str, Any]:
    """Render a batch of reports as a JSON-serializable dict."""
    total = len(reports)
    passed = sum(1 for r in reports if r.passed)
    avg_score = sum(r.score for r in reports) / total if total else 0.0
    return {
        "summary": {
            "total_traces": total,
            "passed_traces": passed,
            "failed_traces": total - passed,
            "average_score": round(avg_score, 2),
        },
        "reports": [r.to_dict() for r in reports],
    }


def render_json_str(reports: list[TraceReport], indent: int = 2) -> str:
    return json.dumps(render_json(reports), indent=indent)


def render_markdown(reports: list[TraceReport]) -> str:
    """Render a batch of reports as a Markdown report suitable for a PR comment."""
    total = len(reports)
    passed = sum(1 for r in reports if r.passed)
    avg_score = sum(r.score for r in reports) / total if total else 0.0

    lines: list[str] = []
    lines.append("# Agent Reliability Harness Report")
    lines.append("")
    lines.append(f"**{passed}/{total} traces passed** - average score **{avg_score:.1f}/100**")
    lines.append("")
    lines.append("| Trace | Agent | Workflow | Status | Score | Latency (ms) | Cost ($) | Citation Coverage |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for report in reports:
        status = "PASS" if report.passed else "FAIL"
        coverage = f"{report.citation_coverage:.0%}" if report.citation_coverage is not None else "n/a"
        lines.append(
            f"| {report.trace_id} | {report.agent_name} | {report.workflow} | {status} | "
            f"{report.score:.1f} | {report.total_latency_ms:.0f} | {report.total_cost_usd:.4f} | {coverage} |"
        )

    for report in reports:
        if not report.findings:
            continue
        lines.append("")
        lines.append(f"## Findings: {report.trace_id}")
        lines.append("")
        lines.append("| Severity | Category | Step | Message |")
        lines.append("|---|---|---|---|")
        for finding in _sorted_findings(report.findings):
            step = finding.step_id or "-"
            message = finding.message.replace("|", "\\|")
            lines.append(f"| {finding.severity} | {finding.category} | {step} | {message} |")

    return "\n".join(lines) + "\n"
