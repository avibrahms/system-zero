from __future__ import annotations

import json
import subprocess as subprocess_module
from pathlib import Path

from click.testing import CliRunner

from sz.commands import init as init_command
from sz.commands import install as install_command
from sz.commands.cli import cli
from sz.core import absorb as absorb_engine
from sz.core import manifest, paths, registry
from sz.interfaces.llm import LLMResult


def _write_source(root: Path) -> Path:
    source = root / "source"
    (source / "src").mkdir(parents=True)
    (source / "README.md").write_text("# Tiny limiter\n\nA small rate limiter.\n")
    (source / "src" / "rate_limiter.py").write_text(
        "class RateLimiter:\n"
        "    def allow(self) -> bool:\n"
        "        return True\n"
    )
    return source


def _draft(module_id: str = "rate-limiter") -> dict:
    return {
        "module_id": module_id,
        "description": "Absorbed rate limiting module.",
        "category": "control",
        "entry": {"type": "python", "command": "entry.py", "args": []},
        "triggers": [{"on": "tick"}],
        "provides": [
            {
                "name": "control.rate-limiter",
                "address": "events:rate.limit.checked",
                "description": "Reports rate-limit decisions.",
            }
        ],
        "requires": [],
        "setpoints": {
            "limit": {
                "default": 10,
                "range": [1, 100],
                "description": "Maximum allowed operations per window.",
            }
        },
        "files_to_copy": [{"from": "src/rate_limiter.py", "to": "lib/rate_limiter.py"}],
        "entry_script": "#!/usr/bin/env python3\nfrom lib.rate_limiter import RateLimiter\nprint(RateLimiter().allow())\n",
        "reconcile_script": (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "python3 - <<'PY'\n"
            "import json, os\n"
            "from pathlib import Path\n"
            "registry = Path(os.environ['SZ_REGISTRY_PATH'])\n"
            "module = Path(os.environ['SZ_MODULE_DIR'])\n"
            "payload = json.loads(registry.read_text()) if registry.exists() else {}\n"
            "runtime = {'bindings': payload.get('bindings', [])}\n"
            "(module / 'runtime.json').write_text(json.dumps(runtime, sort_keys=True) + '\\n')\n"
            "PY\n"
        ),
        "notes": "Copied the source implementation and wrapped it with a thin entrypoint.",
    }


def _patch_absorb(monkeypatch, tmp_path: Path, draft: dict) -> None:
    monkeypatch.setattr(absorb_engine, "CACHE", tmp_path / ".home" / ".sz" / "cache" / "absorb")

    def fake_invoke(prompt: str, **kwargs) -> LLMResult:
        return LLMResult(
            text=json.dumps(draft),
            parsed=json.loads(json.dumps(draft)),
            tokens_in=1,
            tokens_out=1,
            model="mock",
            provider="mock",
        )

    monkeypatch.setattr(absorb_engine.llm, "invoke", fake_invoke)


def test_absorb_dry_run_materializes_valid_staging(tmp_path: Path, monkeypatch) -> None:
    source = _write_source(tmp_path)
    draft = _draft()
    _patch_absorb(monkeypatch, tmp_path, draft)

    result = absorb_engine.absorb(str(source), "rate limiter", dry_run=True)

    staging = Path(result["staging"])
    assert staging.is_dir()
    assert result["draft"]["module_id"] == "rate-limiter"
    assert (staging / "module.yaml").exists()
    assert (staging / "lib" / "rate_limiter.py").read_text().startswith("class RateLimiter")
    assert (staging / "entry.py").read_text().startswith("#!/usr/bin/env python3")
    assert (staging / "reconcile.sh").read_text().startswith("#!/usr/bin/env bash")
    assert manifest.load(staging / "module.yaml")["id"] == "rate-limiter"


def test_absorb_dry_run_works_with_default_mock_provider(tmp_path: Path, monkeypatch) -> None:
    source = _write_source(tmp_path)
    monkeypatch.setenv("SZ_LLM_PROVIDER", "mock")
    monkeypatch.setattr(absorb_engine, "CACHE", tmp_path / ".home" / ".sz" / "cache" / "absorb")

    result = absorb_engine.absorb(str(source), "rate limiter", dry_run=True)

    staging = Path(result["staging"])
    assert result["draft"]["module_id"] == "rate-limiter"
    assert manifest.load(staging / "module.yaml")["id"] == "rate-limiter"
    assert (staging / "source" / "rate_limiter.py").exists()

    second = absorb_engine.absorb(str(source), "rate limiter", dry_run=True)
    second_staging = Path(second["staging"])
    assert manifest.load(second_staging / "module.yaml")["id"] == "rate-limiter"
    assert (second_staging / "source" / "rate_limiter.py").exists()


def test_absorb_non_dry_installs_and_reconciles(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    source = _write_source(tmp_path)
    draft = _draft()
    _patch_absorb(monkeypatch, tmp_path, draft)
    monkeypatch.chdir(repo)
    init_command.cmd.main(args=["--host", "generic", "--yes"], standalone_mode=False)
    original_run = subprocess_module.run

    def fake_run(args, check=False, **kwargs):
        if args[:3] == ["sz", "install", "rate-limiter"]:
            install_command.cmd.main(args=args[2:], standalone_mode=False)
            return subprocess_module.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        return original_run(args, check=check, **kwargs)

    monkeypatch.setattr(absorb_engine.subprocess, "run", fake_run)

    result = absorb_engine.absorb(str(source), "rate limiter")

    assert result["installed"] == "rate-limiter"
    installed_dir = paths.module_dir(repo, "rate-limiter")
    assert (installed_dir / "module.yaml").exists()
    assert (installed_dir / "runtime.json").exists()

    runner = CliRunner()
    reconciled = runner.invoke(cli, ["reconcile", "--reason", "absorb-idempotent"])
    assert reconciled.exit_code == 0, reconciled.output
    first_runtime = (installed_dir / "runtime.json").read_text()

    reconciled = runner.invoke(cli, ["reconcile", "--reason", "absorb-idempotent"])
    assert reconciled.exit_code == 0, reconciled.output
    second_runtime = (installed_dir / "runtime.json").read_text()
    assert first_runtime == second_runtime
    current = registry.read(repo)
    assert "rate-limiter" in current["modules"]

    listed = runner.invoke(cli, ["list"])
    assert listed.exit_code == 0
    assert "rate-limiter" in listed.output
