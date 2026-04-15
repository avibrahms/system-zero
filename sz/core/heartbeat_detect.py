"""Deterministic check for an existing autonomous heartbeat. No LLM."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import yaml

# Marker file/dir paths per known framework.
MARKERS = {
    "claude_code":       [".claude"],
    "cursor":            [".cursorrules", ".cursor"],
    "opencode":          [".opencode"],
    "aider":             [".aider.conf.yml"],
    "hermes":            [".hermes/config.yaml"],
    "openclaw":          [".openclaw"],
    "metaclaw":          [".metaclaw"],
    "connection_engine": ["core/system/maintenance-registry.yaml"],
}

# Adopt-mode hosts (have their own pulse).
ADOPT_HOSTS = {"hermes", "openclaw", "metaclaw", "connection_engine", "unknown"}

EXCLUDE_DIRS = {
    ".git",
    ".sz",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}
YAML_NAMES = {"config.yaml", "config.yml"}
MAX_HEARTBEAT_CONFIG_BYTES = 100_000


def detect(root: Path) -> dict:
    """Return {existing_heartbeat: <name|none>, candidate_hosts: [...]}.

    Adopt-mode hosts win over Install-mode hosts when both markers exist.
    """
    root = root.resolve()
    found = []
    for name, markers in MARKERS.items():
        for m in markers:
            if (root / m).exists():
                found.append(name)
                break
    known_adopt_hits = [h for h in found if h in ADOPT_HOSTS and h != "unknown"]
    if not known_adopt_hits and _has_unknown_heartbeat(root):
        found.append("unknown")
    if not found:
        return {"existing_heartbeat": "none", "candidate_hosts": []}
    adopt_hits = [h for h in found if h in ADOPT_HOSTS]
    if adopt_hits:
        return {"existing_heartbeat": adopt_hits[0], "candidate_hosts": adopt_hits + [h for h in found if h not in ADOPT_HOSTS]}
    return {"existing_heartbeat": found[0], "candidate_hosts": found}


def _has_unknown_heartbeat(root: Path) -> bool:
    return (
        _has_unknown_on_tick_config(root)
        or _has_cron_reference(root)
        or _has_launchd_reference(root)
        or _has_systemd_reference(root)
    )


def _has_unknown_on_tick_config(root: Path) -> bool:
    for config_path in _iter_candidate_yaml_configs(root):
        if _yaml_file_contains_on_tick(config_path):
            return True
    return False


def _iter_candidate_yaml_configs(root: Path):
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in EXCLUDE_DIRS]
        for filename in filenames:
            if filename in YAML_NAMES:
                yield Path(current) / filename


def _yaml_file_contains_on_tick(path: Path) -> bool:
    try:
        if path.stat().st_size > MAX_HEARTBEAT_CONFIG_BYTES:
            return False
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError:
        return _looks_like_on_tick_key(text)
    return _contains_on_tick_key(loaded) or _looks_like_on_tick_key(text)


def _contains_on_tick_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key) == "on_tick":
                return True
            if _contains_on_tick_key(nested):
                return True
    if isinstance(value, list):
        return any(_contains_on_tick_key(item) for item in value)
    return False


def _looks_like_on_tick_key(text: str) -> bool:
    return any(line.lstrip().startswith("on_tick:") for line in text.splitlines())


def _has_cron_reference(root: Path) -> bool:
    cron_text = _cron_text()
    if not cron_text:
        return False
    return _has_external_repo_reference(cron_text, root)


def _cron_text() -> str:
    fixture_path = os.environ.get("SZ_CRONTAB_FILE")
    if fixture_path:
        try:
            return Path(fixture_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout if result.returncode == 0 else ""


def _has_launchd_reference(root: Path) -> bool:
    launchd_dir = Path(os.environ.get("SZ_LAUNCHD_DIR", Path.home() / "Library" / "LaunchAgents"))
    return _dir_has_external_repo_reference(launchd_dir, root, suffixes={".plist"})


def _has_systemd_reference(root: Path) -> bool:
    systemd_dir = Path(os.environ.get("SZ_SYSTEMD_USER_DIR", Path.home() / ".config" / "systemd" / "user"))
    return _dir_has_external_repo_reference(systemd_dir, root, suffixes={".service", ".timer", ".path"})


def _dir_has_external_repo_reference(path: Path, root: Path, *, suffixes: set[str]) -> bool:
    if not path.is_dir():
        return False
    for candidate in path.rglob("*"):
        if not candidate.is_file() or candidate.suffix not in suffixes:
            continue
        try:
            text = candidate.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _has_external_repo_reference(text, root):
            return True
    return False


def _has_external_repo_reference(text: str, root: Path) -> bool:
    root_text = str(root)
    if root_text not in text:
        return False
    external_lines = [
        line
        for line in text.splitlines()
        if root_text in line and "sz tick --reason cron" not in line and ".sz/heartbeat.log" not in line
    ]
    return bool(external_lines)
