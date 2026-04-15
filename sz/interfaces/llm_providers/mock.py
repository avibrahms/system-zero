"""Offline mock LLM provider for tests and local fallbacks."""
from __future__ import annotations

import json
import re
from types import SimpleNamespace


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (slug or "absorbed-feature")[:40].strip("-") or "absorbed-feature"


def _absorb_response(prompt: str) -> dict:
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
    return {
        "module_id": module_id,
        "description": f"Mock absorbed module for {feature}.",
        "category": "absorbed",
        "entry": {"type": "python", "command": "entry.py", "args": []},
        "triggers": [{"on": "tick"}],
        "provides": [
            {
                "name": f"absorbed.{module_id.replace('-', '.')}",
                "address": f"events:absorbed.{module_id}.ran",
                "description": f"Emits events for {feature}.",
            }
        ],
        "requires": [],
        "setpoints": {},
        "files_to_copy": [{"from": source_file, "to": f"source/{source_file.split('/')[-1]}"}],
        "entry_script": (
            "#!/usr/bin/env python3\n"
            "import json, os\n"
            "from pathlib import Path\n"
            "module_dir = Path(os.environ.get('SZ_MODULE_DIR', Path(__file__).resolve().parent))\n"
            f"source = module_dir / 'source' / {source_file.split('/')[-1]!r}\n"
            "print(json.dumps({'absorbed_source': str(source), 'exists': source.exists()}))\n"
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
        "notes": "Mock provider generated a deterministic dry-run absorb draft.",
    }


def call(prompt: str, *, model: str | None = None, max_tokens: int = 1024):
    if prompt.lstrip().startswith("# S0 absorb prompt"):
        text = json.dumps(_absorb_response(prompt))
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
