"""Host capability lookup from the frozen protocol registry."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from sz.core import repo_config, util

_REGISTRY_PATH = util.repo_base() / "spec" / "v0.1.0" / "host-capabilities.yaml"


def _registry() -> dict[str, Any]:
    if not _REGISTRY_PATH.exists():
        return {"adapters": []}
    loaded = yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        return {"adapters": []}
    return loaded


def provided(root: Path) -> set[str]:
    """Return host capabilities exposed by the current repo's configured adapter."""
    cfg = repo_config.read(root)
    host = cfg.get("host", "generic")
    host_mode = cfg.get("host_mode", "install")
    caps: set[str] = set()
    for adapter in _registry().get("adapters", []):
        if adapter.get("host") != host:
            continue
        adapter_mode = adapter.get("mode")
        if adapter_mode == host_mode or (host_mode == "merge" and adapter_mode in {"install", "adopt"}):
            caps.update(str(item) for item in adapter.get("provides", []))
    return caps


def missing(root: Path, required: list[str]) -> list[str]:
    exposed = provided(root)
    return sorted(item for item in required if item not in exposed)
