"""Reusable module installation logic."""
from __future__ import annotations

from pathlib import Path
import shutil

from sz.core import bus, host_capabilities, manifest, paths, reconcile as engine, repo_config, runtime


class ModuleInstallError(Exception):
    """Raised when a module cannot be installed."""


def install_from_source(root: Path, source: Path, module_id: str | None = None, *, force: bool = False) -> str:
    manifest_path = source / "module.yaml"
    if not manifest_path.exists():
        raise ModuleInstallError(f"No module.yaml found in {source}.")

    data = manifest.load(manifest_path)
    resolved_module_id = module_id or data["id"]
    if resolved_module_id != data["id"]:
        raise ModuleInstallError(
            f"Requested module id {resolved_module_id!r} does not match manifest id {data['id']!r}."
        )

    cfg = repo_config.read(root)
    repo_persona = "dynamic" if cfg.get("host_mode") in {"adopt", "merge"} else "static"
    personas = data.get("personas") or ["static", "dynamic"]
    if repo_persona not in personas:
        raise ModuleInstallError(
            f"Module {resolved_module_id} is not compatible with the {repo_persona} persona."
        )

    missing_host_capabilities = host_capabilities.missing(root, data.get("requires_host", []))
    if missing_host_capabilities:
        raise ModuleInstallError(
            f"Module {resolved_module_id} requires host capabilities not exposed by "
            f"{cfg.get('host', 'generic')} ({cfg.get('host_mode', 'install')}): "
            f"{', '.join(missing_host_capabilities)}."
        )

    destination = paths.module_dir(root, resolved_module_id)
    if destination.exists():
        if not force:
            return resolved_module_id
        shutil.rmtree(destination)

    shutil.copytree(source, destination)
    hook_path = data.get("hooks", {}).get("install")
    if hook_path:
        result = runtime.run_hook(root, resolved_module_id, destination, "install", hook_path)
        if result.returncode != 0:
            shutil.rmtree(destination, ignore_errors=True)
            raise ModuleInstallError(
                result.stderr.strip()
                or result.stdout.strip()
                or f"Install hook failed for {resolved_module_id}."
            )

    cfg["modules"][resolved_module_id] = {"version": data["version"], "enabled": True}
    repo_config.write(root, cfg)
    bus.emit(
        paths.bus_path(root),
        "s0",
        "module.installed",
        {"module_id": resolved_module_id, "version": data["version"], "source": str(source)},
    )
    engine.reconcile(root, reason=f"install:{resolved_module_id}")
    return resolved_module_id
