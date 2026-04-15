"""Catalog commands and fetch helpers."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
from typing import Any
from urllib.parse import unquote, urlparse
from urllib.request import urlopen

import click


DEFAULT_INDEX_URL = "https://raw.githubusercontent.com/avibrahms/catalog/main/index.json"


class CatalogError(Exception):
    """Raised when the catalog cannot satisfy a request."""


def _index_url(index_url: str | None = None) -> str:
    return index_url or os.environ.get("SZ_CATALOG") or DEFAULT_INDEX_URL


def load_index(index_url: str | None = None) -> dict[str, Any]:
    """Load a catalog index from SZ_CATALOG, a file URL, a local path, or HTTP."""
    url = _index_url(index_url)
    parsed = urlparse(url)
    try:
        if parsed.scheme == "file":
            return json.loads(Path(unquote(parsed.path)).read_text())
        if parsed.scheme in {"http", "https"}:
            with urlopen(url, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        return json.loads(Path(url).expanduser().read_text())
    except Exception as exc:  # pragma: no cover - click reports the exact error
        raise CatalogError(f"Could not load catalog index from {url}: {exc}") from exc


def find_module(module_id: str, index_url: str | None = None) -> dict[str, Any]:
    index = load_index(index_url)
    for item in index.get("items", []):
        if item.get("id") == module_id:
            return item
    raise CatalogError(f"Module {module_id!r} was not found in the catalog.")


def _local_index_path(index_url: str | None = None) -> Path | None:
    url = _index_url(index_url)
    parsed = urlparse(url)
    if parsed.scheme == "file":
        return Path(unquote(parsed.path))
    if parsed.scheme in {"http", "https"}:
        return None
    return Path(url).expanduser()


def _local_same_repo_source(source: dict[str, Any], index_url: str | None = None) -> Path | None:
    """Resolve same-repo git catalog entries without touching the network.

    Phase 15 publishes catalog entries as git sources, but local/offline test
    runs often point SZ_CATALOG at this checkout's catalog/index.json. In that
    case the source path can be copied directly from the checkout.
    """
    source_path = source.get("path")
    if not source_path:
        return None
    index_path = _local_index_path(index_url)
    if not index_path or not index_path.is_file():
        return None
    for base in (index_path.parent.parent, index_path.parent):
        candidate = (base / str(source_path)).resolve()
        if candidate.is_dir() and (candidate / "module.yaml").is_file():
            return candidate
    return None


def _copy_module_dir(source_dir: Path, out: Path) -> None:
    if not source_dir.is_dir():
        raise CatalogError(f"Catalog source directory does not exist: {source_dir}")
    if not (source_dir / "module.yaml").is_file():
        raise CatalogError(f"Catalog source directory has no module.yaml: {source_dir}")
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, out, dirs_exist_ok=True)


def _fetch_git(source: dict[str, Any], out: Path) -> None:
    url = source.get("url")
    if not url:
        raise CatalogError("Git catalog source is missing url.")
    with tempfile.TemporaryDirectory(prefix="sz-catalog-git-") as tmp:
        clone_dir = Path(tmp) / "repo"
        args = ["git", "clone", "--depth", "1"]
        if source.get("ref"):
            args.extend(["--branch", str(source["ref"])])
        args.extend([str(url), str(clone_dir)])
        result = subprocess.run(args, check=False, text=True, capture_output=True)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise CatalogError(f"Git catalog fetch failed: {detail}")
        _copy_module_dir(clone_dir / str(source.get("path", ".")), out)


def _fetch_tarball(source: dict[str, Any], out: Path) -> None:
    url = source.get("url")
    if not url:
        raise CatalogError("Tarball catalog source is missing url.")
    with tempfile.TemporaryDirectory(prefix="sz-catalog-tar-") as tmp:
        archive = Path(tmp) / "source.tar.gz"
        with urlopen(str(url), timeout=60) as response:
            archive.write_bytes(response.read())
        extract_dir = Path(tmp) / "extract"
        extract_dir.mkdir()
        with tarfile.open(archive) as tf:
            tf.extractall(extract_dir)
        base = extract_dir / str(source.get("path", "."))
        if not (base / "module.yaml").is_file():
            candidates = [p.parent for p in extract_dir.rglob("module.yaml")]
            if len(candidates) == 1:
                base = candidates[0]
        _copy_module_dir(base, out)


def fetch_module(module_id: str, out: Path, index_url: str | None = None) -> Path:
    """Fetch a catalog module into out and return out."""
    item = find_module(module_id, index_url)
    source = item.get("source") or {}
    source_type = source.get("type")
    if source_type == "local":
        _copy_module_dir(Path(str(source.get("path", ""))).expanduser(), out)
    elif source_type == "git":
        local_source = _local_same_repo_source(source, index_url)
        if local_source is not None:
            _copy_module_dir(local_source, out)
        else:
            _fetch_git(source, out)
    elif source_type == "tarball":
        _fetch_tarball(source, out)
    else:
        raise CatalogError(f"Unsupported catalog source type for {module_id}: {source_type!r}")
    return out


@click.group(help="Interact with the module catalog.")
def cmd() -> None:
    """Catalog command group."""


@cmd.command("list", help="List modules in the catalog.")
def list_cmd() -> None:
    try:
        index = load_index()
    except CatalogError as exc:
        raise click.ClickException(str(exc)) from exc
    for item in index.get("items", []):
        click.echo(f"{item['id']}\t{item.get('version', '')}\t{item.get('description', '')}")


@cmd.command(help="Show one catalog module as JSON.")
@click.argument("module_id")
def show(module_id: str) -> None:
    try:
        item = find_module(module_id)
    except CatalogError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(item, indent=2))


@cmd.command(help="Fetch one catalog module to a local directory.")
@click.argument("module_id")
@click.option("--out", type=click.Path(file_okay=False, path_type=Path), required=True)
def fetch(module_id: str, out: Path) -> None:
    try:
        fetch_module(module_id, out)
    except CatalogError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(str(out))
