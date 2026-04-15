from __future__ import annotations

from pathlib import Path

from sz.interfaces import discovery

from tests.interfaces.helpers import make_runtime_root


def test_discovery_reads_registry_and_profile(tmp_path) -> None:
    root = make_runtime_root(tmp_path)
    fixture_dir = Path(__file__).resolve().parents[1] / "spec" / "fixtures"
    (root / ".sz" / "registry.json").write_text((fixture_dir / "registry.json").read_text(encoding="utf-8"), encoding="utf-8")
    (root / ".sz" / "repo-profile.json").write_text((fixture_dir / "repo-profile.json").read_text(encoding="utf-8"), encoding="utf-8")

    modules = discovery.list_modules(root)
    assert [item["module_id"] for item in modules] == ["immune-router", "pulse-core"]
    assert discovery.providers(root, "memory.read")[0]["provider"] == "pulse-core"
    assert discovery.requirers(root, "memory.read")[0]["requirer"] == "immune-router"
    assert discovery.resolve(root, "memory.read")["provider"] == "pulse-core"
    assert discovery.health(root, "immune-router")["status"] == "degraded"
    assert discovery.profile(root)["language"] == "python"
