#!/usr/bin/env python3
"""
Task: Bootstrap START-PROTOCOL session context into one deterministic JSON payload.
Method: Run local bootstrap checks, optionally fetch Todoist scope, and emit a schema-validated bundle.
Knowledge: START/continue preamble must stay scriptified and dry-run safe.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from atomic_write import atomic_text_write
from specification.session_bootstrap_support import build_session_bootstrap_payload
from specification.workflow_models import SessionBootstrapResult
from todoist_client import load_token


def build_session_bootstrap(
    input_value: dict[str, Any] | None = None,
    *,
    dry_run: bool = False,
    args: dict[str, Any] | None = None,
    continue_mode: bool = False,
    **_: Any,
) -> dict[str, Any]:
    payload = dict(input_value or {})
    payload.update(args or {})
    result = build_session_bootstrap_payload(
        focus=payload.get("focus"),
        continue_mode=continue_mode or bool(payload.get("continue")),
        dry_run=dry_run,
        token=None if dry_run else load_token(required=False),
    )
    return SessionBootstrapResult.model_validate(result).model_dump()


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic bootstrap for START-PROTOCOL that emits structured JSON.")
    parser.add_argument("--continue", dest="continue_mode", action="store_true")
    parser.add_argument("--focus")
    parser.add_argument("--output")
    parser.add_argument("--dry-run", action="store_true")
    cli_args = parser.parse_args()

    result = build_session_bootstrap(
        args={"focus": cli_args.focus, "continue": cli_args.continue_mode},
        continue_mode=cli_args.continue_mode,
        dry_run=cli_args.dry_run,
    )
    output = json.dumps(result, indent=2, default=str)
    if cli_args.output:
        atomic_text_write(cli_args.output, output)
        print(f"Preamble written to {cli_args.output}")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
