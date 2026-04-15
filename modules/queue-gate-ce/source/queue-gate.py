#!/usr/bin/env python3
"""Queue depth gate for content creation tasks.

Usage: python3 queue-gate.py [max_depth]

Counts ### entries in ready-queue.md. Exits 0 if queue depth <= max_depth
(task should proceed), exits 1 if queue depth > max_depth (task should skip).

Default max_depth: 15
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
READY_QUEUE = REPO_ROOT / "modules" / "linkedin-content-pipeline" / "posting" / "ready-queue.md"

# Only count posts with actionable statuses (not posted, not rejected)
SKIP_STATUSES = {"posted", "rejected"}


def count_active_queue_entries(path: Path) -> int:
    """Count ### entries in ready-queue.md that are not posted/rejected."""
    if not path.exists():
        return 0
    count = 0
    current_status = None
    for line in path.read_text().splitlines():
        if line.startswith("### "):
            # New entry starts; commit previous entry
            if current_status is not None and current_status not in SKIP_STATUSES:
                count += 1
            current_status = ""  # reset for new entry
        elif current_status is not None and "**Status:**" in line:
            lower = line.lower()
            for s in SKIP_STATUSES:
                if s in lower:
                    current_status = s
                    break
    # Count the last entry
    if current_status is not None and current_status not in SKIP_STATUSES:
        count += 1
    return count


def main():
    max_depth = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    depth = count_active_queue_entries(READY_QUEUE)
    if depth > max_depth:
        print(f"GATE CLOSED: queue depth {depth} > {max_depth}. Skipping content creation.", flush=True)
        sys.exit(1)
    else:
        print(f"GATE OPEN: queue depth {depth} <= {max_depth}. Proceeding.", flush=True)
        sys.exit(0)


if __name__ == "__main__":
    main()
