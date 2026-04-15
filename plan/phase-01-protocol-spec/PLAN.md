# Phase 01 — Freeze the Protocol Spec

## Goal

Convert the human-readable `PROTOCOL_SPEC.md` into machine-checkable artifacts: JSON Schemas for every YAML/JSON file S0 touches, an event-type registry, the LLM-response schemas (Constrained LLM Call discipline), and a conformance test harness skeleton.

## Inputs

- Phase 00 complete.
- `/Users/avi/Documents/Projects/system0-natural/plan/PROTOCOL_SPEC.md` exists and is committed.

## Outputs

- `spec/v0.1.0/manifest.schema.json` — JSON Schema for `module.yaml`.
- `spec/v0.1.0/repo-config.schema.json` — JSON Schema for `.sz.yaml`.
- `spec/v0.1.0/bus-event.schema.json` — JSON Schema for a single bus event.
- `spec/v0.1.0/registry.schema.json` — JSON Schema for `.sz/registry.json`.
- `spec/v0.1.0/repo-profile.schema.json` — JSON Schema for `.sz/repo-profile.json`.
- `spec/v0.1.0/llm-responses/repo-genesis.schema.json` — CLC response schema.
- `spec/v0.1.0/llm-responses/absorb-draft.schema.json` — CLC response schema.
- `spec/v0.1.0/reserved-events.yaml`.
- `spec/v0.1.0/host-capabilities.yaml`.
- `spec/v0.1.0/CHANGELOG.md`.
- `tools/validate-spec.py` — script that validates a given file against a given schema.
- Current-branch git checkpoint history that records the initial freeze and any required reconciliation commits without any branch operations.

## Atomic steps

### Step 1.1 — Confirm current branch and stay on it

```bash
git branch --show-current
```

Verify: prints the current branch name; do not create, switch, rename, or delete any branch during this phase.

### Step 1.2 — Make spec directories

```bash
mkdir -p spec/v0.1.0/llm-responses tools tests/spec
```

