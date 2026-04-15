"""Resolve host adapters to manifests, scripts, and autodetection."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent

DETECT_PRIORITY = [
    "hermes",
    "openclaw",
    "metaclaw",
    "connection_engine",
    "claude_code",
    "cursor",
    "opencode",
    "aider",
    "unknown",
    "generic",
]


def list_names() -> list[str]:
    return sorted(p.name for p in HERE.iterdir() if (p / "manifest.yaml").exists())


def manifest(name: str) -> dict[str, Any]:
    return yaml.safe_load((HERE / name / "manifest.yaml").read_text()) or {}


def install_script(name: str) -> Path:
    return HERE / name / "install.sh"


def uninstall_script(name: str) -> Path:
    return HERE / name / "uninstall.sh"


def detect_script(name: str) -> Path:
    return HERE / name / "detect.sh"


def autodetect(repo_root: Path) -> str:
    """Run detect.sh files in priority order; first hit wins."""
    env = {**os.environ, "SZ_REPO_ROOT": str(repo_root)}
    for name in DETECT_PRIORITY:
        script = detect_script(name)
        if not script.exists():
            continue
        result = subprocess.run(
            ["bash", str(script)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip() == name:
            return name
    return "generic"
