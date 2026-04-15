# Phase 07 — Repo Genesis (the "becomes alive" moment)

## Goal

Implement the killer one-click feature: `sz init` (or `sz genesis` to re-run) that, with one user confirmation, transforms any repository — static or dynamic — into a living, autonomous, self-improving system. Genesis is the bridge between "I just installed a CLI" and "my repo is alive."

## What "becomes alive" means concretely

After Genesis runs successfully:

1. `.sz/repo-profile.json` exists, validates against the schema, and accurately describes the repo (purpose, language, frameworks, existing heartbeat, goals, recommended modules).
2. The right host adapter is installed (Install mode for static, Adopt mode for dynamic).
3. The 3-5 recommended modules are installed and reconciled.
4. The heartbeat is running (Owned for static, Adopted for dynamic).
5. The bus has events flowing (`tick`, `pulse.tick`, `health.snapshot`, etc.).
6. The user can run `sz list`, `sz bus tail`, `sz doctor` and see real activity.

## Spec-driven discipline

Repo Genesis makes exactly **one** Constrained LLM Call. Everything else is algorithmic:
- Inventory: deterministic file scan.
- Heartbeat detection: deterministic marker check.
- Module installation: deterministic, follows recommendation list.
- Adapter selection: deterministic from `existing_heartbeat`.

The one LLM call (`repo-genesis`) returns `repo-profile.json` validated against the schema in `spec/v0.1.0/llm-responses/repo-genesis.schema.json`. Retry up to 2 times on schema mismatch. Abort cleanly if all 3 attempts fail.

## Inputs

- Phases 00–06 complete.
- `spec/v0.1.0/llm-responses/repo-genesis.schema.json` exists.

## Outputs

- `sz/templates/repo_genesis_prompt.md` — the prompt template.
- `sz/core/genesis.py` — the orchestration module.
- `sz/commands/genesis.py` — replaces the phase-02 stub.
- `sz/commands/init.py` — extended to optionally chain Genesis (`--no-genesis` to skip).
- `sz/core/inventory.py` — algorithmic repo inventory.
- `sz/core/heartbeat_detect.py` — algorithmic existing-heartbeat detection.
- `tests/genesis/` — comprehensive tests covering both personas and CLC failure paths.
- Branch `phase-07-repo-genesis`.

## Atomic steps

### Step 7.1 — Branch

```bash
git checkout main
git checkout -b phase-07-repo-genesis
```

### Step 7.2 — Algorithmic inventory: `sz/core/inventory.py`

```python
"""Deterministic repo inventory for Genesis. No LLM."""
from __future__ import annotations
from pathlib import Path
import json

EXCLUDE_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__", ".sz", ".next", ".cache"}
LANGUAGE_MARKERS = {
    "python":     ["pyproject.toml", "setup.py", "requirements.txt", "Pipfile"],
    "javascript": ["package.json"],
    "typescript": ["tsconfig.json"],
    "go":         ["go.mod"],
    "rust":       ["Cargo.toml"],
    "ruby":       ["Gemfile"],
    "java":       ["pom.xml", "build.gradle", "build.gradle.kts"],
    "php":        ["composer.json"],
    "shell":      ["Makefile"],
}
README_FILES = ["README.md", "README.rst", "README.txt", "README"]
META_FILES = ["pyproject.toml", "package.json", "go.mod", "Cargo.toml", "Gemfile", "composer.json", "Makefile"]
MAX_README_BYTES = 5000


def _walk(root: Path) -> list[Path]:
    out = []
    for p in root.rglob("*"):
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        out.append(p)
    return out


def inventory(root: Path) -> dict:
    paths = _walk(root)
    files = [p for p in paths if p.is_file()]
    file_count = len(files)
    extensions: dict[str, int] = {}
    for f in files:
        extensions[f.suffix] = extensions.get(f.suffix, 0) + 1
    detected_languages = []
    for lang, markers in LANGUAGE_MARKERS.items():
        if any((root / m).exists() for m in markers):
            detected_languages.append(lang)
    readme_text = ""
    for r in README_FILES:
        rp = root / r
        if rp.exists() and rp.is_file():
            readme_text = rp.read_text(errors="replace")[:MAX_README_BYTES]
            break
    meta_blobs = {}
    for m in META_FILES:
        mp = root / m
        if mp.exists() and mp.is_file() and mp.stat().st_size <= 10_000:
            meta_blobs[m] = mp.read_text(errors="replace")
    return {
        "file_count": file_count,
        "extension_histogram": extensions,
        "detected_languages": detected_languages,
        "readme_text": readme_text,
        "meta_blobs": meta_blobs,
        "top_dirs": sorted([p.name for p in root.iterdir() if p.is_dir() and p.name not in EXCLUDE_DIRS])[:30],
    }
```

