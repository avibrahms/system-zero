# System Zero Architecture

This is the verbal counterpart to `PROTOCOL_SPEC.md`. The spec is normative; this document is descriptive. If they conflict, the spec wins.

## High-level picture (Static persona)

```
                                ┌─────────────────────────────────────┐
                                │           User's Repository         │
                                │                                     │
   +-----------+     events     │  ┌────────────┐   ┌──────────────┐  │
   |  Host     |───────────────►│  │ Host       │   │ .sz.yaml     │  │
   |  CC,Cur,  │                │  │ adapter    │   │              │  │
   |  cron…    │◄───────────────│  │ (Install)  │   │              │  │
   +-----------+                │  └──────┬─────┘   └──────────────┘  │
                                │         │                            │
                                │         ▼                            │
                                │  ┌─────────────────────────────┐    │
                                │  │   .sz/  (runtime)           │    │
                                │  │                              │    │
                                │  │  bus.jsonl  ◄────► registry  │    │
                                │  │      ▲           json        │    │
                                │  │      │                       │    │
                                │  │  ┌───┴────┬──────┬──────┐    │    │
                                │  │  │heartbt │immune│dream │ …  │    │
                                │  │  └────────┴──────┴──────┘    │    │
                                │  │                              │    │
                                │  │  repo-profile.json           │    │
                                │  └─────────────────────────────┘    │
                                └─────────────────────────────────────┘
```

The Owned heartbeat is a shell loop installed by S0; it fires `sz tick` every N seconds.

## High-level picture (Dynamic persona)

```
   ┌────────────────────────────────────────────────────────┐
   │       Existing autonomous framework                    │
   │  (Hermes / OpenClaw / MetaClaw / connection-engine)    │
   │                                                        │
   │   ┌──────────────────┐                                 │
   │   │ Existing daemon  │── pulse ──┐                     │
   │   │ / scheduler      │           │                     │
   │   └──────────────────┘           │                     │
   │           │                       ▼                     │
   │           │      ┌──────────────────────────────┐      │
   │           │      │  Adopt-mode adapter          │      │
   │           │      │  (subscribes to pulse)       │      │
   │           │      └──────────────┬───────────────┘      │
   │           │                     │                       │
   │           │                     ▼                       │
   │           │      ┌──────────────────────────────┐      │
   │           │      │  sz tick                     │      │
   │           │      └──────────────┬───────────────┘      │
   │           │                     │                       │
   │           │                     ▼                       │
   │           │      ┌─────────────────────────────┐       │
   │           └─────►│   .sz/  (runtime)           │       │
   │                  │  same as Static persona     │       │
   │                  └─────────────────────────────┘       │
   └────────────────────────────────────────────────────────┘
```

Install and Adopt modes keep one active heartbeat at a time. Merge mode intentionally allows both the owned and host heartbeat; `sz tick` deduplicates repeated pulses within the configured dedup window. The Adopt-mode adapter is a 50-line shim that calls `sz tick` from inside the host's existing pulse.

## Three planes (both personas)

### Control plane

The `sz` CLI plus `.sz.yaml`. Humans (and the website) operate here. Side effects: write `.sz.yaml`, copy files into `.sz/<id>/`, install host adapter.

### Data plane

`.sz/bus.jsonl`, `.sz/memory/`, `.sz/registry.json`, `.sz/repo-profile.json`. Modules read and write through CLI sub-commands. No direct file access by modules to anything outside their own dir.

### Execution plane

Per-tick subprocess invocations of module entry points. Each module runs in its own process; failures are isolated.

## Why this shape

