# Phase 14 — End-to-end Test of Absorbing Open-Source Features

## Goal

Prove the **integration-entropy fix** end-to-end. A user takes an S0-equipped repo, absorbs three real features from three real GitHub repos, one at a time, with at least one absorption happening *after* the modules have been talking for a while, and the protocol must:

1. Wrap each absorbed feature as an S0-conformant module.
2. Run the standard reconcile cycle.
3. Make every previously installed module aware of the newcomer.
4. Verify the absorbed feature actually does its job (not just installs).
5. Verify the previously-installed modules visibly react to the absorbed feature's events / vice versa.

This is the third hard checkpoint and the most important: if this passes, S0's central thesis is proven.

## Source repositories under test

Three deliberate choices, each a different shape:

1. **`sindresorhus/p-limit`** — JavaScript concurrency limiter. Absorbed feature: `concurrency-limiter`.
2. **`tj-actions/changed-files`** — git-changed-files detector (or a self-contained shell equivalent). Absorbed feature: `changed-file-detector`.
3. **`simonw/llm`** — Python CLI wrapping multiple LLM providers. Absorbed feature: `llm-provider-bridge`.

If any source repo is unreachable, substitute with a pinned local fixture under `~/.sz/cache/test-fixtures/absorb/`.

## Functional checks per absorption

| Absorbed feature | Functional check |
|---|---|
| `concurrency-limiter` | Given 10 simulated tasks, the limiter caps concurrency at the configured value (peak in-flight ≤ N). |
| `changed-file-detector` | Given a fresh commit changing 2 files, the module emits a `changed.files` event whose payload lists exactly those 2 files. |
| `llm-provider-bridge` | Given an `ask.llm` event with a prompt, the module returns a non-empty string and emits `llm.invoked`. |

## Reaction checks

After each absorption, at least one of `subconscious / metabolism / heartbeat` must visibly respond. Subconscious incorporates new anomaly events; metabolism rotates the bus when the new module pushes it past the size threshold; heartbeat continues without disruption.

## Inputs

- Phases 00–13 complete.
- An LLM provider (real or `mock`). For deterministic CI this phase uses **canned absorb responses** the mock provider returns for the three known sources.

## Outputs

- `tests/e2e/absorb/canned/{p-limit,changed-files,llm}.json` — canned LLM responses.
- `tests/e2e/absorb/run.sh` — the driver.
- `tests/e2e/absorb/test_absorb_e2e.py` — pytest wrapper.
- `tests/e2e/absorb/conftest.py` — stub fixture.
- `.test-reports/phase-14.json`.
- Branch `phase-14-test-absorb-os-feature`.

## Atomic steps

### Step 14.1 — Branch + dirs

```bash
git checkout main
git checkout -b phase-14-test-absorb-os-feature
mkdir -p tests/e2e/absorb/canned .test-reports
```

### Step 14.2 — Pre-cache the source repos

```bash
CACHE="$HOME/.sz/cache/test-fixtures/absorb"
mkdir -p "$CACHE"
[ -d "$CACHE/p-limit" ]       || git clone --depth 1 https://github.com/sindresorhus/p-limit       "$CACHE/p-limit"
[ -d "$CACHE/changed-files" ] || git clone --depth 1 https://github.com/tj-actions/changed-files   "$CACHE/changed-files"
[ -d "$CACHE/llm" ]           || git clone --depth 1 https://github.com/simonw/llm                  "$CACHE/llm"
```

Verify: all three exist.

### Step 14.3 — Canned LLM responses

`tests/e2e/absorb/canned/p-limit.json`:
```json
{
  "module_id": "concurrency-limiter",
  "description": "Concurrency limiter (port of p-limit).",
  "category": "util",
  "entry": {"type": "node", "command": "main.js"},
  "triggers": [{"on": "tick"}],
  "provides": [{"name": "concurrency.limiter", "address": "scripts/p-limit.js", "description": "Limit concurrent function invocations."}],
  "requires": [],
  "setpoints": {"max_concurrent": {"default": 4, "range": [1, 64], "description": "Max simultaneous tasks."}},
  "files_to_copy": [{"from": "index.js", "to": "scripts/p-limit.js"}],
  "entry_script": "#!/usr/bin/env node\nconst pLimit = require('./scripts/p-limit.js');\nconst max = parseInt(process.env.SZ_SETPOINT_max_concurrent || '4', 10);\nconst limit = pLimit(max);\nlet inflight = 0, peak = 0;\nconst tasks = Array.from({length: 10}, () => limit(async () => {\n  inflight++; peak = Math.max(peak, inflight);\n  await new Promise(r => setTimeout(r, 10));\n  inflight--;\n}));\nPromise.all(tasks).then(() => {\n  const { execSync } = require('child_process');\n  execSync(`sz bus emit limiter.metric '{\"peak\":${peak},\"max\":${max}}'`);\n});\n",
  "reconcile_script": "#!/usr/bin/env bash\nset -euo pipefail\necho '{}' > \"$SZ_MODULE_DIR/runtime.json\"\n",
  "notes": "Wraps p-limit's index.js; exercises with 10 fake tasks per tick."
}
```

