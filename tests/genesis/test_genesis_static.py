from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import stat
import sys

import jsonschema
import yaml
from click.testing import CliRunner

from sz.commands.cli import cli


def _write_cli_shim(repo_root: Path) -> Path:
    shim_dir = repo_root / "test-bin"
    shim_dir.mkdir()
    shim_path = shim_dir / "sz"
    project_root = Path(__file__).resolve().parents[2]
    shim_path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"export PYTHONPATH={shlex.quote(str(project_root))}:\"${{PYTHONPATH:-}}\"\n"
        f"exec {shlex.quote(sys.executable)} -m sz.commands.cli \"$@\"\n",
        encoding="utf-8",
    )
    shim_path.chmod(shim_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return shim_dir


def _events(repo_root: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (repo_root / ".sz/bus.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _static_profile() -> dict:
    return {
        "purpose": "A small Python weather bot",
        "language": "python",
        "frameworks": [],
        "existing_heartbeat": "none",
        "goals": ["Post daily weather", "Recover from API failures", "Run autonomously"],
        "recommended_modules": [
            {"id": "heartbeat", "reason": "Start the owned pulse."},
            {"id": "immune", "reason": "Detect API failures."},
            {"id": "subconscious", "reason": "Summarize health."},
        ],
        "risk_flags": [],
    }


def test_genesis_static_repo_installs_modules_and_emits_activity(tmp_path: Path, monkeypatch, force_profile) -> None:
    repo = tmp_path / "static-repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname = \"weather-bot\"\n", encoding="utf-8")
    (repo / "README.md").write_text("# weather-bot\nPosts daily weather to Slack.\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src/main.py").write_text("print('weather')\n", encoding="utf-8")
    shim_dir = _write_cli_shim(repo)

    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", f"{shim_dir}:{os.environ.get('PATH', '')}")
    monkeypatch.setenv("SZ_CRONTAB_FILE", str(repo / "cron.txt"))
    monkeypatch.setenv("SZ_DEDUP_WINDOW_SECONDS", "0")
    force_profile(_static_profile())
    runner = CliRunner()

    result = runner.invoke(cli, ["init", "--host", "generic", "--no-genesis", "--yes"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli, ["genesis", "--yes"])
    assert result.exit_code == 0, result.output

    schema = json.loads((Path(__file__).resolve().parents[2] / "spec/v0.1.0/repo-profile.schema.json").read_text())
    profile = json.loads((repo / ".sz/repo-profile.json").read_text(encoding="utf-8"))
    jsonschema.validate(profile, schema)
    assert profile["existing_heartbeat"] == "none"

    for module_id in ["heartbeat", "immune", "subconscious"]:
        assert (repo / ".sz" / module_id / "module.yaml").exists()

    config = yaml.safe_load((repo / ".sz.yaml").read_text(encoding="utf-8"))
    assert config["host"] == "generic"
    assert config["host_mode"] == "install"

    event_types = [event["type"] for event in _events(repo)]
    assert "repo.genesis.completed" in event_types
    assert "tick" in event_types
    assert "pulse.tick" in event_types
    assert "health.snapshot" in event_types

    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0, result.output
    assert "heartbeat\t0.1.0\thealthy" in result.output
    result = runner.invoke(cli, ["bus", "tail", "--last", "5"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(cli, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "heartbeat: ok" in result.output

    runner.invoke(cli, ["stop"])


def test_genesis_static_repo_works_with_mock_provider_schema_ref(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "mock-repo"
    repo.mkdir()
    (repo / "README.md").write_text("# mock repo\n", encoding="utf-8")
    shim_dir = _write_cli_shim(repo)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", f"{shim_dir}:{os.environ.get('PATH', '')}")
    monkeypatch.setenv("SZ_LLM_PROVIDER", "mock")
    monkeypatch.setenv("SZ_CRONTAB_FILE", str(repo / "cron.txt"))
    monkeypatch.setenv("SZ_DEDUP_WINDOW_SECONDS", "0")
    runner = CliRunner()

    result = runner.invoke(cli, ["init", "--host", "generic", "--no-genesis", "--yes"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(cli, ["genesis", "--yes"])
    assert result.exit_code == 0, result.output

    profile = json.loads((repo / ".sz/repo-profile.json").read_text(encoding="utf-8"))
    assert profile["purpose"] == "mock repo"
    assert [item["id"] for item in profile["recommended_modules"]] == ["heartbeat", "immune", "subconscious"]
    assert any(event["type"] == "repo.genesis.completed" for event in _events(repo))
    runner.invoke(cli, ["stop"])
