"""Absorption orchestration with CLC discipline."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import hashlib, shutil, subprocess
import yaml
from sz.core import paths, manifest as manifest_core
from sz.interfaces import llm

CACHE = paths.user_config_dir() / "cache" / "absorb"


def _src_hash(source: str, ref: str | None) -> str:
    h = hashlib.sha1()
    h.update(source.encode())
    h.update((ref or "HEAD").encode())
    return h.hexdigest()[:12]


def acquire(source: str, ref: str | None) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / _src_hash(source, ref)
    if dest.exists():
        return dest
    if source.startswith("git+") or source.endswith(".git") or source.startswith("https://github.com"):
        url = source[4:] if source.startswith("git+") else source
        subprocess.run(["git", "clone", "--depth", "1", url, str(dest)], check=True)
        if ref:
            subprocess.run(["git", "-C", str(dest), "checkout", ref], check=True)
    elif source.startswith("file://"):
        shutil.copytree(Path(source[len("file://"):]), dest)
    else:
        shutil.copytree(Path(source), dest)
    return dest


def inventory(src: Path, max_total_kb: int = 50) -> dict:
    layout = []
    files = []
    file_paths = []
    seen = 0
    for p in sorted(src.rglob("*")):
        if ".git" in p.parts or ".staging" in p.parts:
            continue
        if p.is_dir():
            layout.append(str(p.relative_to(src)) + "/")
            continue
        rel = str(p.relative_to(src))
        layout.append(rel)
        file_paths.append(rel)
        if p.suffix in {".md", ".py", ".js", ".ts", ".sh", ".yaml", ".yml", ".toml", ".json"} and p.stat().st_size <= 5_000:
            content = p.read_text(errors="replace")
            files.append(f"\n--- {rel} ---\n{content}\n")
            seen += len(content)
            if seen > max_total_kb * 1024:
                break
    return {"layout": "\n".join(layout[:400]), "files": "".join(files), "paths": file_paths}


def render_prompt(template_path: Path, source: str, ref: str | None, feature: str, inv: dict) -> str:
    return (template_path.read_text()
            .replace("{{SOURCE_URL}}", source)
            .replace("{{SOURCE_REF}}", ref or "HEAD")
            .replace("{{FEATURE_NAME}}", feature)
            .replace("{{LAYOUT}}", inv["layout"])
            .replace("{{FILES}}", inv["files"]))


def _inventory_file_paths(inv: dict[str, Any]) -> set[str]:
    if isinstance(inv.get("paths"), list):
        candidates = inv["paths"]
    else:
        candidates = [
            line.strip()
            for line in str(inv.get("layout", "")).splitlines()
            if line.strip() and not line.strip().endswith("/")
        ]
    paths_from_inventory = set()
    for item in candidates:
        path = Path(str(item))
        if path.is_absolute() or "." in path.parts or ".." in path.parts:
            continue
        paths_from_inventory.add(path.as_posix())
    return paths_from_inventory


def materialize(src: Path, draft: dict, target: Path, *, inventory_paths: set[str] | None = None) -> None:
    target.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": draft["module_id"], "version": "0.1.0",
        "category": draft.get("category", "absorbed"),
        "description": draft.get("description", "Absorbed feature."),
        "entry": draft["entry"],
        "triggers": draft.get("triggers", [{"on": "tick"}]),
        "provides": draft.get("provides", []),
        "requires": draft.get("requires", []),
        "setpoints": draft.get("setpoints", {}),
        "hooks": {"reconcile": "reconcile.sh"},
    }
    (target / "module.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    src_resolved = src.resolve()
    target_resolved = target.resolve()
    for spec in draft.get("files_to_copy", []):
        from_p = (src / spec["from"]).resolve()
        try:
            inventory_rel = from_p.relative_to(src_resolved).as_posix()
        except ValueError:
            raise ValueError(f"Refusing to copy outside source: {spec['from']}")
        if inventory_paths is not None and inventory_rel not in inventory_paths:
            raise ValueError(f"Refusing to copy path not present in inventory: {spec['from']}")
        to_p = (target / spec["to"]).resolve()
        try:
            to_p.relative_to(target_resolved)
        except ValueError:
            raise ValueError(f"Refusing to copy outside module: {spec['to']}")
        to_p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(from_p, to_p)
    entry = target / draft["entry"]["command"]
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(draft["entry_script"])
    entry.chmod(0o755)
    rec = target / "reconcile.sh"
    rec.write_text(draft["reconcile_script"])
    rec.chmod(0o755)


def absorb(source: str, feature: str, *, ref: str | None = None,
           module_id: str | None = None, dry_run: bool = False) -> dict:
    src = acquire(source, ref)
    inv = inventory(src)
    template = Path(__file__).resolve().parent.parent / "templates" / "absorb_prompt.md"
    schema_path = Path(__file__).resolve().parents[2] / "spec" / "v0.1.0" / "llm-responses" / "absorb-draft.schema.json"
    prompt = render_prompt(template, source, ref, feature, inv)

    # CLC discipline: validated + retried + logged.
    result = llm.invoke(prompt, schema_path=schema_path, template_id="absorb-draft", max_tokens=4000)
    draft = result.parsed

    if module_id:
        draft["module_id"] = module_id

    # Second-line validation against the full manifest schema.
    fake_manifest = {
        "id": draft["module_id"], "version": "0.1.0",
        "category": draft.get("category", "absorbed"),
        "description": draft.get("description", "absorbed"),
        "entry": draft["entry"],
        "triggers": draft.get("triggers", [{"on": "tick"}]),
        "provides": draft.get("provides", []),
        "requires": draft.get("requires", []),
        "setpoints": draft.get("setpoints", {}),
        "hooks": {"reconcile": "reconcile.sh"},
    }
    errs = manifest_core.validate_manifest(fake_manifest)
    if errs:
        raise ValueError(f"absorb produced invalid manifest: {errs}")

    staging = src / ".staging" / draft["module_id"]
    if staging.exists():
        shutil.rmtree(staging)
    materialize(src, draft, staging, inventory_paths=_inventory_file_paths(inv))

    if dry_run:
        return {"staging": str(staging), "draft": draft}

    subprocess.run(
        ["sz", "install", draft["module_id"], "--source", str(staging)],
        check=True,
        capture_output=True,
        text=True,
    )
    return {"installed": draft["module_id"], "staging": str(staging)}