### Step 7.3 — Algorithmic heartbeat detection: `sz/core/heartbeat_detect.py`

```python
"""Deterministic check for an existing autonomous heartbeat. No LLM."""
from __future__ import annotations
from pathlib import Path

# Marker file/dir paths per known framework.
MARKERS = {
    "claude_code":       [".claude"],
    "cursor":            [".cursorrules", ".cursor"],
    "opencode":          [".opencode"],
    "aider":             [".aider.conf.yml"],
    "hermes":            [".hermes/config.yaml"],
    "openclaw":          [".openclaw"],
    "metaclaw":          [".metaclaw"],
    "connection_engine": ["core/system/maintenance-registry.yaml"],
}

# Adopt-mode hosts (have their own pulse).
ADOPT_HOSTS = {"hermes", "openclaw", "metaclaw", "connection_engine"}


def detect(root: Path) -> dict:
    """Return {existing_heartbeat: <name|none>, candidate_hosts: [...]}.

    Adopt-mode hosts win over Install-mode hosts when both markers exist.
    """
    found = []
    for name, markers in MARKERS.items():
        for m in markers:
            if (root / m).exists():
                found.append(name)
                break
    if not found:
        return {"existing_heartbeat": "none", "candidate_hosts": []}
    adopt_hits = [h for h in found if h in ADOPT_HOSTS]
    if adopt_hits:
        return {"existing_heartbeat": adopt_hits[0], "candidate_hosts": adopt_hits + [h for h in found if h not in ADOPT_HOSTS]}
    return {"existing_heartbeat": found[0], "candidate_hosts": found}
```

### Step 7.4 — Prompt template: `sz/templates/repo_genesis_prompt.md`

```markdown
# S0 Repo Genesis prompt

You are S0 (System Zero). You make repositories alive by understanding their purpose and recommending the first 3-5 self-improvement modules to install.

Output JSON only. No prose, no fences. The runtime validates against a strict schema and rejects non-conforming output.

## Repo inventory (deterministic; do not contradict)

- file_count: {{FILE_COUNT}}
- detected_languages: {{LANGUAGES}}
- top_dirs: {{TOP_DIRS}}
- existing_heartbeat (algorithmic): {{EXISTING_HEARTBEAT}}

README excerpt (first 5 KB):
---
{{README}}
---

Project metadata:
{{META}}

User hint (optional, may be empty):
{{HINT}}

## Available modules in the catalog

{{CATALOG_SUMMARY}}

## Output schema (the runtime validates this; do not deviate)

{
  "purpose":            "<one-line statement of what this repo is for, 1-200 chars>",
  "language":           "<one of [python, javascript, typescript, go, rust, ruby, java, kotlin, swift, php, shell, mixed, other]>",
  "frameworks":         ["<short framework names, can be empty>"],
  "existing_heartbeat": "<one of [none, claude_code, cursor, opencode, aider, hermes, openclaw, metaclaw, connection_engine, custom, unknown]>",
  "goals":              ["<1 to 5 short concrete goals the repo is working toward>"],
  "recommended_modules": [
    {"id": "<exact catalog id>", "reason": "<one short reason, 1-100 chars>"}
  ],
  "risk_flags":         ["<short flags about absorption / autonomy risks; can be empty>"]
}

Hard constraints:
- The `existing_heartbeat` you output MUST equal the algorithmic value above unless you have strong textual evidence to override it.
- `recommended_modules.id` must be from the catalog summary above.
- For Static repos (`existing_heartbeat == "none"`), always include `heartbeat` as the first recommended module.
- For Dynamic repos (`existing_heartbeat` not none), do NOT include `heartbeat` (an Adopt-mode adapter handles it).
- Recommend 3 to 5 modules total. Not more. Not fewer.
```

### Step 7.5 — Orchestration: `sz/core/genesis.py`

