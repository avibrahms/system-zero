# Execution Rules

These rules apply to every phase. GPT-5.4 must obey all of them at all times. Violations invalidate the phase.

## R1. Read the spec before writing code

Before writing any file in a phase, read `PROTOCOL_SPEC.md` and the current phase's `PLAN.md` end-to-end. Never start mid-phase.

## R2. Atomic steps, sequentially

Execute steps in the order they appear in the phase plan. Do not parallelize unless the plan explicitly says `PARALLEL OK`. Do not skip steps. Do not combine steps.

## R3. Verify after every step

Every step ends with a `Verify:` block listing one or more shell commands and their expected outputs. Run them. If any output deviates, do not proceed; jump to the step's `Recovery:` block.

## R4. Use exact paths

Every file path in the plan is absolute or repo-relative as written. Do not invent alternative paths. Do not move files between directories.

## R5. Use the scaffolds verbatim

When a step provides a scaffold (file content), copy it verbatim. Modify only the placeholders explicitly marked `<PLACEHOLDER>`. Do not refactor, simplify, or "improve" the scaffold.

## R6. No silent dependencies

If a step requires a tool, library, or environment variable not declared in `phase-00-prerequisites/PLAN.md`, stop and update phase 00 first.

## R7. No new global state

Never write outside the user's repo or the explicitly listed `~/.sz/` directory. Never modify `~/.bashrc`, `~/.zshrc`, `~/.gitconfig`, system PATH, or any global config not explicitly named.

## R8. Idempotent operations

Every install, init, and reconcile operation must be safe to run twice. The second run is a no-op or reports "already done." If a step is not naturally idempotent, wrap it in a guard.

## R9. Subprocess isolation

Module entry points run in subprocesses. They never share Python interpreters, never share variables, never share connections. Communicate only through the universal interfaces.

## R10. No direct module-to-module reads

A module never reads another module's files. If module A needs data from module B, A queries the bus, the memory layer, or the discovery socket. Never `cat ../module-b/state.json`.

## R11. All times in UTC, ISO-8601

Every timestamp written to disk is UTC ISO-8601 with `Z` suffix. No local times. No epochs.

## R12. All filenames lowercase, kebab-case

Files S0 creates are lowercase, kebab-case, with a single dotted extension. No camelCase, no spaces, no underscores in module IDs.

## R13. Logs go to JSONL

Every persistent log S0 writes is JSONL (one JSON object per line). No free-form text logs in the runtime layer.

## R14. Absolute imports only

Python files inside S0 use absolute imports (`from sz.core import ...`). No relative imports.

## R15. Errors are events

When something fails inside a tick, the failure is appended to the bus as a `module.error` event. Stack traces go to the module's private crash log, not the bus payload.

## R16. The bus is append-only

Never edit, truncate, or rewrite `.sz/bus.jsonl`. Rotation is performed by the metabolism module via copy-and-rename, not in-place truncation.

## R17. Confirm before destructive operations

Any operation that deletes user files (e.g. `sz uninstall`, `sz doctor --fix`) requires a `--confirm` flag or an interactive `[y/N]` prompt. The default is no.

## R18. Capability strings are immutable contracts

Once a capability name is published in the catalog, it cannot be renamed in a minor version. Adding a new capability is a minor version bump; renaming is a major version bump.

## R19. Telemetry is opt-in and absent on Free tier

S0 does not phone home unless the user is on Pro or Team tier AND has opted in. The Free tier never opens an outbound connection except when the user explicitly runs `sz install`, `sz absorb`, or `sz catalog`.

## R20. When in doubt, STOP_AND_REPORT

If a step's verification cannot be unambiguously interpreted as pass or fail, do not guess. Issue `STOP_AND_REPORT` with: which step, what command was run, what output was returned, what the plan expected.

## R21. Anti-laziness clause

