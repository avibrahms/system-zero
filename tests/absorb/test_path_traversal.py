from __future__ import annotations

import json
from pathlib import Path

import pytest

from sz.core import absorb as absorb_engine
from sz.interfaces.llm import LLMResult


def test_absorb_rejects_source_path_traversal(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("# source\n")
    monkeypatch.setattr(absorb_engine, "CACHE", tmp_path / ".home" / ".sz" / "cache" / "absorb")

    draft = {
        "module_id": "bad-module",
        "description": "Invalid module.",
        "category": "control",
        "entry": {"type": "python", "command": "entry.py", "args": []},
        "triggers": [{"on": "tick"}],
        "provides": [],
        "requires": [],
        "setpoints": {},
        "files_to_copy": [{"from": "../../etc/passwd", "to": "passwd"}],
        "entry_script": "#!/usr/bin/env python3\nprint('bad')\n",
        "reconcile_script": "#!/usr/bin/env bash\ncat \"$SZ_REGISTRY_PATH\" >/dev/null\n",
        "notes": "This should be rejected.",
    }

    def fake_invoke(prompt: str, **kwargs) -> LLMResult:
        return LLMResult(
            text=json.dumps(draft),
            parsed=draft,
            tokens_in=1,
            tokens_out=1,
            model="mock",
            provider="mock",
        )

    monkeypatch.setattr(absorb_engine.llm, "invoke", fake_invoke)

    with pytest.raises(ValueError, match="outside source"):
        absorb_engine.absorb(str(source), "bad", dry_run=True)


def test_absorb_rejects_destination_path_traversal(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("# source\n")
    monkeypatch.setattr(absorb_engine, "CACHE", tmp_path / ".home" / ".sz" / "cache" / "absorb")

    draft = {
        "module_id": "bad-module",
        "description": "Invalid module.",
        "category": "control",
        "entry": {"type": "python", "command": "entry.py", "args": []},
        "triggers": [{"on": "tick"}],
        "provides": [],
        "requires": [],
        "setpoints": {},
        "files_to_copy": [{"from": "README.md", "to": "../escaped"}],
        "entry_script": "#!/usr/bin/env python3\nprint('bad')\n",
        "reconcile_script": "#!/usr/bin/env bash\ncat \"$SZ_REGISTRY_PATH\" >/dev/null\n",
        "notes": "This should be rejected.",
    }

    def fake_invoke(prompt: str, **kwargs) -> LLMResult:
        return LLMResult(
            text=json.dumps(draft),
            parsed=draft,
            tokens_in=1,
            tokens_out=1,
            model="mock",
            provider="mock",
        )

    monkeypatch.setattr(absorb_engine.llm, "invoke", fake_invoke)

    with pytest.raises(ValueError, match="outside module"):
        absorb_engine.absorb(str(source), "bad", dry_run=True)


def test_absorb_rejects_entry_path_traversal(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("# source\n")
    monkeypatch.setattr(absorb_engine, "CACHE", tmp_path / ".home" / ".sz" / "cache" / "absorb")

    draft = {
        "module_id": "bad-module",
        "description": "Invalid module.",
        "category": "control",
        "entry": {"type": "python", "command": "../escaped.py", "args": []},
        "triggers": [{"on": "tick"}],
        "provides": [],
        "requires": [],
        "setpoints": {},
        "files_to_copy": [{"from": "README.md", "to": "README.md"}],
        "entry_script": "#!/usr/bin/env python3\nprint('bad')\n",
        "reconcile_script": "#!/usr/bin/env bash\ncat \"$SZ_REGISTRY_PATH\" >/dev/null\n",
        "notes": "This should be rejected.",
    }

    def fake_invoke(prompt: str, **kwargs) -> LLMResult:
        return LLMResult(
            text=json.dumps(draft),
            parsed=draft,
            tokens_in=1,
            tokens_out=1,
            model="mock",
            provider="mock",
        )

    monkeypatch.setattr(absorb_engine.llm, "invoke", fake_invoke)

    with pytest.raises(ValueError, match="entry outside module"):
        absorb_engine.absorb(str(source), "bad", dry_run=True)


def test_absorb_rejects_absolute_entry_path(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("# source\n")
    monkeypatch.setattr(absorb_engine, "CACHE", tmp_path / ".home" / ".sz" / "cache" / "absorb")

    draft = {
        "module_id": "bad-module",
        "description": "Invalid module.",
        "category": "control",
        "entry": {"type": "python", "command": str(tmp_path / "escaped.py"), "args": []},
        "triggers": [{"on": "tick"}],
        "provides": [],
        "requires": [],
        "setpoints": {},
        "files_to_copy": [{"from": "README.md", "to": "README.md"}],
        "entry_script": "#!/usr/bin/env python3\nprint('bad')\n",
        "reconcile_script": "#!/usr/bin/env bash\ncat \"$SZ_REGISTRY_PATH\" >/dev/null\n",
        "notes": "This should be rejected.",
    }

    def fake_invoke(prompt: str, **kwargs) -> LLMResult:
        return LLMResult(
            text=json.dumps(draft),
            parsed=draft,
            tokens_in=1,
            tokens_out=1,
            model="mock",
            provider="mock",
        )

    monkeypatch.setattr(absorb_engine.llm, "invoke", fake_invoke)

    with pytest.raises(ValueError, match="entry outside module"):
        absorb_engine.absorb(str(source), "bad", dry_run=True)


def test_absorb_rejects_source_path_missing_from_inventory(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("# source\n")
    (source / "secret.py").write_text("print('not inventoried')\n")
    monkeypatch.setattr(absorb_engine, "CACHE", tmp_path / ".home" / ".sz" / "cache" / "absorb")
    monkeypatch.setattr(
        absorb_engine,
        "inventory",
        lambda src: {"layout": "README.md", "files": "\n--- README.md ---\n# source\n"},
    )

    draft = {
        "module_id": "bad-module",
        "description": "Invalid module.",
        "category": "control",
        "entry": {"type": "python", "command": "entry.py", "args": []},
        "triggers": [{"on": "tick"}],
        "provides": [],
        "requires": [],
        "setpoints": {},
        "files_to_copy": [{"from": "secret.py", "to": "secret.py"}],
        "entry_script": "#!/usr/bin/env python3\nprint('bad')\n",
        "reconcile_script": "#!/usr/bin/env bash\ncat \"$SZ_REGISTRY_PATH\" >/dev/null\n",
        "notes": "This should be rejected.",
    }

    def fake_invoke(prompt: str, **kwargs) -> LLMResult:
        return LLMResult(
            text=json.dumps(draft),
            parsed=draft,
            tokens_in=1,
            tokens_out=1,
            model="mock",
            provider="mock",
        )

    monkeypatch.setattr(absorb_engine.llm, "invoke", fake_invoke)

    with pytest.raises(ValueError, match="not present in inventory"):
        absorb_engine.absorb(str(source), "bad", dry_run=True)
