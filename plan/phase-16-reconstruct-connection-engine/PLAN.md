# Phase 16 — Reconstruct connection-engine (Anonymized, Via the Protocol)

## Goal

Use the fully-launched SZ protocol to re-derive every module of `connection-engine` as an independent, pluggable, anonymized module, then assemble them all into a public reference repo that demonstrates the complete self-improvement stack running on the SZ protocol alone — no hand-coded glue, no private paths, no user-identifying data, no custom runtime.

The output is threefold:

1. **One catalog entry per connection-engine module** (~30+ modules) in the public SZ catalog. Each has a manifest, a reconcile script, a doctor, and is installable by anyone via `sz install <id>`.
2. **One generated standalone GitHub repo per module** — private by default during this run, release-ready for later public promotion. These repos are marketing/discovery surfaces and portability artifacts, not new sources of truth.
3. **A public reference repo** — `systemzero-dev/connection-engine-reference` — that is an empty repo running `sz init --yes` against a pre-curated profile that recommends all of them. Anyone who clones and boots it gets a working connection-engine clone powered by SZ.

This phase is the ultimate proof: the protocol is expressive enough to reconstruct its own intellectual ancestor.

## Why this phase is last

Because it requires every earlier phase to work. The SZ protocol, the absorb command, the catalog, the cloud, the website, the tests — all must be green before this phase begins. Phase 16 does not produce any new protocol capability; it exercises everything built so far at maximum fidelity.

## Inputs

- Phases 00–15 complete. Public release live at `systemzero.dev`.
- Read access to the real connection-engine repo at `/Users/avi/Documents/Misc/connection-engine/`.
- LLM budget for ~30 absorb calls (Groq tier for speed, OpenAI for quality fallback, Anthropic if user-provided).

## Outputs

- `modules/<id>/` for every connection-engine module that can be wrapped (one per module, not grouped).
- `catalog/modules/<id>/` catalog entries for each.
- Generated standalone module repos for every absorbed module:
  - Default owner: `avibrahms` unless `SZ_MODULE_REPO_OWNER` is set.
  - Default visibility: private unless `SZ_MODULE_REPO_VISIBILITY=public` is set.
  - Name pattern: `sz-module-<id>-ce`.
  - Each repo contains the module files, a README, `.sz-module-origin.json`, `.env.example` if needed, and no private/operator-identifying data.
- A new public GitHub repo `systemzero-dev/connection-engine-reference` containing:
  - `.sz.yaml` with the full profile.
  - `.sz/repo-profile.json` pre-seeded.
  - `README.md` explaining what it is.
  - No source code of its own — everything comes from installed SZ modules.
- `tests/e2e/reconstruct/run.sh` — boots the reference repo from scratch and asserts equivalent behavior.
- `.test-reports/phase-16.json`.
- Current-branch git checkpoint history for this phase, with no branch operations.

## The anonymization discipline (NORMATIVE)

Every absorbed module must pass this filter before it ships:

1. No literal reference to "avi", "Avi", operator email, personal phone, personal domains (except `systemzero.dev`).
2. No reference to `HOSTINGER_DOMAIN` from the source operator's `.env`.
3. No hardcoded paths like `/Users/avi/...`, `/home/avi/...`.
4. No reference to `.config/stealth-browser/...`, personal Stripe accounts, personal LinkedIn, personal Telegram chat IDs.
5. No references to specific operator-owned products (AVI_PRODUCTS__*, VIRALEPIC, etc.).
6. Private connection-engine modules (agent-dashboard private paths, profiles/avi) are REWRITTEN with generic placeholders.
7. Every env var the module requires gets a documented name + example value in the module's README.

The anonymization filter is a script (`tools/anonymize.py`) that scans every module's contents before publish; any hit blocks the module.

## Standalone repo strategy (NORMATIVE)

Standalone module repos exist to multiply the surface area for discovery, trust, demos, and future product packaging. They let each organ be promoted as its own small, understandable object while still belonging to System Zero.

The efficient version is a generated mirror model:

