from __future__ import annotations

import json

from click.testing import CliRunner

from sz.cloud import client as cloud_client
from sz.commands.cli import cli


def test_login_and_logout_manage_token(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()

    login = runner.invoke(cli, ["login", "jwt-token"])
    assert login.exit_code == 0, login.output
    assert (tmp_path / ".sz" / "token").read_text() == "jwt-token"

    logout = runner.invoke(cli, ["logout"])
    assert logout.exit_code == 0, logout.output
    assert not (tmp_path / ".sz" / "token").exists()


def test_upgrade_opens_checkout(monkeypatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr(
        cloud_client,
        "checkout",
        lambda tier, success_url, cancel_url: {"url": f"https://stripe.test/{tier}"},
    )
    monkeypatch.setattr("sz.commands.upgrade.webbrowser.open", lambda url: opened.append(url))

    runner = CliRunner()
    result = runner.invoke(cli, ["upgrade", "--tier", "pro"])

    assert result.exit_code == 0, result.output
    assert "https://stripe.test/pro" in result.output
    assert opened == ["https://stripe.test/pro"]


def test_insights_prints_public_json(monkeypatch) -> None:
    monkeypatch.setattr(
        cloud_client,
        "public_insights",
        lambda: {"trending_modules": [{"module_id": "heartbeat"}], "common_bindings": []},
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["insights", "--scope", "public"])

    assert result.exit_code == 0, result.output
    assert '"trending_modules"' in result.output
    assert '"heartbeat"' in result.output


def test_cloud_endpoint_uses_release_fly_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("SZ_CLOUD", raising=False)
    monkeypatch.setattr(cloud_client.util, "repo_base", lambda: tmp_path / "package")
    monkeypatch.setattr(cloud_client.paths, "repo_root", lambda: (_ for _ in ()).throw(FileNotFoundError()))
    (tmp_path / "package").mkdir()
    (tmp_path / ".s0-release.json").write_text(json.dumps({
        "endpoints": {"api": "https://sz-cloud.fly.dev"}
    }))

    assert cloud_client._endpoint() == "https://sz-cloud.fly.dev"


def test_cloud_endpoint_explicit_overrides_beat_release_fallback(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    user_config = home / ".sz" / "config.yaml"
    user_config.parent.mkdir(parents=True)
    user_config.write_text("cloud_endpoint: https://user-config.test/\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SZ_CLOUD", "https://env.test/")
    monkeypatch.setattr(cloud_client.util, "repo_base", lambda: tmp_path / "package")
    monkeypatch.setattr(cloud_client.paths, "repo_root", lambda: (_ for _ in ()).throw(FileNotFoundError()))
    (tmp_path / "package").mkdir()
    (tmp_path / ".s0-release.json").write_text(json.dumps({
        "endpoints": {"api": "https://sz-cloud.fly.dev"}
    }))

    assert cloud_client._endpoint() == "https://user-config.test"

    user_config.unlink()
    assert cloud_client._endpoint() == "https://env.test"


def test_cloud_endpoint_ignores_repo_default_when_dns_is_deferred(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("SZ_CLOUD", raising=False)
    monkeypatch.setattr(cloud_client.util, "repo_base", lambda: tmp_path / "package")
    monkeypatch.setattr(cloud_client.paths, "repo_root", lambda: tmp_path / "repo")
    (tmp_path / "package").mkdir()
    (tmp_path / "repo" / ".sz").mkdir(parents=True)
    (tmp_path / "repo" / ".sz.yaml").write_text(
        "sz_version: 0.1.0\n"
        "host: generic\n"
        "host_mode: install\n"
        "modules: {}\n"
        "providers: {}\n"
        "cloud:\n"
        "  tier: free\n"
        "  endpoint: https://api.systemzero.dev\n"
        "  telemetry: false\n"
    )
    (tmp_path / ".s0-release.json").write_text(json.dumps({
        "endpoints": {"api": "https://sz-cloud.fly.dev"}
    }))

    assert cloud_client._endpoint() == "https://sz-cloud.fly.dev"
