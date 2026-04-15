# Phase 10 — Cloud Platform + Billing + Data Network

## Goal

Stand up `api.systemzero.dev` on Fly.io. It serves the catalog, runs the Pro/Team hosted absorb endpoint, processes billing, gates paid features, and — critically — operates the **data network effect pipeline**: anonymous opt-in telemetry in, aggregated learning out, delivered back to every user (including Free tier) through catalog updates and a `sz insights` command.

The infrastructure is **not SQLite + handrolled tokens**; it is the real-world stack already in `.env`:

- **Supabase** — cloud Postgres + Row-Level-Security. Replaces SQLite.
- **Clerk** — auth (sign-up, sessions, JWTs, teams). Replaces handrolled tokens.
- **Stripe** — billing. Checkout + subscription webhooks.
- **Resend** — transactional email (welcome, password reset, receipt).
- **Groq** (+ OpenAI, + user-provided Anthropic) — server-side LLM for hosted absorb.
- **PostHog** — opt-in product analytics (never on Free tier without consent).
- **Fly.io** — compute, regions, TLS. Every service we host runs here. No other host.
- **Hostinger** — the **only** DNS. Every record for `systemzero.dev` and `system0.dev` is managed via the Hostinger API determined in phase 00. No other DNS provider is used.

The protocol stays fully usable Free without any cloud call; the cloud unlocks the paid tiers AND feeds the data network effect.

## Architecture

```
                                    DNS (Hostinger only)
                                              │
                                              ▼
                                        systemzero.dev
                                        system0.dev
                                        api.systemzero.dev
                                              │
                                              ▼
                                         Fly.io edge
                                              │
                            ┌─────────────────┼──────────────────┐
                            ▼                 ▼                  ▼
                       sz-web (phase 11)  sz-cloud (this)    Static CDN
                                              │
                           ┌──────────────────┼──────────────────┐
                           ▼                  ▼                  ▼
                       Clerk JWTs         Supabase          LLM providers
                       (verified)         Postgres           (OpenAI/Groq
                                          (RLS)              /Anthropic)
                                              │
                                              ▼
                                         Stripe
                                         Resend
                                         PostHog (opt-in)
```

## Routes (on `sz-cloud`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET  | `/v1/catalog/index` | public | Catalog mirror from GitHub, cached 5 min |
| GET  | `/v1/catalog/modules/{id}` | public | Module detail |
| GET  | `/v1/insights/public` | public | Community-wide aggregations (trending modules, binding heatmap) |
| POST | `/v1/billing/checkout` | Clerk JWT | Create Stripe checkout session |
| POST | `/v1/billing/webhook` | Stripe signature | Subscription events → tier upgrade |
| POST | `/v1/billing/portal` | Clerk JWT | Stripe customer portal redirect |
| GET  | `/v1/me` | Clerk JWT | Current user + tier |
| POST | `/v1/absorb` | Clerk JWT + tier≥pro | Server-side CLC absorb using server LLM keys |
| POST | `/v1/telemetry` | Clerk JWT + opt-in | Module events → Supabase |
| GET  | `/v1/insights/team` | Clerk JWT + tier=team | Team-private aggregations |
| GET  | `/i` | public | Returns `install.sh` with shell content-type |

## Inputs

- Phases 00–09 complete.
- Phase 00 credential validation passed.
- `hostinger_endpoint` recorded when phase 00 could validate the Hostinger DNS surface; if deferred, `.s0-release.json` already carries the `.fly.dev` fallback.

## Outputs

- `cloud/app/` — FastAPI source.
- `cloud/Dockerfile`.
- `cloud/fly.toml`.
- `cloud/Makefile`.
- `cloud/migrations/001_init.sql` — Supabase schema (run via `supabase sql`).
- `cloud/tests/` — unit + integration tests.
- `sz/cloud/client.py` — CLI-side helper that talks to the cloud.
- `sz/commands/login.py` — `sz login` / `sz logout` (Clerk JWT flow).
- `sz/commands/upgrade.py` — `sz upgrade` opens checkout.
- `sz/commands/insights.py` — `sz insights` reveals community/team aggregations.
- DNS records configured for `api.systemzero.dev`.
- Current-branch git checkpoint history for this phase, with no branch operations.

## Atomic steps

### Step 10.1 — Confirm current branch + scaffold

```bash
git branch --show-current
mkdir -p cloud/{app,migrations,tests} sz/cloud
```

Verify: prints the current branch name, creates the cloud scaffolding, and does not create or switch branches.

### Step 10.2 — Supabase schema

