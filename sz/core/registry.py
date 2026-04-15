"""Registry helpers for installed modules."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import jsonschema

from sz.core import manifest, paths, repo_config, util

_SCHEMA_PATH = util.repo_base() / "spec" / "v0.1.0" / "registry.schema.json"
_SCHEMA = util.read_json(_SCHEMA_PATH, default={})


def empty_registry() -> dict[str, Any]:
    return {
        "generated_at": util.utc_now(),
        "modules": {},
        "bindings": [],
        "unsatisfied": [],
    }


def _capability_base(name: str) -> str:
    return name.split("@", 1)[0]


def _configured_module_ids(root: Path) -> set[str] | None:
    if not paths.repo_config_path(root).exists():
        return None
    return set(repo_config.read(root).get("modules", {}).keys())


def _module_records(root: Path) -> list[tuple[str, Path, dict[str, Any], dict[str, Any]]]:
    configured_ids = _configured_module_ids(root)
    cfg = repo_config.read(root)
    records: list[tuple[str, Path, dict[str, Any], dict[str, Any]]] = []

    if not paths.s0_dir(root).exists():
        return records

    for mod_dir in sorted(paths.s0_dir(root).iterdir()):
        if not mod_dir.is_dir():
            continue
        manifest_path = mod_dir / "module.yaml"
        if not manifest_path.exists():
            continue
        data = manifest.load(manifest_path)
        module_id = data["id"]
        if configured_ids is not None and module_id not in configured_ids:
            continue
        module_cfg = cfg.get("modules", {}).get(module_id, {})
        records.append((module_id, manifest_path, data, module_cfg))
    return records


def build(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    registry = empty_registry()
    providers: dict[str, list[dict[str, str]]] = {}
    requirements: list[dict[str, Any]] = []

    for module_id, manifest_path, data, module_cfg in _module_records(root):
        enabled = bool(module_cfg.get("enabled", True))
        provides = [item["name"] for item in data.get("provides", [])]
        requires = [item["name"] for item in data.get("requires", []) if "name" in item]
        registry["modules"][module_id] = {
            "version": data["version"],
            "status": "healthy" if enabled else "disabled",
            "manifest_path": str(manifest_path.relative_to(root)),
            "provides": provides,
            "requires": requires,
        }
        if not enabled:
            continue
        for provided in data.get("provides", []):
            name = provided["name"]
            providers.setdefault(_capability_base(name), []).append(
                {
                    "module_id": module_id,
                    "capability": name,
                    "address": provided.get("address", ""),
                }
            )
        for required in data.get("requires", []):
            if "name" not in required:
                continue
            requirements.append(
                {
                    "module_id": module_id,
                    "capability": required["name"],
                    "optional": bool(required.get("optional", False)),
                    "severity": required.get("on_missing", "warn"),
                    "bindings": module_cfg.get("bindings", {}),
                }
            )

    ambiguous: list[dict[str, Any]] = []
    for requirement in sorted(
        requirements,
        key=lambda item: (item["module_id"], item["capability"]),
    ):
        capability = requirement["capability"]
        candidates = sorted(
            providers.get(_capability_base(capability), []),
            key=lambda item: item["module_id"],
        )
        if candidates:
            pinned = requirement["bindings"].get(capability)
            selected = next(
                (candidate for candidate in candidates if candidate["module_id"] == pinned),
                candidates[0],
            )
            if len(candidates) > 1:
                ambiguous.append(
                    {
                        "requirer": requirement["module_id"],
                        "capability": capability,
                        "providers": [candidate["module_id"] for candidate in candidates],
                        "selected": selected["module_id"],
                        "pinned": pinned,
                    }
                )
            registry["bindings"].append(
                {
                    "requirer": requirement["module_id"],
                    "capability": capability,
                    "provider": selected["module_id"],
                    "address": selected["address"],
                }
            )
            continue

        if requirement["optional"]:
            continue
        registry["unsatisfied"].append(
            {
                "requirer": requirement["module_id"],
                "capability": capability,
                "severity": requirement["severity"],
            }
        )
        registry["modules"][requirement["module_id"]]["status"] = "unsatisfied"

    jsonschema.validate(registry, _SCHEMA)
    return registry, ambiguous


def read(root: Path) -> dict[str, Any]:
    registry = util.read_json(paths.registry_path(root), empty_registry())
    jsonschema.validate(registry, _SCHEMA)
    return registry


def rebuild(root: Path) -> dict[str, Any]:
    registry, _ambiguous = build(root)
    util.atomic_write_json(paths.registry_path(root), registry)
    return registry
