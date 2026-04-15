#!/usr/bin/env python3
"""Functional runtime entry point for a reconstructed connection-engine organ."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from sz.interfaces import bus, memory


SKIP_DIRS = {".git", ".sz", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}
TEXT_SUFFIXES = {".md", ".txt", ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml", ".sh", ".html", ".css"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_yaml(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        return default if loaded is None else loaded
    except Exception:
        return default


def rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def iter_text_files(root: Path, limit: int = 300) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if len(files) >= limit:
            break
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            if path.stat().st_size > 250_000:
                continue
        except OSError:
            continue
        files.append(path)
    return files


def recent_events(bus_path: Path, limit: int = 50) -> list[dict[str, Any]]:
    if not bus_path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in bus_path.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]:
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def action_card_cleanup(root: Path, module_dir: Path, _module_id: str, _contract: dict[str, Any]) -> dict[str, Any]:
    base = root / ".sz" / "shared" / "action-card"
    card_path = base / "action-card.json"
    state_path = base / "action-card-state.json"
    archive_path = base / "action-card-archive.json"
    card = read_json(card_path, {"date": utc_now()[:10], "sections": []})
    state = read_json(state_path, {"completed_items": {}})
    archive = read_json(archive_path, {"entries": []})
    completed = state.get("completed_items") if isinstance(state, dict) else {}
    if not isinstance(completed, dict):
        completed = {}
    entries = archive.setdefault("entries", [])
    card_date = str(card.get("date") or utc_now()[:10])
    item_map: dict[str, dict[str, Any]] = {}
    for section in card.get("sections", []) if isinstance(card, dict) else []:
        if not isinstance(section, dict):
            continue
        for item in section.get("items", []) or []:
            if isinstance(item, dict) and item.get("id"):
                merged = dict(item)
                merged["_section_type"] = section.get("type", "task")
                item_map[str(item["id"])] = merged
    archived_count = 0
    for item_id, completed_at in completed.items():
        item_id = str(item_id)
        if any(e.get("id") == item_id and e.get("card_date") == card_date for e in entries if isinstance(e, dict)):
            continue
        item = item_map.get(item_id, {"id": item_id, "name": item_id})
        entries.append(
            {
                "id": item_id,
                "name": str(item.get("name", item_id)),
                "context": str(item.get("context", "")),
                "section_type": str(item.get("_section_type", "task")),
                "card_date": card_date,
                "completed_at": completed_at,
                "archived_at": utc_now(),
            }
        )
        archived_count += 1
    completed_ids = set(str(item_id) for item_id in completed)
    for section in card.get("sections", []) if isinstance(card, dict) else []:
        if isinstance(section, dict):
            section["items"] = [
                item for item in (section.get("items") or [])
                if not (isinstance(item, dict) and str(item.get("id")) in completed_ids)
            ]
    if isinstance(card, dict):
        card["sections"] = [s for s in card.get("sections", []) if isinstance(s, dict) and s.get("items")]
    state["completed_items"] = {}
    state["last_updated"] = utc_now()
    write_json(card_path, card)
    write_json(state_path, state)
    write_json(archive_path, archive)
    return {
        "operation": "action_card_cleanup",
        "archived_count": archived_count,
        "active_items": sum(len(section.get("items", [])) for section in card.get("sections", [])),
        "archive_entries": len(entries),
        "storage_namespace": ".sz/shared/action-card",
    }


def agent_dashboard(root: Path, module_dir: Path, _module_id: str, _contract: dict[str, Any]) -> dict[str, Any]:
    dashboard = root / ".sz" / "shared" / "dashboard"
    registry = read_json(root / ".sz" / "registry.json", {"modules": {}})
    session = read_json(dashboard / "session.json", {})
    sessions = read_json(dashboard / "sessions.json", [])
    action_card = read_json(root / ".sz" / "shared" / "action-card" / "action-card.json", {"sections": []})
    summary = {
        "operation": "agent_dashboard",
        "installed_modules": len((registry.get("modules") or {})),
        "healthy_modules": sum(
            1 for item in (registry.get("modules") or {}).values()
            if isinstance(item, dict) and item.get("status") == "healthy"
        ),
        "active_session": bool(session),
        "session_count": len(sessions) if isinstance(sessions, list) else 0,
        "active_card_items": sum(
            len(section.get("items", []))
            for section in (action_card.get("sections", []) if isinstance(action_card, dict) else [])
            if isinstance(section, dict)
        ),
    }
    write_json(module_dir / "dashboard-summary.json", summary)
    return summary


def content_autopost_policy(root: Path, _module_dir: Path, _module_id: str, _contract: dict[str, Any]) -> dict[str, Any]:
    base = root / ".sz" / "shared" / "content"
    policy = read_yaml(base / "content-mix-policy.yaml", {})
    statuses = [
        str(status).strip().lower()
        for status in (((policy.get("selection") or {}).get("eligible_statuses") or []) if isinstance(policy, dict) else [])
        if str(status).strip()
    ]
    findings: list[dict[str, Any]] = []
    if statuses and statuses != ["approved"]:
        findings.append({"file": ".sz/shared/content/content-mix-policy.yaml", "issue": "eligible_statuses_not_approved_only"})
    patterns = [
        (re.compile(r"approved,\s*ready,\s*or\s*reserved|approved/ready/reserved", re.I), "stale_eligibility_copy"),
        (re.compile(r"48h rule", re.I), "stale_cadence_copy"),
    ]
    for path in sorted((base / "posting").glob("*.md")) if (base / "posting").exists() else []:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern, label in patterns:
            for match in pattern.finditer(text):
                findings.append({"file": rel(root, path), "line": text.count("\n", 0, match.start()) + 1, "issue": label})
    return {
        "operation": "content_autopost_policy",
        "checked_files": len(list((base / "posting").glob("*.md"))) if (base / "posting").exists() else 0,
        "eligible_statuses": statuses,
        "findings": findings,
        "clean": not findings,
    }


def chronicle(root: Path, module_dir: Path, _module_id: str, _contract: dict[str, Any]) -> dict[str, Any]:
    bus_path = root / ".sz" / "bus.jsonl"
    state_path = module_dir / "chain-state.json"
    state = read_json(state_path, {"chain_head": "0" * 16, "event_count": 0})
    events = recent_events(bus_path, 20)
    events_dir = module_dir / "events"
    today = utc_now()[:10]
    out_path = events_dir / f"events-{today}.jsonl"
    events_dir.mkdir(parents=True, exist_ok=True)
    chain_head = str(state.get("chain_head", "0" * 16))
    recorded = 0
    with out_path.open("a", encoding="utf-8") as handle:
        for event in events:
            normalized = {
                "ts": event.get("ts"),
                "module": event.get("module"),
                "type": event.get("type"),
                "payload_digest": hashlib.sha256(
                    json.dumps(event.get("payload", {}), sort_keys=True).encode("utf-8")
                ).hexdigest()[:16],
            }
            chain_head = hashlib.sha256((chain_head + json.dumps(normalized, sort_keys=True)).encode("utf-8")).hexdigest()[:16]
            normalized["chain_head"] = chain_head
            handle.write(json.dumps(normalized, separators=(",", ":")) + "\n")
            recorded += 1
    state = {"chain_head": chain_head, "event_count": int(state.get("event_count", 0)) + recorded, "updated_at": utc_now()}
    write_json(state_path, state)
    return {"operation": "chronicle", "recorded_events": recorded, "chain_head": chain_head, "event_file": rel(module_dir, out_path)}


def context_assembler(root: Path, _module_dir: Path, _module_id: str, _contract: dict[str, Any]) -> dict[str, Any]:
    query = os.environ.get("SZ_CONTEXT_QUERY") or ""
    if not query:
        for event in reversed(recent_events(root / ".sz" / "bus.jsonl", 30)):
            if event.get("type") == "tick":
                query = str((event.get("payload") or {}).get("reason") or "")
                break
    query = query or "system zero reference stack"
    keywords = [w for w in re.split(r"[\s\-_/.,;:]+", query.lower()) if len(w) > 2]
    max_tokens = int(os.environ.get("SZ_SETPOINT_max_tokens", "2000"))
    top_n = int(os.environ.get("SZ_SETPOINT_top_n", "10"))
    scored: list[tuple[float, Path, int]] = []
    for path in iter_text_files(root, 400):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        haystack = f"{path.as_posix().lower()} {text[:2000].lower()}"
        score = sum(haystack.count(keyword) for keyword in keywords) + (2 if path.name.lower().startswith("readme") else 0)
        if score > 0:
            scored.append((float(score), path, max(1, len(text) // 4)))
    selected: list[dict[str, Any]] = []
    total = 0
    for score, path, estimate in sorted(scored, key=lambda item: (-item[0], item[1].as_posix())):
        if len(selected) >= top_n:
            break
        if total + estimate > max_tokens and selected:
            continue
        selected.append({"path": rel(root, path), "score": score, "token_estimate": estimate})
        total += estimate
    return {"operation": "context_assembler", "query": query, "selected": selected, "selected_count": len(selected), "token_estimate": total}


def eidetic(root: Path, module_dir: Path, _module_id: str, _contract: dict[str, Any]) -> dict[str, Any]:
    concepts = ("evidence", "incident", "decision", "policy", "research", "audit", "memory", "lineage")
    records: list[dict[str, Any]] = []
    for path in iter_text_files(root, 400):
        haystack = path.as_posix().lower()
        matched = [concept for concept in concepts if concept in haystack]
        if not matched:
            continue
        records.append({"path": rel(root, path), "concepts": matched, "suffix": path.suffix.lower() or "<none>"})
    by_concept = {concept: sum(1 for record in records if concept in record["concepts"]) for concept in concepts}
    digest = hashlib.sha256(json.dumps(records, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    index = {"operation": "eidetic", "records": records[:50], "record_count": len(records), "by_concept": by_concept, "digest": digest}
    write_json(module_dir / "evidence-index.json", index)
    return {key: value for key, value in index.items() if key != "records"} | {"sample": records[:5]}


def mcp_server_launcher(root: Path, _module_dir: Path, _module_id: str, _contract: dict[str, Any]) -> dict[str, Any]:
    config_candidates = [root / ".mcp.json", root / ".cursor" / "mcp.json", root / "mcp.json"]
    configs = [path for path in config_candidates if path.exists()]
    server_scripts = [
        path for path in iter_text_files(root, 500)
        if "mcp" in path.as_posix().lower() and path.suffix.lower() in {".py", ".js", ".ts", ".sh"}
    ]
    servers: list[dict[str, Any]] = []
    for config in configs:
        data = read_json(config, {})
        for name, value in ((data.get("mcpServers") or data.get("servers") or {}) if isinstance(data, dict) else {}).items():
            command = value.get("command") if isinstance(value, dict) else None
            servers.append({"name": str(name), "source": rel(root, config), "status": "launchable" if command else "missing_command"})
    for script in server_scripts[:20]:
        servers.append({"name": script.stem, "source": rel(root, script), "status": "script_discovered"})
    return {"operation": "mcp_server_launcher", "server_count": len(servers), "servers": servers[:30], "launched": False}


def queue_gate(root: Path, _module_dir: Path, _module_id: str, _contract: dict[str, Any]) -> dict[str, Any]:
    path = Path(os.environ.get("SZ_QUEUE_PATH", "")) if os.environ.get("SZ_QUEUE_PATH") else root / ".sz" / "shared" / "content" / "ready-queue.md"
    max_depth = int(os.environ.get("SZ_SETPOINT_max_depth", "15"))
    active = 0
    total = 0
    skipped = {"posted", "rejected"}
    current_status: str | None = None
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("### "):
                if current_status is not None:
                    total += 1
                    if current_status not in skipped:
                        active += 1
                current_status = ""
            elif current_status is not None and "**Status:**" in line:
                lower = line.lower()
                for status in skipped:
                    if status in lower:
                        current_status = status
                        break
        if current_status is not None:
            total += 1
            if current_status not in skipped:
                active += 1
    return {"operation": "queue_gate", "queue_path": rel(root, path), "total_entries": total, "active_entries": active, "max_depth": max_depth, "gate_open": active <= max_depth}


def registry_validator(root: Path, _module_dir: Path, _module_id: str, _contract: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    registry_path = root / ".sz" / "registry.json"
    registry = read_json(registry_path, None)
    if not isinstance(registry, dict):
        errors.append("registry_not_object")
        registry = {"modules": {}}
    modules = registry.get("modules")
    if not isinstance(modules, dict):
        errors.append("registry_modules_not_object")
        modules = {}
    config = read_yaml(root / ".sz.yaml", {})
    configured = set((config.get("modules") or {}).keys()) if isinstance(config, dict) else set()
    installed = set(modules.keys())
    for missing in sorted(configured - installed):
        warnings.append(f"configured_module_not_installed:{missing}")
    for module_id, record in modules.items():
        if not isinstance(record, dict):
            errors.append(f"module_record_not_object:{module_id}")
            continue
        for field in ("version", "status", "manifest_path"):
            if not record.get(field):
                errors.append(f"missing_{field}:{module_id}")
        manifest_path = root / str(record.get("manifest_path", ""))
        manifest = read_yaml(manifest_path, None)
        if not isinstance(manifest, dict):
            errors.append(f"manifest_unreadable:{module_id}")
            continue
        entry = manifest.get("entry") or {}
        entry_path = manifest_path.parent / str(entry.get("command", ""))
        if not entry.get("command") or not entry_path.exists():
            errors.append(f"entry_missing:{module_id}")
    for unsatisfied in registry.get("unsatisfied", []) or []:
        if isinstance(unsatisfied, dict):
            severity = unsatisfied.get("severity", "warn")
            target = f"{unsatisfied.get('requirer')}:{unsatisfied.get('capability')}"
            (errors if severity == "error" else warnings).append(f"unsatisfied:{target}")
    return {"operation": "registry_validator", "valid": not errors, "errors": errors, "warnings": warnings, "module_count": len(modules)}


def rollback_email_verification(root: Path, _module_dir: Path, _module_id: str, _contract: dict[str, Any]) -> dict[str, Any]:
    base = root / ".sz" / "shared" / "email"
    output_path = base / "external-output-log.json"
    signals_path = base / "intercepted-signals.json"
    outcome_path = base / "outcomes" / "email-draft-verification.json"
    removed_outputs = 0
    removed_signals = 0
    output_log = read_json(output_path, [])
    if isinstance(output_log, list):
        filtered = [entry for entry in output_log if not (isinstance(entry, dict) and entry.get("source") == "email-draft-verifier")]
        removed_outputs = len(output_log) - len(filtered)
        write_json(output_path, filtered)
    signals = read_json(signals_path, [])
    if isinstance(signals, list):
        filtered_signals = [
            signal for signal in signals
            if not (
                isinstance(signal, dict)
                and signal.get("source_channel") == "email"
                and (signal.get("metadata") or {}).get("origin") == "email-draft.py"
                and (signal.get("metadata") or {}).get("draft_id")
            )
        ]
        removed_signals = len(signals) - len(filtered_signals)
        write_json(signals_path, filtered_signals)
    deleted_outcome = outcome_path.exists()
    if deleted_outcome:
        outcome_path.unlink()
    return {
        "operation": "rollback_email_verification",
        "removed_output_entries": removed_outputs,
        "removed_signal_entries": removed_signals,
        "deleted_outcome_file": deleted_outcome,
    }


def sentinel(root: Path, module_dir: Path, _module_id: str, _contract: dict[str, Any]) -> dict[str, Any]:
    checks = [
        (re.compile(r"AKIA[0-9A-Z]{16}"), "aws_key", "high"),
        (re.compile(r"sk-[A-Za-z0-9]{40,}"), "provider_secret", "high"),
        (re.compile(r"-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----"), "private_key", "critical"),
        (re.compile(r"password\s*=\s*['\"][^'\"]+['\"]", re.I), "inline_password", "medium"),
    ]
    findings: list[dict[str, Any]] = []
    for path in iter_text_files(root, 500):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern, label, severity in checks:
            if pattern.search(text):
                findings.append({"file": rel(root, path), "check": label, "severity": severity})
    report = {"operation": "sentinel", "finding_count": len(findings), "findings": findings[:50], "scanned_files": len(iter_text_files(root, 500))}
    write_json(module_dir / "scan-report.json", report)
    return report


def git_info(root: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
        return result.stdout.strip() if result.returncode == 0 else ""
    status = run("status", "--short").splitlines()
    return {"branch": run("branch", "--show-current") or "unknown", "dirty_files": len(status), "status_sample": status[:20]}


def session_bootstrap(root: Path, module_dir: Path, _module_id: str, _contract: dict[str, Any]) -> dict[str, Any]:
    registry = read_json(root / ".sz" / "registry.json", {"modules": {}})
    profile = read_json(root / ".sz" / "repo-profile.json", {})
    payload = {
        "operation": "session_bootstrap",
        "generated_at": utc_now(),
        "purpose": profile.get("purpose", "unknown"),
        "goals": profile.get("goals", []),
        "module_count": len((registry.get("modules") or {})),
        "git": git_info(root),
        "recent_event_types": [event.get("type") for event in recent_events(root / ".sz" / "bus.jsonl", 10)],
    }
    write_json(module_dir / "session-bootstrap.json", payload)
    return payload


def skill_library(root: Path, module_dir: Path, _module_id: str, _contract: dict[str, Any]) -> dict[str, Any]:
    skills = read_json(module_dir / "source" / "skills.json", [])
    query = os.environ.get("SZ_SKILL_QUERY") or " ".join(
        str((event.get("payload") or {}).get("reason", ""))
        for event in recent_events(root / ".sz" / "bus.jsonl", 10)
        if event.get("type") == "tick"
    )
    query_words = {word for word in re.split(r"[^a-z0-9]+", query.lower()) if len(word) > 2}
    matches = []
    for skill in skills if isinstance(skills, list) else []:
        text = f"{skill.get('id', '')} {skill.get('title', '')} {skill.get('description', '')}".lower()
        score = sum(1 for word in query_words if word in text)
        if score:
            matches.append({"id": skill.get("id"), "title": skill.get("title"), "score": score})
    digest = hashlib.sha256(json.dumps(skills, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return {"operation": "skill_library", "skill_count": len(skills) if isinstance(skills, list) else 0, "digest": digest, "matches": sorted(matches, key=lambda item: (-item["score"], item["id"] or ""))[:10]}


def spec_files(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for base in (root / "plan", root / "spec", root / ".sz" / "shared" / "specs"):
        if base.exists():
            candidates.extend(path for path in sorted(base.rglob("*")) if path.is_file() and path.suffix.lower() in {".md", ".json", ".yaml", ".yml"})
    return candidates[:500]


def spec_dependency_graph(root: Path, module_dir: Path, _module_id: str, _contract: dict[str, Any]) -> dict[str, Any]:
    files = spec_files(root)
    nodes = [rel(root, path) for path in files]
    node_set = set(nodes)
    edges: list[dict[str, Any]] = []
    broken: list[dict[str, Any]] = []
    phase_ref = re.compile(r"phase-\d{2,}(?:-[a-z0-9-]+)?")
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        from_node = rel(root, path)
        for match in sorted(set(phase_ref.findall(text))):
            targets = [node for node in nodes if match in node]
            if targets:
                for target in targets:
                    if target != from_node:
                        edges.append({"from": from_node, "to": target, "via": match, "valid": True})
            else:
                broken.append({"from": from_node, "via": match})
    graph = {"operation": "spec_dependency_graph", "nodes": nodes, "edges": edges, "broken_edges": broken, "cycles": [], "node_count": len(nodes), "edge_count": len(edges)}
    write_json(module_dir / "spec-dependency-graph.json", graph)
    return {key: value for key, value in graph.items() if key not in {"nodes", "edges"}} | {"sample_edges": edges[:10], "broken_edges": broken[:10]}


def spec_lint(root: Path, _module_dir: Path, _module_id: str, _contract: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    files = spec_files(root)
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        relative = rel(root, path)
        if path.name == "PLAN.md":
            for heading in ("## Goal", "## Outputs", "## Acceptance criteria"):
                if heading not in text:
                    errors.append(f"{relative}:missing_heading:{heading}")
        if "TODO" in text or "TBD" in text:
            warnings.append(f"{relative}:placeholder")
        if re.search(r"\.\.\.|and so on", text, re.I):
            warnings.append(f"{relative}:abbreviated_content")
    return {"operation": "spec_lint", "checked_files": len(files), "valid": not errors, "errors": errors[:50], "warnings": warnings[:50]}


def start_preamble(root: Path, module_dir: Path, _module_id: str, _contract: dict[str, Any]) -> dict[str, Any]:
    profile = read_json(root / ".sz" / "repo-profile.json", {})
    registry = read_json(root / ".sz" / "registry.json", {"modules": {}})
    git = git_info(root)
    recent = [event.get("type") for event in recent_events(root / ".sz" / "bus.jsonl", 8)]
    lines = [
        f"Purpose: {profile.get('purpose', 'unknown')}",
        f"Modules installed: {len((registry.get('modules') or {}))}",
        f"Branch: {git['branch']} dirty_files={git['dirty_files']}",
        "Recent events: " + ", ".join(str(item) for item in recent if item),
    ]
    payload = {"operation": "start_preamble", "lines": lines, "line_count": len(lines)}
    write_json(module_dir / "start-preamble.json", payload)
    return payload


def system_zero(root: Path, _module_dir: Path, _module_id: str, _contract: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "repo_config": (root / ".sz.yaml").exists(),
        "runtime_dir": (root / ".sz").is_dir(),
        "registry": (root / ".sz" / "registry.json").exists(),
        "bus": (root / ".sz" / "bus.jsonl").exists(),
        "memory": (root / ".sz" / "memory").is_dir(),
    }
    registry = read_json(root / ".sz" / "registry.json", {"modules": {}})
    missing = [name for name, ok in checks.items() if not ok]
    return {"operation": "system_zero", "ready": not missing, "checks": checks, "missing": missing, "module_count": len((registry.get("modules") or {}))}


HANDLERS = {
    "action-card-cleanup-ce": action_card_cleanup,
    "agent-dashboard-ce": agent_dashboard,
    "check-linkedin-autopost-policy-ce": content_autopost_policy,
    "chronicle-ce": chronicle,
    "context-assembler-ce": context_assembler,
    "eidetic-ce": eidetic,
    "mcp-server-launcher-ce": mcp_server_launcher,
    "queue-gate-ce": queue_gate,
    "registry-validator-ce": registry_validator,
    "rollback-email-verification-ce": rollback_email_verification,
    "sentinel-ce": sentinel,
    "session-bootstrap-ce": session_bootstrap,
    "skill-library-ce": skill_library,
    "spec-dependency-graph-ce": spec_dependency_graph,
    "spec-lint-ce": spec_lint,
    "start-preamble-ce": start_preamble,
    "system-zero-ce": system_zero,
}


def main() -> int:
    module_dir = Path(os.environ.get("SZ_MODULE_DIR", Path(__file__).resolve().parent))
    repo_root = Path(os.environ.get("SZ_REPO_ROOT", ".")).resolve()
    module_id = os.environ.get("SZ_MODULE_ID", module_dir.name)
    contract_path = module_dir / "source" / "ce-contract.json"
    contract = read_json(contract_path, {})
    handler = HANDLERS.get(module_id)
    if handler is None:
        raise SystemExit(f"no functional handler registered for {module_id}")
    payload = handler(repo_root, module_dir, module_id, contract)
    payload.update(
        {
            "module_id": module_id,
            "source_kind": contract.get("source_kind"),
            "source_label": contract.get("source_label"),
            "behavior_digest": hashlib.sha256(
                json.dumps(contract.get("behaviors", []), sort_keys=True).encode("utf-8")
            ).hexdigest()[:16],
        }
    )
    event_type = contract.get("event_type") or f"ce.{module_id.replace('-ce', '').replace('-', '.')}.snapshot"
    bus.emit(Path(os.environ["SZ_BUS_PATH"]), module_id, event_type, payload)
    memory.append(repo_root, "ce.reconstruction", {"module_id": module_id, "event_type": event_type, **payload})
    memory.set(repo_root, f"{module_id}.last_result", payload)
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
