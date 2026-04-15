#!/usr/bin/env python3
"""Absorb a local source using a canned draft JSON matched by substring.

Usage:
  absorb_with_canned.py <source-dir> <module-id>

Expects env SZ_ABSORB_CANNED pointing to a directory of canned JSON files
named matching common source repo names (p-limit.json, changed-files.json, llm.json).
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    src, module_id = pathlib.Path(sys.argv[1]), sys.argv[2]
    canned = pathlib.Path(os.environ["SZ_ABSORB_CANNED"])
    if "p-limit" in str(src):
        draft = json.loads((canned / "p-limit.json").read_text())
    elif "changed-files" in str(src):
        draft = json.loads((canned / "changed-files.json").read_text())
    elif "/llm" in str(src):
        draft = json.loads((canned / "llm.json").read_text())
    else:
        print("no canned match")
        sys.exit(2)
    draft["module_id"] = module_id
    import yaml

    staging = pathlib.Path(tempfile.mkdtemp(prefix="sz-absorb-")) / module_id
    staging.mkdir(parents=True)
    manifest = {
        "id": module_id,
        "version": "0.1.0",
        "category": draft.get("category", "absorbed"),
        "description": draft.get("description", ""),
        "entry": draft["entry"],
        "triggers": draft.get("triggers", [{"on": "tick"}]),
        "provides": draft.get("provides", []),
        "requires": draft.get("requires", []),
        "setpoints": draft.get("setpoints", {}),
        "hooks": {"reconcile": "reconcile.sh"},
    }
    (staging / "module.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    for s in draft.get("files_to_copy", []):
        src_p = (src / s["from"]).resolve()
        dst_p = (staging / s["to"]).resolve()
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        if src_p.exists():
            shutil.copy2(src_p, dst_p)
    e = staging / draft["entry"]["command"]
    e.parent.mkdir(parents=True, exist_ok=True)
    e.write_text(draft["entry_script"])
    e.chmod(0o755)
    r = staging / "reconcile.sh"
    r.write_text(draft["reconcile_script"])
    r.chmod(0o755)
    subprocess.run(["sz", "install", module_id, "--source", str(staging)], check=True)


if __name__ == "__main__":
    main()
