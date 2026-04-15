# Phase 00 — Prerequisites

## Goal

Verify the executor environment can run every later phase. Install missing tools. Establish the working directory. Verify every credential present in the real `.env` at the repo root. Stop early if anything fundamental is missing.

## Inputs

- A workstation running macOS (Apple Silicon or Intel) or Linux x86_64.
- Network access.
- Write access to `/Users/avi/Documents/Projects/system0-natural/`.
- The `.env` file at the repo root with all the keys enumerated in step 0.11.

## Outputs

- A `.tooling-report.json` at the repo root listing every checked tool and credential (values masked).
- A `tooling/bootstrap.sh` script that re-runs the same checks on any machine.
- A single unambiguous phase-00 completion state in the current workspace. Under spec-driven runners that forbid branch operations, stay on the current branch and treat the verified workspace state as authoritative.

## Atomic steps

### Step 0.1 — Confirm working directory

```bash
cd /Users/avi/Documents/Projects/system0-natural
pwd
```

Verify: output is exactly `/Users/avi/Documents/Projects/system0-natural`.

### Step 0.2 — Initialize git if needed

```bash
[ -d .git ] || git init
git status
```

### Step 0.3 — Record branch override state

```bash
git branch --show-current
```

If the executor is running under a spec/runner that forbids branch creation or switching, this step is satisfied by staying on the current branch and recording that branch name in `.tooling-report.json`.

### Step 0.4 — Check Python 3.10+

```bash
python3 --version
```

### Step 0.5 — Check pip and pipx

```bash
python3 -m pip --version
which pipx || python3 -m pip install --user pipx && python3 -m pipx ensurepath
pipx --version
```

### Step 0.6 — Check core CLI tools

```bash
for cmd in git curl jq tar unzip make bash openssl dig; do
  command -v "$cmd" >/dev/null && echo "OK: $cmd" || echo "MISSING: $cmd"
done
```

Recovery: `brew install` or `apt-get install` as needed.

### Step 0.7 — Check distribution + cloud tools

```bash
for cmd in node npm gh fly; do
  command -v "$cmd" >/dev/null && echo "OK: $cmd" || echo "MISSING: $cmd"
done
```

Recovery: `brew install node gh`; `curl -L https://fly.io/install.sh | sh`.

### Step 0.8 — Check Python packages

```bash
python3 -m pip install --user --upgrade \
  "pyyaml>=6.0" "jsonschema>=4.20" "click>=8.1" "rich>=13.7" "platformdirs>=4.2" \
  "fastapi>=0.110" "uvicorn>=0.27" "stripe>=8.0" "httpx>=0.27" \
  "supabase>=2.0" "resend>=1.0"
```

Verify: `python3 -c "import yaml, jsonschema, click, rich, platformdirs, fastapi, uvicorn, stripe, httpx, supabase, resend; print('ok')"` prints `ok`.

### Step 0.9 — Verify `~/.sz` creatable

```bash
mkdir -p ~/.sz
```

### Step 0.10 — Network reachability

```bash
for t in \
  "github:https://api.github.com" \
  "stripe:https://api.stripe.com" \
  "fly:https://api.fly.io" \
  "npm:https://registry.npmjs.org" \
  "pypi:https://pypi.org" \
  "openai:https://api.openai.com/v1/models" \
  "groq:https://api.groq.com" \
  "supabase:https://supabase.com" \
  "clerk:https://api.clerk.com" \
  "resend:https://api.resend.com" \
  "posthog:https://app.posthog.com" \
  "hostinger:https://developers.hostinger.com"; do
  n="${t%%:*}"; u="${t#*:}"
  curl -sS -o /dev/null -w "$n %{http_code}\n" --max-time 10 "$u" || echo "$n UNREACHABLE"
done
```

Verify: every line ends with a numeric status code (2xx/3xx/4xx are all fine — 401 means the endpoint is up and asking for auth).

### Step 0.11 — Credentials present in `.env`

The real `.env` contains these keys. Each mandatory entry must be non-empty.

**Mandatory for v0.1:**

| Key | Used by phase |
|---|---|
| `OPENAI_API_KEY` | 03, 06, 07, 10 |
| `GROQ_API_KEY` | 03 |
| `STRIPE_SECRET_KEY` | 10 |
| `STRIPE_PUBLISHABLE_KEY` | 10, 11 |
| `STRIPE_WEBHOOK_SECRET` | 10 |
| `HOSTINGER_API_TOKEN` | 10, 11 |
| `HOSTINGER_DOMAIN` | 11 |
| `FLYIO_API_TOKEN` | 10, 11, 15 |
| `SUPABASE_URL` | 10 |
| `SUPABASE_SERVICE_ROLE_KEY` | 10 |
| `NEXT_PUBLIC_SUPABASE_URL` | 11 |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | 11 |
| `CLERK_SECRET_KEY` | 10, 11 |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | 11 |
| `PYPI` | 15 |

