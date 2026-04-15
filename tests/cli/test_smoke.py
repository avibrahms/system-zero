from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import stat
import sys
import time

import yaml
from click.testing import CliRunner

from sz.commands import stop as stop_command
from sz.commands.cli import cli


def _write_module(source: Path) -> None:
    (source / "entry.sh").write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [ -z \"${SZ_LLM_BIN:-}\" ]; then\n"
        "  echo 'missing SZ_LLM_BIN' >&2\n"
        "  exit 1\n"
        "fi\n"
        "printf '%s\\n' \"$SZ_LLM_BIN\" > \"$SZ_REPO_ROOT/llm-bin.txt\"\n"
        "printf 'tick-ran\\n' >> \"$SZ_REPO_ROOT/tick-ran.txt\"\n"
    )
    (source / "install.sh").write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [ -z \"${SZ_LLM_BIN:-}\" ]; then\n"
        "  echo 'missing SZ_LLM_BIN' >&2\n"
        "  exit 1\n"
        "fi\n"
        "printf '%s\\n' \"$SZ_LLM_BIN\" > \"$SZ_MODULE_DIR/install-llm-bin.txt\"\n"
        "printf 'installed\\n' > \"$SZ_MODULE_DIR/install.txt\"\n"
    )
    (source / "doctor.sh").write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [ -z \"${SZ_LLM_BIN:-}\" ]; then\n"
        "  echo 'missing SZ_LLM_BIN' >&2\n"
        "  exit 1\n"
        "fi\n"
        "printf 'doctor-ok\\n' > \"$SZ_REPO_ROOT/doctor-ran.txt\"\n"
    )
    (source / "uninstall.sh").write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [ -z \"${SZ_LLM_BIN:-}\" ]; then\n"
        "  echo 'missing SZ_LLM_BIN' >&2\n"
        "  exit 1\n"
        "fi\n"
        "printf 'uninstalled\\n' > \"$SZ_REPO_ROOT/uninstall-ran.txt\"\n"
    )
    (source / "reconcile.sh").write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "exit 0\n"
    )
    (source / "module.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "hello-module",
                "version": "0.1.0",
                "category": "testing",
                "description": "Synthetic module for smoke tests",
                "entry": {"type": "bash", "command": "entry.sh"},
                "triggers": [{"on": "tick"}],
                "hooks": {
                    "install": "install.sh",
                    "doctor": "doctor.sh",
                    "uninstall": "uninstall.sh",
                    "reconcile": "reconcile.sh",
                },
            },
            sort_keys=False,
        )
    )


