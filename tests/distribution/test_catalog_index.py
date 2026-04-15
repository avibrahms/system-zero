import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]


def test_catalog_has_seven():
    idx = json.loads((HERE / "catalog" / "index.json").read_text())
    assert idx["version"] == "0.1.0"
    ids = {it["id"] for it in idx["items"]}
    assert ids >= {"heartbeat", "immune", "subconscious", "dreaming", "metabolism", "endocrine", "prediction"}
