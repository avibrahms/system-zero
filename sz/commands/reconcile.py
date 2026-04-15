import click
from sz.core import reconcile as engine


@click.command(help="Recompute capability bindings and run each module's reconcile hook.")
@click.option("--reason", default="manual")
def cmd(reason: str) -> None:
    reg = engine.reconcile(reason=reason)
    click.echo(
        f"Reconciled {len(reg['modules'])} modules, "
        f"{len(reg['bindings'])} bindings, "
        f"{len(reg['unsatisfied'])} unsatisfied."
    )
