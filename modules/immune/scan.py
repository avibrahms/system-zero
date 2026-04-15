#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


EXTENSIONS = {".py", ".js", ".ts", ".sh", ".yaml", ".yml", ".md"}
SKIP_DIRS = {".git", ".sz", "node_modules", ".venv", "venv", "dist", "build", "__pycache__"}
SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}
PATTERNS = [
    ("hardcoded-password", "high", re.compile(r"(?i)\b(password|passwd|pwd)\b\s*[:=]\s*['\"][^'\"]+['\"]")),
    ("aws-access-key", "high", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("fixme", "medium", re.compile(r"\bFIXME\b")),
    ("todo", "low", re.compile(r"\bTODO\b")),
]


def main() -> int:
    root = Path(os.environ["SZ_REPO_ROOT"])
    threshold = os.environ.get("SZ_SETPOINT_severity_threshold", "medium")
    minimum = SEVERITY_ORDER.get(threshold, SEVERITY_ORDER["medium"])
    for path in iter_source_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for kind, severity, pattern in PATTERNS:
            if SEVERITY_ORDER[severity] < minimum:
                continue
            match = pattern.search(text)
            if not match:
                continue
            line = text.count("\n", 0, match.start()) + 1
            emit(
                {
                    "kind": kind,
                    "severity": severity,
                    "path": str(path.relative_to(root)),
                    "line": line,
                }
            )
            break
    return 0


def iter_source_files(root: Path):
    for current, dirs, files in os.walk(root):
        dirs[:] = [item for item in dirs if item not in SKIP_DIRS]
        base = Path(current)
        for name in sorted(files):
            path = base / name
            if name == ".env" or path.suffix in EXTENSIONS:
                yield path


def emit(payload: dict[str, object]) -> None:
    subprocess.run(
        ["sz", "bus", "emit", "anomaly.detected", json.dumps(payload, separators=(",", ":")), "--module", "immune"],
        check=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
