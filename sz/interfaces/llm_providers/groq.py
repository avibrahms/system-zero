"""Groq provider through the OpenAI-compatible API surface."""
from __future__ import annotations

import json
import os
from types import SimpleNamespace
import urllib.request


def call(prompt: str, *, model: str | None = None, max_tokens: int = 1024):
    body = {
        "model": model or os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1/chat/completions"),
        data=json.dumps(body).encode("utf-8"),
        headers={
            "authorization": f"Bearer {os.environ['GROQ_API_KEY']}",
            "content-type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
    choice = payload["choices"][0]["message"]["content"]
    usage = payload.get("usage", {})
    return SimpleNamespace(
        text=choice,
        tokens_in=usage.get("prompt_tokens", 0),
        tokens_out=usage.get("completion_tokens", 0),
        model=payload.get("model", body["model"]),
    )
