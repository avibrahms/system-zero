#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${SZ_REPO_ROOT:-$(pwd)}"
HCONF="$REPO_ROOT/.hermes/config.yaml"
[ -f "$HCONF" ] || { echo "no .hermes/config.yaml; cannot adopt"; exit 2; }

python3 - "$HCONF" <<'PY'
import pathlib
import sys

import yaml

p = pathlib.Path(sys.argv[1])
data = yaml.safe_load(p.read_text()) or {}
hooks = data.setdefault("hooks", {})
on_tick = hooks.setdefault("on_tick", [])
cmd = "sz tick --reason hermes"
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
cfg["host"] = "hermes"
cfg["host_mode"] = "adopt"
p.write_text(yaml.safe_dump(cfg, sort_keys=False))
PY

echo "hermes adapter installed (Adopt mode) - Hermes will now call sz tick on each pulse."
