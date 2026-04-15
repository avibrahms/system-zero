from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from sz.commands.cli import cli
from sz.interfaces import llm


def test_genesis_clc_failure_emits_event_and_leaves_no_profile(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# broken\n", encoding="utf-8")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SZ_CRONTAB_FILE", str(repo / "cron.txt"))
    runner = CliRunner()

    result = runner.invoke(cli, ["init", "--host", "generic", "--no-genesis", "--yes"])
    assert result.exit_code == 0, result.output

    def fail_invoke(prompt, *, schema_path=None, template_id=None, model=None, max_tokens=1024):
        raise llm.CLCFailure(["forced failure"])

    monkeypatch.setattr(llm, "invoke", fail_invoke)
    result = runner.invoke(cli, ["genesis", "--yes"])

    assert result.exit_code != 0
    assert not (repo / ".sz/repo-profile.json").exists()
    events = [
        json.loads(line)
        for line in (repo / ".sz/bus.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(event["type"] == "llm.call.failed" for event in events)
