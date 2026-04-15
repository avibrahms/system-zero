"""Test-only: inject a canned LLM profile into Repo Genesis.

This file is under `tests/` and is never packaged or distributed. The shipping
code in `sz/core/genesis.py` has no awareness of this fixture. Any phase test
that needs a deterministic profile must import `force_profile` from here.
"""
import json
from dataclasses import dataclass

import pytest


@dataclass
class _Result:
    text: str
    parsed: dict
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = "mock:canned"


@pytest.fixture
def force_profile(monkeypatch):
    """Usage: force_profile({"purpose": "...", ...}) inside a test."""
    def _apply(profile: dict):
        from sz.interfaces import llm

        def fake_invoke(prompt, *, schema_path=None, template_id=None, model=None, max_tokens=1024):
            return _Result(text=json.dumps(profile), parsed=profile)

        monkeypatch.setattr(llm, "invoke", fake_invoke)
    return _apply
