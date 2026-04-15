#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${SZ_REPO_ROOT:-$(pwd)}"
CONF="$REPO_ROOT/.openclaw/config.yaml"
[ -d "$REPO_ROOT/.openclaw" ] || { echo "no .openclaw directory; cannot adopt"; exit 2; }
touch "$CONF"

python3 - "$CONF" <<'PY'
import pathlib
import sys

import yaml

p = pathlib.Path(sys.argv[1])
data = yaml.safe_load(p.read_text()) or {}
hooks = data.setdefault("hooks", {})
on_tick = hooks.setdefault("on_tick", [])
cmd = "sz tick --reason openclaw"
if cmd not in on_tick:
    on_tick.append(cmd)
p.write_text(yaml.safe_dump(data, sort_keys=False))
PY

python3 - "$REPO_ROOT/.sz.yaml" <<'PY'
import pathlib
import sys

import yaml

p = pathlib.Path(sys.argv[1])
cfg = yaml.safe_load(p.read_text()) if p.exists() else {}
cfg = cfg or {}
cfg["host"] = "openclaw"
cfg["host_mode"] = "adopt"
p.write_text(yaml.safe_dump(cfg, sort_keys=False))
PY

echo "openclaw adapter installed (Adopt mode)"
