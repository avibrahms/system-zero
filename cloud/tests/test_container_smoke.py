from __future__ import annotations

import importlib
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_hosted_absorb_runtime_dependencies_are_importable() -> None:
    importlib.import_module("jsonschema")
    absorb = importlib.import_module("sz.core.absorb")

    assert hasattr(absorb, "absorb")
    assert shutil.which("git") is not None


def test_cloud_dockerfiles_include_absorb_runtime_contract() -> None:
    dockerfile = (ROOT / "cloud" / "Dockerfile").read_text()
    prelaunch = (ROOT / "cloud" / "Dockerfile.prelaunch").read_text()

    assert "apt-get install -y --no-install-recommends ca-certificates git" in dockerfile
    assert "apt-get install -y --no-install-recommends ca-certificates git" in prelaunch
    assert "--no-deps" not in prelaunch
    assert "pip install --no-cache-dir -e /app" in prelaunch
