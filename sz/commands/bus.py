from __future__ import annotations

import json
from pathlib import Path

import click

from sz.core import paths
from sz.interfaces import bus


def _root() -> Path:
    return paths.repo_root()


@click.group(help="Bus interface commands.")
def group() -> None:
    """Interact with the append-only runtime bus."""


@group.command(name="emit")
@click.argument("event_type")
@click.argument("json_payload")
@click.option("--module", "module_id", default="s0", show_default=True)
@click.option("--correlation-id", default=None)
def _emit(event_type: str, json_payload: str, module_id: str, correlation_id: str | None) -> None:
    payload = json.loads(json_payload)
    event = bus.emit(
        paths.bus_path(_root()),
        module_id,
        event_type,
        payload,
        correlation_id=correlation_id,
    )
    click.echo(json.dumps(event, ensure_ascii=False))


@group.command(name="subscribe")
@click.argument("module_id")
@click.argument("pattern")
def _subscribe(module_id: str, pattern: str) -> None:
    click.echo(json.dumps(bus.subscribe(_root(), module_id, pattern), ensure_ascii=False))


@group.command(name="tail")
@click.option("--last", type=int, default=None)
@click.option("--filter", "pattern", default=None)
def _tail(last: int | None, pattern: str | None) -> None:
    events = bus.tail(paths.bus_path(_root()), last=last, pattern=pattern)
    click.echo(json.dumps(events, ensure_ascii=False))
