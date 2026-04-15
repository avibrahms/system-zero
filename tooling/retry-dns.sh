#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
. ./.env

DOMAIN="${1:-all}"
RECORD="${2:-api}"
ENDPOINT=$(jq -r '.hostinger_endpoint // empty' .tooling-report.json)
FLY_CLOUD=$(jq -r '.fly_apps.cloud // "sz-cloud"' .s0-release.json)

if [ -z "$ENDPOINT" ]; then
  echo "missing .tooling-report.json.hostinger_endpoint" >&2
  exit 2
fi

domains=()
if [ "$DOMAIN" = "all" ]; then
  domains=(systemzero.dev system0.dev)
else
  domains=("$DOMAIN")
fi

for zone in "${domains[@]}"; do
  ZONE_ID=$(curl -sS -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
    "$ENDPOINT/zones?name=$zone" | jq -r '(.data // .zones // .result // [])[0].id // empty')
  if [ -z "$ZONE_ID" ]; then
    echo "zone not visible: $zone" >&2
    continue
  fi

  EXISTING=$(curl -sS -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
    "$ENDPOINT/zones/$ZONE_ID/records?name=$RECORD&type=CNAME" | jq -r '(.data // .records // .result // [])[0].id // empty')
  if [ -z "$EXISTING" ]; then
    curl -sS -X POST -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
      -H "Content-Type: application/json" \
      "$ENDPOINT/zones/$ZONE_ID/records" \
      -d "{\"name\":\"$RECORD\",\"type\":\"CNAME\",\"value\":\"$FLY_CLOUD.fly.dev\",\"ttl\":300}" >/dev/null
  else
    curl -sS -X PUT -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
      -H "Content-Type: application/json" \
      "$ENDPOINT/zones/$ZONE_ID/records/$EXISTING" \
      -d "{\"name\":\"$RECORD\",\"type\":\"CNAME\",\"value\":\"$FLY_CLOUD.fly.dev\",\"ttl\":300}" >/dev/null
  fi
done

python3 - <<PY
import json, pathlib
p = pathlib.Path(".s0-release.json")
s = json.loads(p.read_text())
s.setdefault("dns", {})["status"] = "hostinger"
s.setdefault("endpoints", {})["api"] = "https://api.systemzero.dev"
p.write_text(json.dumps(s, indent=2) + "\n")
PY
