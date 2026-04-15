# System Zero Protocol Specification

**Version:** 0.1.0-draft
**Status:** Source of truth for the entire build plan. Every phase must conform to this document. Changes here propagate everywhere; never edit a phase to disagree with this spec — edit this spec and re-run downstream phases.

---

## 0. Goal

Define the minimum, host-agnostic, module-agnostic, framework-agnostic protocol that allows independent self-improvement modules to be installed into any repository, communicate through a small set of universal interfaces, and automatically reconcile when the set of installed modules changes — and to do all of this whether the host has its own heartbeat (Adopt mode) or needs S0 to install one (Install mode).

The protocol's job is to be the **integration standard for self-improvement**, the way MCP is the standard for tool access and A2A is the standard for agent-to-agent calls.

---

## 1. Two-persona requirement (NORMATIVE)

The protocol must serve both:

- **Static persona**: the repo has no autonomous loop. S0 installs an Owned heartbeat. The repo "becomes alive" via Repo Genesis.
- **Dynamic persona**: the repo has an existing loop (OpenClaw, Hermes, MetaClaw, connection-engine, custom, or **unknown**). S0 offers three modes at init time: Install, Adopt, Merge. Default is Adopt when a known heartbeat is detected; Merge is offered as a one-keystroke alternative; Install is always offered so the user can choose to add S0's own pulse alongside or instead.

Three host modes (NORMATIVE):

- **Install**: S0 runs its own heartbeat. No adoption even if markers exist.
- **Adopt**: S0 uses the host's heartbeat only. No second pulse.
- **Merge**: Both heartbeats run. Deduplication is handled by `sz tick` itself (it short-circuits if a tick was fired within the last `dedup_window_seconds` setpoint, default 30s).

Unknown-heartbeat detection: if a `.*/config.yaml` with an `on_tick` key, a systemd unit, a launchd plist, or a cron entry referencing this repo is present but doesn't match any registered framework marker, the detector reports `existing_heartbeat: "unknown"`. The Genesis flow then asks the user explicitly which mode to use; the default is Install + a note to consider Merge once the unknown daemon's API is understood.

Acceptance: any module written for the protocol must work identically in all three modes. A module is forbidden from assuming who fires its tick OR how often.

---

## 2. The seven universal interfaces

Every module talks to the rest of the world through exactly these seven interfaces. Modules never bypass them.

### 2.1 `memory`

A read/write key-value store plus an append-only event log plus an optional vector index (vector index is provider-injected — see `requires.providers`).

API (exposed as a CLI sub-command and a Python helper):
```
sz memory get <key>
sz memory set <key> <value>
sz memory append <stream> <json-line>
sz memory tail <stream> [--from-cursor <id>]
sz memory search <query> [--top <n>]    # only if a vector provider is installed
```

Storage layout: `.sz/memory/kv.json`, `.sz/memory/streams/<stream>.jsonl`, `.sz/memory/vector/` (provider-managed).

### 2.2 `bus`

Append-only JSONL pub/sub on `.sz/bus.jsonl`. Modules emit events; modules subscribe by polling from a saved cursor.

```
sz bus emit <type> <json-payload>
sz bus subscribe <module-id> <pattern>          # returns events since module's cursor
sz bus tail [--last <n>] [--filter <pattern>]
```

Event schema (mandatory fields):
```
{"ts": "<UTC ISO-8601>",
 "module": "<emitter-id>",
 "type": "<dotted.lowercase>",
 "payload": { ... },
 "correlation_id": "<optional uuid>"}
```

Reserved event types (S0 emits these; modules may subscribe but not emit):
- `module.installed`
- `module.uninstalled`
- `module.upgraded`
- `module.errored`
- `reconcile.started`
- `reconcile.finished`
- `tick`
- `repo.genesis.completed`
- `host.adopted`
- `host.session.started`
- `host.session.ended`
- `host.commit.made`
- `host.edit.committed`

### 2.3 `llm`

Vendor-agnostic LLM invocation. S0 reads `~/.sz/config.yaml` (and env overrides) to pick a provider. Modules never see the vendor name.

