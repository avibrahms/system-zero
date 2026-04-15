"""Filesystem layout helpers."""
from __future__ import annotations

import os
from pathlib import Path


def repo_root(start: Path | None = None) -> Path:
    p = (start or Path.cwd()).resolve()
    for candidate in [p, *p.parents]:
        if (candidate / ".sz").is_dir():
            return candidate
    raise FileNotFoundError("No .sz/ found in this directory or any parent.")


def s0_dir(root: Path) -> Path:
    return root / ".sz"


def module_dir(root: Path, mod_id: str) -> Path:
    return s0_dir(root) / mod_id


def bus_path(root: Path) -> Path:
    return s0_dir(root) / "bus.jsonl"


def registry_path(root: Path) -> Path:
    return s0_dir(root) / "registry.json"


def profile_path(root: Path) -> Path:
    return s0_dir(root) / "repo-profile.json"


def repo_config_path(root: Path) -> Path:
    return root / ".sz.yaml"


def user_config_dir() -> Path:
    return Path(os.path.expanduser("~/.sz"))


def memory_dir(root: Path) -> Path:
    return s0_dir(root) / "memory"


def streams_dir(root: Path) -> Path:
    return memory_dir(root) / "streams"


def cursors_dir(root: Path) -> Path:
    return memory_dir(root) / "cursors"


def shared_dir(root: Path) -> Path:
    return s0_dir(root) / "shared"


def bin_dir(root: Path) -> Path:
    return s0_dir(root) / "bin"


def heartbeat_script_path(root: Path) -> Path:
    return bin_dir(root) / "heartbeat.sh"


def heartbeat_pid_path(root: Path) -> Path:
    return s0_dir(root) / "heartbeat.pid"


def heartbeat_log_path(root: Path) -> Path:
    return s0_dir(root) / "heartbeat.log"
