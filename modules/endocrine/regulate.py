#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess


GREEN_STREAK_TARGET = 3


def main() -> int:
    events = bus_subscribe("endocrine-entry", "health.snapshot")
    if not events:
        return 0
    latest = events[-1].get("payload", {})
    color = str(latest.get("color", "GREEN")).upper()
    streak = int(memory_get("endocrine.green_streak") or 0)
    target = None
    if color == "RED":
        streak = 0
        target = "low"
    elif color == "AMBER":
        streak = 0
        target = "medium"
    elif color == "GREEN":
        streak += 1
        if streak >= GREEN_STREAK_TARGET:
            target = "high"
    memory_set("endocrine.green_streak", streak)
    if target:
        setpoint_set("immune", "severity_threshold", target)
        bus_emit(
            "setpoint.adjusted",
            {
                "module_id": "immune",
                "setpoint": "severity_threshold",
                "value": target,
                "reason": f"health.{color.lower()}",
            },
        )
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


def setpoint_set(module_id: str, key: str, value: str) -> None:
    subprocess.run(["sz", "setpoint", "set", module_id, key, value], check=True, text=True, capture_output=True)


def bus_emit(event_type: str, payload: dict[str, object]) -> None:
    subprocess.run(
        ["sz", "bus", "emit", event_type, json.dumps(payload, separators=(",", ":")), "--module", "endocrine"],
        check=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
