"""Talks to sz-cloud via Clerk JWT stored at ~/.sz/token."""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Any

import yaml

from sz.core import paths, repo_config, util


DEFAULT_ENDPOINT = "https://api.systemzero.dev"


def _clean_endpoint(value: str | None) -> str | None:
    if not value:
        return None
    return value.rstrip("/")


def _release_endpoint() -> str | None:
    roots = [util.repo_base(), util.repo_base().parent]
    for root in roots:
        release_path = root / ".s0-release.json"
        if not release_path.exists():
            continue
        try:
            state = json.loads(release_path.read_text())
        except Exception:
            continue
        endpoint = _clean_endpoint((state.get("endpoints") or {}).get("api"))
        if endpoint:
            return endpoint
    return None


def _endpoint() -> str:
    cfg_p = paths.user_config_dir() / "config.yaml"
    if cfg_p.exists():
        cfg = yaml.safe_load(cfg_p.read_text()) or {}
        endpoint = _clean_endpoint(cfg.get("cloud_endpoint"))
        if endpoint:
            return endpoint
    env_endpoint = _clean_endpoint(os.environ.get("SZ_CLOUD"))
    if env_endpoint:
        return env_endpoint
    try:
        root = paths.repo_root()
    except FileNotFoundError:
        root = None
    if root is not None:
        config_path = paths.repo_config_path(root)
        if config_path.exists():
            cloud = repo_config.read(root).get("cloud", {})
            endpoint = _clean_endpoint(cloud.get("endpoint"))
            if endpoint and endpoint != DEFAULT_ENDPOINT:
                return endpoint
    release_endpoint = _release_endpoint()
    if release_endpoint:
        return release_endpoint
    return DEFAULT_ENDPOINT


def _token() -> str | None:
    p = paths.user_config_dir() / "token"
    return p.read_text().strip() if p.exists() else None


def _req(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    url = _endpoint() + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"content-type": "application/json"}
    tok = _token()
    if tok:
        headers["authorization"] = f"Bearer {tok}"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def me() -> dict[str, Any] | None:
    try:
        return _req("GET", "/v1/me")
    except Exception:
        return None


def checkout(tier: str, success_url: str, cancel_url: str) -> dict[str, Any]:
    return _req(
        "POST",
        "/v1/billing/checkout",
        {"tier": tier, "success_url": success_url, "cancel_url": cancel_url},
    )


def hosted_absorb(source: str, feature: str, module_id: str | None = None) -> dict[str, Any]:
    return _req("POST", "/v1/absorb", {"source": source, "feature": feature, "id": module_id})


def public_insights() -> dict[str, Any]:
    return _req("GET", "/v1/insights/public")


def team_insights() -> dict[str, Any]:
    return _req("GET", "/v1/insights/team")


def telemetry(
    install_id: str,
    events: list[dict[str, Any]],
    *,
    repo_fingerprint: str,
    host: str,
    host_mode: str,
    sz_version: str,
    telemetry_opt_in: bool,
) -> dict[str, Any]:
    return _req(
        "POST",
        "/v1/telemetry",
        {
            "install_id": install_id,
            "events": events,
            "repo_fingerprint": repo_fingerprint,
            "host": host,
            "host_mode": host_mode,
            "sz_version": sz_version,
            "telemetry_opt_in": telemetry_opt_in,
        },
    )