def _write_cli_shim(repo_root: Path) -> Path:
    shim_dir = repo_root / "test-bin"
    shim_dir.mkdir()
    shim_path = shim_dir / "sz"
    project_root = Path(__file__).resolve().parents[2]
    shim_path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"export PYTHONPATH={shlex.quote(str(project_root))}:\"${{PYTHONPATH:-}}\"\n"
        f"exec {shlex.quote(sys.executable)} -m sz.commands.cli \"$@\"\n"
    )
    shim_path.chmod(shim_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return shim_dir


def _read_events(bus_path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in bus_path.read_text().splitlines()
        if line.strip()
    ]


def _wait_for_heartbeat_tick(bus_path: Path, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        events = _read_events(bus_path)
        if any(
            event["type"] == "tick" and event["payload"].get("reason") == "heartbeat"
            for event in events
        ):
            return
        time.sleep(0.1)
    raise AssertionError("Timed out waiting for a heartbeat tick.")


def _wait_for_file(path: Path, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists():
            return
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for {path.name}.")


def _run_cli_smoke(tmp_path: Path, monkeypatch, host: str, host_mode: str) -> None:
    repo_root = tmp_path / f"{host_mode}-repo"
    repo_root.mkdir()
    module_source = tmp_path / "hello-module"
    module_source.mkdir()
    _write_module(module_source)
    shim_dir = _write_cli_shim(repo_root)

    runner = CliRunner()
    monkeypatch.chdir(repo_root)
    monkeypatch.setenv("PATH", f"{shim_dir}:{os.environ.get('PATH', '')}")
    monkeypatch.setenv("SZ_INTERVAL", "1")
    monkeypatch.setenv("SZ_DEDUP_WINDOW_SECONDS", "0")
    monkeypatch.setenv("SZ_CRONTAB_FILE", str(repo_root / "cron.txt"))
    if host == "openclaw":
        (repo_root / ".openclaw").mkdir()
        (repo_root / ".openclaw/config.yaml").write_text("hooks:\n  on_tick: []\n")

    result = runner.invoke(cli, ["init", "--host", host, "--host-mode", host_mode, "--no-genesis", "--yes"])
    assert result.exit_code == 0, result.output

    sz_dir = repo_root / ".sz"
    assert (sz_dir / "bus.jsonl").exists()
    assert (sz_dir / "bin" / "heartbeat.sh").exists()
    assert (sz_dir / "memory" / "streams").is_dir()
    assert (sz_dir / "memory" / "cursors").is_dir()
    assert (sz_dir / "shared").is_dir()

    config = yaml.safe_load((repo_root / ".sz.yaml").read_text())
    assert config["host"] == host
    assert config["host_mode"] == host_mode
    assert config["cloud"]["tier"] == "free"

    result = runner.invoke(cli, ["install", "hello-module", "--source", str(module_source)])
    assert result.exit_code == 0, result.output
    assert (sz_dir / "hello-module" / "install.txt").read_text().strip() == "installed"
    assert (sz_dir / "hello-module" / "install-llm-bin.txt").read_text().strip()

    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0, result.output
    assert "hello-module\t0.1.0\thealthy" in result.output

    result = runner.invoke(cli, ["start"])
    assert result.exit_code == 0, result.output
    pid_path = sz_dir / "heartbeat.pid"
    assert pid_path.exists()
    _wait_for_heartbeat_tick(sz_dir / "bus.jsonl")
    _wait_for_file(repo_root / "tick-ran.txt")

    result = runner.invoke(cli, ["stop"])
    assert result.exit_code == 0, result.output
    assert not pid_path.exists()

    time.sleep(1.2)
    heartbeat_tick_count = sum(
        1
        for event in _read_events(sz_dir / "bus.jsonl")
        if event["type"] == "tick" and event["payload"].get("reason") == "heartbeat"
    )
    time.sleep(1.2)
    assert (
        sum(
            1
            for event in _read_events(sz_dir / "bus.jsonl")
            if event["type"] == "tick" and event["payload"].get("reason") == "heartbeat"
        )
        == heartbeat_tick_count
    )
    tick_runs_before_manual = len((repo_root / "tick-ran.txt").read_text().splitlines())

    result = runner.invoke(cli, ["tick", "--reason", "smoke"])
    assert result.exit_code == 0, result.output
    assert len((repo_root / "tick-ran.txt").read_text().splitlines()) == tick_runs_before_manual + 1
    assert (repo_root / "llm-bin.txt").read_text().strip()

    result = runner.invoke(cli, ["doctor"])
    assert result.exit_code == 0, result.output
    assert (repo_root / "doctor-ran.txt").read_text().strip() == "doctor-ok"

    result = runner.invoke(cli, ["absorb", "--help"])
    assert result.exit_code == 0, result.output
    assert "Absorb a feature from an open-source repo as an S0 module." in result.output
    assert "--feature" in result.output

    stub_expectations = {
        "catalog": "Catalog is implemented in phase 09.",
    }
    for command, expected in stub_expectations.items():
        result = runner.invoke(cli, [command])
        assert result.exit_code == 0, result.output
        assert expected in result.output

    result = runner.invoke(cli, ["memory", "set", "answer", "42"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(cli, ["memory", "get", "answer"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == 42

    result = runner.invoke(cli, ["bus", "tail", "--last", "1"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)[0]["type"] == "tick"

    result = runner.invoke(cli, ["bus", "emit", "custom.ready", '{"ok":true}'])
    assert result.exit_code == 0, result.output
    emitted = json.loads(result.output)
    assert emitted["module"] == "s0"
    assert emitted["type"] == "custom.ready"
    assert emitted["payload"] == {"ok": True}

    monkeypatch.setenv("SZ_LLM_PROVIDER", "mock")
    result = runner.invoke(cli, ["llm", "provider"])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "mock"

    result = runner.invoke(cli, ["schedule", "list"])
    assert result.exit_code == 0, result.output
    schedule_entries = json.loads(result.output)
    assert any(entry["module_id"] == "hello-module" for entry in schedule_entries)

    result = runner.invoke(cli, ["discovery", "list"])
    assert result.exit_code == 0, result.output
    modules = json.loads(result.output)
    assert any(item["module_id"] == "hello-module" for item in modules)

    result = runner.invoke(cli, ["storage", "path", "private", "hello-module"])
    assert result.exit_code == 0, result.output
    assert result.output.strip().endswith("/.sz/hello-module")

    result = runner.invoke(cli, ["lifecycle", "run-hook", "hello-module", "doctor"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["returncode"] == 0

    result = runner.invoke(cli, ["uninstall", "hello-module", "--confirm"])
    assert result.exit_code == 0, result.output
    assert (repo_root / "uninstall-ran.txt").read_text().strip() == "uninstalled"
    assert not (sz_dir / "hello-module").exists()

    events = _read_events(sz_dir / "bus.jsonl")
    event_types = [event["type"] for event in events]
    assert event_types[:2] == ["sz.initialized", "module.installed"]
    assert event_types[-1] == "module.uninstalled"
    assert any(
        event["type"] == "tick" and event["payload"].get("reason") == "heartbeat"
        for event in events
    )
    assert any(
        event["type"] == "tick" and event["payload"].get("reason") == "smoke"
        for event in events
    )
    assert events[0]["payload"]["host"] == host
    assert events[0]["payload"]["host_mode"] == host_mode


def test_cli_smoke_static_repo(tmp_path: Path, monkeypatch) -> None:
    _run_cli_smoke(tmp_path, monkeypatch, host="generic", host_mode="install")


def test_cli_smoke_dynamic_adopt_repo(tmp_path: Path, monkeypatch) -> None:
    _run_cli_smoke(tmp_path, monkeypatch, host="openclaw", host_mode="adopt")


def test_stop_falls_back_when_process_group_signal_is_denied(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "permission-fallback-repo"
    repo_root.mkdir()
    shim_dir = _write_cli_shim(repo_root)

    runner = CliRunner()
    monkeypatch.chdir(repo_root)
    monkeypatch.setenv("PATH", f"{shim_dir}:{os.environ.get('PATH', '')}")
    monkeypatch.setenv("SZ_INTERVAL", "1")
    monkeypatch.setenv("SZ_DEDUP_WINDOW_SECONDS", "0")
    monkeypatch.setenv("SZ_CRONTAB_FILE", str(repo_root / "cron.txt"))

    result = runner.invoke(cli, ["init", "--host", "generic", "--host-mode", "install", "--no-genesis", "--yes"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli, ["start"])
    assert result.exit_code == 0, result.output
    pid_path = repo_root / ".sz" / "heartbeat.pid"
    pid = int(pid_path.read_text().strip())
    _wait_for_heartbeat_tick(repo_root / ".sz" / "bus.jsonl")

    def deny_process_group_signal(pid: int, sig: int) -> None:
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(stop_command.os, "killpg", deny_process_group_signal)
    result = runner.invoke(cli, ["stop"])
    assert result.exit_code == 0, result.output
    assert not pid_path.exists()
    assert not (repo_root / ".sz" / "heartbeat.stop").exists()
    assert not stop_command._is_running(pid)
