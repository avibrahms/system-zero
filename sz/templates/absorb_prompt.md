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
  "entry_script":"<full text of entry file>",
  "reconcile_script":"<full bash script content>",
  "notes":"<short text on decisions>"
}

Hard constraints (the runtime enforces):
- Every `files_to_copy.from` must reference a path in the inventory. No invented paths.
- The `entry_script` invokes or wraps the absorbed source; it must not re-implement it.
- The `reconcile_script` must:
  - Read `$SZ_REGISTRY_PATH`.
  - For each `requires.name`, query `sz discovery resolve <name>` and write the result to `$SZ_MODULE_DIR/runtime.json`.
  - Be idempotent: two consecutive runs produce the same `runtime.json`.
- Output JSON only. No fences. No surrounding text.
