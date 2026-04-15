# Phase 06 — The Absorb Workflow (with Constrained LLM Call)

## Goal

Implement `sz absorb <source-url> --feature <name>`. After this phase, a developer can point S0 at any open-source repository, name a feature, and S0 produces an S0-conformant module wrapping that feature, installs it, runs the standard reconcile cycle, and the absorbed feature becomes a first-class citizen that any other module can talk to. The LLM call in this workflow obeys the **Constrained LLM Call (CLC)** discipline: templated prompt, schema-validated response, retry-on-mismatch, logged.

## The integration-entropy problem this solves

When an LLM absorbs a feature ad hoc, it modifies the receiving repo's source files and wires the feature inline. Two months later, after ten more absorptions, the wiring is a tangle and no module knows what other modules exist. S0 solves this by **constraining absorption to a single output: an S0 module manifest plus a reconcile script.** The LLM never modifies any file outside the new module's directory. All cross-module concerns are handled by the standard reconcile cycle, which runs after every absorption and gives every existing module a chance to discover and re-bind to the newcomer.

## Inputs

- Phases 00–05 complete.
- The LLM provider configured in phase 03 is reachable (or `mock` is acceptable for dry runs).
- The CLC schema `spec/v0.1.0/llm-responses/absorb-draft.schema.json` exists from phase 01.

## Outputs

- `sz/commands/absorb.py` — full implementation, replacing the phase-02 stub.
- `sz/templates/absorb_prompt.md` — the prompt template that drives the LLM (CLC).
- `sz/core/absorb.py` — orchestration logic (clone, scan, draft via CLC, validate, install).
- `tests/absorb/test_absorb_dry.py` — dry-run tests with the `mock` LLM.
- `tests/absorb/test_clc_retry.py` — verifies CLC retry behavior on this specific call.
- Branch `phase-06-absorb-workflow`.

## How absorption works (algorithm)

1. **Acquire source**: clone the URL into `~/.sz/cache/absorb/<sha>/`.
2. **Inventory**: deterministic scan of the source tree (top-level dirs, files <= 5 KB, file extensions, README excerpt, `package.json`/`pyproject.toml`/`go.mod`/`Cargo.toml` parsed). Cap at 50 KB total.
3. **CLC for the manifest draft**: invoke `sz llm invoke` with `--schema spec/v0.1.0/llm-responses/absorb-draft.schema.json` and `--template-id absorb-draft`. The runtime validates and retries.
4. **Validate the manifest** against `spec/v0.1.0/manifest.schema.json` (a second, independent check). Reject on schema failure.
5. **Path-traversal guard**: every `files_to_copy.from` must resolve under the source root; every `files_to_copy.to` must resolve under the staging module dir. Refuse otherwise.
6. **Materialize**: create `~/.sz/cache/absorb/<sha>/.staging/<module_id>/`. Copy each file. Write `module.yaml`, `entry`, `reconcile.sh`.
7. **Install**: invoke `sz install <module_id> --source <staging-path>`. The standard install path runs validation again and triggers a reconcile.
8. **Health check**: invoke `sz doctor <module_id>`; if it fails, print the LLM's notes and the doctor's stderr, and ask the user whether to roll back (`--auto-rollback` flag controls).
9. **Result**: print a one-line summary; the new module is on the bus, in the registry, and other modules' reconcile hooks have already run against it.

## Atomic steps

### Step 6.1 — Branch

```bash
git checkout main
git checkout -b phase-06-absorb-workflow
```

### Step 6.2 — Write `sz/templates/absorb_prompt.md`

Place this verbatim. The LLM is constrained to JSON output. Variables in `{{...}}` are substituted at runtime. The schema-validation feedback is appended automatically by the CLC engine on retry, NOT by this template.

