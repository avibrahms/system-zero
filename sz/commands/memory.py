from __future__ import annotations

import json
from pathlib import Path

import click

from sz.core import paths
from sz.interfaces import memory


def _root() -> Path:
    return paths.repo_root()


def _parse_value(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


@click.group(help="Memory interface commands.")
def group() -> None:
    """Interact with the runtime KV and stream stores."""


@group.command(name="get")
@click.argument("key")
def _get(key: str) -> None:
    click.echo(json.dumps(memory.get(_root(), key), ensure_ascii=False))


@group.command(name="set")
@click.argument("key")
@click.argument("value")
def _set(key: str, value: str) -> None:
    stored = memory.set(_root(), key, _parse_value(value))
    click.echo(json.dumps({"key": key, "value": stored}, ensure_ascii=False))


@group.command(name="append")
@click.argument("stream")
@click.argument("json_line")
def _append(stream: str, json_line: str) -> None:
    item = _parse_value(json_line)
    click.echo(json.dumps(memory.append(_root(), stream, item), ensure_ascii=False))


@group.command(name="tail")
@click.argument("stream")
@click.option("--from-cursor", type=int, default=0, show_default=True)
def _tail(stream: str, from_cursor: int) -> None:
    items, cursor = memory.tail(_root(), stream, from_cursor=from_cursor)
    click.echo(json.dumps({"items": items, "next_cursor": cursor}, ensure_ascii=False))


@group.command(name="search")
@click.argument("query")
@click.option("--top", type=int, default=5, show_default=True)
def _search(query: str, top: int) -> None:
    click.echo(json.dumps(memory.search(_root(), query, top=top), ensure_ascii=False))
