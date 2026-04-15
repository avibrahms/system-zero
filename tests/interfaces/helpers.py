from __future__ import annotations

from pathlib import Path

from sz.core import util


def make_runtime_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    sz_dir = root / ".sz"
    (sz_dir / "memory" / "streams").mkdir(parents=True)
    (sz_dir / "memory" / "cursors").mkdir(parents=True)
    (sz_dir / "shared").mkdir(parents=True)
    (sz_dir / "bus.jsonl").touch()
    util.atomic_write_json(
        sz_dir / "registry.json",
        {"generated_at": util.utc_now(), "modules": {}, "bindings": [], "unsatisfied": []},
    )
    return root