1. **Canonical source of truth remains here**: `modules/<id>-ce/` plus the catalog entry. Standalone repos are exported artifacts, not hand-maintained forks.
2. **Every repo is independently useful**: README explains the organ, its use case, installation command, inputs, outputs, required env vars, and a minimal smoke test.
3. **Every repo points back to System Zero**: README links to `systemzero.dev`, the catalog entry, and the reference repo.
4. **Every repo can be promoted independently**: topics, concise positioning, and examples are generated so each organ can become a landing/discovery surface later.
5. **GitHub export is soft-blocked**: if repo creation, push, naming, auth, or rate limits fail, phase 16 records the failure in `BLOCKERS.md` and `.test-reports/phase-16.json`, then continues. Catalog installability is the hard requirement; GitHub mirrors are amplification, not core protocol validity.
6. **No copy-paste maintenance**: future edits regenerate and push mirrors from the canonical module tree. Manual edits in mirror repos are overwritten unless promoted back into `modules/<id>-ce/`.

## Source module inventory (from connection-engine, survey first)

Run a one-time survey:

```bash
python3 tools/connection_engine_survey.py \
  --source /Users/avi/Documents/Misc/connection-engine \
  --out modules-inventory.json
```

This produces a JSON list of:
- Each `core/system/scripts/*.py` as a candidate (nervous-system phases, immune, subconscious, dreaming, predictive_memory, dream_router, memory_selector, skill-preselector, registry_loader, circadian-daemon, etc.).
- Each `modules/<x>/` already-modular thing (chronicle, sentinel, viralepic — viralepic is an Avi product, flagged and excluded).
- Home-templates skills (evolve, symbiosis, cohere, emerge, natural-inspiration, scrutinize, etc. — dozens).
- Heartbeat-beacon, agent-dashboard HTTP server.

Categorize each candidate:
- **keep**: reusable self-improvement, anonymizable.
- **skip**: operator-specific (viralepic, profiles/avi, AVI_PRODUCTS secrets).
- **rewrite**: rename + genericize (agent-dashboard → generic-dashboard).

The categorization is manual on first run. GPT-5.4 may propose categories via a Constrained LLM Call (`ce-inventory-classify` schema) if an LLM provider with enough context window is available; final approval is marked `INVOKE_REVIEWER`.

## Atomic steps

### Step 16.1 — Confirm current branch + survey

```bash
git branch --show-current
mkdir -p tools tests/e2e/reconstruct .test-reports
```

Verify: prints the current branch name, creates the survey scaffolding, and does not create or switch branches.

Write `tools/connection_engine_survey.py`:
```python
#!/usr/bin/env python3
"""Enumerate connection-engine candidates for absorption.

Walks the source tree, identifies files that look like modules (standalone scripts,
maintenance.yaml, or directory-shaped modules), and emits a JSON inventory for
phase 16 consumption."""
import argparse, json, pathlib, re, sys

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv"}
SKIP_NAMES = {"viralepic", "profiles"}

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
```

Run and inspect:
```bash
chmod +x tools/connection_engine_survey.py
tools/connection_engine_survey.py --source /Users/avi/Documents/Misc/connection-engine --out modules-inventory.json
jq '. | length' modules-inventory.json
```

Verify: prints a positive integer (expect 25-40).

### Step 16.2 — Anonymization filter: `tools/anonymize.py`

