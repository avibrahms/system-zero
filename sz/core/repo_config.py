"""Repo configuration helpers for .sz.yaml."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from sz.core import paths, util

DEFAULT = {
    "sz_version": "0.1.0",
    "host": "generic",
    "host_mode": "install",
    "modules": {},
    "providers": {},
    "cloud": {"tier": "free", "endpoint": "https://api.systemzero.dev", "telemetry": False},
}

_SCHEMA_PATH = util.repo_base() / "spec" / "v0.1.0" / "repo-config.schema.json"
_SCHEMA = util.read_json(_SCHEMA_PATH, default={})


def _with_defaults(data: dict[str, Any] | None) -> dict[str, Any]:
    merged = copy.deepcopy(DEFAULT)
    if not data:
        return merged
    for key, value in data.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged


def read(root: Path) -> dict[str, Any]:
    config_path = paths.repo_config_path(root)
    if not config_path.exists():
        return copy.deepcopy(DEFAULT)
    loaded = yaml.safe_load(config_path.read_text()) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"{config_path} must contain a YAML mapping.")
    config = _with_defaults(loaded)
    jsonschema.validate(config, _SCHEMA)
    return config


def write(root: Path, config: dict[str, Any]) -> None:
    merged = _with_defaults(config)
    jsonschema.validate(merged, _SCHEMA)
    rendered = yaml.safe_dump(merged, sort_keys=False)
    util.atomic_write_text(paths.repo_config_path(root), rendered)