`tests/e2e/absorb/canned/changed-files.json`:
```json
{
  "module_id": "changed-file-detector",
  "description": "Detect files changed in HEAD relative to HEAD~1.",
  "category": "util",
  "entry": {"type": "bash", "command": "main.sh"},
  "triggers": [{"on": "event", "match": "host.commit.made"}],
  "provides": [{"name": "changed.files", "address": "events:changed.files", "description": "List of files changed in latest commit."}],
  "requires": [],
  "setpoints": {},
  "files_to_copy": [],
  "entry_script": "#!/usr/bin/env bash\nset -euo pipefail\nfiles=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || true)\njson=$(echo \"$files\" | jq -R -s -c 'split(\"\\n\")|map(select(length>0))')\ns0 bus emit changed.files \"{\\\"files\\\": $json}\"\n",
  "reconcile_script": "#!/usr/bin/env bash\nset -euo pipefail\necho '{}' > \"$SZ_MODULE_DIR/runtime.json\"\n",
  "notes": "Self-contained shell; uses no source files."
}
```

`tests/e2e/absorb/canned/llm.json`:
```json
{
  "module_id": "llm-provider-bridge",
  "description": "Bridge ask.llm events into the configured S0 LLM provider.",
  "category": "cognition",
  "entry": {"type": "bash", "command": "main.sh"},
  "triggers": [{"on": "event", "match": "ask.llm"}],
  "provides": [{"name": "llm.bridge", "address": "events:llm.invoked", "description": "Receives ask.llm; emits llm.invoked."}],
  "requires": [{"providers": ["bus", "llm"]}],
  "setpoints": {"model": {"default": "gpt-4o-mini", "enum": ["gpt-4o-mini", "claude-3-haiku"], "description": "Model id."}},
  "files_to_copy": [],
  "entry_script": "#!/usr/bin/env bash\nset -euo pipefail\nlast=$(sz bus subscribe llm-bridge 'ask.llm' | tail -n1)\n[ -z \"$last\" ] && exit 0\nprompt=$(echo \"$last\" | jq -r '.payload.prompt')\nresp=$(sz llm invoke --prompt \"$prompt\" --max-tokens 200)\ns0 bus emit llm.invoked \"$resp\"\n",
  "reconcile_script": "#!/usr/bin/env bash\nset -euo pipefail\necho '{}' > \"$SZ_MODULE_DIR/runtime.json\"\n",
  "notes": "Bridges to S0's own llm interface."
}
```

### Step 14.4 — Test fixture for canned absorb

`tests/e2e/absorb/conftest.py`:
```python
"""Pytest fixture: monkeypatch the mock LLM to return canned absorb drafts."""
import json
from pathlib import Path
import pytest

CANNED = Path(__file__).parent / "canned"


@pytest.fixture
def stub_absorb_llm(monkeypatch):
    from sz.interfaces.llm_providers import mock as mod
    from sz.interfaces.llm import LLMResult

    def fake_call(prompt, *, model=None, max_tokens=1024):
        if "p-limit" in prompt:
            data = (CANNED / "p-limit.json").read_text()
        elif "changed-files" in prompt:
            data = (CANNED / "changed-files.json").read_text()
        elif "simonw/llm" in prompt or "/llm/" in prompt:
            data = (CANNED / "llm.json").read_text()
        else:
            data = json.dumps({"error": "no_canned_match"})
        return LLMResult(text=data, parsed=None, tokens_in=10, tokens_out=300, model="mock:canned")

    monkeypatch.setattr(mod, "call", fake_call)
    yield
```

### Step 14.5 — Driver script

