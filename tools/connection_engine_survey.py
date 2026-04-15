#!/usr/bin/env python3
"""Enumerate connection-engine candidates for absorption.

Walks the source tree, identifies files that look like modules (standalone scripts,
maintenance.yaml, or directory-shaped modules), and emits a JSON inventory for
phase 16 consumption.
"""
import argparse, json, pathlib, re, sys

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv"}
SKIP_NAMES = {
    "argentina",
    "business",
    "google-ads",
    "identity",
    "linkedin-content-pipeline",
    "linkedin-messaging",
    "mass-market",
    "moonshot-ventures",
    "profiles",
    "solo-venture",
    "viralepic",
}

def survey(src: pathlib.Path) -> list[dict]:
    items = []
    # 1. Every modules/<x>/CLAUDE.md is a candidate module.
    for m in sorted((src / "modules").glob("*/CLAUDE.md")):
        name = m.parent.name
        items.append({"kind": "module-dir", "id": name, "path": str(m.parent),
                      "category": "skip" if name in SKIP_NAMES else "keep"})
    # 2. Every core/system/scripts/*.py with a __main__ entry.
    scripts_dir = src / "core" / "system" / "scripts"
    if scripts_dir.exists():
        for p in sorted(scripts_dir.rglob("*.py")):
            if any(s in p.parts for s in SKIP_DIRS): continue
            text = p.read_text(errors="ignore")[:2000]
            if "__main__" in text or "def main" in text:
                items.append({"kind": "script", "id": p.stem.replace("_","-"),
                              "path": str(p), "category": "keep"})
    # 3. Home-templates skills.
    for m in sorted((src / "home-templates" / "agent-dashboard" / "skills").glob("*/SKILL.md")) if (src / "home-templates").exists() else []:
        items.append({"kind":"skill","id": m.parent.name, "path": str(m.parent), "category":"rewrite"})
    return items

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    pathlib.Path(a.out).write_text(json.dumps(survey(pathlib.Path(a.source)), indent=2))
    print(f"wrote {a.out}")

if __name__ == "__main__":
    main()
