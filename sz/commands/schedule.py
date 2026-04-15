from __future__ import annotations

import json
from pathlib import Path

import click

from sz.core import manifest, paths, runtime
from sz.interfaces import schedule


def _root() -> Path:
    return paths.repo_root()


@click.group(help="Schedule interface commands.")
def group() -> None:
    """Inspect or manually fire scheduled work."""


@group.command(name="list")
def _list() -> None:
    click.echo(json.dumps(schedule.module_triggers(_root()), ensure_ascii=False))


@group.command(name="fire")
@click.argument("module_id")
@click.argument("task", required=False)
def _fire(module_id: str, task: str | None) -> None:
    root = _root()
    module_dir = paths.module_dir(root, module_id)
    data = manifest.load(module_dir / "module.yaml")
    timeout = data.get("limits", {}).get("max_runtime_seconds", 300)
    result = runtime.run_entry(root, module_id, module_dir, data["entry"], timeout)
    click.echo(
        json.dumps(
            {
                "module_id": module_id,
                "task": task,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
            ensure_ascii=False,
        )
    )
