"""Pytest fixture: monkeypatch the mock LLM to return canned absorb drafts."""
import json
from pathlib import Path
import pytest

CANNED = Path(__file__).parent / "canned"


@pytest.fixture
def stub_absorb_llm(monkeypatch):
    from sz.interfaces.llm_providers import mock as mod
    from sz.interfaces.llm import LLMResult

    def fake_call(prompt, *, model=None, max_tokens=1024):
        if "p-limit" in prompt:
            data = (CANNED / "p-limit.json").read_text()
        elif "changed-files" in prompt:
            data = (CANNED / "changed-files.json").read_text()
        elif "simonw/llm" in prompt or "/llm/" in prompt:
            data = (CANNED / "llm.json").read_text()
        else:
            data = json.dumps({"error": "no_canned_match"})
        return LLMResult(text=data, parsed=None, tokens_in=10, tokens_out=300, model="mock:canned", provider="mock")

    monkeypatch.setattr(mod, "call", fake_call)
    yield
