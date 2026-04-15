"""Runtime execution helpers for hooks and module entry points."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from sz.core import bus, paths


def module_environment(root: Path, module_id: str, module_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "SZ_REPO_ROOT": str(root),
            "SZ_MODULE_DIR": str(module_dir),
            "SZ_MODULE_ID": module_id,
            "SZ_BUS_PATH": str(paths.bus_path(root)),
            "SZ_MEMORY_DIR": str(paths.memory_dir(root)),
            "SZ_REGISTRY_PATH": str(paths.registry_path(root)),
            "SZ_PROFILE_PATH": str(paths.profile_path(root)),
        }
    )
    return env


def _command_for_entry(module_dir: Path, entry: dict[str, Any]) -> list[str]:
    command = entry["command"]
    args = [str(arg) for arg in entry.get("args", [])]
    resolved = str((module_dir / command).resolve()) if not Path(command).is_absolute() else command

    entry_type = entry["type"]
    if entry_type == "python":
        return [sys.executable, resolved, *args]
    if entry_type == "bash":
        return ["bash", resolved, *args]
    if entry_type == "node":
        return ["node", resolved, *args]
    return [resolved, *args]


def run_hook(root: Path, module_id: str, module_dir: Path, hook_name: str, relative_path: str) -> subprocess.CompletedProcess[str]:
    command = ["/bin/bash", str((module_dir / relative_path).resolve())]
    return subprocess.run(
        command,
        cwd=module_dir,
        env=module_environment(root, module_id, module_dir),
        capture_output=True,
        text=True,
        check=False,
    )


def run_entry(root: Path, module_id: str, module_dir: Path, entry: dict[str, Any], timeout: int) -> subprocess.CompletedProcess[str]:
    command = _command_for_entry(module_dir, entry)
    try:
        return subprocess.run(
            command,
            cwd=module_dir,
            env=module_environment(root, module_id, module_dir),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        crash_path = module_dir / "crash.log"
        with crash_path.open("a", encoding="utf-8") as handle:
            handle.write(f"timeout while running {' '.join(command)}\n")
        bus.emit(
            paths.bus_path(root),
            "s0",
            "module.errored",
            {"module_id": module_id, "reason": "timeout", "command": command},
        )
        raise RuntimeError(f"Module {module_id} exceeded timeout of {timeout}s.") from exc
