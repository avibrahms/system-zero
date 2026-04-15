# System Zero — your repo, alive

I'm releasing System Zero today.

It's the smallest, host-agnostic, framework-agnostic protocol that gives any repository, in one click, autonomy + self-improvement + safe absorption of any open-source feature.

Two clicks for the visitor:
1. `pipx install sz-cli` (or `curl -sSL https://systemzero.dev/i | sh`; npm is pending token rotation)
2. `sz init`

What happens at step 2 — Repo Genesis: System Zero scans the repo, detects whether it has a heartbeat (Claude Code, Cursor, Hermes, OpenClaw, MetaClaw, connection-engine, custom), then either installs its own (Owned) or adopts the existing one (Adopted). It picks 3-5 self-improvement modules to install (immune, subconscious, dreaming, metabolism, endocrine, prediction, …), runs the reconcile cycle, and starts the heartbeat. The repo is alive.

When you absorb a feature from any GitHub repo (`sz absorb https://github.com/<x>`), the protocol's reconcile cycle re-wires every previously installed module to the newcomer. That's how features added today still talk to features added next month — the magic-board property.

The protocol is open-source forever. Cloud features (hosted catalog, Pro absorb, cloud backup, telemetry opt-in, team library) are $19/mo Pro, $49/seat Team. Stripe.

→ install: https://systemzero.dev
→ source: https://github.com/avibrahms/system-zero
→ catalog: https://github.com/avibrahms/catalog
→ spec: https://github.com/avibrahms/system-zero/blob/main/plan/PROTOCOL_SPEC.md

Apache 2.0. PRs welcome.