**Optional (graceful fallback):**

| Key | Behavior if absent |
|---|---|
| `ANTHROPIC_API_KEY` | falls back to OpenAI / Groq / mock |
| `GH_TOKEN` | use `gh auth login` instead |
| `NPM_TOKEN` | use `npm login` instead |
| `NEXT_PUBLIC_POSTHOG_KEY` | telemetry disabled |
| `TELEGRAM_BOT_TOKEN` | notification channel unavailable |
| `HEARTBEAT_BEACON_URL`, `BEACON_WRITE_SECRET` | phase-16 beacon disabled |
| `CLERK_JWKS_URL` | phase 10 discovers it via the Clerk API (using `CLERK_SECRET_KEY`) and sets it as a Fly secret at deploy time |
| `RESEND_API_KEY` | phase 10 falls back to the durable outbox; welcome email delivery is deferred, not blocking |

Action:

```bash
python3 - <<'PY'
import pathlib, sys
p = pathlib.Path(".env")
if not p.exists(): print("NO .env"); sys.exit(1)
required = ["OPENAI_API_KEY","GROQ_API_KEY",
            "STRIPE_SECRET_KEY","STRIPE_PUBLISHABLE_KEY","STRIPE_WEBHOOK_SECRET",
            "HOSTINGER_API_TOKEN","HOSTINGER_DOMAIN",
            "FLYIO_API_TOKEN",
            "SUPABASE_URL","SUPABASE_SERVICE_ROLE_KEY",
            "NEXT_PUBLIC_SUPABASE_URL","NEXT_PUBLIC_SUPABASE_ANON_KEY",
            "CLERK_SECRET_KEY","NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY",
            "PYPI"]
optional = ["ANTHROPIC_API_KEY","GH_TOKEN","NPM_TOKEN",
            "NEXT_PUBLIC_POSTHOG_KEY","TELEGRAM_BOT_TOKEN",
            "HEARTBEAT_BEACON_URL","BEACON_WRITE_SECRET","RESEND_API_KEY"]
present = {}
for line in p.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line: continue
    k, v = line.split("=", 1)
    v = v.strip().strip('"').strip("'")
    present[k.strip()] = bool(v)
missing = [k for k in required if not present.get(k, False)]
for k in required: print(f"{k}: {'PRESENT' if present.get(k,False) else 'MISSING'}")
print("---")
for k in optional: print(f"{k}: {'PRESENT' if present.get(k,False) else 'ABSENT (ok)'}")
sys.exit(1 if missing else 0)
PY
```

Verify: exit code 0; every mandatory key is `PRESENT`.

### Step 0.12 — Lightweight credential validation

