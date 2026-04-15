"""Deterministic repo inventory for Genesis. No LLM."""
from __future__ import annotations

from pathlib import Path

EXCLUDE_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__", ".sz", ".next", ".cache"}
LANGUAGE_MARKERS = {
    "python":     ["pyproject.toml", "setup.py", "requirements.txt", "Pipfile"],
    "javascript": ["package.json"],
    "typescript": ["tsconfig.json"],
    "go":         ["go.mod"],
    "rust":       ["Cargo.toml"],
    "ruby":       ["Gemfile"],
    "java":       ["pom.xml", "build.gradle", "build.gradle.kts"],
    "php":        ["composer.json"],
    "shell":      ["Makefile"],
}
README_FILES = ["README.md", "README.rst", "README.txt", "README"]
META_FILES = ["pyproject.toml", "package.json", "go.mod", "Cargo.toml", "Gemfile", "composer.json", "Makefile"]
MAX_README_BYTES = 5000


def _walk(root: Path) -> list[Path]:
    out = []
    for p in root.rglob("*"):
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        out.append(p)
    return out


def inventory(root: Path) -> dict:
    paths = _walk(root)
    files = [p for p in paths if p.is_file()]
    file_count = len(files)
    extensions: dict[str, int] = {}
    for f in files:
        extensions[f.suffix] = extensions.get(f.suffix, 0) + 1
    detected_languages = []
    for lang, markers in LANGUAGE_MARKERS.items():
        if any((root / m).exists() for m in markers):
            detected_languages.append(lang)
    readme_text = ""
    for r in README_FILES:
        rp = root / r
        if rp.exists() and rp.is_file():
            readme_text = rp.read_text(errors="replace")[:MAX_README_BYTES]
            break
    meta_blobs = {}
    for m in META_FILES:
        mp = root / m
        if mp.exists() and mp.is_file() and mp.stat().st_size <= 10_000:
            meta_blobs[m] = mp.read_text(errors="replace")
    return {
        "file_count": file_count,
        "extension_histogram": extensions,
        "detected_languages": detected_languages,
        "readme_text": readme_text,
        "meta_blobs": meta_blobs,
        "top_dirs": sorted([p.name for p in root.iterdir() if p.is_dir() and p.name not in EXCLUDE_DIRS])[:30],
    }
