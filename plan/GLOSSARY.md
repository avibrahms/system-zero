# Glossary

Every term used inside the plan folder. If a phase uses a word not defined here, GPT-5.4 must stop and request clarification before proceeding.

## System Zero (S0, s0)

The protocol being built. Also the runtime that implements the protocol. Also the CLI command (`sz`). Also the brand. Context disambiguates which is meant; phase plans always specify.

## Module

The unit of packaging. A directory containing at minimum a `module.yaml` manifest. A module is what gets installed, started, reconciled, and uninstalled. Every absorbed open-source feature becomes a module. The five built-in self-improvement modules ported from connection-engine (heartbeat, immune, subconscious, dreaming, metabolism) are also modules. There is no privileged module category at runtime.

## Host

The surrounding development environment of the user's repository. Examples: Claude Code, Cursor, OpenCode, Aider, OpenClaw, Hermes, MetaClaw, plain editor + git, plain cron. S0 runs inside any of these.

## Host adapter

A small, host-specific package that translates host-native events into S0 bus events. Three modes: Install, Adopt, and Merge (defined below).

## Install mode (host adapter)

The adapter installs S0's own heartbeat, hooks, or cron into the host environment. Used when the host has no heartbeat of its own (Claude Code, Cursor, plain editor, plain cron).

## Adopt mode (host adapter)

The adapter detects an existing heartbeat, daemon, or scheduler inside the host (OpenClaw, Hermes, MetaClaw, connection-engine, custom autonomous frameworks) and **registers as a subscriber** rather than launching a competing heartbeat. S0 modules then fire on the host's existing pulse. There is exactly one heartbeat source.

## Merge mode (host adapter)

The adapter **both** registers as a subscriber to the existing heartbeat AND installs S0's own heartbeat on a slower cadence. The two pulses coexist. Useful when:

1. The user wants S0 modules to fire on the fast pulse of their framework (for responsiveness) AND on a slower independent pulse (for resilience — if the host daemon dies, SZ still ticks).
2. The host emits on events (commits, sessions) while SZ needs wall-clock cron triggers the host does not provide.

Merge mode is always OFFERED when Adopt mode is detected. The user chooses at `sz init` time. Default is Adopt. Merge is one-keystroke away. Ticks fired by either source are indistinguishable on the bus (same `type: tick` event), so modules cannot tell which pulse fired them.

## Generic heartbeat detection

When `heartbeat_detect.detect()` finds an `existing_heartbeat` marker but does not recognize the framework (not in `{claude_code, cursor, opencode, aider, hermes, openclaw, metaclaw, connection_engine}`), it returns `existing_heartbeat: "unknown"`. The init flow then OFFERS three options: Install (ignore the unknown daemon), Adopt (attempt generic adoption via a cron entry that runs alongside the unknown daemon), or Merge (recommended). The detection is heuristic: presence of any `.*/config.yaml` with an `on_tick` key, any systemd unit file, any launchd plist, or any cron entry referencing the current working directory.

## Universal interface (or "socket")

One of seven repo-level services S0 provides to every module:

1. **memory** — read/write to a shared key-value + JSONL log.
2. **bus** — publish/subscribe events.
3. **llm** — call the configured LLM provider (vendor-agnostic).
4. **storage** — module-private and module-shared filesystem paths.
5. **schedule** — register cron-like triggers.
6. **discovery** — query "who else is installed?", "who provides capability X?".
7. **lifecycle** — declare install/start/stop/uninstall/reconcile hooks.

Modules talk only through these sockets. They do not read each other's source files. They do not directly call each other.

## Capability

A named ability a module declares it provides or requires. Examples: `provides: anomaly.detection`, `requires: vector.search`. Capabilities use dotted lowercase strings. The protocol matches `requires` to `provides` at install time and re-runs the match on every reconcile cycle.

## Reconcile (verb) / Reconciliation (noun)

The act of recomputing the module-to-module wiring. Triggered automatically when a module is installed, uninstalled, or upgraded; can be invoked manually with `sz reconcile`. Every module that declares `provides` or `requires` must expose an idempotent `reconcile.sh`.

## Manifest

The `module.yaml` file at the root of every module directory. Declares id, version, category, provides, requires, host capabilities needed, entry points, triggers, setpoints, lifecycle hooks. Validated against `spec/v0.1.0/manifest.schema.json`.

## Setpoint

A tunable parameter exposed by a module, with a default and either a discrete enum or a numeric min/max range. The website renders setpoints as sliders or selectors. Edits are written to `.sz.yaml`.

## `.sz/`

The runtime directory at the root of any repo that has run `sz init`. Contains: `bus.jsonl`, `bin/`, `<module-id>/` per installed module, `registry.json`, `state.json`, `repo-profile.json`. Created by `sz init`. Owned by S0; modules write only into their own subdirectory.

## `.sz.yaml`

The repo-level configuration file. Lists installed modules, their pinned versions, their setpoint overrides, the chosen host adapter, the chosen LLM provider, the cloud tier (free/pro/team). Hand-editable. Version-controlled in the user's repo.

## Repo Genesis