```
sz llm invoke --prompt-file <path> [--model <profile>] [--max-tokens N] [--schema <path>]
```

When `--schema <path>` is passed, the runtime applies the Constrained LLM Call discipline: validates the response, retries up to 2 more times on schema mismatch, and logs to `llm.calls`. Without `--schema`, the response is returned raw and CLC is bypassed (only allowed for prototyping; not for in-protocol calls).

Providers shipped with v0.1: `anthropic`, `groq`, `openai`, `mock` (offline test fallback). Provider plug-in interface allows third parties to add more.

### 2.4 `storage`

Filesystem paths S0 guarantees:
- `.sz/<module-id>/` — module-private. Module owns it. S0 never writes here except during install.
- `.sz/shared/<namespace>/` — shared between modules that have negotiated access via capabilities.

Modules call `s0 storage path <kind> [<namespace>]` to resolve.

### 2.5 `schedule`

Cron-style triggers. Modules declare schedules in their manifest; S0 evaluates them on every tick (whether the tick is owned or adopted).

```
sz schedule list
sz schedule fire <module-id> [task]
```

Schedule expressions follow standard 5-field cron in local time, plus the special tokens `@tick` (every tick), `@hourly`, `@daily`, `@weekly`.

### 2.6 `discovery`

Live introspection of the module landscape.

```
sz discovery list
sz discovery providers <capability>
sz discovery requirers <capability>
sz discovery resolve <capability>
sz discovery health <module-id>
sz discovery profile                         # returns repo-profile.json content
```

### 2.7 `lifecycle`

Standard hooks every module may implement. The sz calls them at well-defined moments. All hooks are optional except `entry`.

| Hook | When called | Required? |
|---|---|---|
| `install.sh` | Once, immediately after files copied. | optional |
| `start.sh` | When the heartbeat starts and this module is enabled. | optional |
| `stop.sh` | Before heartbeat stops or before uninstall. | optional |
| `uninstall.sh` | Once, before files are removed. | optional |
| `reconcile.sh` | Whenever the module landscape changes. Idempotent. | **required if module declares `requires` or `provides`** |
| `entry` | The thing that actually runs on tick or event match. | **required** |
| `doctor.sh` | When `sz doctor` runs. | recommended |

Hooks run in the module's own subprocess. They receive S0 context via environment variables: `SZ_REPO_ROOT`, `SZ_MODULE_DIR`, `SZ_MODULE_ID`, `SZ_BUS_PATH`, `SZ_MEMORY_DIR`, `SZ_REGISTRY_PATH`, `SZ_PROFILE_PATH`, `SZ_LLM_BIN`.

---

## 3. The module manifest (`module.yaml`)

The single required file at the root of every module directory. Schema:

```yaml
# Identity
id: <kebab-case-string>
version: <semver>
category: <free-form-string>            # e.g. "physiology", "cognition", "logging"
description: <one line>

# Execution
entry:
  type: python | bash | node | binary
  command: <relative path>
  args: [<optional>]

# Triggers (when does the entry run?)
triggers:
  - on: tick
  - on: event
    match: <event-type-glob>
  - cron: "<5-field cron>"

# Capability contracts
provides:
  - name: <dotted.lowercase>
    address: <relative path or socket>
    description: <one line>
requires:
  - name: <dotted.lowercase>
    optional: true | false
    on_missing: warn | error
  - providers: [llm, vector, memory, bus, storage, schedule, discovery]

# Tunable parameters
setpoints:
  <name>:
    default: <value>
    range: [<min>, <max>]               # OR
    enum: [<v1>, <v2>, ...]             # OR
    description: <one line>
    mode: simple | advanced

# Lifecycle hooks
hooks:
  install: install.sh
  start: start.sh
  stop: stop.sh
  uninstall: uninstall.sh
  reconcile: reconcile.sh
  doctor: doctor.sh

# Host capability requirements
requires_host:
  - session_lifecycle | commit_events | clock_only | edit_events | command_palette | external_heartbeat

# Conflicts
conflicts: [<module-id>, ...]

# Resource hints
limits:
  max_runtime_seconds: <int>
  max_memory_mb: <int>

# Persona compatibility
personas: [static, dynamic]               # default: both
```