### Step 1.3 — Write `spec/v0.1.0/manifest.schema.json`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://systemzero.dev/spec/v0.1.0/manifest.schema.json",
  "title": "S0 Module Manifest",
  "type": "object",
  "required": ["id", "version", "category", "description", "entry"],
  "additionalProperties": false,
  "properties": {
    "id":         { "type": "string", "pattern": "^[a-z][a-z0-9-]{2,40}$" },
    "version":    { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+(-[A-Za-z0-9.-]+)?$" },
    "category":   { "type": "string", "minLength": 1, "maxLength": 50 },
    "description":{ "type": "string", "minLength": 1, "maxLength": 200 },
    "entry": {
      "type": "object", "required": ["type", "command"], "additionalProperties": false,
      "properties": {
        "type":    { "enum": ["python", "bash", "node", "binary"] },
        "command": { "type": "string", "minLength": 1 },
        "args":    { "type": "array", "items": { "type": "string" } }
      }
    },
    "triggers": {
      "type": "array",
      "items": {
        "oneOf": [
          { "type": "object", "required": ["on"], "additionalProperties": false,
            "properties": { "on": { "const": "tick" } } },
          { "type": "object", "required": ["on", "match"], "additionalProperties": false,
            "properties": { "on": { "const": "event" }, "match": { "type": "string" } } },
          { "type": "object", "required": ["cron"], "additionalProperties": false,
            "properties": { "cron": { "type": "string" } } }
        ]
      }
    },
    "provides": {
      "type": "array",
      "items": {
        "type": "object", "required": ["name"], "additionalProperties": false,
        "properties": {
          "name":        { "type": "string", "pattern": "^[a-z][a-z0-9.-]*[a-z0-9]$" },
          "address":     { "type": "string" },
          "description": { "type": "string" }
        }
      }
    },
    "requires": {
      "type": "array",
      "items": {
        "oneOf": [
          { "type": "object", "required": ["name"], "additionalProperties": false,
            "properties": {
              "name":       { "type": "string", "pattern": "^[a-z][a-z0-9.-]*[a-z0-9]$" },
              "optional":   { "type": "boolean", "default": false },
              "on_missing": { "enum": ["warn", "error"], "default": "warn" }
            }
          },
          { "type": "object", "required": ["providers"], "additionalProperties": false,
            "properties": { "providers": { "type": "array", "items": { "enum": ["llm", "vector", "memory", "bus", "storage", "schedule", "discovery"] } } }
          }
        ]
      }
    },
    "setpoints": {
      "type": "object",
      "patternProperties": {
        "^[a-z][a-z0-9_]*$": {
          "type": "object", "required": ["default"], "additionalProperties": false,
          "properties": {
            "default":     {},
            "range":       { "type": "array", "minItems": 2, "maxItems": 2 },
            "enum":        { "type": "array", "minItems": 1 },
            "description": { "type": "string" },
            "mode":        { "enum": ["simple", "advanced"], "default": "simple" }
          },
          "oneOf": [{ "required": ["range"] }, { "required": ["enum"] }]
        }
      },
      "additionalProperties": false
    },
    "hooks": {
      "type": "object", "additionalProperties": false,
      "properties": {
        "install":   { "type": "string" },
        "start":     { "type": "string" },
        "stop":      { "type": "string" },
        "uninstall": { "type": "string" },
        "reconcile": { "type": "string" },
        "doctor":    { "type": "string" }
      }
    },
    "requires_host": { "type": "array", "items": { "type": "string" } },
    "conflicts":     { "type": "array", "items": { "type": "string" } },
    "limits": {
      "type": "object", "additionalProperties": false,
      "properties": {
        "max_runtime_seconds": { "type": "integer", "minimum": 1, "maximum": 3600 },
        "max_memory_mb":       { "type": "integer", "minimum": 1, "maximum": 65536 }
      }
    },
    "personas":  { "type": "array", "items": { "enum": ["static", "dynamic"] } },
    "sz":        { "type": "string" }
  }
}
```

Verify: `python3 -c "import json; json.load(open('spec/v0.1.0/manifest.schema.json'))"` exits 0.

### Step 1.4 — Write `spec/v0.1.0/repo-config.schema.json`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://systemzero.dev/spec/v0.1.0/repo-config.schema.json",
  "title": "S0 Repo Config",
  "type": "object",
  "required": ["sz_version", "host", "modules"],
  "additionalProperties": false,
  "properties": {
    "sz_version": { "type": "string" },
    "host": { "enum": ["claude_code", "cursor", "opencode", "aider", "hermes", "openclaw", "metaclaw", "connection_engine", "generic"] },
    "host_mode": { "enum": ["install", "adopt", "merge"] },
    "modules": {
      "type": "object",
      "patternProperties": {
        "^[a-z][a-z0-9-]{2,40}$": {
          "type": "object", "additionalProperties": false,
          "properties": {
            "version":     { "type": "string" },
            "enabled":     { "type": "boolean", "default": true },
            "setpoints":   { "type": "object" },
            "bindings":    { "type": "object", "additionalProperties": { "type": "string" } },
            "quiet_hours": { "type": "array", "items": { "type": "string", "pattern": "^[0-9]{2}:[0-9]{2}-[0-9]{2}:[0-9]{2}$" } }
          }
        }
      },
      "additionalProperties": false
    },
    "providers": {
      "type": "object", "additionalProperties": false,
      "properties": {
        "llm":    { "type": "string" },
        "vector": { "type": "string" }
      }
    },
    "cloud": {
      "type": "object", "additionalProperties": false,
      "properties": {
        "tier":      { "enum": ["free", "pro", "team"] },
        "endpoint":  { "type": "string", "format": "uri" },
        "telemetry": { "type": "boolean" }
      }
    }
  }
}
```

