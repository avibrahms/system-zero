"""sz insights — the redistribution side of the network effect."""
from __future__ import annotations

import json

import click

from sz.cloud import client


@click.command(help="Show community-wide or team-private aggregations from the cloud.")
@click.option("--scope", type=click.Choice(["public", "team"]), default="public")
def cmd(scope: str) -> None:
    if scope == "public":
        data = client.public_insights()
    else:
        data = client.team_insights()
    click.echo(json.dumps(data, indent=2))
