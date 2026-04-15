#!/usr/bin/env python3
"""Import-safe alias for the hyphenated context-assembler script."""

from __future__ import annotations

import importlib.util
from pathlib import Path

source_path = Path(__file__).with_name("context-assembler.py")
spec = importlib.util.spec_from_file_location("context_assembler_runtime", source_path)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

assemble_context = module.assemble_context
main = module.main


if __name__ == "__main__":
    raise SystemExit(main())
