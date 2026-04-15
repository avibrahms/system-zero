#!/usr/bin/env python3
"""Initialize deterministic moonshot tracking files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from atomic_write import atomic_text_write


def _metrics_template(venture_name: str, created: str) -> str:
    return f"""# {venture_name} -- Metrics

**Status:** Pre-launch
**Created:** {created}

## Traction MVP Metrics

| Metric | Week 1 | Week 2 | Week 3 | Week 4 |
|--------|--------|--------|--------|--------|
| Users | | | | |
| API calls | | | | |
| Revenue | | | | |
| Signups | | | | |

## Fundraising Metrics

| Milestone | Target Date | Status |
|-----------|------------|--------|
| Pre-seed deck ready | | |
| First investor meeting | | |
| Term sheet | | |
| Close | | |
"""


def _build_log_template(
    venture_name: str,
    created: str,
    one_liner: str,
    key_finding: str,
    mvp: str,
    business_target: str,
    score: str,
) -> str:
    return f"""# {venture_name} -- Build Log

## Day 0: {created} -- Venture Package Created

- Company defined: {one_liner}
- Research completed: {key_finding}
- MVP designed: {mvp}
- Business plan drafted: {business_target}
- Score: {score}
- Status: Package complete. Awaiting greenlight for MVP build.
"""


def _write_text(path: Path, content: str, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists; pass --overwrite to replace it")
    atomic_text_write(str(path), content)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Initialize moonshot venture tracking files from deterministic templates."
    )
    parser.add_argument("--venture-dir", required=True, help="Path to ventures/<name> directory")
    parser.add_argument("--venture-name", required=True, help="Display name for the venture")
    parser.add_argument("--created", required=True, help="Creation date to stamp into the files")
    parser.add_argument("--one-liner", required=True, help="Company one-liner")
    parser.add_argument("--key-finding", required=True, help="Key research finding")
    parser.add_argument("--mvp", required=True, help="Short MVP description")
    parser.add_argument("--score", required=True, help='Score string such as "48/60"')
    parser.add_argument(
        "--business-target",
        default="[fundraising target]",
        help="Fundraising target summary for BUILD-LOG.md",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing METRICS.md and BUILD-LOG.md if they already exist",
    )
    args = parser.parse_args()

    venture_dir = Path(args.venture_dir)
    venture_dir.mkdir(parents=True, exist_ok=True)

    metrics_path = venture_dir / "METRICS.md"
    build_log_path = venture_dir / "BUILD-LOG.md"

    _write_text(metrics_path, _metrics_template(args.venture_name, args.created), args.overwrite)
    _write_text(
        build_log_path,
        _build_log_template(
            args.venture_name,
            args.created,
            args.one_liner,
            args.key_finding,
            args.mvp,
            args.business_target,
            args.score,
        ),
        args.overwrite,
    )

    print(
        json.dumps(
            {
                "venture_dir": str(venture_dir),
                "created_files": [str(metrics_path), str(build_log_path)],
                "overwrite": args.overwrite,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
