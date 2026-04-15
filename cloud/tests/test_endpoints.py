from __future__ import annotations


def test_public_endpoints_and_install_script(cloud_app) -> None:
    _main, _fake, client, _headers = cloud_app

    catalog = client.get("/v1/catalog/index")
    assert catalog.status_code == 200
    assert catalog.json()["items"][0]["id"] == "heartbeat"

    module = client.get("/v1/catalog/modules/heartbeat")
    assert module.status_code == 200
    assert module.json()["description"] == "Pulse"

    insights = client.get("/v1/insights/public")
    assert insights.status_code == 200
    assert set(insights.json()) == {"trending_modules", "common_bindings"}

    installer = client.get("/i")
    assert installer.status_code == 200
    assert "System Zero installer" in installer.text
    assert installer.headers["content-type"].startswith("text/x-shellscript")

    cors = client.options(
        "/v1/catalog/index",
        headers={"Origin": "https://systemzero.dev", "Access-Control-Request-Method": "GET"},
    )
    assert cors.headers["access-control-allow-origin"] == "*"


def test_me_and_billing_not_configured(cloud_app, monkeypatch) -> None:
    main, fake, client, headers = cloud_app
    fake.rows["users"].append({"clerk_user_id": "user_1", "email": "avi@example.com", "tier": "free"})
    main.BILLING_READY = False

    me = client.get("/v1/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["tier"] == "free"

    checkout = client.post("/v1/billing/checkout", json={"tier": "pro"}, headers=headers)
    assert checkout.status_code == 503
    assert checkout.json()["detail"] == "billing_not_configured"

    main.BILLING_READY = True
