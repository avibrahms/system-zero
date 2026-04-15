#!/usr/bin/env python3
import json, os
from pathlib import Path
module_dir = Path(os.environ.get('SZ_MODULE_DIR', Path(__file__).resolve().parent))
source = module_dir / 'source' / 'AGENTS.md'
print(json.dumps({'absorbed_source': str(source), 'exists': source.exists()}))