`cloud/migrations/001_init.sql`:
```sql
-- Identity: Clerk is the primary identity provider; we store the clerk_user_id.
create table if not exists users (
  clerk_user_id text primary key,
  email text not null,
  tier text not null default 'free' check (tier in ('free','pro','team')),
  stripe_customer_id text unique,
  stripe_subscription_id text unique,
  team_id uuid references teams(id),
  created_at timestamptz not null default now()
);

create table if not exists teams (
  id uuid primary key default gen_random_uuid(),
  owner_clerk_user_id text references users(clerk_user_id) not null,
  name text not null,
  stripe_customer_id text unique,
  created_at timestamptz not null default now()
);

create table if not exists installs (
  id uuid primary key default gen_random_uuid(),
  clerk_user_id text references users(clerk_user_id),
  repo_fingerprint text not null, -- hashed
  host text not null,
  host_mode text not null,
  sz_version text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists module_events (
  id bigserial primary key,
  install_id uuid references installs(id) on delete cascade,
  event_type text not null,  -- module.installed, module.errored, reconcile.finished, tick, etc.
  module_id text,
  payload jsonb,
  ts timestamptz not null default now()
);

create table if not exists absorb_records (
  id uuid primary key default gen_random_uuid(),
  clerk_user_id text references users(clerk_user_id),
  source_url text not null,
  feature text not null,
  module_id text not null,
  llm_provider text not null,
  tokens_in int, tokens_out int,
  status text not null check (status in ('succeeded','failed')),
  validation_errors jsonb,
  ts timestamptz not null default now()
);

-- Aggregated views regenerated by a nightly job.
create materialized view if not exists mv_trending_modules as
  select module_id, count(*) as installs_30d
  from module_events where event_type='module.installed' and ts > now() - interval '30 days'
  group by module_id order by installs_30d desc;

create materialized view if not exists mv_capability_bindings as
  select (payload->>'requirer') as requirer, (payload->>'provider') as provider,
         (payload->>'capability') as capability, count(*) as c
  from module_events where event_type='module.reconciled'
  group by 1,2,3 order by c desc;

-- RLS: users see only their own installs/events; public views are unrestricted.
alter table users enable row level security;
alter table installs enable row level security;
alter table module_events enable row level security;
alter table absorb_records enable row level security;

create policy own_user_row on users for select using (clerk_user_id = auth.jwt()->>'sub');
create policy own_installs  on installs  for all using (clerk_user_id = auth.jwt()->>'sub');
create policy own_events    on module_events for select using (
  install_id in (select id from installs where clerk_user_id = auth.jwt()->>'sub'));
create policy own_absorbs   on absorb_records for select using (clerk_user_id = auth.jwt()->>'sub');
```

Apply:
```bash
. ./.env
curl -sS -X POST "$SUPABASE_URL/rest/v1/rpc/exec_sql" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d "$(jq -Rs '{query: .}' < cloud/migrations/001_init.sql)"
```

If RPC is unavailable, use the Supabase dashboard SQL editor. Verify by listing tables with `curl "$SUPABASE_URL/rest/v1/users" -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" >/dev/null`.

### Step 10.3 — `cloud/app/main.py` (FastAPI)

