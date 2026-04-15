from __future__ import annotations


def test_free_tier_telemetry_silent_drop(cloud_app) -> None:
    _main, fake, client, headers = cloud_app
    fake.rows["users"].append({"clerk_user_id": "user_1", "email": "avi@example.com", "tier": "free"})

    result = client.post(
        "/v1/telemetry",
        json={
            "install_id": "00000000-0000-0000-0000-000000000001",
            "telemetry_opt_in": True,
            "events": [{"type": "module.installed", "module": "heartbeat", "payload": {}}],
        },
        headers=headers,
    )
    assert result.status_code == 200
    assert result.json() == {"accepted": False, "reason": "free tier does not transmit"}
    assert fake.rows["module_events"] == []


def test_pro_tier_telemetry_records_events(cloud_app) -> None:
    _main, fake, client, headers = cloud_app
    fake.rows["users"].append({"clerk_user_id": "user_1", "email": "avi@example.com", "tier": "pro"})

    result = client.post(
        "/v1/telemetry",
        json={
            "install_id": "00000000-0000-0000-0000-000000000001",
            "repo_fingerprint": "hash",
            "host": "generic",
            "host_mode": "install",
            "sz_version": "0.1.0",
            "telemetry_opt_in": True,
            "events": [{"type": "module.installed", "module": "heartbeat", "payload": {"ok": True}}],
        },
        headers=headers,
    )
    assert result.status_code == 200
    assert result.json() == {"accepted": True, "count": 1}
    assert fake.rows["installs"][0]["repo_fingerprint"] == "hash"
    assert fake.rows["module_events"][0]["event_type"] == "module.installed"
    assert fake.rows["module_events"][0]["ts"] == "db-default-now"


def test_pro_tier_requires_explicit_opt_in(cloud_app) -> None:
    _main, fake, client, headers = cloud_app
    fake.rows["users"].append({"clerk_user_id": "user_1", "email": "avi@example.com", "tier": "pro"})

    result = client.post(
        "/v1/telemetry",
        json={
            "install_id": "00000000-0000-0000-0000-000000000001",
            "telemetry_opt_in": False,
            "events": [{"type": "module.installed", "module": "heartbeat", "payload": {}}],
        },
        headers=headers,
    )
    assert result.status_code == 200
    assert result.json() == {"accepted": False, "reason": "telemetry opt-in required"}
    assert fake.rows["module_events"] == []


def test_posthog_forwarding_is_after_paid_opt_in(cloud_app, monkeypatch) -> None:
    main, fake, client, headers = cloud_app
    captures: list[dict] = []
    monkeypatch.setattr(main, "_posthog_capture", lambda **kwargs: captures.append(kwargs))
    fake.rows["users"].append({"clerk_user_id": "user_1", "email": "avi@example.com", "tier": "pro"})

    result = client.post(
        "/v1/telemetry",
        json={
            "install_id": "00000000-0000-0000-0000-000000000001",
            "telemetry_opt_in": True,
            "events": [{"type": "module.installed", "module": "heartbeat", "payload": {}}],
        },
        headers=headers,
    )

    assert result.status_code == 200
    assert captures[0]["distinct_id"] == "user_1"
    assert captures[0]["event"] == "sz.module.installed"
