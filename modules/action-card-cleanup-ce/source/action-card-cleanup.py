#!/usr/bin/env python3
"""
Action Card Cleanup — archives completed items and cleans the active card.

Run at session start (before any task execution) to ensure:
  1. Completed items are moved to the permanent archive
  2. They don't reappear in the active card
  3. Plan/clean protocols don't recreate them as new Todoist tasks
  4. Incomplete items from past days persist in the active card

Usage:
  python3 system/scripts/action-card-cleanup.py [--quiet]

Data files:
  system/data/action-card.json — Active card (items get removed once archived)
  system/data/action-card-state.json — Completion state (cleared for archived items)
  system/data/action-card-archive.json — Permanent archive (items added here)
"""

import sys
from pathlib import Path
from datetime import datetime

from atomic_write import atomic_json_read, atomic_json_write

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = REPO_ROOT / "core" / "system" / "data"
CARD_PATH = DATA_DIR / "action-card.json"
STATE_PATH = DATA_DIR / "action-card-state.json"
ARCHIVE_PATH = DATA_DIR / "action-card-archive.json"

QUIET = "--quiet" in sys.argv


def load_json(path, default):
    if path.exists():
        return atomic_json_read(path)
    return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_json_write(path, data)


def main():
    card = load_json(CARD_PATH, {"date": "", "sections": []})
    state = load_json(STATE_PATH, {"completed_items": {}})
    archive = load_json(ARCHIVE_PATH, {"entries": []})

    completed = state.get("completed_items", {})

    if not completed:
        if not QUIET:
            print("Action Card: No completed items to archive.")
        return

    card_date = card.get("date", datetime.now().strftime("%Y-%m-%d"))
    archived_count = 0

    # Build item detail map from card
    item_map = {}
    for sec in card.get("sections", []):
        for item in sec.get("items", []):
            item_map[item["id"]] = {**item, "_section_type": sec["type"]}

    # Archive each completed item
    for item_id, completed_at in completed.items():
        # Check if already archived (idempotent)
        if any(e["id"] == item_id and e["card_date"] == card_date for e in archive["entries"]):
            continue

        item_info = item_map.get(item_id, {"id": item_id, "name": item_id})
        archive["entries"].append({
            "id": item_id,
            "name": item_info.get("name", item_id),
            "context": item_info.get("context", ""),
            "section_type": item_info.get("_section_type", "task"),
            "card_date": card_date,
            "completed_at": completed_at
        })
        archived_count += 1

    # Remove completed items from card sections
    for sec in card.get("sections", []):
        sec["items"] = [i for i in sec["items"] if i["id"] not in completed]

    # Remove empty sections
    card["sections"] = [s for s in card["sections"] if s.get("items")]

    # Clear archived items from state (keep state file for any non-card items)
    state["completed_items"] = {}
    state["last_updated"] = datetime.now().isoformat()

    # Save all
    save_json(CARD_PATH, card)
    save_json(STATE_PATH, state)
    save_json(ARCHIVE_PATH, archive)

    if not QUIET:
        print(f"Action Card: Archived {archived_count} completed items. {sum(len(s.get('items', [])) for s in card.get('sections', []))} active items remain.")


if __name__ == "__main__":
    main()
