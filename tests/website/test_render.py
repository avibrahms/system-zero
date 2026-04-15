import json
import os
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")


def _website_url() -> str:
    if os.environ.get("WEBSITE_URL"):
        return os.environ["WEBSITE_URL"].rstrip("/")
    release = Path(__file__).resolve().parents[2] / ".s0-release.json"
    if release.exists():
        data = json.loads(release.read_text())
        endpoint = data.get("endpoints", {}).get("web")
        if endpoint:
            return endpoint.rstrip("/")
    return "https://systemzero.dev"


def test_organism_renders():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        page.goto(_website_url())
        # canvas exists and has non-zero size
        canvas = page.query_selector("#organism")
        assert canvas is not None
        bbox = canvas.bounding_box()
        assert bbox["width"] > 100 and bbox["height"] > 100
        # at least one module card renders (after catalog fetch or fallback)
        page.wait_for_selector(".card", timeout=10000)
        cards = page.query_selector_all(".card")
        assert len(cards) >= 5
        b.close()
