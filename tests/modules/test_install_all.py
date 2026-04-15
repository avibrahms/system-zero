from __future__ import annotations

from tests.modules._helpers import MODULE_IDS, init_repo, install_many, registry


def test_install_all_registers_modules_and_bindings(tmp_path, monkeypatch) -> None:
    repo_root, runner = init_repo(tmp_path, monkeypatch)

    install_many(runner, MODULE_IDS)

    current = registry(repo_root)
    assert sorted(current["modules"]) == sorted(MODULE_IDS)
    assert {
        "requirer": "subconscious",
        "capability": "anomaly.detection",
        "provider": "immune",
        "address": "events:anomaly.detected",
    } in current["bindings"]
    assert {
        "requirer": "endocrine",
        "capability": "health.snapshot",
        "provider": "subconscious",
        "address": "memory:subconscious.snapshot",
    } in current["bindings"]