Validation rules: see `spec/v0.1.0/manifest.schema.json`.

---

## 4. The repo configuration (`.sz.yaml`)

The single file the user (or the website) edits to configure their installed modules:

```yaml
sz_version: 0.1.0
host: claude_code | cursor | opencode | aider | hermes | openclaw | metaclaw | connection_engine | unknown | generic
host_mode: install | adopt | merge
modules:
  <module-id>:
    version: <pinned semver>
    enabled: true | false
    setpoints:
      <name>: <override-value>
    bindings:
      <capability-name>: <provider-module-id>
    quiet_hours:
      - "22:00-07:00"
providers:
  llm: anthropic | groq | openai | mock | <plugin>
  vector: <provider-id> | none
cloud:
  tier: free | pro | team
  endpoint: https://api.systemzero.dev      # overridable
  telemetry: false                          # opt-in only
```

S0 guarantees that this file is sufficient to fully reconstruct an S0 installation on a fresh machine via `sz restore`.

---

## 5. The catalog

Public GitHub repository (`systemzero-dev/catalog`). Layout:

```
catalog/
  modules/
    <module-id>/
      module.yaml
      README.md
      source.yaml                        # type: git|tarball|local; url; ref; path
  index.json                             # auto-generated
```

`sz install <id>` consults `index.json`, fetches the source, validates the manifest, and installs into `.sz/<id>/`.

External URLs are allowed via `sz install --source git+https://...` but require `--allow-external`.

---

## 6. The reconciliation cycle

Triggered by:
- `sz install <id>` (after install completes)
- `sz uninstall <id>` (before files are removed)
- `sz upgrade <id>`
- `sz reconcile` (manual)
- A `module.installed`, `module.uninstalled`, or `module.upgraded` event landing on the bus

Algorithm (deterministic, idempotent):

```
1. emit reconcile.started
2. read all installed manifests
3. build the capability graph:
   - nodes = (module, provided-capability) and (module, required-capability)
   - edges = (requirement -> provider) chosen by:
       a. exact name match
       b. if multiple providers, prefer the one pinned in .sz.yaml bindings
       c. else lexicographically smallest module-id
       d. if no provider and required is mandatory, mark as UNSATISFIED
4. write the resolved bindings to .sz/registry.json
5. for each installed module, in alphabetical order:
   a. set env SZ_RECONCILE_REASON=<reason>
   b. run the module's reconcile.sh in its own subprocess
   c. capture stdout/stderr to .sz/<id>/reconcile.log
   d. emit module.reconciled with status code
6. for each unsatisfied requirement, emit capability.unsatisfied
7. emit reconcile.finished
```

Idempotency: running reconcile twice produces identical `registry.json` and identical `reconcile.log` content.
Decoupling: a module's `reconcile.sh` works without knowing which module triggered the cycle. It reads `.sz/registry.json`.

---

## 7. Repo Genesis (the "becomes alive" moment)

Triggered by `sz init` (always) and `sz genesis` (re-run later).

Algorithm:

```
1. Inventory the repo (deterministic):
   - All file paths under the root, excluding .git/, node_modules/, .venv/, dist/, build/, .sz/.
   - First 5 KB of README.md / package.json / pyproject.toml / setup.py / Cargo.toml / go.mod / requirements.txt / Makefile / README.rst.
   - Detected ecosystems: presence of language-specific marker files.
   - Detected existing autonomous frameworks: scan for OpenClaw / Hermes / MetaClaw / connection-engine markers, agentic CLI configs.
2. Detect existing heartbeat (algorithm, not LLM):
   - Check for known scheduler/daemon patterns (cron entries pointing into this dir, launchd plists, systemd units, framework-specific marker files).
   - Output: existing_heartbeat: <none|known-name|unknown>.
3. Make exactly one Constrained LLM Call:
   - Template: sz/templates/repo_genesis_prompt.md
   - Schema: spec/v0.1.0/llm-responses/repo-genesis.schema.json
   - Inputs: inventory + ecosystem markers + existing_heartbeat + the user's optional --hint
4. Validate response. Retry up to 2 times on schema failure with feedback. Abort if all fail.
5. Write .sz/repo-profile.json.
6. Print recommendations and ask `[Y/n]` (skip with --yes).
7. On confirm:
   a. Resolve host_mode: install if existing_heartbeat == none; otherwise offer install, adopt, and merge, defaulting to adopt for a known heartbeat and install for an unknown heartbeat.
   b. Install host adapter accordingly.
   c. Install each recommended module via the standard install path.
   d. Run reconcile.
   e. If install mode: start the heartbeat (`sz start --interval 300`).
   f. Emit repo.genesis.completed with the profile in payload.
8. Print: "Repo is alive. Heartbeat: <owned|adopted>. Modules: <list>. Try: sz list, sz doctor, sz bus tail."
```