Do not abbreviate file content, scaffolds, or tests with `...`, "and so on", or "TODO: similar pattern". If the plan asks for ten cases, write ten cases. If the plan asks for a 200-line file, write 200 lines.

## R22. Anti-reinvention clause

If two phases would reasonably need the same helper function, the helper is implemented once in `sz/core/util.py` and imported. No copy-paste of S0-internal code.

## R23. Anti-vendor clause

No phase plan, scaffold, or test in this folder may hardcode a specific LLM provider, IDE, or operating system beyond what is explicitly required by the host adapter being implemented. Default LLM provider is selected from the user's environment.

## R24. Commit boundaries

Each phase ends with a single git commit on a branch named `phase-NN-name`. Commit message: `phase NN: <name> complete`. Do not commit mid-phase. Do not squash phases.

## R25. Constrained LLM Call (CLC) discipline — spec-driven

Every LLM call inside S0 must obey four rules:

1. **Templated prompt**: the prompt text lives in a file under `sz/templates/`. The plan never inlines free-form prompts. Variables are substituted at call time with `{{NAME}}` placeholders.
2. **Schema-validated response**: the call declares a JSON Schema for its output, stored under `spec/v0.1.0/llm-responses/<call-name>.schema.json`. The response is validated before any side effect.
3. **Retry-on-mismatch**: if validation fails, the call retries up to 2 more times with the validation errors appended to the prompt as feedback. After 3 attempts, the call returns an error event on the bus and aborts the operation.
4. **Logged**: every CLC writes one record to memory stream `llm.calls` with `{template_id, response_hash, attempts, validation_status, model, tokens_in, tokens_out}`.

Plans that introduce a new LLM call MUST also add the prompt template, the response schema, and a unit test for at least one valid and one invalid response.

## R26. Algorithm-first rule

Before introducing an LLM call, the plan must show in writing that no deterministic algorithm can do the job at acceptable quality. If a regex, AST walk, dependency graph traversal, or shell command would suffice, that is preferred. LLM calls are a last resort because they are non-deterministic and expensive.

## R27. Two-persona test rule

Every phase that ships user-facing behavior must include at least one acceptance test against a Static-repo fixture and one against a Dynamic-repo fixture. If a feature only works on one persona, that is a phase-incomplete signal, not an acceptable trade-off.

## R28. Spec changes propagate

If a phase needs to change `PROTOCOL_SPEC.md`, `EXECUTION_RULES.md`, or any schema, the change must be made *before* the dependent code is written, in its own commit, with a one-line note in `spec/v0.1.0/CHANGELOG.md`. Code that diverges from the spec is reverted; the spec is never edited to match drifted code.

## R29. Bypass policy governs overnight runs

Summary of the rule each phase must obey (full policy is in Appendix A at the bottom of this file):

1. When a condition matches a soft-blocker row in Appendix A: apply the listed bypass, append to `BLOCKERS.md` at the repo root, update `.s0-release.json`, mark the phase `status: degraded`, advance to the next phase.
2. When a condition matches the hard-blocker list (7 entries only): halt the run with `status: hard_blocked` and emit `phase.hard_blocked` on the bus.
3. An unlisted failure mode is treated as a hard blocker. Never invent bypasses mid-run.

The verifier treats `status: degraded` as passing for advancement. Phase 15's final audit decides whether the accumulated degradation clears the "core-essentials green" bar defined in Appendix A.

Intent: unattended overnight runs produce maximum progress. The operator triages `BLOCKERS.md` in the morning.

---

# Appendix A — Bypass Policy (authoritative)

## Intent

The plan is designed to run unattended (e.g. `./bin/run-system0-overnight`). When a phase hits a condition it cannot satisfy, the default behavior is **bypass + annotate, keep going** — not halt. Only a small, explicitly enumerated set of conditions are allowed to halt the run.

## Two categories