```python
"""Repo Genesis: the becomes-alive workflow."""
from __future__ import annotations
from pathlib import Path
import json, subprocess
import yaml
from sz.core import paths, repo_config, inventory, heartbeat_detect
from sz.core import bus as bus_core
from sz.interfaces import llm

CATALOG_SUMMARY_FALLBACK = """\
heartbeat        — periodic pulse; required for any Static repo
immune           — passive anomaly detector
subconscious     — aggregates anomalies into a colored health snapshot
dreaming         — generates novel hypotheses during quiet periods
metabolism       — rotates the bus log
endocrine        — modulates module setpoints based on aggregate health
prediction       — predicts next likely event from history
"""


def _catalog_summary() -> str:
    """Read the local catalog index if available, otherwise fallback."""
    here = Path(__file__).resolve().parents[2] / "catalog" / "index.json"
    if not here.exists():
        return CATALOG_SUMMARY_FALLBACK
    idx = json.loads(here.read_text())
    lines = []
    for it in idx["items"]:
        lines.append(f"{it['id']:18s} — {it['description']}")
    return "\n".join(lines)


def render_prompt(inv: dict, hb: dict, hint: str) -> str:
    template = (Path(__file__).resolve().parent.parent / "templates" / "repo_genesis_prompt.md").read_text()
    meta = "\n".join(f"--- {k} ---\n{v}" for k, v in inv["meta_blobs"].items())
    return (template
            .replace("{{FILE_COUNT}}", str(inv["file_count"]))
            .replace("{{LANGUAGES}}", json.dumps(inv["detected_languages"]))
            .replace("{{TOP_DIRS}}", json.dumps(inv["top_dirs"]))
            .replace("{{EXISTING_HEARTBEAT}}", hb["existing_heartbeat"])
            .replace("{{README}}", inv["readme_text"][:5000])
            .replace("{{META}}", meta[:8000])
            .replace("{{HINT}}", hint or "")
            .replace("{{CATALOG_SUMMARY}}", _catalog_summary()))


def genesis(root: Path | None = None, *, hint: str = "", auto_yes: bool = False,
            host_mode_override: str | None = None) -> dict:
    """Run Repo Genesis.

    IMPORTANT: this function does NOT read `SZ_FORCE_GENESIS_PROFILE` or any other
    test-only environment variable. Tests must use pytest's `monkeypatch` to replace
    `sz.interfaces.llm.invoke` with a function that returns a canned profile. Keeping
    the test hook out of the shipped code preserves the single responsibility of
    this function (production) and avoids any accidental test-mode leak in releases.
    See `tests/genesis/conftest.py` for the canonical test fixture.
    """
    root = root or paths.repo_root()
    inv = inventory.inventory(root)
    hb = heartbeat_detect.detect(root)
    prompt = render_prompt(inv, hb, hint)
    schema_path = Path(__file__).resolve().parents[2] / "spec" / "v0.1.0" / "llm-responses" / "repo-genesis.schema.json"
    result = llm.invoke(prompt, schema_path=schema_path, template_id="repo-genesis", max_tokens=1500)
    profile = result.parsed

    # Force the algorithmic heartbeat decision unless the LLM has very strong signal.
    # Algorithm wins by default; the LLM may add nuance via risk_flags.
    profile["existing_heartbeat"] = hb["existing_heartbeat"]

    # Persist the profile.
    paths.profile_path(root).write_text(json.dumps(profile, indent=2, sort_keys=True))

    # Decide host_mode + host adapter.
    if profile["existing_heartbeat"] == "none":
        host_mode = "install"
        host = _pick_install_host(root)
    elif profile["existing_heartbeat"] == "unknown" or profile["existing_heartbeat"] == "custom":
        host_mode = "install"
        host = "generic"
        profile["risk_flags"] = list(set((profile.get("risk_flags") or []) + ["unknown_host_using_generic"]))
    else:
        host_mode = "adopt"
        host = profile["existing_heartbeat"]

    # Show recommendations and confirm.
    summary_lines = [
        f"Purpose: {profile['purpose']}",
        f"Language: {profile['language']}",
        f"Frameworks: {', '.join(profile.get('frameworks', []) or [])}",
        f"Heartbeat: {profile['existing_heartbeat']} ({host_mode} mode via host: {host})",
        "Recommended modules:",
    ]
    for m in profile["recommended_modules"]:
        summary_lines.append(f"  - {m['id']}: {m['reason']}")
    print("\n".join(summary_lines))

    if not auto_yes:
        ans = input("\nProceed to install? [Y/n] ").strip().lower()
        if ans not in ("", "y", "yes"):
            print("aborted; .sz/repo-profile.json saved for inspection.")
            return {"profile": profile, "installed": [], "host": None}

    # Apply host adapter.
    subprocess.run(["sz", "host", "install", host], check=True,
                   env={**__import__("os").environ})

    # Install recommended modules in order.
    installed = []
    for m in profile["recommended_modules"]:
        r = subprocess.run(["sz", "install", m["id"]], capture_output=True, text=True)
        if r.returncode == 0:
            installed.append(m["id"])
        else:
            bus_core.emit(paths.bus_path(root), "sz", "module.errored",
                          {"id": m["id"], "phase": "genesis", "stderr": r.stderr[:500]})

    # Start (or attach to) heartbeat.
    if host_mode == "install":
        subprocess.run(["sz", "start", "--interval", "300"], check=False)
    # Adopt mode: nothing to start; the host's daemon already pulses.

    bus_core.emit(paths.bus_path(root), "sz", "repo.genesis.completed",
                  {"profile": profile, "installed": installed, "host": host, "host_mode": host_mode})

    print(f"\nRepo is alive. Heartbeat: {host_mode}. Modules installed: {', '.join(installed)}.")
    print("Try: sz list, sz doctor, sz bus tail.")
    return {"profile": profile, "installed": installed, "host": host, "host_mode": host_mode}


def _pick_install_host(root: Path) -> str:
    # If there's a Claude/Cursor/OpenCode/Aider marker, prefer that adapter.
    for name in ["claude_code", "cursor", "opencode", "aider"]:
        markers = {"claude_code": [".claude"], "cursor": [".cursorrules", ".cursor"],
                   "opencode": [".opencode"], "aider": [".aider.conf.yml"]}
        if any((root / m).exists() for m in markers[name]):
            return name
    return "generic"
```

