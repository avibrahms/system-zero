#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${SZ_REPO_ROOT:-$(pwd)}"
REG="$REPO_ROOT/core/system/maintenance-registry.yaml"
[ -f "$REG" ] || { echo "no maintenance-registry.yaml; cannot adopt"; exit 2; }
python3 - "$REG" <<'PY'
import pathlib
import sys

import yaml

p = pathlib.Path(sys.argv[1])
data = yaml.safe_load(p.read_text()) or {}
tasks = data.setdefault("tasks", {})
key = "sz--tick"
if key not in tasks:
    tasks[key] = {
        "frequency": "5m",
        "command": "sz tick --reason connection_engine",
        "outcome_file": "core/system/data/outcomes/s0-tick.json",
    }
    p.write_text(yaml.safe_dump(data, sort_keys=False))
PY
python3 - "$REPO_ROOT/.sz.yaml" <<'PY'
import pathlib
import sys

import yaml

p = pathlib.Path(sys.argv[1])
cfg = yaml.safe_load(p.read_text()) if p.exists() else {}
cfg = cfg or {}
cfg["host"] = "connection_engine"
cfg["host_mode"] = "adopt"
p.write_text(yaml.safe_dump(cfg, sort_keys=False))
PY
echo "connection_engine adapter installed (Adopt mode)"
