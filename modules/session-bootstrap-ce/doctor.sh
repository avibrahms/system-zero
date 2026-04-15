#!/usr/bin/env bash
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
    re.compile(r"\b" + first_name + r"\b", re.I),
    re.compile(r"\b" + upper_token + r"(?:[-_][A-Z0-9]+)+\b"),
    re.compile(re.escape(home_token)),
    re.compile(r"\b" + product_token + r"\b", re.I),
]
for path in module.rglob("*"):
    if path.is_file():
        text = path.read_text(errors="ignore")
        for rx in patterns:
            if rx.search(text):
                raise SystemExit(f"anonymization hit in {path.relative_to(module)}")
print("ok")
PY
