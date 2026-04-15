"""Discovery interface backed by the runtime registry."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from sz.core import paths, util


def _registry(root: Path) -> dict[str, Any]:
    return util.read_json(
        paths.registry_path(root),
        {"generated_at": util.utc_now(), "modules": {}, "bindings": [], "unsatisfied": []},
    )


def list_modules(root: Path) -> list[dict[str, Any]]:
    registry = _registry(root)
    return [
        {"module_id": module_id, **record}
        for module_id, record in sorted(registry.get("modules", {}).items())
    ]


def providers(root: Path, capability: str) -> list[dict[str, Any]]:
    registry = _registry(root)
    bindings = [
        binding
        for binding in registry.get("bindings", [])
        if binding.get("capability") == capability
    ]
    if bindings:
        deduped: dict[str, dict[str, Any]] = {}
        for binding in bindings:
            deduped[binding["provider"]] = binding
        return [deduped[key] for key in sorted(deduped)]

    provided: list[dict[str, Any]] = []
    for module_id, record in sorted(registry.get("modules", {}).items()):
        if capability in record.get("provides", []):
            provided.append(
                {
                    "provider": module_id,
                    "capability": capability,
                    "address": "",
                    "requirer": None,
                }
            )
    return provided


def requirers(root: Path, capability: str) -> list[dict[str, Any]]:
    registry = _registry(root)
    found: list[dict[str, Any]] = []
    for module_id, record in sorted(registry.get("modules", {}).items()):
        if capability in record.get("requires", []):
            found.append(
                {
                    "requirer": module_id,
                    "capability": capability,
                    "status": record.get("status", "healthy"),
                }
            )
    return found


def resolve(root: Path, capability: str) -> dict[str, Any] | None:
    providers_for_capability = providers(root, capability)
    if not providers_for_capability:
        return None
    return sorted(
        providers_for_capability,
        key=lambda item: (item.get("provider", ""), item.get("address", "")),
    )[0]


def health(root: Path, module_id: str) -> dict[str, Any] | None:
    registry = _registry(root)
    record = registry.get("modules", {}).get(module_id)
    if record is None:
        return None
    return {"module_id": module_id, **record}


def profile(root: Path) -> dict[str, Any]:
    return util.read_json(paths.profile_path(root), {})
