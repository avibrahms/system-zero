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
cfg["host"] = "unknown"
cfg["host_mode"] = "adopt"
p.write_text(yaml.safe_dump(cfg, sort_keys=False))
PY
echo "unknown heartbeat detected; no adapter hook was installed."
echo "Wire the existing daemon to run: sz tick --reason unknown"
