#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/Users/avi/Documents/Projects/system0-natural"
REPORT="$REPO_ROOT/.test-reports/phase-16.json"
mkdir -p "$(dirname "$REPORT")"
export SZ_CATALOG="${SZ_CATALOG:-file://$REPO_ROOT/catalog/index.json}"
CATALOG_LABEL="${SZ_CATALOG_LABEL:-local-current-branch}"
source "$REPO_ROOT/tests/e2e/sz-shim.sh"
SHIM_DIR="$(mktemp -d)"
install_local_sz_shim "$REPO_ROOT" "$SHIM_DIR"
export PATH="$SHIM_DIR:$PATH"

# Fresh clone of the reference repo.
WORK=$(mktemp -d)
cd "$WORK"
gh repo clone "${SZ_GITHUB_OWNER:-avibrahms}/connection-engine-reference"
cd connection-engine-reference
bash bootstrap.sh

# Seed behavior fixtures after bootstrap so the reconstructed modules have real
# protocol-native work to perform on the validation tick.
mkdir -p .sz/shared/action-card .sz/shared/content/posting .sz/shared/email/outcomes .sz/shared/dashboard plan/phase-demo
cat > .sz/shared/action-card/action-card.json <<'JSON'
{
  "date": "2026-04-15",
  "sections": [
    {
      "type": "task",
      "items": [
        {"id": "ship-phase-16", "name": "Ship phase 16", "context": "verification"},
        {"id": "keep-working", "name": "Keep working", "context": "active"}
      ]
    }
  ]
}
JSON
cat > .sz/shared/action-card/action-card-state.json <<'JSON'
{"completed_items": {"ship-phase-16": "2026-04-15T03:00:00Z"}}
JSON
cat > .sz/shared/action-card/action-card-archive.json <<'JSON'
{"entries": []}
JSON
cat > .sz/shared/content/ready-queue.md <<'MD'
### Post A
**Status:** approved

### Post B
**Status:** rejected

### Post C
**Status:** ready
MD
cat > .sz/shared/content/content-mix-policy.yaml <<'YAML'
selection:
  eligible_statuses:
    - approved
YAML
cat > .sz/shared/content/posting/AUTO-POST-PROTOCOL.md <<'MD'
Only approved posts are eligible for automated posting.
MD
cat > .sz/shared/email/external-output-log.json <<'JSON'
[
  {"source": "email-draft-verifier", "id": "remove-me"},
  {"source": "other", "id": "keep-me"}
]
JSON
cat > .sz/shared/email/intercepted-signals.json <<'JSON'
[
  {"source_channel": "email", "metadata": {"origin": "email-draft.py", "draft_id": "d1"}},
  {"source_channel": "chat", "metadata": {"origin": "manual"}}
]
JSON
cat > .sz/shared/email/outcomes/email-draft-verification.json <<'JSON'
{"status": "test-artifact"}
JSON
cat > .sz/shared/dashboard/session.json <<'JSON'
{"id": "fixture-session", "state": "active"}
JSON
cat > .sz/shared/dashboard/sessions.json <<'JSON'
[{"id": "fixture-session"}]
JSON
cat > plan/phase-demo/PLAN.md <<'MD'
# Phase Demo

## Goal

Validate reconstructed module behavior.

## Outputs

- A fixture plan that can be linted.

## Acceptance criteria

1. The fixture is discoverable.
MD

# Must end up alive.
LIST_OUTPUT="$(sz list)"
printf '%s\n' "$LIST_OUTPUT" | grep -Eq "heartbeat|immune|subconscious" || { echo "no core modules"; exit 1; }
printf '%s\n' "$LIST_OUTPUT" | grep -q "skill-library-ce" || { echo "no rewritten skill library"; exit 1; }
sz tick --reason "reconstruct fixture system zero phase"
sz tick --reason reconstruct-check
sz bus tail --last 50 --filter "health.snapshot" | grep -q . || { echo "no snapshot"; exit 1; }
CE_SNAPSHOTS="$(sz bus tail --last 200 --filter "ce.*.snapshot" | jq 'length')"
[ "$CE_SNAPSHOTS" -gt 0 ] || { echo "no reconstructed module snapshots"; exit 1; }

event_payloads() {
  sz bus tail --last 400 --filter "$1" | jq '[.[].payload]'
}

event_payloads "ce.action.card.cleanup.snapshot" | jq -e 'any(.archived_count >= 1 and .active_items == 1)' >/dev/null || { echo "action-card cleanup did not archive completed item"; exit 1; }
jq -e '.completed_items == {}' .sz/shared/action-card/action-card-state.json >/dev/null || { echo "action-card state was not cleared"; exit 1; }
jq -e '.entries | length == 1' .sz/shared/action-card/action-card-archive.json >/dev/null || { echo "action-card archive was not written"; exit 1; }
event_payloads "ce.registry.validation.snapshot" | jq -e 'any(.valid == true and .module_count >= 20)' >/dev/null || { echo "registry validation did not pass"; exit 1; }
event_payloads "ce.queue.gate.snapshot" | jq -e 'any(.active_entries == 2 and .gate_open == true)' >/dev/null || { echo "queue gate did not count active queue entries"; exit 1; }
event_payloads "ce.email.verification.rollback.snapshot" | jq -e 'any(.removed_output_entries >= 1 and .removed_signal_entries >= 1 and .deleted_outcome_file == true)' >/dev/null || { echo "email rollback did not remove verification artifacts"; exit 1; }
event_payloads "ce.spec.lint.snapshot" | jq -e 'any(.checked_files >= 1 and .valid == true)' >/dev/null || { echo "spec lint did not validate fixture specs"; exit 1; }
event_payloads "ce.context.assembler.snapshot" | jq -e 'any(.selected_count >= 1)' >/dev/null || { echo "context assembler did not select files"; exit 1; }
event_payloads "ce.skill.library.snapshot" | jq -e 'any(.skill_count >= 100)' >/dev/null || { echo "skill library did not expose sanitized skills"; exit 1; }
event_payloads "ce.chronicle.snapshot" | jq -e 'any(.recorded_events >= 1 and (.chain_head | length) == 16)' >/dev/null || { echo "chronicle did not record bus events"; exit 1; }
event_payloads "ce.system.zero.audit.snapshot" | jq -e 'any(.ready == true and .module_count >= 20)' >/dev/null || { echo "system-zero audit did not pass"; exit 1; }

# Anonymization sweep — no HITs in the entire checkout.
rm -f .sz/bin/sz
if ! python3 "$REPO_ROOT/tools/anonymize.py" . >/tmp/anon.out 2>&1; then
  cat /tmp/anon.out
  echo "anonymization violated"; exit 1
fi
if [ -s /tmp/anon.out ]; then
  cat /tmp/anon.out
  echo "anonymization violated"; exit 1
fi

MODULES="$(sz list | wc -l | tr -d " ")"
printf '{"status":"PASSED","modules":%s,"ce_snapshot_events":%s,"catalog":"%s","module_specific_assertions":true}\n' "$MODULES" "$CE_SNAPSHOTS" "$CATALOG_LABEL" > "$REPORT"
echo "PHASE 16 PASSED"
