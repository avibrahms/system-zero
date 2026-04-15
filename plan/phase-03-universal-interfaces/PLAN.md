# Phase 03 — Implement the seven universal interfaces

## Goal

Replace the stubs from phase 02 with working implementations of the seven sockets every module plugs into: `memory`, `bus`, `llm`, `storage`, `schedule`, `discovery`, `lifecycle`. Each is exposed as both a CLI sub-command (so any module language can use it via shell) and a Python helper (so Python modules and S0 internals can use it directly). The `llm` interface implements the **Constrained LLM Call** discipline: `sz llm invoke --schema <path>` validates and retries.

## Inputs

- Phases 00–02 complete.
- The CLI groups exist as stubs.

## Outputs

- `sz/interfaces/{memory,bus,llm,storage,schedule,discovery,lifecycle}.py`.
- `sz/interfaces/llm_providers/{anthropic,openai,mock}.py`.
- Replaced `sz/commands/{memory,bus,llm,schedule,discovery}.py` with full implementations.
- `tests/interfaces/test_*.py` for each interface, including a CLC validation/retry test.
- Current-branch git checkpoint history for this phase, with no branch operations.

## Atomic steps

### Step 3.1 — Confirm current branch and stay on it

```bash
git branch --show-current
```

Verify: prints the current branch name; do not create, switch, rename, or delete any branch during this phase.


### Step 3.2 — `sz/interfaces/bus.py`

Implements `emit`, `tail`, `subscribe`, with per-module cursors stored at `.sz/memory/cursors/<module>.json`. Append-only writer with `os.fsync`. Subscribers advance cursors deterministically. Pattern matching via `fnmatch`.

### Step 3.3 — `sz/interfaces/memory.py`

Implements `get/set/append/tail/search`. KV stored at `.sz/memory/kv.json` with atomic `tmp.replace(p)`. Streams under `.sz/memory/streams/<name>.jsonl`. `search` is a stub returning `[]` unless a vector provider is registered (deferred to v0.2).

### Step 3.4 — `sz/interfaces/llm.py` with CLC discipline

Pseudocode:

```python
def invoke(prompt: str, *, model=None, max_tokens=1024, schema_path: Path | None = None,
           template_id: str | None = None) -> LLMResult:
    if schema_path is None:
        # Ungated invocation; only allowed via CLI without --schema.
        return _call_provider(prompt, model=model, max_tokens=max_tokens)
    schema = json.loads(schema_path.read_text())
    validator = Draft202012Validator(schema)
    feedback = ""
    last_errs = []
    for attempt in range(3):
        text = _call_provider(prompt + feedback, model=model, max_tokens=max_tokens).text
        try:
            data = _parse_json_envelope(text)
        except Exception as e:
            last_errs = [f"not JSON: {e}"]
        else:
            errs = list(validator.iter_errors(data))
            if not errs:
                _log_call(template_id, text, attempts=attempt+1, validation_status="ok")
                return LLMResult(text=text, parsed=data, ...)
            last_errs = [f"{list(e.absolute_path)}: {e.message}" for e in errs]
        feedback = "\n\n[VALIDATION_ERROR] retry " + str(attempt+2) + ":\n" + "\n".join(last_errs)
    _log_call(template_id, text, attempts=3, validation_status="failed")
    raise CLCFailure(last_errs)
```

`_log_call` appends to `.sz/memory/streams/llm.calls.jsonl`.

### Step 3.5 — Provider files

Three providers in `sz/interfaces/llm_providers/`: `anthropic.py`, `openai.py`, `mock.py`. Identical to the sz scaffolds (urllib-only, no SDK), with provider selection via env `SZ_LLM_PROVIDER` falling back to `~/.sz/config.yaml`, then to whichever API key is present, then to `mock`.

### Step 3.6 — `sz/interfaces/storage.py`

`private(root, mod_id)` returns `.sz/<id>/`; `shared(root, ns)` returns `.sz/shared/<ns>/`.

### Step 3.7 — `sz/interfaces/schedule.py`

5-field cron + special tokens (`@tick`, `@hourly`, `@daily`, `@weekly`). Pure Python, UTC-anchored.

### Step 3.8 — `sz/interfaces/discovery.py`

Reads `.sz/registry.json`. Methods: `list_modules`, `providers`, `requirers`, `resolve`, `health`, `profile` (the last reads `.sz/repo-profile.json`).

### Step 3.9 — `sz/interfaces/lifecycle.py`

`run_hook(root, mod_id, hook_name, env_extra=None)`. Subprocess isolation. Env always carries `SZ_REPO_ROOT`, `SZ_MODULE_DIR`, `SZ_MODULE_ID`, `SZ_BUS_PATH`, `SZ_MEMORY_DIR`, `SZ_REGISTRY_PATH`, `SZ_PROFILE_PATH`.