```markdown
# S0 absorb prompt

You are wrapping an open-source feature as an S0 (System Zero) module. Your output must be JSON only. No prose, no markdown fences.

## Source repository inventory

URL: {{SOURCE_URL}}
Ref: {{SOURCE_REF}}

Top-level layout:
{{LAYOUT}}

Selected file contents (truncated):
{{FILES}}

## Feature requested

The user wants to absorb the feature called: **{{FEATURE_NAME}}**.

## S0 v0.1 protocol summary (NORMATIVE)

Modules talk to each other only through these interfaces, exposed as `s0 <verb>` shell commands:
- `sz bus emit <type> <json>` and `sz bus subscribe <module-id> <pattern>`
- `sz memory get/set <key>`, `sz memory append <stream> <json>`
- `sz llm invoke --prompt-file <file>`
- `sz discovery resolve <capability>`, `sz discovery providers <capability>`

A module is a directory with one `module.yaml` and at minimum an `entry` script. `provides` declares capabilities other modules can require. `requires` declares capabilities this module needs (use `optional: true` if soft).

The reconcile script reads `$SZ_REGISTRY_PATH` (a JSON file) to learn about other installed modules and re-bind. It must be idempotent and must not modify anything outside `$SZ_MODULE_DIR`.

## Output schema (the runtime validates this; do not deviate)

Output a single JSON object with these exact keys:

{
  "module_id":   "<kebab-case>",            # 3..40 chars, [a-z0-9-]
  "description": "<one line>",
  "category":    "<short tag>",
  "entry":       {"type":"python|bash|node","command":"<rel path>","args":[]},
  "triggers":    [{"on":"tick"} | {"on":"event","match":"<glob>"} | {"cron":"<5 fields>"}],
  "provides":    [{"name":"<dotted.lowercase>","address":"<events:type|memory:key|<rel path>>","description":"<one line>"}],
  "requires":    [{"name":"<dotted.lowercase>","optional":bool,"on_missing":"warn|error"} | {"providers":["llm","memory","bus","storage","schedule","discovery"]}],
  "setpoints":   {"<name>":{"default":<v>,"range":[min,max]|"enum":[...],"description":"<one line>"}},
  "files_to_copy":[{"from":"<path-in-source>","to":"<path-in-module>"}],
  "entry_script":"<full text of entry file>",
  "reconcile_script":"<full bash script content>",
  "notes":"<short text on decisions>"
}

Hard constraints (the runtime enforces):
- Every `files_to_copy.from` must reference a path in the inventory. No invented paths.
- The `entry_script` invokes or wraps the absorbed source; it must not re-implement it.
- The `reconcile_script` must:
  - Read `$SZ_REGISTRY_PATH`.
  - For each `requires.name`, query `sz discovery resolve <name>` and write the result to `$SZ_MODULE_DIR/runtime.json`.
  - Be idempotent: two consecutive runs produce the same `runtime.json`.
- Output JSON only. No fences. No surrounding text.
```

### Step 6.3 — Write `sz/core/absorb.py`