### Step 7.6 — `sz/commands/genesis.py`

```python
import json, click
from sz.core import genesis as engine

@click.command(help="Make this repo alive (Repo Genesis).")
@click.option("--hint", default="", help="Optional one-line hint about repo purpose.")
@click.option("--yes", "auto_yes", is_flag=True, help="Skip confirmation.")
def cmd(hint, auto_yes):
    result = engine.genesis(hint=hint, auto_yes=auto_yes)
    click.echo(json.dumps({k: v for k, v in result.items() if k != "profile"}, indent=2))
```

### Step 7.7 — Wire `sz init` to optionally chain Genesis

In `sz/commands/init.py`, add `--no-genesis` flag (default False). After init succeeds AND the bus has been initialized AND `--no-genesis` was not passed:

```python
if not no_genesis:
    if not auto_yes:
        click.echo("Run Repo Genesis now? It will detect what this repo does and recommend modules.")
        ans = click.prompt("[Y/n]", default="Y")
        if ans.lower() not in ("y", "yes"): return
    from sz.core import genesis as engine
    engine.genesis(root, auto_yes=auto_yes)
```

### Step 7.8 — Tests

All genesis tests use a shared test fixture that replaces `sz.interfaces.llm.invoke` with a canned function. The fixture lives in `tests/genesis/conftest.py` and is never imported by any shipping code.

`tests/genesis/conftest.py`:
```python
"""Test-only: inject a canned LLM profile into Repo Genesis.

This file is under `tests/` and is never packaged or distributed. The shipping
code in `sz/core/genesis.py` has no awareness of this fixture. Any phase test
that needs a deterministic profile must import `force_profile` from here.
"""
import json
from dataclasses import dataclass
import pytest


@dataclass
class _Result:
    text: str
    parsed: dict
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = "mock:canned"


@pytest.fixture
def force_profile(monkeypatch):
    """Usage: force_profile({"purpose": "...", ...}) inside a test."""
    def _apply(profile: dict):
        from sz.interfaces import llm
        def fake_invoke(prompt, *, schema_path=None, template_id=None, model=None, max_tokens=1024):
            return _Result(text=json.dumps(profile), parsed=profile)
        monkeypatch.setattr(llm, "invoke", fake_invoke)
    return _apply
```

