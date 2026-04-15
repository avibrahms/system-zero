"""sz login: paste a Clerk-issued JWT from the website after sign-in."""
from __future__ import annotations

import click

from sz.core import paths


@click.command(help="Paste the Clerk JWT from systemzero.dev/token to authenticate.")
@click.argument("token")
def cmd(token: str) -> None:
    p = paths.user_config_dir() / "token"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(token.strip())
    p.chmod(0o600)
    click.echo("token saved")
