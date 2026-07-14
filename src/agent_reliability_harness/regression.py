"""Baseline-versus-candidate regression comparison.

The comparison consumes two JSON validation reports (the exact structure
written by ``arh validate --json-out``) and produces a deterministic diff:

- newly introduced findings (present in candidate, absent in baseline);
- resolved findings (present in baseline, absent in candidate);
- per-trace pass/fail transitions and score / latency / cost deltas;
- traces added to or removed from the suite;
- an aggregate summary suitable for a CI gate.

Finding identity ("fingerprint") is ``(trace_id, rule_id, category,
step_id)``. Messages are deliberately excluded: they contain measured values
(latencies, costs) that legitimately vary between runs. Reports produced by
v0.1.x (no ``rule_id`` on findings) are supported through a second matching
pass that ignores ``rule_id``; see COMPATIBILITY.md.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Optional

GATE_CHOICES = ("regressions", "failures", "never")


@dataclass
class FindingRef:
    """A finding as it appears in a JSON report, plus its trace."""

    trace_id: str
    severity: str
    category: str
    message: str
    step_id: Optional[str]
    rule_id: str

    @staticmethod
    def from_json(trace_id: str, raw: dict[str, Any]) -> "FindingRef":
        return FindingRef(
            trace_id=trace_id,
            severity=str(raw.get("severity", "")),
            category=str(raw.get("category", "")),
            message=str(raw.get("message", "")),
            step_id=raw.get("step_id"),
            rule_id=str(raw.get("rule_id", "") or ""),
        )

    def fingerprint(self) -> tuple[str, str, str, str]:
        return (self.trace_id, self.rule_id, self.category, self.step_id or "")

    def loose_fingerprint(self) -> tuple[str, str, str]:
        """Fingerprint ignoring rule_id, for v0.1.x baselines."""
        return (self.trace_id, self.category, self.step_id or "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "step_id": self.step_id,
            "rule_id": self.rule_id,
        }


@dataclass
class TraceDelta:
    """Per-trace comparison between baseline and candidate."""

    trace_id: str
    in_baseline: bool
    in_candidate: bool
    baseline_passed: Optional[bool] = None
    candidate_passed: Optional[bool] = None
    baseline_score: Optional[float] = None
    candidate_score: Optional[float] = None
    score_delta: Optional[float] = None
    latency_delta_ms: Optional[float] = None
    cost_delta_usd: Optional[float] = None
    new_findings: list[FindingRef] = field(default_factory=list)
    resolved_findings: list[FindingRef] = field(default_factory=list)

    @property
    def status_change(self) -> str:
        if not self.in_baseline:
            return "added"
        if not self.in_candidate:
            return "removed"
        if self.baseline_passed and not self.candidate_passed:
            return "pass->fail"
        if not self.baseline_passed and self.candidate_passed:
            return "fail->pass"
        return "unchanged"

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "status_change": self.status_change,
            "baseline_passed": self.baseline_passed,
            "candidate_passed": self.candidate_passed,
            "baseline_score": self.baseline_score,
            "candidate_score": self.candidate_score,
            "score_delta": round(self.score_delta, 2) if self.score_delta is not None else None,
            "latency_delta_ms": self.latency_delta_ms,
            "cost_delta_usd": (
                round(self.cost_delta_usd, 6) if self.cost_delta_usd is not None else None
            ),
            "new_findings": [f.to_dict() for f in self.new_findings],
            "resolved_findings": [f.to_dict() for f in self.resolved_findings],
        }


@dataclass
class ComparisonResult:
    """Full baseline-versus-candidate comparison."""

    traces: list[TraceDelta]
    baseline_policy_id: str
    candidate_policy_id: str

    @property
    def new_findings(self) -> list[FindingRef]:
        return [f for delta in self.traces for f in delta.new_findings]

    @property
    def resolved_findings(self) -> list[FindingRef]:
        return [f for delta in self.traces for f in delta.resolved_findings]

    @property
    def new_error_findings(self) -> list[FindingRef]:
        return [f for f in self.new_findings if f.severity == "error"]

    @property
    def pass_to_fail(self) -> list[TraceDelta]:
        return [d for d in self.traces if d.status_change == "pass->fail"]

    @property
    def fail_to_pass(self) -> list[TraceDelta]:
        return [d for d in self.traces if d.status_change == "fail->pass"]

    @property
    def added_failing(self) -> list[TraceDelta]:
        return [
            d for d in self.traces if d.status_change == "added" and d.candidate_passed is False
        ]

    def max_score_drop(self) -> float:
        drops = [
            -d.score_delta
            for d in self.traces
            if d.score_delta is not None and d.score_delta < 0
        ]
        return max(drops, default=0.0)

    def summary(self) -> dict[str, Any]:
        compared = [d for d in self.traces if d.in_baseline and d.in_candidate]
        deltas = [d.score_delta for d in compared if d.score_delta is not None]
        return {
            "traces_compared": len(compared),
            "traces_added": sum(1 for d in self.traces if d.status_change == "added"),
            "traces_removed": sum(1 for d in self.traces if d.status_change == "removed"),
            "pass_to_fail": len(self.pass_to_fail),
            "fail_to_pass": len(self.fail_to_pass),
            "new_findings": len(self.new_findings),
            "new_error_findings": len(self.new_error_findings),
            "resolved_findings": len(self.resolved_findings),
            "average_score_delta": (
                round(sum(deltas) / len(deltas), 2) if deltas else 0.0
            ),
            "max_score_drop": round(self.max_score_drop(), 2),
        }


def _extract_reports(report_json: dict[str, Any], label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(report_json, dict) or "reports" not in report_json:
        raise ValueError(
            f"{label} report is not a validation report: expected an object with a "
            "'reports' key (produced by 'arh validate --json-out')"
        )
    reports = report_json["reports"]
    if not isinstance(reports, list):
        raise ValueError(f"{label} report field 'reports' must be a list")
    by_id: dict[str, dict[str, Any]] = {}
    for entry in reports:
        if not isinstance(entry, dict) or "trace_id" not in entry:
            raise ValueError(f"{label} report contains an entry without a 'trace_id'")
        trace_id = str(entry["trace_id"])
        if trace_id in by_id:
            raise ValueError(
                f"{label} report contains duplicate trace_id '{trace_id}'; "
                "regression comparison needs unique trace IDs"
            )
        by_id[trace_id] = entry
    return by_id


def _findings(trace_id: str, entry: dict[str, Any]) -> list[FindingRef]:
    return [
        FindingRef.from_json(trace_id, raw)
        for raw in entry.get("findings") or []
        if isinstance(raw, dict)
    ]


def _diff_findings(
    baseline: list[FindingRef], candidate: list[FindingRef]
) -> tuple[list[FindingRef], list[FindingRef]]:
    """Return (new, resolved) findings using two-tier fingerprint matching."""
    base_counter: Counter[tuple[str, str, str, str]] = Counter(
        f.fingerprint() for f in baseline
    )
    new: list[FindingRef] = []
    for finding in candidate:
        fp = finding.fingerprint()
        if base_counter[fp] > 0:
            base_counter[fp] -= 1
        else:
            new.append(finding)
    cand_counter: Counter[tuple[str, str, str, str]] = Counter(
        f.fingerprint() for f in candidate
    )
    resolved: list[FindingRef] = []
    for finding in baseline:
        fp = finding.fingerprint()
        if cand_counter[fp] > 0:
            cand_counter[fp] -= 1
        else:
            resolved.append(finding)

    # Second pass: match remaining findings ignoring rule_id, so baselines
    # produced by v0.1.x (which had no rule_id) do not report every finding
    # as both new and resolved.
    legacy_involved = any(not f.rule_id for f in baseline) or any(
        not f.rule_id for f in candidate
    )
    if legacy_involved and new and resolved:
        resolved_loose: Counter[tuple[str, str, str]] = Counter(
            f.loose_fingerprint() for f in resolved
        )
        still_new: list[FindingRef] = []
        matched_loose: Counter[tuple[str, str, str]] = Counter()
        for finding in new:
            fp3 = finding.loose_fingerprint()
            if resolved_loose[fp3] > 0:
                resolved_loose[fp3] -= 1
                matched_loose[fp3] += 1
            else:
                still_new.append(finding)
        still_resolved: list[FindingRef] = []
        for finding in resolved:
            fp3 = finding.loose_fingerprint()
            if matched_loose[fp3] > 0:
                matched_loose[fp3] -= 1
            else:
                still_resolved.append(finding)
        new, resolved = still_new, still_resolved

    ordering = lambda f: (f.trace_id, f.rule_id, f.category, f.step_id or "", f.message)
    return sorted(new, key=ordering), sorted(resolved, key=ordering)


def compare_reports(
    baseline_json: dict[str, Any], candidate_json: dict[str, Any]
) -> ComparisonResult:
    """Compare two validation-report JSON documents."""
    baseline = _extract_reports(baseline_json, "baseline")
    candidate = _extract_reports(candidate_json, "candidate")

    def _policy_id(reports: dict[str, dict[str, Any]]) -> str:
        ids = sorted({str(e.get("policy_id", "")) for e in reports.values()})
        return ids[0] if len(ids) == 1 else ",".join(i for i in ids if i)

    deltas: list[TraceDelta] = []
    for trace_id in sorted(set(baseline) | set(candidate)):
        base_entry = baseline.get(trace_id)
        cand_entry = candidate.get(trace_id)
        delta = TraceDelta(
            trace_id=trace_id,
            in_baseline=base_entry is not None,
            in_candidate=cand_entry is not None,
        )
        if base_entry is not None:
            delta.baseline_passed = bool(base_entry.get("passed"))
            delta.baseline_score = base_entry.get("score")
        if cand_entry is not None:
            delta.candidate_passed = bool(cand_entry.get("passed"))
            delta.candidate_score = cand_entry.get("score")
        if base_entry is not None and cand_entry is not None:
            if isinstance(delta.baseline_score, (int, float)) and isinstance(
                delta.candidate_score, (int, float)
            ):
                delta.score_delta = float(delta.candidate_score) - float(delta.baseline_score)
            base_latency = base_entry.get("total_latency_ms")
            cand_latency = cand_entry.get("total_latency_ms")
            if isinstance(base_latency, (int, float)) and isinstance(cand_latency, (int, float)):
                delta.latency_delta_ms = float(cand_latency) - float(base_latency)
            base_cost = base_entry.get("total_cost_usd")
            cand_cost = cand_entry.get("total_cost_usd")
            if isinstance(base_cost, (int, float)) and isinstance(cand_cost, (int, float)):
                delta.cost_delta_usd = float(cand_cost) - float(base_cost)
            delta.new_findings, delta.resolved_findings = _diff_findings(
                _findings(trace_id, base_entry), _findings(trace_id, cand_entry)
            )
        elif cand_entry is not None:
            # Added trace: its findings are all new.
            delta.new_findings, _ = _diff_findings([], _findings(trace_id, cand_entry))
        deltas.append(delta)

    return ComparisonResult(
        traces=deltas,
        baseline_policy_id=_policy_id(baseline),
        candidate_policy_id=_policy_id(candidate),
    )


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------


def evaluate_gate(
    result: ComparisonResult,
    fail_on: str = "regressions",
    max_score_drop: Optional[float] = None,
) -> tuple[bool, list[str]]:
    """Decide whether the comparison passes the CI gate.

    Returns ``(passed, reasons)``; ``reasons`` explains every gate failure.

    - ``regressions`` (default): fail on new error-severity findings, on any
      trace flipping pass->fail, on any *added* trace that fails, and - when
      ``max_score_drop`` is set - on any per-trace score drop above it.
    - ``failures``: fail if any candidate trace fails, regardless of the
      baseline (equivalent to ``arh validate`` semantics).
    - ``never``: always pass (report-only mode).
    """
    if fail_on not in GATE_CHOICES:
        raise ValueError(f"unknown fail_on '{fail_on}' (expected one of {GATE_CHOICES})")

    reasons: list[str] = []
    if fail_on == "never":
        return True, reasons

    if fail_on == "failures":
        failing = sorted(
            d.trace_id for d in result.traces if d.in_candidate and d.candidate_passed is False
        )
        if failing:
            reasons.append(f"candidate has failing traces: {', '.join(failing)}")
        return not reasons, reasons

    new_errors = result.new_error_findings
    if new_errors:
        reasons.append(
            f"{len(new_errors)} new error finding(s): "
            + ", ".join(
                sorted({f"{f.trace_id}:{f.rule_id or f.category}" for f in new_errors})
            )
        )
    for delta in result.pass_to_fail:
        reasons.append(f"trace '{delta.trace_id}' regressed from pass to fail")
    for delta in result.added_failing:
        reasons.append(f"added trace '{delta.trace_id}' fails")
    if max_score_drop is not None:
        for delta in result.traces:
            if delta.score_delta is not None and -delta.score_delta > max_score_drop:
                reasons.append(
                    f"trace '{delta.trace_id}' score dropped "
                    f"{-delta.score_delta:.2f} points (limit {max_score_drop:.2f})"
                )
    return not reasons, reasons


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def render_compare_json(
    result: ComparisonResult, gate_passed: bool, gate_reasons: list[str]
) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "baseline_policy_id": result.baseline_policy_id,
        "candidate_policy_id": result.candidate_policy_id,
        "summary": result.summary(),
        "gate": {"passed": gate_passed, "reasons": gate_reasons},
        "traces": [d.to_dict() for d in result.traces],
    }


def render_compare_json_str(
    result: ComparisonResult, gate_passed: bool, gate_reasons: list[str], indent: int = 2
) -> str:
    return json.dumps(render_compare_json(result, gate_passed, gate_reasons), indent=indent)


def render_compare_console(
    result: ComparisonResult, gate_passed: bool, gate_reasons: list[str]
) -> str:
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("AGENT RELIABILITY HARNESS - REGRESSION COMPARISON")
    lines.append("=" * 72)
    summary = result.summary()
    lines.append("")
    lines.append(
        f"traces compared={summary['traces_compared']}  "
        f"added={summary['traces_added']}  removed={summary['traces_removed']}"
    )
    lines.append(
        f"pass->fail={summary['pass_to_fail']}  fail->pass={summary['fail_to_pass']}  "
        f"new findings={summary['new_findings']} "
        f"(errors={summary['new_error_findings']})  "
        f"resolved={summary['resolved_findings']}"
    )
    lines.append(
        f"average score delta={summary['average_score_delta']:+.2f}  "
        f"max score drop={summary['max_score_drop']:.2f}"
    )
    for delta in result.traces:
        interesting = (
            delta.status_change != "unchanged"
            or delta.new_findings
            or delta.resolved_findings
            or (delta.score_delta or 0.0) != 0.0
        )
        if not interesting:
            continue
        lines.append("")
        score_part = ""
        if delta.baseline_score is not None and delta.candidate_score is not None:
            score_part = (
                f"  score {delta.baseline_score:.1f} -> {delta.candidate_score:.1f}"
                f" ({(delta.score_delta or 0.0):+.1f})"
            )
        lines.append(f"[{delta.status_change.upper():10}] {delta.trace_id}{score_part}")
        for finding in delta.new_findings:
            loc = f" (step={finding.step_id})" if finding.step_id else ""
            lines.append(
                f"  + NEW      [{finding.severity.upper():7}] "
                f"[{finding.rule_id or finding.category}] {finding.message}{loc}"
            )
        for finding in delta.resolved_findings:
            loc = f" (step={finding.step_id})" if finding.step_id else ""
            lines.append(
                f"  - RESOLVED [{finding.severity.upper():7}] "
                f"[{finding.rule_id or finding.category}] {finding.message}{loc}"
            )
    lines.append("")
    lines.append("-" * 72)
    lines.append(f"GATE: {'PASS' if gate_passed else 'FAIL'}")
    for reason in gate_reasons:
        lines.append(f"  - {reason}")
    lines.append("-" * 72)
    return "\n".join(lines)


def render_compare_markdown(
    result: ComparisonResult, gate_passed: bool, gate_reasons: list[str]
) -> str:
    summary = result.summary()
    lines: list[str] = []
    lines.append("# Agent Reliability Harness - Regression Comparison")
    lines.append("")
    lines.append(f"**Gate: {'PASS' if gate_passed else 'FAIL'}**")
    if gate_reasons:
        lines.append("")
        for reason in gate_reasons:
            lines.append(f"- {reason}")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Traces compared | {summary['traces_compared']} |")
    lines.append(f"| Added / removed | {summary['traces_added']} / {summary['traces_removed']} |")
    lines.append(f"| Pass to fail | {summary['pass_to_fail']} |")
    lines.append(f"| Fail to pass | {summary['fail_to_pass']} |")
    lines.append(
        f"| New findings (errors) | {summary['new_findings']} "
        f"({summary['new_error_findings']}) |"
    )
    lines.append(f"| Resolved findings | {summary['resolved_findings']} |")
    lines.append(f"| Average score delta | {summary['average_score_delta']:+.2f} |")
    lines.append(f"| Max score drop | {summary['max_score_drop']:.2f} |")

    changed = [
        d
        for d in result.traces
        if d.status_change != "unchanged" or d.new_findings or d.resolved_findings
    ]
    if changed:
        lines.append("")
        lines.append("## Changed traces")
        lines.append("")
        lines.append("| Trace | Change | Score | New findings | Resolved |")
        lines.append("|---|---|---|---|---|")
        for delta in changed:
            if delta.baseline_score is not None and delta.candidate_score is not None:
                score = (
                    f"{delta.baseline_score:.1f} -> {delta.candidate_score:.1f} "
                    f"({(delta.score_delta or 0.0):+.1f})"
                )
            elif delta.candidate_score is not None:
                score = f"{delta.candidate_score:.1f}"
            else:
                score = "n/a"
            lines.append(
                f"| {delta.trace_id} | {delta.status_change} | {score} | "
                f"{len(delta.new_findings)} | {len(delta.resolved_findings)} |"
            )
        for delta in changed:
            if not delta.new_findings and not delta.resolved_findings:
                continue
            lines.append("")
            lines.append(f"### {delta.trace_id}")
            lines.append("")
            lines.append("| Change | Severity | Rule | Step | Message |")
            lines.append("|---|---|---|---|---|")
            for finding in delta.new_findings:
                message = finding.message.replace("|", "\\|")
                lines.append(
                    f"| new | {finding.severity} | {finding.rule_id or finding.category} | "
                    f"{finding.step_id or '-'} | {message} |"
                )
            for finding in delta.resolved_findings:
                message = finding.message.replace("|", "\\|")
                lines.append(
                    f"| resolved | {finding.severity} | "
                    f"{finding.rule_id or finding.category} | "
                    f"{finding.step_id or '-'} | {message} |"
                )
    return "\n".join(lines) + "\n"
