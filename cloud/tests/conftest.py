from __future__ import annotations

import importlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient


@dataclass
class Result:
    data: Any = None
    count: int | None = None


class FakeTable:
    def __init__(self, db: "FakeSupabase", name: str) -> None:
        self.db = db
        self.name = name
        self.action = "select"
        self.payload: dict[str, Any] | None = None
        self.filters: list[tuple[str, str, Any]] = []
        self._limit: int | None = None
        self._single = False
        self._count: str | None = None

    def select(self, columns: str, count: str | None = None) -> "FakeTable":
        self.action = "select"
        self._count = count
        return self

    def insert(self, payload: dict[str, Any]) -> "FakeTable":
        self.action = "insert"
        self.payload = dict(payload)
        return self

    def upsert(self, payload: dict[str, Any], on_conflict: str | None = None) -> "FakeTable":
        self.action = "upsert"
        self.payload = dict(payload)
        self.on_conflict = on_conflict
        return self

    def update(self, payload: dict[str, Any]) -> "FakeTable":
        self.action = "update"
        self.payload = dict(payload)
        return self

    def eq(self, column: str, value: Any) -> "FakeTable":
        self.filters.append(("eq", column, value))
        return self

    def in_(self, column: str, values: list[Any]) -> "FakeTable":
        self.filters.append(("in", column, values))
        return self

    def limit(self, count: int) -> "FakeTable":
        self._limit = count
        return self

    def maybe_single(self) -> "FakeTable":
        self._single = True
        return self

    def single(self) -> "FakeTable":
        self._single = True
        return self

    def _rows(self) -> list[dict[str, Any]]:
        rows = [dict(row) for row in self.db.rows.setdefault(self.name, [])]
        for op, column, value in self.filters:
            if op == "eq":
                rows = [row for row in rows if row.get(column) == value]
            elif op == "in":
                rows = [row for row in rows if row.get(column) in value]
        if self._limit is not None:
            rows = rows[: self._limit]
        return rows

    def execute(self) -> Result:
        table = self.db.rows.setdefault(self.name, [])
        if self.action == "insert":
            assert self.payload is not None
            row = dict(self.payload)
            row.setdefault("id", f"{self.name}_{len(table) + 1}")
            table.append(row)
            return Result(row)
        if self.action == "upsert":
            assert self.payload is not None
            key = getattr(self, "on_conflict", None)
            if key is None:
                key = "clerk_user_id" if self.name == "users" else "id"
            for row in table:
                if row.get(key) == self.payload.get(key):
                    row.update(self.payload)
                    return Result(row)
            table.append(dict(self.payload))
            return Result(self.payload)
        if self.action == "update":
            assert self.payload is not None
            matched = self._rows()
            for row in table:
                if any(row is item for item in matched):
                    row.update(self.payload)
            # Object identity is lost because _rows copies; update by filters instead.
            for row in table:
                if all(
                    (row.get(column) == value if op == "eq" else row.get(column) in value)
                    for op, column, value in self.filters
                ):
                    row.update(self.payload)
            return Result(self._rows())
        rows = self._rows()
        if self._single:
            return Result(rows[0] if rows else None)
        return Result(rows, len(rows) if self._count == "exact" else None)


class FakeSupabase:
    def __init__(self) -> None:
        self.rows: dict[str, list[dict[str, Any]]] = {
            "users": [],
            "teams": [],
            "installs": [],
            "module_events": [],
            "absorb_records": [],
            "subscriptions": [],
            "usage_logs": [],
            "mv_trending_modules": [{"module_id": "heartbeat", "installs_30d": 3}],
            "mv_capability_bindings": [{"requirer": "immune", "provider": "heartbeat", "capability": "clock", "c": 2}],
        }

    def table(self, name: str) -> FakeTable:
        return FakeTable(self, name)


@pytest.fixture
def cloud_app(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro")
    monkeypatch.setenv("STRIPE_PRICE_TEAM", "price_team")
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_clerk")
    monkeypatch.setenv("CLERK_JWKS_URL", "https://clerk.example.test/.well-known/jwks.json")
    monkeypatch.setenv("EMAIL_PROVIDER", "outbox")
    monkeypatch.setenv("EMAIL_OUTBOX_DIR", str(tmp_path / "outbox"))

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk["kid"] = "test-key"

    sys.modules.pop("cloud.app.main", None)
    main = importlib.import_module("cloud.app.main")
    fake = FakeSupabase()
    main.supa = fake
    main._clerk_jwks.cache_clear()
    monkeypatch.setattr(main, "_clerk_jwks", lambda: {"keys": [public_jwk]})
    main._cache["catalog"] = {"items": [{"id": "heartbeat", "description": "Pulse"}]}
    main._cache["ts"] = 9999999999

    token = jwt.encode(
        {"sub": "user_1", "email": "avi@example.com"},
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )
    client = TestClient(main.app)
    return main, fake, client, {"authorization": f"Bearer {token}"}
