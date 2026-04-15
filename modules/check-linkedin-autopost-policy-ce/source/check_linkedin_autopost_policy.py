#!/usr/bin/env python3
"""Detect drift in LinkedIn auto-post eligibility and cadence copy."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
POLICY_PATH = REPO_ROOT / "modules" / "linkedin-content-pipeline" / "content-mix-policy.yaml"

TEXT_CHECKS = [
    (
        REPO_ROOT / "modules" / "linkedin-content-pipeline" / "posting" / "AUTO-POST-PROTOCOL.md",
        re.compile(r"approved,\s*ready,\s*or\s*reserved|approved/ready/reserved", re.IGNORECASE),
        "stale auto-post eligibility language",
    ),
    (
        REPO_ROOT / "modules" / "linkedin-content-pipeline" / "posting" / "PIPELINE.md",
        re.compile(r"approved,\s*ready,\s*and\s*reserved|approved/ready/reserved", re.IGNORECASE),
        "stale pipeline scheduling language",
    ),
    (
        REPO_ROOT / "modules" / "linkedin-content-pipeline" / "maintenance.yaml",
        re.compile(r"select best eligible post\s*\(approved/ready/reserved\)", re.IGNORECASE),
        "stale maintenance auto-post selection language",
    ),
    (
        REPO_ROOT / "modules" / "linkedin-content-pipeline" / "posting" / "ready-queue.md",
        re.compile(r"48h rule", re.IGNORECASE),
        "stale 48h cadence copy in live queue",
    ),
]


def _line_number(text: str, match: re.Match[str]) -> int:
    return text.count("\n", 0, match.start()) + 1


def main() -> int:
    findings: list[str] = []

    try:
        policy = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        print(f"ERROR: failed to read {POLICY_PATH}: {exc}", file=sys.stderr)
        return 2

    eligible_statuses = [
        str(status).strip().lower()
        for status in ((policy.get("selection") or {}).get("eligible_statuses") or [])
        if str(status).strip()
    ]
    if eligible_statuses != ["approved"]:
        findings.append(
            f"{POLICY_PATH.relative_to(REPO_ROOT)}: selection.eligible_statuses must be ['approved'], got {eligible_statuses!r}"
        )

    for path, pattern, label in TEXT_CHECKS:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as exc:
            findings.append(f"{path.relative_to(REPO_ROOT)}: failed to read file ({exc})")
            continue
        for match in pattern.finditer(text):
            findings.append(
                f"{path.relative_to(REPO_ROOT)}:{_line_number(text, match)}: {label}: {match.group(0)!r}"
            )

    if findings:
        print("LinkedIn auto-post policy drift detected:")
        for finding in findings:
            print(f"- {finding}")
        return 1

    print("LinkedIn auto-post policy drift check: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
