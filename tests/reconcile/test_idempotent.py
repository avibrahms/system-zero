from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from sz.commands.cli import cli


CAPABILITY = "feature.alpha"


def _init_repo(tmp_path: Path, monkeypatch, *, host: str = "generic", host_mode: str = "install") -> tuple[Path, CliRunner]:
    repo_root = tmp_path / f"{host}-{host_mode}-repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--host", host, "--host-mode", host_mode, "--yes"])
    assert result.exit_code == 0, result.output
    return repo_root, runner


def _write_module(
    root: Path,
    module_id: str,
    *,
    provides: list[dict[str, str]] | None = None,
    requires: list[dict[str, object]] | None = None,
    requires_host: list[str] | None = None,
) -> Path:
    source = root / module_id
    source.mkdir()
    (source / "entry.sh").write_text("#!/usr/bin/env bash\nset -euo pipefail\n", encoding="utf-8")
    (source / "reconcile.sh").write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "python3 - <<'PY'\n"
        "import json\n"
        "import os\n"
        "from pathlib import Path\n"
        "module_id = os.environ['SZ_MODULE_ID']\n"
        "registry = json.loads(Path(os.environ['SZ_REGISTRY_PATH']).read_text(encoding='utf-8'))\n"
        "lines = []\n"
        "for binding in registry['bindings']:\n"
        "    if binding['requirer'] == module_id:\n"
        "        lines.append(f\"{binding['capability']}={binding['provider']}:{binding['address']}\")\n"
        "for item in registry['unsatisfied']:\n"
        "    if item['requirer'] == module_id:\n"
        "        lines.append(f\"unsatisfied={item['capability']}\")\n"
        "Path(os.environ['SZ_MODULE_DIR'], 'state.log').write_text('\\n'.join(sorted(lines)) + ('\\n' if lines else ''), encoding='utf-8')\n"
        "PY\n",
        encoding="utf-8",
    )
    manifest = {
        "id": module_id,
        "version": "0.1.0",
        "category": "testing",
        "description": f"Synthetic {module_id} module",
        "entry": {"type": "bash", "command": "entry.sh"},
        "triggers": [{"on": "tick"}],
        "hooks": {"reconcile": "reconcile.sh"},
    }
    if provides is not None:
        manifest["provides"] = provides
    if requires is not None:
        manifest["requires"] = requires
    if requires_host is not None:
        manifest["requires_host"] = requires_host
    (source / "module.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return source


def _install(runner: CliRunner, module_id: str, source: Path) -> None:
    result = runner.invoke(cli, ["install", module_id, "--source", str(source)])
    assert result.exit_code == 0, result.output


def _registry(root: Path) -> dict[str, object]:
    return json.loads((root / ".sz" / "registry.json").read_text(encoding="utf-8"))


def _without_generated_at(root: Path) -> str:
    payload = _registry(root)
    payload["generated_at"] = "<ignored>"
    return json.dumps(payload, indent=2, sort_keys=False) + "\n"


def _assert_old_module_sees_new_module(repo_root: Path, runner: CliRunner) -> None:
    consumer = _write_module(
        repo_root,
        "consumer-mod",
        requires=[{"name": CAPABILITY, "optional": False, "on_missing": "warn"}],
    )
    provider = _write_module(
        repo_root,
        "provider-mod",
        provides=[{"name": CAPABILITY, "address": "events:feature.alpha", "description": "alpha events"}],
    )

    _install(runner, "consumer-mod", consumer)
    assert {"requirer": "consumer-mod", "capability": CAPABILITY, "severity": "warn"} in _registry(repo_root)["unsatisfied"]

    _install(runner, "provider-mod", provider)

    binding = {
        "requirer": "consumer-mod",
        "capability": CAPABILITY,
        "provider": "provider-mod",
        "address": "events:feature.alpha",
    }
    assert binding in _registry(repo_root)["bindings"]
    assert (repo_root / ".sz" / "consumer-mod" / "state.log").read_text(encoding="utf-8") == (
        "feature.alpha=provider-mod:events:feature.alpha\n"
    )


def test_old_module_sees_new_module(tmp_path, monkeypatch) -> None:
    repo_root, runner = _init_repo(tmp_path, monkeypatch)
    _assert_old_module_sees_new_module(repo_root, runner)


def test_reconcile_idempotent(tmp_path, monkeypatch) -> None:
    repo_root, runner = _init_repo(tmp_path, monkeypatch)
    consumer = _write_module(
        repo_root,
        "consumer-mod",
        requires=[{"name": CAPABILITY, "optional": False, "on_missing": "warn"}],
    )
    provider = _write_module(
        repo_root,
        "provider-mod",
        provides=[{"name": CAPABILITY, "address": "events:feature.alpha", "description": "alpha events"}],
    )
    _install(runner, "consumer-mod", consumer)
    _install(runner, "provider-mod", provider)

    result = runner.invoke(cli, ["reconcile", "--reason", "idempotent"])
    assert result.exit_code == 0, result.output
    first = _without_generated_at(repo_root)
    first_log = (repo_root / ".sz" / "consumer-mod" / "reconcile.log").read_text(encoding="utf-8")

    result = runner.invoke(cli, ["reconcile", "--reason", "idempotent"])
    assert result.exit_code == 0, result.output
    assert _without_generated_at(repo_root) == first
    assert (repo_root / ".sz" / "consumer-mod" / "reconcile.log").read_text(encoding="utf-8") == first_log


def test_uninstall_re_unsatisfies(tmp_path, monkeypatch) -> None:
    repo_root, runner = _init_repo(tmp_path, monkeypatch)
    consumer = _write_module(
        repo_root,
        "consumer-mod",
        requires=[{"name": CAPABILITY, "optional": False, "on_missing": "warn"}],
    )
    provider = _write_module(
        repo_root,
        "provider-mod",
        provides=[{"name": CAPABILITY, "address": "events:feature.alpha", "description": "alpha events"}],
    )
    _install(runner, "consumer-mod", consumer)
    _install(runner, "provider-mod", provider)

    result = runner.invoke(cli, ["uninstall", "provider-mod", "--confirm"])
    assert result.exit_code == 0, result.output

    assert {"requirer": "consumer-mod", "capability": CAPABILITY, "severity": "warn"} in _registry(repo_root)["unsatisfied"]
    assert (repo_root / ".sz" / "consumer-mod" / "state.log").read_text(encoding="utf-8") == "unsatisfied=feature.alpha\n"
    assert not (repo_root / ".sz" / "provider-mod").exists()


def test_pinned_binding_wins(tmp_path, monkeypatch) -> None:
    repo_root, runner = _init_repo(tmp_path, monkeypatch)
    consumer = _write_module(
        repo_root,
        "consumer-mod",
        requires=[{"name": CAPABILITY, "optional": False, "on_missing": "warn"}],
    )
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
    _install(runner, "consumer-mod", consumer)
    _install(runner, "provider-bbb", provider_b)
    _install(runner, "provider-ccc", provider_c)

    config_path = repo_root / ".sz.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["modules"]["consumer-mod"]["bindings"] = {CAPABILITY: "provider-ccc"}
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    result = runner.invoke(cli, ["reconcile", "--reason", "pin-test"])
    assert result.exit_code == 0, result.output

    assert {
        "requirer": "consumer-mod",
        "capability": CAPABILITY,
        "provider": "provider-ccc",
        "address": "events:provider-ccc",
    } in _registry(repo_root)["bindings"]


def test_versioned_capability_requires_compatible_provider(tmp_path, monkeypatch) -> None:
    repo_root, runner = _init_repo(tmp_path, monkeypatch)
    consumer = _write_module(
        repo_root,
        "consumer-mod",
        requires=[{"name": "feature.versioned@^1.0", "optional": False, "on_missing": "warn"}],
    )
    old_provider = _write_module(
        repo_root,
        "provider-aaa",
        provides=[{"name": "feature.versioned@^0.9", "address": "events:old", "description": "old provider"}],
    )
    new_provider = _write_module(
        repo_root,
        "provider-zzz",
        provides=[{"name": "feature.versioned@^1.2", "address": "events:new", "description": "new provider"}],
    )

    _install(runner, "consumer-mod", consumer)
    _install(runner, "provider-aaa", old_provider)
    assert {
        "requirer": "consumer-mod",
        "capability": "feature.versioned@^1.0",
        "severity": "warn",
    } in _registry(repo_root)["unsatisfied"]

    _install(runner, "provider-zzz", new_provider)

    assert {
        "requirer": "consumer-mod",
        "capability": "feature.versioned@^1.0",
        "provider": "provider-zzz",
        "address": "events:new",
    } in _registry(repo_root)["bindings"]
    assert not _registry(repo_root)["unsatisfied"]


def test_unversioned_requirement_accepts_versioned_provider(tmp_path, monkeypatch) -> None:
    repo_root, runner = _init_repo(tmp_path, monkeypatch)
    consumer = _write_module(
        repo_root,
        "consumer-mod",
        requires=[{"name": "feature.versioned", "optional": False, "on_missing": "warn"}],
    )
    provider = _write_module(
        repo_root,
        "provider-mod",
        provides=[{"name": "feature.versioned@^1.0", "address": "events:versioned", "description": "versioned provider"}],
    )

    _install(runner, "consumer-mod", consumer)
    _install(runner, "provider-mod", provider)

    assert {
        "requirer": "consumer-mod",
        "capability": "feature.versioned",
        "provider": "provider-mod",
        "address": "events:versioned",
    } in _registry(repo_root)["bindings"]
