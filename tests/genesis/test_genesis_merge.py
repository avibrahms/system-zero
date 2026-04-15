from __future__ import annotations

import json
import os
from pathlib import Path

import yaml
from click.testing import CliRunner

from sz.commands.cli import cli
from tests.genesis.test_genesis_dynamic import _dynamic_profile
from tests.genesis.test_genesis_static import _events, _write_cli_shim


def test_init_merge_mode_runs_genesis_and_dedupes_duplicate_ticks(tmp_path: Path, monkeypatch, force_profile) -> None:
    repo = tmp_path / "merge-repo"
    repo.mkdir()
    (repo / ".hermes").mkdir()
    hermes_config = repo / ".hermes/config.yaml"
    hermes_config.write_text("hooks:\n  on_tick: []\n", encoding="utf-8")
    (repo / "README.md").write_text("# merge\n", encoding="utf-8")
    shim_dir = _write_cli_shim(repo)

    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", f"{shim_dir}:{os.environ.get('PATH', '')}")
    monkeypatch.setenv("SZ_CRONTAB_FILE", str(repo / "cron.txt"))
    force_profile(_dynamic_profile())
    runner = CliRunner()

    result = runner.invoke(cli, ["init", "--host", "hermes", "--host-mode", "merge", "--yes"])
    assert result.exit_code == 0, result.output

    config = yaml.safe_load((repo / ".sz.yaml").read_text(encoding="utf-8"))
    assert config["host"] == "hermes"
    assert config["host_mode"] == "merge"
    assert "sz tick --reason cron" in (repo / "cron.txt").read_text(encoding="utf-8")
    hermes = yaml.safe_load(hermes_config.read_text(encoding="utf-8"))
    assert "sz tick --reason hermes" in hermes["hooks"]["on_tick"]

    tick_count = sum(1 for event in _events(repo) if event["type"] == "tick")
    result = runner.invoke(cli, ["tick", "--reason", "duplicate"])
    assert result.exit_code == 0, result.output
    assert sum(1 for event in _events(repo) if event["type"] == "tick") == tick_count

    last_tick = json.loads((repo / ".sz/memory/kv.json").read_text(encoding="utf-8"))["last_tick_ts"]
    assert last_tick.endswith("Z")
    runner.invoke(cli, ["stop"])
