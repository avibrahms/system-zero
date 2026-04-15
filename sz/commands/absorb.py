from __future__ import annotations

import json
import subprocess
import sys

import click

from sz.core import util
from sz.core import absorb as engine


@click.command(help="Absorb a feature from an open-source repo as an S0 module.")
@click.argument("source")
@click.option("--feature", required=True)
@click.option("--ref", default=None)
@click.option("--id", "module_id", default=None)
@click.option("--dry-run", is_flag=True)
@click.option("--auto-rollback", is_flag=True)
def cmd(source, feature, ref, module_id, dry_run, auto_rollback):
    try:
        result = engine.absorb(source, feature, ref=ref, module_id=module_id, dry_run=dry_run)
    except Exception as e:
        click.echo(f"absorb failed: {e}", err=True)
        sys.exit(1)
    if not dry_run:
        r = subprocess.run(util.sz_command("doctor", result["installed"]), capture_output=True, text=True)
        if r.returncode != 0:
            click.echo("doctor failed after absorb", err=True)
            notes = result.get("notes")
            if notes:
                click.echo(f"LLM draft notes: {notes}", err=True)
            if r.stdout.strip():
                click.echo(r.stdout.strip(), err=True)
            if r.stderr.strip():
                click.echo(r.stderr.strip(), err=True)
            if auto_rollback:
                click.echo("rolling back absorbed module", err=True)
                subprocess.run(util.sz_command("uninstall", result["installed"], "--confirm"), check=False)
            elif click.confirm("Roll back absorbed module?", default=False):
                subprocess.run(util.sz_command("uninstall", result["installed"], "--confirm"), check=False)
            else:
                click.echo("leaving absorbed module installed for inspection", err=True)
            sys.exit(2)
    click.echo(json.dumps(result, indent=2))
