"""Repo Genesis: the becomes-alive workflow."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml

from sz.commands import host as host_command
from sz.commands import start as start_command
from sz.commands import tick as tick_command
from sz.core import bus as bus_core
from sz.core import heartbeat_detect, inventory, module_install, paths, reconcile as reconcile_engine, repo_config
from sz.interfaces import llm

CATALOG_SUMMARY_FALLBACK = """\
heartbeat        - periodic pulse; required for any Static repo
immune           - passive anomaly detector
subconscious     - aggregates anomalies into a colored health snapshot
dreaming         - generates novel hypotheses during quiet periods
metabolism       - rotates the bus log
endocrine        - modulates module setpoints based on aggregate health
prediction       - predicts next likely event from history
"""

GENESIS_MODULES: dict[str, dict[str, str]] = {
    "heartbeat": {
        "description": "Genesis bootstrap pulse observer.",
        "event": "pulse.tick",
        "category": "physiology",
    },
    "immune": {
        "description": "Genesis bootstrap anomaly detector.",
        "event": "health.snapshot",
        "category": "physiology",
    },
    "subconscious": {
        "description": "Genesis bootstrap health aggregator.",
        "event": "health.snapshot",
        "category": "cognition",
    },
    "dreaming": {
        "description": "Genesis bootstrap hypothesis generator.",
        "event": "dream.generated",
        "category": "cognition",
    },
    "metabolism": {
        "description": "Genesis bootstrap bus maintenance checker.",
        "event": "metabolism.checked",
        "category": "physiology",
    },
    "endocrine": {
        "description": "Genesis bootstrap setpoint modulator.",
        "event": "setpoints.checked",
        "category": "physiology",
    },
    "prediction": {
        "description": "Genesis bootstrap event predictor.",
        "event": "prediction.updated",
        "category": "cognition",
    },
}


def _catalog_summary() -> str:
    """Read the local catalog index if available, otherwise fallback."""
    here = Path(__file__).resolve().parents[2] / "catalog" / "index.json"
    if not here.exists():
        return CATALOG_SUMMARY_FALLBACK
    idx = json.loads(here.read_text())
    lines = []
    for it in idx["items"]:
        lines.append(f"{it['id']:18s} - {it['description']}")
    return "\n".join(lines)


def render_prompt(inv: dict, hb: dict, hint: str) -> str:
    template = (Path(__file__).resolve().parent.parent / "templates" / "repo_genesis_prompt.md").read_text()
    meta = "\n".join(f"--- {k} ---\n{v}" for k, v in inv["meta_blobs"].items())
    return (template
            .replace("{{FILE_COUNT}}", str(inv["file_count"]))
            .replace("{{LANGUAGES}}", json.dumps(inv["detected_languages"]))
            .replace("{{TOP_DIRS}}", json.dumps(inv["top_dirs"]))
            .replace("{{EXISTING_HEARTBEAT}}", hb["existing_heartbeat"])
            .replace("{{README}}", inv["readme_text"][:5000])
            .replace("{{META}}", meta[:8000])
            .replace("{{HINT}}", hint or "")
            .replace("{{CATALOG_SUMMARY}}", _catalog_summary()))


def genesis(root: Path | None = None, *, hint: str = "", auto_yes: bool = False,
            host_mode_override: str | None = None) -> dict:
    """Run Repo Genesis.

    IMPORTANT: this function does NOT read `SZ_FORCE_GENESIS_PROFILE` or any other
    test-only environment variable. Tests must use pytest's `monkeypatch` to replace
    `sz.interfaces.llm.invoke` with a function that returns a canned profile. Keeping
    the test hook out of the shipped code preserves the single responsibility of
    this function (production) and avoids any accidental test-mode leak in releases.
    See `tests/genesis/conftest.py` for the canonical test fixture.
    """
    root = root or paths.repo_root()
    inv = inventory.inventory(root)
    hb = heartbeat_detect.detect(root)
    prompt = render_prompt(inv, hb, hint)
    schema_path = Path(__file__).resolve().parents[2] / "spec" / "v0.1.0" / "llm-responses" / "repo-genesis.schema.json"
    try:
        result = llm.invoke(prompt, schema_path=schema_path, template_id="repo-genesis", max_tokens=1500)
    except llm.CLCFailure as exc:
        _emit_llm_failure(root, exc.errors)
        _remove_pending_profile(root)
        raise
    profile = dict(result.parsed)

    # Force the algorithmic heartbeat decision unless the LLM has very strong signal.
    # Algorithm wins by default; the LLM may add nuance via risk_flags.
    profile["existing_heartbeat"] = hb["existing_heartbeat"]

    # Persist the profile.
    paths.profile_path(root).write_text(json.dumps(profile, indent=2, sort_keys=True))

    host, host_mode = _resolve_host(root, profile["existing_heartbeat"], host_mode_override)

    # Show recommendations and confirm.
    summary_lines = [
        f"Purpose: {profile['purpose']}",
        f"Language: {profile['language']}",
        f"Frameworks: {', '.join(profile.get('frameworks', []) or [])}",
        f"Heartbeat: {profile['existing_heartbeat']} ({host_mode} mode via host: {host})",
        "Recommended modules:",
    ]
    for m in profile["recommended_modules"]:
        summary_lines.append(f"  - {m['id']}: {m['reason']}")
    print("\n".join(summary_lines))

    if not auto_yes:
        ans = input("\nProceed to install? [Y/n] ").strip().lower()
        if ans not in ("", "y", "yes"):
            print("aborted; .sz/repo-profile.json saved for inspection.")
            return {"profile": profile, "installed": [], "host": None}

    configured_host, configured_mode = _install_host_adapter(root, host, host_mode)

    installed = []
    for m in profile["recommended_modules"]:
        module_id = m["id"]
        if _install_recommended_module(root, module_id):
            installed.append(module_id)

    reconcile_engine.reconcile(root, reason="genesis")
    _run_initial_tick(root)

    if configured_mode == "install":
        _start_owned_heartbeat(root)
    # Adopt mode: nothing to start; the host's daemon already pulses.

    bus_core.emit(paths.bus_path(root), "s0", "repo.genesis.completed",
                  {"profile": profile, "installed": installed, "host": configured_host, "host_mode": configured_mode})

    print(f"\nRepo is alive. Heartbeat: {configured_mode}. Modules installed: {', '.join(installed)}.")
    print("Try: sz list, sz doctor, sz bus tail.")
    return {"profile": profile, "installed": installed, "host": configured_host, "host_mode": configured_mode}


def _pick_install_host(root: Path) -> str:
    # If there's a Claude/Cursor/OpenCode/Aider marker, prefer that adapter.
    for name in ["claude_code", "cursor", "opencode", "aider"]:
        markers = {"claude_code": [".claude"], "cursor": [".cursorrules", ".cursor"],
                   "opencode": [".opencode"], "aider": [".aider.conf.yml"]}
        if any((root / m).exists() for m in markers[name]):
            return name
    return "generic"


def _resolve_host(root: Path, existing_heartbeat: str, host_mode_override: str | None) -> tuple[str, str]:
    requested_mode = host_mode_override if host_mode_override not in (None, "auto") else None
    if existing_heartbeat == "none":
        return _pick_install_host(root), "install"
    if existing_heartbeat in {"unknown", "custom"}:
        if requested_mode in {"adopt", "merge"}:
            return "unknown", requested_mode
        return "generic", "install"
    if requested_mode == "install":
        return "generic", "install"
    if requested_mode == "merge":
        return existing_heartbeat, "merge"
    return existing_heartbeat, "adopt"


def _install_host_adapter(root: Path, host: str, host_mode: str) -> tuple[str, str]:
    try:
        return host_command.install_adapter(root, host, host_mode)
    except Exception as exc:
        bus_core.emit(
            paths.bus_path(root),
            "s0",
            "module.errored",
            {"id": host, "phase": "genesis.host", "stderr": str(exc)[:500]},
        )
        cfg = repo_config.read(root)
        return str(cfg.get("host", host)), str(cfg.get("host_mode", host_mode))


def _install_recommended_module(root: Path, module_id: str) -> bool:
    try:
        source = _module_source(root, module_id)
        module_install.install_from_source(root, source, module_id)
        return True
    except Exception as exc:
        bus_core.emit(
            paths.bus_path(root),
            "s0",
            "module.errored",
            {"id": module_id, "phase": "genesis", "stderr": str(exc)[:500]},
        )
        return False


def _module_source(root: Path, module_id: str) -> Path:
    repo_catalog_source = Path(__file__).resolve().parents[2] / "catalog" / "modules" / module_id
    if (repo_catalog_source / "module.yaml").exists():
        return repo_catalog_source
    if module_id not in GENESIS_MODULES:
        raise module_install.ModuleInstallError(f"Module {module_id!r} is not available in the local catalog.")
    return _ensure_genesis_module_source(root, module_id)


def _ensure_genesis_module_source(root: Path, module_id: str) -> Path:
    meta = GENESIS_MODULES[module_id]
    source = paths.s0_dir(root) / "cache" / "genesis-modules" / module_id
    source.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": module_id,
        "version": "0.1.0",
        "category": meta["category"],
        "description": meta["description"],
        "entry": {"type": "python", "command": "entry.py"},
        "triggers": [{"on": "tick"}],
        "hooks": {"reconcile": "reconcile.sh", "doctor": "doctor.sh"},
    }
    (source / "module.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    (source / "entry.py").write_text(_entry_script(meta["event"]))
    (source / "reconcile.sh").write_text(_reconcile_script())
    (source / "doctor.sh").write_text(_doctor_script())
    for executable in ["entry.py", "reconcile.sh", "doctor.sh"]:
        (source / executable).chmod(0o755)
    return source


def _entry_script(event_type: str) -> str:
    return f"""#!/usr/bin/env python3
