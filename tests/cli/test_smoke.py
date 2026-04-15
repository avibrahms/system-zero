from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

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


def _run_cli_smoke(tmp_path: Path, monkeypatch, host: str, host_mode: str) -> None:
    repo_root = tmp_path / f"{host_mode}-repo"
    repo_root.mkdir()
    module_source = tmp_path / "hello-module"
    module_source.mkdir()
    _write_module(module_source)

    runner = CliRunner()
    monkeypatch.chdir(repo_root)

    result = runner.invoke(cli, ["init", "--host", host, "--host-mode", host_mode, "--yes"])
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

    result = runner.invoke(cli, ["tick", "--reason", "smoke"])
    assert result.exit_code == 0, result.output
    assert (repo_root / "tick-ran.txt").read_text().strip() == "tick-ran"
    assert (repo_root / "llm-bin.txt").read_text().strip()

    result = runner.invoke(cli, ["doctor"])
    assert result.exit_code == 0, result.output
    assert (repo_root / "doctor-ran.txt").read_text().strip() == "doctor-ok"

    stub_expectations = {
        "reconcile": "Reconcile is implemented in phase 04.",
        "absorb": "Absorb is implemented in phase 06.",
        "genesis": "Repo Genesis is implemented in phase 07.",
        "catalog": "Catalog is implemented in phase 09.",
        "host": "Host management is implemented in phase 05.",
        "memory": "Memory interface is implemented in phase 03.",
        "bus": "Bus interface is implemented in phase 03.",
        "llm": "LLM interface is implemented in phase 03.",
        "schedule": "Schedule interface is implemented in phase 03.",
        "discovery": "Discovery interface is implemented in phase 03.",
    }
    for command, expected in stub_expectations.items():
        result = runner.invoke(cli, [command])
        assert result.exit_code == 0, result.output
        assert expected in result.output

    result = runner.invoke(cli, ["uninstall", "hello-module", "--confirm"])
    assert result.exit_code == 0, result.output
    assert (repo_root / "uninstall-ran.txt").read_text().strip() == "uninstalled"
    assert not (sz_dir / "hello-module").exists()

    events = [
        json.loads(line)
        for line in (sz_dir / "bus.jsonl").read_text().splitlines()
        if line.strip()
    ]
    event_types = [event["type"] for event in events]
    assert event_types == [
        "sz.initialized",
        "module.installed",
        "tick",
        "module.uninstalled",
    ]
    assert events[0]["payload"]["host"] == host
    assert events[0]["payload"]["host_mode"] == host_mode


def test_cli_smoke_static_repo(tmp_path: Path, monkeypatch) -> None:
    _run_cli_smoke(tmp_path, monkeypatch, host="generic", host_mode="install")


def test_cli_smoke_dynamic_adopt_repo(tmp_path: Path, monkeypatch) -> None:
    _run_cli_smoke(tmp_path, monkeypatch, host="openclaw", host_mode="adopt")
