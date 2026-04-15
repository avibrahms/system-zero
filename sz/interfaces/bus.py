"""Append-only bus helpers backed by JSONL with per-module cursors."""
from __future__ import annotations

import fnmatch
import json
import os
from pathlib import Path
from typing import Any

import jsonschema

from sz.core import paths, util

_SCHEMA_PATH = util.repo_base() / "spec" / "v0.1.0" / "bus-event.schema.json"
_SCHEMA = util.read_json(_SCHEMA_PATH, default={})


def _validate_event(event: dict[str, Any]) -> None:
    jsonschema.validate(event, _SCHEMA)


def _cursor_path(root: Path, module_id: str) -> Path:
    return paths.cursors_dir(root) / f"{module_id}.json"


def read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        events.append(json.loads(line))
    return events


def read_cursor(root: Path, module_id: str) -> int:
    cursor_path = _cursor_path(root, module_id)
    payload = util.read_json(cursor_path, {"cursor": 0})
    return int(payload.get("cursor", 0))


def write_cursor(root: Path, module_id: str, cursor: int) -> None:
    util.atomic_write_json(
        _cursor_path(root, module_id),
        {"cursor": int(cursor), "updated_at": util.utc_now()},
    )


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
    util.ensure_directory(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return event


def tail(path: Path, *, last: int | None = None, pattern: str | None = None) -> list[dict[str, Any]]:
    events = read_events(path)
    if pattern:
        events = [event for event in events if fnmatch.fnmatch(event["type"], pattern)]
    if last is not None:
        events = events[-last:]
    return events


def subscribe(root: Path, module_id: str, pattern: str | list[str] | None = None) -> list[dict[str, Any]]:
    all_events = read_events(paths.bus_path(root))
    cursor = max(0, read_cursor(root, module_id))
    pending = all_events[cursor:]
    patterns = [pattern] if isinstance(pattern, str) else list(pattern or [])
    if patterns:
        matched = [
            event
            for event in pending
            if any(fnmatch.fnmatch(event["type"], item) for item in patterns)
        ]
    else:
        matched = pending
    write_cursor(root, module_id, len(all_events))
    return matched