### Step 3.10 — Replace each `sz/commands/<iface>.py` stub with the working CLI

`sz/commands/llm.py` (key file — exposes the CLC):

```python
import json, sys, click
from pathlib import Path
from sz.interfaces import llm

@click.group(help="LLM interface (Constrained LLM Call discipline).")
def group(): pass

@group.command(name="invoke")
@click.option("--prompt-file", type=click.Path(exists=True))
@click.option("--prompt", default=None)
@click.option("--model", default=None)
@click.option("--max-tokens", type=int, default=1024)
@click.option("--schema", "schema_path", type=click.Path(exists=True), default=None,
              help="JSON Schema for the response. If set, applies CLC discipline.")
@click.option("--template-id", default=None)
def _invoke(prompt_file, prompt, model, max_tokens, schema_path, template_id):
    if prompt_file:
        prompt = open(prompt_file).read()
    if not prompt:
        prompt = sys.stdin.read()
    try:
        r = llm.invoke(prompt, model=model, max_tokens=max_tokens,
                       schema_path=Path(schema_path) if schema_path else None,
                       template_id=template_id)
    except llm.CLCFailure as e:
        click.echo(json.dumps({"error": "clc_failed", "details": e.errors}), err=True)
        sys.exit(2)
    click.echo(json.dumps({"text": r.text, "parsed": r.parsed,
                           "tokens_in": r.tokens_in, "tokens_out": r.tokens_out,
                           "model": r.model}, ensure_ascii=False))

@group.command(name="provider")
def _provider():
    click.echo(llm.selected_provider())
```

Apply the same shape for `memory.py`, `bus.py`, `schedule.py`, `discovery.py`, with `sz`-namespaced paths.

### Step 3.11 — Make `tick` consult the schedule

Update `sz/commands/tick.py` so a module fires when **any** trigger matches: `on: tick` always; `on: event` is checked at phase-04 reconcile and during heartbeat by reading the cursor; `cron:` is matched by `schedule.matches`.

### Step 3.12 — Tests

Create `tests/interfaces/test_{bus,memory,llm,schedule,discovery,llm_clc}.py`.

Critical: `test_llm_clc.py` tests the Constrained LLM Call discipline with a stubbed provider that returns:
1. Valid JSON matching schema → 1 call, no retries.
2. Valid JSON not matching schema → 3 calls, then `CLCFailure`.
3. First call invalid, second call valid → 2 calls, returns valid.

```python
def test_clc_succeeds_on_first(monkeypatch, tmp_path):
    schema = {"type":"object","required":["x"],"properties":{"x":{"type":"integer"}}}
    schema_p = tmp_path/"s.json"; schema_p.write_text(json.dumps(schema))
    from sz.interfaces.llm_providers import mock as m
    m.call = lambda p,**kw: SimpleNamespace(text='{"x":1}', tokens_in=1, tokens_out=1, model="mock")
    r = llm.invoke("hi", schema_path=schema_p, template_id="t")
    assert r.parsed == {"x":1}

def test_clc_retries_then_fails(monkeypatch, tmp_path):
    ... # similar, returns invalid 3 times, raises CLCFailure
```

Run:
```bash
python3 -m pytest tests/interfaces -q
```

Verify: all tests pass.

### Step 3.13 — Commit

```bash
git add sz tests/interfaces plan/phase-03-universal-interfaces
git commit -m "phase 03: universal interfaces complete with CLC"
```

## Acceptance criteria

1. Every interface CLI works end-to-end.
2. `sz llm invoke --prompt "hello"` returns a non-empty `text` field with `mock` provider when no API keys.
3. `sz llm invoke --prompt "hi" --schema <bad-fitness-schema>` retries 3 times, fails with `clc_failed`.
4. `sz llm invoke --prompt "hi" --schema <fittable-schema>` returns `parsed` matching schema.
5. The `tick` command honors `on: tick`, `cron:`, and (after phase 05 wires events) `on: event`.
6. `pytest tests/interfaces -q` passes.

## Failure modes and recovery

| Symptom | Cause | Action |
|---|---|---|
| `sz llm invoke` hangs | provider HTTP without timeout | confirm `urlopen(..., timeout=120)` in providers |
| `subscribe` returns same events twice | cursor not advanced | check `write_cursor` always called |
| Cron expression matches in wrong tz | spec says UTC | confirm `datetime.now(timezone.utc)` |
| CLC retries with stale prompt | feedback not appended | confirm `prompt + feedback` not `prompt = feedback` |

## Rollback

`git checkout main && git branch -D phase-03-universal-interfaces`.
