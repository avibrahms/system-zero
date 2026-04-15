import json
from pathlib import Path

from click.testing import CliRunner

from sz.commands import catalog
from sz.commands.cli import cli
from tests.cli.test_smoke import _write_cli_shim

HERE = Path(__file__).resolve().parents[2]


def test_install_fetches_from_catalog_by_default(tmp_path, monkeypatch):
    repo_root = tmp_path / "catalog-install-repo"
    repo_root.mkdir()
    shim_dir = _write_cli_shim(repo_root)
    runner = CliRunner()

    monkeypatch.chdir(repo_root)
    monkeypatch.setenv("PATH", f"{shim_dir}:{__import__('os').environ.get('PATH', '')}")
    monkeypatch.setenv("SZ_CATALOG", (HERE / "catalog" / "index.json").as_uri())
    monkeypatch.setenv("SZ_CRONTAB_FILE", str(repo_root / "cron.txt"))

    result = runner.invoke(cli, ["init", "--host", "generic", "--host-mode", "install", "--no-genesis", "--yes"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli, ["install", "heartbeat"])
    assert result.exit_code == 0, result.output
    assert "Installed heartbeat" in result.output

    registry = json.loads((repo_root / ".sz" / "registry.json").read_text())
    assert "heartbeat" in registry["modules"]


def test_local_catalog_git_sources_resolve_without_network(tmp_path, monkeypatch):
    def fail_if_git_clone(*args, **kwargs):  # noqa: ANN001, ANN002
        raise AssertionError("local catalog fetch should not invoke git clone")

    monkeypatch.setattr(catalog.subprocess, "run", fail_if_git_clone)

    out = tmp_path / "heartbeat"
    catalog.fetch_module("heartbeat", out, (HERE / "catalog" / "index.json").as_uri())

    assert (out / "module.yaml").is_file()
