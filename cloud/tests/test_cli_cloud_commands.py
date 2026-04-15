from __future__ import annotations

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
