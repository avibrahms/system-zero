# Phase 04 — The Reconciliation Engine

## Goal

Implement the cycle that wires modules together every time the module landscape changes. After this phase, `sz install <X>` triggers a reconcile that re-binds every existing module's requirements, and previously installed modules learn about the newcomer through the standard mechanism. This is the heart of S0.

## Inputs

- Phases 00–03 complete.

## Outputs

- `sz/core/reconcile.py` — full implementation.
- `sz/commands/reconcile.py` — replaces the phase-02 stub.
- `sz/commands/install.py` — extended to call reconcile after a successful install.
- `sz/commands/uninstall.py` — extended to call reconcile before files are removed.
- `tests/reconcile/` — comprehensive tests including the "old module learns about new module" scenario, repeated for both Static and Dynamic personas.
- Current-branch git checkpoint history for this phase, with no branch operations.

## Atomic steps

### Step 4.1 — Confirm current branch and stay on it

```bash
git branch --show-current
```

Verify: prints the current branch name; do not create, switch, rename, or delete any branch during this phase.


### Step 4.2 — Write `sz/core/reconcile.py`

Algorithm exactly as in `PROTOCOL_SPEC.md` §6. The function `reconcile(root, *, reason)` is the public entry point. Idempotent. All env vars exported to module reconcile hooks use `S0_*` prefix (`SZ_RECONCILE_REASON`, `SZ_REGISTRY_PATH`, etc.).

Resolution rule (per spec §8): if multiple providers exist for one capability, prefer the one pinned via `.sz.yaml.modules.<requirer>.bindings.<capability>: <provider-id>`. Otherwise pick lexicographically smallest module-id and emit `capability.ambiguous`.

### Step 4.3 — Replace `sz/commands/reconcile.py`

```python
import click
from sz.core import reconcile as engine

@click.command(help="Recompute capability bindings and run each module's reconcile hook.")
@click.option("--reason", default="manual")
def cmd(reason: str) -> None:
    reg = engine.reconcile(reason=reason)
    click.echo(f"Reconciled {len(reg['modules'])} modules, "
               f"{len(reg['bindings'])} bindings, "
               f"{len(reg['unsatisfied'])} unsatisfied.")
```

### Step 4.4 — Wire reconcile into install / uninstall

In `sz/commands/install.py`, after the `bus.emit(... module.installed ...)` call, append `engine.reconcile(root, reason=f"install:{name}")`.

In `sz/commands/uninstall.py`, **before** `shutil.rmtree(target)`: pop the module from `.sz.yaml`, write back, then call `engine.reconcile(root, reason=f"uninstall:{name}")`. After reconcile, `rmtree`.

### Step 4.5 — Tests

`tests/reconcile/test_idempotent.py`:

- `test_old_module_sees_new_module`: install A (requires B.feature, no provider), install B (provides B.feature). After install of B, registry binding is `A.B.feature -> B`.
- `test_reconcile_idempotent`: two consecutive `sz reconcile` calls produce byte-identical `registry.json` (modulo `generated_at`).
- `test_uninstall_re_unsatisfies`: after B is uninstalled, A's requirement is back in `unsatisfied`.
- `test_pinned_binding_wins`: install A (requires F), install B and C (both provide F). `.sz.yaml.modules.A.bindings.F: C`. After reconcile, binding chooses C even though B is alphabetically smaller.

`tests/reconcile/test_personas.py`: same scenarios, run twice — once with `--host generic` (Static) and once with a stub `--host hermes` adapter (Dynamic) that exposes `external_heartbeat`. Modules behave identically.

Run:
```bash
python3 -m pytest tests/reconcile -q
```

Verify: all tests pass.

### Step 4.6 — Manual end-to-end

Identical to the sz version, with `sz` swapped throughout. Two modules: `logger` (provides `log.line`), `sink` (requires `log.line`). Install sink first; verify `unsatisfied` includes `log.line`. Install logger; verify binding appears; verify `sink/state.log` contains `log.line=logger:events:log.line`.

### Step 4.7 — Commit

```bash
git add sz tests/reconcile plan/phase-04-reconciliation-engine
git commit -m "phase 04: reconciliation engine complete"
```

## Acceptance criteria

1. Installing a module triggers a reconcile cycle; the bus shows `reconcile.started` → `module.reconciled` (one per module that has a reconcile hook) → `reconcile.finished`.
2. A previously installed module's `reconcile.sh` runs when a new module is installed; it observes the newcomer in `.sz/registry.json`.
3. Pinned bindings in `.sz.yaml` win over alphabetical default.
4. Reconcile is byte-identical across two consecutive runs (modulo `generated_at`).
5. `pytest tests/reconcile -q` passes for both Static and Dynamic personas.

## Failure modes and recovery

| Symptom | Cause | Action |
|---|---|---|
| Reconcile loop infinite | a reconcile hook emits a reconcile-triggering event | the engine ignores its own reserved event types when computing whether to re-fire |
| Reconcile drift between runs | a hook writes a timestamp into its runtime.json | the absorb prompt and the module-authoring guide forbid this; tests catch it |
| Old module's reconcile.sh fails | hook script not executable | install validates `chmod +x`; doctor flags it |
| Multiple providers pick wrong one | pin missing | UI surfaces `capability.ambiguous` events; user pins via `.sz.yaml.bindings` |

## Rollback

`git checkout main && git branch -D phase-04-reconciliation-engine`.
