# System Zero

**pip installs packages. S0 installs behaviors.**

System Zero is an open protocol and CLI for installing autonomous, event-driven modules into a repository. Modules get shared memory, an event bus, scheduling, lifecycle hooks, discovery, storage, and a constrained LLM interface so they can live inside a codebase without becoming one-off scripts.

```bash
curl -sSL https://systemzero.dev/i | sh
cd your-repo
sz init
```

## Install

```bash
# Recommended
curl -sSL https://systemzero.dev/i | sh

# Python package
pipx install sz-cli
pip install sz-cli
```

Then:

```bash
sz init
sz list
sz doctor
sz bus tail
```

## What Is In This Repo

- `sz/` contains the Python CLI and protocol runtime.
- `modules/` contains bundled modules that can be installed into a repo.
- `catalog/` contains the public module catalog metadata.
- `spec/` contains the public protocol schemas.
- `npm-wrapper/` contains the thin npm launcher package.
- `install.sh` is the curl installer.

Internal launch plans, tests, cloud deployment code, website source, build reports, and recovery tooling are intentionally kept out of this public repo. They live in the private build workspace so users see the protocol and installable artifacts instead of the overnight machinery that produced them.