```python
"""Absorption orchestration with CLC discipline."""
from __future__ import annotations
from pathlib import Path
import hashlib, json, shutil, subprocess, tempfile
import yaml
from sz.core import paths, manifest as manifest_core
from sz.interfaces import llm

CACHE = paths.user_config_dir() / "cache" / "absorb"


def _src_hash(source: str, ref: str | None) -> str:
    h = hashlib.sha1()
    h.update(source.encode())
    h.update((ref or "HEAD").encode())
    return h.hexdigest()[:12]


def acquire(source: str, ref: str | None) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / _src_hash(source, ref)
    if dest.exists():
        return dest
    if source.startswith("git+") or source.endswith(".git") or source.startswith("https://github.com"):
        url = source[4:] if source.startswith("git+") else source
        subprocess.run(["git", "clone", "--depth", "1", url, str(dest)], check=True)
        if ref:
            subprocess.run(["git", "-C", str(dest), "checkout", ref], check=True)
    elif source.startswith("file://"):
        shutil.copytree(Path(source[len("file://"):]), dest)
    else:
        shutil.copytree(Path(source), dest)
    return dest


def inventory(src: Path, max_total_kb: int = 50) -> dict:
    layout = []
    files = []
    seen = 0
    for p in sorted(src.rglob("*")):
        if ".git" in p.parts:
            continue
        if p.is_dir():
            layout.append(str(p.relative_to(src)) + "/")
            continue
        rel = str(p.relative_to(src))
        layout.append(rel)
        if p.suffix in {".md", ".py", ".js", ".ts", ".sh", ".yaml", ".yml", ".toml", ".json"} and p.stat().st_size <= 5_000:
            content = p.read_text(errors="replace")
            files.append(f"\n--- {rel} ---\n{content}\n")
            seen += len(content)
            if seen > max_total_kb * 1024:
                break
    return {"layout": "\n".join(layout[:400]), "files": "".join(files)}


def render_prompt(template_path: Path, source: str, ref: str | None, feature: str, inv: dict) -> str:
    return (template_path.read_text()
            .replace("{{SOURCE_URL}}", source)
            .replace("{{SOURCE_REF}}", ref or "HEAD")
            .replace("{{FEATURE_NAME}}", feature)
            .replace("{{LAYOUT}}", inv["layout"])
            .replace("{{FILES}}", inv["files"]))


def materialize(src: Path, draft: dict, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": draft["module_id"], "version": "0.1.0",
        "category": draft.get("category", "absorbed"),
        "description": draft.get("description", "Absorbed feature."),
        "entry": draft["entry"],
        "triggers": draft.get("triggers", [{"on": "tick"}]),
        "provides": draft.get("provides", []),
        "requires": draft.get("requires", []),
        "setpoints": draft.get("setpoints", {}),
        "hooks": {"reconcile": "reconcile.sh"},
    }
    (target / "module.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    src_resolved = src.resolve()
    target_resolved = target.resolve()
    for spec in draft.get("files_to_copy", []):
        from_p = (src / spec["from"]).resolve()
        if not str(from_p).startswith(str(src_resolved)):
            raise ValueError(f"Refusing to copy outside source: {spec['from']}")
        to_p = (target / spec["to"]).resolve()
        if not str(to_p).startswith(str(target_resolved)):
            raise ValueError(f"Refusing to copy outside module: {spec['to']}")
        to_p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(from_p, to_p)
    entry = target / draft["entry"]["command"]
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(draft["entry_script"])
    entry.chmod(0o755)
    rec = target / "reconcile.sh"
    rec.write_text(draft["reconcile_script"])
    rec.chmod(0o755)


def absorb(source: str, feature: str, *, ref: str | None = None,
           module_id: str | None = None, dry_run: bool = False) -> dict:
    src = acquire(source, ref)
    inv = inventory(src)
    template = Path(__file__).resolve().parent.parent / "templates" / "absorb_prompt.md"
    schema_path = Path(__file__).resolve().parents[2] / "spec" / "v0.1.0" / "llm-responses" / "absorb-draft.schema.json"
    prompt = render_prompt(template, source, ref, feature, inv)

    # CLC discipline: validated + retried + logged.
    result = llm.invoke(prompt, schema_path=schema_path, template_id="absorb-draft", max_tokens=4000)
    draft = result.parsed

    if module_id:
        draft["module_id"] = module_id

    # Second-line validation against the full manifest schema.
    fake_manifest = {
        "id": draft["module_id"], "version": "0.1.0",
        "category": draft.get("category", "absorbed"),
        "description": draft.get("description", "absorbed"),
        "entry": draft["entry"],
        "triggers": draft.get("triggers", [{"on": "tick"}]),
        "provides": draft.get("provides", []),
        "requires": draft.get("requires", []),
        "setpoints": draft.get("setpoints", {}),
        "hooks": {"reconcile": "reconcile.sh"},
    }
    errs = manifest_core.validate_manifest(fake_manifest)
    if errs:
        raise ValueError(f"absorb produced invalid manifest: {errs}")

    staging = src / ".staging" / draft["module_id"]
    if staging.exists():
        shutil.rmtree(staging)
    materialize(src, draft, staging)

    if dry_run:
        return {"staging": str(staging), "draft": draft}

    subprocess.run(["sz", "install", draft["module_id"], "--source", str(staging)], check=True)
    return {"installed": draft["module_id"], "staging": str(staging)}
```

