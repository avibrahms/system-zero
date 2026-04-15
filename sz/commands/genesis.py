from __future__ import annotations

import json

import click

from sz.core import genesis as engine
from sz.interfaces import llm


@click.command(help="Make this repo alive (Repo Genesis).")
@click.option("--hint", default="", help="Optional one-line hint about repo purpose.")
@click.option("--yes", "auto_yes", is_flag=True, help="Skip confirmation.")
def cmd(hint, auto_yes):
    try:
        result = engine.genesis(hint=hint, auto_yes=auto_yes)
    except llm.CLCFailure as exc:
        raise click.ClickException("Repo Genesis CLC failed: " + "; ".join(exc.errors)) from exc
    click.echo(json.dumps({k: v for k, v in result.items() if k != "profile"}, indent=2))
