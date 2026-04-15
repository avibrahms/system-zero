"""Registry helpers for installed modules."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import jsonschema

from sz.core import manifest, paths, repo_config, util

_SCHEMA_PATH = util.repo_base() / "spec" / "v0.1.0" / "registry.schema.json"
_SCHEMA = util.read_json(_SCHEMA_PATH, default={})
_VERSION_RE = re.compile(r"^\d+(?:\.\d+){0,2}$")


def empty_registry() -> dict[str, Any]:
    return {
        "generated_at": util.utc_now(),
        "modules": {},
        "bindings": [],
        "unsatisfied": [],
    }


def _without_generated_at(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "generated_at"}


def _preserve_generated_at_on_noop(root: Path, rebuilt: dict[str, Any]) -> None:
    registry_path = paths.registry_path(root)
    if not registry_path.exists():
        return
    existing = util.read_json(registry_path, {})
    if not isinstance(existing, dict):
        return
    if not isinstance(existing.get("generated_at"), str):
        return
    if _without_generated_at(existing) == _without_generated_at(rebuilt):
        rebuilt["generated_at"] = existing["generated_at"]


def _split_capability(name: str) -> tuple[str, str | None]:
    base, marker, version_range = name.partition("@")
    return base, version_range if marker else None


def _capability_base(name: str) -> str:
    return _split_capability(name)[0]


def _parse_version(value: str) -> tuple[int, int, int] | None:
    core = value.split("-", 1)[0]
    if not _VERSION_RE.match(core):
        return None
    parts = [int(part) for part in core.split(".")]
    while len(parts) < 3:
        parts.append(0)
    return parts[0], parts[1], parts[2]


def _next_patch(version: tuple[int, int, int]) -> tuple[int, int, int]:
    major, minor, patch = version
    return major, minor, patch + 1


def _range_interval(version_range: str) -> tuple[tuple[int, int, int], tuple[int, int, int]] | None:
    if version_range in {"*", "x", "X"}:
        return (0, 0, 0), (10**9, 0, 0)

    if version_range.startswith("^"):
        lower = _parse_version(version_range[1:])
        if lower is None:
            return None
        major, minor, patch = lower
        if major > 0:
            upper = (major + 1, 0, 0)
        elif minor > 0:
            upper = (0, minor + 1, 0)
        else:
            upper = (0, 0, patch + 1)
        return lower, upper

    exact = _parse_version(version_range)
    if exact is None:
        return None
    return exact, _next_patch(exact)


def _ranges_overlap(
    left: tuple[tuple[int, int, int], tuple[int, int, int]],
    right: tuple[tuple[int, int, int], tuple[int, int, int]],
) -> bool:
    left_lower, left_upper = left
    right_lower, right_upper = right
    return left_lower < right_upper and right_lower < left_upper


def _capability_matches(required: str, provided: str) -> bool:
    required_base, required_range = _split_capability(required)
    provided_base, provided_range = _split_capability(provided)
    if required_base != provided_base:
        return False
    if required_range is None:
        return True
    if provided_range is None:
        return False

    required_interval = _range_interval(required_range)
    provided_interval = _range_interval(provided_range)
    if required_interval is None or provided_interval is None:
        return required_range == provided_range
    return _ranges_overlap(required_interval, provided_interval)


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
            [
                provider
                for provider in providers.get(_capability_base(capability), [])
                if _capability_matches(capability, provider["capability"])
            ],
            key=lambda item: item["module_id"],
        )
        if candidates:
            pinned = requirement["bindings"].get(capability) or requirement["bindings"].get(
                _capability_base(capability)
            )
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

    _preserve_generated_at_on_noop(root, registry)
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
