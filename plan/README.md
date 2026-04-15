# System Zero — Build Plan

This folder is the complete, ordered, executable plan for building **System Zero (s0)**, an open-source protocol that gives any repository, on any host, in one click, autonomy + self-improvement + safe absorption of any open-source feature.

## Domains

- Primary: `systemzero.dev`
- Alias: `system0.dev`

Both are owned and managed via Hostinger; their tokens are in the repo `.env` file.

## Who executes this plan

The intended executor is **GPT-5.4**: precise, focused, literal, does not improvise. Every phase plan in this folder is written for that executor:

- Atomic steps with one action each.
- Exact file paths, exact commands, exact expected outputs.
- A verification command after every meaningful step.
- A fail-recovery path when something can go wrong.
- No metaphors, no "use judgment", no "etc."

A human or a more creative model is invoked from inside a phase only when the plan explicitly says `INVOKE_REVIEWER`. Otherwise GPT-5.4 executes deterministically.

## What System Zero is — one sentence per persona

**Persona A (Static repo user)**: I have a folder I work on with Claude Code, OpenCode, Cursor, plain editor + git, or any LLM-based assistant. The folder does what I tell it to but does not run on its own. I install s0; in one click my repo gains a heartbeat, detects what it's *for*, picks the first 3-5 self-improvement modules that fit, and starts running autonomously. Every week I add another module from the catalog. When I find a feature in some open-source GitHub repo, `sz absorb <url>` wraps it as a module and reconciles it with everything I already installed.

**Persona B (Dynamic repo user)**: I'm using OpenClaw, Hermes, MetaClaw, an autonomous framework, or my own custom heartbeat. My problem is: my framework evolves, every module I add is tied to the framework, every feature in a different framework is unreachable. I install s0; it **detects my existing heartbeat and adopts it** — no second daemon, no double-pulse. All s0 modules subscribe to my heartbeat's events. I get a vendor-neutral standard, can absorb features from any other framework, and stay portable when my framework breaks or gets replaced.

Both personas use the same protocol. The difference is which adapter s0 chooses at install time.

## What System Zero is — three sentences for the public

1. A repo-level **protocol** for self-improvement. Like MCP for tool access and A2A for agent communication, S0 is the standard for *what gets installed inside a repo to make it alive*.
2. A small **runtime** (one binary, `sz`) that implements the protocol on disk. Modules are directories. The bus is a JSONL file. The catalog is a public GitHub repo. No databases, no vendor lock, no surprises.
3. A growing **catalog** of self-improvement modules, every one designed under the same standard so they integrate automatically — including features absorbed from third-party open-source projects via `sz absorb`.

## The pain System Zero solves

When a developer asks an LLM to absorb a feature from an open-source repo into their own, the LLM does the wiring once. A week later they absorb a second feature. The second feature does not know the first feature exists. The first feature does not learn the second one arrived. After ten absorptions the repo is a tangle. S0 makes every absorption obey one protocol so all features stay composable forever — *and* gives the repo a heartbeat in the same install so everything actually runs.

## Distribution channels (everything ships in v0.1)

| Channel | Audience | Command |
|---|---|---|
| `curl \| sh` bootstrap | Any Mac / Linux | `curl -sSL https://systemzero.dev/i \| sh` |
| pip | Python devs | `pipx install system-zero` |
| npm | JS/TS devs | `npm i -g system-zero` |
| brew (post-launch) | Mac power users | `brew install system-zero` (formula in brew tap) |
| API | Programmatic / cloud | `https://api.systemzero.dev/v1/...` |
| Web (one-click) | Non-CLI | `systemzero.dev` → "Install on this repo" → copies command |

Every channel installs the same `sz` CLI and points at the same hosted catalog by default.

## Business shape (covered in phase 10)

| Tier | Price | What you get |
|---|---|---|
| Free | $0 | Protocol + CLI + 5 default modules + public catalog + local-only |
| Pro | $19/mo | Hosted catalog dashboard + private modules + cloud backup of `.sz/` + priority absorb queue (we host the LLM call) + telemetry opt-in |
| Team | $49/mo/seat | Everything in Pro + shared module library across teammates + audit log + SSO (Google/Microsoft) + 99.9% SLA on the API |

Stripe collects payment; Fly.io hosts the cloud platform; the protocol stays open-source forever.

## Reading order

1. `GLOSSARY.md` — terms used everywhere. Read this first.
2. `EXECUTION_RULES.md` — invariants GPT-5.4 must obey on every phase (29 rules + Appendix A bypass policy). **The bypass policy in Appendix A is authoritative for "what to do when a step would otherwise fail" during an overnight run.**
3. `PROTOCOL_SPEC.md` — the v0.1 protocol itself. Source of truth for all phases.
4. `ARCHITECTURE.md` — visual and verbal architecture.
5. Phase folders, in order: `phase-00` through `phase-16`. Do not skip phases. Do not reorder.

## CLI and package naming

- **Package name** on PyPI and npm: `system-zero` (both available at plan time).
- **CLI binary**: `sz` (short, unambiguous; `s0` is already in use on this machine by an existing agent).
- **Python module**: `sz`.
- **Runtime directory**: `.sz/` in user repos.
- **Repo config**: `.sz.yaml`.
- **Env vars** exported to modules: `SZ_*` prefix.

## Phase index

