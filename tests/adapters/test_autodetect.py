from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from sz.commands.cli import cli


def _invoke(runner: CliRunner, args: list[str]) -> str:
    result = runner.invoke(cli, args)
    assert result.exit_code == 0, result.output
    return result.output


def test_autodetect_prefers_adopt_mode_markers(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git/hooks").mkdir(parents=True)
    (repo / ".claude").mkdir()
    (repo / ".hermes").mkdir()
    (repo / ".hermes/config.yaml").write_text("hooks:\n  on_tick: []\n")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SZ_CRONTAB_FILE", str(repo / "cron.txt"))
    runner = CliRunner()

    _invoke(runner, ["init", "--host", "generic", "--no-genesis", "--yes"])

    assert _invoke(runner, ["host", "detect"]).strip() == "hermes"


def test_autodetect_reports_unknown_before_generic(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "unknown"
    repo.mkdir()
    (repo / ".git/hooks").mkdir(parents=True)
    (repo / "custom").mkdir()
    (repo / "custom/config.yaml").write_text("on_tick:\n  - custom tick\n")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SZ_CRONTAB_FILE", str(repo / "cron.txt"))
    runner = CliRunner()

    _invoke(runner, ["init", "--host", "generic", "--no-genesis", "--yes"])

    assert _invoke(runner, ["host", "detect"]).strip() == "unknown"


def test_init_auto_adopts_detected_heartbeat_with_yes(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "auto-adopt"
    repo.mkdir()
    (repo / ".git/hooks").mkdir(parents=True)
    (repo / ".hermes").mkdir()
    (repo / ".hermes/config.yaml").write_text("hooks:\n  on_tick: []\n")
    cron_file = repo / "cron.txt"
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SZ_CRONTAB_FILE", str(cron_file))
    runner = CliRunner()

    _invoke(runner, ["init", "--no-genesis", "--yes"])

    assert _invoke(runner, ["host", "current"]).strip() == "hermes (adopt)"
    assert "sz tick --reason hermes" in (repo / ".hermes/config.yaml").read_text()
    assert not cron_file.exists() or "sz tick --reason cron" not in cron_file.read_text()


def test_init_auto_installs_for_unknown_heartbeat_with_yes(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "auto-unknown-install"
    repo.mkdir()
    (repo / ".git/hooks").mkdir(parents=True)
    (repo / "custom").mkdir()
    (repo / "custom/config.yaml").write_text("on_tick:\n  - custom tick\n")
    cron_file = repo / "cron.txt"
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SZ_CRONTAB_FILE", str(cron_file))
    runner = CliRunner()

    _invoke(runner, ["init", "--no-genesis", "--yes"])

    assert _invoke(runner, ["host", "current"]).strip() == "generic (install)"
    assert "sz tick --reason cron" in cron_file.read_text()
    assert "sz tick --reason unknown" not in (repo / "custom/config.yaml").read_text()
