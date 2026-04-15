from pathlib import Path

from sz.core import inventory


def test_inventory_detects_languages_and_excludes_runtime_dirs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# demo\nA tiny Python project.\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname = \"demo\"\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src/app.py").write_text("print('ok')\n", encoding="utf-8")
    (repo / ".git").mkdir()
    (repo / ".git/ignored.py").write_text("ignored\n", encoding="utf-8")
    (repo / ".sz").mkdir()
    (repo / ".sz/bus.jsonl").write_text("{}\n", encoding="utf-8")

    result = inventory.inventory(repo)

    assert result["detected_languages"] == ["python"]
    assert result["extension_histogram"][".py"] == 1
    assert result["file_count"] == 3
    assert result["readme_text"].startswith("# demo")
    assert "pyproject.toml" in result["meta_blobs"]
    assert result["top_dirs"] == ["src"]
