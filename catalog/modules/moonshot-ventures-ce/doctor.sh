#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import sys
from pathlib import Path
import yaml
module = Path(__import__('os').environ['SZ_MODULE_DIR'])
manifest_path = module / 'module.yaml'
if not manifest_path.is_file():
    raise SystemExit('missing module.yaml')
data = yaml.safe_load(manifest_path.read_text()) or {}
entry = module / data.get('entry', {}).get('command', '')
reconcile = module / data.get('hooks', {}).get('reconcile', 'reconcile.sh')
missing = [str(path.relative_to(module)) for path in (entry, reconcile) if not path.exists()]
if missing:
    raise SystemExit('missing required files: ' + ', '.join(missing))
print('ok')
PY
