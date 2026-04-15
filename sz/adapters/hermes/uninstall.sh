#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${SZ_REPO_ROOT:-$(pwd)}"
HCONF="$REPO_ROOT/.hermes/config.yaml"
[ -f "$HCONF" ] || { echo "no .hermes/config.yaml; nothing to remove"; exit 0; }
python3 - "$HCONF" <<'PY'
import pathlib
import sys

import yaml

p = pathlib.Path(sys.argv[1])
data = yaml.safe_load(p.read_text()) or {}
hooks = data.get("hooks", {})
hooks["on_tick"] = [c for c in hooks.get("on_tick", []) if c != "sz tick --reason hermes"]
data["hooks"] = hooks
p.write_text(yaml.safe_dump(data, sort_keys=False))
PY
echo "hermes adapter uninstalled"