### Step 6.4 — Replace `sz/commands/absorb.py`

```python
from __future__ import annotations
import json, sys
import click
from sz.core import absorb as engine


@click.command(help="Absorb a feature from an open-source repo as an S0 module.")
@click.argument("source")
@click.option("--feature", required=True)
@click.option("--ref", default=None)
@click.option("--id", "module_id", default=None)
@click.option("--dry-run", is_flag=True)
@click.option("--auto-rollback", is_flag=True)
def cmd(source, feature, ref, module_id, dry_run, auto_rollback):
    try:
        result = engine.absorb(source, feature, ref=ref, module_id=module_id, dry_run=dry_run)
    except Exception as e:
        click.echo(f"absorb failed: {e}", err=True)
        sys.exit(1)
    click.echo(json.dumps(result, indent=2))
    if not dry_run and auto_rollback:
        import subprocess
        r = subprocess.run(["sz", "doctor", result["installed"]], capture_output=True, text=True)
        if r.returncode != 0:
            click.echo("doctor failed; rolling back", err=True)
            subprocess.run(["sz", "uninstall", result["installed"], "--confirm"], check=False)
            sys.exit(2)
```

### Step 6.5 — Tests

`tests/absorb/test_absorb_dry.py`: same shape as the sz version — a tiny source dir, a `monkeypatch` that makes the mock LLM return a hand-crafted valid draft, dry-run check that staging contains `module.yaml`, copied source file, entry script, reconcile script. Then a non-dry version installs and checks the registry.

`tests/absorb/test_clc_retry.py`: makes the mock LLM return invalid JSON twice then valid JSON; absorb completes successfully; `llm.calls` stream shows 3 attempts logged.

`tests/absorb/test_path_traversal.py`: monkeypatch produces a draft whose `files_to_copy.from` is `../../etc/passwd`; absorb must raise.

Run:
```bash
python3 -m pytest tests/absorb -q
```

### Step 6.6 — Manual real-LLM smoke (optional)

If `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` is set:
```bash
TMP=$(mktemp -d); cd "$TMP"
git init -q
sz init --host generic
sz absorb https://github.com/sindresorhus/p-limit --feature "concurrency limiter" --dry-run
```

Verify (manual): the staged `module.yaml` is well-formed; `entry_script` invokes/wraps logic from `index.js`; `provides` lists at least one capability whose name relates to concurrency.

### Step 6.7 — Commit

```bash
git add sz tests/absorb plan/phase-06-absorb-workflow
git commit -m "phase 06: absorb workflow with CLC complete"
```

## Acceptance criteria

1. `sz absorb <local-source-dir> --feature X --dry-run` returns a JSON describing the staging directory and a valid `module.yaml`.
2. Without `--dry-run`, the absorbed module installs and reconciles; `sz list` shows it.
3. The absorbed module's `reconcile.sh` is idempotent.
4. Path-traversal attempts are rejected (test must explicitly cover `../../`).
5. CLC retry test passes: invalid → invalid → valid completes in 3 attempts.
6. `pytest tests/absorb -q` passes.
7. Branch `phase-06-absorb-workflow` exists with one commit.

## Failure modes and recovery

| Symptom | Cause | Action |
|---|---|---|
| LLM emits markdown fences | provider habit | the CLC `_parse_json_envelope` strips fences before validation |
| LLM keeps failing schema | systemic prompt issue | improve `absorb_prompt.md`; never relax the schema |
| Real LLM produces a working module on a small source but fails on a large one | inventory truncated | narrow with `--ref` or pre-extract subdir before absorb |
| `entry_script` calls `node` but node missing | system dep | absorb prompt should declare `requires_host: [node]`; doctor catches |

## Rollback

`git checkout main && git branch -D phase-06-absorb-workflow`.