```bash
. ./.env

curl -sSf https://api.openai.com/v1/models                         -H "Authorization: Bearer $OPENAI_API_KEY" >/dev/null && echo "openai OK"     || echo "openai FAIL"
curl -sSf https://api.groq.com/openai/v1/models                    -H "Authorization: Bearer $GROQ_API_KEY"   >/dev/null && echo "groq OK"       || echo "groq FAIL"
curl -sSf https://api.fly.io/graphql                               -H "Authorization: Bearer $FLYIO_API_TOKEN" -H "content-type: application/json" -d '{"query":"{ viewer { id } }"}' >/dev/null && echo "fly OK" || echo "fly FAIL"
curl -sSf https://api.stripe.com/v1/account                        -u "$STRIPE_SECRET_KEY:" >/dev/null && echo "stripe OK" || echo "stripe FAIL"
curl -sSf "$SUPABASE_URL/rest/v1/"                                 -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" >/dev/null && echo "supabase OK" || echo "supabase FAIL"
curl -sSf https://api.clerk.com/v1/users                           -H "Authorization: Bearer $CLERK_SECRET_KEY" >/dev/null && echo "clerk OK" || echo "clerk FAIL"
if [ -n "${RESEND_API_KEY:-}" ]; then
  curl -sSf https://api.resend.com/domains -H "Authorization: Bearer $RESEND_API_KEY" >/dev/null \
    && echo "resend OK" \
    || echo "resend DEFERRED (non-blocking)"
else
  echo "resend ABSENT (deferred/non-blocking)"
fi

# Hostinger — DNS ONLY source of truth. Cloudflare is not used. Validate the documented base URL
# against an actual zone read because Hostinger's DNS API is domain-scoped, not list-scoped.
HOSTINGER_ENDPOINT=""
base="https://developers.hostinger.com/api/dns/v1"
if curl -sSf "$base/zones/$HOSTINGER_DOMAIN" -H "Authorization: Bearer $HOSTINGER_API_TOKEN" >/dev/null 2>&1; then
  HOSTINGER_ENDPOINT="$base"; echo "hostinger OK ($base)"
fi
if [ -z "$HOSTINGER_ENDPOINT" ]; then
  echo "hostinger DEFERRED — documented Hostinger DNS base URL did not accept the token + domain."
fi

# Zone-scope check: confirm the Hostinger token can actually list zones for systemzero.dev and system0.dev.
# HOSTINGER_DOMAIN in .env is the primary domain of the Hostinger account; it may differ from the target zones.
# If either target zone is absent from the token's visible zones, the DNS steps in phases 10/11 will fail.
if [ -n "$HOSTINGER_ENDPOINT" ]; then
  for DOMAIN in systemzero.dev system0.dev; do
    if curl -sSf -H "Authorization: Bearer $HOSTINGER_API_TOKEN" "$HOSTINGER_ENDPOINT/zones/$DOMAIN" >/dev/null; then
      echo "hostinger-zone OK: $DOMAIN"
    else
      echo "hostinger-zone DEFERRED: $DOMAIN — not visible to this token"
      echo "  (HOSTINGER_DOMAIN in .env is set to: ${HOSTINGER_DOMAIN:-unset})"
      echo "  DNS for this zone will stay on .fly.dev until morning triage."
    fi
  done
fi

[ ${#PYPI} -gt 30 ] && echo "pypi token-length OK" || echo "pypi FAIL"

echo "HOSTINGER_ENDPOINT=$HOSTINGER_ENDPOINT"
```

Verify: the core service checks (`openai`, `groq`, `fly`, `stripe`, `supabase`, `clerk`, `pypi token-length`) end in `OK`. `resend` may end in `OK`, `DEFERRED (non-blocking)`, or `ABSENT (deferred/non-blocking)`. Hostinger may end in `OK (...)` or `DEFERRED`; when deferred, the downstream fallback is `.fly.dev` and the deferral is recorded in step 0.15b. **Do not fall back to Cloudflare or any other DNS provider — DNS remains Hostinger-only when enabled.**

### Step 0.13 — Generate `.tooling-report.json`

Write the file at the repo root capturing: platform, python, node, tool versions, package versions, every credential's `validated: true|false`, and `hostinger_endpoint` (the working Hostinger DNS base URL when available; empty string is allowed when DNS is deferred). `dns_strategy` is always `hostinger-only`. No fallback provider is allowed.

### Step 0.14 — `tooling/bootstrap.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
echo "== System Zero bootstrap check =="
python3 --version
for c in git curl jq tar unzip make bash openssl dig node npm gh fly; do
  command -v "$c" >/dev/null || { echo "MISSING: $c"; exit 1; }
done
python3 -c "import yaml, jsonschema, click, rich, platformdirs, fastapi, uvicorn, stripe, httpx, supabase, resend"
mkdir -p ~/.sz
echo "OK"
```

### Step 0.15 — `.gitignore`

```
.sz/
__pycache__/
*.pyc
.venv/
.DS_Store
.idea/
.vscode/
.tooling-report.json
.env
.env.local
.env.cloud
node_modules/
dist/
build/
```

### Step 0.15b — Initialize BLOCKERS.md and .s0-release.json

These two files are the overnight-run contract (Appendix A in `plan/EXECUTION_RULES.md`). Every later phase reads and appends to them.

Create `BLOCKERS.md` at the repo root:
```markdown
# Blockers — run <run-id>

This file is the morning triage report for the overnight run. Every soft-blocker that was bypassed
appears as a dated section, newest first. Hard blockers appear with `[HARD]` and stop the run.

Policy: Appendix A in `plan/EXECUTION_RULES.md`.

