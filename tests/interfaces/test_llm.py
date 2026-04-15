from __future__ import annotations

import json

from sz.interfaces import llm


def test_llm_invoke_uses_mock_provider(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SZ_LLM_PROVIDER", "mock")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    result = llm.invoke("hello world")

    assert result.provider == "mock"
    assert result.parsed is None
    payload = json.loads(result.text)
    assert payload["reply"] == "mock response"


def test_selected_provider_prefers_env_over_config(monkeypatch, tmp_path) -> None:
    home = tmp_path / "home"
    (home / ".sz").mkdir(parents=True)
    (home / ".sz" / "config.yaml").write_text("providers:\n  llm: groq\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SZ_LLM_PROVIDER", "mock")

    assert llm.selected_provider() == "mock"