```python
"""sz-cloud: catalog mirror + Clerk auth + Supabase persistence + Stripe billing + provider-pluggable email + hosted absorb + telemetry."""
from __future__ import annotations
import hashlib, json, os
from datetime import datetime, timezone
from pathlib import Path

import httpx, stripe
from fastapi import FastAPI, HTTPException, Header, Request, Response
from fastapi.responses import JSONResponse
from supabase import create_client, Client
try:
    import resend
except Exception:  # keep startup alive when the provider is unavailable
    resend = None

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
supa: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_PRO      = os.environ.get("STRIPE_PRICE_PRO", "")
STRIPE_PRICE_TEAM     = os.environ.get("STRIPE_PRICE_TEAM", "")
BILLING_READY         = bool(STRIPE_WEBHOOK_SECRET and STRIPE_PRICE_PRO and STRIPE_PRICE_TEAM)

CLERK_SECRET   = os.environ["CLERK_SECRET_KEY"]
CLERK_JWKS_URL = os.environ.get("CLERK_JWKS_URL", "https://clerk.systemzero.dev/.well-known/jwks.json")

EMAIL_PROVIDER   = os.environ.get("EMAIL_PROVIDER", "resend")
EMAIL_FROM       = os.environ.get("EMAIL_FROM", "welcome@systemzero.dev")
EMAIL_OUTBOX_DIR = Path(os.environ.get("EMAIL_OUTBOX_DIR", "/data/outbox"))

if resend is not None and os.environ.get("RESEND_API_KEY"):
    resend.api_key = os.environ["RESEND_API_KEY"]

CATALOG_REMOTE = "https://raw.githubusercontent.com/systemzero-dev/catalog/main/index.json"

app = FastAPI(title="sz-cloud", version="0.1.0")


# ---- Clerk JWT verification ----

import jwt  # pyjwt, add to requirements
from functools import lru_cache

@lru_cache(maxsize=1)
def _clerk_jwks() -> dict:
    with httpx.Client(timeout=15) as c:
        return c.get(CLERK_JWKS_URL).json()


def require_user(authorization: str | None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        key = next(k for k in _clerk_jwks()["keys"] if k["kid"] == kid)
        public_key = jwt.PyJWK(key).key
        claims = jwt.decode(token, public_key, algorithms=["RS256"], options={"verify_aud": False})
    except Exception as e:
        raise HTTPException(401, f"invalid token: {e}")
    return {"sub": claims["sub"], "email": claims.get("email","")}


def tier_of(clerk_user_id: str) -> str:
    r = supa.table("users").select("tier").eq("clerk_user_id", clerk_user_id).maybe_single().execute()
    return (r.data or {}).get("tier", "free")


def send_transactional_email(*, to_email: str, subject: str, html: str) -> dict:
    if EMAIL_PROVIDER == "resend" and resend is not None and os.environ.get("RESEND_API_KEY"):
        try:
            resend.Emails.send({
                "from": EMAIL_FROM,
                "to": [to_email],
                "subject": subject,
                "html": html,
            })
            return {"status": "sent", "provider": "resend"}
        except Exception:
            pass

    EMAIL_OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = EMAIL_OUTBOX_DIR / f"{stamp}-{to_email.replace('@', '_at_')}.json"
    target.write_text(json.dumps({
        "provider": "outbox",
        "from": EMAIL_FROM,
        "to": to_email,
        "subject": subject,
        "html": html,
    }, indent=2))
    return {"status": "queued", "provider": "outbox", "path": str(target)}


# ---- Public catalog ----

_cache = {"catalog": None, "ts": 0}

@app.get("/v1/catalog/index")
async def get_catalog_index():
    now = datetime.now(timezone.utc).timestamp()
    if _cache["catalog"] and now - _cache["ts"] < 300:
        return _cache["catalog"]
    async with httpx.AsyncClient(timeout=10) as c:
        data = (await c.get(CATALOG_REMOTE)).json()
    _cache["catalog"] = data; _cache["ts"] = now
    return data

@app.get("/v1/catalog/modules/{mod_id}")
async def get_module(mod_id: str):
    idx = await get_catalog_index()
    for it in idx["items"]:
        if it["id"] == mod_id: return it
    raise HTTPException(404)


# ---- Public insights (network effect redistribution) ----

@app.get("/v1/insights/public")
def public_insights():
    trending = supa.table("mv_trending_modules").select("*").limit(20).execute().data
    bindings = supa.table("mv_capability_bindings").select("*").limit(50).execute().data
    return {"trending_modules": trending, "common_bindings": bindings}


# ---- Billing ----

@app.post("/v1/billing/checkout")
def create_checkout(payload: dict, authorization: str | None = Header(None)):
    if not BILLING_READY:
        raise HTTPException(503, "billing_not_configured")
    user = require_user(authorization)
    tier = payload["tier"]
    price = STRIPE_PRICE_PRO if tier == "pro" else STRIPE_PRICE_TEAM
    # Ensure the user row exists.
    supa.table("users").upsert({"clerk_user_id": user["sub"], "email": user["email"]}).execute()
    sess = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price, "quantity": 1}],
        success_url=payload.get("success_url", "https://systemzero.dev/welcome"),
        cancel_url=payload.get("cancel_url", "https://systemzero.dev/pricing"),
        customer_email=user["email"],
        client_reference_id=user["sub"],
        metadata={"tier": tier, "clerk_user_id": user["sub"]},
    )
    return {"id": sess.id, "url": sess.url}


@app.post("/v1/billing/webhook")
async def stripe_webhook(req: Request, stripe_signature: str = Header(None)):
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(503, "billing_not_configured")
    body = await req.body()
    try:
        event = stripe.Webhook.construct_event(body, stripe_signature, STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(400, "bad signature")
    if event["type"] == "checkout.session.completed":
        sess = event["data"]["object"]
        clerk_user_id = sess["metadata"]["clerk_user_id"]
        tier = sess["metadata"]["tier"]
        supa.table("users").update({
            "tier": tier,
            "stripe_customer_id": sess["customer"],
            "stripe_subscription_id": sess.get("subscription"),
        }).eq("clerk_user_id", clerk_user_id).execute()
        # Welcome email is best-effort: send via provider when available, otherwise queue durably to the outbox.
        u = supa.table("users").select("email").eq("clerk_user_id", clerk_user_id).single().execute().data
        send_transactional_email(
            to_email=u["email"],
            subject=f"Welcome to System Zero {tier.title()}",
            html="<p>Your repo just got sharper. <a href='https://systemzero.dev/docs'>Start here</a>.</p>",
        )
    elif event["type"] == "customer.subscription.deleted":
        sub = event["data"]["object"]
        supa.table("users").update({"tier": "free", "stripe_subscription_id": None}) \
            .eq("stripe_subscription_id", sub["id"]).execute()
    return Response(status_code=200)


@app.get("/v1/me")
def me(authorization: str | None = Header(None)):
    user = require_user(authorization)
    t = tier_of(user["sub"])
    return {"sub": user["sub"], "email": user["email"], "tier": t}


# ---- Pro/Team: hosted absorb ----

@app.post("/v1/absorb")
def hosted_absorb(payload: dict, authorization: str | None = Header(None)):
    user = require_user(authorization)
    t = tier_of(user["sub"])
    if t not in ("pro", "team"):
        raise HTTPException(402, "Pro or Team tier required")
    # Run the same absorb_prompt.md through whichever server provider is configured.
    # For v0.1 this is a thin pass-through to the OpenAI/Groq keys on the server;
    # full CLC discipline identical to the local `sz absorb`.
    from sz.core import absorb as engine  # import lazily to share the template + schema
    try:
        result = engine.absorb(payload["source"], payload["feature"],
                               ref=payload.get("ref"), module_id=payload.get("id"),
                               dry_run=True)
    except Exception as e:
        supa.table("absorb_records").insert({
            "clerk_user_id": user["sub"], "source_url": payload["source"], "feature": payload["feature"],
            "module_id": payload.get("id",""), "llm_provider": os.environ.get("SZ_LLM_PROVIDER","openai"),
            "status": "failed", "validation_errors": {"msg": str(e)[:500]}
        }).execute()
        raise HTTPException(422, f"absorb failed: {e}")
    supa.table("absorb_records").insert({
        "clerk_user_id": user["sub"], "source_url": payload["source"], "feature": payload["feature"],
        "module_id": result["draft"]["module_id"], "llm_provider": os.environ.get("SZ_LLM_PROVIDER","openai"),
        "status": "succeeded", "tokens_in": 0, "tokens_out": 0,
    }).execute()
    return result


# ---- Telemetry (opt-in, Pro/Team) ----

@app.post("/v1/telemetry")
def telemetry(payload: dict, authorization: str | None = Header(None)):
    user = require_user(authorization)
    if tier_of(user["sub"]) == "free":
        # Free tier is never collected from in v0.1. Silent accept, drop.
        return {"accepted": False, "reason": "free tier does not transmit"}
    install_id = payload.get("install_id")
    for ev in payload.get("events", []):
        supa.table("module_events").insert({
            "install_id": install_id, "event_type": ev["type"],
            "module_id": ev.get("module"), "payload": ev.get("payload", {})
        }).execute()
    return {"accepted": True, "count": len(payload.get("events", []))}


# ---- Team insights ----

@app.get("/v1/insights/team")
def team_insights(authorization: str | None = Header(None)):
    user = require_user(authorization)
    if tier_of(user["sub"]) != "team":
        raise HTTPException(402, "Team tier required")
    u = supa.table("users").select("team_id").eq("clerk_user_id", user["sub"]).single().execute().data
    if not u or not u.get("team_id"):
        return {"installs": [], "events_7d": 0}
    inst = supa.table("installs").select("*").eq("team_id", u["team_id"]).execute().data
    count = supa.table("module_events").select("id", count="exact").in_(
        "install_id", [i["id"] for i in inst]
    ).execute().count or 0
    return {"installs": inst, "events_7d": count}


# ---- Install bootstrap ----

@app.get("/i")
def install_script():
    p = Path(__file__).resolve().parents[2] / "install.sh"
    return Response(content=p.read_text(), media_type="text/x-shellscript")
```