import json
import os
from datetime import datetime, timezone
from pathlib import Path

event = {{
    "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "module": os.environ.get("SZ_MODULE_ID", "unknown"),
    "type": "{event_type}",
    "payload": {{"source": "genesis-bootstrap"}},
}}
with Path(os.environ["SZ_BUS_PATH"]).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(event, separators=(",", ":")) + "\\n")
"""


def _reconcile_script() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import json
import os
from pathlib import Path

registry = Path(os.environ["SZ_REGISTRY_PATH"])
module_dir = Path(os.environ["SZ_MODULE_DIR"])
payload = json.loads(registry.read_text(encoding="utf-8")) if registry.exists() else {}
(module_dir / "runtime.json").write_text(json.dumps({"bindings": payload.get("bindings", [])}, sort_keys=True) + "\\n", encoding="utf-8")
PY
"""


def _doctor_script() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail
test -f "$SZ_MODULE_DIR/module.yaml"
"""


def _run_initial_tick(root: Path) -> None:
    old_cwd = Path.cwd()
    os.chdir(root)
    try:
        tick_command.cmd.main(args=["--reason", "genesis"], standalone_mode=False)
    finally:
        os.chdir(old_cwd)


def _start_owned_heartbeat(root: Path) -> None:
    old_cwd = Path.cwd()
    os.chdir(root)
    try:
        start_command.cmd.main(args=["--interval", "300"], standalone_mode=False)
    finally:
        os.chdir(old_cwd)


def _emit_llm_failure(root: Path, errors: list[str]) -> None:
    if not paths.bus_path(root).parent.exists():
        return
    bus_core.emit(
        paths.bus_path(root),
        "s0",
        "llm.call.failed",
        {"template_id": "repo-genesis", "errors": errors},
    )


def _remove_pending_profile(root: Path) -> None:
    profile_path = paths.profile_path(root)
    if not profile_path.exists():
        return
    try:
        profile: dict[str, Any] = json.loads(profile_path.read_text())
    except json.JSONDecodeError:
        return
    if "genesis_pending" in profile.get("risk_flags", []):
        profile_path.unlink()
