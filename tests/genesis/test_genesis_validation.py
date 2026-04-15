from __future__ import annotations

import json
import os
from pathlib import Path

import yaml
from click.testing import CliRunner

from sz.commands.cli import cli
from tests.genesis.test_genesis_static import _events, _write_cli_shim


def test_genesis_rejects_recommendation_constraints_before_side_effects(
    tmp_path: Path,
    monkeypatch,
    force_profile,
) -> None:
    repo = tmp_path / "invalid-profile"
    repo.mkdir()
    (repo / "README.md").write_text("# invalid\n", encoding="utf-8")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SZ_CRONTAB_FILE", str(repo / "cron.txt"))
    force_profile(
        {
            "purpose": "A repo with an invalid recommendation set",
            "language": "other",
            "frameworks": [],
            "existing_heartbeat": "none",
            "goals": ["Run autonomously"],
            "recommended_modules": [
                {"id": "immune", "reason": "Only one module and not heartbeat."},
            ],
            "risk_flags": [],
        }
    )
    runner = CliRunner()

    result = runner.invoke(cli, ["init", "--host", "generic", "--no-genesis", "--yes"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(cli, ["genesis", "--yes"])

    assert result.exit_code != 0
    assert not (repo / ".sz/repo-profile.json").exists()
    assert not (repo / ".sz/immune").exists()
    assert any(event["type"] == "llm.call.failed" for event in _events(repo))


def test_genesis_unknown_heartbeat_uses_algorithmic_profile_and_no_heartbeat_module(
    tmp_path: Path,
    monkeypatch,
    force_profile,
) -> None:
    repo = tmp_path / "unknown-dynamic"
    repo.mkdir()
    (repo / "custom").mkdir()
    (repo / "custom/config.yaml").write_text("on_tick:\n  - custom tick\n", encoding="utf-8")
    (repo / "README.md").write_text("# unknown dynamic\n", encoding="utf-8")
    shim_dir = _write_cli_shim(repo)

    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", f"{shim_dir}:{os.environ.get('PATH', '')}")
    monkeypatch.setenv("SZ_CRONTAB_FILE", str(repo / "cron.txt"))
    monkeypatch.setenv("SZ_DEDUP_WINDOW_SECONDS", "0")
    force_profile(
        {
            "purpose": "A repo with a custom unknown pulse",
            "language": "other",
            "frameworks": [],
            "existing_heartbeat": "none",
            "goals": ["Keep the existing pulse visible", "Detect regressions", "Run safely"],
            "recommended_modules": [
                {"id": "immune", "reason": "Detect regressions."},
                {"id": "subconscious", "reason": "Summarize health."},
                {"id": "prediction", "reason": "Predict next events."},
            ],
            "risk_flags": [],
        }
    )
    runner = CliRunner()

    result = runner.invoke(cli, ["init", "--host", "generic", "--no-genesis", "--yes"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(cli, ["genesis", "--yes"])
    assert result.exit_code == 0, result.output

    profile = json.loads((repo / ".sz/repo-profile.json").read_text(encoding="utf-8"))
    assert profile["existing_heartbeat"] == "unknown"
    assert [item["id"] for item in profile["recommended_modules"]] == ["immune", "subconscious", "prediction"]
    assert not (repo / ".sz/heartbeat").exists()

    config = yaml.safe_load((repo / ".sz.yaml").read_text(encoding="utf-8"))
    assert config["host"] == "generic"
    assert config["host_mode"] == "install"

    event = next(event for event in _events(repo) if event["type"] == "repo.genesis.completed")
    assert event["payload"]["profile"]["existing_heartbeat"] == "unknown"
    assert event["payload"]["host"] == "generic"
    assert event["payload"]["host_mode"] == "install"
    runner.invoke(cli, ["stop"])
