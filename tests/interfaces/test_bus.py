from __future__ import annotations

from sz.core import paths
from sz.interfaces import bus

from tests.interfaces.helpers import make_runtime_root


def test_bus_emit_tail_and_subscribe(tmp_path) -> None:
    root = make_runtime_root(tmp_path)
    bus_path = paths.bus_path(root)

    bus.emit(bus_path, "alpha", "alpha.started", {"step": 1})
    bus.emit(bus_path, "beta", "beta.done", {"step": 2})
    bus.emit(bus_path, "alpha", "alpha.finished", {"step": 3})

    tail = bus.tail(bus_path, last=2)
    assert [event["type"] for event in tail] == ["beta.done", "alpha.finished"]

    subscribed = bus.subscribe(root, "watcher", "alpha.*")
    assert [event["type"] for event in subscribed] == ["alpha.started", "alpha.finished"]
    assert bus.subscribe(root, "watcher", "alpha.*") == []
    assert bus.read_cursor(root, "watcher") == 3
