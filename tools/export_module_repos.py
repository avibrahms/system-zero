#!/usr/bin/env python3
"""Export absorbed System Zero modules to standalone GitHub repos.

The canonical source stays in this repo. Exported repos are generated mirrors for
discovery, demos, and independent promotion.
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path("/Users/avi/Documents/Projects/system0-natural")
OWNER = os.environ.get("SZ_MODULE_REPO_OWNER", "avibrahms")
VISIBILITY = os.environ.get("SZ_MODULE_REPO_VISIBILITY", "private")
DRY_RUN = os.environ.get("SZ_MODULE_REPO_DRY_RUN", "0") == "1"


def run(cmd, cwd=None, check=True):
    if DRY_RUN:
        print("+", " ".join(cmd))
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=check)


def default_branch(full_name):
    result = run(
        ["gh", "repo", "view", full_name, "--json", "defaultBranchRef", "--jq", ".defaultBranchRef.name"],
        check=False,
    )
    branch = result.stdout.strip() if result.stdout else ""
    return branch or "main"


def module_readme(module_id, manifest):
    title = manifest.get("name") or module_id
    desc = manifest.get("description") or "A standalone System Zero organ exported from the connection-engine reconstruction."
    env = manifest.get("env", []) or manifest.get("environment", [])
    env_block = "\n".join(f"- `{e}`" for e in env) if env else "- None required by default."
    return f"""# {title}

{desc}

This repo is a generated standalone mirror of the `{module_id}` System Zero module.
The canonical source lives in the System Zero catalog; this repo exists so the organ
can be discovered, demonstrated, and promoted independently.

## Install

```bash
sz install {module_id}
sz doctor
```

## Required environment

{env_block}

## Source of truth

- Catalog module: `catalog/modules/{module_id}`
- Canonical module tree: `modules/{module_id}`
- System Zero: https://systemzero.dev
- Reference stack: https://github.com/avibrahms/connection-engine-reference
"""


def load_manifest(module_dir):
    for name in ("module.yaml", "module.yml", "manifest.yaml", "manifest.json"):
        p = module_dir / name
        if p.exists():
            if p.suffix == ".json":
                return json.loads(p.read_text())
            try:
                import yaml
                return yaml.safe_load(p.read_text()) or {}
            except Exception:
                return {}
    return {}


def export_one(module_dir):
    module_id = module_dir.name
    repo_name = f"sz-module-{module_id}"
    full_name = f"{OWNER}/{repo_name}"
    manifest = load_manifest(module_dir)
    work = pathlib.Path(tempfile.mkdtemp(prefix=f"{repo_name}-"))
    try:
        shutil.copytree(module_dir, work / module_id)
        (work / "README.md").write_text(module_readme(module_id, manifest))
        (work / ".sz-module-origin.json").write_text(json.dumps({
            "module_id": module_id,
            "canonical_path": f"modules/{module_id}",
            "catalog_path": f"catalog/modules/{module_id}",
            "generated": True,
            "source_of_truth": "system0-natural",
        }, indent=2) + "\n")
        env_example = work / ".env.example"
        if not env_example.exists():
            env_example.write_text("# Add module-specific environment values here.\n")

        run(["git", "init", "-q"], cwd=work)
        run(["git", "config", "user.email", "ops@systemzero.dev"], cwd=work)
        run(["git", "config", "user.name", "System Zero"], cwd=work)
        run(["git", "add", "."], cwd=work)
        run(["git", "commit", "-m", f"export {module_id} module"], cwd=work)

        exists = run(["gh", "repo", "view", full_name], check=False).returncode == 0
        if not exists:
            run(["gh", "repo", "create", full_name, f"--{VISIBILITY}", "--source", str(work), "--push"])
        else:
            run(["git", "remote", "add", "origin", f"https://github.com/{full_name}.git"], cwd=work, check=False)
            run(["git", "push", "-u", "origin", f"HEAD:{default_branch(full_name)}", "--force"], cwd=work)
        run(["gh", "repo", "edit", full_name, "--add-topic", "system-zero", "--add-topic", "agentic-ai", "--add-topic", "self-improvement"], check=False)
        return {"id": module_id, "repo": f"https://github.com/{full_name}", "status": "exported"}
    except Exception as exc:
        return {"id": module_id, "repo": full_name, "status": "soft_blocked", "error": str(exc)[:500]}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    modules = sorted((ROOT / "modules").glob("*-ce"))
    results = [export_one(m) for m in modules if m.is_dir()]
    out = ROOT / ".test-reports" / "phase-16-module-repos.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))
    if not modules:
        sys.exit("no absorbed *-ce modules found")


if __name__ == "__main__":
    main()
