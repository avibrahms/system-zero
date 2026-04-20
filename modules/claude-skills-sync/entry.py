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


# ALL available skills from the AI ecosystem (80+ skills)
AVAILABLE_SKILLS = {
    # Frontend - React Ecosystem
    "react-19": {
        "description": "React 19 with React Compiler - no more useMemo/useCallback needed",
        "tags": ["react", "frontend", "hooks"],
        "url": "https://github.com/ai-coders/claude-skills-react19",
    },
    "react": {
        "description": "React 18 with hooks, context, and modern patterns",
        "tags": ["react", "frontend"],
        "url": "https://github.com/ai-coders/claude-skills-react",
    },
    "nextjs-15": {
        "description": "Next.js 15 App Router with Server Actions, partial prerendering",
        "tags": ["nextjs", "react", "fullstack"],
        "url": "https://github.com/ai-coders/claude-skills-nextjs15",
    },
    "nextjs": {
        "description": "Next.js 14 App Router patterns",
        "tags": ["nextjs", "react", "fullstack"],
        "url": "https://github.com/ai-coders/claude-skills-nextjs",
    },

    # Frontend - Angular
    "angular-core": {
        "description": "Angular core patterns: standalone components, signals, inject, control flow",
        "tags": ["angular", "frontend"],
        "url": "https://github.com/ai-coders/claude-skills-angular-core",
    },
    "angular-architecture": {
        "description": "Angular architecture: Scope Rule, project structure, file naming",
        "tags": ["angular", "frontend", "architecture"],
        "url": "https://github.com/ai-coders/claude-skills-angular-architecture",
    },
    "angular-forms": {
        "description": "Angular forms: Signal Forms and Reactive Forms",
        "tags": ["angular", "forms"],
        "url": "https://github.com/ai-coders/claude-skills-angular-forms",
    },
    "angular-performance": {
        "description": "Angular performance: NgOptimizedImage, @defer, lazy loading",
        "tags": ["angular", "performance"],
        "url": "https://github.com/ai-coders/claude-skills-angular-performance",
    },

    # Frontend - Mobile
    "react-native": {
        "description": "React Native with Expo and bare workflow",
        "tags": ["react-native", "mobile", "ios", "android"],
        "url": "https://github.com/ai-coders/claude-skills-react-native",
    },

    # State Management
    "zustand-5": {
        "description": "Zustand 5 state management - new simplified API",
        "tags": ["state", "react"],
        "url": "https://github.com/ai-coders/claude-skills-zustand5",
    },
    "zustand": {
        "description": "Zustand state management",
        "tags": ["state", "react"],
        "url": "https://github.com/ai-coders/claude-skills-zustand",
    },
    "redux-toolkit": {
        "description": "Redux Toolkit with RTK Query",
        "tags": ["state", "react", "redux"],
        "url": "https://github.com/ai-coders/claude-skills-redux",
    },
    "jotai": {
        "description": "Jotai atomic state management",
        "tags": ["state", "react"],
        "url": "https://github.com/ai-coders/claude-skills-jotai",
    },
    "recoil": {
        "description": "Recoil state management",
        "tags": ["state", "react"],
        "url": "https://github.com/ai-coders/claude-skills-recoil",
    },

    # CSS / Styling
    "tailwind-4": {
        "description": "Tailwind CSS 4 with cn() pattern, no var() in className",
        "tags": ["css", "tailwind"],
        "url": "https://github.com/ai-coders/claude-skills-tailwind4",
    },
    "tailwind": {
        "description": "Tailwind CSS 3 patterns",
        "tags": ["css", "tailwind"],
        "url": "https://github.com/ai-coders/claude-skills-tailwind",
    },
    "nativewind": {
        "description": "NativeWind - Tailwind for React Native",
        "tags": ["css", "tailwind", "react-native"],
        "url": "https://github.com/ai-coders/claude-skills-nativewind",
    },
    "styled-components": {
        "description": "Styled components CSS-in-JS",
        "tags": ["css", "styled-components"],
        "url": "https://github.com/ai-coders/claude-skills-styled-components",
    },
    "emotion": {
        "description": "Emotion CSS-in-JS",
        "tags": ["css", "emotion"],
        "url": "https://github.com/ai-coders/claude-skills-emotion",
    },

    # Testing
    "playwright": {
        "description": "Playwright E2E testing with Page Objects, selectors",
        "tags": ["testing", "e2e"],
        "url": "https://github.com/ai-coders/claude-skills-playwright",
    },
    "vitest": {
        "description": "Vitest fast test runner",
        "tags": ["testing", "vite"],
        "url": "https://github.com/ai-coders/claude-skills-vitest",
    },
    "pytest": {
        "description": "Pytest for Python - fixtures, mocking, markers",
        "tags": ["testing", "python"],
        "url": "https://github.com/ai-coders/claude-skills-pytest",
    },
    "jest": {
        "description": "Jest testing framework",
        "tags": ["testing", "javascript"],
        "url": "https://github.com/ai-coders/claude-skills-jest",
    },
    "cypress": {
        "description": "Cypress E2E testing",
        "tags": ["testing", "e2e"],
        "url": "https://github.com/ai-coders/claude-skills-cypress",
    },
    "testing-library": {
        "description": "React Testing Library",
        "tags": ["testing", "react"],
        "url": "https://github.com/ai-coders/claude-skills-testing-library",
    },
    "mocha": {
        "description": "Mocha JS testing framework",
        "tags": ["testing", "javascript"],
        "url": "https://github.com/ai-coders/claude-skills-mocha",
    },

    # Databases / ORMs
    "prisma": {
        "description": "Prisma TypeScript ORM with full type safety",
        "tags": ["orm", "database", "typescript"],
        "url": "https://github.com/ai-coders/claude-skills-prisma",
    },
    "supabase": {
        "description": "Supabase Firebase alternative with PostgreSQL",
        "tags": ["backend", "database", "baas"],
        "url": "https://github.com/ai-coders/claude-skills-supabase",
    },
    "django-drf": {
        "description": "Django REST Framework - ViewSets, Serializers, Filters",
        "tags": ["backend", "python", "api"],
        "url": "https://github.com/ai-coders/claude-skills-django-drf",
    },
    "sqlalchemy": {
        "description": "SQLAlchemy ORM for Python",
        "tags": ["orm", "database", "python"],
        "url": "https://github.com/ai-coders/claude-skills-sqlalchemy",
    },
    "drizzle": {
        "description": "Drizzle ORM - lightweight TypeScript ORM",
        "tags": ["orm", "database", "typescript"],
        "url": "https://github.com/ai-coders/claude-skills-drizzle",
    },
    "mongoose": {
        "description": "Mongoose MongoDB ODM",
        "tags": ["database", "mongodb", "nodejs"],
        "url": "https://github.com/ai-coders/claude-skills-mongoose",
    },

    # Backend / APIs
    "express": {
        "description": "Express.js middleware patterns",
        "tags": ["backend", "nodejs", "api"],
        "url": "https://github.com/ai-coders/claude-skills-express",
    },
    "fastapi": {
        "description": "FastAPI Python modern API framework",
        "tags": ["backend", "python", "api"],
        "url": "https://github.com/ai-coders/claude-skills-fastapi",
    },
    "flask": {
        "description": "Flask micro-framework",
        "tags": ["backend", "python"],
        "url": "https://github.com/ai-coders/claude-skills-flask",
    },
    "django": {
        "description": "Django web framework",
        "tags": ["backend", "python"],
        "url": "https://github.com/ai-coders/claude-skills-django",
    },
    "nestjs": {
        "description": "NestJS Node.js framework",
        "tags": ["backend", "nodejs", "api"],
        "url": "https://github.com/ai-coders/claude-skills-nestjs",
    },

    # Go
    "go-testing": {
        "description": "Go testing patterns with teatest, Bubbletea TUI testing",
        "tags": ["go", "testing"],
        "url": "https://github.com/ai-coders/claude-skills-go-testing",
    },
    "golang": {
        "description": "Go best practices and patterns",
        "tags": ["go", "backend"],
        "url": "https://github.com/ai-coders/claude-skills-golang",
    },

    # DevOps
    "github-actions": {
        "description": "GitHub Actions CI/CD workflows",
        "tags": ["devops", "ci-cd"],
        "url": "https://github.com/ai-coders/claude-skills-github-actions",
    },
    "docker": {
        "description": "Docker container patterns",
        "tags": ["devops", "docker"],
        "url": "https://github.com/ai-coders/claude-skills-docker",
    },
    "gcp": {
        "description": "Google Cloud Platform deployment",
        "tags": ["devops", "gcp", "cloud"],
        "url": "https://github.com/ai-coders/claude-skills-gcp",
    },
    "cron": {
        "description": "Cron scheduled tasks automation",
        "tags": ["devops", "cron", "automation"],
        "url": "https://github.com/ai-coders/claude-skills-cron",
    },
    "kubernetes": {
        "description": "Kubernetes deployment",
        "tags": ["devops", "k8s"],
        "url": "https://github.com/ai-coders/claude-skills-kubernetes",
    },
    "terraform": {
        "description": "Terraform infrastructure as code",
        "tags": ["devops", "iac"],
        "url": "https://github.com/ai-coders/claude-skills-terraform",
    },

    # Vector Databases / AI
    "pinecone": {
        "description": "Pinecone vector database for RAG",
        "tags": ["ai", "vector-db", "rag"],
        "url": "https://github.com/ai-coders/claude-skills-pinecone",
    },
    "weaviate": {
        "description": "Weaviate open-source vector database",
        "tags": ["ai", "vector-db"],
        "url": "https://github.com/ai-coders/claude-skills-weaviate",
    },
    "openai-sdk": {
        "description": "OpenAI API patterns",
        "tags": ["ai", "llm"],
        "url": "https://github.com/ai-coders/claude-skills-openai",
    },
    "ai-sdk-5": {
        "description": "Vercel AI SDK 5 - breaking changes from v4",
        "tags": ["ai", "llm", "vercel"],
        "url": "https://github.com/ai-coders/claude-skills-ai-sdk-5",
    },

    # AI Agent Patterns
    "sdd": {
        "description": "Spec-Driven Development workflow",
        "tags": ["workflow", "sdd"],
        "url": "https://github.com/ai-coders/claude-skills-sdd",
    },
    "mcp-builder": {
        "description": "Model Context Protocol server builder",
        "tags": ["ai", "mcp"],
        "url": "https://github.com/ai-coders/claude-skills-mcp",
    },
    "elixir-antipatterns": {
        "description": "Elixir/Phoenix anti-patterns catalog",
        "tags": ["elixir", "phoenix"],
        "url": "https://github.com/ai-coders/claude-skills-elixir",
    },
    "make": {
        "description": "Make (Integromat) no-code automation",
        "tags": ["automation", "nocode"],
        "url": "https://github.com/ai-coders/claude-skills-make",
    },
    "n8n": {
        "description": "n8n workflow automation",
        "tags": ["automation", "workflow"],
        "url": "https://github.com/ai-coders/claude-skills-n8n",
    },

    # Other Frameworks
    "electron": {
        "description": "Electron desktop app - main/renderer, IPC",
        "tags": ["desktop", "cross-platform"],
        "url": "https://github.com/ai-coders/claude-skills-electron",
    },
    "svelte": {
        "description": "Svelte framework",
        "tags": ["frontend", "svelte"],
        "url": "https://github.com/ai-coders/claude-skills-svelte",
    },
    "sveltekit": {
        "description": "SvelteKit full-stack framework",
        "tags": ["frontend", "svelte", "fullstack"],
        "url": "https://github.com/ai-coders/claude-skills-sveltekit",
    },
    "vue": {
        "description": "Vue.js 3 with composition API",
        "tags": ["frontend", "vue"],
        "url": "https://github.com/ai-coders/claude-skills-vue",
    },
    "nuxt": {
        "description": "Nuxt.js Vue meta-framework",
        "tags": ["frontend", "vue", "fullstack"],
        "url": "https://github.com/ai-coders/claude-skills-nuxt",
    },

    # TypeScript
    "typescript": {
        "description": "TypeScript strict patterns - types, interfaces, generics",
        "tags": ["typescript", "language"],
        "url": "https://github.com/ai-coders/claude-skills-typescript",
    },
    "zod-4": {
        "description": "Zod 4 schema validation - breaking from v3",
        "tags": ["typescript", "validation"],
        "url": "https://github.com/ai-coders/claude-skills-zod-4",
    },
    "zod": {
        "description": "Zod schema validation",
        "tags": ["typescript", "validation"],
        "url": "https://github.com/ai-coders/claude-skills-zod",
    },

    # Java
    "java-21": {
        "description": "Java 21 - records, sealed types, virtual threads",
        "tags": ["java", "backend"],
        "url": "https://github.com/ai-coders/claude-skills-java-21",
    },
    "spring-boot-3": {
        "description": "Spring Boot 3 configuration and DI",
        "tags": ["java", "backend"],
        "url": "https://github.com/ai-coders/claude-skills-spring-boot-3",
    },
    "hexagonal-architecture": {
        "description": "Hexagonal architecture layering",
        "tags": ["architecture", "java"],
        "url": "https://github.com/ai-coders/claude-skills-hexagonal",
    },

    # Observability
    "sentry": {
        "description": "Sentry error monitoring",
        "tags": ["monitoring", "error-tracking"],
        "url": "https://github.com/ai-coders/claude-skills-sentry",
    },
    "prometheus": {
        "description": "Prometheus monitoring - PromQL, alerting",
        "tags": ["monitoring", "metrics"],
        "url": "https://github.com/ai-coders/claude-skills-prometheus",
    },
    "grafana": {
        "description": "Grafana dashboards and visualization",
        "tags": ["monitoring", "visualization"],
        "url": "https://github.com/ai-coders/claude-skills-grafana",
    },
    "elk": {
        "description": "ELK Stack - Elasticsearch, Logstash, Kibana",
        "tags": ["monitoring", "logging"],
        "url": "https://github.com/ai-coders/claude-skills-elk",
    },

    # Integrations
    "webhooks": {
        "description": "Webhook HTTP callbacks",
        "tags": ["integration", "webhooks"],
        "url": "https://github.com/ai-coders/claude-skills-webhooks",
    },
    "whatsapp": {
        "description": "WhatsApp Business API messaging",
        "tags": ["integration", "messaging"],
        "url": "https://github.com/ai-coders/claude-skills-whatsapp",
    },
    "stripe": {
        "description": "Stripe payment integration",
        "tags": ["integration", "payments"],
        "url": "https://github.com/ai-coders/claude-skills-stripe",
    },
    "twilio": {
        "description": "Twilio SMS/Voice API",
        "tags": ["integration", "messaging"],
        "url": "https://github.com/ai-coders/claude-skills-twilio",
    },
    "sendgrid": {
        "description": "SendGrid email API",
        "tags": ["integration", "email"],
        "url": "https://github.com/ai-coders/claude-skills-sendgrid",
    },
    "mailgun": {
        "description": "Mailgun email API",
        "tags": ["integration", "email"],
        "url": "https://github.com/ai-coders/claude-skills-mailgun",
    },

    # Messaging
    "rabbitmq": {
        "description": "RabbitMQ message broker",
        "tags": ["messaging", "mq"],
        "url": "https://github.com/ai-coders/claude-skills-rabbitmq",
    },
    "kafka": {
        "description": "Apache Kafka streaming",
        "tags": ["messaging", "streaming"],
        "url": "https://github.com/ai-coders/claude-skills-kafka",
    },

    # Misc Tools
    "deno": {
        "description": "Deno JavaScript runtime - secure Node alternative",
        "tags": ["runtime", "javascript"],
        "url": "https://github.com/ai-coders/claude-skills-deno",
    },
    "bun": {
        "description": "Bun JavaScript runtime",
        "tags": ["runtime", "javascript"],
        "url": "https://github.com/ai-coders/claude-skills-bun",
    },
    "pnpm": {
        "description": "pnpm package manager",
        "tags": ["package-manager", "nodejs"],
        "url": "https://github.com/ai-coders/claude-skills-pnpm",
    },
    "bolt-new": {
        "description": "Bolt.new AI app builder",
        "tags": ["ai", "no-code"],
        "url": "https://github.com/ai-coders/claude-skills-bolt-new",
    },
    "bash-scripting": {
        "description": "Bash shell scripting automation",
        "tags": ["scripting", "shell"],
        "url": "https://github.com/ai-coders/claude-skills-bash",
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