#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from collections import Counter, defaultdict


def main() -> int:
    window = int(os.environ.get("SZ_SETPOINT_history_window", "200"))
    top_k = int(os.environ.get("SZ_SETPOINT_top_k", "3"))
    events = bus_tail(window)
    event_types = [str(event.get("type", "")) for event in events if event.get("type")]
    predictions = predict_next(event_types, top_k)
    bus_emit("prediction.next", {"predictions": predictions, "history_size": len(event_types)})
    return 0


def bus_tail(last: int) -> list[dict[str, object]]:
    result = subprocess.run(["sz", "bus", "tail", "--last", str(last)], check=True, text=True, capture_output=True)
    value = json.loads(result.stdout or "[]")
    return value if isinstance(value, list) else []


def predict_next(event_types: list[str], top_k: int) -> list[dict[str, object]]:
    if not event_types:
        return []
    transitions: dict[str, Counter[str]] = defaultdict(Counter)
    for left, right in zip(event_types, event_types[1:]):
        transitions[left][right] += 1
    current = event_types[-1]
    counts = transitions.get(current) or Counter(event_types)
    total = sum(counts.values()) or 1
    return [
        {"type": event_type, "score": count / total, "count": count}
        for event_type, count in counts.most_common(top_k)
    ]


def bus_emit(event_type: str, payload: dict[str, object]) -> None:
    subprocess.run(
        ["sz", "bus", "emit", event_type, json.dumps(payload, separators=(",", ":")), "--module", "prediction"],
        check=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
