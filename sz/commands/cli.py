"""sz CLI entry point."""
from __future__ import annotations

import click

from sz.commands import (
    absorb,
    bus,
    catalog,
    discovery,
    doctor,
    genesis,
    host,
    init,
    install,
    llm,
    ls,
    memory,
    reconcile,
    schedule,
    start,
    stop,
    tick,
    uninstall,
)


@click.group(help="System Zero — one-click autonomy + self-improvement for any repository.")
@click.version_option("0.1.0")
def cli() -> None:
    """Root command group."""


cli.add_command(init.cmd, name="init")
cli.add_command(install.cmd, name="install")
cli.add_command(uninstall.cmd, name="uninstall")
cli.add_command(ls.cmd, name="list")
cli.add_command(doctor.cmd, name="doctor")
cli.add_command(tick.cmd, name="tick")
cli.add_command(start.cmd, name="start")
cli.add_command(stop.cmd, name="stop")
cli.add_command(reconcile.cmd, name="reconcile")
cli.add_command(absorb.cmd, name="absorb")
cli.add_command(genesis.cmd, name="genesis")
cli.add_command(catalog.cmd, name="catalog")

cli.add_command(host.group, name="host")
cli.add_command(memory.group, name="memory")
cli.add_command(bus.group, name="bus")
cli.add_command(llm.group, name="llm")
cli.add_command(schedule.group, name="schedule")
cli.add_command(discovery.group, name="discovery")


def main() -> None:
    cli(standalone_mode=True)


if __name__ == "__main__":
    main()
