#!/usr/bin/env python3
"""
rollback-email-verification.py — remove email draft verification artifacts.

Rollback scope:
1. Remove external-output-log.json entries created by gmail-draft-verifier
2. Remove intercepted-signals.json entries registered by gmail-draft.py
3. Delete core/system/data/outcomes/email-draft-verification.json

The script does not revert source files. Follow the manual steps it prints after
completion for git-backed file reverts and script deletion.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SYSTEM_DIR = REPO_ROOT / "core" / "system"
DATA_DIR = SYSTEM_DIR / "data"

sys.path.insert(0, str(SYSTEM_DIR / "scripts"))
from atomic_write import atomic_json_read, atomic_json_write, atomic_multi_path_lock

OUTPUT_LOG_PATH = DATA_DIR / "external-output-log.json"
SIGNALS_PATH = DATA_DIR / "intercepted-signals.json"
OUTCOME_PATH = DATA_DIR / "outcomes" / "email-draft-verification.json"


def main() -> None:
    removed_outputs = 0
    removed_signals = 0
    deleted_outcome = False

    with atomic_multi_path_lock([OUTPUT_LOG_PATH, SIGNALS_PATH, OUTCOME_PATH]):
        if OUTPUT_LOG_PATH.exists():
            output_log = atomic_json_read(str(OUTPUT_LOG_PATH))
            filtered_log = [
                entry
                for entry in output_log
                if entry.get("source") != "gmail-draft-verifier"
            ]
            removed_outputs = len(output_log) - len(filtered_log)
            if removed_outputs:
                atomic_json_write(str(OUTPUT_LOG_PATH), filtered_log)

        if SIGNALS_PATH.exists():
            signals = atomic_json_read(str(SIGNALS_PATH))
            filtered_signals = [
                signal
                for signal in signals
                if not (
                    signal.get("source_channel") == "email"
                    and signal.get("metadata", {}).get("origin") == "gmail-draft.py"
                    and signal.get("metadata", {}).get("draft_id")
                )
            ]
            removed_signals = len(signals) - len(filtered_signals)
            if removed_signals:
                atomic_json_write(str(SIGNALS_PATH), filtered_signals)

        if OUTCOME_PATH.exists():
            OUTCOME_PATH.unlink()
            deleted_outcome = True

    result = {
        "ok": True,
        "removed_output_entries": removed_outputs,
        "removed_signal_entries": removed_signals,
        "deleted_outcome_file": deleted_outcome,
        "manual_steps": [
            "git checkout -- core/system/scripts/gmail-draft.py",
            "git checkout -- core/system/maintenance-registry.yaml",
            "git checkout -- core/system/data/cloud-core/private-overlay-map.yaml",
            "rm core/system/scripts/gmail-draft-verifier.py",
            "rm core/system/scripts/rollback-email-verification.py",
        ],
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
