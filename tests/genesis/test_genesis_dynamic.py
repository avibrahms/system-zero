from __future__ import annotations

import os
from pathlib import Path

import yaml
from click.testing import CliRunner

from sz.commands.cli import cli
from tests.genesis.test_genesis_static import _events, _write_cli_shim


def _dynamic_profile() -> dict:
    return {
        "purpose": "A dynamic Hermes repository",
        "language": "python",
        "frameworks": ["hermes"],
        "existing_heartbeat": "hermes",
        "goals": ["Adopt the existing pulse", "Detect regressions", "Run safely"],
        "recommended_modules": [
            {"id": "immune", "reason": "Detect regressions."},
            {"id": "subconscious", "reason": "Summarize health."},
            {"id": "prediction", "reason": "Predict next events."},
        ],
        "risk_flags": [],
    }


def test_genesis_dynamic_repo_adopts_existing_heartbeat(tmp_path: Path, monkeypatch, force_profile) -> None:
    repo = tmp_path / "dynamic-repo"
    repo.mkdir()
    (repo / ".hermes").mkdir()
    hermes_config = repo / ".hermes/config.yaml"
    hermes_config.write_text("hooks:\n  on_tick:\n    - existing hermes task\n", encoding="utf-8")
    (repo / "README.md").write_text("# dynamic\n", encoding="utf-8")
    shim_dir = _write_cli_shim(repo)

    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", f"{shim_dir}:{os.environ.get('PATH', '')}")
    monkeypatch.setenv("SZ_CRONTAB_FILE", str(repo / "cron.txt"))
    monkeypatch.setenv("SZ_DEDUP_WINDOW_SECONDS", "0")
    force_profile(_dynamic_profile())
    runner = CliRunner()

    result = runner.invoke(cli, ["init", "--host", "hermes", "--host-mode", "adopt", "--no-genesis", "--yes"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(cli, ["genesis", "--yes"])
    assert result.exit_code == 0, result.output

    config = yaml.safe_load((repo / ".sz.yaml").read_text(encoding="utf-8"))
    assert config["host"] == "hermes"
    assert config["host_mode"] == "adopt"
    assert not (repo / ".sz/heartbeat.pid").exists()

    hermes = yaml.safe_load(hermes_config.read_text(encoding="utf-8"))
    assert "sz tick --reason hermes" in hermes["hooks"]["on_tick"]
    for module_id in ["immune", "subconscious", "prediction"]:
        assert (repo / ".sz" / module_id / "module.yaml").exists()
    assert not (repo / ".sz/heartbeat").exists()

    event = next(event for event in _events(repo) if event["type"] == "repo.genesis.completed")
    assert event["payload"]["host"] == "hermes"
    assert event["payload"]["host_mode"] == "adopt"
