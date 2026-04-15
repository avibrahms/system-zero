from __future__ import annotations

import os
import signal
import subprocess
import time

import click

from sz.core import paths


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False

    result = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=False,
    )
    state = result.stdout.strip()
    return result.returncode == 0 and bool(state) and not state.startswith("Z")


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

    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        pid_path.unlink(missing_ok=True)
        click.echo("No heartbeat is running.")
        return

    for _ in range(20):
        if not _is_running(pid):
            break
        time.sleep(0.1)

    if _is_running(pid):
        raise click.ClickException(f"Heartbeat process {pid} did not stop cleanly.")

    pid_path.unlink(missing_ok=True)
    click.echo(f"Heartbeat stopped (pid {pid}).")
