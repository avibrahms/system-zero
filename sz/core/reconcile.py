"""Deterministic module reconciliation engine."""
from __future__ import annotations

from pathlib import Path

from sz.core import bus, manifest, paths, registry, runtime, util


def _write_reconcile_log(module_dir: Path, returncode: int, stdout: str, stderr: str) -> None:
    util.atomic_write_text(
        module_dir / "reconcile.log",
        f"returncode={returncode}\nstdout:\n{stdout}\nstderr:\n{stderr}",
    )


def reconcile(root: Path | None = None, *, reason: str = "manual") -> dict[str, object]:
    """Recompute capability bindings and run installed modules' reconcile hooks."""
    repo_root = root or paths.repo_root()
    bus_path = paths.bus_path(repo_root)

    bus.emit(bus_path, "s0", "reconcile.started", {"reason": reason})

    current, ambiguous = registry.build(repo_root)
    util.atomic_write_json(paths.registry_path(repo_root), current)

    for item in ambiguous:
        bus.emit(bus_path, "s0", "capability.ambiguous", item)

    for module_id in sorted(current["modules"]):
        module_dir = paths.module_dir(repo_root, module_id)
        manifest_path = module_dir / "module.yaml"
        data = manifest.load(manifest_path)
        hook_path = data.get("hooks", {}).get("reconcile")
        if not hook_path:
            continue

        result = runtime.run_hook(
            repo_root,
            module_id,
            module_dir,
            "reconcile",
            hook_path,
            {"SZ_RECONCILE_REASON": reason},
        )
        _write_reconcile_log(module_dir, result.returncode, result.stdout, result.stderr)
        bus.emit(
            bus_path,
            "s0",
            "module.reconciled",
            {"module_id": module_id, "returncode": result.returncode},
        )

    for item in current["unsatisfied"]:
        bus.emit(bus_path, "s0", "capability.unsatisfied", item)

    bus.emit(
        bus_path,
        "s0",
        "reconcile.finished",
        {
            "reason": reason,
            "modules": len(current["modules"]),
            "bindings": len(current["bindings"]),
            "unsatisfied": len(current["unsatisfied"]),
        },
    )
    return current
