#!/usr/bin/env python3
"""
Claude Skills Sync Module for System Zero

Installs and manages AI agent skills in repository,
bringing modern development patterns from the AI ecosystem.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import click


# Available skills (MVP subset)
AVAILABLE_SKILLS = {
    "react-19": {
        "description": "React 19 with React Compiler patterns",
        "tags": ["react", "frontend"],
        "url": "https://github.com/ai-coders/claude-skills-react19",
    },
    "nextjs-15": {
        "description": "Next.js 15 App Router patterns",
        "tags": ["nextjs", "react", "fullstack"],
        "url": "https://github.com/ai-coders/claude-skills-nextjs15",
    },
    "prisma": {
        "description": "Type-safe ORM with full TypeScript",
        "tags": ["orm", "database", "typescript"],
        "url": "https://github.com/ai-coders/claude-skills-prisma",
    },
    "playwright": {
        "description": "E2E testing with Page Objects",
        "tags": ["testing", "e2e"],
        "url": "https://github.com/ai-coders/claude-skills-playwright",
    },
    "tailwind-4": {
        "description": "Tailwind CSS 4 with cn() pattern",
        "tags": ["css", "tailwind"],
        "url": "https://github.com/ai-coders/claude-skills-tailwind4",
    },
    "zustand-5": {
        "description": "Zustand 5 state management",
        "tags": ["state", "react"],
        "url": "https://github.com/ai-coders/claude-skills-zustand5",
    },
    "supabase": {
        "description": "Firebase alternative with PostgreSQL",
        "tags": ["backend", "database", "baas"],
        "url": "https://github.com/ai-coders/claude-skills-supabase",
    },
    "sdd": {
        "description": "Spec-Driven Development workflow",
        "tags": ["workflow", "sdd"],
        "url": "https://github.com/ai-coders/claude-skills-sdd",
    },
}


def get_skills_dir() -> Path:
    """Get skills directory."""
    return Path(os.environ.get("SZ_REPO_ROOT", ".")) / os.environ.get(
        "SZ_SETPOINT_skills_dir", "docs/skills"
    )


def install_skill(skill_id: str, version: str | None = None) -> dict:
    """Install a skill to docs/skills/."""
    if skill_id not in AVAILABLE_SKILLS:
        return {"error": f"Unknown skill: {skill_id}"}
    
    skill = AVAILABLE_SKILLS[skill_id]
    skills_dir = get_skills_dir()
    skill_dir = skills_dir / skill_id
    
    # Create skill directory
    skill_dir.mkdir(parents=True, exist_ok=True)
    
    # Create skill README
    readme_content = f"""# {skill_id}

{skill['description']}

## Tags
{', '.join(skill['tags'])}

## Installation
Auto-installed by claude-skills-sync module.

## Version
{version or 'latest'}

## Source
{skill['url']}
"""
    (skill_dir / "README.md").write_text(readme_content)
    
    return {"installed": skill_id, "version": version or "latest"}


def list_installed_skills() -> list[dict]:
    """List installed skills."""
    skills_dir = get_skills_dir()
    if not skills_dir.exists():
        return []
    
    installed = []
    for skill_dir in skills_dir.iterdir():
        if skill_dir.is_dir() and (skill_dir / "README.md").exists():
            readme = (skill_dir / "README.md").read_text()
            installed.append({
                "id": skill_dir.name,
                "description": readme.split("\n")[1] if "\n" in readme else "",
            })
    
    return installed


def generate_registry() -> dict:
    """Generate skills registry."""
    skills_dir = get_skills_dir()
    registry = {
        "version": "0.1.0",
        "generated_at": subprocess.run(
            ["date", "+%Y-%m-%dT%H:%M:%SZ"], capture_output=True, text=True
        ).stdout.strip(),
        "skills": {},
    }
    
    installed = list_installed_skills()
    for skill in installed:
        registry["skills"][skill["id"]] = skill
    
    return registry


def update_skills() -> dict:
    """Check for skill updates (placeholder)."""
    return {"updated": 0, "message": "Update check placeholder"}


# CLI Commands
@click.group()
def cli():
    """Claude Skills Sync commands."""
    pass


@cli.command()
@click.option("--skill", "skill_id", required=True, help="Skill ID to install")
@click.option("--version", help="Specific version to lock")
def install(skill_id: str, version: str | None):
    """Install a skill."""
    result = install_skill(skill_id, version)
    click.echo(json.dumps(result))


@cli.command()
@click.option("--all", is_flag=True, help="Install all skills")
def install_all(all: bool):
    """Install all skills."""
    if all:
        results = []
        for skill_id in AVAILABLE_SKILLS:
            results.append(install_skill(skill_id))
        click.echo(json.dumps(results))
    else:
        click.echo(json.dumps({"error": "Use --all to install all"}))


@cli.command()
def list():
    """List installed skills."""
    skills = list_installed_skills()
    click.echo(json.dumps({"skills": skills}, indent=2)))


@cli.command()
def available():
    """List available skills."""
    click.echo(json.dumps({"skills": AVAILABLE_SKILLS}, indent=2))


@cli.command()
def registry():
    """Generate skills registry."""
    reg = generate_registry()
    click.echo(json.dumps(reg, indent=2))


@cli.command()
def update():
    """Check for skill updates."""
    result = update_skills()
    click.echo(json.dumps(result))


def main() -> int:
    """Main entry point for tick/event triggers."""
    # Auto-update logic
    auto_update = os.environ.get("SZ_SETPOINT_auto_update", "false") == "true"
    if auto_update:
        update_skills()
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] != "entry.py":
        cli()
    else:
        sys.exit(main())