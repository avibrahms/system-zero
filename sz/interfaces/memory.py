"""Memory interface: KV store plus append-only streams."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from sz.core import paths, repo_config, util


def _kv_path(root: Path) -> Path:
    return paths.memory_dir(root) / "kv.json"


def _stream_path(root: Path, stream: str) -> Path:
    return paths.streams_dir(root) / f"{stream}.jsonl"


def get(root: Path, key: str, default: Any = None) -> Any:
    payload = util.read_json(_kv_path(root), {})
    return payload.get(key, default)


def set(root: Path, key: str, value: Any) -> Any:
    payload = util.read_json(_kv_path(root), {})
    payload[key] = value
    util.atomic_write_json(_kv_path(root), payload)
    return value


def append(root: Path, stream: str, item: Any) -> Any:
    path = _stream_path(root, stream)
    util.ensure_directory(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return item


def tail(root: Path, stream: str, from_cursor: int | None = None) -> tuple[list[Any], int]:
    path = _stream_path(root, stream)
    if not path.exists():
        return [], 0
    items = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    cursor = max(0, int(from_cursor or 0))
    return items[cursor:], len(items)


def search(root: Path, query: str, top: int = 5) -> list[Any]:
    config = repo_config.read(root)
    provider = (config.get("providers") or {}).get("vector")
    if not provider or provider == "none":
        return []
    return []