`tests/e2e/absorb/run.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
REPORT="$PWD/.test-reports/phase-14.json"
mkdir -p "$(dirname "$REPORT")"
results='[]'
record() { results=$(echo "$results" | jq --arg n "$1" --arg s "$2" --arg d "$3" '. + [{name:$n,status:$s,detail:$d}]'); }

MOD=/Users/avi/Documents/Projects/system0-natural/modules
CACHE="$HOME/.sz/cache/test-fixtures/absorb"
WORK=$(mktemp -d); cd "$WORK"
git init -q; git config user.email "t@t"; git config user.name "t"
echo init > README.md; git add -A; git commit -qm "init"

# Init in adopt-skip mode (just for the test; real users do `sz init`).
sz init --host generic --no-genesis
for m in heartbeat immune subconscious metabolism; do sz install "$m" --source "$MOD/$m"; done

# Use canned mock for absorb.
export SZ_LLM_PROVIDER=mock
export SZ_ABSORB_CANNED=$(realpath /Users/avi/Documents/Projects/system0-natural/tests/e2e/absorb/canned)

absorb_local() {
  local src="$1" feature="$2"
  python3 - <<PY > .draft.json
import json, os, pathlib
src = "$src"
canned = pathlib.Path(os.environ["SZ_ABSORB_CANNED"])
if "p-limit" in src:        f = canned / "p-limit.json"
elif "changed-files" in src: f = canned / "changed-files.json"
elif "/llm" in src:         f = canned / "llm.json"
else: print('{"error":"no_match"}'); raise SystemExit(2)
print(f.read_text())
PY
  module_id=$(jq -r '.module_id' .draft.json)
  staging="$WORK/.staging-$module_id"
  rm -rf "$staging"; mkdir -p "$staging"
  python3 - <<PY
import json, pathlib, shutil, yaml
draft = json.load(open(".draft.json"))
src = pathlib.Path("$src")
target = pathlib.Path("$staging")
manifest = {
  "id": draft["module_id"], "version": "0.1.0",
  "category": draft.get("category","absorbed"),
  "description": draft.get("description",""),
  "entry": draft["entry"], "triggers": draft.get("triggers",[{"on":"tick"}]),
  "provides": draft.get("provides",[]), "requires": draft.get("requires",[]),
  "setpoints": draft.get("setpoints",{}),
  "hooks": {"reconcile":"reconcile.sh"},
}
(target/"module.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
for s in draft.get("files_to_copy",[]):
    src_p = (src / s["from"]).resolve()
    dst_p = (target / s["to"]).resolve()
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    if src_p.exists(): shutil.copy2(src_p, dst_p)
e = target / draft["entry"]["command"]
e.parent.mkdir(parents=True, exist_ok=True)
e.write_text(draft["entry_script"]); e.chmod(0o755)
r = target / "reconcile.sh"
r.write_text(draft["reconcile_script"]); r.chmod(0o755)
PY
  sz install "$module_id" --source "$staging"
}

# Absorption 1: p-limit.
absorb_local "$CACHE/p-limit" "concurrency limiter"
sz tick --reason post-absorb-1
peak=$(sz bus tail --last 50 --filter limiter.metric | tail -n1 | jq -r '.payload.peak // 99')
[ "$peak" -le 4 ] && record "absorb1: limiter caps at 4" pass "peak=$peak" || record "absorb1: limiter caps at 4" fail "peak=$peak"

# Absorption 2: changed-files. Make a commit, fire the event, verify the payload.
absorb_local "$CACHE/changed-files" "changed file detector"
echo x > a.txt; echo y > b.txt; git add -A; git commit -qm "two"
sz bus emit host.commit.made "$(jq -nc --arg sha "$(git rev-parse HEAD)" '{sha:$sha}')"
sz tick --reason post-absorb-2
sleep 1
files=$(sz bus tail --last 50 --filter changed.files | tail -n1 | jq -r '.payload.files | sort | join(",")')
[ "$files" = "a.txt,b.txt" ] && record "absorb2: changed.files exact match" pass "$files" || record "absorb2: changed.files exact match" fail "$files"

# Absorption 3: llm-bridge. Ask, expect a response.
absorb_local "$CACHE/llm" "llm provider bridge"
sz bus emit ask.llm '{"prompt":"hi"}'
sz tick --reason post-absorb-3
got=$(sz bus tail --last 50 --filter llm.invoked | tail -n1 | jq -r '.payload.text // empty')
[ -n "$got" ] && record "absorb3: llm bridge responds" pass "" || record "absorb3: llm bridge responds" fail ""

# Cross-module reaction: subconscious snapshot exists.
sz memory get subconscious.snapshot | jq . > /dev/null && record "cross: subconscious snapshot well-formed" pass "" || record "cross: subconscious snapshot well-formed" fail ""

# Reconcile idempotent across all 3 absorptions.
sz reconcile --reason check-1
A=$(jq 'del(.generated_at)' .sz/registry.json | sha256sum | awk '{print $1}')
sz reconcile --reason check-2
B=$(jq 'del(.generated_at)' .sz/registry.json | sha256sum | awk '{print $1}')
[ "$A" = "$B" ] && record "absorb: reconcile idempotent" pass "$A" || record "absorb: reconcile idempotent" fail ""

# All required bindings satisfied (no errors).
unsat=$(jq '.unsatisfied | length' .sz/registry.json)
[ "$unsat" = "0" ] && record "absorb: zero unsatisfied" pass "$unsat" || record "absorb: zero unsatisfied" fail "$unsat"

echo "$results" | jq . > "$REPORT"
FAILED=$(jq '[.[] | select(.status==\"fail\")] | length' "$REPORT")
[ "$FAILED" -eq 0 ] || { echo "PHASE 14 FAILED ($FAILED)"; exit 1; }
echo "ABSORB E2E PASSED"
```

