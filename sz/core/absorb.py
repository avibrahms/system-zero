"""Absorption orchestration with CLC discipline.

The LLM proposes what matters in the source repository. The runtime then
normalizes that proposal into a safe, protocol-native S0 module. This keeps
absorb from degenerating into "run some foreign repo on tick".
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
import hashlib, json, re, shutil, subprocess
import yaml
from sz.core import paths, manifest as manifest_core, util
from sz.interfaces import llm

CACHE = paths.user_config_dir() / "cache" / "absorb"
TEXT_SUFFIXES = {".md", ".py", ".js", ".ts", ".sh", ".yaml", ".yml", ".toml", ".json"}
DEFAULT_REQUIRED_PROVIDERS = ["bus", "memory", "discovery"]
SOURCE_TREE_SKIP_DIRS = {
    ".git",
    ".staging",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".turbo",
}
SOURCE_TREE_MAX_BYTES = 20_000_000
SOURCE_TREE_MAX_FILE_BYTES = 2_000_000


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
        source_path = Path(source[len("file://"):])
        if source_path.is_file():
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, dest / source_path.name)
        else:
            shutil.copytree(source_path, dest)
    else:
        source_path = Path(source)
        if source_path.is_file():
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, dest / source_path.name)
        else:
            shutil.copytree(source_path, dest)
    return dest


def inventory(src: Path, max_total_kb: int = 50) -> dict:
    layout = []
    files = []
    file_paths = []
    seen = 0
    budget = max_total_kb * 1024
    for p in sorted(src.rglob("*")):
        rel_parts = p.relative_to(src).parts
        if any(part in SOURCE_TREE_SKIP_DIRS for part in rel_parts):
            continue
        if p.is_dir():
            layout.append(str(p.relative_to(src)) + "/")
            continue
        rel = str(p.relative_to(src))
        layout.append(rel)
        file_paths.append(rel)
        if seen >= budget:
            continue
        if p.suffix in {".md", ".py", ".js", ".ts", ".sh", ".yaml", ".yml", ".toml", ".json"} and p.stat().st_size <= 5_000:
            content = p.read_text(errors="replace")
            remaining = max(0, budget - seen)
            if len(content) > remaining:
                content = content[:remaining] + "\n...[truncated]\n"
            files.append(f"\n--- {rel} ---\n{content}\n")
            seen += len(content)
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


def _resolve_beneath(base: Path, raw_path: str, error_prefix: str) -> Path:
    if Path(raw_path).is_absolute():
        raise ValueError(f"{error_prefix}: {raw_path}")
    base_resolved = base.resolve()
    candidate = (base_resolved / raw_path).resolve()
    try:
        candidate.relative_to(base_resolved)
    except ValueError:
        raise ValueError(f"{error_prefix}: {raw_path}")
    return candidate


def _slug(value: str, *, fallback: str = "absorbed-feature", limit: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    slug = (slug or fallback)[:limit].strip("-")
    return slug or fallback


def _capability_for(module_id: str) -> str:
    return "absorbed." + module_id.replace("-", ".")


def _short(value: Any, default: str, limit: int) -> str:
    text = str(value or default).strip()
    return (text[:limit].rstrip() or default)


def _valid_trigger(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and (
            value == {"on": "tick"}
            or (value.get("on") == "event" and isinstance(value.get("match"), str) and value["match"])
            or (isinstance(value.get("cron"), str) and value["cron"])
        )
    )


def _valid_setpoint(value: Any) -> bool:
    if not isinstance(value, dict) or "default" not in value:
        return False
    has_range = isinstance(value.get("range"), list) and len(value["range"]) == 2
    has_enum = isinstance(value.get("enum"), list) and bool(value["enum"])
    return has_range ^ has_enum


def _normalize_setpoints(raw: Any, action_names: list[str] | None = None) -> dict[str, Any]:
    setpoints: dict[str, Any] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            name = re.sub(r"[^a-z0-9_]+", "_", str(key).lower()).strip("_")
            if not name or not re.match(r"^[a-z][a-z0-9_]*$", name):
                continue
            if _valid_setpoint(value):
                cleaned = {"default": value["default"]}
                if "range" in value:
                    cleaned["range"] = value["range"]
                if "enum" in value:
                    cleaned["enum"] = value["enum"]
                if value.get("description"):
                    cleaned["description"] = _short(value["description"], "", 160)
                if value.get("mode") in {"simple", "advanced"}:
                    cleaned["mode"] = value["mode"]
                setpoints[name] = cleaned
    setpoints.setdefault(
        "execution_mode",
        {
            "default": "observe",
            "enum": ["observe", "execute"],
            "description": "Observe by default; execute only after an operator opts in.",
            "mode": "simple",
        },
    )
    setpoints.setdefault(
        "action_name",
        {
            "default": "auto",
            "enum": ["auto", *(action_names or [])],
            "description": "Behavior action to run when execution_mode=execute.",
            "mode": "simple",
        },
    )
    setpoints.setdefault(
        "max_items",
        {
            "default": 1,
            "range": [1, 100],
            "description": "Maximum pending inbox items processed per tick.",
            "mode": "advanced",
        },
    )
    setpoints.setdefault(
        "command_timeout_seconds",
        {
            "default": 0,
            "range": [0, 3600],
            "description": "Per-command timeout override; 0 uses the selected behavior action's own timeout.",
            "mode": "advanced",
        },
    )
    setpoints.setdefault(
        "max_output_chars",
        {
            "default": 4000,
            "range": [100, 50000],
            "description": "Maximum stdout/stderr characters retained in each result.",
            "mode": "advanced",
        },
    )
    return setpoints


def _normalize_requires(raw: Any) -> list[dict[str, Any]]:
    providers = set(DEFAULT_REQUIRED_PROVIDERS)
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and isinstance(item.get("providers"), list):
                providers.update(
                    provider
                    for provider in item["providers"]
                    if provider in {"llm", "vector", "memory", "bus", "storage", "schedule", "discovery"}
                )
    return [{"providers": sorted(providers)}]


def _normalize_triggers(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        triggers = [item for item in raw if _valid_trigger(item)]
        if triggers:
            return triggers
    return [{"on": "tick"}]


def _default_files(paths_from_inventory: set[str]) -> list[str]:
    preferred_names = [
        "README.md",
        "program.md",
        "pyproject.toml",
        "package.json",
        "train.py",
        "prepare.py",
        "harness.py",
        "harness.md",
        "meta_harness.py",
        "metaharness.py",
        "lobster.py",
    ]
    selected: list[str] = []
    for wanted in preferred_names:
        for path in sorted(paths_from_inventory):
            if path == wanted or path.endswith("/" + wanted):
                selected.append(path)
                break
    if not selected:
        selected = [
            path
            for path in sorted(paths_from_inventory)
            if Path(path).suffix.lower() in TEXT_SUFFIXES
        ][:6]
    return selected


def _normalize_files(draft: dict[str, Any], inventory_paths: set[str]) -> list[dict[str, str]]:
    selected: list[str] = []
    for spec in draft.get("files_to_copy", []):
        if not isinstance(spec, dict):
            continue
        raw = str(spec.get("from", "")).strip()
        if raw in inventory_paths and raw not in selected:
            selected.append(raw)
    for path in _default_files(inventory_paths):
        if path not in selected:
            selected.append(path)
    files: list[dict[str, str]] = []
    for path in selected[:12]:
        files.append({"from": path, "to": f"source/{path}"})
    return files


def _source_file_records(src: Path, files_to_copy: list[dict[str, str]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for spec in files_to_copy:
        source_path = src / spec["from"]
        data = source_path.read_bytes()
        records.append(
            {
                "from": spec["from"],
                "to": spec["to"],
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return records


def _safe_action_name(value: str, fallback: str = "run") -> str:
    name = re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")
    if not name or not re.match(r"^[a-z][a-z0-9_]*$", name):
        return fallback
    return name[:40].strip("_") or fallback


def _command_is_safe(command: list[str]) -> bool:
    if not command:
        return False
    joined = " ".join(command).lower()
    banned = [
        " rm ",
        "rm -",
        "sudo ",
        "curl ",
        "wget ",
        "git push",
        "git reset",
        "git clean",
        "docker ",
        "kubectl ",
        "gh repo",
        "> /dev/",
    ]
    return not any(item in f" {joined} " for item in banned)


def _add_action(
    actions: list[dict[str, Any]],
    seen: set[tuple[str, ...]],
    *,
    name: str,
    command: list[str],
    description: str,
    cwd: str = "source_repo",
    timeout_seconds: int = 60,
    output_globs: list[str] | None = None,
) -> None:
    if not _command_is_safe(command):
        return
    key = (cwd, *command)
    if key in seen:
        return
    seen.add(key)
    action_name = _safe_action_name(name)
    existing_names = {str(action.get("name")) for action in actions}
    if action_name in existing_names:
        base = action_name[:35].rstrip("_") or "run"
        suffix = 2
        while f"{base}_{suffix}" in existing_names:
            suffix += 1
        action_name = f"{base}_{suffix}"
    actions.append(
        {
            "name": action_name,
            "description": _short(description, "Absorbed source command.", 180),
            "command": [str(part) for part in command],
            "cwd": cwd,
            "timeout_seconds": int(max(1, min(timeout_seconds, 3600))),
            "output_globs": output_globs or ["*.log", "*.json", "*.tsv", "*.txt", "results/**"],
        }
    )


def _shell_words(command: str) -> list[str]:
    import shlex

    try:
        return shlex.split(command)
    except ValueError:
        return []


def _read_json_source(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _read_toml_source(path: Path) -> dict[str, Any]:
    try:
        import tomllib
    except Exception:
        return {}
    try:
        loaded = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _iter_named_source_files(src: Path, names: set[str], *, limit: int = 200) -> list[Path]:
    matches: list[Path] = []
    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        if any(part in SOURCE_TREE_SKIP_DIRS for part in rel.parts):
            continue
        if path.is_file() and path.name in names:
            matches.append(path)
    matches.sort(key=lambda path: (0 if path.parent == src else 1, len(path.relative_to(src).parts), path.as_posix()))
    return matches[:limit]


def _cwd_for_source_file(src: Path, path: Path) -> str:
    parent = path.parent.relative_to(src).as_posix()
    return "source_repo" if parent == "." else parent


def _script_command_prefix(package_path: Path, package: dict[str, Any]) -> list[str]:
    package_manager = str(package.get("packageManager") or "").lower()
    package_dir = package_path.parent
    if package_manager.startswith("pnpm") or (package_dir / "pnpm-lock.yaml").exists():
        return ["pnpm", "run"]
    if package_manager.startswith("yarn") or (package_dir / "yarn.lock").exists():
        return ["yarn", "run"]
    if package_manager.startswith("bun") or (package_dir / "bun.lockb").exists():
        return ["bun", "run"]
    return ["npm", "run"]


def _script_is_safe(script_name: str, script_value: Any) -> bool:
    text = f"{script_name} {script_value}".lower()
    risky_terms = (
        "docker",
        "release",
        "publish",
        "deploy",
        "install-ca",
        "adb ",
        "xcodebuild",
        "simctl",
        "fastlane",
        "gradlew",
        "open ",
        "rm -",
        "sudo",
        "git push",
    )
    return not any(term in text for term in risky_terms)


def _feature_terms(feature: str) -> list[str]:
    stopwords = {
        "and",
        "for",
        "from",
        "into",
        "the",
        "this",
        "that",
        "with",
        "style",
        "ideas",
    }
    return [
        term
        for term in re.split(r"[^a-z0-9]+", feature.lower())
        if len(term) > 2 and term not in stopwords
    ]


def _score_behavior_action(action: dict[str, Any], terms: list[str]) -> int:
    haystack = f"{action['name']} {action['description']} {' '.join(action['command'])}".lower()
    score = sum(1 for term in terms if term in haystack)
    name = str(action.get("name", "")).lower()
    if "lobster" in name or "molt" in name:
        score += 6
    if "openclaw" in name:
        score += 4
    if "train" in name and any(term in terms for term in {"research", "experiment", "experiments", "metric"}):
        score += 4
    if ("agent" in name or "rpc" in name) and any(term in terms for term in {"agent", "harness", "runtime", "tool"}):
        score += 2
    if ("lint" in name or "check" in name) and not any(term in terms for term in {"lint", "check"}):
        score -= 2
    if "test" in name and "test" not in terms:
        score -= 1
    if any(term in name for term in ("_gen", "_write", "_stage")):
        score -= 3
    return score


def _infer_behavior_actions(src: Path, inventory_paths: set[str], feature: str) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    terms = _feature_terms(feature)

    package_paths = _iter_named_source_files(src, {"package.json"}, limit=80)
    package_paths.sort(key=lambda path: (0 if path.parent == src else 1, len(path.relative_to(src).parts), path.as_posix()))
    for package_path in package_paths:
        package = _read_json_source(package_path)
        scripts = package.get("scripts") if isinstance(package.get("scripts"), dict) else {}
        if not scripts:
            continue
        cwd = _cwd_for_source_file(src, package_path)
        rel_parent = "." if cwd == "source_repo" else cwd
        prefix = _script_command_prefix(package_path, package)
        preferred_scripts = ["test", "build", "check", "lint", "start", "dev", "openclaw", "openclaw:rpc", "moltbot:rpc"]
        matched_scripts = [name for name in sorted(scripts) if any(term in name.lower() for term in terms)]
        for script_name in [*preferred_scripts, *matched_scripts]:
            if script_name not in scripts or not _script_is_safe(script_name, scripts[script_name]):
                continue
            _add_action(
                actions,
                seen,
                name=f"{_safe_action_name(rel_parent, 'root')}_{script_name}",
                command=[*prefix, script_name],
                description=f"Run package.json script `{script_name}` from `{rel_parent}`.",
                cwd=cwd,
                timeout_seconds=180 if script_name in {"test", "build", "check", "lint"} else 120,
            )

    makefile_paths = _iter_named_source_files(src, {"Makefile", "makefile"}, limit=20)
    for makefile_path in makefile_paths:
        text = makefile_path.read_text(encoding="utf-8", errors="ignore")
        targets = set(re.findall(r"^([a-zA-Z][\\w-]*):", text, flags=re.MULTILINE))
        for target in ("test", "build", "run", "lint"):
            if target in targets:
                cwd = _cwd_for_source_file(src, makefile_path)
                rel_parent = "." if cwd == "source_repo" else cwd
                _add_action(
                    actions,
                    seen,
                    name=f"{_safe_action_name(rel_parent, 'root')}_make_{target}",
                    command=["make", target],
                    description=f"Run Makefile target `{target}` from `{rel_parent}`.",
                    cwd=cwd,
                    timeout_seconds=180,
                )

    pyproject_paths = _iter_named_source_files(src, {"pyproject.toml"}, limit=30)
    pyproject = _read_toml_source(src / "pyproject.toml") if (src / "pyproject.toml").exists() else {}
    has_uv_project = bool(pyproject)
    has_tests = any(
        path.startswith("tests/") or Path(path).name.startswith("test_") or Path(path).name.endswith("_test.py")
        for path in inventory_paths
    )
    if has_tests:
        _add_action(
            actions,
            seen,
            name="python_tests",
            command=["python3", "-m", "pytest"],
            description="Run the absorbed Python test suite.",
            timeout_seconds=180,
        )
    if "prepare.py" in inventory_paths:
        _add_action(
            actions,
            seen,
            name="prepare",
            command=(["uv", "run", "prepare.py"] if has_uv_project else ["python3", "prepare.py"]),
            description="Run the absorbed repository's preparation step.",
            timeout_seconds=600,
            output_globs=["*.log", "*.json", "*.tsv", "data/**", "results/**"],
        )
    if "train.py" in inventory_paths:
        _add_action(
            actions,
            seen,
            name="train",
            command=(["uv", "run", "train.py"] if has_uv_project else ["python3", "train.py"]),
            description="Run the absorbed repository's training or experiment script.",
            timeout_seconds=900,
            output_globs=["run.log", "*.log", "results.tsv", "*.tsv", "results/**"],
        )

    for pyproject_path in pyproject_paths:
        nested_pyproject = _read_toml_source(pyproject_path)
        project = nested_pyproject.get("project") if isinstance(nested_pyproject.get("project"), dict) else {}
        scripts = project.get("scripts") if isinstance(project.get("scripts"), dict) else {}
        if not scripts:
            continue
        cwd = _cwd_for_source_file(src, pyproject_path)
        rel_parent = "." if cwd == "source_repo" else cwd
        for script_name in sorted(scripts)[:10]:
            if terms and not any(term in script_name.lower() for term in terms):
                continue
            _add_action(
                actions,
                seen,
                name=f"{_safe_action_name(rel_parent, 'root')}_{script_name}",
                command=["uv", "run", script_name],
                description=f"Run pyproject console script `{script_name}` from `{rel_parent}`.",
                cwd=cwd,
                timeout_seconds=180,
            )

    for candidate_path in _iter_named_source_files(src, {"main.py", "app.py", "cli.py", "agent.py", "harness.py"}, limit=50):
        rel_path = candidate_path.relative_to(src).as_posix()
        cwd = _cwd_for_source_file(src, candidate_path)
        rel_parent = "." if cwd == "source_repo" else cwd
        if cwd != "source_repo" and terms and not any(term in rel_path.lower() for term in terms):
            continue
        if rel_path in inventory_paths or cwd != "source_repo":
            _add_action(
                actions,
                seen,
                name=f"{_safe_action_name(rel_parent, 'root')}_{candidate_path.stem}",
                command=["python3", candidate_path.name],
                description=f"Run `{candidate_path.name}` from `{rel_parent}`.",
                cwd=cwd,
                timeout_seconds=120,
            )

    readme_paths = [
        path
        for path in _iter_named_source_files(src, {"README.md", "program.md"}, limit=40)
        if path.parent == src or any(term in path.relative_to(src).as_posix().lower() for term in terms)
    ]
    command_re = re.compile(
        r"(?m)^\\s*(?:\\$\\s*)?"
        r"((?:uv\\s+run|python3?|pytest|npm\\s+run|npm\\s+test|pnpm\\s+run|yarn\\s+run|bun\\s+run|make)\\s+[^\\n`;&|]+)"
    )
    for readme_path in readme_paths:
        text = readme_path.read_text(encoding="utf-8", errors="ignore")
        cwd = _cwd_for_source_file(src, readme_path)
        for raw in command_re.findall(text)[:8]:
            command = _shell_words(raw.strip())
            if not command:
                continue
            name_seed = "_".join(command[:3])
            timeout = 900 if any("train" in part or "experiment" in part for part in command) else 180
            _add_action(
                actions,
                seen,
                name=f"doc_{name_seed}",
                command=command,
                description=f"Run documented command from {readme_path.relative_to(src).as_posix()}: `{raw.strip()}`.",
                cwd=cwd,
                timeout_seconds=timeout,
            )

    for action in actions:
        action["score"] = _score_behavior_action(action, terms)

    actions.sort(key=lambda item: (-int(item.get("score", 0)), item["name"]))
    for action in actions:
        action.pop("score", None)
    return actions[:12]


def _normalize_behavior(raw: Any, inferred_actions: list[dict[str, Any]]) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    if isinstance(raw, dict) and isinstance(raw.get("actions"), list):
        for item in raw["actions"]:
            if not isinstance(item, dict):
                continue
            command = item.get("command")
            if isinstance(command, str):
                command = _shell_words(command)
            if not isinstance(command, list) or not all(isinstance(part, str) and part for part in command):
                continue
            _add_action(
                actions,
                seen,
                name=str(item.get("name") or "run"),
                command=command,
                description=str(item.get("description") or "LLM-proposed absorbed behavior command."),
                cwd=str(item.get("cwd") or "source_repo"),
                timeout_seconds=int(item.get("timeout_seconds") or 60),
                output_globs=[
                    str(pattern)
                    for pattern in item.get("output_globs", [])
                    if isinstance(pattern, str) and pattern
                ] or None,
            )

    for action in inferred_actions:
        _add_action(
            actions,
            seen,
            name=action["name"],
            command=action["command"],
            description=action["description"],
            cwd=action.get("cwd", "source_repo"),
            timeout_seconds=int(action.get("timeout_seconds", 60)),
            output_globs=action.get("output_globs") or None,
        )

    if not actions:
        actions.append(
            {
                "name": "inspect",
                "description": "Inspect source tree when no safe executable behavior could be inferred.",
                "command": ["python3", "-c", "from pathlib import Path; print('\\n'.join(sorted(p.as_posix() for p in Path('.').rglob('*') if p.is_file())[:200]))"],
                "cwd": "source_repo",
                "timeout_seconds": 30,
                "output_globs": ["*.md", "*.py", "*.json", "*.txt"],
            }
        )
    return {
        "version": "system-zero-behavior-contract-v1",
        "default_action": actions[0]["name"],
        "actions": actions,
    }


def _source_tree_files(src: Path, priority_paths: list[str] | None = None) -> list[Path]:
    candidates: list[Path] = []
    seen: set[str] = set()
    for raw_path in priority_paths or []:
        try:
            path = _resolve_beneath(src, raw_path, "Refusing behavior priority outside source")
        except ValueError:
            continue
        if not path.is_file():
            continue
        rel = path.relative_to(src).as_posix()
        if any(part in SOURCE_TREE_SKIP_DIRS for part in Path(rel).parts) or rel in seen:
            continue
        candidates.append(path)
        seen.add(rel)
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(src).as_posix()
        if any(part in SOURCE_TREE_SKIP_DIRS for part in Path(rel).parts) or rel in seen:
            continue
        candidates.append(path)
        seen.add(rel)
    return candidates


def _behavior_priority_paths(src: Path, behavior_contract: dict[str, Any], feature: str = "") -> list[str]:
    priority: list[str] = []
    terms = _feature_terms(feature)

    def add(raw: str) -> None:
        raw = raw.strip("/")
        if raw and raw not in priority:
            priority.append(raw)

    def add_dir(raw: str, *, max_bytes: int = 5_000_000, max_files: int = 2000) -> None:
        directory = src / raw.strip("/")
        if not directory.is_dir():
            return
        added_bytes = 0
        added_files = 0
        for path in sorted(directory.rglob("*")):
            if added_files >= max_files:
                break
            if not path.is_file():
                continue
            rel = path.relative_to(src).as_posix()
            if any(part in SOURCE_TREE_SKIP_DIRS for part in Path(rel).parts):
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if added_bytes + size > max_bytes:
                break
            add(rel)
            added_bytes += size
            added_files += 1

    def add_script_references(cwd_prefix: str, script_name: str) -> None:
        package_path = src / cwd_prefix / "package.json" if cwd_prefix else src / "package.json"
        package = _read_json_source(package_path)
        scripts = package.get("scripts") if isinstance(package.get("scripts"), dict) else {}
        script = scripts.get(script_name)
        if not isinstance(script, str):
            return
        for token in _shell_words(script):
            cleaned = token.strip("\"'")
            if Path(cleaned).suffix.lower() not in {".py", ".js", ".mjs", ".cjs", ".ts", ".sh"}:
                continue
            rel_path = f"{cwd_prefix}/{cleaned}".strip("/")
            add(rel_path)
            parent = str(Path(rel_path).parent)
            if parent and parent != ".":
                add_dir(parent)

    for name in (
        "README.md",
        "program.md",
        "package.json",
        "pyproject.toml",
        "uv.lock",
        "pnpm-lock.yaml",
        "package-lock.json",
        "yarn.lock",
        "bun.lockb",
        "Makefile",
        "makefile",
    ):
        add(name)

    actions = behavior_contract.get("actions") if isinstance(behavior_contract.get("actions"), list) else []
    for action in actions:
        if not isinstance(action, dict):
            continue
        cwd = str(action.get("cwd") or "source_repo")
        cwd_prefix = "" if cwd == "source_repo" else cwd.strip("/")
        for name in (
            "README.md",
            "program.md",
            "package.json",
            "pyproject.toml",
            "uv.lock",
            "pnpm-lock.yaml",
            "package-lock.json",
            "yarn.lock",
            "bun.lockb",
            "Makefile",
            "makefile",
        ):
            add(f"{cwd_prefix}/{name}" if cwd_prefix else name)
        command = action.get("command") if isinstance(action.get("command"), list) else []
        if len(command) >= 3 and command[0] in {"npm", "pnpm", "yarn", "bun"} and command[1] == "run":
            add_script_references(cwd_prefix, str(command[2]))
        for part in command:
            if not isinstance(part, str):
                continue
            if Path(part).suffix.lower() not in {".py", ".js", ".mjs", ".cjs", ".ts", ".sh"}:
                continue
            add(f"{cwd_prefix}/{part}" if cwd_prefix else part)
    if terms:
        generic_terms = {"agent", "runtime", "tool", "tools", "execution", "engine", "loop", "patterns", "reusable", "connection"}
        priority_terms = [term for term in terms if term not in generic_terms]
        if not priority_terms:
            priority_terms = terms
        matched_bytes = 0
        for term in priority_terms:
            term_bytes = 0
            for path in sorted(src.rglob("*")):
                if matched_bytes >= 5_000_000 or term_bytes >= 1_500_000:
                    break
                if not path.is_file():
                    continue
                rel = path.relative_to(src).as_posix()
                rel_lower = rel.lower()
                if any(part in SOURCE_TREE_SKIP_DIRS for part in Path(rel).parts):
                    continue
                if term not in rel_lower:
                    continue
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                if matched_bytes + size > 5_000_000 or term_bytes + size > 1_500_000:
                    continue
                add(rel)
                matched_bytes += size
                term_bytes += size
    return [path for path in priority if (src / path).is_file()]


def _source_tree_summary(src: Path, priority_paths: list[str] | None = None) -> dict[str, Any]:
    digest = hashlib.sha256()
    files = 0
    bytes_total = 0
    skipped_files = 0
    samples: list[str] = []
    for path in _source_tree_files(src, priority_paths):
        rel = path.relative_to(src)
        try:
            size = path.stat().st_size
        except OSError:
            skipped_files += 1
            continue
        if size > SOURCE_TREE_MAX_FILE_BYTES or bytes_total + size > SOURCE_TREE_MAX_BYTES:
            skipped_files += 1
            continue
        rel_text = rel.as_posix()
        digest.update(rel_text.encode("utf-8"))
        digest.update(path.read_bytes())
        files += 1
        bytes_total += size
        if len(samples) < 30:
            samples.append(rel_text)
    return {
        "path": "source_repo",
        "files": files,
        "bytes": bytes_total,
        "sha256": digest.hexdigest(),
        "skipped_files": skipped_files,
        "sample": samples,
    }


def _copy_source_tree(src: Path, target: Path, priority_paths: list[str] | None = None) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    copied_bytes = 0
    for path in _source_tree_files(src, priority_paths):
        rel = path.relative_to(src)
        dest = target / rel
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > SOURCE_TREE_MAX_FILE_BYTES or copied_bytes + size > SOURCE_TREE_MAX_BYTES:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        copied_bytes += size


def _entry_script() -> str:
    return """#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sz.interfaces import bus, memory


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\\n", encoding="utf-8")


def rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def digest_sources(module_dir: Path, manifest: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    for record in manifest.get("files", []):
        rel = str(record.get("to", ""))
        path = module_dir / rel
        if path.exists():
            digest.update(rel.encode("utf-8"))
            digest.update(path.read_bytes())
    source_tree = module_dir / "source_repo"
    if source_tree.exists():
        for path in sorted(source_tree.rglob("*")):
            if not path.is_file():
                continue
            try:
                source_rel = path.relative_to(source_tree).as_posix()
            except ValueError:
                continue
            digest.update(source_rel.encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


def seed_inbox(inbox_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    inbox = read_json(inbox_path, {"items": []})
    if not isinstance(inbox, dict):
        inbox = {"items": []}
    items = inbox.setdefault("items", [])
    if not isinstance(items, list):
        inbox["items"] = items = []
    if not items:
        items.append(
            {
                "id": "bootstrap",
                "status": "pending",
                "action": (manifest.get("behavior_contract") or {}).get("default_action", "auto"),
                "objective": manifest.get("feature", "Absorbed feature"),
                "created_at": utc_now(),
                "source": manifest.get("source"),
            }
        )
    return inbox


def select_action(manifest: dict[str, Any], item: dict[str, Any]) -> dict[str, Any] | None:
    contract = manifest.get("behavior_contract") if isinstance(manifest.get("behavior_contract"), dict) else {}
    actions = contract.get("actions") if isinstance(contract.get("actions"), list) else []
    configured = os.environ.get("SZ_SETPOINT_action_name", "auto")
    item_action = str(item.get("action") or "auto")
    requested = configured if configured and configured != "auto" else item_action
    if requested == "auto":
        requested = str(contract.get("default_action") or (actions[0].get("name") if actions and isinstance(actions[0], dict) else ""))
    for action in actions:
        if isinstance(action, dict) and action.get("name") == requested:
            return action
    return actions[0] if actions and isinstance(actions[0], dict) else None


def safe_child(base: Path, raw: str) -> Path:
    base_resolved = base.resolve()
    candidate = (base_resolved / raw).resolve()
    try:
        candidate.relative_to(base_resolved)
    except ValueError:
        raise RuntimeError(f"path escapes workspace: {raw}")
    return candidate


def ensure_workspace(module_dir: Path, shared_dir: Path, task_id: str) -> Path:
    workspace = shared_dir / "workspaces" / task_id
    source_repo = module_dir / "source_repo"
    if workspace.exists():
        return workspace
    if not source_repo.exists():
        raise RuntimeError("missing source_repo; cannot execute absorbed behavior")
    shutil.copytree(
        source_repo,
        workspace,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".mypy_cache", ".venv", "venv", "node_modules"),
    )
    return workspace


def collect_outputs(workspace: Path, patterns: list[str], limit: int = 20) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pattern in patterns or []:
        if not isinstance(pattern, str) or not pattern:
            continue
        for path in sorted(workspace.glob(pattern)):
            if len(outputs) >= limit:
                return outputs
            if not path.is_file():
                continue
            rel_path = rel(workspace, path)
            if rel_path in seen:
                continue
            seen.add(rel_path)
            try:
                data = path.read_bytes()
            except OSError:
                continue
            outputs.append({"path": rel_path, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    return outputs


def run_action(
    module_dir: Path,
    shared_dir: Path,
    manifest: dict[str, Any],
    item: dict[str, Any],
    task_id: str,
) -> dict[str, Any]:
    action = select_action(manifest, item)
    if action is None:
        return {"status": "blocked", "error": "no behavior action available"}
    command = action.get("command")
    if not isinstance(command, list) or not all(isinstance(part, str) and part for part in command):
        return {"status": "blocked", "action": action.get("name"), "error": "invalid behavior command"}

    workspace = ensure_workspace(module_dir, shared_dir, task_id)
    cwd_raw = str(action.get("cwd") or ".")
    if cwd_raw == "source_repo":
        cwd_raw = "."
    cwd = safe_child(workspace, cwd_raw)
    cwd.mkdir(parents=True, exist_ok=True)
    write_json(workspace / ".s0-task.json", item)

    timeout_override = int(os.environ.get("SZ_SETPOINT_command_timeout_seconds", "0"))
    timeout = timeout_override if timeout_override > 0 else int(action.get("timeout_seconds", 60))
    timeout = max(1, min(timeout, 3600))
    max_output_chars = int(os.environ.get("SZ_SETPOINT_max_output_chars", "4000"))
    env = dict(os.environ)
    env.update(
        {
            "S0_ABSORBED_SOURCE": str(workspace),
            "S0_TASK_ID": task_id,
            "S0_FEATURE": str(manifest.get("feature") or ""),
        }
    )
    started = time.time()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        status = "completed" if completed.returncode == 0 else "failed"
        return {
            "status": status,
            "action": action.get("name"),
            "description": action.get("description"),
            "command": command,
            "cwd": rel(workspace, cwd),
            "returncode": completed.returncode,
            "duration_seconds": round(time.time() - started, 3),
            "stdout": (completed.stdout or "")[-max_output_chars:],
            "stderr": (completed.stderr or "")[-max_output_chars:],
            "outputs": collect_outputs(workspace, action.get("output_globs") or []),
            "workspace": rel(shared_dir.parent.parent.parent, workspace),
        }
    except FileNotFoundError as exc:
        return {
            "status": "blocked",
            "action": action.get("name"),
            "command": command,
            "duration_seconds": round(time.time() - started, 3),
            "error": f"command not found: {exc.filename}",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "action": action.get("name"),
            "command": command,
            "duration_seconds": round(time.time() - started, 3),
            "stdout": (exc.stdout or "")[-max_output_chars:] if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "")[-max_output_chars:] if isinstance(exc.stderr, str) else "",
        }
    except Exception as exc:
        return {
            "status": "blocked",
            "action": action.get("name"),
            "command": command,
            "duration_seconds": round(time.time() - started, 3),
            "error": str(exc)[:1000],
        }


def process_items(
    module_dir: Path,
    shared_dir: Path,
    inbox: dict[str, Any],
    manifest: dict[str, Any],
    source_digest: str,
    limit: int,
) -> list[dict[str, Any]]:
    processed: list[str] = []
    executions: list[dict[str, Any]] = []
    results_dir = shared_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    mode = os.environ.get("SZ_SETPOINT_execution_mode", "observe")
    for item in inbox.get("items", []):
        if len(processed) >= limit:
            break
        if not isinstance(item, dict) or item.get("status") not in {"pending", "waiting_for_execute"}:
            continue
        task_id = str(item.get("id") or f"task-{len(processed) + 1}")
        action = select_action(manifest, item)
        if mode == "execute":
            execution = run_action(module_dir, shared_dir, manifest, item, task_id)
            final_status = execution.get("status", "failed")
        else:
            execution = {
                "status": "waiting_for_execute",
                "action": action.get("name") if action else None,
                "description": action.get("description") if action else None,
                "command": action.get("command") if action else None,
                "reason": "execution_mode is observe; switch setpoint execution_mode=execute to run absorbed behavior",
            }
            final_status = "waiting_for_execute"
        evidence = {
            "task_id": task_id,
            "completed_at": utc_now() if final_status == "completed" else None,
            "recorded_at": utc_now(),
            "status": final_status,
            "objective": item.get("objective"),
            "feature": manifest.get("feature"),
            "source": manifest.get("source"),
            "source_ref": manifest.get("ref"),
            "source_digest": source_digest,
            "behavior_contract": manifest.get("behavior_contract"),
            "execution": execution,
            "copied_files": [
                {
                    "path": record.get("to"),
                    "source": record.get("from"),
                    "sha256": record.get("sha256"),
                    "bytes": record.get("bytes"),
                }
                for record in manifest.get("files", [])
            ],
            "protocol_behavior": [
                "read source-backed feature manifest",
                "maintain shared task inbox",
                "map source behavior to a declared action",
                "execute declared action when execution_mode=execute",
                "emit bus snapshot",
                "append memory snapshot",
                "write deterministic task result with command evidence",
            ],
        }
        write_json(results_dir / f"{task_id}.json", evidence)
        item["status"] = final_status
        if evidence["completed_at"]:
            item["completed_at"] = evidence["completed_at"]
        item["last_recorded_at"] = evidence["recorded_at"]
        item["result"] = str((results_dir / f"{task_id}.json").relative_to(shared_dir.parent.parent.parent))
        processed.append(task_id)
        executions.append(execution)
    return executions


def main() -> int:
    module_dir = Path(os.environ.get("SZ_MODULE_DIR", Path(__file__).resolve().parent)).resolve()
    repo_root = Path(os.environ.get("SZ_REPO_ROOT", ".")).resolve()
    module_id = os.environ.get("SZ_MODULE_ID", module_dir.name)
    bus_path = Path(os.environ.get("SZ_BUS_PATH", repo_root / ".sz" / "bus.jsonl"))
    manifest = read_json(module_dir / "source_manifest.json", {})
    shared_dir = repo_root / ".sz" / "shared" / "absorbed" / module_id
    inbox_path = shared_dir / "inbox.json"
    state_path = module_dir / "state.json"
    mode = os.environ.get("SZ_SETPOINT_execution_mode", "observe")
    try:
        max_items = max(1, int(os.environ.get("SZ_SETPOINT_max_items", "1")))
    except ValueError:
        max_items = 1

    source_digest = digest_sources(module_dir, manifest)
    inbox = seed_inbox(inbox_path, manifest)
    executions = process_items(module_dir, shared_dir, inbox, manifest, source_digest, max_items)
    write_json(inbox_path, inbox)

    state = read_json(state_path, {"ticks": 0})
    state["ticks"] = int(state.get("ticks", 0)) + 1
    state["last_tick_at"] = utc_now()
    state["last_source_digest"] = source_digest
    state["last_executions"] = executions
    write_json(state_path, state)

    items = [item for item in inbox.get("items", []) if isinstance(item, dict)]
    completed = sum(1 for item in items if item.get("status") == "completed")
    failed = sum(1 for item in items if item.get("status") in {"failed", "timeout", "blocked"})
    waiting = sum(1 for item in items if item.get("status") in {"pending", "waiting_for_execute"})
    contract = manifest.get("behavior_contract") if isinstance(manifest.get("behavior_contract"), dict) else {}
    payload = {
        "operation": "absorbed_feature",
        "feature": manifest.get("feature"),
        "source": manifest.get("source"),
        "mode": mode,
        "behavior_contract_version": contract.get("version"),
        "default_action": contract.get("default_action"),
        "actions_total": len(contract.get("actions", []) if isinstance(contract.get("actions"), list) else []),
        "source_digest": source_digest[:16],
        "source_files": len(manifest.get("files", [])),
        "source_tree": manifest.get("source_tree"),
        "tasks_total": len(items),
        "tasks_completed": completed,
        "tasks_failed": failed,
        "tasks_waiting": waiting,
        "executions": executions,
        "shared_namespace": f".sz/shared/absorbed/{module_id}",
    }
    event_type = f"absorbed.{module_id.replace('-', '.')}.snapshot"
    bus.emit(bus_path, module_id, event_type, payload)
    memory.append(repo_root, "absorbed.snapshots", {"module_id": module_id, "event_type": event_type, **payload})
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _reconcile_script() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import json
import os
from pathlib import Path

module_id = os.environ["SZ_MODULE_ID"]
registry_path = Path(os.environ["SZ_REGISTRY_PATH"])
module_dir = Path(os.environ["SZ_MODULE_DIR"])
registry = json.loads(registry_path.read_text()) if registry_path.exists() else {}
runtime = {
    "module_id": module_id,
    "bindings": [
        item for item in registry.get("bindings", [])
        if item.get("requirer") == module_id or item.get("provider") == module_id
    ],
    "unsatisfied": [
        item for item in registry.get("unsatisfied", [])
        if item.get("requirer") == module_id
    ],
}
(module_dir / "runtime.json").write_text(json.dumps(runtime, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
PY
"""


def _doctor_script() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import hashlib
import json
import os
from pathlib import Path

import yaml

module_dir = Path(os.environ["SZ_MODULE_DIR"])
manifest = yaml.safe_load((module_dir / "module.yaml").read_text()) or {}
source_manifest = json.loads((module_dir / "source_manifest.json").read_text())
if manifest.get("entry", {}).get("command") != "entry.py":
    raise SystemExit("absorbed modules must execute the protocol adapter entry.py")
for required in ["entry.py", "reconcile.sh", "doctor.sh", "source_manifest.json"]:
    if not (module_dir / required).exists():
        raise SystemExit(f"missing {required}")
if not (module_dir / "source_repo").exists():
    raise SystemExit("missing source_repo")
behavior = source_manifest.get("behavior_contract")
if not isinstance(behavior, dict) or not behavior.get("actions"):
    raise SystemExit("missing executable behavior_contract.actions")
for record in source_manifest.get("files", []):
    path = module_dir / record["to"]
    if not path.exists():
        raise SystemExit(f"missing copied source file: {record['to']}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != record.get("sha256"):
        raise SystemExit(f"source digest mismatch: {record['to']}")
print("ok")
PY
"""


def _normalize_draft(
    draft: dict[str, Any],
    *,
    source: str,
    ref: str | None,
    feature: str,
    module_id: str | None,
    src: Path,
    inv: dict[str, Any],
    llm_result: llm.LLMResult,
) -> dict[str, Any]:
    inventory_paths = _inventory_file_paths(inv)
    resolved_id = _slug(module_id or draft.get("module_id") or feature)
    files_to_copy = _normalize_files(draft, inventory_paths)
    source_records = _source_file_records(src, files_to_copy)
    inferred_actions = _infer_behavior_actions(src, inventory_paths, feature)
    behavior_contract = _normalize_behavior(draft.get("behavior"), inferred_actions)
    source_tree_priority_paths = _behavior_priority_paths(src, behavior_contract, feature)
    action_names = [action["name"] for action in behavior_contract.get("actions", []) if isinstance(action, dict)]
    notes = _short(draft.get("notes"), "", 500)
    normalized = {
        "module_id": resolved_id,
        "description": _short(
            draft.get("description"),
            f"Absorbed protocol adapter for {feature}.",
            200,
        ),
        "category": _short(draft.get("category"), "absorbed", 50),
        "entry": {"type": "python", "command": "entry.py", "args": []},
        "triggers": _normalize_triggers(draft.get("triggers")),
        "provides": [
            {
                "name": _capability_for(resolved_id),
                "address": f"events:absorbed.{resolved_id.replace('-', '.')}.snapshot",
                "description": f"Source-backed snapshots for {resolved_id}.",
            }
        ],
        "requires": _normalize_requires(draft.get("requires")),
        "setpoints": _normalize_setpoints(draft.get("setpoints"), action_names),
        "files_to_copy": files_to_copy,
        "behavior_contract": behavior_contract,
        "entry_script": _entry_script(),
        "reconcile_script": _reconcile_script(),
        "doctor_script": _doctor_script(),
        "source_manifest": {
            "source": source,
            "ref": ref or "HEAD",
            "feature": feature,
            "module_id": resolved_id,
            "llm": {
                "provider": llm_result.provider,
                "model": llm_result.model,
                "tokens_in": llm_result.tokens_in,
                "tokens_out": llm_result.tokens_out,
            },
            "files": source_records,
            "source_tree": _source_tree_summary(src, source_tree_priority_paths),
            "source_tree_priority_files": source_tree_priority_paths,
            "behavior_contract": behavior_contract,
            "draft_notes": notes,
            "adapter": "system-zero-protocol-absorb-v2",
        },
        "source_tree_priority_paths": source_tree_priority_paths,
        "notes": (
            (notes + " " if notes else "")
            + "Normalized into an executable protocol adapter: source files are copied under source/, "
            + "the runnable source tree is copied under source_repo/, entry.py maps tasks to declared "
            + "behavior actions, and commands run only when execution_mode=execute."
        ).strip(),
    }
    return normalized


def _manifest_for(draft: dict[str, Any]) -> dict[str, Any]:
    actions = (draft.get("behavior_contract") or {}).get("actions", [])
    max_timeout = 60
    if isinstance(actions, list):
        for action in actions:
            if isinstance(action, dict):
                try:
                    max_timeout = max(max_timeout, int(action.get("timeout_seconds", 60)))
                except (TypeError, ValueError):
                    pass
    return {
        "id": draft["module_id"], "version": "0.1.0",
        "category": draft.get("category", "absorbed"),
        "description": draft.get("description", "Absorbed feature."),
        "entry": draft["entry"],
        "triggers": draft.get("triggers", [{"on": "tick"}]),
        "provides": draft.get("provides", []),
        "requires": draft.get("requires", []),
        "setpoints": draft.get("setpoints", {}),
        "hooks": {"reconcile": "reconcile.sh", "doctor": "doctor.sh"},
        "limits": {"max_runtime_seconds": min(3600, max_timeout + 30), "max_memory_mb": 1024},
        "personas": ["static", "dynamic"],
    }


def materialize(src: Path, draft: dict, target: Path, *, inventory_paths: set[str] | None = None) -> None:
    target.mkdir(parents=True, exist_ok=True)
    manifest = _manifest_for(draft)
    (target / "module.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    (target / "source_manifest.json").write_text(
        json.dumps(draft["source_manifest"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    src_resolved = src.resolve()
    target_resolved = target.resolve()
    for spec in draft.get("files_to_copy", []):
        from_p = _resolve_beneath(src_resolved, spec["from"], "Refusing to copy outside source")
        try:
            inventory_rel = from_p.relative_to(src_resolved).as_posix()
        except ValueError:
            raise ValueError(f"Refusing to copy outside source: {spec['from']}")
        if inventory_paths is not None and inventory_rel not in inventory_paths:
            raise ValueError(f"Refusing to copy path not present in inventory: {spec['from']}")
        to_p = _resolve_beneath(target_resolved, spec["to"], "Refusing to copy outside module")
        to_p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(from_p, to_p)
    _copy_source_tree(src_resolved, target_resolved / "source_repo", draft.get("source_tree_priority_paths") or [])
    entry = _resolve_beneath(target_resolved, draft["entry"]["command"], "Refusing to write entry outside module")
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(draft["entry_script"])
    entry.chmod(0o755)
    rec = target / "reconcile.sh"
    rec.write_text(draft["reconcile_script"])
    rec.chmod(0o755)
    doc = target / "doctor.sh"
    doc.write_text(draft["doctor_script"])
    doc.chmod(0o755)
    manifest_core.load(target / "module.yaml")


def absorb(source: str, feature: str, *, ref: str | None = None,
           module_id: str | None = None, dry_run: bool = False, force: bool = False) -> dict:
    src = acquire(source, ref)
    inv = inventory(src)
    template = Path(__file__).resolve().parent.parent / "templates" / "absorb_prompt.md"
    schema_path = Path(__file__).resolve().parents[1] / "spec" / "v0.1.0" / "llm-responses" / "absorb-draft.schema.json"
    prompt = render_prompt(template, source, ref, feature, inv)

    # CLC discipline: validated + retried + logged.
    result = llm.invoke(prompt, schema_path=schema_path, template_id="absorb-draft", max_tokens=4000)
    draft = _normalize_draft(
        result.parsed,
        source=source,
        ref=ref,
        feature=feature,
        module_id=module_id,
        src=src,
        inv=inv,
        llm_result=result,
    )

    errs = manifest_core.validate_manifest(_manifest_for(draft))
    if errs:
        raise ValueError(f"absorb normalization produced invalid manifest: {errs}")

    staging = src / ".staging" / draft["module_id"]
    if staging.exists():
        shutil.rmtree(staging)
    materialize(src, draft, staging, inventory_paths=_inventory_file_paths(inv))

    if dry_run:
        return {"staging": str(staging), "draft": draft, "normalized": True}

    subprocess.run(
        util.sz_command("install", draft["module_id"], "--source", str(staging), *(["--force"] if force else [])),
        check=True,
        capture_output=True,
        text=True,
    )
    return {"installed": draft["module_id"], "staging": str(staging), "notes": draft.get("notes", "")}
