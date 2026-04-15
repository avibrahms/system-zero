from __future__ import annotations

import json
from pathlib import Path
import re
import sys

import click

from sz.core import util
from sz.interfaces import llm

_TEMPLATE_PLACEHOLDER = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


@click.group(help="LLM interface (Constrained LLM Call discipline).")
def group() -> None:
    """Invoke the configured LLM provider."""


def _template_path(template_id: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", template_id):
        raise click.ClickException(f"Invalid template id: {template_id}")
    templates_dir = Path(__file__).resolve().parents[1] / "templates"
    candidates = [
        templates_dir / f"{template_id.replace('-', '_')}_prompt.md",
        templates_dir / f"{template_id}.md",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise click.ClickException(f"No prompt template found for template id: {template_id}")


def _schema_path(raw: str | None) -> Path | None:
    if raw is None:
        return None
    candidate = Path(raw)
    if candidate.exists():
        return candidate
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", raw):
        raise click.ClickException(f"Schema path does not exist: {raw}")
    resolved = util.repo_base() / "spec" / "v0.1.0" / "llm-responses" / f"{raw}.schema.json"
    if not resolved.exists():
        raise click.ClickException(f"No LLM response schema found for schema id: {raw}")
    return resolved


def _parse_assignment(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise click.ClickException(f"Template variable must be KEY=VALUE: {raw}")
    key, value = raw.split("=", 1)
    if not re.fullmatch(r"[A-Z0-9_]+", key):
        raise click.ClickException(f"Invalid template variable name: {key}")
    return key, value


def _render_template(template_id: str, template_vars: tuple[str, ...], template_var_files: tuple[str, ...]) -> str:
    values: dict[str, str] = {}
    for raw in template_vars:
        key, value = _parse_assignment(raw)
        values[key] = value
    for raw in template_var_files:
        key, value = _parse_assignment(raw)
        values[key] = Path(value).read_text(encoding="utf-8")

    prompt = _template_path(template_id).read_text(encoding="utf-8")
    for key, value in values.items():
        prompt = prompt.replace(f"{{{{{key}}}}}", value)

    unresolved = sorted(set(_TEMPLATE_PLACEHOLDER.findall(prompt)))
    if unresolved:
        raise click.ClickException(f"Unresolved template variables: {', '.join(unresolved)}")
    return prompt


@group.command(name="invoke")
@click.option("--prompt-file", type=click.Path(exists=True, dir_okay=False))
@click.option("--prompt", default=None)
@click.option("--model", default=None)
@click.option("--max-tokens", type=int, default=1024, show_default=True)
@click.option(
    "--schema",
    "schema_path",
    type=click.Path(exists=False, dir_okay=False),
    default=None,
    help="JSON Schema path or schema id under spec/v0.1.0/llm-responses. If set, applies CLC discipline.",
)
@click.option("--template-id", default=None)
@click.option("--template-var", "template_vars", multiple=True, help="Template substitution as KEY=VALUE.")
@click.option("--template-var-file", "template_var_files", multiple=True, help="Template substitution as KEY=PATH.")
def _invoke(
    prompt_file: str | None,
    prompt: str | None,
    model: str | None,
    max_tokens: int,
    schema_path: str | None,
    template_id: str | None,
    template_vars: tuple[str, ...],
    template_var_files: tuple[str, ...],
) -> None:
    if prompt_file:
        prompt = Path(prompt_file).read_text(encoding="utf-8")
    elif template_id:
        prompt = _render_template(template_id, template_vars, template_var_files)
    if not prompt:
        prompt = sys.stdin.read()
    try:
        result = llm.invoke(
            prompt,
            model=model,
            max_tokens=max_tokens,
            schema_path=_schema_path(schema_path),
            template_id=template_id,
        )
    except llm.CLCFailure as exc:
        click.echo(json.dumps({"error": "clc_failed", "details": exc.errors}), err=True)
        raise SystemExit(2)
    click.echo(
        json.dumps(
            {
                "text": result.text,
                "parsed": result.parsed,
                "tokens_in": result.tokens_in,
                "tokens_out": result.tokens_out,
                "model": result.model,
                "provider": result.provider,
            },
            ensure_ascii=False,
        )
    )


@group.command(name="provider")
def _provider() -> None:
    click.echo(llm.selected_provider())
