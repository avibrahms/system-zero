from __future__ import annotations

import json
from pathlib import Path
import sys

import click

from sz.interfaces import llm


@click.group(help="LLM interface (Constrained LLM Call discipline).")
def group() -> None:
    """Invoke the configured LLM provider."""


@group.command(name="invoke")
@click.option("--prompt-file", type=click.Path(exists=True, dir_okay=False))
@click.option("--prompt", default=None)
@click.option("--model", default=None)
@click.option("--max-tokens", type=int, default=1024, show_default=True)
@click.option(
    "--schema",
    "schema_path",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="JSON Schema for the response. If set, applies CLC discipline.",
)
@click.option("--template-id", default=None)
def _invoke(
    prompt_file: str | None,
    prompt: str | None,
    model: str | None,
    max_tokens: int,
    schema_path: str | None,
    template_id: str | None,
) -> None:
    if prompt_file:
        prompt = Path(prompt_file).read_text(encoding="utf-8")
    if not prompt:
        prompt = sys.stdin.read()
    try:
        result = llm.invoke(
            prompt,
            model=model,
            max_tokens=max_tokens,
            schema_path=Path(schema_path) if schema_path else None,
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
