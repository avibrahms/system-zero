"""Offline mock LLM provider for tests and local fallbacks."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from types import SimpleNamespace


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (slug or "absorbed-feature")[:40].strip("-") or "absorbed-feature"


def _absorb_response(prompt: str) -> dict:
    canned = _canned_absorb_response(prompt)
    if canned is not None:
        return canned

    feature_match = re.search(r"called:\s+\*\*(.*?)\*\*", prompt, flags=re.DOTALL)
    feature = feature_match.group(1).strip() if feature_match else "absorbed feature"
    files = re.findall(r"\n--- ([^\n]+) ---\n", prompt)
    source_file = next(
        (item for item in files if item.endswith((".py", ".js", ".ts", ".sh"))),
        next(
            (item for item in files if item.endswith((".json", ".yaml", ".yml", ".toml", ".md"))),
            files[0] if files else "README.md",
        ),
    )
    module_id = _slug(feature)
    event_type = f"absorbed.{module_id}.snapshot"
    source_basename = source_file.split("/")[-1]
    return {
        "module_id": module_id,
        "description": f"Deterministic absorbed module for {feature}.",
        "category": "absorbed",
        "entry": {"type": "python", "command": "entry.py", "args": []},
        "triggers": [{"on": "tick"}],
        "provides": [
            {
                "name": f"absorbed.{module_id.replace('-', '.')}",
                "address": f"events:{event_type}",
                "description": f"Emits a source-backed snapshot for {feature}.",
            }
        ],
        "requires": [],
        "setpoints": {},
        "files_to_copy": [{"from": source_file, "to": f"source/{source_basename}"}],
        "entry_script": (
            "#!/usr/bin/env python3\n"
            "import hashlib, json, os\n"
            "from pathlib import Path\n"
            "from sz.interfaces import bus, memory\n"
            "module_dir = Path(os.environ.get('SZ_MODULE_DIR', Path(__file__).resolve().parent))\n"
            "repo_root = Path(os.environ.get('SZ_REPO_ROOT', '.')).resolve()\n"
            "module_id = os.environ.get('SZ_MODULE_ID', module_dir.name)\n"
            "bus_path = Path(os.environ.get('SZ_BUS_PATH', repo_root / '.sz' / 'bus.jsonl'))\n"
            f"source = module_dir / 'source' / {source_basename!r}\n"
            "text = source.read_text(errors='ignore') if source.exists() else ''\n"
            "payload = {\n"
            "    'source_file': source.name,\n"
            "    'source_exists': source.exists(),\n"
            "    'source_lines': len(text.splitlines()),\n"
            "    'source_sha256': hashlib.sha256(text.encode()).hexdigest()[:16],\n"
            "}\n"
            f"bus.emit(bus_path, module_id, {event_type!r}, payload)\n"
            "memory.append(repo_root, 'absorbed.snapshots', {'module_id': module_id, **payload})\n"
            "print(json.dumps(payload, sort_keys=True))\n"
        ),
        "reconcile_script": (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "python3 - <<'PY'\n"
            "import json, os\n"
            "from pathlib import Path\n"
            "registry = Path(os.environ['SZ_REGISTRY_PATH'])\n"
            "module = Path(os.environ['SZ_MODULE_DIR'])\n"
            "payload = json.loads(registry.read_text()) if registry.exists() else {}\n"
            "runtime = {'bindings': payload.get('bindings', [])}\n"
            "(module / 'runtime.json').write_text(json.dumps(runtime, sort_keys=True) + '\\n')\n"
            "PY\n"
        ),
        "notes": "Mock provider generated a deterministic source-backed absorb draft.",
    }


def _canned_absorb_response(prompt: str) -> dict | None:
    canned_dir = os.environ.get("SZ_ABSORB_CANNED")
    if not canned_dir:
        return None

    source_match = re.search(r"^URL:\s*(.*?)\s*$", prompt, flags=re.MULTILINE)
    source = source_match.group(1) if source_match else ""
    source_name = Path(source).name
    if "p-limit" in source or source_name == "p-limit":
        filename = "p-limit.json"
    elif "changed-files" in source or source_name == "changed-files":
        filename = "changed-files.json"
    elif "simonw/llm" in source or source_name == "llm":
        filename = "llm.json"
    else:
        return None

    path = Path(canned_dir) / filename
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_genesis_response(prompt: str) -> dict:
    heartbeat_match = re.search(r"existing_heartbeat \(algorithmic\):\s*([a-z_]+)", prompt)
    existing_heartbeat = heartbeat_match.group(1) if heartbeat_match else "none"
    languages_match = re.search(r"detected_languages:\s*(\[.*?\])", prompt)
    try:
        languages = json.loads(languages_match.group(1)) if languages_match else []
    except json.JSONDecodeError:
        languages = []
    language = languages[0] if languages else "other"
    if len(languages) > 1:
        language = "mixed"
    if language not in {"python", "javascript", "typescript", "go", "rust", "ruby", "java", "kotlin", "swift", "php", "shell", "mixed", "other"}:
        language = "other"

    readme_match = re.search(r"README excerpt \(first 5 KB\):\n---\n(.*?)\n---", prompt, flags=re.DOTALL)
    readme = (readme_match.group(1).strip() if readme_match else "")
    heading = next((line.lstrip("# ").strip() for line in readme.splitlines() if line.strip()), "")
    purpose = heading[:200] or "Self-improving repository"

    if existing_heartbeat == "none":
        modules = [
            {"id": "heartbeat", "reason": "Start the owned pulse loop."},
            {"id": "immune", "reason": "Detect early failure signals."},
            {"id": "subconscious", "reason": "Summarize repository health."},
        ]
    else:
        modules = [
            {"id": "immune", "reason": "Detect early failure signals."},
            {"id": "subconscious", "reason": "Summarize repository health."},
            {"id": "prediction", "reason": "Predict likely next events."},
        ]

    return {
        "purpose": purpose,
        "language": language,
        "frameworks": [],
        "existing_heartbeat": existing_heartbeat,
        "goals": ["Run autonomously", "Detect regressions", "Improve safely"],
        "recommended_modules": modules,
        "risk_flags": [],
    }


def _dreaming_hypothesis_response(prompt: str) -> dict:
    return {
        "hypothesis": "Recent health events suggest anomaly density is rising before prediction confidence stabilizes.",
        "novelty_score": 0.82,
        "confidence": 0.64,
        "rationale": "The bus history links health and prediction events closely enough to test a threshold adjustment.",
    }


def call(prompt: str, *, model: str | None = None, max_tokens: int = 1024):
    if prompt.lstrip().startswith("# S0 absorb prompt"):
        text = json.dumps(_absorb_response(prompt))
    elif prompt.lstrip().startswith("# S0 Repo Genesis prompt"):
        text = json.dumps(_repo_genesis_response(prompt))
    elif prompt.lstrip().startswith("# S0 Dreaming hypothesis prompt"):
        text = json.dumps(_dreaming_hypothesis_response(prompt))
    else:
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
