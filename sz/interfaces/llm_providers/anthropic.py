"""Anthropic messages provider using urllib only."""
from __future__ import annotations

import json
import os
from types import SimpleNamespace
import urllib.request


def call(prompt: str, *, model: str | None = None, max_tokens: int = 1024):
    body = {
        "model": model or os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-latest"),
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    request = urllib.request.Request(
        os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1/messages"),
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": os.environ.get("ANTHROPIC_VERSION", "2023-06-01"),
            "content-type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
    text = "".join(
        item.get("text", "")
        for item in payload.get("content", [])
        if item.get("type") == "text"
    )
    usage = payload.get("usage", {})
    return SimpleNamespace(
        text=text,
        tokens_in=usage.get("input_tokens", 0),
        tokens_out=usage.get("output_tokens", 0),
        model=payload.get("model", body["model"]),
    )
