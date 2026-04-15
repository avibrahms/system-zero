#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${SZ_REPO_ROOT:-$(pwd)}"
CONF="$REPO_ROOT/.metaclaw/config.yaml"
[ -f "$CONF" ] || { echo "no .metaclaw/config.yaml; nothing to remove"; exit 0; }
python3 - "$CONF" <<'PY'
import pathlib
import sys

import yaml

p = pathlib.Path(sys.argv[1])
data = yaml.safe_load(p.read_text()) or {}
hooks = data.get("hooks", {})
hooks["on_tick"] = [c for c in hooks.get("on_tick", []) if c != "sz tick --reason metaclaw"]
data["hooks"] = hooks
p.write_text(yaml.safe_dump(data, sort_keys=False))
PY
echo "metaclaw adapter uninstalled"
