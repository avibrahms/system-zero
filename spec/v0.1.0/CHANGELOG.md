# S0 Spec Changelog

## v0.1.0 - initial freeze

- Manifest schema (`module.yaml`).
- Repo config schema (`.sz.yaml`).
- Bus event schema.
- Capability registry schema.
- Repo profile schema (Repo Genesis output).
- LLM-response schemas: repo-genesis, absorb-draft.
- Reserved event registry.
- Host capability registry, including Adopt-mode adapters.
- Clarified the normative failure event name as `module.errored` across the source-of-truth docs and frozen artifacts.
- Reconciled the source-of-truth docs with the frozen v0.1.0 artifacts for `host_mode: merge` and the Repo Genesis CLC schema path.
- Reconciled phase verification with the spec-loop current-branch workflow so phase checkpoints are verified without any branch operations.
- Added `groq` to the v0.1 shipped LLM provider list for phase 03 universal interfaces.
- Allowed capability version ranges in manifest capability names so `requires` / `provides` entries can use `name@range` contracts.
- Added `unknown` as a repo-config host for phase 05 generic heartbeat detection.
