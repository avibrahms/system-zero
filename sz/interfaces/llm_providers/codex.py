"""Codex CLI provider using the user's ChatGPT/Codex login when available."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace


def _default_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))


def _codex_bin() -> str | None:
    configured = os.environ.get("SZ_CODEX_BIN")
    if configured:
        return configured
    found = shutil.which("codex")
    if found:
        return found
    if os.name == "posix":
        candidate = Path("/Applications/Codex.app/Contents/Resources/codex")
        if candidate.exists():
            return str(candidate)
    return None


def _auth_mode() -> str | None:
    auth_path = _default_home() / "auth.json"
    if not auth_path.exists():
        return None
    try:
        payload = json.loads(auth_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    mode = payload.get("auth_mode")
    return str(mode).strip().lower() if mode else None


def probe() -> dict[str, object]:
    binary = _codex_bin()
    if not binary:
        return {"available": False, "reason": "codex CLI not found on PATH", "source": "subscription_cli"}
    try:
        result = subprocess.run(
            [binary, "login", "status"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except Exception as exc:
        mode = _auth_mode()
        if mode == "chatgpt":
            return {"available": True, "reason": "Codex auth file indicates ChatGPT subscription login", "source": "subscription_cli"}
        if mode:
            return {"available": True, "reason": f"Codex auth file indicates login mode `{mode}`", "source": "subscription_cli"}
        return {"available": False, "reason": f"failed to probe codex login status: {exc}", "source": "subscription_cli"}

    output = f"{result.stdout}\n{result.stderr}".strip().lower()
    if result.returncode == 0 and "logged in" in output:
        if "chatgpt" in output:
            return {"available": True, "reason": "Codex CLI is logged in using ChatGPT", "source": "subscription_cli"}
        return {"available": True, "reason": "Codex CLI is authenticated", "source": "subscription_cli"}
    mode = _auth_mode()
    if mode == "chatgpt":
        return {"available": True, "reason": "Codex auth file indicates ChatGPT subscription login", "source": "subscription_cli"}
    return {"available": False, "reason": "codex CLI is installed but not logged in", "source": "subscription_cli"}


def _source_config_model() -> tuple[str | None, str | None]:
    config_path = _default_home() / "config.toml"
    if not config_path.exists():
        return None, None
    try:
        import tomllib
        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return None, None
    model = payload.get("model")
    effort = payload.get("model_reasoning_effort")
    return (
        str(model).strip() if model else None,
        str(effort).strip() if effort else None,
    )


def call(prompt: str, *, model: str | None = None, max_tokens: int = 1024):
    binary = _codex_bin()
    if not binary:
        raise RuntimeError("codex CLI not found")

    source_auth = _default_home() / "auth.json"
    if not source_auth.exists():
        raise RuntimeError("codex auth.json not found; run `codex login` first")

    default_model, default_effort = _source_config_model()
    selected_model = model or os.environ.get("SZ_CODEX_MODEL") or default_model
    selected_effort = os.environ.get("SZ_CODEX_REASONING_EFFORT") or default_effort

    with tempfile.TemporaryDirectory(prefix="s0-codex-home-") as temp_home, tempfile.NamedTemporaryFile(
        prefix="s0-codex-last-", delete=False
    ) as last_message:
        temp_home_path = Path(temp_home)
        shutil.copy2(source_auth, temp_home_path / "auth.json")

        config_lines = []
        if selected_model:
            config_lines.append(f'model = "{selected_model}"')
        if selected_effort:
            config_lines.append(f'model_reasoning_effort = "{selected_effort}"')
        config_lines.extend(
            [
                "[features]",
                "codex_hooks = false",
                "multi_agent = false",
            ]
        )
        (temp_home_path / "config.toml").write_text("\n".join(config_lines) + "\n", encoding="utf-8")

        env = dict(os.environ)
        env["CODEX_HOME"] = temp_home
        env.pop("SZ_LLM_PROVIDER", None)

        cmd = [
            binary,
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--cd",
            str(Path(tempfile.gettempdir()).resolve()),
            "--ephemeral",
            "--output-last-message",
            last_message.name,
            prompt,
        ]
        completed = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=int(os.environ.get("SZ_CODEX_TIMEOUT_SECONDS", "300")),
        )
        text = Path(last_message.name).read_text(encoding="utf-8", errors="replace").strip()
        Path(last_message.name).unlink(missing_ok=True)
    if completed.returncode != 0:
        detail = text or completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(detail or f"codex exec failed with exit code {completed.returncode}")
    if not text:
        raise RuntimeError("codex exec returned no final message")
    return SimpleNamespace(
        text=text,
        tokens_in=max(1, len(prompt.split())),
        tokens_out=max(1, min(max_tokens, len(text.split()))),
        model=selected_model or default_model or "codex-default",
    )
