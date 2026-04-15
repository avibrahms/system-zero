"""Offline mock LLM provider for tests and local fallbacks."""
from __future__ import annotations

import json
from types import SimpleNamespace


def call(prompt: str, *, model: str | None = None, max_tokens: int = 1024):
    text = json.dumps(
        {
            "reply": "mock response",
            "prompt_excerpt": prompt[: min(len(prompt), 80)],
            "max_tokens": max_tokens,
        }
    )
    return SimpleNamespace(
        text=text,
        tokens_in=max(1, len(prompt.split())),
        tokens_out=max(1, len(text.split())),
        model=model or "mock-default",
    )
