from __future__ import annotations

from sz.interfaces import storage

from tests.interfaces.helpers import make_runtime_root


def test_storage_paths_are_created(tmp_path) -> None:
    root = make_runtime_root(tmp_path)

    private_path = storage.private(root, "hello-module")
    shared_path = storage.shared(root, "signals")

    assert private_path == root / ".sz" / "hello-module"
    assert shared_path == root / ".sz" / "shared" / "signals"
    assert private_path.is_dir()
    assert shared_path.is_dir()
