"""Append-only bus helpers backed by JSONL."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import jsonschema

from sz.core import util

_SCHEMA_PATH = util.repo_base() / "spec" / "v0.1.0" / "bus-event.schema.json"
_SCHEMA = util.read_json(_SCHEMA_PATH, default={})


def _validate_event(event: dict[str, Any]) -> None:
    jsonschema.validate(event, _SCHEMA)


def emit(
    path: Path,
    module: str,
    event_type: str,
    payload: dict[str, Any],
    correlation_id: str | None = None,
) -> dict[str, Any]:
    event = {
        "ts": util.utc_now(),
        "module": module,
        "type": event_type,
        "payload": payload,
    }
    if correlation_id:
        event["correlation_id"] = correlation_id
    _validate_event(event)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return event


def read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        events.append(json.loads(line))
    return events
