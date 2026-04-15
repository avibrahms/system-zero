"""Deterministic check for an existing autonomous heartbeat. No LLM."""
from __future__ import annotations

from pathlib import Path

# Marker file/dir paths per known framework.
MARKERS = {
    "claude_code":       [".claude"],
    "cursor":            [".cursorrules", ".cursor"],
    "opencode":          [".opencode"],
    "aider":             [".aider.conf.yml"],
    "hermes":            [".hermes/config.yaml"],
    "openclaw":          [".openclaw"],
    "metaclaw":          [".metaclaw"],
    "connection_engine": ["core/system/maintenance-registry.yaml"],
}

# Adopt-mode hosts (have their own pulse).
ADOPT_HOSTS = {"hermes", "openclaw", "metaclaw", "connection_engine"}


def detect(root: Path) -> dict:
    """Return {existing_heartbeat: <name|none>, candidate_hosts: [...]}.

    Adopt-mode hosts win over Install-mode hosts when both markers exist.
    """
    found = []
    for name, markers in MARKERS.items():
        for m in markers:
            if (root / m).exists():
                found.append(name)
                break
    if not found:
        return {"existing_heartbeat": "none", "candidate_hosts": []}
    adopt_hits = [h for h in found if h in ADOPT_HOSTS]
    if adopt_hits:
        return {"existing_heartbeat": adopt_hits[0], "candidate_hosts": adopt_hits + [h for h in found if h not in ADOPT_HOSTS]}
    return {"existing_heartbeat": found[0], "candidate_hosts": found}
