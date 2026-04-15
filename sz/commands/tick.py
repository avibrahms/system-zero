from __future__ import annotations

import click

from sz.core import bus, manifest, paths, registry, runtime


@click.command(help="Run one System Zero tick.")
@click.option("--reason", default="manual", show_default=True)
def cmd(reason: str) -> None:
    root = paths.repo_root()
    current = registry.rebuild(root)
    bus.emit(paths.bus_path(root), "s0", "tick", {"reason": reason})

    for module_id in sorted(current["modules"]):
        module_dir = paths.module_dir(root, module_id)
        data = manifest.load(module_dir / "module.yaml")
        if not any(trigger.get("on") == "tick" for trigger in data.get("triggers", [])):
            continue
        timeout = data.get("limits", {}).get("max_runtime_seconds", 300)
        result = runtime.run_entry(root, module_id, module_dir, data["entry"], timeout)
        if result.returncode != 0:
            bus.emit(
                paths.bus_path(root),
                "s0",
                "module.errored",
                {"module_id": module_id, "returncode": result.returncode},
            )
            raise click.ClickException(f"Module {module_id} failed during tick.")
    click.echo(f"Tick completed ({reason})")