### Step 1.5 — Write `spec/v0.1.0/bus-event.schema.json`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://systemzero.dev/spec/v0.1.0/bus-event.schema.json",
  "title": "S0 Bus Event",
  "type": "object",
  "required": ["ts", "module", "type", "payload"],
  "additionalProperties": false,
  "properties": {
    "ts":             { "type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]+)?Z$" },
    "module":         { "type": "string", "pattern": "^[a-z][a-z0-9-]{2,40}$|^s0$" },
    "type":           { "type": "string", "pattern": "^[a-z][a-z0-9._-]*[a-z0-9]$" },
    "payload":        { "type": "object" },
    "correlation_id": { "type": "string", "pattern": "^[a-f0-9-]{8,64}$" }
  }
}
```

### Step 1.6 — Write `spec/v0.1.0/registry.schema.json`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://systemzero.dev/spec/v0.1.0/registry.schema.json",
  "title": "S0 Capability Registry",
  "type": "object",
  "required": ["generated_at", "modules", "bindings", "unsatisfied"],
  "additionalProperties": false,
  "properties": {
    "generated_at": { "type": "string" },
    "modules": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "required": ["version", "status", "manifest_path"],
        "properties": {
          "version":       { "type": "string" },
          "status":        { "enum": ["healthy", "degraded", "unsatisfied", "disabled"] },
          "manifest_path": { "type": "string" },
          "provides":      { "type": "array", "items": { "type": "string" } },
          "requires":      { "type": "array", "items": { "type": "string" } }
        }
      }
    },
    "bindings": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["requirer", "capability", "provider", "address"],
        "properties": {
          "requirer":   { "type": "string" },
          "capability": { "type": "string" },
          "provider":   { "type": "string" },
          "address":    { "type": "string" }
        }
      }
    },
    "unsatisfied": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["requirer", "capability"],
        "properties": {
          "requirer":   { "type": "string" },
          "capability": { "type": "string" },
          "severity":   { "enum": ["warn", "error"] }
        }
      }
    }
  }
}
```

### Step 1.7 — Write `spec/v0.1.0/repo-profile.schema.json` (NEW)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://systemzero.dev/spec/v0.1.0/repo-profile.schema.json",
  "title": "S0 Repo Profile",
  "type": "object",
  "required": ["purpose", "language", "frameworks", "existing_heartbeat", "goals", "recommended_modules", "risk_flags"],
  "additionalProperties": false,
  "properties": {
    "purpose":        { "type": "string", "minLength": 1, "maxLength": 200 },
    "language":       { "enum": ["python", "javascript", "typescript", "go", "rust", "ruby", "java", "kotlin", "swift", "php", "shell", "mixed", "other"] },
    "frameworks":     { "type": "array", "items": { "type": "string" } },
    "existing_heartbeat": { "enum": ["none", "claude_code", "cursor", "opencode", "aider", "hermes", "openclaw", "metaclaw", "connection_engine", "custom", "unknown"] },
    "goals":          { "type": "array", "minItems": 1, "maxItems": 5, "items": { "type": "string", "maxLength": 200 } },
    "recommended_modules": {
      "type": "array", "minItems": 1, "maxItems": 10,
      "items": {
        "type": "object", "required": ["id", "reason"], "additionalProperties": false,
        "properties": {
          "id":     { "type": "string", "pattern": "^[a-z][a-z0-9-]{2,40}$" },
          "reason": { "type": "string", "maxLength": 100 }
        }
      }
    },
    "risk_flags":     { "type": "array", "items": { "type": "string", "maxLength": 100 } }
  }
}
```

### Step 1.8 — Write `spec/v0.1.0/llm-responses/repo-genesis.schema.json` (NEW)

This is identical in shape to `repo-profile.schema.json`; the LLM emits the profile directly.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://systemzero.dev/spec/v0.1.0/llm-responses/repo-genesis.schema.json",
  "$ref": "https://systemzero.dev/spec/v0.1.0/repo-profile.schema.json"
}
```

