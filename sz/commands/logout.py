"""sz logout: remove the saved Clerk JWT."""
from __future__ import annotations

import click

from sz.core import paths


@click.command(help="Remove the saved System Zero cloud token.")
def cmd() -> None:
    p = paths.user_config_dir() / "token"
    if p.exists():
        p.unlink()
    click.echo("token removed")
