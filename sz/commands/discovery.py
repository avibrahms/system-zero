from __future__ import annotations

import json
from pathlib import Path

import click

from sz.core import paths
from sz.interfaces import discovery


def _root() -> Path:
    return paths.repo_root()


@click.group(help="Discovery interface commands.")
def group() -> None:
    """Inspect the live module landscape."""


@group.command(name="list")
def _list() -> None:
    click.echo(json.dumps(discovery.list_modules(_root()), ensure_ascii=False))


@group.command(name="providers")
@click.argument("capability")
def _providers(capability: str) -> None:
    click.echo(json.dumps(discovery.providers(_root(), capability), ensure_ascii=False))


@group.command(name="requirers")
@click.argument("capability")
def _requirers(capability: str) -> None:
    click.echo(json.dumps(discovery.requirers(_root(), capability), ensure_ascii=False))


@group.command(name="resolve")
@click.argument("capability")
def _resolve(capability: str) -> None:
    click.echo(json.dumps(discovery.resolve(_root(), capability), ensure_ascii=False))


@group.command(name="health")
@click.argument("module_id")
def _health(module_id: str) -> None:
    click.echo(json.dumps(discovery.health(_root(), module_id), ensure_ascii=False))


@group.command(name="profile")
def _profile() -> None:
    click.echo(json.dumps(discovery.profile(_root()), ensure_ascii=False))