`chmod +x tests/e2e/absorb/run.sh`.

### Step 14.6 — Pytest wrapper

`tests/e2e/absorb/test_absorb_e2e.py`:
```python
import os, json, shutil, subprocess
from pathlib import Path
import pytest

HERE = Path(__file__).resolve().parents[3]
CACHE = Path.home() / ".sz" / "cache" / "test-fixtures" / "absorb"


@pytest.mark.skipif(shutil.which("sz") is None, reason="s0 missing")
@pytest.mark.skipif(not (CACHE / "p-limit").exists(), reason="p-limit missing")
def test_absorb_three_features(tmp_path, stub_absorb_llm):
    cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        subprocess.run(["git", "init", "-q"], check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], check=True)
        subprocess.run(["git", "config", "user.name",  "t"], check=True)
        subprocess.run(["sz", "init", "--host", "generic", "--no-genesis"], check=True)
        for m in ["heartbeat","immune","subconscious","metabolism"]:
            subprocess.run(["sz", "install", m, "--source", str(HERE/"modules"/m)], check=True)
        for src in [CACHE/"p-limit", CACHE/"changed-files", CACHE/"llm"]:
            r = subprocess.run(["sz","absorb",str(src),"--feature","auto"], capture_output=True, text=True)
            assert r.returncode == 0, r.stderr
        reg = json.loads((tmp_path/".sz"/"registry.json").read_text())
        assert {"concurrency-limiter","changed-file-detector","llm-provider-bridge"}.issubset(set(reg["modules"]))
        subprocess.run(["sz","reconcile"], check=True)
        a = json.loads((tmp_path/".sz"/"registry.json").read_text()); a.pop("generated_at",None)
        subprocess.run(["sz","reconcile"], check=True)
        b = json.loads((tmp_path/".sz"/"registry.json").read_text()); b.pop("generated_at",None)
        assert a == b
    finally:
        os.chdir(cwd)
```

### Step 14.7 — Run

```bash
bash tests/e2e/absorb/run.sh
python3 -m pytest tests/e2e/absorb -q
```

Verify: script ends with `ABSORB E2E PASSED`; pytest is green.

### Step 14.8 — Optional: real-LLM verification

If `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` is set, run the same scenario with the real LLM. Capture output to `.test-reports/phase-14-real-llm.json`. Discrepancies between real and canned outputs do not fail the phase but are recorded.

### Step 14.9 — Commit

```bash
git add tests/e2e/absorb .test-reports/phase-14.json plan/phase-14-test-absorb-os-feature
git commit -m "phase 14: absorb open-source features end-to-end test passing"
```

## Acceptance criteria

1. `bash tests/e2e/absorb/run.sh` ends with `ABSORB E2E PASSED`.
2. After three absorptions, registry contains `concurrency-limiter`, `changed-file-detector`, `llm-provider-bridge`.
3. Functional behavior of each absorbed feature is verified by bus payload checks.
4. `sz reconcile` is byte-identical (modulo `generated_at`) across two runs after the third absorption.
5. `subconscious.snapshot` is well-formed and reflects the increased event volume.
6. Pytest is green.

## Failure modes and recovery

| Symptom | Cause | Action |
|---|---|---|
| Limiter peak exceeds max | tasks finish too fast / race | the canned `setTimeout(10)` should suffice; if a slow CI box races, raise count |
| `changed.files` includes more than `a.txt,b.txt` | extra commits between HEAD and HEAD~1 | the test ensures isolation by committing twice (`init` then `two`) |
| `llm.invoked.text` empty with mock | mock returned echo only | acceptable: any non-empty string passes |
| Reconcile drifts | a reconcile.sh writes a timestamp | the canned scripts use `echo '{}'`; never let a draft introduce non-determinism |

## Rollback

`git checkout main && git branch -D phase-14-test-absorb-os-feature`.
