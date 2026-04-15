#!/usr/bin/env python3
"""Generate catalog/index.json from catalog/modules/."""
import json, sys
from pathlib import Path
import yaml

HERE = Path(__file__).resolve().parents[1]
MODULES = HERE / "modules"
OUT = HERE / "index.json"


def main() -> int:
    items = []
    for mdir in sorted(MODULES.iterdir()):
        man_p = mdir / "module.yaml"
        src_p = mdir / "source.yaml"
        rdme = mdir / "README.md"
        if not (man_p.exists() and src_p.exists()):
            continue
        man = yaml.safe_load(man_p.read_text())
        src = yaml.safe_load(src_p.read_text())
        items.append({
            "id": man["id"],
            "version": man["version"],
            "category": man.get("category", ""),
            "description": man.get("description", ""),
            "personas": man.get("personas", ["static", "dynamic"]),
            "provides": [c["name"] for c in man.get("provides", []) or []],
            "requires": [r["name"] for r in (man.get("requires") or []) if "name" in r],
            "setpoints": man.get("setpoints", {}),
            "source": src,
            "readme": rdme.read_text() if rdme.exists() else "",
        })
    OUT.write_text(json.dumps({"version": "0.1.0", "items": items}, indent=2))
    print(f"wrote {OUT} ({len(items)} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