| Category | Rule |
|---|---|
| **Hard blocker** | Halt the run. Write to `BLOCKERS.md`. Emit `phase.hard_blocked` on the bus. The operator must resolve before re-running. |
| **Soft blocker** | Apply the pre-defined bypass. Write to `BLOCKERS.md` with category `deferred`. Continue. Phase logs `status: degraded`. |

## The hard-blocker list (exhaustive; nothing else halts)

1. **No LLM provider reachable** — `OPENAI_API_KEY`, `GROQ_API_KEY`, and `ANTHROPIC_API_KEY` all absent AND the `mock` provider is disabled. `sz absorb` and Repo Genesis cannot function.
2. **`FLYIO_API_TOKEN` invalid** — cannot deploy any service.
3. **`SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` invalid** — cloud app cannot start.
4. **Python 3.10+ missing / core CLI tools missing** — phase 00 cannot complete bootstrap.
5. **Git repo corrupted or uncommittable** — phase-branch discipline (R24) cannot proceed.
6. **User explicitly set `S0_HARD_STOP=1`** — manual kill switch.
7. **Data-integrity violation inside the protocol itself** — e.g. `registry.json` schema validation fails after reconcile, or `bus.jsonl` corruption prevents future writes. These indicate a protocol bug, not an external failure.

Any other failure is a soft blocker.

## Soft-blocker bypass table

| Condition | Bypass | What downstream uses |
|---|---|---|
| `STRIPE_SECRET_KEY` starts with `sk_live_` AND `STRIPE_AUTO_CREATE != 1` | Skip product/price creation. `/v1/billing/checkout` returns 503 `billing_not_configured`. Website shows "Billing setup pending." | Catalog, absorb, telemetry still deploy. |
| Stripe returns 401/403 | Same as above. | Same. |
| `RESEND_API_KEY` missing / 401 / 403 | Skip Resend. Welcome emails queue to `cloud/outbox/<ts>-<email>.json` on Fly volume. Tier upgrade still fires. | Webhook works; email deferred. |
| `CLERK_SECRET_KEY` 401 OR `CLERK_JWKS_URL` unresolvable | Skip Clerk. API runs "public-read-only" mode: catalog public; all auth endpoints return 503 `auth_not_configured`. | Website works as static info page. |
| Hostinger zone for `systemzero.dev` / `system0.dev` not visible | Skip DNS provisioning for that zone. Record hostname as `sz-cloud.fly.dev` / `sz-web.fly.dev` in `.s0-release.json.endpoints`. Downstream reads from that file. | Users visit `.fly.dev` until DNS fixed. |
| `PYPI` publish fails (name taken / rate-limit / 403) | Cascade: `system-zero` → `systemzero` → `system-zero-cli` → `sz-cli`. First success wins. Record to `.s0-release.json.pypi_package`. | install.sh, npm wrapper, brew formula read `.s0-release.json`. |
| `NPM_TOKEN` publish fails | Cascade: `system-zero` → `systemzero` → `sz-cli`. Record to `.s0-release.json.npm_package`. | Only npm install command uses this. |
| GitHub repo name taken (`gh repo create` 422) | Auto-append `-protocol`, `-dev-2`, `-dev-3`. Record to `.s0-release.json.github_repos`. | README cross-links read from `.s0-release.json`. |
| Fly.io app name taken | Auto-append `-2`, `-3`, … Record to `.s0-release.json.fly_apps`. | DNS and cert commands read from `.s0-release.json`. |
| Brew tap name taken | Soft skip — brew is optional. Log to BLOCKERS. | Users install via pip / npm / curl. |
| A module's `install.sh` or `doctor.sh` fails in phase 08 | Mark that one module `status: degraded`. Reconcile continues. | Phase 12 needs ≥3 CE modules; if ≥3 pass, test stands. |
| Catalog fetch 404s | Fall back to local `catalog/index.json`. Log to BLOCKERS. | Modules install locally. |
| `sz absorb` produces invalid draft after 3 CLC retries | Mark source `skip` in inventory. Continue. | Phase 14 needs ≥2 of 3; phase 16 needs ≥15 candidates. |
| Hostinger API body shape unknown | Try `.data`, `.zones`, `.result`. If all empty, soft-skip DNS for that zone. | Same as zone-not-visible. |
| Fly dedicated IP allocation fails | Fall back to `dig sz-web.fly.dev`. Flag `drift_risk: true`. | DNS created but manual re-point if Fly rotates IPs. |
| Phase verifier fails 4 attempts | Mark phase `status: degraded`. Emit `phase.soft_blocked`. Move on. | Tests (12/13/14) validate whether degraded phases matter. |
| PostHog rejects events | Silent drop. Telemetry is non-essential. | No user-visible impact. |
| Absorb source clone fails (404, DMCA, rate-limit) | Skip that source. Move on. | Phase 14/16 thresholds use N-1 instead of N. |

