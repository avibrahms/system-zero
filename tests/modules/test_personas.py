from __future__ import annotations

from sz.commands.cli import cli
from tests.modules._helpers import MODULES_ROOT, events, init_repo, install_many


def test_static_persona_installs_local_heartbeat_source(tmp_path, monkeypatch) -> None:
    _repo_root, runner = init_repo(tmp_path, monkeypatch, host="generic", host_mode="install")

    result = runner.invoke(
        cli,
        ["install", "heartbeat", "--source", str(MODULES_ROOT / "heartbeat")],
    )

    assert result.exit_code == 0, result.output


def test_dynamic_persona_rejects_heartbeat_and_runs_other_modules(tmp_path, monkeypatch) -> None:
    repo_root, runner = init_repo(tmp_path, monkeypatch, host="hermes", host_mode="adopt")

    result = runner.invoke(
        cli,
        ["install", "heartbeat", "--source", str(MODULES_ROOT / "heartbeat")],
    )
    assert result.exit_code != 0
    assert "dynamic persona" in result.output
    assert not (repo_root / ".sz" / "heartbeat").exists()

    install_many(runner, ["immune", "subconscious", "dreaming", "metabolism", "endocrine", "prediction"])
    (repo_root / "leak.py").write_text('password = "dynamic"\n', encoding="utf-8")
    result = runner.invoke(cli, ["tick", "--reason", "hermes"])
    assert result.exit_code == 0, result.output

    assert "health.snapshot" in [event["type"] for event in events(repo_root)]