<!-- bypass entries appended below this line; do not edit by hand during a run -->
```

Create `.s0-release.json` at the repo root:
```bash
python3 - <<'PY'
import json, pathlib, datetime, os
p = pathlib.Path(".s0-release.json")
now = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds").replace("+00:00","Z")
state = {
  "run_id": now,
  "started_at": now,
  "ended_at": None,
  "overall_status": "green",
  "pypi_package": None,
  "npm_package":  None,
  "fly_apps": {},
  "endpoints": {
    "api":       "https://api.systemzero.dev",
    "web":       "https://systemzero.dev",
    "alias_web": "https://system0.dev"
  },
  "github_repos": {},
  "billing":  {"status": "unset"},
  "auth":     {"status": "unset"},
  "email":    {"status": "unset"},
  "dns":      {"status": "hostinger" if os.environ.get("HOSTINGER_ENDPOINT") else "unset",
               "endpoint": os.environ.get("HOSTINGER_ENDPOINT","")},
  "phases": {},
  "degraded": [],
  "skipped":  []
}
p.write_text(json.dumps(state, indent=2))
print(str(p))
PY
```

If phase 00's Hostinger zone check deferred any zone, append a BLOCKERS.md entry now:

```bash
if [ ${#HOSTINGER_ZONES_DEFERRED[@]} -gt 0 ]; then
  {
    echo ""
    echo "## $(date -u +%FT%TZ) · phase-00 · hostinger-zone-deferred"
    echo ""
    echo "- **Category**: deferred"
    echo "- **What failed**: Hostinger token cannot read zone(s): ${HOSTINGER_ZONES_DEFERRED[*]}"
    echo "- **Bypass applied**: Hostinger-zone-not-visible — DNS skipped for these zones; .fly.dev hostnames used downstream"
    echo "- **Downstream effect**: phase 10 uses sz-cloud.fly.dev; phase 11 uses sz-web.fly.dev; website references updated in .s0-release.json.endpoints"
    echo "- **Action to resolve**: at https://hpanel.hostinger.com rotate the token with DNS-write scope for these zones, OR set S0_DNS_REQUIRED=1 in env to turn this into a hard blocker next run"
    echo "- **Run command to retry only this bypass**: bash tooling/retry-hostinger-dns.sh"
  } >> BLOCKERS.md
  # Record degradation.
  python3 - <<'PY'
import json, pathlib
p = pathlib.Path(".s0-release.json"); s = json.loads(p.read_text())
s["dns"] = {"status": "deferred", "reason": "hostinger-zone-not-visible"}
s["endpoints"]["api"] = "https://sz-cloud.fly.dev"
s["endpoints"]["web"] = "https://sz-web.fly.dev"
s["endpoints"]["alias_web"] = "(deferred)"
s["degraded"].append("phase-00: dns deferred — hostinger zone(s) not visible")
p.write_text(json.dumps(s, indent=2))
PY
fi
```

Verify: `jq . .s0-release.json` parses; if deferred, `BLOCKERS.md` has one entry.

### Step 0.16 — Record phase completion state

```bash
grep -qxF "BLOCKERS.md" .gitignore || echo "BLOCKERS.md" >> .gitignore
grep -qxF ".s0-release.json" .gitignore || echo ".s0-release.json" >> .gitignore
python3 - <<'PY'
import json, pathlib, subprocess
head = subprocess.run(
    ["git", "rev-parse", "HEAD"],
    cwd=".",
    check=True,
    text=True,
    capture_output=True,
).stdout.strip()
report_path = pathlib.Path(".tooling-report.json")
report = json.loads(report_path.read_text())
report["phase_completion_state"] = {
    "git_branch": subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=".",
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip(),
    "git_head": head,
    "mode": "workspace-state"
}
report_path.write_text(json.dumps(report, indent=2) + "\n")
print(head)
PY
```

## Acceptance criteria

1. `bash tooling/bootstrap.sh` exits 0.
2. `.tooling-report.json` shows every mandatory credential validated.
3. `.s0-release.json` exists and records either a working Hostinger DNS base URL or a DNS deferral with `.fly.dev` fallback endpoints. Either state is acceptable for the overnight run.
4. `.tooling-report.json.phase_completion_state` records the current branch and `HEAD`, so a verifier has one unambiguous phase-00 completion state even when branch operations are forbidden by the runner.

## Failure modes and recovery

| Symptom | Cause | Action |
|---|---|---|
| `OPENAI_API_KEY` missing | .env edit | `STOP_AND_REPORT`; need at least one LLM key |
| All Hostinger endpoints fail | Hostinger DNS API differs for this account, or token scope is wrong | Soft-defer DNS for this run: write the deferral to `BLOCKERS.md`, set `.s0-release.json.endpoints` to `.fly.dev`, and continue. Morning triage can rotate the Hostinger token or pin the correct API shape. |
| Supabase 401 | wrong service-role key | regenerate from Supabase dashboard |
| Clerk 401 | wrong secret key | regenerate; keep test vs live mode consistent with Stripe |
| Fly token org vs app scope | not auto-detected | regenerate as org-scoped; phase 10 creates apps inside that org |
| `PYPI` token expired | rotate | regenerate at pypi.org/manage/account/token; paste as `PYPI=pypi-...` |

## Rollback

`rm -f tooling/bootstrap.sh .gitignore .tooling-report.json`.
