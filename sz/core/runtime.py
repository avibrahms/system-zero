"""Runtime execution helpers for hooks and module entry points."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from sz.core import bus, manifest, paths, repo_config


def _resolve_llm_bin() -> str:
    configured = os.environ.get("SZ_LLM_BIN")
    if configured:
        return configured

    for candidate in ("sz", "s0"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    return sys.executable


def module_environment(root: Path, module_id: str, module_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    data = manifest.load(module_dir / "module.yaml")
    cfg = repo_config.read(root)
    module_cfg = cfg.get("modules", {}).get(module_id, {})
    configured_setpoints = module_cfg.get("setpoints", {}) or {}
    for key, definition in (data.get("setpoints", {}) or {}).items():
        value = configured_setpoints.get(key, definition.get("default"))
        env[f"SZ_SETPOINT_{key}"] = _stringify_env_value(value)
    env.update(
        {
            "SZ_REPO_ROOT": str(root),
            "SZ_MODULE_DIR": str(module_dir),
            "SZ_MODULE_ID": module_id,
            "SZ_BUS_PATH": str(paths.bus_path(root)),
            "SZ_MEMORY_DIR": str(paths.memory_dir(root)),
            "SZ_REGISTRY_PATH": str(paths.registry_path(root)),
            "SZ_PROFILE_PATH": str(paths.profile_path(root)),
            "SZ_LLM_BIN": _resolve_llm_bin(),
        }
    )
    return env


def _stringify_env_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        import json

        return json.dumps(value, separators=(",", ":"))
    return str(value)


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


def run_hook(
    root: Path,
    module_id: str,
    module_dir: Path,
    hook_name: str,
    relative_path: str,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command = ["/bin/bash", str((module_dir / relative_path).resolve())]
    env = module_environment(root, module_id, module_dir)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        command,
        cwd=module_dir,
        env=env,
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