### Step 1.9 — Write `spec/v0.1.0/llm-responses/absorb-draft.schema.json` (NEW)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://systemzero.dev/spec/v0.1.0/llm-responses/absorb-draft.schema.json",
  "title": "S0 Absorb Draft",
  "type": "object",
  "required": ["module_id", "description", "category", "entry", "triggers", "provides", "requires", "setpoints", "files_to_copy", "entry_script", "reconcile_script"],
  "additionalProperties": false,
  "properties": {
    "module_id":   { "type": "string", "pattern": "^[a-z][a-z0-9-]{2,40}$" },
    "description": { "type": "string", "minLength": 1, "maxLength": 200 },
    "category":    { "type": "string", "minLength": 1, "maxLength": 50 },
    "entry": {
      "type": "object", "required": ["type", "command"], "additionalProperties": false,
      "properties": {
        "type":    { "enum": ["python", "bash", "node", "binary"] },
        "command": { "type": "string" },
        "args":    { "type": "array", "items": { "type": "string" } }
      }
    },
    "triggers": { "type": "array", "minItems": 1 },
    "provides": { "type": "array" },
    "requires": { "type": "array" },
    "setpoints":{ "type": "object" },
    "files_to_copy": {
      "type": "array",
      "items": {
        "type": "object", "required": ["from", "to"], "additionalProperties": false,
        "properties": {
          "from": { "type": "string" },
          "to":   { "type": "string" }
        }
      }
    },
    "entry_script":     { "type": "string", "minLength": 1 },
    "reconcile_script": { "type": "string", "minLength": 1 },
    "notes":            { "type": "string" }
  }
}
```

### Step 1.10 — Write `spec/v0.1.0/reserved-events.yaml`

```yaml
reserved:
  - module.installed
  - module.uninstalled
  - module.upgraded
  - module.reconciled
  - module.errored
  - reconcile.started
  - reconcile.finished
  - capability.unsatisfied
  - capability.ambiguous
  - tick
  - repo.genesis.completed
  - host.adopted
  - host.session.started
  - host.session.ended
  - host.commit.made
  - host.edit.committed
  - llm.call.failed
```

### Step 1.11 — Write `spec/v0.1.0/host-capabilities.yaml`

```yaml
capabilities:
  - id: clock_only
    description: Host can fire the heartbeat at intervals.
  - id: commit_events
    description: Host emits events when commits land.
  - id: session_lifecycle
    description: Host emits start/end events for an interactive session.
  - id: edit_events
    description: Host emits events on each file save.
  - id: command_palette
    description: Host can register user-visible commands.
  - id: external_heartbeat
    description: Host already runs a daemon; S0 adopts its pulse rather than installing a second one.
adapters:
  - host: generic
    mode: install
    provides: [clock_only, commit_events]
  - host: claude_code
    mode: install
    provides: [clock_only, commit_events, session_lifecycle, command_palette]
  - host: cursor
    mode: install
    provides: [clock_only, commit_events, edit_events, command_palette]
  - host: opencode
    mode: install
    provides: [clock_only, commit_events, session_lifecycle]
  - host: aider
    mode: install
    provides: [clock_only, commit_events, session_lifecycle]
  - host: hermes
    mode: adopt
    provides: [external_heartbeat, session_lifecycle]
  - host: openclaw
    mode: adopt
    provides: [external_heartbeat, session_lifecycle]
  - host: metaclaw
    mode: adopt
    provides: [external_heartbeat, session_lifecycle]
  - host: connection_engine
    mode: adopt
    provides: [external_heartbeat, session_lifecycle]
```

### Step 1.12 — Write `spec/v0.1.0/CHANGELOG.md`

```markdown
# S0 Spec Changelog

## v0.1.0 — initial freeze

