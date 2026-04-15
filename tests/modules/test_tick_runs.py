from __future__ import annotations

import json

from sz.commands.cli import cli
from tests.modules._helpers import events, init_repo, install_many


def test_tick_runs_installed_modules_and_emits_core_events(tmp_path, monkeypatch) -> None:
    repo_root, runner = init_repo(tmp_path, monkeypatch)
    install_many(runner, ["heartbeat", "immune", "subconscious", "endocrine", "prediction"])
    (repo_root / "leak.py").write_text('password = "x"\n', encoding="utf-8")

    for _ in range(2):
        result = runner.invoke(cli, ["tick", "--reason", "modules-test"])
        assert result.exit_code == 0, result.output

    event_types = [event["type"] for event in events(repo_root)]
    assert "pulse.tick" in event_types
    assert "anomaly.detected" in event_types
    assert "health.snapshot" in event_types
    assert "prediction.next" in event_types

    snapshot_result = runner.invoke(cli, ["memory", "get", "subconscious.snapshot"])
    assert snapshot_result.exit_code == 0, snapshot_result.output
    snapshot = json.loads(snapshot_result.output)
    assert snapshot["color"] in {"AMBER", "RED"}
    assert snapshot["anomaly_count"] >= 2

    prediction_events = [event for event in events(repo_root) if event["type"] == "prediction.next"]
    assert prediction_events[-1]["payload"]["predictions"]
