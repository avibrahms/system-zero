"""OpenAI chat-completions provider using urllib only."""
from __future__ import annotations

import json
import os
from types import SimpleNamespace
import urllib.request


def call(prompt: str, *, model: str | None = None, max_tokens: int = 1024):
    body = {
        "model": model or os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions"),
        data=json.dumps(body).encode("utf-8"),
        headers={
            "authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
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