Genesis is non-destructive. No files outside `.sz/` and `.sz.yaml` are created. Re-running `sz genesis` is safe; it overwrites `.sz/repo-profile.json` only.

The schema for the LLM response is normative:

```json
{
  "purpose":         "string, 1-200 chars",
  "language":        "string from enum [python,javascript,typescript,go,rust,ruby,java,kotlin,swift,php,shell,mixed,other]",
  "frameworks":      ["array of strings"],
  "existing_heartbeat": "string, one of [none, claude_code, cursor, opencode, aider, hermes, openclaw, metaclaw, connection_engine, custom, unknown]",
  "goals":           ["1-5 short goal statements"],
  "recommended_modules": [
    {"id": "string from catalog", "reason": "string, 1-100 chars"}
  ],
  "risk_flags":      ["array of short strings, can be empty"]
}
```

---

## 8. Capability matching rules

Capabilities matched by exact dotted-name, version-aware:

- A `requires: anomaly.detection` is satisfied by any `provides: anomaly.detection`.
- If multiple providers exist, S0 picks the lexicographically smallest module-id and emits `capability.ambiguous`. User can pin in `.sz.yaml`:
  ```yaml
  modules:
    consumer-mod:
      bindings:
        anomaly.detection: producer-mod-x
  ```
- A capability provider can declare a version range with the capability name: `provides: anomaly.detection@^1.0`.
- A capability requirer can pin a version range: `requires: anomaly.detection@^1.0`.

Capability addresses are opaque strings. They may be:
- A relative file path inside the provider module.
- A bus event type (`anomaly.detected`).
- A memory key prefix (`memory:anomaly/`).
- A subprocess command.

S0 writes resolved addresses to `.sz/registry.json`; modules read from there to reach their dependencies.

---

## 9. Host adapters and Adopt mode

A host adapter is a small package that:
1. Either installs an Owned heartbeat (Install mode) or registers as a subscriber to an existing heartbeat (Adopt mode).
2. Maps host events to S0 bus events.

Adapters live in `sz/adapters/<host>/`. Selection by name at `sz init --host <name>` (or auto-detected by Repo Genesis).

Standard host adapters in v0.1:

| Adapter | Install mode | Adopt mode | Provides host capabilities |
|---|---|---|---|
| `generic` | git post-commit + cron | n/a | clock_only, commit_events |
| `claude_code` | hooks + cron | n/a | clock_only, commit_events, session_lifecycle |
| `cursor` | .cursorrules + cron | n/a | clock_only, commit_events, edit_events |
| `opencode` | hooks + cron | n/a | clock_only, commit_events, session_lifecycle |
| `aider` | post-commit + cron | n/a | clock_only, commit_events, session_lifecycle |
| `hermes` | n/a | hooks into Hermes scheduler | external_heartbeat, session_lifecycle |
| `openclaw` | n/a | hooks into OpenClaw loop | external_heartbeat, session_lifecycle |
| `metaclaw` | n/a | hooks into MetaClaw loop | external_heartbeat, session_lifecycle |
| `connection_engine` | n/a | adopts circadian-daemon | external_heartbeat, session_lifecycle |
| `unknown` | n/a | records unknown heartbeat detection; manual pulse wiring required | external_heartbeat |

