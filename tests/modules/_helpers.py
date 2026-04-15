from __future__ import annotations

import json
import os
from pathlib import Path

import yaml
from click.testing import CliRunner

from sz.commands.cli import cli
from tests.cli.test_smoke import _write_cli_shim


MODULE_IDS = ["heartbeat", "immune", "subconscious", "dreaming", "metabolism", "endocrine", "prediction"]
MODULES_ROOT = Path(__file__).resolve().parents[2] / "modules"


def init_repo(tmp_path: Path, monkeypatch, *, host: str = "generic", host_mode: str = "install") -> tuple[Path, CliRunner]:
    repo_root = tmp_path / f"{host}-{host_mode}-repo"
    repo_root.mkdir()
    if host == "hermes":
        (repo_root / ".hermes").mkdir()
        (repo_root / ".hermes/config.yaml").write_text("hooks:\n  on_tick: []\n", encoding="utf-8")
    shim_dir = _write_cli_shim(repo_root)
    monkeypatch.chdir(repo_root)
    monkeypatch.setenv("PATH", f"{shim_dir}:{os.environ.get('PATH', '')}")
    monkeypatch.setenv("SZ_CRONTAB_FILE", str(repo_root / "cron.txt"))
    monkeypatch.setenv("SZ_DEDUP_WINDOW_SECONDS", "0")
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--host", host, "--host-mode", host_mode, "--no-genesis", "--yes"])
    assert result.exit_code == 0, result.output
    return repo_root, runner


def install_module(runner: CliRunner, module_id: str) -> None:
    result = runner.invoke(cli, ["install", module_id, "--source", str(MODULES_ROOT / module_id)])
    assert result.exit_code == 0, result.output


def install_many(runner: CliRunner, module_ids: list[str]) -> None:
    for module_id in module_ids:
        install_module(runner, module_id)


def registry(repo_root: Path) -> dict[str, object]:
    return json.loads((repo_root / ".sz" / "registry.json").read_text(encoding="utf-8"))


def events(repo_root: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (repo_root / ".sz" / "bus.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def config(repo_root: Path) -> dict[str, object]:
    return yaml.safe_load((repo_root / ".sz.yaml").read_text(encoding="utf-8"))
