from __future__ import annotations

import os
import signal
import time

import click

from sz.core import paths


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


@click.command(help="Stop the owned heartbeat loop.")
def cmd() -> None:
    root = paths.repo_root()
    pid_path = paths.heartbeat_pid_path(root)
    if not pid_path.exists():
        click.echo("No heartbeat is running.")
        return

    pid = int(pid_path.read_text().strip())
    if not _is_running(pid):
        pid_path.unlink(missing_ok=True)
        click.echo("No heartbeat is running.")
        return

    os.kill(pid, signal.SIGTERM)
    for _ in range(20):
        if not _is_running(pid):
            break
        time.sleep(0.1)
    pid_path.unlink(missing_ok=True)
    click.echo(f"Heartbeat stopped (pid {pid}).")
