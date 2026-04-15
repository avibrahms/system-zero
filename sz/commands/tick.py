from __future__ import annotations

import os
from datetime import datetime, timezone

import click

from sz.core import bus, manifest, paths, registry, runtime
from sz.interfaces import bus as bus_interface
from sz.interfaces import memory
from sz.interfaces import schedule


@click.command(help="Run one System Zero tick.")
@click.option("--reason", default="manual", show_default=True)
def cmd(reason: str) -> None:
    root = paths.repo_root()
    last_tick = memory.get(root, "last_tick_ts")
    window = int(os.environ.get("SZ_DEDUP_WINDOW_SECONDS", "30"))
    now = datetime.now(timezone.utc)
    if last_tick:
        previous = datetime.fromisoformat(str(last_tick).rstrip("Z")).replace(tzinfo=timezone.utc)
        delta = (now - previous).total_seconds()
        if delta < window:
            if os.environ.get("SZ_DEBUG") == "1":
                bus.emit(paths.bus_path(root), "sz", "tick.deduped", {"delta": delta})
            return
    memory.set(root, "last_tick_ts", now.isoformat().replace("+00:00", "Z"))

    current = registry.rebuild(root)
    bus.emit(paths.bus_path(root), "s0", "tick", {"reason": reason})

    for module_id in sorted(current["modules"]):
        module_dir = paths.module_dir(root, module_id)
        data = manifest.load(module_dir / "module.yaml")
        triggers = data.get("triggers", [])
        should_run = any(trigger.get("on") == "tick" for trigger in triggers)
        should_run = should_run or any(
            trigger.get("cron") and schedule.matches(trigger["cron"])
            for trigger in triggers
        )
        event_patterns = [
            trigger["match"]
            for trigger in triggers
            if trigger.get("on") == "event" and trigger.get("match")
        ]
        if event_patterns:
            should_run = should_run or bool(bus_interface.subscribe(root, module_id, event_patterns))
        if not should_run:
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