`tests/genesis/test_inventory.py`: a fixture repo with known files; assert detected_languages, file_count, readme excerpt, meta blobs.

`tests/genesis/test_heartbeat_detect.py`: parametrize over fixtures with each possible marker; assert detected name.

`tests/genesis/test_genesis_static.py`:
- Setup: tmp Python project (just a `pyproject.toml`, README, single `.py`).
- Use `force_profile({...})` with `recommended_modules = ["heartbeat","immune","subconscious"]`.
- Run `sz genesis --yes`.
- Assert: `.sz/repo-profile.json` exists and validates; the three modules are installed; `.sz.yaml.host_mode == "install"`; bus has `repo.genesis.completed`.

`tests/genesis/test_genesis_dynamic.py`:
- Setup: tmp repo with a planted `.hermes/config.yaml`.
- `force_profile({...})` with `existing_heartbeat="hermes"` and recommendations excluding `heartbeat`.
- Run `sz genesis --yes`.
- Assert: `.sz.yaml.host_mode == "adopt"`, `.sz.yaml.host == "hermes"`. The recommended modules are installed. The Hermes config now contains `sz tick` in its `on_tick` hooks.

`tests/genesis/test_genesis_merge.py`:
- Setup: same as dynamic.
- Run `sz init --host-mode merge --yes`.
- Assert: `.sz.yaml.host_mode == "merge"`; the Hermes config has the hook AND a cron line was installed; `sz/memory/last_tick_ts` deduplication correctly silences duplicates fired within 30s.

`tests/genesis/test_clc_failure.py`:
- Replace `llm.invoke` with a function that raises `CLCFailure` on every call.
- Run `sz genesis --yes`.
- Assert: process exits with non-zero; `.sz/repo-profile.json` does NOT exist; bus has `llm.call.failed`.

`tests/genesis/test_invalid_module_id.py`:
- Use `force_profile` with a `recommended_modules.id` not in the catalog.
- Genesis still proceeds; the bad install fires `module.errored`; profile is preserved with the bad id; user can rerun.

Run:
```bash
python3 -m pytest tests/genesis -q
```

### Step 7.8b — Test-only helpers under `tests/helpers/`

The phase-12 and phase-13 drivers need a way to force a canned profile from a shell script. That cannot be done via pytest monkeypatch alone; we need a standalone script.

The helpers are **tests/-only** — they never ship and are never referenced by `sz/` code.

`tests/helpers/run_genesis_with_profile.py`:
```python
#!/usr/bin/env python3
"""Run sz.core.genesis.genesis() with a canned LLM profile, in-process.

Usage:
  run_genesis_with_profile.py --profile '<json>'

This replaces sz.interfaces.llm.invoke with a function that returns the profile
directly, then calls genesis() and writes the profile to .sz/repo-profile.json.
"""
import argparse, json, sys
from types import SimpleNamespace


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    a = ap.parse_args()
    profile = json.loads(a.profile)
    from sz.interfaces import llm
    def fake_invoke(prompt, *, schema_path=None, template_id=None, model=None, max_tokens=1024):
        return SimpleNamespace(text=json.dumps(profile), parsed=profile,
                               tokens_in=0, tokens_out=0, model="mock:canned")
    llm.invoke = fake_invoke  # monkeypatch for this process
    from sz.core import genesis as engine
    engine.genesis(auto_yes=True)


if __name__ == "__main__":
    main()
```

