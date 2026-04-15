"""Shared utilities for the System Zero runtime."""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


def utc_now() -> str:
    """Return the current UTC timestamp as ISO-8601 with a Z suffix."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_base() -> Path:
    """Return the repository root that contains the protocol spec."""
    current = Path(__file__).resolve()
    for candidate in [current.parent, *current.parents]:
        if (candidate / "spec" / "v0.1.0").is_dir():
            return candidate
    raise FileNotFoundError("Could not locate repo root containing spec/v0.1.0.")


def ensure_directory(path: Path) -> Path:
    """Create the directory if needed and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path, default: Any) -> Any:
    """Read JSON data or return the provided default when absent."""
    if not path.exists():
        return copy.deepcopy(default)
    return json.loads(path.read_text())


def atomic_write_text(path: Path, content: str) -> None:
    """Write a file atomically using a same-directory temporary file."""
    ensure_directory(path.parent)
    with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as handle:
        handle.write(content)
        handle.flush()
        temp_path = Path(handle.name)
    temp_path.replace(path)


def atomic_write_json(path: Path, payload: Any) -> None:
    """Write JSON atomically with stable formatting."""
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=False) + "\n")
