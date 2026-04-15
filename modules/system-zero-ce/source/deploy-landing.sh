#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-preview}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
LANDING_DIR="$REPO_ROOT/modules/system-zero/landing"
PROJECT_NAME="${SYSTEM_ZERO_CF_PAGES_PROJECT:-system-zero-landing}"

case "$MODE" in
  preview)
    BRANCH="${SYSTEM_ZERO_PREVIEW_BRANCH:-preview}"
    EXPECTED_ENV="test"
    ;;
  production|prod)
    BRANCH="${SYSTEM_ZERO_PRODUCTION_BRANCH:-main}"
    EXPECTED_ENV="production"
    ;;
  *)
    echo "Usage: $0 [preview|production]"
    exit 1
    ;;
esac

if ! command -v npx >/dev/null 2>&1; then
  echo "npx is required to run Cloudflare Pages deploys."
  exit 1
fi

if [[ ! -f "$LANDING_DIR/index.html" || ! -f "$LANDING_DIR/_worker.js" ]]; then
  echo "Landing source is incomplete: expected index.html and _worker.js in $LANDING_DIR"
  exit 1
fi

echo "Deploying System Zero landing"
echo "  mode: $MODE"
echo "  project: $PROJECT_NAME"
echo "  branch: $BRANCH"
echo ""

DEPLOY_OUTPUT="$(mktemp "/tmp/system-zero-landing-deploy.XXXXXX.log")"

set +e
npx wrangler pages deploy "$LANDING_DIR" \
  --project-name "$PROJECT_NAME" \
  --branch "$BRANCH" | tee "$DEPLOY_OUTPUT"
STATUS=$?
set -e

if [[ $STATUS -ne 0 ]]; then
  echo ""
  echo "Cloudflare deploy failed. Review $DEPLOY_OUTPUT"
  exit $STATUS
fi

DEPLOY_URL="$(
  DEPLOY_OUTPUT="$DEPLOY_OUTPUT" python3 <<'PY'
import os
import re
from pathlib import Path

text = Path(os.environ["DEPLOY_OUTPUT"]).read_text()
matches = re.findall(r"https://[^\s)]+", text)
print(matches[-1] if matches else "")
PY
)"

if [[ -n "$DEPLOY_URL" ]]; then
  echo ""
  echo "Deployment URL: $DEPLOY_URL"
  echo "Next: python3 modules/system-zero/scripts/smoke-check-landing.py --url $DEPLOY_URL --expected-environment $EXPECTED_ENV"
else
  echo ""
  echo "Deploy completed, but no URL was parsed from Wrangler output."
  echo "Run the smoke script manually once the Pages URL is known."
fi
