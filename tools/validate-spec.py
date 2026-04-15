#!/usr/bin/env python3
"""Validate a YAML or JSON file against an S0 JSON Schema.

Usage:
  tools/validate-spec.py <schema.json> <data.yaml|.json>
"""
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


def load(path: Path):
    text = path.read_text()
    if path.suffix in {".yaml", ".yml"}:
        return yaml.safe_load(text)
    return json.loads(text)


def main(schema_path: str, data_path: str) -> int:
    schema = json.loads(Path(schema_path).read_text())
    data = load(Path(data_path))
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(data))
    if errors:
        for e in errors:
            print(f"ERROR at {list(e.absolute_path)}: {e.message}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