```python
#!/usr/bin/env python3
"""Scan a module directory and reject if operator-identifying tokens appear."""
import re, sys, pathlib

PATTERNS = [
    (re.compile(r"\b[aA]vi[- _]?[bB]elhassen\b"), "operator name"),
    (re.compile(r"/Users/avi/"), "operator home path"),
    (re.compile(r"/home/avi/"), "operator home path"),
    (re.compile(r"\bavi[a-z0-9_-]*@[a-z0-9.-]+\.[a-z]+"), "operator email"),
    (re.compile(r"\bviralepic\b", re.I), "operator product"),
    (re.compile(r"\bcomplianceiq\b", re.I), "operator product"),
    (re.compile(r"\bdebt[_-]?radar\b", re.I), "operator product"),
    (re.compile(r"\bagent[_-]?bill\b", re.I), "operator product"),
    (re.compile(r"\bbreakpoint[_-]?ai\b", re.I), "operator product"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS key"),
    (re.compile(r"sk-[A-Za-z0-9]{40,}"), "provider secret"),
    (re.compile(r"pk_live_[A-Za-z0-9]{20,}"), "stripe publishable live"),
    (re.compile(r"sk_live_[A-Za-z0-9]{20,}"), "stripe secret live"),
    (re.compile(r"whsec_[A-Za-z0-9]{20,}"), "stripe webhook"),
    (re.compile(r"heartbeat-beacon"), "personal beacon endpoint"),
    (re.compile(r"avi[a-z0-9]*\.(com|net|io|dev|app)\b", re.I), "operator domain"),
]

def scan(module_dir: pathlib.Path) -> list[tuple[pathlib.Path, str, str]]:
    hits = []
    for p in module_dir.rglob("*"):
        if not p.is_file(): continue
        try: text = p.read_text(errors="ignore")
        except Exception: continue
        for rx, label in PATTERNS:
            for m in rx.finditer(text):
                hits.append((p, label, m.group(0)[:60]))
    return hits

def main():
    if len(sys.argv) != 2:
        print("usage: anonymize.py <module-dir>"); sys.exit(2)
    d = pathlib.Path(sys.argv[1])
    hits = scan(d)
    for p, label, sample in hits:
        print(f"HIT {label}: {p.relative_to(d)} :: {sample}")
    sys.exit(1 if hits else 0)

if __name__ == "__main__":
    main()
```

### Step 16.3 — Process each `keep` candidate

For each `keep` item in `modules-inventory.json`:

1. Run `sz absorb <absolute-local-path> --feature <module-id> --id <module-id>-ce`. This uses the existing absorb workflow (phase 06) with CLC discipline; produces a staged module.
2. Run `tools/anonymize.py <staged-path>`. If it emits any HIT, stop, apply a sed fix to strip the offending token (replace with a generic placeholder), and re-run until clean.
3. Run `sz install <module-id>-ce --source <staged-path>` into a scratch repo to verify it installs and `sz doctor` passes.
4. Copy the module into `modules/<module-id>-ce/` in this repo.
5. Add a catalog entry under `catalog/modules/<module-id>-ce/`.

Automate the loop:

```bash
python3 - <<'PY'
import json, subprocess, sys, os, pathlib, shutil
repo = pathlib.Path("/Users/avi/Documents/Projects/system0-natural")
inv = json.loads((repo / "modules-inventory.json").read_text())
results = {"absorbed": [], "skipped": [], "failed": []}
scratch = pathlib.Path("/tmp/sz-reconstruct"); scratch.mkdir(exist_ok=True)
os.chdir(scratch)
subprocess.run(["sz","init","--host","generic","--no-genesis"], check=True)
for item in inv:
    if item["category"] != "keep":
        results["skipped"].append(item["id"]); continue
    mid = item["id"] + "-ce"
    src = item["path"]
    r = subprocess.run(["sz","absorb","file://"+src,"--feature",item["id"],"--id",mid,"--dry-run"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        results["failed"].append({"id":mid,"err":r.stderr[:400]}); continue
    # Anonymize; if hit, retry with manual placeholder replacement (loop manual)
    staging_line = [l for l in r.stdout.splitlines() if '"staging"' in l][0]
    staging = json.loads(r.stdout)["staging"]
    anon = subprocess.run(["python3", str(repo/"tools/anonymize.py"), staging], capture_output=True, text=True)
    if anon.returncode != 0:
        results["failed"].append({"id":mid,"anonymize":anon.stdout[:400]}); continue
    subprocess.run(["sz","install",mid,"--source",staging], check=False)
    dst = repo / "modules" / mid
    if dst.exists(): shutil.rmtree(dst)
    shutil.copytree(staging, dst)
    results["absorbed"].append(mid)
print(json.dumps(results, indent=2))
PY
```

Verify: `results.absorbed` has at least 15 entries. Remaining `failed` and `skipped` are documented in the phase report.

