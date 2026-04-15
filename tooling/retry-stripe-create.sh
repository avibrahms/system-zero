#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
. ./.env

if [ -f .env.cloud ]; then
  # shellcheck disable=SC1091
  . ./.env.cloud
fi

if [ -n "${STRIPE_PRICE_PRO:-}" ] && [ -n "${STRIPE_PRICE_TEAM:-}" ]; then
  python3 - <<PY
import json, pathlib
p = pathlib.Path(".s0-release.json")
s = json.loads(p.read_text())
live = "${STRIPE_SECRET_KEY:-}".startswith("sk_live_")
s["billing"] = {
    "status": "live" if live else "test",
    "price_pro": "${STRIPE_PRICE_PRO}",
    "price_team": "${STRIPE_PRICE_TEAM}",
}
p.write_text(json.dumps(s, indent=2) + "\n")
PY
  echo "stripe prices already configured"
  exit 0
fi

case "${STRIPE_SECRET_KEY:-}" in
  sk_live_*)
    if [ "${STRIPE_AUTO_CREATE:-0}" != "1" ]; then
      echo "refusing to create live Stripe products without STRIPE_AUTO_CREATE=1" >&2
      exit 2
    fi
    ;;
esac

PRO_PRODUCT=$(curl -sS https://api.stripe.com/v1/products \
  -u "$STRIPE_SECRET_KEY:" \
  -d name="System Zero Pro" \
  -d description="Hosted catalog + cloud absorb + telemetry + insights" | jq -r .id)
PRO_PRICE=$(curl -sS https://api.stripe.com/v1/prices \
  -u "$STRIPE_SECRET_KEY:" \
  -d product="$PRO_PRODUCT" \
  -d unit_amount=1900 \
  -d currency=usd \
  -d "recurring[interval]=month" | jq -r .id)
TEAM_PRODUCT=$(curl -sS https://api.stripe.com/v1/products \
  -u "$STRIPE_SECRET_KEY:" \
  -d name="System Zero Team" \
  -d description="Pro + shared library + audit + team insights + SSO" | jq -r .id)
TEAM_PRICE=$(curl -sS https://api.stripe.com/v1/prices \
  -u "$STRIPE_SECRET_KEY:" \
  -d product="$TEAM_PRODUCT" \
  -d unit_amount=4900 \
  -d currency=usd \
  -d "recurring[interval]=month" | jq -r .id)

{
  echo "STRIPE_PRICE_PRO=$PRO_PRICE"
  echo "STRIPE_PRICE_TEAM=$TEAM_PRICE"
} > .env.cloud

python3 - <<PY
import json, pathlib
p = pathlib.Path(".s0-release.json")
s = json.loads(p.read_text())
live = "${STRIPE_SECRET_KEY:-}".startswith("sk_live_")
s["billing"] = {
    "status": "live" if live else "test",
    "price_pro": "$PRO_PRICE",
    "price_team": "$TEAM_PRICE",
}
p.write_text(json.dumps(s, indent=2) + "\n")
PY
