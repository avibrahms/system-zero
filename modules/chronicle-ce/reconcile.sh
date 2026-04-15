#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import json, os
from pathlib import Path
registry = Path(os.environ['SZ_REGISTRY_PATH'])
module = Path(os.environ['SZ_MODULE_DIR'])
payload = json.loads(registry.read_text()) if registry.exists() else {}
runtime = {'bindings': payload.get('bindings', [])}
(module / 'runtime.json').write_text(json.dumps(runtime, sort_keys=True) + '\n')
PY
