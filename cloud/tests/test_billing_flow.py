from __future__ import annotations

import json
from types import SimpleNamespace


def test_checkout_webhook_upgrade_then_hosted_absorb(cloud_app, monkeypatch) -> None:
    main, fake, client, headers = cloud_app

    monkeypatch.setattr(
        main.stripe.checkout.Session,
        "create",
        lambda **kwargs: SimpleNamespace(id="cs_test", url="https://stripe.test/checkout"),
    )
    checkout = client.post(
        "/v1/billing/checkout",
        json={"tier": "pro", "success_url": "https://ok", "cancel_url": "https://cancel"},
        headers=headers,
    )
    assert checkout.status_code == 200
    assert checkout.json()["url"] == "https://stripe.test/checkout"
    assert fake.rows["users"][0]["clerk_user_id"] == "user_1"

    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {"clerk_user_id": "user_1", "tier": "pro"},
                "customer": "cus_123",
                "subscription": "sub_123",
            }
        },
    }
    monkeypatch.setattr(
        main.stripe.Webhook,
        "construct_event",
        lambda body, signature, secret: json.loads(body),
    )
    webhook = client.post(
        "/v1/billing/webhook",
        content=json.dumps(event),
        headers={"stripe-signature": "mocked"},
    )
    assert webhook.status_code == 200
    assert fake.rows["users"][0]["tier"] == "pro"

    from sz.core import absorb as absorb_engine

    monkeypatch.setattr(
        absorb_engine,
        "absorb",
        lambda source, feature, ref=None, module_id=None, dry_run=False: {
            "staging": "/tmp/staging",
            "draft": {"module_id": module_id or "absorbed-feature"},
        },
    )
    absorb = client.post(
        "/v1/absorb",
        json={"source": "https://github.com/example/repo", "feature": "cache", "id": "cache-module"},
        headers=headers,
    )
    assert absorb.status_code == 200
    assert absorb.json()["draft"]["module_id"] == "cache-module"
    assert fake.rows["absorb_records"][0]["status"] == "succeeded"


def test_billing_portal_uses_phase_schema_customer(cloud_app, monkeypatch) -> None:
    main, fake, client, headers = cloud_app
    captured: dict = {}
    fake.rows["users"].append({
        "clerk_user_id": "user_1",
        "email": "avi@example.com",
        "tier": "pro",
        "stripe_customer_id": "cus_phase",
    })

    def create_portal(**kwargs):
        captured["kwargs"] = kwargs
        return SimpleNamespace(url="https://stripe.test/portal")

    monkeypatch.setattr(main.stripe.billing_portal.Session, "create", create_portal)

    portal = client.post(
        "/v1/billing/portal",
        json={"return_url": "https://systemzero.dev/account"},
        headers=headers,
    )

    assert portal.status_code == 200
    assert portal.json()["url"] == "https://stripe.test/portal"
    assert captured["kwargs"]["customer"] == "cus_phase"
