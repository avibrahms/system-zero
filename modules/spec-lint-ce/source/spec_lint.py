#!/usr/bin/env python3
"""Validate workflow specs against the spec contract and import graph."""

from __future__ import annotations

import argparse
import json
import sys

from specification.workflow_support import (
    build_dependency_graph,
    discover_workflow_specs,
    validate_workflow_spec,
    write_dependency_graph,
)


def lint_all() -> tuple[list[str], list[str], dict]:
    errors: list[str] = []
    warnings: list[str] = []
    for path in discover_workflow_specs():
        spec_errors, spec_warnings = validate_workflow_spec(path)
        errors.extend(f"{path.name}: {error}" for error in spec_errors)
        warnings.extend(f"{path.name}: {warning}" for warning in spec_warnings)

    graph = build_dependency_graph()
    write_dependency_graph(graph)
    if graph["cycles"]:
        errors.extend(f"cycle: {' -> '.join(cycle)}" for cycle in graph["cycles"])
    warnings.extend(f"orphan: {name}" for name in graph["orphans"])
    return errors, warnings, graph


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-all", action="store_true", help="Validate all workflow specs")
    parser.add_argument("--json", action="store_true", help="Print JSON result")
    args = parser.parse_args()

    if not args.validate_all:
        parser.error("Only --validate-all is supported")

    errors, warnings, graph = lint_all()
    result = {"errors": errors, "warnings": warnings, "graph": graph}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if errors:
            print("Workflow spec lint FAILED:", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
        else:
            print(f"Workflow spec lint passed ({len(graph['nodes'])} specs)")
        for warning in warnings:
            print(f"  WARNING: {warning}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
