from __future__ import annotations

from sz.interfaces import memory

from tests.interfaces.helpers import make_runtime_root


def test_memory_kv_and_streams(tmp_path) -> None:
    root = make_runtime_root(tmp_path)

    assert memory.get(root, "missing") is None
    memory.set(root, "answer", 42)
    assert memory.get(root, "answer") == 42

    memory.append(root, "events", {"n": 1})
    memory.append(root, "events", {"n": 2})
    items, cursor = memory.tail(root, "events", from_cursor=1)
    assert items == [{"n": 2}]
    assert cursor == 2
    assert memory.search(root, "anything") == []
