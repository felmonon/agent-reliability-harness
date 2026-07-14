"""Rendering of TraceReport objects to console text, JSON, Markdown, JUnit XML,
and SARIF.

All renderers are deterministic: identical reports produce byte-identical
output. No renderer reads a clock, environment, or random source.
"""

from __future__ import annotations

import json
from typing import Any
from xml.sax.saxutils import escape, quoteattr

from agent_reliability_harness.models import Finding, TraceReport
from agent_reliability_harness.rules import UNKNOWN_RULE_ID, get_rule

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
                rule = f" {finding.rule_id}:" if finding.rule_id else ""
                lines.append(
                    f"  - [{finding.severity.upper():7}] [{finding.category:9}]"
                    f"{rule} {finding.message}{loc}"
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
    """Render a batch of reports as a JSON-serializable dict.

    This structure doubles as the regression baseline format consumed by
    ``arh compare`` (see docs/regression-testing.md).
    """
    total = len(reports)
    passed = sum(1 for r in reports if r.passed)
    avg_score = sum(r.score for r in reports) / total if total else 0.0
    return {
        "schema_version": "1",
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
        lines.append("| Severity | Rule | Category | Step | Message |")
        lines.append("|---|---|---|---|---|")
        for finding in _sorted_findings(report.findings):
            step = finding.step_id or "-"
            rule = finding.rule_id or "-"
            message = finding.message.replace("|", "\\|")
            lines.append(
                f"| {finding.severity} | {rule} | {finding.category} | {step} | {message} |"
            )

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# JUnit XML
# ---------------------------------------------------------------------------


def render_junit(reports: list[TraceReport]) -> str:
    """Render reports as JUnit XML (one testcase per trace).

    The output targets the de facto JUnit schema understood by CI systems:
    ``<testsuites>`` / ``<testsuite>`` / ``<testcase>`` with ``<failure>``
    elements for failing traces. ``time`` is the trace's total latency in
    seconds (the harness itself does not time anything, so reports stay
    deterministic).
    """
    total = len(reports)
    failures = sum(1 for r in reports if not r.passed)
    lines: list[str] = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(
        f'<testsuites name="agent-reliability-harness" tests="{total}" '
        f'failures="{failures}">'
    )
    lines.append(
        f'  <testsuite name="agent-reliability-harness" tests="{total}" '
        f'failures="{failures}" errors="0" skipped="0">'
    )
    for report in reports:
        classname = quoteattr(f"{report.agent_name}.{report.workflow}")
        name = quoteattr(report.trace_id)
        time = f"{report.total_latency_ms / 1000.0:.3f}"
        if report.passed:
            lines.append(
                f"    <testcase classname={classname} name={name} time=\"{time}\"/>"
            )
            continue
        lines.append(
            f"    <testcase classname={classname} name={name} time=\"{time}\">"
        )
        error_findings = [f for f in report.findings if f.severity == "error"]
        summary = (
            f"score={report.score:.1f}/100; "
            f"{len(error_findings)} error finding(s)"
        )
        detail_lines = [
            f"[{f.severity.upper()}] [{f.rule_id or f.category}] {f.message}"
            + (f" (step={f.step_id})" if f.step_id else "")
            for f in _sorted_findings(report.findings)
        ]
        lines.append(
            f"      <failure message={quoteattr(summary)} type=\"PolicyViolation\">"
            f"{escape(chr(10).join(detail_lines))}</failure>"
        )
        lines.append("    </testcase>")
    lines.append("  </testsuite>")
    lines.append("</testsuites>")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# SARIF 2.1.0
# ---------------------------------------------------------------------------

_SARIF_LEVELS = {"error": "error", "warning": "warning", "info": "note"}


def render_sarif(reports: list[TraceReport], tool_version: str) -> dict[str, Any]:
    """Render reports as a SARIF 2.1.0 document.

    Each finding becomes a SARIF ``result``. The artifact location is the
    trace's source file when known (``TraceReport.source_path``), so GitHub
    code scanning and other SARIF consumers can annotate the trace fixture
    that produced the finding. Findings without a registered rule fall back
    to the ``ARH-000`` placeholder rule.
    """
    rule_ids = sorted(
        {(f.rule_id or UNKNOWN_RULE_ID) for report in reports for f in report.findings}
    )
    rules_json = []
    for rule_id in rule_ids:
        rule = get_rule(rule_id)
        rules_json.append(
            {
                "id": rule_id,
                "name": rule_id.replace("-", ""),
                "shortDescription": {"text": rule.summary},
                "helpUri": rule.help_uri,
                "defaultConfiguration": {
                    "level": _SARIF_LEVELS.get(rule.default_severity, "warning")
                },
                "properties": {"category": rule.category},
            }
        )
    rule_index = {rule_id: index for index, rule_id in enumerate(rule_ids)}

    results = []
    for report in reports:
        artifact_uri = report.source_path or f"traces/{report.trace_id}.json"
        artifact_uri = artifact_uri.replace("\\", "/")
        for finding in _sorted_findings(report.findings):
            rule_id = finding.rule_id or UNKNOWN_RULE_ID
            message = finding.message
            if finding.step_id:
                message = f"{message} (trace '{report.trace_id}', step '{finding.step_id}')"
            else:
                message = f"{message} (trace '{report.trace_id}')"
            location: dict[str, Any] = {
                "physicalLocation": {
                    "artifactLocation": {"uri": artifact_uri},
                }
            }
            if finding.step_id:
                location["logicalLocations"] = [
                    {"name": finding.step_id, "kind": "member"}
                ]
            results.append(
                {
                    "ruleId": rule_id,
                    "ruleIndex": rule_index[rule_id],
                    "level": _SARIF_LEVELS.get(finding.severity, "warning"),
                    "message": {"text": message},
                    "locations": [location],
                    "partialFingerprints": {
                        "arhFingerprint/v1": (
                            f"{report.trace_id}|{rule_id}|{finding.category}|"
                            f"{finding.step_id or ''}"
                        )
                    },
                }
            )

    return {
        "$schema": (
            "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/"
            "Schemata/sarif-schema-2.1.0.json"
        ),
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "agent-reliability-harness",
                        "informationUri": (
                            "https://github.com/felmonon/agent-reliability-harness"
                        ),
                        "version": tool_version,
                        "rules": rules_json,
                    }
                },
                "results": results,
            }
        ],
    }


def render_sarif_str(reports: list[TraceReport], tool_version: str, indent: int = 2) -> str:
    return json.dumps(render_sarif(reports, tool_version), indent=indent)