| Concern | Choice | Rationale |
|---|---|---|
| Discovery | filesystem layout (`.sz/<id>/`) | proven by npm, cargo, claude skills |
| Communication | append-only JSONL bus | works on any OS / language; survives reboots; greppable |
| Coordination | reconcile cycle on landscape change | the answer to "old features don't know new features arrived" |
| Configuration | one YAML file in the user's repo | one source of truth, version-controllable |
| Runtime | shell loop, adopted scheduler, or merged pulses | no language coupling; isolation comes for free; Install/Adopt keep a single active pulse, while Merge relies on tick deduplication |
| Vendor neutrality | LLM access through one CLI command | swap providers without touching modules |
| Host neutrality | small adapter per host translates to common events | modules never see the host |
| LLM safety | every LLM call is a CLC (templated + schema'd + retried) | no surprise outputs, fully testable |
| Persona symmetry | Same protocol, three host modes (Install / Adopt / Merge) | one product for both audiences |

## How a module reaches its dependencies

```
                module B's reconcile.sh
                          │
                          ▼
        reads .sz/registry.json
                          │
                          ▼
       finds: anomaly.detection -> module-A:scripts/detect.py
                          │
                          ▼
       writes .sz/B/runtime.json
                          │
                          ▼
       on next tick, B's entry reads runtime.json,
       subscribes to module A's events on the bus
```

A module's reconcile.sh is the **only** place that learns the wiring. The entry reads the resolved configuration and runs.

## How a new module landing causes the world to update

```
   user runs: sz install vector-pgvector
              │
              ▼
   S0 copies files, validates manifest, runs install hook
              │
              ▼
   S0 emits module.installed
              │
              ▼
   reconcile cycle starts
              │
              ▼
   for each existing module M (alphabetical):
       run M/reconcile.sh
              │
              ▼
       M sees the new module in registry.json
       M re-binds: requires: vector.search now satisfied
       M writes new runtime.json
              │
              ▼
   bus gets module.reconciled events
              │
              ▼
   on next tick, every module is using the new wiring
```

This is the magic-board property: every existing module gets a chance to react to every newcomer, automatically. No human re-coding.

## How "becomes alive" works (Repo Genesis)

```
   user runs: sz init  (from any repo, after install)
              │
              ▼
   1. Algorithmic inventory of the repo (file scan)
   2. Algorithmic detection of existing heartbeat
   3. ONE Constrained LLM Call → repo-profile.json
              │
              ▼
   Print: "I think this repo is for X. I recommend installing
           heartbeat, immune, subconscious. Existing heartbeat: none.
           Proceed? [Y/n]"
              │
              ▼
   On Y:
     - Pick host_mode (install if no heartbeat; otherwise offer install/adopt/merge, default adopt for known heartbeat and install for unknown heartbeat)
     - Install host adapter
     - Install recommended modules
     - Run reconcile
     - Start (or attach to) heartbeat
     - Emit repo.genesis.completed
              │
              ▼
   Repo is alive.
```

## How "absorb" plugs into all of this

```
   user runs: sz absorb <repo-url> --feature rate-limiter
              │
              ▼
   Clone source into ~/.sz/cache/absorb/<sha>/
              │
              ▼
   Algorithmic inventory of source
              │
              ▼
   Constrained LLM Call → manifest draft (validated)
              │
              ▼
   Materialize files into staging dir
              │
              ▼
   Standard install + reconcile cycle
              │
              ▼
   Absorbed feature is now a first-class module that any
   other module can find via discovery.
```

## Distribution channels

```
                       ┌──────────────────────┐
                       │  Single source of    │
                       │  truth: PyPI         │
                       │  system-zero==0.1.0  │
                       └──────────┬───────────┘
                                  │
       ┌────────────┬─────────────┼────────────┬──────────────┐
       ▼            ▼             ▼            ▼              ▼
   pipx install  npm wrapper  curl|sh      brew tap      Web 1-click
   user runs:    invokes pipx  detects     formula       copies the
   pipx install  + sz binary    pipx,       installs      "pipx install"
   system-zero                  installs    via pipx      command
                                pipx if
                                missing
```

## Cloud platform (Pro / Team only)

```
                          systemzero.dev (DNS via Hostinger)
                                  │
                       ┌──────────┴──────────┐
                       │   Fly.io app:        │
                       │   sz-cloud           │
                       │                      │
                       │   FastAPI            │
                       │   ├ /v1/catalog/*   │
                       │   ├ /v1/absorb     │ (Pro+)
                       │   ├ /v1/billing/*  │
                       │   └ /v1/telemetry  │ (opt-in)
                       │                      │
                       │   SQLite on volume   │
                       │                      │
                       │   Stripe webhook     │
                       │   handler            │
                       └──────────────────────┘
                                  │
                                  ▼
                          stripe.com checkout
```

## Failure isolation

- Module crash in `entry` → killed after `limits.max_runtime_seconds`, marked degraded, bus gets `module.errored`. Other modules unaffected.
- Module crash in `reconcile.sh` → cycle continues for other modules.
- Bus file unreadable line → seek past, log to S0's own error stream.
- LLM provider unreachable → CLC retries, then aborts the calling operation cleanly.
- Host adapter break → manual `sz tick` still works.
- Cloud unreachable → catalog falls back to last-known mirror in `~/.sz/cache/`.

## Why this scales to many modules

Many-to-many through the bus. Many-to-many through the capability graph. No central arbiter. Adding a new module is O(N) reconcile work but each reconcile is fast.

## Why this scales to many users

A user's installation is a `.sz.yaml`. Anyone with that file plus the catalog can reproduce via `sz restore`. Teams collaborate by versioning `.sz.yaml`. The cloud is opt-in, not required.

## Spec-driven everywhere

Every YAML/JSON file the protocol writes has a JSON Schema. Every LLM call has a templated prompt + a response schema. Every module's behavior is declared in its manifest, not discovered at runtime. Every host integration is a small adapter, not a fork. The whole system is a stack of specs; the LLM fills the gaps where deterministic algorithms cannot.