Each `failed` entry must have a human-readable note added to `modules-inventory.json`; a followup manual absorption may be attempted after fixing the specific blocker.

### Step 16.4 — Rebuild the catalog index

```bash
catalog/scripts/build-index.py
jq '.items | length' catalog/index.json
```

Verify: the new count is old + the number of absorbed-ce modules.

### Step 16.5 — Export standalone module repos

Create `tools/export_module_repos.py`:

```python
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
- Reference stack: https://github.com/systemzero-dev/connection-engine-reference
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
        run(["git", "config", "user.name", "systemzero-dev"], cwd=work)
        run(["git", "add", "."], cwd=work)
        run(["git", "commit", "-m", f"export {module_id} module"], cwd=work)

        exists = run(["gh", "repo", "view", full_name], check=False).returncode == 0
        if not exists:
            run(["gh", "repo", "create", full_name, f"--{VISIBILITY}", "--source", str(work), "--push"])
        else:
            run(["git", "remote", "add", "origin", f"https://github.com/{full_name}.git"], cwd=work, check=False)
            run(["git", "push", "-u", "origin", "HEAD:main", "--force"], cwd=work)
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
```

Run:

```bash
chmod +x tools/export_module_repos.py
SZ_MODULE_REPO_OWNER="${SZ_MODULE_REPO_OWNER:-avibrahms}" \
SZ_MODULE_REPO_VISIBILITY="${SZ_MODULE_REPO_VISIBILITY:-private}" \
tools/export_module_repos.py
```

Verify:

```bash
jq '[.[] | select(.status=="exported")] | length' .test-reports/phase-16-module-repos.json
jq '[.[] | select(.status=="soft_blocked")] | length' .test-reports/phase-16-module-repos.json
```

Required: every absorbed module has either `status: exported` or `status: soft_blocked` with a concrete error. At least 80% should export successfully when GitHub auth is available. Soft-blocked exports are copied into `BLOCKERS.md` with a one-line retry command.

### Step 16.6 — Create the reference repo

```bash
mkdir -p ../connection-engine-reference
cd ../connection-engine-reference
git init -q
git config user.email "ops@systemzero.dev"
git config user.name "systemzero-dev"

cat > README.md <<'MD'
# connection-engine-reference

An open-source, anonymized reconstruction of connection-engine, assembled entirely from [System Zero](https://systemzero.dev) modules.

This repo has no source code of its own. It has:
- A pre-seeded `.sz/repo-profile.json` that names ~30 modules.
- A `.sz.yaml` that pins them.
- A one-line `bootstrap.sh` that installs `sz` and runs `sz init`.

Run:

    bash bootstrap.sh

…and you get a working, autonomous, self-improving repo whose behavior approximates connection-engine's self-improvement loop. All modules are independently maintained in the [public catalog](https://github.com/systemzero-dev/catalog).
MD

cat > bootstrap.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail
command -v sz >/dev/null || curl -sSL https://systemzero.dev/i | sh
sz init --yes
sz doctor
sz list
SH
chmod +x bootstrap.sh
```

Write a `.sz.yaml` that pins every absorbed `<id>-ce` module with its default setpoints. Write a `.sz/repo-profile.json` with the reconstructed stack (generic, anonymized).

Commit and publish:
```bash
git add .
git commit -m "initial reference stack"
gh repo create systemzero-dev/connection-engine-reference --public --source . --push
```

### Step 16.7 — End-to-end validation

`tests/e2e/reconstruct/run.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
REPORT="$PWD/.test-reports/phase-16.json"
mkdir -p "$(dirname "$REPORT")"

# Fresh clone of the reference repo.
WORK=$(mktemp -d); cd "$WORK"
gh repo clone systemzero-dev/connection-engine-reference
cd connection-engine-reference
bash bootstrap.sh

# Must end up alive.
sz list | grep -Eq "heartbeat|immune|subconscious" || { echo "no core modules"; exit 1; }
sz tick --reason reconstruct-check
sz tick --reason reconstruct-check
sz bus tail --last 50 --filter "health.snapshot" | grep -q . || { echo "no snapshot"; exit 1; }

# Anonymization sweep — no HITs in the entire checkout.
python3 /Users/avi/Documents/Projects/system0-natural/tools/anonymize.py . >/tmp/anon.out 2>&1
if [ -s /tmp/anon.out ]; then
  cat /tmp/anon.out
  echo "anonymization violated"; exit 1
fi

echo '{"status":"PASSED","modules":"'$(sz list | wc -l | tr -d " ")'"}' > "$REPORT"
echo "PHASE 16 PASSED"
```

