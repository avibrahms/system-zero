from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from sz.interfaces import llm
from sz.interfaces import memory
from sz.interfaces.llm_providers import mock as mock_provider

from tests.interfaces.helpers import make_runtime_root


def test_clc_succeeds_on_first(monkeypatch, tmp_path) -> None:
    root = make_runtime_root(tmp_path)
    monkeypatch.chdir(root)
    monkeypatch.setenv("SZ_LLM_PROVIDER", "mock")
    schema = {"type": "object", "required": ["x"], "properties": {"x": {"type": "integer"}}}
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")

    monkeypatch.setattr(
        mock_provider,
        "call",
        lambda prompt, **kwargs: SimpleNamespace(text='{"x":1}', tokens_in=1, tokens_out=1, model="mock"),
    )

    result = llm.invoke("hi", schema_path=schema_path, template_id="t")

    assert result.parsed == {"x": 1}
    items, _ = memory.tail(root, "llm.calls")
    assert items[-1]["attempts"] == 1
    assert items[-1]["validation_status"] == "ok"


def test_clc_retries_then_fails(monkeypatch, tmp_path) -> None:
    root = make_runtime_root(tmp_path)
    monkeypatch.chdir(root)
    monkeypatch.setenv("SZ_LLM_PROVIDER", "mock")
    schema = {"type": "object", "required": ["x"], "properties": {"x": {"type": "integer"}}}
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")

    monkeypatch.setattr(
        mock_provider,
        "call",
        lambda prompt, **kwargs: SimpleNamespace(text='{"x":"bad"}', tokens_in=1, tokens_out=1, model="mock"),
    )

    with pytest.raises(llm.CLCFailure):
        llm.invoke("hi", schema_path=schema_path, template_id="t")

    items, _ = memory.tail(root, "llm.calls")
    assert items[-1]["attempts"] == 3
    assert items[-1]["validation_status"] == "failed"


def test_clc_retries_then_succeeds(monkeypatch, tmp_path) -> None:
    root = make_runtime_root(tmp_path)
    monkeypatch.chdir(root)
    monkeypatch.setenv("SZ_LLM_PROVIDER", "mock")
    schema = {"type": "object", "required": ["x"], "properties": {"x": {"type": "integer"}}}
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")

    responses = iter(
        [
            SimpleNamespace(text="not json", tokens_in=1, tokens_out=1, model="mock"),
            SimpleNamespace(text='{"x":2}', tokens_in=1, tokens_out=1, model="mock"),
        ]
    )
    monkeypatch.setattr(mock_provider, "call", lambda prompt, **kwargs: next(responses))

    result = llm.invoke("hi", schema_path=schema_path, template_id="t")

    assert result.parsed == {"x": 2}
    items, _ = memory.tail(root, "llm.calls")
    assert items[-1]["attempts"] == 2
    assert items[-1]["validation_status"] == "ok"
