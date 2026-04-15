"""sz-cloud: catalog mirror + Clerk auth + Supabase persistence + Stripe billing + provider-pluggable email + hosted absorb + telemetry."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
import jwt
import stripe
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from supabase import Client, create_client

try:
    import resend
except Exception:  # keep startup alive when the provider is unavailable
    resend = None

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
supa: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_PRO = os.environ.get("STRIPE_PRICE_PRO", "")
STRIPE_PRICE_TEAM = os.environ.get("STRIPE_PRICE_TEAM", "")
BILLING_READY = bool(STRIPE_WEBHOOK_SECRET and STRIPE_PRICE_PRO and STRIPE_PRICE_TEAM)

CLERK_SECRET = os.environ["CLERK_SECRET_KEY"]
CLERK_JWKS_URL = os.environ.get("CLERK_JWKS_URL", "https://clerk.systemzero.dev/.well-known/jwks.json")

EMAIL_PROVIDER = os.environ.get("EMAIL_PROVIDER", "resend")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "welcome@systemzero.dev")
EMAIL_OUTBOX_DIR = Path(os.environ.get("EMAIL_OUTBOX_DIR", "/data/outbox"))

if resend is not None and os.environ.get("RESEND_API_KEY"):
    resend.api_key = os.environ["RESEND_API_KEY"]

CATALOG_REMOTE = "https://raw.githubusercontent.com/systemzero-dev/catalog/main/index.json"
POSTHOG_KEY = os.environ.get("POSTHOG_KEY") or os.environ.get("NEXT_PUBLIC_POSTHOG_KEY", "")
POSTHOG_HOST = (
    os.environ.get("POSTHOG_HOST")
    or os.environ.get("NEXT_PUBLIC_POSTHOG_HOST")
    or "https://app.posthog.com"
).rstrip("/")


def _asset_path(*parts: str) -> Path:
    here = Path(__file__).resolve()
    for base in (here.parents[2], here.parents[1]):
        candidate = base.joinpath(*parts)
        if candidate.exists():
            return candidate
    return here.parents[2].joinpath(*parts)


CATALOG_LOCAL = _asset_path("catalog", "index.json")

app = FastAPI(title="sz-cloud", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Clerk JWT verification ----


@lru_cache(maxsize=1)
def _clerk_jwks() -> dict[str, Any]:
    with httpx.Client(timeout=15) as c:
        response = c.get(CLERK_JWKS_URL)
        response.raise_for_status()
        return response.json()


def require_user(authorization: str | None) -> dict[str, str]:
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
        raise HTTPException(401, f"invalid token: {e}") from e
    return {"sub": claims["sub"], "email": claims.get("email", "")}


def tier_of(clerk_user_id: str) -> str:
    r = supa.table("users").select("tier").eq("clerk_user_id", clerk_user_id).maybe_single().execute()
    return (r.data or {}).get("tier", "free")


def send_transactional_email(*, to_email: str, subject: str, html: str) -> dict[str, Any]:
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


def _stripe_customer_id_for_user(user: dict[str, str]) -> str | None:
    row = supa.table("users").select("stripe_customer_id").eq(
        "clerk_user_id", user["sub"]
    ).maybe_single().execute().data or {}
    return row.get("stripe_customer_id")


def _ensure_user(user: dict[str, str]) -> None:
    supa.table("users").upsert({
        "clerk_user_id": user["sub"],
        "email": user["email"] or f"{user['sub']}@systemzero.dev",
    }).execute()


def _record_subscription(
    *,
    clerk_user_id: str,
    email: str,
    tier: str,
    stripe_customer_id: str,
    stripe_subscription_id: str | None,
    stripe_price_id: str | None,
) -> None:
    supa.table("users").upsert({
        "clerk_user_id": clerk_user_id,
        "email": email or f"{clerk_user_id}@systemzero.dev",
        "tier": tier,
        "stripe_customer_id": stripe_customer_id,
        "stripe_subscription_id": stripe_subscription_id,
    }).execute()


def _record_subscription_deleted(stripe_subscription_id: str) -> None:
    supa.table("users").update({"tier": "free", "stripe_subscription_id": None}) \
        .eq("stripe_subscription_id", stripe_subscription_id).execute()


def _record_absorb(
    *,
    clerk_user_id: str,
    source_url: str,
    feature: str,
    module_id: str,
    status: str,
    validation_errors: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "clerk_user_id": clerk_user_id,
        "source_url": source_url,
        "feature": feature,
        "module_id": module_id,
        "llm_provider": os.environ.get("SZ_LLM_PROVIDER", "openai"),
        "status": status,
    }
    if status == "succeeded":
        payload.update({"tokens_in": 0, "tokens_out": 0})
    if validation_errors is not None:
        payload["validation_errors"] = validation_errors
    supa.table("absorb_records").insert(payload).execute()


def _posthog_capture(*, distinct_id: str, event: str, properties: dict[str, Any]) -> None:
    if not POSTHOG_KEY:
        return
    try:
        with httpx.Client(timeout=5) as c:
            response = c.post(
                f"{POSTHOG_HOST}/capture/",
                json={
                    "api_key": POSTHOG_KEY,
                    "distinct_id": distinct_id,
                    "event": event,
                    "properties": properties,
                },
            )
            response.raise_for_status()
    except Exception:
        # Appendix A: PostHog is opt-in and non-essential; rejected events are dropped.
        return


# ---- Public catalog ----

_cache: dict[str, Any] = {"catalog": None, "ts": 0}


@app.get("/v1/catalog/index")
async def get_catalog_index() -> dict[str, Any]:
    now = datetime.now(timezone.utc).timestamp()
    if _cache["catalog"] and now - _cache["ts"] < 300:
        return _cache["catalog"]
    async with httpx.AsyncClient(timeout=10) as c:
        response = await c.get(CATALOG_REMOTE)
        if response.status_code == 404 and CATALOG_LOCAL.exists():
            data = json.loads(CATALOG_LOCAL.read_text())
        else:
            response.raise_for_status()
            data = response.json()
    _cache["catalog"] = data
    _cache["ts"] = now
    return data


@app.get("/v1/catalog/modules/{mod_id}")
async def get_module(mod_id: str) -> dict[str, Any]:
    idx = await get_catalog_index()
    for it in idx["items"]:
        if it["id"] == mod_id:
            return it
    raise HTTPException(404)


# ---- Public insights (network effect redistribution) ----


@app.get("/v1/insights/public")
def public_insights() -> dict[str, Any]:
    trending = supa.table("mv_trending_modules").select("*").limit(20).execute().data
    bindings = supa.table("mv_capability_bindings").select("*").limit(50).execute().data
    return {"trending_modules": trending, "common_bindings": bindings}


# ---- Billing ----


@app.post("/v1/billing/checkout")
def create_checkout(payload: dict[str, Any], authorization: str | None = Header(None)) -> dict[str, Any]:
    if not BILLING_READY:
        raise HTTPException(503, "billing_not_configured")
    user = require_user(authorization)
    tier = payload["tier"]
    if tier not in ("pro", "team"):
        raise HTTPException(400, "tier must be pro or team")
    price = STRIPE_PRICE_PRO if tier == "pro" else STRIPE_PRICE_TEAM
    _ensure_user(user)
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


@app.post("/v1/billing/portal")
def billing_portal(payload: dict[str, Any], authorization: str | None = Header(None)) -> dict[str, str]:
    if not BILLING_READY:
        raise HTTPException(503, "billing_not_configured")
    user = require_user(authorization)
    customer_id = _stripe_customer_id_for_user(user)
    if not customer_id:
        raise HTTPException(404, "stripe_customer_not_found")
    sess = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=payload.get("return_url", "https://systemzero.dev/account"),
    )
    return {"url": sess.url}


@app.post("/v1/billing/webhook")
async def stripe_webhook(req: Request, stripe_signature: str = Header(None)) -> Response:
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(503, "billing_not_configured")
    body = await req.body()
    try:
        event = stripe.Webhook.construct_event(body, stripe_signature, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        raise HTTPException(400, "bad signature") from e
    if event["type"] == "checkout.session.completed":
        sess = event["data"]["object"]
        clerk_user_id = sess["metadata"]["clerk_user_id"]
        tier = sess["metadata"]["tier"]
        email = sess.get("customer_details", {}).get("email") or sess.get("customer_email") or ""
        if not email:
            u = supa.table("users").select("email").eq("clerk_user_id", clerk_user_id).single().execute().data or {}
            email = u.get("email", "")
        _record_subscription(
            clerk_user_id=clerk_user_id,
            email=email,
            tier=tier,
            stripe_customer_id=sess["customer"],
            stripe_subscription_id=sess.get("subscription"),
            stripe_price_id=sess.get("metadata", {}).get("stripe_price_id"),
        )
        send_transactional_email(
            to_email=email,
            subject=f"Welcome to System Zero {tier.title()}",
            html="<p>Your repo just got sharper. <a href='https://systemzero.dev/docs'>Start here</a>.</p>",
        )
    elif event["type"] == "customer.subscription.deleted":
        sub = event["data"]["object"]
        _record_subscription_deleted(sub["id"])
    return Response(status_code=200)


@app.get("/v1/me")
def me(authorization: str | None = Header(None)) -> dict[str, str]:
    user = require_user(authorization)
    t = tier_of(user["sub"])
    return {"sub": user["sub"], "email": user["email"], "tier": t}


# ---- Pro/Team: hosted absorb ----


@app.post("/v1/absorb")
def hosted_absorb(payload: dict[str, Any], authorization: str | None = Header(None)) -> dict[str, Any]:
    user = require_user(authorization)
    t = tier_of(user["sub"])
    if t not in ("pro", "team"):
        raise HTTPException(402, "Pro or Team tier required")
    from sz.core import absorb as engine
    try:
        result = engine.absorb(payload["source"], payload["feature"],
                               ref=payload.get("ref"), module_id=payload.get("id"),
                               dry_run=True)
    except Exception as e:
        _record_absorb(
            clerk_user_id=user["sub"],
            source_url=payload["source"],
            feature=payload["feature"],
            module_id=payload.get("id", ""),
            status="failed",
            validation_errors={"msg": str(e)[:500]},
        )
        raise HTTPException(422, f"absorb failed: {e}") from e
    _record_absorb(
        clerk_user_id=user["sub"],
        source_url=payload["source"],
        feature=payload["feature"],
        module_id=result["draft"]["module_id"],
        status="succeeded",
    )
    return result


# ---- Telemetry (opt-in, Pro/Team) ----


def _install_payload(payload: dict[str, Any], user: dict[str, str]) -> dict[str, Any]:
    repo_fingerprint = payload.get("repo_fingerprint")
    if not repo_fingerprint:
        repo_fingerprint = hashlib.sha256(user["sub"].encode()).hexdigest()
    return {
        "id": payload["install_id"],
        "clerk_user_id": user["sub"],
        "repo_fingerprint": repo_fingerprint,
        "host": payload.get("host", "unknown"),
        "host_mode": payload.get("host_mode", "install"),
        "sz_version": payload.get("sz_version", "0.1.0"),
    }


@app.post("/v1/telemetry")
def telemetry(payload: dict[str, Any], authorization: str | None = Header(None)) -> dict[str, Any]:
    user = require_user(authorization)
    if tier_of(user["sub"]) == "free":
        return {"accepted": False, "reason": "free tier does not transmit"}
    if payload.get("telemetry_opt_in") is not True:
        return {"accepted": False, "reason": "telemetry opt-in required"}
    install_id = payload.get("install_id")
    if not install_id:
        raise HTTPException(400, "install_id required")
    events = payload.get("events", [])
    supa.table("installs").upsert(_install_payload(payload, user), on_conflict="id").execute()
    for ev in events:
        supa.table("module_events").insert({
            "install_id": install_id,
            "event_type": ev["type"],
            "module_id": ev.get("module"),
            "payload": ev.get("payload", {}),
            "ts": ev.get("ts"),
        }).execute()
    for ev in events:
        _posthog_capture(
            distinct_id=user["sub"],
            event=f"sz.{ev['type']}",
            properties={
                "install_id": install_id,
                "module_id": ev.get("module"),
                "host": payload.get("host", "unknown"),
                "host_mode": payload.get("host_mode", "install"),
                "sz_version": payload.get("sz_version", "0.1.0"),
            },
        )
    return {"accepted": True, "count": len(events)}


# ---- Team insights ----


@app.get("/v1/insights/team")
def team_insights(authorization: str | None = Header(None)) -> dict[str, Any]:
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
def install_script() -> Response:
    p = _asset_path("install.sh")
    return Response(content=p.read_text(), media_type="text/x-shellscript")