The "becomes alive" moment, executed by `sz init` (or `sz genesis` to re-run later). Algorithm:

1. Scan the repo (deterministic file inventory).
2. Make exactly one constrained LLM call with a templated prompt and a JSON Schema for the response.
3. The LLM returns `repo-profile.json`: language, framework, declared purpose, detected goals, suggested first modules.
4. The CLI presents the suggestions and asks for `[Y/n]`.
5. On confirm: install the suggested modules, run reconcile, start the heartbeat (or adopt the existing one).

The output of Genesis is `.sz/repo-profile.json` and the bus event `repo.genesis.completed`.

## `repo-profile.json`

JSON document produced by Repo Genesis. Schema in `spec/v0.1.0/repo-profile.schema.json`. Fields include: `purpose`, `language`, `frameworks`, `existing_heartbeat`, `recommended_modules`, `risk_flags`, `goals`. Modules consume this to behave appropriately for the repo.

## Constrained LLM call (CLC)

The protocol's discipline for using LLMs anywhere inside S0. Every LLM use must:

1. Use a templated prompt file under `sz/templates/`.
2. Declare a JSON Schema for the expected response under `spec/v0.1.0/llm-responses/<call-name>.schema.json`.
3. Validate the response against the schema; if it fails, retry up to N times with the validation error appended.
4. Log the call (template id, response hash, validation status) to memory stream `llm.calls`.

The framework prefers algorithms over LLMs whenever both can do the job. LLMs are used only where unavoidable (Repo Genesis, Absorb).

## Catalog

A public GitHub repository (`avibrahms/catalog`). Layout:

```
catalog/
  modules/
    <module-id>/
      module.yaml              # the manifest (canonical)
      README.md                # human-facing docs
      source.yaml              # where to fetch the actual code
  index.json                   # auto-generated index of all modules
```

The CLI fetches from here when running `sz install`. The website mirrors it from a CDN.

## Absorb (verb)

The act of taking a feature from an external open-source repository and wrapping it as an S0 module. Performed by `sz absorb <repo-url> --feature <name>`. The result is a new module directory plus a generated `module.yaml`. Absorption uses a Constrained LLM Call with the absorb prompt template.

## Cloud tier

One of `free`, `pro`, `team`. Stored in `.sz.yaml` under `cloud.tier`. Determines whether the CLI calls the local catalog only or the hosted catalog with private modules. The runtime works fully on `free` without ever contacting the cloud; the cloud is opt-in.

## API (S0 Cloud API)

Hosted at `api.systemzero.dev`. Endpoints (defined in phase 10):

- `GET  /v1/catalog/index` — same as the static index, served from edge cache.
- `GET  /v1/catalog/modules/<id>` — module details.
- `POST /v1/absorb` — Pro/Team only: hosted absorb that runs the constrained LLM call on our infra so the user does not need their own API key.
- `POST /v1/billing/checkout` — Stripe checkout session.
- `POST /v1/billing/webhook` — Stripe webhook.
- `POST /v1/telemetry` — Pro/Team opt-in usage data.

## Heartbeat

A loop that fires `sz tick` at regular intervals. Two flavors:

- **Owned heartbeat**: installed by S0 in Install mode. A shell loop or cron entry.
- **Adopted heartbeat**: an existing daemon in the host (OpenClaw, Hermes, connection-engine, etc.) configured to call `sz tick` on its own pulse, via the Adopt-mode adapter.

There is exactly one heartbeat per repo at any time.

## Tick

One iteration of the heartbeat. During a tick, S0 evaluates which modules' triggers match, calls each in subprocess isolation, captures their output, and appends events to the bus.

## Bus event

A line in `.sz/bus.jsonl`. Schema: `{ts, module, type, payload, correlation_id?}`. `type` follows dotted lowercase conventions (`commit.made`, `anomaly.detected`, `module.installed`, `repo.genesis.completed`).

## Capability address

The string that resolves to a concrete module providing a capability. Format: `<module-id>:<capability-name>` (e.g. `pgvector:vector.search`). Discovery returns capability addresses; modules call through the sz, never directly to the address.

## Acceptance criteria

The set of mechanical, executable checks that gate a phase's completion. If any criterion fails, the phase is incomplete. GPT-5.4 must not advance to the next phase until all criteria pass.

## Static repo

A repository that has no scheduler, no daemon, no autonomous loop. Defaults: a Python project, a Node project, a website, a personal notes folder. S0 installs an Owned heartbeat for these.

## Dynamic repo

A repository whose host already runs an autonomous loop (OpenClaw, Hermes, MetaClaw, connection-engine, custom). S0 enters Adopt mode for these.

## INVOKE_REVIEWER

A token used in phase plans. When a step is marked `INVOKE_REVIEWER`, GPT-5.4 must pause and hand off to a human or a more creative model. After the reviewer responds, GPT-5.4 resumes from the next step.

## STOP_AND_REPORT

A token used in phase plans. When a step is marked `STOP_AND_REPORT`, GPT-5.4 must halt, summarize the state, and surface to the user. The plan does not continue automatically.
