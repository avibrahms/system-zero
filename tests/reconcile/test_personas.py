from __future__ import annotations

import json

import pytest
import yaml

from sz.commands.cli import cli
from tests.reconcile.test_idempotent import (
    CAPABILITY,
    _assert_old_module_sees_new_module,
    _init_repo,
    _install,
    _registry,
    _without_generated_at,
    _write_module,
)


@pytest.mark.parametrize(
    ("host", "host_mode"),
    [
        ("generic", "install"),
        ("hermes", "adopt"),
    ],
)
def test_reconcile_behaves_identically_for_static_and_dynamic_personas(tmp_path, monkeypatch, host: str, host_mode: str) -> None:
    repo_root, runner = _init_repo(tmp_path, monkeypatch, host=host, host_mode=host_mode)
    config = yaml.safe_load((repo_root / ".sz.yaml").read_text(encoding="utf-8"))
    assert config["host"] == host
    assert config["host_mode"] == host_mode

    _assert_old_module_sees_new_module(repo_root, runner)

    result = runner.invoke(cli, ["uninstall", "provider-mod", "--confirm"])
    assert result.exit_code == 0, result.output
    assert {"requirer": "consumer-mod", "capability": CAPABILITY, "severity": "warn"} in _registry(repo_root)["unsatisfied"]

    provider_b = _write_module(
        repo_root,
        "provider-bbb",
        provides=[{"name": CAPABILITY, "address": "events:provider-bbb", "description": "B provider"}],
    )
    provider_c = _write_module(
        repo_root,
        "provider-ccc",
        provides=[{"name": CAPABILITY, "address": "events:provider-ccc", "description": "C provider"}],
    )
    _install(runner, "provider-bbb", provider_b)
    _install(runner, "provider-ccc", provider_c)

    config_path = repo_root / ".sz.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["modules"]["consumer-mod"]["bindings"] = {CAPABILITY: "provider-ccc"}
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    result = runner.invoke(cli, ["reconcile", "--reason", f"{host}-persona"])
    assert result.exit_code == 0, result.output
    first = _without_generated_at(repo_root)
    result = runner.invoke(cli, ["reconcile", "--reason", f"{host}-persona"])
    assert result.exit_code == 0, result.output
    assert _without_generated_at(repo_root) == first

    registry = _registry(repo_root)
    assert registry["bindings"] == [
        {
            "requirer": "consumer-mod",
            "capability": CAPABILITY,
            "provider": "provider-ccc",
            "address": "events:provider-ccc",
        }
    ]
    assert not registry["unsatisfied"]

    event_types = [
        event["type"]
        for event in (
            json.loads(line)
            for line in (repo_root / ".sz" / "bus.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    ]
    assert "reconcile.started" in event_types
    assert "module.reconciled" in event_types
    assert "reconcile.finished" in event_types
