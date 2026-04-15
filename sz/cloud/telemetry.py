"""Opt-in cloud telemetry flushing for sz tick."""
from __future__ import annotations

import hashlib
import fnmatch
import threading
import uuid
from pathlib import Path
from typing import Any

from sz.cloud import client
from sz.core import paths, repo_config, util
from sz.interfaces import bus as bus_interface

_TELEMETRY_MODULE_ID = "s0-cloud-telemetry"


def flush_after_tick(root: Path) -> threading.Thread | None:
    config = repo_config.read(root)
    cloud = config.get("cloud", {})
    if cloud.get("telemetry") is not True:
        return None
    if cloud.get("tier") not in ("pro", "team"):
        return None
    if not (paths.user_config_dir() / "token").exists():
        return None

    events, cursor_after = _peek_events(root, "*")
    if not events:
        return None

    thread = threading.Thread(
        target=_flush,
        args=(root, config, events, cursor_after),
        name="s0-cloud-telemetry",
        daemon=True,
    )
    thread.start()
    return thread


def _install_id(root: Path) -> str:
    target = paths.s0_dir(root) / "cloud-install-id"
    if target.exists():
        return target.read_text().strip()
    install_id = str(uuid.uuid4())
    util.atomic_write_text(target, install_id + "\n")
    return install_id


def _repo_fingerprint(root: Path) -> str:
    marker = f"{root.resolve()}:{(root / '.git').exists()}"
    return hashlib.sha256(marker.encode()).hexdigest()


def _peek_events(root: Path, pattern: str) -> tuple[list[dict[str, Any]], int]:
    all_events = bus_interface.read_events(paths.bus_path(root))
    cursor = max(0, bus_interface.read_cursor(root, _TELEMETRY_MODULE_ID))
    pending = all_events[cursor:]
    matched = [
        event
        for event in pending
        if fnmatch.fnmatch(event["type"], pattern)
    ]
    return matched, len(all_events)


def _flush(
    root: Path,
    config: dict[str, Any],
    events: list[dict[str, Any]],
    cursor_after: int,
) -> None:
    try:
        response = client.telemetry(
            _install_id(root),
            events,
            repo_fingerprint=_repo_fingerprint(root),
            host=config.get("host", "generic"),
            host_mode=config.get("host_mode", "install"),
            sz_version=config.get("sz_version", "0.1.0"),
            telemetry_opt_in=config.get("cloud", {}).get("telemetry") is True,
        )
        if response.get("accepted") is not True:
            return
        current_cursor = bus_interface.read_cursor(root, _TELEMETRY_MODULE_ID)
        bus_interface.write_cursor(root, _TELEMETRY_MODULE_ID, max(current_cursor, cursor_after))
    except Exception:
        # Telemetry is opt-in and non-essential. A network or provider failure must not
        # break the local tick loop. The cursor is left untouched so events retry later.
        return
