#!/usr/bin/env python3
"""
Approval Gate Module for System Zero

Requires human approval before executing changes in the repository.
Provides safety for production systems, learning environments, and safety-critical code.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import click


class Decision(Enum):
    """Approval decisions."""
    APPROVED = "approved"
    REJECTED = "rejected"
    REQUEST_INFO = "request_info"


class RiskLevel(Enum):
    """Risk assessment levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Proposal:
    """Change proposal."""
    id: int
    what: str
    why: str
    files: list[str]
    risk: RiskLevel
    diff_summary: str = ""
    requested_by: str = "system"
    status: str = "pending"


@dataclass
class DecisionLog:
    """Decision record."""
    id: int
    proposal_id: int
    decision: Decision
    decided_by: str
    decided_at: str
    comment: str = ""


# Storage
def get_storage_path() -> Path:
    """Get decisions storage path."""
    return Path(os.environ.get("SZ_MODULE_DIR", ".sz/approval-gate")) / "decisions.jsonl"


def load_proposals() -> list[Proposal]:
    """Load pending proposals."""
    storage = get_storage_path()
    if not storage.exists():
        return []
    
    proposals = []
    for line in storage.read_text().strip().split("\n"):
        if line:
            data = json.loads(line)
            if data.get("status") == "pending":
                proposals.append(Proposal(**data))
    return proposals


def save_proposal(proposal: Proposal) -> None:
    """Save a proposal."""
    storage = get_storage_path()
    storage.parent.mkdir(parents=True, exist_ok=True)
    
    with open(storage, "a") as f:
        f.write(json.dumps({
            "id": proposal.id,
            "what": proposal.what,
            "why": proposal.why,
            "files": proposal.files,
            "risk": proposal.risk.value,
            "diff_summary": proposal.diff_summary,
            "requested_by": proposal.requested_by,
            "status": proposal.status,
        }) + "\n")


def make_decision(proposal_id: int, decision: Decision, decided_by: str, comment: str = "") -> dict:
    """Record a decision."""
    storage = get_storage_path()
    
    # Read all proposals
    proposals = []
    if storage.exists():
        with open(storage) as f:
            for line in f:
                if line.strip():
                    proposals.append(json.loads(line))
    
    # Update proposal status
    for p in proposals:
        if p["id"] == proposal_id:
            p["status"] = decision.value
            p["decided_by"] = decided_by
            p["decided_at"] = datetime.now().isoformat()
            p["comment"] = comment
    
    # Write back
    with open(storage, "w") as f:
        for p in proposals:
            f.write(json.dumps(p) + "\n")
    
    return {"proposal_id": proposal_id, "decision": decision.value}


def assess_risk(files: list[str], change_type: str) -> RiskLevel:
    """Assess risk level of changes."""
    high_risk_patterns = ["production", "prod", "migration", "schema"]
    low_risk_patterns = ["docs", "test", "readme", "changelog"]
    
    files_str = " ".join(files).lower()
    change_str = change_type.lower()
    
    if any(p in files_str or p in change_str for p in high_risk_patterns):
        return RiskLevel.HIGH
    elif any(p in files_str or p in change_str for p in low_risk_patterns):
        return RiskLevel.LOW
    else:
        return RiskLevel.MEDIUM


# CLI Commands
@click.group()
def cli():
    """Approval Gate commands."""
    pass


@cli.command()
def list():
    """List pending proposals."""
    proposals = load_proposals()
    
    if not proposals:
        click.echo("No pending proposals")
        return
    
    for p in proposals:
        click.echo(f"#{p.id}: [{p.risk.value.upper()}] {p.what[:50]}")


@cli.command()
@click.argument("proposal_id", type=int)
@click.option("--decided-by", default="user", help="Who is making the decision")
@click.option("--comment", default="", help="Optional comment")
def approve(proposal_id: int, decided_by: str, comment: str):
    """Approve a proposal."""
    result = make_decision(proposal_id, Decision.APPROVED, decided_by, comment)
    click.echo(json.dumps(result))


@cli.command()
@click.argument("proposal_id", type=int)
@click.option("--decided-by", default="user", help="Who is making the decision")
@click.option("--comment", default="", help="Reason for rejection")
def reject(proposal_id: int, decided_by: str, comment: str):
    """Reject a proposal."""
    result = make_decision(proposal_id, Decision.REJECTED, decided_by, comment)
    click.echo(json.dumps(result))


@cli.command()
@click.argument("proposal_id", type=int)
@click.option("--decided-by", default="user", help="Who is requesting info")
@click.option("--comment", default="", help="Questions for the requester")
def request_info(proposal_id: int, decided_by: str, comment: str):
    """Request more information."""
    result = make_decision(proposal_id, Decision.REQUEST_INFO, decided_by, comment)
    click.echo(json.dumps(result))


@cli.command()
@click.option("--what", required=True, help="What changes")
@click.option("--why", required=True, help="Why changes")
@click.option("--files", required=True, help="Comma-separated files")
@click.option("--diff", default="", help="Diff summary")
def propose(what: str, why: str, files: str, diff: str):
    """Submit a change proposal."""
    files_list = [f.strip() for f in files.split(",")]
    risk = assess_risk(files_list, what)
    
    # Get next ID
    storage = get_storage_path()
    next_id = 1
    if storage.exists():
        with open(storage) as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    next_id = max(next_id, data["id"] + 1)
    
    proposal = Proposal(
        id=next_id,
        what=what,
        why=why,
        files=files_list,
        risk=risk,
        diff_summary=diff,
    )
    save_proposal(proposal)
    
    click.echo(json.dumps({
        "id": proposal.id,
        "risk": proposal.risk.value,
        "status": "pending",
    }))


@cli.command()
def status():
    """Show approval mode status."""
    mode = os.environ.get("SZ_SETPOINT_mode", "approve")
    click.echo(json.dumps({
        "mode": mode,
        "max_pending": os.environ.get("SZ_SETPOINT_max_pending", "10"),
    }))


def main() -> int:
    """Main entry point for event triggers."""
    mode = os.environ.get("SZ_SETPOINT_mode", "approve")
    
    # Auto-approve low risk if mode is auto-low
    if mode == "auto-low":
        proposals = load_proposals()
        for p in proposals:
            if p.risk == RiskLevel.LOW:
                make_decision(p.id, Decision.APPROVED, "auto-low", "Auto-approved low risk")
    
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] != "entry.py":
        cli()
    else:
        sys.exit(main())