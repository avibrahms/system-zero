from __future__ import annotations

import os
import signal
import subprocess
import time
from typing import Literal

import click

from sz.core import paths


SignalStatus = Literal["sent", "missing", "denied"]


def _is_running(pid: int) -> bool:
    permission_denied = False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        permission_denied = True

    try:
        result = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return True
    state = result.stdout.strip()
    if result.returncode == 0 and bool(state):
        return not state.startswith("Z")
    return permission_denied


def _signal_process(pid: int, sig: signal.Signals) -> SignalStatus:
    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        return "missing"
    except PermissionError:
        return "denied"
    return "sent"


def _signal_process_group(pid: int, sig: signal.Signals) -> SignalStatus:
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        return "missing"
    except PermissionError:
        return "denied"
    return "sent"


def _cleanup(pid_path, stop_path) -> None:
    pid_path.unlink(missing_ok=True)
    stop_path.unlink(missing_ok=True)


@click.command(help="Stop the owned heartbeat loop.")
def cmd() -> None:
    root = paths.repo_root()
    pid_path = paths.heartbeat_pid_path(root)
    stop_path = paths.heartbeat_stop_path(root)
    if not pid_path.exists():
        click.echo("No heartbeat is running.")
        return

    pid = int(pid_path.read_text().strip())
    if not _is_running(pid):
        _cleanup(pid_path, stop_path)
        click.echo("No heartbeat is running.")
        return

    stop_path.write_text("stop\n", encoding="utf-8")
    group_status = _signal_process_group(pid, signal.SIGTERM)
    if group_status in {"missing", "denied"}:
        direct_status = _signal_process(pid, signal.SIGTERM)
        if direct_status == "missing" and not _is_running(pid):
            _cleanup(pid_path, stop_path)
            click.echo("No heartbeat is running.")
            return

    for _ in range(50):
        if not _is_running(pid):
            break
        time.sleep(0.1)

    if _is_running(pid):
        raise click.ClickException(f"Heartbeat process {pid} did not stop cleanly.")

    _cleanup(pid_path, stop_path)
    click.echo(f"Heartbeat stopped (pid {pid}).")