Adopt-mode adapters all expose the host capability `external_heartbeat`. A module that declares `requires_host: [external_heartbeat]` will not be installed in a Static repo (S0 emits a clear error and suggests `--persona static`).

---

## 10. The absorb workflow

`sz absorb <source-url> --feature <name> [--id <new-module-id>]`

Flow:

1. Clone source repo into `~/.sz/cache/absorb/<sha>/`.
2. Inventory the repo (deterministic).
3. Constrained LLM Call with `sz/templates/absorb_prompt.md` and schema `spec/v0.1.0/llm-responses/absorb-draft.schema.json`. Up to 2 retries on schema mismatch.
4. Validate the drafted manifest against `spec/v0.1.0/manifest.schema.json`.
5. Materialize: copy the chosen source files into `.sz/cache/absorb/<sha>/.staging/<module-id>/`. Write `module.yaml`, `entry`, `reconcile.sh`.
6. Install via the standard install path (validate + install hook + reconcile).
7. Run `sz doctor <module-id>`. If failed, optionally `--auto-rollback`.

Critical rule: the absorb LLM may NOT modify any files outside `.sz/<new-id>/` or `.sz.yaml`. It never patches other modules. Cross-module concerns are handled by the standard reconcile cycle.

---

## 11. Constrained LLM Call (CLC) — the spec for every LLM use

Every LLM call inside S0 conforms to:

1. **Templated prompt** at `sz/templates/<call-name>.md`.
2. **Response schema** at `spec/v0.1.0/llm-responses/<call-name>.schema.json`.
3. **Validation** against the schema.
4. **Retry** up to 2 more times on mismatch, appending `[VALIDATION_ERROR]: <messages>` to the prompt.
5. **Logging** to memory stream `llm.calls`.

Calls registered in v0.1:
- `repo-genesis` (Repo Genesis)
- `absorb-draft` (Absorb workflow)

Modules MAY register additional CLCs for their own purposes; the same discipline applies.

---

## 12. Distribution

S0 ships through five channels, each defined in phase 09:

- pip: `system-zero` on PyPI.
- npm: `system-zero` on npm registry (a thin wrapper that downloads + invokes the Python CLI).
- curl: `https://systemzero.dev/i` returns an `install.sh` that auto-detects pipx vs pip.
- brew: a tap at `systemzero-dev/homebrew-tap` (post-launch).
- Web: `systemzero.dev` "Install on this repo" produces a copy-pasteable command.

All channels install the same `sz` CLI. The Python package is the canonical artifact; npm and brew wrap it.

---

## 13. Cloud platform

Defined in phase 10. Hosted on Fly.io. Endpoints under `api.systemzero.dev`. Stripe for billing. Static catalog mirror via CDN.

The protocol is fully usable Free without any cloud call. The cloud unlocks the Pro/Team tiers.

---

## 14. Failure semantics

- A module that crashes during a tick is marked `degraded` in `.sz/registry.json`. Heartbeat skips it on subsequent ticks until `sz doctor --fix` clears it.
- A module that fails to install leaves no trace (atomic install via staging).
- A reconcile cycle that fails for one module does not abort the cycle; other modules still reconcile.
- The bus is append-only; corruption of older entries is tolerated, S0 seeks past unparsable lines.
- A CLC that fails validation 3 times emits `llm.call.failed` and the calling operation aborts with a clear error.

---

## 15. Conformance test (informative)

A module is "S0-conformant" if:
1. Its manifest validates.
2. Its `entry` runs to completion within `limits.max_runtime_seconds` on a no-op input.
3. Its `reconcile.sh` (if declared) is idempotent.
4. It writes only inside `.sz/<id>/` and through the universal interfaces.
5. It survives the standard test bench (`sz test conformance <id>`).
6. It works in both Static and Dynamic personas (or declares `personas: [static]` / `[dynamic]` if intentionally limited).

The conformance test runner ships in phase 09.

---

## 16. Open questions deferred to v0.2

- Cross-machine module distribution (multi-developer team).
- Hot-replace of a running module.
- A typed schema language for bus payloads.
- Module signing (sigstore).
- A Windows-native runtime (WSL works in v0.1).

These are explicitly not in scope. Phase plans must not assume them.