Run:
```bash
bash tests/e2e/reconstruct/run.sh
```

Verify: prints `PHASE 16 PASSED`. The reference repo boots, ticks, emits health snapshots, and passes anonymization.

### Step 16.8 — Commit

```bash
cd /Users/avi/Documents/Projects/system0-natural
git add tools/anonymize.py tools/connection_engine_survey.py tools/export_module_repos.py modules-inventory.json modules catalog tests/e2e/reconstruct .test-reports/phase-16.json .test-reports/phase-16-module-repos.json plan/phase-16-reconstruct-connection-engine
git commit -m "phase 16: reconstruct connection-engine (anonymized) via sz"
```

## Acceptance criteria

1. `modules-inventory.json` lists ≥25 candidates with categories assigned.
2. ≥15 modules absorbed into `modules/<id>-ce/` and validated against the manifest schema.
3. The anonymization filter scans every absorbed module and finds zero HITs.
4. Every absorbed module has a standalone repo export record in `.test-reports/phase-16-module-repos.json`.
5. At least 80% of absorbed modules are pushed as private standalone repos when GitHub auth is available; failures are soft-blocked with retry commands.
6. `systemzero-dev/connection-engine-reference` exists as a public repo.
7. `bash bootstrap.sh` in that repo, on a fresh machine, ends with `sz list` showing the absorbed modules running.
8. `tests/e2e/reconstruct/run.sh` ends with `PHASE 16 PASSED`.
9. The reference repo and standalone module repos contain zero references to operator identity (verified by tools/anonymize.py).

## Failure modes and recovery

| Symptom | Cause | Action |
|---|---|---|
| Absorb produces non-conformant module for a script | source script is tightly coupled to connection-engine internals | manually unwrap the specific module's dependency; OR mark it `skip` in the inventory with a reason |
| Anonymization filter keeps hitting on the same token | the filter is too aggressive OR a module legitimately uses a sensitive name | adjust the specific pattern or rename the offending identifier in the absorbed copy |
| `bootstrap.sh` fails because a module's entry needs a secret | module declared env requirements | the reference repo ships a `.env.example` listing what the user needs to provide; bootstrap.sh prints a clear message rather than failing silently |
| Reference repo does not "behave like" connection-engine | semantic gap | document the gap in the reference repo's README; iterate via PRs after launch |
| GH repo name taken | upstream conflict | use `systemzero-dev/ce-reference` and update README links |
| Standalone module repo creation fails | GitHub auth, rate limit, repo name conflict, or network failure | mark that module `soft_blocked` in `.test-reports/phase-16-module-repos.json`, append a retry command to `BLOCKERS.md`, and continue |
| Standalone repos drift from catalog modules | manual edits happened in exported mirrors | regenerate mirrors from `modules/<id>-ce/`; if a mirror edit is valuable, port it back to the canonical module before regenerating |

## Rollback

`gh repo delete systemzero-dev/connection-engine-reference --confirm`; delete generated `sz-module-*-ce` repos only if they were not intentionally kept as private discovery surfaces. Absorbed modules can be kept in the catalog independently — they are valuable even if the reference repo or mirrors are withdrawn.

## After phase 16 — the payoff

This phase is the proof that the protocol is universal. If SZ can reconstruct its own ancestor (connection-engine) from scratch via absorb + reconcile, then SZ can plausibly reconstruct any other self-improvement framework as well. The public reference repo becomes the strongest demo available: a fully working autonomous organism, visible in its entirety, assembled without any hand-coded integration.

Future phases (v0.2+) will add: automatic module quality tests, a module-author bounty system, private catalog networks for teams, and a `sz graft` command that moves modules between repos while preserving bindings.
