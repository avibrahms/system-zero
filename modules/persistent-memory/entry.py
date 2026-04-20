#!/usr/bin/env python3
"""
Persistent Memory Module for System Zero

Provides SQLite-based persistent storage for observations that survive
repository restarts, server reboots, and team transitions.

Transforms System Zero from stateless to stateful.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import click


# Database path
def get_db_path() -> Path:
    module_dir = os.environ.get("SZ_MODULE_DIR", ".sz/persistent-memory")
    return Path(module_dir) / "memory.db"


def get_connection() -> sqlite3.Connection:
    """Get database connection with WAL mode for concurrency."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize database schema."""
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                type TEXT CHECK (type IN (
                    'decision', 'architecture', 'bugfix',
                    'pattern', 'config', 'preference', 'discovery'
                )) NOT NULL,
                content TEXT NOT NULL,
                project TEXT,
                scope TEXT DEFAULT 'project',
                topic_key TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                session_id TEXT,
                updated_at TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_observations_search ON observations (title, content);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_observations_topic 
                ON observations (project, topic_key) WHERE topic_key IS NOT NULL;
            
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                observation_id INTEGER,
                decision_type TEXT NOT NULL,
                decided_by TEXT,
                decided_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                comment TEXT,
                FOREIGN KEY (observation_id) REFERENCES observations(id)
            );
        """)
        conn.commit()
    finally:
        conn.close()


def save_observation(
    title: str,
    type: str,
    content: str,
    project: str | None = None,
    scope: str = "project",
    topic_key: str | None = None,
    session_id: str | None = None,
) -> dict:
    """Save an observation to persistent memory."""
    conn = get_connection()
    try:
        # Check for existing topic to update
        if topic_key and project:
            existing = conn.execute(
                """SELECT id FROM observations 
                   WHERE project = ? AND topic_key = ?""",
                (project, topic_key)
            ).fetchone()
            
            if existing:
                conn.execute(
                    """UPDATE observations 
                       SET content = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE id = ?""",
                    (content, existing["id"])
                )
                conn.commit()
                return {"id": existing["id"], "action": "updated"}
        
        # Insert new observation
        cursor = conn.execute(
            """INSERT INTO observations (title, type, content, project, scope, topic_key, session_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (title, type, content, project, scope, topic_key, session_id)
        )
        conn.commit()
        return {"id": cursor.lastrowid, "action": "created"}
    finally:
        conn.close()


def search_observations(query: str, limit: int = 20, type_filter: str | None = None) -> list[dict]:
    """Search observations using full-text search."""
    conn = get_connection()
    try:
        sql = """
            SELECT * FROM observations 
            WHERE title LIKE ? OR content LIKE ?
        """
        params = [f"%{query}%", f"%{query}%"]
        
        if type_filter:
            sql += " AND type = ?"
            params.append(type_filter)
        
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_context(project: str, limit: int = 20) -> list[dict]:
    """Get recent context for a project (session recovery)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM observations 
               WHERE project = ? OR scope = 'global'
               ORDER BY created_at DESC 
               LIMIT ?""",
            (project, limit)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def cleanup_old_observations(retention_days: int) -> int:
    """Remove observations older than retention period."""
    conn = get_connection()
    try:
        cutoff = datetime.now() - timedelta(days=retention_days)
        cursor = conn.execute(
            "DELETE FROM observations WHERE created_at < ?",
            (cutoff.isoformat(),)
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


# CLI Commands
@click.group()
def cli():
    """Persistent Memory commands."""
    pass


@cli.command()
@click.option("--title", required=True, help="Observation title")
@click.option("--type", "obs_type", required=True, 
              type=click.Choice(["decision", "architecture", "bugfix", "pattern", "config", "preference", "discovery"]))
@click.option("--content", required=True, help="Observation content")
@click.option("--project", help="Project name")
@click.option("--scope", default="project", help="Scope: project or global")
@click.option("--topic", help="Topic key for upserts")
def save(title: str, obs_type: str, content: str, project: str | None, scope: str, topic: str | None):
    """Save an observation to persistent memory."""
    init_db()
    result = save_observation(title, obs_type, content, project, scope, topic)
    click.echo(json.dumps(result))


@cli.command()
@click.argument("query")
@click.option("--limit", default=20, help="Max results")
@click.option("--type", help="Filter by type")
def search(query: str, limit: int, type: str | None):
    """Search observations."""
    init_db()
    results = search_observations(query, limit, type)
    click.echo(json.dumps(results, indent=2, default=str))


@cli.command()
@click.option("--project", required=True, help="Project name")
@click.option("--limit", default=20, help="Max results")
def context(project: str, limit: int):
    """Get context for session recovery."""
    init_db()
    results = get_context(project, limit)
    click.echo(json.dumps(results, indent=2, default=str))


@cli.command()
@click.option("--retention-days", default=90, help="Days to keep")
def cleanup(retention_days: int):
    """Clean up old observations."""
    init_db()
    removed = cleanup_old_observations(retention_days)
    click.echo(json.dumps({"removed": removed}))


@cli.command()
def init():
    """Initialize persistent memory database."""
    init_db()
    click.echo(json.dumps({"status": "initialized", "db": str(get_db_path())}))


def main() -> int:
    """Main entry point for tick/event triggers."""
    # Auto-capture logic runs here
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] != "entry.py":
        cli()
    else:
        sys.exit(main())