#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  echo "NO .env" >&2
  exit 1
fi

set -a
source .env
set +a

HOSTINGER_ENDPOINT="https://developers.hostinger.com/api/dns/v1"
deferred=()

for zone in systemzero.dev system0.dev; do
  if curl -sSf -H "Authorization: Bearer $HOSTINGER_API_TOKEN" "$HOSTINGER_ENDPOINT/zones/$zone" >/dev/null; then
    echo "hostinger-zone OK: $zone"
  else
    echo "hostinger-zone DEFERRED: $zone"
    deferred+=("$zone")
  fi
done

python3 tooling/generate-tooling-report.py

python3 - <<'PY' "$HOSTINGER_ENDPOINT" "${deferred[@]}"
import datetime as dt
import json
import pathlib
import sys

endpoint = sys.argv[1]
deferred = sys.argv[2:]
release_path = pathlib.Path(".s0-release.json")
if release_path.exists():
    state = json.loads(release_path.read_text())
else:
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    state = {
        "run_id": now,
        "started_at": now,
        "ended_at": None,
        "overall_status": "green",
        "pypi_package": None,
        "npm_package": None,
        "fly_apps": {},
        "endpoints": {
            "api": "https://api.systemzero.dev",
            "web": "https://systemzero.dev",
            "alias_web": "https://system0.dev",
        },
        "github_repos": {},
        "billing": {"status": "unset"},
        "auth": {"status": "unset"},
        "email": {"status": "unset"},
        "dns": {"status": "unset", "endpoint": ""},
        "phases": {},
        "degraded": [],
        "skipped": [],
    }

state["ended_at"] = dt.datetime.now(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
if deferred:
    state["overall_status"] = "degraded"
    state["dns"] = {
        "status": "deferred",
        "reason": "hostinger-zone-not-visible",
        "endpoint": endpoint,
        "deferred_zones": deferred,
    }
    state["endpoints"]["api"] = "https://sz-cloud.fly.dev"
    state["endpoints"]["web"] = "https://sz-web.fly.dev"
    state["endpoints"]["alias_web"] = "(deferred)"
    note = "phase-00: dns deferred — hostinger zone(s) not visible"
    if note not in state["degraded"]:
        state["degraded"].append(note)
else:
    state["dns"] = {
        "status": "hostinger",
        "endpoint": endpoint,
        "zones": ["systemzero.dev", "system0.dev"],
    }
    state["phases"]["00"] = "green"

release_path.write_text(json.dumps(state, indent=2) + "\n")
PY
