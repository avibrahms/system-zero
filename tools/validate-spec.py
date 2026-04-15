#!/usr/bin/env python3
"""Validate a YAML or JSON file against an S0 JSON Schema.

Usage:
  tools/validate-spec.py <schema.json> <data.yaml|.json>
"""
import json
import sys
from pathlib import Path

import yaml
from jsonschema import exceptions, validators
from referencing import Registry, Resource


def load(path: Path):
    text = path.read_text()
    if path.suffix in {".yaml", ".yml"}:
        return yaml.safe_load(text)
    return json.loads(text)


def find_spec_root(path: Path) -> Path:
    for candidate in (path, *path.parents):
        if candidate.name == "spec":
            return candidate
    return path.parent


def build_registry(spec_root: Path) -> Registry:
    resources = {}
    for schema_path in sorted(spec_root.rglob("*.json")):
        contents = json.loads(schema_path.read_text())
        schema_id = contents.get("$id")
        if not schema_id:
            continue
        resources[schema_id] = Resource.from_contents(contents)
    return Registry().with_resources(resources.items())


def main(schema_path: str, data_path: str) -> int:
    schema_file = Path(schema_path)
    schema = json.loads(schema_file.read_text())
    data = load(Path(data_path))
    registry = build_registry(find_spec_root(schema_file.resolve()))
    validator_cls = validators.validator_for(schema)
    try:
        validator_cls.check_schema(schema)
    except exceptions.SchemaError as error:
        print(f"SCHEMA ERROR: {error.message}")
        return 1
    validator = validator_cls(schema, registry=registry)
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
