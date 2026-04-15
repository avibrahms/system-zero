from __future__ import annotations

import webbrowser

import click

from sz.cloud import client


@click.command(help="Open Stripe checkout to upgrade to Pro or Team.")
@click.option("--tier", type=click.Choice(["pro", "team"]), default="pro")
def cmd(tier: str) -> None:
    sess = client.checkout(
        tier=tier,
        success_url="https://systemzero.dev/welcome",
        cancel_url="https://systemzero.dev/pricing",
    )
    click.echo(f"Open: {sess['url']}")
    webbrowser.open(sess["url"])
