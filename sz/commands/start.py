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

    result = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=False,
    )
    state = result.stdout.strip()
    return result.returncode == 0 and bool(state) and not state.startswith("Z")


@click.command(help="Start the owned heartbeat loop.")
@click.option("--interval", type=int, default=None, help="Heartbeat interval in seconds.")
def cmd(interval: int | None) -> None:
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
        env={**os.environ.copy(), **({"SZ_INTERVAL": str(interval)} if interval else {})},
    )
    pid_path.write_text(f"{process.pid}\n")
    click.echo(f"Heartbeat started (pid {process.pid}).")
