from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from sz.core import runtime
from sz.commands.cli import cli
from sz.interfaces import llm
from sz.interfaces import memory
from sz.interfaces.llm_providers import mock as mock_provider
from tests.interfaces.helpers import make_runtime_root
from tests.modules._helpers import events, init_repo, install_module


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = PROJECT_ROOT / "spec" / "v0.1.0" / "llm-responses" / "dreaming-hypothesis.schema.json"


def test_dreaming_clc_accepts_valid_response(monkeypatch, tmp_path) -> None:
    root = make_runtime_root(tmp_path)
    monkeypatch.chdir(root)
    monkeypatch.setenv("SZ_LLM_PROVIDER", "mock")
    monkeypatch.setattr(
        mock_provider,
        "call",
        lambda prompt, **kwargs: SimpleNamespace(
            text=json.dumps(
                {
                    "hypothesis": "Raise immune sensitivity after clustered amber snapshots.",
                    "novelty_score": 0.74,
                    "confidence": 0.62,
                    "rationale": "The recent bus history contains repeated amber health snapshots.",
                }
            ),
            tokens_in=1,
            tokens_out=1,
            model="mock",
        ),
    )

    result = llm.invoke(
        "dreaming prompt",
        schema_path=SCHEMA_PATH,
        template_id="dreaming-hypothesis",
        max_tokens=300,
    )

    assert result.parsed["hypothesis"].startswith("Raise immune sensitivity")
    items, _ = memory.tail(root, "llm.calls")
    assert items[-1]["template_id"] == "dreaming-hypothesis"
    assert items[-1]["validation_status"] == "ok"


def test_dreaming_clc_rejects_invalid_response(monkeypatch, tmp_path) -> None:
    root = make_runtime_root(tmp_path)
    monkeypatch.chdir(root)
    monkeypatch.setenv("SZ_LLM_PROVIDER", "mock")
    monkeypatch.setattr(
        mock_provider,
        "call",
        lambda prompt, **kwargs: SimpleNamespace(
            text=json.dumps({"hypothesis": "", "novelty_score": 1.5}),
            tokens_in=1,
            tokens_out=1,
            model="mock",
        ),
    )

    with pytest.raises(llm.CLCFailure):
        llm.invoke(
            "dreaming prompt",
            schema_path=SCHEMA_PATH,
            template_id="dreaming-hypothesis",
            max_tokens=300,
        )

    items, _ = memory.tail(root, "llm.calls")
    assert items[-1]["template_id"] == "dreaming-hypothesis"
    assert items[-1]["validation_status"] == "failed"


def test_dreaming_entry_emits_validated_hypothesis(monkeypatch, tmp_path) -> None:
    repo_root, runner = init_repo(tmp_path, monkeypatch)
    monkeypatch.setenv("SZ_LLM_PROVIDER", "mock")
    monkeypatch.setenv("PYTHONPATH", f"{PROJECT_ROOT}:{os.environ.get('PYTHONPATH', '')}")
    install_module(runner, "dreaming")

    emit_result = runner.invoke(cli, ["bus", "emit", "health.snapshot", '{"color":"GREEN","anomaly_count":0}'])
    assert emit_result.exit_code == 0, emit_result.output

    module_dir = repo_root / ".sz" / "dreaming"
    env = runtime.module_environment(repo_root, "dreaming", module_dir)
    result = subprocess.run(
        ["bash", str(module_dir / "dream.sh")],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    hypothesis_events = [event for event in events(repo_root) if event["type"] == "hypothesis.generated"]
    assert hypothesis_events
    payload = hypothesis_events[-1]["payload"]
    assert payload["hypothesis"] == payload["text"]
    assert 0.0 <= payload["novelty_score"] <= 1.0

    calls, _ = memory.tail(repo_root, "llm.calls")
    assert calls[-1]["template_id"] == "dreaming-hypothesis"
    assert calls[-1]["validation_status"] == "ok"
