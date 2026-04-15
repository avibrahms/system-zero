#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from os import environ


def main() -> int:
    anomalies = bus_subscribe("subconscious-entry", "anomaly.*")
    count = memory_get("subconscious.anomaly_count") or 0
    count = int(count) + len(anomalies)
    red_threshold = int(environ.get("SZ_SETPOINT_red_threshold", "5"))
    amber_threshold = int(environ.get("SZ_SETPOINT_amber_threshold", "2"))
    color = "GREEN"
    if count >= red_threshold:
        color = "RED"
    elif count >= amber_threshold:
        color = "AMBER"
    snapshot = {
        "color": color,
        "anomaly_count": count,
        "new_anomalies": len(anomalies),
    }
    memory_set("subconscious.anomaly_count", count)
    memory_set("subconscious.snapshot", snapshot)
    bus_emit("health.snapshot", snapshot)
    return 0


def run_json(args: list[str]):
    result = subprocess.run(args, check=True, text=True, capture_output=True)
    return json.loads(result.stdout or "null")


def bus_subscribe(module_id: str, pattern: str) -> list[dict[str, object]]:
    value = run_json(["sz", "bus", "subscribe", module_id, pattern])
    return value if isinstance(value, list) else []


def memory_get(key: str):
    return run_json(["sz", "memory", "get", key])


def memory_set(key: str, value) -> None:
    subprocess.run(["sz", "memory", "set", key, json.dumps(value, separators=(",", ":"))], check=True)


def bus_emit(event_type: str, payload: dict[str, object]) -> None:
    subprocess.run(
        ["sz", "bus", "emit", event_type, json.dumps(payload, separators=(",", ":")), "--module", "subconscious"],
        check=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
