from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from sz.commands import init as init_command
from sz.core import absorb as absorb_engine
from sz.interfaces import llm


def _write_source(root: Path) -> Path:
    source = root / "source"
    (source / "src").mkdir(parents=True)
    (source / "src" / "rate_limiter.py").write_text("def allow():\n    return True\n")
    return source


def _valid_response() -> str:
    return json.dumps(
        {
            "module_id": "retry-limiter",
            "description": "Absorbed retry limiter.",
            "category": "control",
            "entry": {"type": "python", "command": "entry.py", "args": []},
            "triggers": [{"on": "tick"}],
            "provides": [],
            "requires": [],
            "setpoints": {},
            "files_to_copy": [{"from": "src/rate_limiter.py", "to": "lib/rate_limiter.py"}],
            "entry_script": "#!/usr/bin/env python3\nfrom lib.rate_limiter import allow\nprint(allow())\n",
            "reconcile_script": "#!/usr/bin/env bash\nset -euo pipefail\ncat \"$SZ_REGISTRY_PATH\" >/dev/null\nprintf '{}\\n' > \"$SZ_MODULE_DIR/runtime.json\"\n",
            "notes": "Valid on third attempt.",
        }
    )


def test_absorb_clc_retries_until_valid_response(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    source = _write_source(tmp_path)
    monkeypatch.chdir(repo)
    init_command.cmd.main(args=["--host", "generic", "--no-genesis", "--yes"], standalone_mode=False)
    monkeypatch.setattr(absorb_engine, "CACHE", tmp_path / ".home" / ".sz" / "cache" / "absorb")

    responses = iter(
        [
            '{"bad": true}',
            "not json",
            _valid_response(),
        ]
    )

    def fake_provider(prompt: str, *, model: str | None, max_tokens: int):
        text = next(responses)
        return SimpleNamespace(
            text=text,
            tokens_in=1,
            tokens_out=1,
            model=model or "mock",
            provider="mock",
        )

    monkeypatch.setattr(llm, "_call_provider", fake_provider)

    result = absorb_engine.absorb(str(source), "rate limiter", dry_run=True)

    assert result["draft"]["module_id"] == "retry-limiter"
    calls_path = repo / ".sz" / "memory" / "streams" / "llm.calls.jsonl"
    records = [json.loads(line) for line in calls_path.read_text().splitlines()]
    assert records[-1]["template_id"] == "absorb-draft"
    assert records[-1]["attempts"] == 3
    assert records[-1]["validation_status"] == "ok"