- Manifest schema (`module.yaml`).
- Repo config schema (`.sz.yaml`).
- Bus event schema.
- Capability registry schema.
- Repo profile schema (Repo Genesis output).
- LLM-response schemas: repo-genesis, absorb-draft.
- Reserved event registry.
- Host capability registry, including Adopt-mode adapters.
```

### Step 1.13 — Write `tools/validate-spec.py`

```python
#!/usr/bin/env python3
"""Validate a YAML or JSON file against an S0 JSON Schema.

Usage:
  tools/validate-spec.py <schema.json> <data.yaml|.json>
"""
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


def load(path: Path):
    text = path.read_text()
    if path.suffix in {".yaml", ".yml"}:
        return yaml.safe_load(text)
    return json.loads(text)


def main(schema_path: str, data_path: str) -> int:
    schema = json.loads(Path(schema_path).read_text())
    data = load(Path(data_path))
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(data))
    if errors:
        for e in errors:
            print(f"ERROR at {list(e.absolute_path)}: {e.message}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
```

`chmod +x tools/validate-spec.py`.

### Step 1.14 — Fixtures, one per schema

Create `tests/spec/fixtures/manifest-minimal.yaml`, `manifest-full.yaml`, `repo-config.yaml`, `bus-event.json`, `registry.json`, `repo-profile.json`, `absorb-draft.json`. Use the same content patterns as the previous spec frozen for sz, with these adjustments:

- `repo-config.yaml`: include `cloud: {tier: free}` and `host_mode: install`.
- `manifest-full.yaml`: include `personas: [static, dynamic]`.
- `repo-profile.json`: a complete profile with all required fields populated for a Python/FastAPI fixture.
- `absorb-draft.json`: a minimal valid draft.

### Step 1.15 — Validate every fixture

```bash
tools/validate-spec.py spec/v0.1.0/manifest.schema.json     tests/spec/fixtures/manifest-minimal.yaml
tools/validate-spec.py spec/v0.1.0/manifest.schema.json     tests/spec/fixtures/manifest-full.yaml
tools/validate-spec.py spec/v0.1.0/repo-config.schema.json  tests/spec/fixtures/repo-config.yaml
tools/validate-spec.py spec/v0.1.0/bus-event.schema.json    tests/spec/fixtures/bus-event.json
tools/validate-spec.py spec/v0.1.0/registry.schema.json     tests/spec/fixtures/registry.json
tools/validate-spec.py spec/v0.1.0/repo-profile.schema.json tests/spec/fixtures/repo-profile.json
tools/validate-spec.py spec/v0.1.0/llm-responses/absorb-draft.schema.json tests/spec/fixtures/absorb-draft.json
```

Verify: every invocation prints `OK`.

### Step 1.16 — Verify the current-branch checkpoint history

```bash
git log --oneline --grep '^phase 01:' -n 5
```

Verify: the current branch contains `phase 01: protocol spec frozen at v0.1.0`, followed by any reconciliation commit(s) needed to align the frozen artifacts and source-of-truth docs. No branch creation, switching, renaming, or deletion occurred.

## Acceptance criteria

1. All seven JSON Schemas exist, parse, and validate their fixtures.
2. `spec/v0.1.0/CHANGELOG.md` exists with the v0.1.0 entry.
3. `tools/validate-spec.py` is executable and prints `OK` for the seven fixtures.
4. The current branch contains the phase 01 checkpoint history, including `phase 01: protocol spec frozen at v0.1.0` and any required reconciliation commit(s), with no branch operations performed.

## Failure modes and recovery

| Symptom | Cause | Action |
|---|---|---|
| Schema does not parse | typo | re-paste from the plan; do not "fix" by trial-and-error |
| Fixture validation fails | drift | match fixture to spec; never relax the schema to make a fixture pass |
| `jsonschema` not found | phase 00 skipped | Stop, run phase 00, retry |

## Rollback

`rm -rf spec tools tests/spec`.