`tests/helpers/absorb_with_canned.py`:
```python
#!/usr/bin/env python3
"""Absorb a local source using a canned draft JSON matched by substring.

Usage:
  absorb_with_canned.py <source-dir> <module-id>

Expects env SZ_ABSORB_CANNED pointing to a directory of canned JSON files
named matching common source repo names (p-limit.json, changed-files.json, llm.json).
"""
import json, os, pathlib, shutil, subprocess, sys, tempfile


def main():
    if len(sys.argv) != 3: print(__doc__); sys.exit(2)
    src, module_id = pathlib.Path(sys.argv[1]), sys.argv[2]
    canned = pathlib.Path(os.environ["SZ_ABSORB_CANNED"])
    if "p-limit" in str(src):        draft = json.loads((canned / "p-limit.json").read_text())
    elif "changed-files" in str(src): draft = json.loads((canned / "changed-files.json").read_text())
    elif "/llm" in str(src):         draft = json.loads((canned / "llm.json").read_text())
    else: print("no canned match"); sys.exit(2)
    draft["module_id"] = module_id
    import yaml
    staging = pathlib.Path(tempfile.mkdtemp(prefix="sz-absorb-")) / module_id
    staging.mkdir(parents=True)
    manifest = {
      "id": module_id, "version": "0.1.0",
      "category": draft.get("category","absorbed"),
      "description": draft.get("description",""),
      "entry": draft["entry"], "triggers": draft.get("triggers",[{"on":"tick"}]),
      "provides": draft.get("provides",[]), "requires": draft.get("requires",[]),
      "setpoints": draft.get("setpoints",{}),
      "hooks": {"reconcile":"reconcile.sh"},
    }
    (staging/"module.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    for s in draft.get("files_to_copy",[]):
        src_p = (src / s["from"]).resolve()
        dst_p = (staging / s["to"]).resolve()
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        if src_p.exists(): shutil.copy2(src_p, dst_p)
    e = staging / draft["entry"]["command"]
    e.parent.mkdir(parents=True, exist_ok=True)
    e.write_text(draft["entry_script"]); e.chmod(0o755)
    r = staging / "reconcile.sh"
    r.write_text(draft["reconcile_script"]); r.chmod(0o755)
    subprocess.run(["sz","install",module_id,"--source",str(staging)], check=True)


if __name__ == "__main__":
    main()
```

Both helpers live under `tests/helpers/`. They are **never** imported by `sz/` code and **never** packaged into the wheel (`pyproject.toml`'s `packages.find.include = ["sz*"]` excludes `tests`).

### Step 7.9 — Manual end-to-end (real LLM, optional)

Action:
```bash
TMP=$(mktemp -d); cd "$TMP"
mkdir -p src
cat > pyproject.toml <<'TOML'
[project]
name = "weather-bot"
version = "0.1.0"
TOML
cat > README.md <<'MD'
# weather-bot
A small bot that fetches weather and posts to Slack daily.
MD
echo "import requests" > src/main.py
git init -q && git add -A && git commit -qm init

sz init --host generic --no-genesis
sz genesis --hint "I want this to run weather posts daily and recover from API failures"
sz list
sz bus tail --last 30
```

Verify (manual): the LLM produces a sensible profile (purpose mentions weather/Slack), recommends `heartbeat`, `immune`, plus 1-2 others; modules install; bus shows `repo.genesis.completed`.

### Step 7.10 — Commit

```bash
git add sz tests/genesis plan/phase-07-repo-genesis
git commit -m "phase 07: repo genesis (becomes-alive) complete"
```

## Acceptance criteria

1. `sz genesis --yes` on a tmp Static repo creates a valid profile, installs recommended modules, starts the Owned heartbeat, emits `repo.genesis.completed`.
2. `sz genesis --yes` on a tmp Dynamic repo (with planted `.hermes/config.yaml`) sets `host_mode: adopt`, installs Adopt adapter, recommended modules don't include `heartbeat`, framework's hook config now contains `sz tick`.
3. CLC failure on Genesis aborts cleanly with `llm.call.failed` and no partial state.
4. Path-invariants hold: nothing outside `.sz/`, `.sz.yaml`, the host adapter's marker block, and the framework's config (Adopt mode) is touched.
5. `pytest tests/genesis -q` passes.
6. Branch `phase-07-repo-genesis` exists with one commit.

## Failure modes and recovery

| Symptom | Cause | Action |
|---|---|---|
| LLM picks a module not in the catalog | catalog drift or hallucination | install attempt fails, `module.errored`; user can rerun with `--hint` to nudge |
| LLM disagrees with algorithmic heartbeat detection | LLM hallucinates | code overrides with `hb["existing_heartbeat"]` always |
| User cancels at confirmation | by design | profile is saved; user can `sz install <module>` manually later |
| `sz host install <X>` fails inside Genesis | adapter prerequisite missing | bus emits error; remaining modules still install; user re-runs `sz host install <X>` after fixing |
| `sz install` sequence fails midway | network or catalog issue | partial install is recorded; user runs `sz genesis` again — idempotent |

## Rollback

`git checkout main && git branch -D phase-07-repo-genesis`.
