from __future__ import annotations

import json
import os
from pathlib import Path

from click.testing import CliRunner

from sz.commands.cli import cli
from tests.genesis.test_genesis_static import _write_cli_shim


def test_genesis_preserves_profile_and_emits_error_for_unknown_module(tmp_path: Path, monkeypatch, force_profile) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# odd\n", encoding="utf-8")
    shim_dir = _write_cli_shim(repo)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", f"{shim_dir}:{os.environ.get('PATH', '')}")
    monkeypatch.setenv("SZ_CRONTAB_FILE", str(repo / "cron.txt"))
    monkeypatch.setenv("SZ_DEDUP_WINDOW_SECONDS", "0")
    force_profile(
        {
            "purpose": "A repo with one bad recommendation",
            "language": "other",
            "frameworks": [],
            "existing_heartbeat": "none",
            "goals": ["Install what can be installed"],
            "recommended_modules": [
                {"id": "heartbeat", "reason": "Start the pulse."},
                {"id": "ghost-module", "reason": "Not in the catalog."},
                {"id": "immune", "reason": "Detect failures."},
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
    assert any(item["id"] == "ghost-module" for item in profile["recommended_modules"])
    assert (repo / ".sz/heartbeat/module.yaml").exists()
    assert (repo / ".sz/immune/module.yaml").exists()
    assert not (repo / ".sz/ghost-module").exists()

    events = [
        json.loads(line)
        for line in (repo / ".sz/bus.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(
        event["type"] == "module.errored" and event["payload"].get("id") == "ghost-module"
        for event in events
    )
    runner.invoke(cli, ["stop"])
