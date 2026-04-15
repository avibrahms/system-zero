"""Registry helpers for installed modules."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import jsonschema

from sz.core import manifest, paths, util

_SCHEMA_PATH = util.repo_base() / "spec" / "v0.1.0" / "registry.schema.json"
_SCHEMA = util.read_json(_SCHEMA_PATH, default={})


def empty_registry() -> dict[str, Any]:
    return {
        "generated_at": util.utc_now(),
        "modules": {},
        "bindings": [],
        "unsatisfied": [],
    }


def read(root: Path) -> dict[str, Any]:
    registry = util.read_json(paths.registry_path(root), empty_registry())
    jsonschema.validate(registry, _SCHEMA)
    return registry


def rebuild(root: Path) -> dict[str, Any]:
    registry = empty_registry()
    provider_index: dict[str, tuple[str, str]] = {}

    for mod_dir in sorted(paths.s0_dir(root).iterdir()):
        if not mod_dir.is_dir():
            continue
        manifest_path = mod_dir / "module.yaml"
        if not manifest_path.exists():
            continue
        data = manifest.load(manifest_path)
        provides = [item["name"] for item in data.get("provides", [])]
        requires = [item["name"] for item in data.get("requires", []) if "name" in item]
        registry["modules"][data["id"]] = {
            "version": data["version"],
            "status": "healthy",
            "manifest_path": str(manifest_path.relative_to(root)),
            "provides": provides,
            "requires": requires,
        }
        for provided in data.get("provides", []):
            provider_index.setdefault(
                provided["name"],
                (data["id"], provided.get("address", "")),
            )

    for module_id, record in registry["modules"].items():
        for required in record.get("requires", []):
            if required in provider_index:
                provider_id, address = provider_index[required]
                registry["bindings"].append(
                    {
                        "requirer": module_id,
                        "capability": required,
                        "provider": provider_id,
                        "address": address,
                    }
                )
            else:
                registry["unsatisfied"].append(
                    {
                        "requirer": module_id,
                        "capability": required,
                        "severity": "warn",
                    }
                )
                registry["modules"][module_id]["status"] = "unsatisfied"

    jsonschema.validate(registry, _SCHEMA)
    util.atomic_write_json(paths.registry_path(root), registry)
    return registry
