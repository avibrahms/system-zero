# System Zero

[![PyPI](https://img.shields.io/pypi/v/sz-cli?style=for-the-badge&label=PyPI)](https://pypi.org/project/sz-cli/)
[![Python](https://img.shields.io/pypi/pyversions/sz-cli?style=for-the-badge)](https://pypi.org/project/sz-cli/)
[![Website](https://img.shields.io/badge/website-systemzero.dev-0f766e?style=for-the-badge)](https://systemzero.dev)
[![Protocol](https://img.shields.io/badge/protocol-S0%20v0.1.0-111827?style=for-the-badge)](PROTOCOL_SPEC.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue?style=for-the-badge)](LICENSE)
[![Stars](https://img.shields.io/github/stars/avibrahms/system-zero?style=for-the-badge)](https://github.com/avibrahms/system-zero/stargazers)

`agentic-ai` · `autonomous-agents` · `repository-automation` · `developer-tools` · `llm` · `protocol` · `cli`

**pip installs packages. S0 installs behaviors.**

System Zero is an open protocol that lets you plug independent, AI-powered modules into any code repository — so your codebase can monitor, maintain, and improve itself over time.

Think of it like a standard electrical outlet system. Instead of appliances plugging into wall sockets, autonomous modules plug into your repo through a fixed set of universal interfaces. Add a module, remove a module, swap one for another — the system rewires itself.

```bash
curl -sSL https://systemzero.dev/i | sh
cd your-repo
sz init
```

That's it. S0 scans your repo, figures out what it is, recommends modules, and installs a heartbeat. Your repo is alive.

---

## What this actually does

When you run `sz init`, three things happen:

1. **S0 scans your repo** — language, frameworks, structure, goals — and generates a profile.
2. **It recommends and installs modules** from the catalog (or custom sources). Each module declares what it provides and what it requires.
3. **It starts a heartbeat** — a recurring tick that wakes modules up periodically so they can do their work.

A module isn't passive code you call. It's a persistent, event-driven, LLM-capable agent that lives inside your repo. It wakes up, observes, decides, and acts — then goes back to sleep until the next trigger.

The pattern every module follows:

```
wake up → read state from memory → read events from bus →
maybe call an LLM with structured input/output →
write new state → emit events → go back to sleep
```

Modules don't talk to each other directly. They talk through seven universal interfaces. They declare capabilities ("I provide anomaly detection") and requirements ("I need code analysis"). When you add or remove a module, a reconciliation cycle rebuilds the capability graph and re-wires everything automatically. No configuration spaghetti.

---

## The seven universal interfaces

Every module talks to the rest of the world through exactly these interfaces. No exceptions.

**`memory`** — A key-value store, an append-only event log, and an optional vector index. Modules remember things across ticks. They track trends over time. This is what makes them stateful, not stateless.

**`bus`** — Append-only JSONL pub/sub. Modules emit events, subscribe by pattern. This is the nervous system — when something happens in one module, others can react.

**`llm`** — Vendor-agnostic LLM invocation. Anthropic, OpenAI, Groq, or a mock for offline testing. Modules never see the provider name. They just call `sz llm invoke` and get structured output back.

**`storage`** — Guaranteed filesystem paths. Each module gets its own private directory. Shared namespaces exist for modules that negotiate access through capabilities.

**`schedule`** — Cron-style triggers evaluated on every tick. Standard 5-field cron, plus `@tick`, `@hourly`, `@daily`, `@weekly`.

**`discovery`** — Live introspection. Query installed modules, capability providers, resolved bindings, health status. Modules can see the landscape they're part of.

**`lifecycle`** — Standard hooks: install, start, stop, reconcile, doctor, entry. Called at well-defined moments. Every module knows when it's being installed, when the landscape changes, when it's time to run.

---

## Why this matters — the real innovations

S0 is not a linter. It's not a CI/CD tool. It's not another dev framework. Here's what it actually brings that didn't exist before:

### It's a package manager for behaviors, not code

pip installs libraries. npm installs packages. S0 installs autonomous behaviors into a repository.

A `module.yaml` manifest is to autonomous behaviors what `package.json` is to JavaScript libraries. The `provides`/`requires` capability system is dependency injection for agents, not for functions. Nobody has a standard for "install an autonomous behavior into a repo the way you install a package." This is that standard.

### The Constrained LLM Call discipline

Every other system that uses LLMs treats them as magic black boxes — you send a prompt, you get text back, you hope it's useful.

S0 enforces something different. Every LLM call inside the protocol follows the CLC pattern:

1. **Templated prompt** — not ad-hoc strings, but versioned templates.
2. **Schema-validated response** — the LLM's output must conform to a JSON schema.
3. **Retry with structured feedback** — if validation fails, S0 retries up to 2 more times, appending the validation errors to the prompt.
4. **Logged to an audit trail** — every call is recorded in the `llm.calls` memory stream.

This is how LLMs should be used in infrastructure. Not "call GPT and hope." Structured input, structured output, validated, logged, auditable.

### The reconciliation cycle

When you add or remove a module, S0 doesn't just install files. It rebuilds the entire capability graph, resolves all bindings, and runs every module's `reconcile.sh` so they can adapt to the new landscape. The system configures itself.

This is reactive dependency injection. A module's `reconcile.sh` doesn't need to know which module triggered the cycle. It reads the resolved registry and adapts. Idempotent, deterministic, decoupled.

### Host-agnostic heartbeat

S0 doesn't care what development environment you use. Three modes at init time:

- **Install** — S0 runs its own heartbeat. Works anywhere.
- **Adopt** — Your repo already has an autonomous loop (Claude Code, Cursor, Aider, a custom daemon)? S0 hooks into it. No second pulse.
- **Merge** — Both heartbeats run. Deduplication is automatic.

A module written for S0 works identically in all three modes. It never assumes who fires its tick or how often.

---

## Where S0 sits

There are three protocols that matter for the agentic era:

- **MCP** standardizes how AI applications access tools and data sources.
- **A2A** standardizes how AI agents communicate with each other.
- **S0** standardizes how AI agents live inside and operate on a codebase.

MCP connects agents to the outside world. A2A connects agents to each other. S0 connects agents to a repository — giving them memory, events, scheduling, and lifecycle management so they can be useful residents, not one-shot visitors.

---

## How a module works

A module is a directory with two required things: a `module.yaml` manifest and an `entry` script.

```yaml
id: readme-keeper
version: 0.1.0
category: documentation
description: Keeps README in sync with actual API surface

entry:
  type: python
  command: entry.py

triggers:
  - on: event
    match: host.commit.made

provides:
  - name: docs.readme.sync
    address: bus:readme.updated
    description: Emits readme.updated when docs are refreshed

requires:
  - name: code.analysis
    optional: false
    on_missing: warn

setpoints:
  drift_threshold:
    default: 0.3
    range: [0.1, 0.9]
    description: How much drift before triggering a rewrite

hooks:
  reconcile: reconcile.sh
  doctor: doctor.sh
```

The entry script does the actual work. It reads memory, checks events, maybe calls an LLM, writes results. It uses the `sz` CLI or the Python helpers — never raw file access, never direct module-to-module imports.

Modules communicate through the bus and through capabilities. If module A provides `code.analysis` and module B requires it, S0 wires them together in `registry.json`. Module B reads the resolved address from the registry. If module A is swapped for module C (which also provides `code.analysis`), module B doesn't change — the reconciliation cycle updates the wiring.

---

## The absorb workflow

This is one of the most interesting things S0 can do.

```bash
sz absorb https://github.com/someone/useful-tool --feature linting --id smart-linter
```

S0 clones the external repo, inventories it, and makes a Constrained LLM Call to extract the specified feature into a proper S0 module — complete with manifest, entry script, and reconcile hook. It validates the result against the manifest schema, installs it through the standard path, and runs `sz doctor` to verify everything works.

It takes someone else's code and turns it into a pluggable behavior for your repo. The LLM does the extraction; the protocol ensures the output is valid and safe.

Critical rule: the absorb LLM never modifies files outside `.sz/<new-id>/` or `.sz.yaml`. It never patches other modules. Cross-module concerns are handled by the reconcile cycle.

---

## Install

```bash
# curl (recommended)
curl -sSL https://systemzero.dev/i | sh

# pipx / pip
pipx install sz-cli
pip install sz-cli

# npm
npm install -g system-zero
```

Then:

```bash
cd your-repo
sz init          # Repo Genesis — scans, recommends, installs
sz list          # See what's installed
sz doctor        # Health check
sz bus tail      # Watch the nervous system
```

---

## What's in this repo

```
sz/                  CLI source (Python, Click + Rich)
  commands/          All sz subcommands
  adapters/          Host adapters (generic, claude_code, cursor, etc.)
  templates/         Prompt templates for Constrained LLM Calls
spec/v0.1.0/         JSON schemas for manifests, LLM responses, registry
PROTOCOL_SPEC.md     Human-readable protocol source of truth
modules/             Built-in and example modules
catalog/             Public module catalog
npm-wrapper/         Thin npm launcher package
install.sh           Curl installer
```

---

## Design principles

**Non-destructive.** S0 never creates files outside `.sz/` and `.sz.yaml`. Your repo is yours. S0 is a guest.

**Idempotent.** Running `sz reconcile` twice produces identical results. Running `sz genesis` again is safe.

**Fail gracefully.** A module that crashes is marked `degraded` and skipped on subsequent ticks — other modules keep running. A module that fails to install leaves no trace. The bus tolerates corrupted entries by seeking past them.

**No vendor lock-in.** LLM provider is configurable. Host adapter is swappable. The protocol works fully offline with the `mock` provider. The cloud tier is optional — everything works locally without it.

**Modules are citizens, not plugins.** A module has its own memory, its own storage, its own lifecycle hooks. It's not a callback registered with a framework. It's an independent agent that happens to follow a shared protocol.

---

## Current status

**v0.1.0** — The protocol spec is stable. The CLI is functional. The catalog is young. This is the "the architecture is built, now we need tenants" stage.

What's here: the full protocol implementation, seven universal interfaces, the reconciliation engine, Repo Genesis, the absorb workflow, host adapters for generic, Claude Code, Cursor, OpenCode, Aider, and several autonomous frameworks.

What's needed: more modules. The protocol is only as useful as the behaviors you can install through it. If you build a module that does something genuinely useful — even something small — that's the most valuable contribution right now.

---

## Contributing

The most impactful thing you can do is **write a module**. Start with the [module manifest spec](spec/v0.1.0/manifest.schema.json), look at the example modules in `modules/`, and build something that makes a repo better at being itself.

If you want to work on the core:
- The CLI lives in `sz/commands/`
- Host adapters live in `sz/adapters/`
- The reconciliation engine is the heart of the system
- Integration and deployment tests live in the private build workspace for now; public test fixtures will be promoted as the protocol stabilizes.

File issues. Send PRs. Or just install S0 on a real repo, run `sz init`, and tell us what happened.

---

## License

Apache 2.0

---

*S0 is for repo behaviors what USB is for peripherals — one standard plug that any module can use.*
