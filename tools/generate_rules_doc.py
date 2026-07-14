#!/usr/bin/env python3
"""Regenerate docs/rules.md from the rule registry. Run from the repo root:

    python tools/generate_rules_doc.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from agent_reliability_harness.rules import _RULES  # noqa: E402

TITLES = {
    "schema": "Schema (tool-call contracts)",
    "budget": "Budgets",
    "safety": "Safety",
    "grounding": "Grounding",
    "sequence": "Sequence (trajectory shape)",
    "flow": "Flow (errors and side effects)",
    "completion": "Completion",
}


def main() -> None:
    lines = [
        "# Rule Reference",
        "",
        "All findings carry one of these stable rule IDs. IDs never change meaning;",
        "new rules get new IDs. This file is generated from the rule registry",
        "(`src/agent_reliability_harness/rules.py`); regenerate it with",
        "`python tools/generate_rules_doc.py` after changing the registry.",
        "",
    ]
    current = None
    for rule in _RULES:
        if rule.category != current:
            current = rule.category
            lines += [f"## {TITLES[current]}", ""]
        lines += [
            f"### {rule.rule_id}",
            "",
            f"**{rule.summary}** (default severity: {rule.default_severity})",
            "",
            f"Remediation: {rule.remediation}",
            "",
        ]
    (REPO_ROOT / "docs" / "rules.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote docs/rules.md")


if __name__ == "__main__":
    main()
