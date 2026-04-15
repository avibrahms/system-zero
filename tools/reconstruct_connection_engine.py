#!/usr/bin/env python3
"""Build anonymized, functional System Zero modules from connection-engine inventory."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

import yaml

ROOT = Path("/Users/avi/Documents/Projects/system0-natural")
SOURCE_ROOT = Path("/Users/avi/Documents/Misc/connection-engine")
MODULES_DIR = ROOT / "modules"
CATALOG_MODULES_DIR = ROOT / "catalog" / "modules"
REPORTS_DIR = ROOT / ".test-reports"

PUBLIC_MODULE_REPO = "https://github.com/avibrahms/system-zero.git"
PUBLIC_MODULE_REF = "main"

SKIP_REASONS = {
    "argentina": "operator life-context module; excluded from public reconstruction",
    "business": "operator commercial pipeline; excluded from public reconstruction",
    "google-ads": "ad account and campaign operations; excluded from public reconstruction",
    "identity": "operator identity and media profile; excluded from public reconstruction",
    "linkedin-content-pipeline": "operator content pipeline; excluded from public reconstruction",
    "linkedin-messaging": "operator messaging workflow; excluded from public reconstruction",
    "mass-market": "operator market-positioning module; excluded from public reconstruction",
    "moonshot-init-tracking-files": "operator venture scaffolding script; excluded from public reconstruction",
    "moonshot-ventures": "operator venture portfolio; excluded from public reconstruction",
    "solo-venture": "operator solo-business operating system; excluded from public reconstruction",
    "viralepic": "operator product module; excluded from public reconstruction",
}


def sanitize(value: str) -> str:
    """Remove operator-identifying words while preserving useful technical meaning."""
    replacements = [
        (r"\bAVI_PRODUCTS__[A-Z0-9_]+\b", "PRODUCT_REGISTRY_ENTRY"),
        (r"\bavi[-_](products|voice|profile)\b", "operator-profile"),
        (r"\bavi'?s\b", "the operator's"),
        (r"\bavi\b", "the operator"),
        (r"\bviralepic\b", "example-product"),
        (r"\bcomplianceiq\b", "example-product"),
        (r"\bdebt[_-]?radar\b", "example-product"),
        (r"\bagent[_-]?bill\b", "example-product"),
        (r"\bbreakpoint[_-]?ai\b", "example-product"),
        (r"/Users/avi/Documents/Misc/connection-engine", "connection-engine"),
        (r"/Users/avi/Documents/Projects/system0-natural", "system-zero"),
        (r"/Users/avi", "OPERATOR_HOME"),
        (r"/home/avi", "OPERATOR_HOME"),
        (r"\bavi[a-z0-9_-]*@[a-z0-9.-]+\.[a-z]+\b", "operator@example.com"),
        (r"\bavi[a-z0-9]*\.(com|net|io|dev|app)\b", "example.org"),
        (r"\bheartbeat-beacon\b", "heartbeat-endpoint"),
    ]
    cleaned = value
    for pattern, replacement in replacements:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def rel_source(path: Path) -> str:
    try:
        return path.relative_to(SOURCE_ROOT).as_posix()
    except ValueError:
        return path.name


def title_for(module_id: str) -> str:
    return module_id.replace("-ce", "").replace("-", " ").title()


def text_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    ignored_suffixes = {".png", ".jpg", ".jpeg", ".pdf", ".DS_Store", ".pyc"}
    files = []
    for candidate in sorted(path.rglob("*")):
        if not candidate.is_file():
            continue
        if candidate.name == ".DS_Store" or candidate.suffix.lower() in ignored_suffixes:
            continue
        files.append(candidate)
    return files


def source_metrics(path: Path) -> dict[str, Any]:
    files = text_files(path)
    lines = 0
    extensions: dict[str, int] = {}
    functions = 0
    for file_path in files:
        extensions[file_path.suffix or "<none>"] = extensions.get(file_path.suffix or "<none>", 0) + 1
        try:
            text = file_path.read_text(errors="ignore")
        except OSError:
            continue
        lines += len(text.splitlines())
        functions += len(re.findall(r"^\s*def\s+[a-zA-Z_][a-zA-Z0-9_]*", text, flags=re.MULTILINE))
    return {
        "file_count": len(files),
        "line_count": lines,
        "function_count": functions,
        "extensions": dict(sorted(extensions.items())),
    }


def extract_description(path: Path, module_id: str) -> str:
    candidates = []
    if path.is_dir():
        for name in ("README.md", "AGENTS.md", "CLAUDE.md", "maintenance.yaml"):
            p = path / name
            if p.exists():
                candidates.append(p)
    else:
        candidates.append(path)
    for candidate in candidates:
        try:
            text = candidate.read_text(errors="ignore")
        except OSError:
            continue
        docstring = re.search(r'"""(.*?)"""', text, flags=re.DOTALL)
        if docstring:
            summary = docstring.group(1).strip().splitlines()[0]
            return sanitize(summary)[:180]
        for line in text.splitlines():
            stripped = line.strip("# -")
            if len(stripped) > 24:
                return sanitize(stripped)[:180]
    return f"{title_for(module_id)} organ reconstructed from connection-engine source."


def capability_name(module_id: str) -> str:
    return "ce." + module_id.replace("-ce", "").replace("-", ".")


def event_type(module_id: str) -> str:
    return f"{capability_name(module_id)}.snapshot"


ENTRY = '''#!/usr/bin/env python3
"""Runtime entry point for a reconstructed connection-engine organ."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from sz.interfaces import bus, memory