### Step 10.4 — `cloud/Dockerfile`

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY app /app/app
# Hosted absorb shells out to git for GitHub sources.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates git \
 && rm -rf /var/lib/apt/lists/*
# Install runtime deps + the sz package itself, because /v1/absorb imports sz.core.absorb.
# We install system-zero from PyPI after it is published (phase 15). During development
# (pre-PyPI-publish) the build uses the fallback: COPY ../sz + pip install -e .
ARG SZ_SOURCE=pypi
RUN if [ "$SZ_SOURCE" = "pypi" ]; then \
      pip install --no-cache-dir fastapi uvicorn[standard] stripe httpx pyyaml supabase resend pyjwt[crypto] system-zero; \
    else \
      pip install --no-cache-dir fastapi uvicorn[standard] stripe httpx pyyaml supabase resend pyjwt[crypto]; \
    fi
# Dev-only fallback: if building pre-publish, the build step copies the sz/ dir alongside app/
# and installs it editable. The pre-publish Makefile target in step 10.6 handles this.
ENV PYTHONPATH=/app
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Pre-publish build (used until PyPI publish completes in phase 15):
```bash
# In cloud/Makefile, add:
deploy-prelaunch:
	rm -rf local-sz && cp -R ../sz local-sz && cp ../pyproject.toml .
	fly deploy --build-arg SZ_SOURCE=local \
	  --dockerfile Dockerfile.prelaunch
```

And `cloud/Dockerfile.prelaunch` (only used before PyPI publish):
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY app /app/app
COPY local-sz /app/sz
COPY pyproject.toml /app/pyproject.toml
# Hosted absorb imports the local package and shells out to git for GitHub sources.
# Editable install must include pyproject dependencies such as jsonschema.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates git \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir -e /app fastapi uvicorn[standard] stripe httpx supabase resend pyjwt[crypto]
ENV PYTHONPATH=/app
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Step 10.5 — `cloud/fly.toml`

```toml
app = "sz-cloud"
primary_region = "iad"

[build]

[env]
PORT = "8080"

[http_service]
internal_port = 8080
force_https = true
auto_stop_machines = true
auto_start_machines = true
min_machines_running = 1
```

No volume: Supabase holds all state.

### Step 10.6 — `cloud/Makefile`

```makefile
.PHONY: launch deploy logs ssh secrets

launch:
	fly launch --copy-config --no-deploy --name sz-cloud --region iad

secrets:
	# Resolve CLERK_JWKS_URL if not already set in the env.
	# Clerk exposes a per-instance frontend API host; the JWKS URL is <host>/.well-known/jwks.json.
	if [ -z "$$CLERK_JWKS_URL" ]; then \
	  CLERK_JWKS_URL=$$(curl -sS https://api.clerk.com/v1/jwks -H "Authorization: Bearer $$CLERK_SECRET_KEY" -o /dev/null -w '%{url_effective}\n' 2>/dev/null); \
	  if ! echo "$$CLERK_JWKS_URL" | grep -q "jwks"; then \
	    CLERK_FAPI=$$(curl -sS https://api.clerk.com/v1/instance -H "Authorization: Bearer $$CLERK_SECRET_KEY" | jq -r '.frontend_api // empty'); \
	    [ -n "$$CLERK_FAPI" ] && CLERK_JWKS_URL="https://$$CLERK_FAPI/.well-known/jwks.json"; \
	  fi; \
	  [ -z "$$CLERK_JWKS_URL" ] && { echo "CLERK_JWKS_URL could not be resolved; set it manually in .env"; exit 2; }; \
	fi; \
	fly secrets set \
	  STRIPE_SECRET_KEY=$$STRIPE_SECRET_KEY \
	  STRIPE_PUBLISHABLE_KEY=$$STRIPE_PUBLISHABLE_KEY \
	  STRIPE_WEBHOOK_SECRET=$$STRIPE_WEBHOOK_SECRET \
	  STRIPE_PRICE_PRO=$$STRIPE_PRICE_PRO \
	  STRIPE_PRICE_TEAM=$$STRIPE_PRICE_TEAM \
	  CLERK_SECRET_KEY=$$CLERK_SECRET_KEY \
	  CLERK_JWKS_URL="$$CLERK_JWKS_URL" \
	  SUPABASE_URL=$$SUPABASE_URL \
	  SUPABASE_SERVICE_ROLE_KEY=$$SUPABASE_SERVICE_ROLE_KEY \
	  RESEND_API_KEY=$$RESEND_API_KEY \
	  OPENAI_API_KEY=$$OPENAI_API_KEY \
	  GROQ_API_KEY=$$GROQ_API_KEY

deploy: secrets
	fly deploy

logs:
	fly logs

ssh:
	fly ssh console
```

### Step 10.7 — Create Stripe products + prices (with live-mode bypass)

Live-mode Stripe creates customer-facing prices — this is expensive to clean up if done in error. Per Appendix A in `plan/EXECUTION_RULES.md`, when `STRIPE_SECRET_KEY` starts with `sk_live_` and `STRIPE_AUTO_CREATE=1` is not set, we skip product creation and let the cloud API return `billing_not_configured` on upgrade attempts. The run continues; the operator flips `STRIPE_AUTO_CREATE=1` and re-runs only this step later.

```bash
. ./.env

LIVE_MODE=0
case "$STRIPE_SECRET_KEY" in sk_live_*) LIVE_MODE=1 ;; esac

if [ "$LIVE_MODE" = "1" ] && [ "${STRIPE_AUTO_CREATE:-0}" != "1" ]; then
  echo "stripe: LIVE mode detected without STRIPE_AUTO_CREATE=1 → deferring product creation"
  {
    echo ""
    echo "## $(date -u +%FT%TZ) · phase-10 · stripe-live-deferred"
    echo ""
    echo "- **Category**: deferred"
    echo "- **What failed**: STRIPE_SECRET_KEY is live-mode; STRIPE_AUTO_CREATE not set"
    echo "- **Bypass applied**: Stripe product/price creation skipped; /v1/billing/checkout returns 503"
    echo "- **Downstream effect**: website shows upgrade buttons but clicking returns 'Billing setup pending'"
    echo "- **Action to resolve**: set STRIPE_AUTO_CREATE=1 in .env, then run: bash tooling/retry-stripe-create.sh"
    echo "- **Run command to retry only this bypass**: STRIPE_AUTO_CREATE=1 bash tooling/retry-stripe-create.sh"
  } >> BLOCKERS.md
  python3 - <<'PY'
import json, pathlib
p = pathlib.Path(".s0-release.json"); s = json.loads(p.read_text())
s["billing"] = {"status": "deferred", "reason": "live-mode_without_opt_in"}
s["degraded"].append("phase-10: billing deferred (live-mode Stripe, no opt-in)")
p.write_text(json.dumps(s, indent=2))
PY
else
  PRO_PRODUCT=$(curl -sS https://api.stripe.com/v1/products -u "$STRIPE_SECRET_KEY:" -d name="System Zero Pro"  -d description="Hosted catalog + cloud absorb + telemetry + insights" | jq -r .id)
  PRO_PRICE=$(curl -sS https://api.stripe.com/v1/prices -u "$STRIPE_SECRET_KEY:" -d product=$PRO_PRODUCT -d unit_amount=1900 -d currency=usd -d "recurring[interval]=month" | jq -r .id)
  TEAM_PRODUCT=$(curl -sS https://api.stripe.com/v1/products -u "$STRIPE_SECRET_KEY:" -d name="System Zero Team" -d description="Pro + shared library + audit + team insights + SSO" | jq -r .id)
  TEAM_PRICE=$(curl -sS https://api.stripe.com/v1/prices -u "$STRIPE_SECRET_KEY:" -d product=$TEAM_PRODUCT -d unit_amount=4900 -d currency=usd -d "recurring[interval]=month" | jq -r .id)

  echo "STRIPE_PRICE_PRO=$PRO_PRICE"   >> .env.cloud
  echo "STRIPE_PRICE_TEAM=$TEAM_PRICE" >> .env.cloud
  python3 - <<PY
import json, pathlib
p = pathlib.Path(".s0-release.json"); s = json.loads(p.read_text())
s["billing"] = {"status": "live" if "$LIVE_MODE" == "1" else "test",
                "price_pro": "$PRO_PRICE", "price_team": "$TEAM_PRICE"}
p.write_text(json.dumps(s, indent=2))
PY
fi
```

Write `tooling/retry-stripe-create.sh` that re-runs just the non-deferred branch above against the now-opt-in env. Idempotent by `curl`'s product POST — a second call creates a duplicate; skip that by checking `.env.cloud` first.

### Step 10.8 — Configure Stripe webhook

```bash
API_ENDPOINT=$(jq -r '.endpoints.api // "https://api.systemzero.dev"' .s0-release.json)
HOOK=$(curl -sS https://api.stripe.com/v1/webhook_endpoints -u "$STRIPE_SECRET_KEY:" \
  -d url="$API_ENDPOINT/v1/billing/webhook" \
  -d "enabled_events[]=checkout.session.completed" \
  -d "enabled_events[]=customer.subscription.deleted")
SECRET=$(echo "$HOOK" | jq -r .secret)
# Add STRIPE_WEBHOOK_SECRET=$SECRET to .env for both local and fly secrets.
```

### Step 10.9 — Launch + deploy on Fly.io (with auto-rename on name collision)

```bash
cd cloud
. ../.env
. ../.env.cloud

# Try preferred name first; on collision, append numeric suffixes until success.
APP_NAME="sz-cloud"
for i in "" -2 -3 -4 -5 -6 -7 -8 -9; do
  candidate="sz-cloud$i"
  if fly apps create "$candidate" --org personal >/dev/null 2>&1 \
     || fly status -a "$candidate" >/dev/null 2>&1; then
    APP_NAME="$candidate"; break
  fi
done
echo "fly app: $APP_NAME"

# Patch fly.toml with the chosen name (idempotent).
sed -i.bak "s/^app = \".*\"/app = \"$APP_NAME\"/" fly.toml
rm -f fly.toml.bak

make secrets
fly deploy -a "$APP_NAME"
fly status -a "$APP_NAME"

# Record the chosen app name for downstream phases.
python3 - <<PY
import json, pathlib
p = pathlib.Path("../.s0-release.json"); s = json.loads(p.read_text())
s.setdefault("fly_apps", {})["cloud"] = "$APP_NAME"
if "$APP_NAME" != "sz-cloud":
    s["degraded"].append("phase-10: fly app auto-renamed to $APP_NAME (sz-cloud taken)")
    with open("../BLOCKERS.md", "a") as f:
        import datetime
        f.write(f"\n## {datetime.datetime.now(datetime.UTC).isoformat(timespec='seconds').replace('+00:00','Z')} · phase-10 · fly-app-renamed\n\n")
        f.write("- **Category**: degraded\n")
        f.write("- **What failed**: sz-cloud already exists on this Fly account\n")
        f.write("- **Bypass applied**: Fly-app-name-taken — renamed to $APP_NAME\n")
        f.write("- **Downstream effect**: DNS CNAME points at $APP_NAME.fly.dev\n")
        f.write("- **Action to resolve**: optional; the renamed app works. If you want the canonical name, destroy the conflict and re-run.\n")
        f.write("- **Run command to retry only this bypass**: fly apps destroy sz-cloud && rerun phase 10\n")
p.write_text(json.dumps(s, indent=2))
PY
cd ..
```

Verify:
```bash
APP_NAME=$(jq -r '.fly_apps.cloud' .s0-release.json)
curl -sSf "https://$APP_NAME.fly.dev/v1/catalog/index" | jq '.items | length'
```

### Step 10.10 — DNS (Hostinger only)

DNS is Hostinger-only. The working API base URL was recorded in `.tooling-report.json.hostinger_endpoint` during phase 00. Reuse it here. **Do not introduce any other DNS provider.**

```bash
. ./.env
ENDPOINT=$(jq -r '.hostinger_endpoint' .tooling-report.json)
FLY_CLOUD=$(jq -r '.fly_apps.cloud // "sz-cloud"' .s0-release.json)

if [ -z "$ENDPOINT" ] || [ "$ENDPOINT" = "null" ]; then
  echo "no hostinger_endpoint in tooling report; api DNS deferred"
  {
    echo ""
    echo "## $(date -u +%FT%TZ) · phase-10 · dns-endpoint-deferred-all"
    echo ""
    echo "- **Category**: deferred"
    echo "- **What failed**: .tooling-report.json.hostinger_endpoint is empty"
    echo "- **Bypass applied**: api DNS skipped for all zones; service stays on $FLY_CLOUD.fly.dev"
    echo "- **Downstream effect**: CLI and website use https://$FLY_CLOUD.fly.dev until DNS is repaired"
    echo "- **Action to resolve**: fix Hostinger endpoint discovery and run bash tooling/retry-dns.sh all api"
    echo "- **Run command to retry only this bypass**: bash tooling/retry-dns.sh all api"
  } >> BLOCKERS.md
  python3 - <<PY
import json, pathlib
p = pathlib.Path(".s0-release.json"); s = json.loads(p.read_text())
s["dns"] = {"status": "deferred", "reason": "missing_hostinger_endpoint"}
s["endpoints"]["api"] = "https://$FLY_CLOUD.fly.dev"
s["degraded"].append("phase-10: api dns deferred for all zones (no hostinger endpoint)")
p.write_text(json.dumps(s, indent=2))
PY
  exit 0
fi

for DOMAIN in systemzero.dev system0.dev; do
  # 1) Resolve the zone id for this domain.
  ZONE_ID=$(curl -sS -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
    "$ENDPOINT/zones?name=$DOMAIN" | jq -r '(.data // .zones // .result // [])[0].id // empty')

  if [ -z "$ZONE_ID" ]; then
    # SOFT blocker per Appendix A in plan/EXECUTION_RULES.md — skip DNS for this zone; endpoint stays on .fly.dev.
    echo "zone $DOMAIN not visible to token → DNS deferred for $DOMAIN"
    {
      echo ""
      echo "## $(date -u +%FT%TZ) · phase-10 · dns-zone-deferred"
      echo ""
      echo "- **Category**: deferred"
      echo "- **What failed**: Hostinger zone lookup for $DOMAIN returned empty"
      echo "- **Bypass applied**: Hostinger-zone-not-visible — api.$DOMAIN not provisioned; service stays on $FLY_CLOUD.fly.dev"
      echo "- **Downstream effect**: CLI + website point at https://$FLY_CLOUD.fly.dev until this is fixed"
      echo "- **Action to resolve**: rotate token with DNS-write scope for $DOMAIN at hpanel.hostinger.com"
      echo "- **Run command to retry only this bypass**: bash tooling/retry-dns.sh $DOMAIN api"
    } >> BLOCKERS.md
    python3 - <<PY
import json, pathlib
p = pathlib.Path(".s0-release.json"); s = json.loads(p.read_text())
s["dns"] = {"status": "deferred", "reason": "zone_not_visible", "zone": "$DOMAIN"}
s["endpoints"]["api"] = "https://$FLY_CLOUD.fly.dev"
if "phase-10: dns api.$DOMAIN deferred" not in s["degraded"]:
    s["degraded"].append("phase-10: dns api.$DOMAIN deferred")
p.write_text(json.dumps(s, indent=2))
PY
    continue
  fi

  # 2) Idempotent: check if api.<domain> CNAME already exists.
  EXISTING=$(curl -sS -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
    "$ENDPOINT/zones/$ZONE_ID/records?name=api&type=CNAME" | jq -r '(.data // .records // .result // [])[0].id // empty')

  # 3) Create or update. CNAME target is the actual Fly app name (may be renamed).
  if [ -z "$EXISTING" ]; then
    curl -sS -X POST -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
      -H "Content-Type: application/json" \
      "$ENDPOINT/zones/$ZONE_ID/records" \
      -d "{\"name\":\"api\",\"type\":\"CNAME\",\"value\":\"$FLY_CLOUD.fly.dev\",\"ttl\":300}"
  else
    curl -sS -X PUT -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
      -H "Content-Type: application/json" \
      "$ENDPOINT/zones/$ZONE_ID/records/$EXISTING" \
      -d "{\"name\":\"api\",\"type\":\"CNAME\",\"value\":\"$FLY_CLOUD.fly.dev\",\"ttl\":300}"
  fi
done

API_ENDPOINT=$(jq -r '.endpoints.api // "https://api.systemzero.dev"' .s0-release.json)
if [ "$API_ENDPOINT" = "https://api.systemzero.dev" ]; then
  cd cloud
  fly certs add api.systemzero.dev
  fly certs check api.systemzero.dev
  cd ..
else
  echo "api dns deferred; skipping custom-domain cert checks"
fi
```

NOTE on API shape: the Hostinger DNS API's exact request/response body keys may differ from what is shown above depending on the surface discovered in phase 00. The script tolerates the common variants (`.data // .zones // .result`). If all return empty, the `if [ -z "$ZONE_ID" ]; then continue` branch above kicks in: DNS is soft-skipped for that zone, BLOCKERS.md records the deferral, and the run continues using `sz-cloud.fly.dev` as the endpoint. **Never** substitute another DNS provider.

Verify (5-30 min propagation; `.fly.dev` also counts when DNS is deferred):
```bash
API_ENDPOINT=$(jq -r '.endpoints.api // "https://api.systemzero.dev"' .s0-release.json)
API_HOST="${API_ENDPOINT#https://}"
dig +short "$API_HOST" || true
curl -sSf "$API_ENDPOINT/v1/catalog/index" | jq '.items | length'
```

### Step 10.11 — CLI side: `sz/cloud/client.py`

```python
"""Talks to sz-cloud via Clerk JWT stored at ~/.sz/token."""
from __future__ import annotations
import json, os
import urllib.request
from pathlib import Path
import yaml
from sz.core import paths


def _endpoint() -> str:
    cfg_p = paths.user_config_dir() / "config.yaml"
    if cfg_p.exists():
        cfg = yaml.safe_load(cfg_p.read_text()) or {}
        if cfg.get("cloud_endpoint"): return cfg["cloud_endpoint"]
    return os.environ.get("SZ_CLOUD", "https://api.systemzero.dev")


def _token() -> str | None:
    p = paths.user_config_dir() / "token"
    return p.read_text().strip() if p.exists() else None


def _req(method: str, path: str, body: dict | None = None) -> dict:
    url = _endpoint() + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"content-type": "application/json"}
    tok = _token()
    if tok: headers["authorization"] = f"Bearer {tok}"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def me() -> dict | None:
    try: return _req("GET", "/v1/me")
    except Exception: return None


def checkout(tier: str, success_url: str, cancel_url: str) -> dict:
    return _req("POST", "/v1/billing/checkout",
                {"tier": tier, "success_url": success_url, "cancel_url": cancel_url})


def hosted_absorb(source: str, feature: str, module_id: str | None = None) -> dict:
    return _req("POST", "/v1/absorb", {"source": source, "feature": feature, "id": module_id})


def public_insights() -> dict:
    return _req("GET", "/v1/insights/public")


def team_insights() -> dict:
    return _req("GET", "/v1/insights/team")


def telemetry(install_id: str, events: list[dict]) -> dict:
    return _req("POST", "/v1/telemetry", {"install_id": install_id, "events": events})
```

### Step 10.12 — `sz login`, `sz upgrade`, `sz insights`

`sz/commands/login.py`:
```python
"""sz login: paste a Clerk-issued JWT from the website after sign-in."""
import click
from sz.core import paths

@click.command(help="Paste the Clerk JWT from systemzero.dev/token to authenticate.")
@click.argument("token")
def cmd(token):
    p = paths.user_config_dir() / "token"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(token.strip())
    p.chmod(0o600)
    click.echo("token saved")
```

`sz/commands/upgrade.py`:
```python
import click, webbrowser
from sz.cloud import client

@click.command(help="Open Stripe checkout to upgrade to Pro or Team.")
@click.option("--tier", type=click.Choice(["pro","team"]), default="pro")
def cmd(tier):
    sess = client.checkout(tier=tier,
                           success_url="https://systemzero.dev/welcome",
                           cancel_url="https://systemzero.dev/pricing")
    click.echo(f"Open: {sess['url']}")
    webbrowser.open(sess["url"])
```

`sz/commands/insights.py`:
```python
"""sz insights — the redistribution side of the network effect."""
import click, json
from sz.cloud import client

@click.command(help="Show community-wide or team-private aggregations from the cloud.")
@click.option("--scope", type=click.Choice(["public","team"]), default="public")
def cmd(scope):
    if scope == "public":
        data = client.public_insights()
    else:
        data = client.team_insights()
    click.echo(json.dumps(data, indent=2))
```

Register all three in `sz/commands/cli.py`.

### Step 10.13 — Telemetry integration

Add a background thread inside `sz tick` that batches and flushes `module_events` to `/v1/telemetry` when:

- The user has a saved token.
- `.sz.yaml` has `cloud.telemetry: true` (opt-in explicit).
- Tier is `pro` or `team` (Free tier never transmits).

`.sz.yaml` default is `cloud.telemetry: false` even for Pro/Team — opt-in must be explicit by the user editing the file or running `sz telemetry enable`.

### Step 10.14 — Tests

`cloud/tests/test_endpoints.py`: spin up FastAPI with TestClient. Mock Clerk JWKS with a local signing keypair; mock Stripe webhook signatures with the test secret. Hit every endpoint; assert shapes.

`cloud/tests/test_billing_flow.py`: simulate checkout.session.completed → user tier flips to pro → subsequent /v1/absorb succeeds.

`cloud/tests/test_free_tier_silent.py`: /v1/telemetry with a free-tier user returns `{accepted:false}` and no rows are inserted.

Run:
```bash
python3 -m pytest cloud/tests -q
```

### Step 10.15 — Commit

```bash
git add cloud sz/cloud sz/commands/login.py sz/commands/upgrade.py sz/commands/insights.py plan/phase-10-cloud-and-billing
git commit -m "phase 10: cloud + supabase + clerk + stripe + resend + groq + data network"
```

## Acceptance criteria

1. `$(jq -r '.endpoints.api' .s0-release.json)/v1/catalog/index` returns the catalog over TLS, CORS-open.
2. Stripe Pro and Team prices exist; webhook is registered with `.env.STRIPE_WEBHOOK_SECRET`.
3. A Stripe test-mode checkout completes; webhook fires; Supabase `users` row has `tier='pro'`; the welcome email is either sent through the configured provider or queued durably to the outbox.
4. `sz login <clerk-jwt>` saves token; `sz upgrade --tier pro` opens a working checkout URL.
5. `sz insights --scope public` returns JSON with `trending_modules` and `common_bindings`.
6. Free-tier telemetry POST returns `{accepted:false}`; Pro telemetry POST records events in Supabase.
7. `pytest cloud/tests -q` is green.
8. `$(jq -r '.endpoints.api' .s0-release.json)/i` returns the install.sh content.

## Failure modes and recovery

| Symptom | Cause | Action |
|---|---|---|
| Clerk JWKS 404 | wrong `CLERK_JWKS_URL` | find the correct URL in Clerk dashboard → API Keys; set env override |
| Supabase `exec_sql` RPC unavailable | tenant lacks that function | paste the SQL into Supabase Dashboard SQL editor manually |
| Stripe webhook signature mismatch | wrong secret env | re-run step 10.8 |
| Hostinger DNS API returns empty / unknown body shape | the account's Hostinger surface differs from documented variants | Soft-bypass per Appendix A: skip DNS for that zone, annotate `BLOCKERS.md`, use `sz-cloud.fly.dev` as endpoint. Morning triage pins the correct body shape. **Never fall back to another DNS provider** — DNS is Hostinger-only by policy. |
| Resend unavailable / domain not verified | first deploy or provider issue | queue the welcome email to the outbox fallback; do not block billing, deploy, or launch |
| PostHog collects without consent | bug | telemetry must be gated by `cloud.telemetry: true` in `.sz.yaml` — unit test covers |
| MV refresh never runs | no cron | create a Supabase Edge Function scheduled cron to `refresh materialized view`; stub in this phase, implement pre-launch |

## Rollback

```
cd cloud && fly destroy sz-cloud --yes
git checkout main && git branch -D phase-10-cloud-and-billing
# Stripe products: deactivate via dashboard
# Supabase: keep the schema; it's safe to empty
```
