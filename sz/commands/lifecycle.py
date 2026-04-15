from __future__ import annotations

import json
from pathlib import Path

import click

from sz.core import paths
from sz.interfaces import lifecycle


def _root() -> Path:
    return paths.repo_root()


@click.group(help="Lifecycle interface commands.")
def group() -> None:
    """Run module lifecycle hooks in isolation."""


@group.command(name="run-hook")
@click.argument("module_id")
@click.argument("hook_name")
@click.option("--env", "env_items", multiple=True, help="Extra env entries as KEY=VALUE.")
def _run_hook(module_id: str, hook_name: str, env_items: tuple[str, ...]) -> None:
    env_extra: dict[str, str] = {}
    for item in env_items:
        key, _, value = item.partition("=")
        env_extra[key] = value
    result = lifecycle.run_hook(_root(), module_id, hook_name, env_extra=env_extra or None)
    if result is None:
        click.echo(json.dumps({"status": "missing"}, ensure_ascii=False))
        return
    click.echo(
        json.dumps(
            {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
            ensure_ascii=False,
        )
    )
