from __future__ import annotations

import os
import signal
import subprocess

import click

from sz.core import paths


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


@click.command(help="Start the owned heartbeat loop.")
def cmd() -> None:
    root = paths.repo_root()
    pid_path = paths.heartbeat_pid_path(root)
    if pid_path.exists():
        pid = int(pid_path.read_text().strip())
        if _is_running(pid):
            click.echo(f"Heartbeat already running (pid {pid}).")
            return
        pid_path.unlink()

    log_file = paths.heartbeat_log_path(root).open("a", encoding="utf-8")
    process = subprocess.Popen(
        ["/bin/bash", str(paths.heartbeat_script_path(root))],
        cwd=root,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env=os.environ.copy(),
    )
    pid_path.write_text(f"{process.pid}\n")
    click.echo(f"Heartbeat started (pid {process.pid}).")
