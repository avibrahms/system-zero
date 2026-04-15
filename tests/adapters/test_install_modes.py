from __future__ import annotations

import json
import os
from pathlib import Path

import yaml
from click.testing import CliRunner

from sz.commands.cli import cli


INSTALL_EXPECTATIONS = {
    "generic": [".git/hooks/post-commit"],
    "claude_code": [".claude/hooks/sz-on-prompt.sh", ".claude/hooks/sz-on-stop.sh", ".claude/settings.json", ".git/hooks/post-commit"],
    "cursor": [".cursorrules", ".git/hooks/post-commit"],
    "opencode": [".opencode/hooks/sz-session-end.sh", ".git/hooks/post-commit"],
    "aider": [".aider.sz.sh", ".git/hooks/post-commit"],
}


def _init_git(repo: Path) -> None:
    (repo / ".git" / "hooks").mkdir(parents=True)


def _invoke(runner: CliRunner, args: list[str]) -> str:
    result = runner.invoke(cli, args)
    assert result.exit_code == 0, result.output
    return result.output


def test_install_mode_adapters_install_uninstall_idempotently(tmp_path: Path, monkeypatch) -> None:
    for adapter, expected_paths in INSTALL_EXPECTATIONS.items():
        repo = tmp_path / adapter
        repo.mkdir()
        _init_git(repo)
        cron_file = repo / "cron.txt"
        monkeypatch.chdir(repo)
        monkeypatch.setenv("SZ_CRONTAB_FILE", str(cron_file))
        runner = CliRunner()

        _invoke(runner, ["init", "--host", adapter, "--no-genesis", "--yes"])
        _invoke(runner, ["host", "install", adapter])

        for rel in expected_paths:
            assert (repo / rel).exists(), rel
        assert "sz tick --reason cron" in cron_file.read_text()
        assert _invoke(runner, ["host", "current"]).strip() == f"{adapter} (install)"

        if adapter == "claude_code":
            settings = json.loads((repo / ".claude/settings.json").read_text())
            assert "UserPromptSubmit" in settings["hooks"]
            assert "Stop" in settings["hooks"]
        if adapter == "cursor":
            assert "sz tick --reason cursor" in (repo / ".cursorrules").read_text()

        _invoke(runner, ["host", "uninstall"])
        assert "sz tick --reason cron" not in cron_file.read_text()
        assert "# >>> sz-generic >>>" not in (repo / ".git/hooks/post-commit").read_text()
        assert yaml.safe_load((repo / ".sz.yaml").read_text())["host"] == "generic"


def test_host_list_includes_phase_05_adapters(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "list"
    repo.mkdir()
    _init_git(repo)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SZ_CRONTAB_FILE", str(repo / "cron.txt"))
    runner = CliRunner()

    _invoke(runner, ["init", "--host", "generic", "--no-genesis", "--yes"])
    output = _invoke(runner, ["host", "list"])

    for adapter in [
        "generic",
        "claude_code",
        "cursor",
        "opencode",
        "aider",
        "hermes",
        "openclaw",
        "metaclaw",
        "connection_engine",
        "unknown",
    ]:
        assert adapter in output
    assert "mode=install" in output
    assert "mode=adopt" in output