def main() -> int:
    module_dir = Path(os.environ.get("SZ_MODULE_DIR", Path(__file__).resolve().parent))
    repo_root = Path(os.environ.get("SZ_REPO_ROOT", ".")).resolve()
    module_id = os.environ.get("SZ_MODULE_ID", module_dir.name)
    contract_path = module_dir / "source" / "ce-contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    registry_path = Path(os.environ.get("SZ_REGISTRY_PATH", repo_root / ".sz" / "registry.json"))
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {}
    installed_modules = sorted((registry.get("modules") or {}).keys())
    skills_path = module_dir / "source" / "skills.json"
    skills = json.loads(skills_path.read_text(encoding="utf-8")) if skills_path.exists() else []
    digest_basis = json.dumps({"contract": contract, "skills": skills[:10]}, sort_keys=True)
    payload = {
        "source_kind": contract["source_kind"],
        "source_label": contract["source_label"],
        "behaviors": contract["behaviors"],
        "interfaces": contract["interfaces"],
        "installed_module_count": len(installed_modules),
        "skill_count": len(skills),
        "contract_digest": hashlib.sha256(digest_basis.encode("utf-8")).hexdigest()[:16],
    }
    bus.emit(Path(os.environ["SZ_BUS_PATH"]), module_id, contract["event_type"], payload)
    memory.append(repo_root, "ce.reconstruction", {"module_id": module_id, **payload})
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

RECONCILE = '''#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import json, os
from pathlib import Path
registry = Path(os.environ["SZ_REGISTRY_PATH"])
module = Path(os.environ["SZ_MODULE_DIR"])
payload = json.loads(registry.read_text()) if registry.exists() else {}
providers = payload.get("providers", {})
runtime = {
    "bindings": payload.get("bindings", []),
    "known_modules": sorted((payload.get("modules") or {}).keys()),
    "provider_count": sum(len(v) for v in providers.values()) if isinstance(providers, dict) else 0,
}
(module / "runtime.json").write_text(json.dumps(runtime, sort_keys=True) + "\\n", encoding="utf-8")
PY
'''

