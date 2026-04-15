#!/usr/bin/env python3
"""Build, validate, and visualize workflow-spec dependencies."""

from __future__ import annotations

import argparse
import json

from specification.workflow_support import build_dependency_graph, write_dependency_graph


def to_dot(graph: dict) -> str:
    lines = ["digraph workflow_specs {"]
    for node in graph["nodes"]:
        lines.append(f'  "{node}";')
    for edge in graph["edges"]:
        status = "valid" if edge["valid"] else "broken"
        lines.append(
            f'  "{edge["from"]}" -> "{edge["to"]}" [label="{edge["via"]} ({status})"];'
        )
    lines.append("}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate dependency edges")
    parser.add_argument("--visualize", action="store_true", help="Print DOT graph")
    parser.add_argument("--json", action="store_true", help="Print JSON graph")
    args = parser.parse_args()

    graph = build_dependency_graph()
    write_dependency_graph(graph)

    if args.visualize:
        print(to_dot(graph))
    elif args.json:
        print(json.dumps(graph, indent=2))
    else:
        print(json.dumps(graph, indent=2))

    return 1 if args.check and (graph["broken_edges"] or graph["cycles"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
