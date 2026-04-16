# S0 absorb prompt

You are wrapping an open-source feature as an S0 (System Zero) module. Your output must be JSON only. No prose, no markdown fences.

## Source repository inventory

URL: {{SOURCE_URL}}
Ref: {{SOURCE_REF}}

Top-level layout:
{{LAYOUT}}

Selected file contents (truncated):
{{FILES}}

## Feature requested

The user wants to absorb the feature called: **{{FEATURE_NAME}}**.

## S0 v0.1 protocol summary (NORMATIVE)

Modules talk to each other only through these interfaces, exposed as `s0 <verb>` shell commands:
- `sz bus emit <type> <json>` and `sz bus subscribe <module-id> <pattern>`
- `sz memory get/set <key>`, `sz memory append <stream> <json>`
- `sz llm invoke --prompt-file <file>`
- `sz discovery resolve <capability>`, `sz discovery providers <capability>`

A module is a directory with one `module.yaml` and at minimum an `entry` script. `provides` declares capabilities other modules can require. `requires` declares capabilities this module needs (use `optional: true` if soft).

The reconcile script reads `$SZ_REGISTRY_PATH` (a JSON file) to learn about other installed modules and re-bind. It must be idempotent and must not modify anything outside `$SZ_MODULE_DIR`.

Absorption is not permission to blindly run a foreign repository on every tick. Prefer a small protocol adapter that copies the minimal source evidence, exposes the feature through bus/memory/task artifacts, and only executes expensive or environment-specific commands after an explicit setpoint opt-in.

Absorption must still preserve the source repository's real behavior. Identify the safest executable commands or entry points that actually perform the requested feature. The runtime will preserve the full bounded source tree under `source_repo/`, normalize your proposed behavior actions, and only run them when `execution_mode=execute`.

## Output schema (the runtime validates this; do not deviate)

Output a single JSON object with these exact keys:

{
  "module_id":   "<kebab-case>",            # 3..40 chars, [a-z0-9-]
  "description": "<one line>",
  "category":    "<short tag>",
  "entry":       {"type":"python|bash|node","command":"<rel path>","args":[]},
  "triggers":    [{"on":"tick"} | {"on":"event","match":"<glob>"} | {"cron":"<5 fields>"}],
  "provides":    [{"name":"<dotted.lowercase>","address":"<events:type|memory:key|<rel path>>","description":"<one line>"}],
  "requires":    [{"name":"<dotted.lowercase>","optional":bool,"on_missing":"warn|error"} | {"providers":["llm","memory","bus","storage","schedule","discovery"]}],
  "setpoints":   {"<name>":{"default":<v>,"range":[min,max]|"enum":[...],"description":"<one line>"}},
  "files_to_copy":[{"from":"<path-in-source>","to":"<path-in-module>"}],
  "behavior":    {"actions":[{"name":"<snake_case>","description":"<what external behavior this runs>","command":["<argv0>","<arg1>"],"cwd":"source_repo","timeout_seconds":60,"output_globs":["*.log","results/**"]}]},
  "entry_script":"<full text of entry file>",
  "reconcile_script":"<full bash script content>",
  "notes":"<short text on decisions>"
}

Hard constraints (the runtime enforces):
- Every `files_to_copy.from` must reference a path in the inventory. No invented paths.
- The `entry_script` invokes, wraps, or exposes the absorbed source through a protocol-native adapter; it must not re-implement the feature from scratch.
- Do not set `entry.command` to a copied source file such as `train.py`; use an adapter entry point such as `entry.py`.
- `behavior.actions` should name real source behavior: test command, build command, CLI command, training command, harness command, or documented run command. Do not invent commands absent from the inventory or selected contents.
- String setpoints must include an `enum`; numeric setpoints must include a `range`.
- Prefer `{"providers":["bus","memory","discovery"]}` for universal S0 interfaces rather than invented required capability names such as `bus.events`.
- The `reconcile_script` must:
  - Read `$SZ_REGISTRY_PATH`.
  - For each `requires.name`, query `sz discovery resolve <name>` and write the result to `$SZ_MODULE_DIR/runtime.json`.
  - Be idempotent: two consecutive runs produce the same `runtime.json`.
- Output JSON only. No fences. No surrounding text.