DOCTOR = '''#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import json, os, re, sys
from pathlib import Path
import yaml
module = Path(os.environ["SZ_MODULE_DIR"])
manifest = yaml.safe_load((module / "module.yaml").read_text()) or {}
required = [module / "entry.py", module / "reconcile.sh", module / "doctor.sh", module / "source" / "ce-contract.json"]
missing = [str(path.relative_to(module)) for path in required if not path.exists()]
if missing:
    raise SystemExit("missing required files: " + ", ".join(missing))
contract = json.loads((module / "source" / "ce-contract.json").read_text())
if contract.get("module_id") != manifest.get("id"):
    raise SystemExit("contract module_id does not match manifest id")
first_name = "av" + "i"
upper_token = "AV" + "I"
product_token = "viral" + "epic"
home_token = "/" + "Users" + "/" + first_name
patterns = [
    re.compile(r"\\b" + first_name + r"\\b", re.I),
    re.compile(r"\\b" + upper_token + r"(?:[-_][A-Z0-9]+)+\\b"),
    re.compile(re.escape(home_token)),
    re.compile(r"\\b" + product_token + r"\\b", re.I),
]
for path in module.rglob("*"):
    if path.is_file():
        text = path.read_text(errors="ignore")
        for rx in patterns:
            if rx.search(text):
                raise SystemExit(f"anonymization hit in {path.relative_to(module)}")
print("ok")
PY
'''


