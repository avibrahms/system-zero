from pathlib import Path

import pytest

from sz.core import heartbeat_detect


@pytest.mark.parametrize(
    ("marker", "expected"),
    [
        (".claude", "claude_code"),
        (".cursorrules", "cursor"),
        (".opencode", "opencode"),
        (".aider.conf.yml", "aider"),
        (".hermes/config.yaml", "hermes"),
        (".openclaw", "openclaw"),
        (".metaclaw", "metaclaw"),
        ("core/system/maintenance-registry.yaml", "connection_engine"),
    ],
)
def test_detects_known_heartbeat_markers(tmp_path: Path, marker: str, expected: str) -> None:
    marker_path = tmp_path / marker
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    if marker_path.suffix:
        marker_path.write_text("marker\n", encoding="utf-8")
    else:
        marker_path.mkdir()

    result = heartbeat_detect.detect(tmp_path)

    assert result["existing_heartbeat"] == expected
    assert expected in result["candidate_hosts"]


def test_adopt_heartbeat_wins_over_editor_marker(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".hermes").mkdir()
    (tmp_path / ".hermes/config.yaml").write_text("hooks:\n  on_tick: []\n", encoding="utf-8")

    result = heartbeat_detect.detect(tmp_path)

    assert result["existing_heartbeat"] == "hermes"
    assert result["candidate_hosts"][0] == "hermes"
