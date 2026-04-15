from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from sz.commands.cli import cli


def _init_git(repo: Path) -> None:
    (repo / ".git" / "hooks").mkdir(parents=True)


def _plant_marker(repo: Path, adapter: str) -> Path:
    if adapter == "hermes":
        path = repo / ".hermes/config.yaml"
        path.parent.mkdir()
        path.write_text("hooks:\n  on_tick:\n    - existing hermes task\n")
        return path
    if adapter == "openclaw":
        path = repo / ".openclaw/config.yaml"
        path.parent.mkdir()
        path.write_text("hooks:\n  on_tick:\n    - existing openclaw task\n")
        return path
    if adapter == "metaclaw":
        path = repo / ".metaclaw/config.yaml"
        path.parent.mkdir()
        path.write_text("hooks:\n  on_tick:\n    - existing metaclaw task\n")
        return path
    path = repo / "core/system/maintenance-registry.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("tasks:\n  existing-task:\n    command: keep-running\n")
    return path


def _invoke(runner: CliRunner, args: list[str]) -> str:
    result = runner.invoke(cli, args)
    assert result.exit_code == 0, result.output
    return result.output


def _hook_command(config_path: Path, adapter: str) -> bool:
    data = yaml.safe_load(config_path.read_text()) or {}
    if adapter == "connection_engine":
        return data["tasks"]["sz--tick"]["command"] == "sz tick --reason connection_engine"
    return f"sz tick --reason {adapter}" in data["hooks"]["on_tick"]


def test_adopt_mode_adapters_do_not_install_cron(tmp_path: Path, monkeypatch) -> None:
    for adapter in ["hermes", "openclaw", "metaclaw", "connection_engine"]:
        repo = tmp_path / adapter
        repo.mkdir()
        _init_git(repo)
        marker = _plant_marker(repo, adapter)
        cron_file = repo / "cron.txt"
        monkeypatch.chdir(repo)
        monkeypatch.setenv("SZ_CRONTAB_FILE", str(cron_file))
        runner = CliRunner()

        _invoke(runner, ["init", "--host", "generic", "--no-genesis", "--yes"])
        assert "sz tick --reason cron" in cron_file.read_text()
        _invoke(runner, ["host", "install", adapter])

        assert _invoke(runner, ["host", "current"]).strip() == f"{adapter} (adopt)"
        assert _hook_command(marker, adapter)
        assert "sz tick --reason cron" not in cron_file.read_text()

        before = yaml.safe_load(marker.read_text()) or {}
        _invoke(runner, ["host", "uninstall"])
        after = yaml.safe_load(marker.read_text()) or {}
        assert "sz tick --reason cron" not in cron_file.read_text()
        if adapter == "connection_engine":
            assert "sz--tick" not in after.get("tasks", {})
            assert before["tasks"]["existing-task"] == after["tasks"]["existing-task"]
        else:
            assert f"sz tick --reason {adapter}" not in after.get("hooks", {}).get("on_tick", [])
            assert before["hooks"]["on_tick"][0].startswith("existing")


def test_merge_mode_installs_adopt_hook_and_generic_cron(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "merge"
    repo.mkdir()
    _init_git(repo)
    marker = _plant_marker(repo, "hermes")
    cron_file = repo / "cron.txt"
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SZ_CRONTAB_FILE", str(cron_file))
    runner = CliRunner()

    _invoke(runner, ["init", "--host", "generic", "--no-genesis", "--yes"])
    _invoke(runner, ["host", "install", "hermes", "--mode", "merge"])

    assert _invoke(runner, ["host", "current"]).strip() == "hermes (merge)"
    assert _hook_command(marker, "hermes")
    assert "sz tick --reason cron" in cron_file.read_text()
