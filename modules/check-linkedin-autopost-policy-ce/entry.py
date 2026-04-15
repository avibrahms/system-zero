#!/usr/bin/env python3
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
