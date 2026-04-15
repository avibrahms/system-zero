from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from sz.core import manifest, paths, repo_config


def _root() -> Path:
    return paths.repo_root()


def _parse_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _module_manifest(root: Path, module_id: str) -> dict[str, Any]:
    module_dir = paths.module_dir(root, module_id)
    if not module_dir.exists():
        raise click.ClickException(f"Module {module_id} is not installed.")
    return manifest.load(module_dir / "module.yaml")


def _validate_setpoint(data: dict[str, Any], key: str, value: Any) -> None:
    setpoints = data.get("setpoints", {}) or {}
    if key not in setpoints:
        raise click.ClickException(f"Module {data['id']} has no setpoint {key}.")
    definition = setpoints[key]
    if "enum" in definition and value not in definition["enum"]:
        raise click.ClickException(
            f"Invalid value for {data['id']}.{key}: {value!r}. "
            f"Expected one of {definition['enum']}."
        )
    if "range" in definition:
        lower, upper = definition["range"]
        if not isinstance(value, (int, float)) or value < lower or value > upper:
            raise click.ClickException(
                f"Invalid value for {data['id']}.{key}: {value!r}. "
                f"Expected number between {lower} and {upper}."
            )


@click.group(help="Read and update module setpoints.")
def group() -> None:
    """Setpoint helper commands."""


@group.command(name="get")
@click.argument("module_id")
@click.argument("key")
def _get(module_id: str, key: str) -> None:
    root = _root()
    data = _module_manifest(root, module_id)
    setpoints = data.get("setpoints", {}) or {}
    if key not in setpoints:
        raise click.ClickException(f"Module {module_id} has no setpoint {key}.")
    cfg = repo_config.read(root)
    configured = cfg.get("modules", {}).get(module_id, {}).get("setpoints", {})
    value = configured.get(key, setpoints[key].get("default"))
    click.echo(json.dumps(value, ensure_ascii=False))


@group.command(name="set")
@click.argument("module_id")
@click.argument("key")
@click.argument("value")
def _set(module_id: str, key: str, value: str) -> None:
    root = _root()
    data = _module_manifest(root, module_id)
    parsed = _parse_value(value)
    _validate_setpoint(data, key, parsed)

    cfg = repo_config.read(root)
    module_cfg = cfg.setdefault("modules", {}).setdefault(module_id, {"version": data["version"], "enabled": True})
    module_cfg.setdefault("setpoints", {})[key] = parsed
    repo_config.write(root, cfg)
    click.echo(json.dumps({"module_id": module_id, "setpoint": key, "value": parsed}, ensure_ascii=False))