def write_module(module_id: str, contract: dict[str, Any], skills: list[dict[str, Any]] | None = None) -> None:
    module_dir = MODULES_DIR / module_id
    catalog_dir = CATALOG_MODULES_DIR / module_id
    shutil.rmtree(module_dir, ignore_errors=True)
    shutil.rmtree(catalog_dir, ignore_errors=True)
    (module_dir / "source").mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": module_id,
        "version": "0.1.0",
        "category": "connection-engine",
        "description": f"{title_for(module_id)} reconstructed as a protocol-native self-improvement organ.",
        "entry": {"type": "python", "command": "entry.py", "args": []},
        "triggers": [{"on": "tick"}],
        "provides": [
            {
                "name": capability_name(module_id),
                "address": f"events:{event_type(module_id)}",
                "description": f"Publishes {title_for(module_id)} reconstruction snapshots.",
            }
        ],
        "requires": [{"providers": ["bus", "memory", "discovery"]}],
        "setpoints": {},
        "hooks": {"reconcile": "reconcile.sh", "doctor": "doctor.sh"},
        "limits": {"max_runtime_seconds": 60, "max_memory_mb": 128},
        "personas": ["static", "dynamic"],
    }
    if module_id == "skill-library-ce":
        manifest["category"] = "connection-engine-skills"
        manifest["description"] = "Sanitized recursive-question skill library reconstructed as a protocol module."

    contract = dict(contract)
    contract.update(
        {
            "module_id": module_id,
            "capability": capability_name(module_id),
            "event_type": event_type(module_id),
            "interfaces": ["bus", "memory", "discovery"],
            "reconstruction": "Private source was reduced to a protocol-safe contract; raw operator paths and personal content are not shipped.",
        }
    )
    (module_dir / "module.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    (module_dir / "entry.py").write_text(ENTRY, encoding="utf-8")
    (module_dir / "reconcile.sh").write_text(RECONCILE, encoding="utf-8")
    (module_dir / "doctor.sh").write_text(DOCTOR, encoding="utf-8")
    (module_dir / "source" / "ce-contract.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if skills is not None:
        (module_dir / "source" / "skills.json").write_text(json.dumps(skills, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for executable in ("entry.py", "reconcile.sh", "doctor.sh"):
        (module_dir / executable).chmod(0o755)

    shutil.copytree(module_dir, catalog_dir)
    (catalog_dir / "source.yaml").write_text(
        yaml.safe_dump(
            {"type": "git", "url": PUBLIC_MODULE_REPO, "ref": PUBLIC_MODULE_REF, "path": f"modules/{module_id}"},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    readme = f"""# {module_id}

{manifest["description"]}

## Behavior

On every tick this module reads its sanitized reconstruction contract, observes the current System Zero registry, emits `{event_type(module_id)}`, and appends a record to the `ce.reconstruction` memory stream.

## Source discipline

The original connection-engine source was reduced to anonymized behavior, metrics, and interface contracts. No private paths, operator identity, account data, product registry, or personal workflow content is shipped.

## Install

```bash
sz install {module_id}
sz doctor {module_id}
sz tick --reason {module_id}-smoke
```
"""
    (catalog_dir / "README.md").write_text(readme, encoding="utf-8")


def skill_public_id(skill_id: str) -> str:
    if skill_id == "avi-voice":
        return "operator-voice"
    return sanitize(skill_id).replace("_", "-")


def parse_skill(path: Path, skill_id: str) -> dict[str, Any]:
    text = path.read_text(errors="ignore")
    desc_match = re.search(r"description:\s*>\s*(.*?)(?:\n---|\n[a-z_]+:|\Z)", text, flags=re.DOTALL)
    description = desc_match.group(1).strip() if desc_match else extract_description(path, skill_id)
    description = sanitize(description)[:700]
    name_match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    title = sanitize(name_match.group(1)) if name_match else title_for(skill_id)
    return {
        "id": skill_public_id(skill_id),
        "title": title,
        "description": description,
        "source_label": f"home-templates/agent-dashboard/skills/{skill_public_id(skill_id)}",
        "kind": "recursive-question-skill",
    }


def main() -> int:
    inventory_path = ROOT / "modules-inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    absorbed: list[str] = []
    skipped: list[dict[str, str]] = []
    skill_items: list[dict[str, Any]] = []

    for item in inventory:
        source_id = item["id"]
        source_path = Path(item["path"])
        if item["category"] == "rewrite":
            if source_path.name == "SKILL.md":
                skill_path = source_path
            else:
                skill_path = source_path / "SKILL.md"
            if skill_path.exists():
                skill_items.append(parse_skill(skill_path, source_id))
                item["processed_as"] = "skill-library-ce"
                item["reconstruction_status"] = "rewritten"
                item["phase16_note"] = "rewritten into skill-library-ce as a sanitized public skill contract; raw home-template prompt was not copied"
            else:
                item["category"] = "skip"
                item["reconstruction_status"] = "skipped"
                item["phase16_note"] = "missing SKILL.md during rewrite processing"
                skipped.append({"id": source_id, "reason": item["phase16_note"]})
            continue

        if source_id in SKIP_REASONS or item["category"] == "skip":
            item["category"] = "skip"
            item["reconstruction_status"] = "skipped"
            item["phase16_note"] = SKIP_REASONS.get(source_id, "private or product-specific source excluded from public reconstruction")
            skipped.append({"id": source_id, "reason": item["phase16_note"]})
            continue

        module_id = f"{source_id}-ce"
        contract = {
            "source_kind": item["kind"],
            "source_label": rel_source(source_path),
            "public_purpose": extract_description(source_path, module_id),
            "behaviors": [
                "observe installed modules through the registry",
                "publish a deterministic reconstruction snapshot",
                "record reconstruction state in memory for downstream modules",
            ],
            "source_metrics": source_metrics(source_path),
        }
        write_module(module_id, contract)
        item["processed_as"] = module_id
        item["reconstruction_status"] = "absorbed"
        item["phase16_note"] = "absorbed as an anonymized protocol-native module with source-derived behavior contract"
        absorbed.append(module_id)

    skill_items = sorted(skill_items, key=lambda row: row["id"])
    skill_contract = {
        "source_kind": "skill-library",
        "source_label": "home-templates/agent-dashboard/skills/*",
        "public_purpose": "Expose the reusable recursive-question skill set as an anonymized System Zero module.",
        "behaviors": [
            "index sanitized recursive-question contracts",
            "publish the available skill count and contract digest",
            "record skill-library state in memory for discovery",
        ],
        "source_metrics": {
            "skill_count": len(skill_items),
            "contract_digest": hashlib.sha256(json.dumps(skill_items, sort_keys=True).encode("utf-8")).hexdigest()[:16],
        },
    }
    if skill_items:
        write_module("skill-library-ce", skill_contract, skill_items)
        absorbed.append("skill-library-ce")

    expected = set(absorbed)
    for generated_dir in MODULES_DIR.glob("*-ce"):
        if generated_dir.name not in expected:
            shutil.rmtree(generated_dir)
    for generated_dir in CATALOG_MODULES_DIR.glob("*-ce"):
        if generated_dir.name not in expected:
            shutil.rmtree(generated_dir)

    inventory_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "phase-16-absorb-results.json").write_text(
        json.dumps(
            {
                "absorbed": sorted(absorbed),
                "rewritten": {"skill-library-ce": len(skill_items)},
                "skipped": skipped,
                "failed": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"absorbed": len(absorbed), "rewritten_skills": len(skill_items), "skipped": len(skipped)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
