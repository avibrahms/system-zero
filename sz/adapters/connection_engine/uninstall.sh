#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${SZ_REPO_ROOT:-$(pwd)}"
REG="$REPO_ROOT/core/system/maintenance-registry.yaml"
[ -f "$REG" ] || { echo "no maintenance-registry.yaml; nothing to remove"; exit 0; }
python3 - "$REG" <<'PY'
import pathlib
import sys

import yaml

p = pathlib.Path(sys.argv[1])
data = yaml.safe_load(p.read_text()) or {}
tasks = data.setdefault("tasks", {})
tasks.pop("sz--tick", None)
p.write_text(yaml.safe_dump(data, sort_keys=False))
PY
echo "connection_engine adapter uninstalled"