| Phase | Name | One-line goal |
|---|---|---|
| 00 | Prerequisites | Verify environment + every credential present in `.env` (OpenAI, Groq, Stripe×3, Hostinger, Fly.io, Supabase, Clerk, Resend, PostHog, PyPI). |
| 01 | Protocol spec | Freeze the v0.1 protocol as a versioned spec document, including Repo Genesis, Adopt-host, Merge-host. |
| 02 | sz CLI | Build the `sz` command-line tool and `system-zero` Python package. |
| 03 | Universal interfaces | Implement the seven sockets every module plugs into. Add Groq to LLM provider list. |
| 04 | Reconciliation engine | Implement the auto-rewiring loop that runs when modules are added/removed/upgraded. |
| 05 | Host adapters + 3 modes | Install-mode, Adopt-mode, Merge-mode. Add generic heartbeat detection that works for unknown frameworks. Always offer our heartbeat as an option. |
| 06 | Absorb workflow | Build `sz absorb <source>` that wraps any open-source feature as a constrained, schema-validated SZ module. |
| 07 | Repo Genesis | The "becomes alive" moment. One Constrained LLM Call. Test-only profile override lives under `tests/`, not shipped. |
| 08 | Port first seven modules | heartbeat, immune, subconscious, dreaming, metabolism, endocrine, prediction. |
| 09 | Catalog + distribution | Public GitHub catalog + `system-zero` on PyPI + npm wrapper + curl install bootstrap + brew formula stub. |
| 10 | Cloud + billing | Fly.io app; **Supabase** for DB; **Clerk** for auth; **Resend** for email; **Stripe** for billing; **Hostinger** for DNS (the only DNS); **PostHog** for opt-in telemetry. Network-effect data pipeline in place from day 1. |
| 11 | Website | A non-standard living-organism site at systemzero.dev + system0.dev. Clerk widget for upgrade. Pricing is temporary; value prop is network-effect intelligence. |
| 12 | Test on STATIC template repo | Install sz; verify it becomes alive. Must install ≥ 3 connection-engine-derived modules + ≥ 1 absorbed open-source module, all working together. |
| 13 | Test on DYNAMIC template repo | Repo with built-in mini-heartbeat. Test all three modes: Install (offer our heartbeat), Adopt (use existing), Merge (run both). Same ≥3 CE + ≥1 OS requirement. |
| 14 | Test absorbing OS features | Absorb three real features from three real GitHub repos and verify they integrate with the already-installed modules. |
| 15 | Launch | pip publish + npm publish + Fly.io deploy + DNS cutover + GitHub release + announcement. |
| 16 | **Reconstruct connection-engine (anonymized)** | After everything else passes, use `sz absorb` to re-derive every module of connection-engine, each as its own module repo. Produce a public, anonymized `connection-engine-reference` repo that demonstrates the full self-improvement stack assembled entirely via the SZ protocol. |

## Monetization thesis

Pricing is $0 Free / $19 Pro / $49 Team for now; these numbers will be revised after launch. The real value is **network effect plus centralized learning plus redistribution**:

1. Every opt-in Pro/Team install anonymously contributes: which modules were recommended by Genesis, which absorptions succeeded, which module pairs bind most often, which setpoints converge over time.
2. Our cloud aggregates and learns: better Genesis recommendations, better module ranking, better absorb prompts, better defaults.
3. Every user — including Free tier — receives improvements back through catalog updates, better default setpoints, and an optional `sz insights` command that reveals trending modules, common failure patterns, setpoint distributions across the community.
4. Pro/Team adds *private* data aggregation for the team's own corpus.

The pipeline for that collection + learning + redistribution is built into phase 10 from day 1, gated by opt-in. The pricing is the lever, not the moat. The moat is the data network effect.

## Definition of done for the whole plan

System Zero v0.1 is releasable when:

1. All 17 phase plans are completed and their acceptance criteria pass.
2. A new user can, on a fresh machine, run any of:
   - `curl -sSL https://systemzero.dev/i | sh`
   - `pipx install system-zero`
   - `npm i -g system-zero`
   - Visit `systemzero.dev`, click "Install on this repo", paste the printed command.
   …and end up with a working `sz` command that initializes their repo, runs Repo Genesis, installs the recommended modules, and the repo demonstrably runs autonomously and self-improves.
3. Both test template repos (static and dynamic) demonstrably "become alive" with measurable evidence on the bus. Each test uses ≥ 3 connection-engine-derived modules plus ≥ 1 absorbed open-source feature, all working together through the protocol.
4. `sz absorb` produces conformant modules from at least three real open-source repos and they integrate with the previously installed modules without breakage.
5. Phase 16 produces an anonymized reconstructed connection-engine repo that boots, passes its own conformance suite, and has zero references to specific user identity.
6. Stripe checkout works; Pro tier features (cloud catalog mirror, priority absorb, `sz insights`) are reachable; Free tier remains fully usable offline.
7. systemzero.dev and system0.dev both resolve to the website; api.systemzero.dev serves the catalog + billing endpoints.

## What this plan deliberately does not include in v0.1

- Windows native support (WSL works).
- A signed-module / supply-chain layer (catalog is curated; signatures are v0.2).
- Vector search inside `memory` (provider plug-in interface ships, no default provider).
- A native mobile app.
- Module sandboxing beyond subprocess isolation (full sandboxing v0.2).

These are explicit non-goals. GPT-5.4 must not invent them.
