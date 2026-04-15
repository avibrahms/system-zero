from __future__ import annotations

import json

from click.testing import CliRunner

from sz.cloud import client as cloud_client
from sz.cloud import telemetry as cloud_telemetry
from sz.commands.cli import cli
from sz.core import paths, repo_config
from sz.interfaces import bus
from tests.interfaces.helpers import make_runtime_root


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


def _write_telemetry_opt_in_config(root) -> None:
    repo_config.write(
        root,
        {
            "sz_version": "0.1.0",
            "host": "generic",
            "host_mode": "install",
            "modules": {},
            "providers": {},
            "cloud": {
                "tier": "pro",
                "endpoint": "https://cloud.test",
                "telemetry": True,
            },
        },
    )


def _write_saved_token(home) -> None:
    token_path = home / ".sz" / "token"
    token_path.parent.mkdir(parents=True)
    token_path.write_text("jwt-token\n")


def test_telemetry_flush_failure_does_not_advance_bus_cursor(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    _write_saved_token(home)
    root = make_runtime_root(tmp_path)
    _write_telemetry_opt_in_config(root)
    bus.emit(paths.bus_path(root), "heartbeat", "module.installed", {"module_id": "heartbeat"})

    def fail_telemetry(*args, **kwargs):
        raise RuntimeError("cloud unavailable")

    monkeypatch.setattr(cloud_telemetry.client, "telemetry", fail_telemetry)

    thread = cloud_telemetry.flush_after_tick(root)
    assert thread is not None
    thread.join(timeout=1)

    assert bus.read_cursor(root, "s0-cloud-telemetry") == 0


def test_telemetry_flush_rejection_does_not_advance_bus_cursor(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    _write_saved_token(home)
    root = make_runtime_root(tmp_path)
    _write_telemetry_opt_in_config(root)
    bus.emit(paths.bus_path(root), "heartbeat", "module.installed", {"module_id": "heartbeat"})

    monkeypatch.setattr(
        cloud_telemetry.client,
        "telemetry",
        lambda *args, **kwargs: {"accepted": False, "reason": "not eligible"},
    )

    thread = cloud_telemetry.flush_after_tick(root)
    assert thread is not None
    thread.join(timeout=1)

    assert bus.read_cursor(root, "s0-cloud-telemetry") == 0


def test_telemetry_flush_success_advances_bus_cursor_after_post(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    _write_saved_token(home)
    root = make_runtime_root(tmp_path)
    _write_telemetry_opt_in_config(root)
    bus.emit(paths.bus_path(root), "heartbeat", "module.installed", {"module_id": "heartbeat"})
    bus.emit(paths.bus_path(root), "immune", "module.errored", {"module_id": "immune"})
    sent_batches = []

    def accept_telemetry(install_id, events, **kwargs):
        sent_batches.append({"install_id": install_id, "events": events, **kwargs})
        return {"accepted": True, "count": len(events)}

    monkeypatch.setattr(cloud_telemetry.client, "telemetry", accept_telemetry)

    thread = cloud_telemetry.flush_after_tick(root)
    assert thread is not None
    thread.join(timeout=1)

    assert [event["type"] for event in sent_batches[0]["events"]] == [
        "module.installed",
        "module.errored",
    ]
    assert bus.read_cursor(root, "s0-cloud-telemetry") == 2
    assert cloud_telemetry.flush_after_tick(root) is None
