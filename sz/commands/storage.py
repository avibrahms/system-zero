from __future__ import annotations

from pathlib import Path

import click

from sz.core import paths
from sz.interfaces import storage


def _root() -> Path:
    return paths.repo_root()


@click.group(help="Storage interface commands.")
def group() -> None:
    """Resolve module-private and shared storage paths."""


@group.command(name="path")
@click.argument("kind", type=click.Choice(["private", "shared"]))
@click.argument("name")
def _path(kind: str, name: str) -> None:
    root = _root()
    resolved = storage.private(root, name) if kind == "private" else storage.shared(root, name)
    click.echo(str(resolved))