## Core-essentials green invariant

The run is **successful-with-degradation** if ALL of these hold at the end of phase 15:

1. `pipx install <chosen name from .s0-release.json>` from a fresh machine installs and produces a working `sz` CLI.
2. `sz init --yes` on a new repo runs Repo Genesis end-to-end.
3. Public catalog index resolves (from GitHub or from `sz-cloud.fly.dev/v1/catalog/index` if DNS deferred).
4. At least 3 modules from phase 08 install on a fresh repo via `sz install`.
5. At least one absorption (phase 14) succeeded.
6. `BLOCKERS.md` exists and lists every soft-skip so the operator can triage.

If those six hold, the operator wakes up to a launchable v0.1.0-rc1 even if Stripe/Clerk/DNS/Resend/PostHog/npm/brew had to be deferred.

## Annotation template

Every bypass appends one block to `/Users/avi/Documents/Projects/system0-natural/BLOCKERS.md`:

```markdown
## <UTC-ISO-8601> · phase-NN · <short-condition-name>

- **Category**: deferred | degraded | skipped
- **What failed**: <one-line: the command or check that tripped the bypass>
- **Bypass applied**: <which row of Appendix A matched>
- **Downstream effect**: <what subsequent phases should know>
- **Action to resolve**: <the concrete step the operator takes>
- **Run command to retry only this bypass**: <one copy-pasteable shell line>
```

Order: newest-first. Never truncate.

## Release-state file: `.s0-release.json`

Machine-readable companion to `BLOCKERS.md`. Downstream phases read it to learn which names/endpoints actually exist.

Minimum schema:
```json
{
  "run_id": "<iso-8601>",
  "started_at": "<iso-8601>",
  "ended_at": "<iso-8601 | null>",
  "overall_status": "green | degraded | hard_blocked",
  "pypi_package": "string | null",
  "npm_package":  "string | null",
  "fly_apps":     { "cloud": "...", "web": "..." },
  "endpoints":    { "api": "https://...", "web": "https://...", "alias_web": "https://... | (deferred)" },
  "github_repos": { "core": "...", "catalog": "...", "tap": "..." },
  "billing":      { "status": "live | test | deferred", "price_pro": "...", "price_team": "..." },
  "auth":         { "status": "clerk | guest-only" },
  "email":        { "status": "resend | outbox" },
  "dns":          { "status": "hostinger | deferred" },
  "phases":       { "00": "green", "01": "green", "...": "..." },
  "degraded":     ["phase-10: billing deferred (live-mode without opt-in)"],
  "skipped":      []
}
```

Phase 00 writes the initial empty version; every phase updates fields relevant to it.

## Execution discipline

1. Before any bypass is applied, confirm the condition is in the soft-blocker table. If not listed, fall through to hard-block — do not invent bypasses.
2. Every bypass writes to `BLOCKERS.md` and `.s0-release.json` atomically (tmp-file + rename).
3. Downstream phases read `.s0-release.json` to learn names/endpoints; they never assume defaults.
4. The verifier treats a phase ending with `status: degraded` as passing for advancement, but logs it so phase 15's final audit sees it.
