#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${SZ_REPO_ROOT:-$(pwd)}"
python3 - "$REPO_ROOT/.sz.yaml" <<'PY'
import pathlib
import sys

import yaml

p = pathlib.Path(sys.argv[1])
cfg = yaml.safe_load(p.read_text()) if p.exists() else {}
cfg = cfg or {}
if cfg.get("host") == "unknown":
    cfg["host"] = "generic"
    cfg["host_mode"] = "install"
p.write_text(yaml.safe_dump(cfg, sort_keys=False))
PY
echo "unknown adapter uninstalled"
