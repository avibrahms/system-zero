"""Module manifest loading and validation."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import jsonschema
import yaml

from sz.core import util

_SCHEMA_PATH = util.repo_base() / "spec" / "v0.1.0" / "manifest.schema.json"
_SCHEMA = util.read_json(_SCHEMA_PATH, default={})


class _ManifestLoader(yaml.SafeLoader):
    """Loader that keeps YAML 1.2-style string keys such as `on` intact."""


_ManifestLoader.yaml_implicit_resolvers = {
    key: list(value)
    for key, value in yaml.SafeLoader.yaml_implicit_resolvers.items()
}

for first_letter, resolvers in list(_ManifestLoader.yaml_implicit_resolvers.items()):
    _ManifestLoader.yaml_implicit_resolvers[first_letter] = [
        (tag, regexp)
        for tag, regexp in resolvers
        if tag != "tag:yaml.org,2002:bool"
    ]


def schema_path() -> Path:
    return _SCHEMA_PATH


def validate(data: dict[str, Any]) -> dict[str, Any]:
    jsonschema.validate(data, _SCHEMA)
    if (data.get("requires") or data.get("provides")) and "reconcile" not in data.get("hooks", {}):
        raise ValueError("Modules that declare requires or provides must define hooks.reconcile.")
    return data


def load(path: Path) -> dict[str, Any]:
    raw = yaml.load(path.read_text(), Loader=_ManifestLoader) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Manifest at {path} must be a mapping.")
    return validate(raw)
