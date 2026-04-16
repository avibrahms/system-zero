"""Claude Code CLI provider using the user's Claude subscription login when available."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace


def _claude_bin() -> str | None:
    configured = os.environ.get("SZ_CLAUDE_BIN")
    if configured:
        return configured
    return shutil.which("claude")


def probe() -> dict[str, object]:
    binary = _claude_bin()
    if not binary:
        return {"available": False, "reason": "claude CLI not found on PATH", "source": "subscription_cli"}
    try:
        result = subprocess.run(
            [binary, "auth", "status"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except Exception as exc:
        return {"available": False, "reason": f"failed to probe claude auth status: {exc}", "source": "subscription_cli"}

    payload = None
    try:
        payload = json.loads(result.stdout.strip() or "{}")
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict) and payload.get("loggedIn"):
        return {"available": True, "reason": "Claude Code CLI is logged in", "source": "subscription_cli"}
    return {"available": False, "reason": "claude CLI is installed but not logged in", "source": "subscription_cli"}


def call(prompt: str, *, model: str | None = None, max_tokens: int = 1024):
    binary = _claude_bin()
    if not binary:
        raise RuntimeError("claude CLI not found")

    cmd = [
        binary,
        "-p",
        "--output-format",
        "text",
        "--permission-mode",
        "default",
        prompt,
    ]
    selected_model = model or os.environ.get("SZ_CLAUDE_MODEL")
    selected_effort = os.environ.get("SZ_CLAUDE_EFFORT")
    if selected_model:
        cmd.extend(["--model", selected_model])
    if selected_effort:
        cmd.extend(["--effort", selected_effort])

    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        timeout=int(os.environ.get("SZ_CLAUDE_TIMEOUT_SECONDS", "180")),
    )
    text = (completed.stdout or "").strip()
    if completed.returncode != 0:
        detail = text or completed.stderr.strip()
        raise RuntimeError(detail or f"claude -p failed with exit code {completed.returncode}")
    if not text:
        raise RuntimeError("claude -p returned no text")
    return SimpleNamespace(
        text=text,
        tokens_in=max(1, len(prompt.split())),
        tokens_out=max(1, min(max_tokens, len(text.split()))),
        model=selected_model or "claude-code-default",
    )
