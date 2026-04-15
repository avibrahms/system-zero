"""Storage path helpers for module-private and shared namespaces."""
from __future__ import annotations

from pathlib import Path

from sz.core import paths, util


def private(root: Path, module_id: str) -> Path:
    return util.ensure_directory(paths.module_dir(root, module_id))


def shared(root: Path, namespace: str) -> Path:
    return util.ensure_directory(paths.shared_dir(root) / namespace)
