"""Vendor-neutral LLM interface with Constrained LLM Call validation."""
from __future__ import annotations

import hashlib
import importlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
import yaml

from sz.core import paths, util
from sz.interfaces import memory


@dataclass
class LLMResult:
    text: str
    parsed: Any
    tokens_in: int
    tokens_out: int
    model: str
    provider: str


class CLCFailure(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("Constrained LLM Call failed validation.")
        self.errors = errors


def _user_config() -> dict[str, Any]:
    config_path = paths.user_config_dir() / "config.yaml"
    if not config_path.exists():
        return {}
    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return loaded if isinstance(loaded, dict) else {}


def _configured_provider() -> str | None:
    if os.environ.get("SZ_LLM_PROVIDER"):
        return os.environ["SZ_LLM_PROVIDER"].strip().lower()
    config = _user_config()
    nested = config.get("providers")
    if isinstance(nested, dict) and nested.get("llm"):
        return str(nested["llm"]).strip().lower()
    if config.get("llm_provider"):
        return str(config["llm_provider"]).strip().lower()
    return None


def selected_provider() -> str:
    configured = _configured_provider()
    if configured in {"anthropic", "groq", "openai", "mock"}:
        return configured
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("GROQ_API_KEY"):
        return "groq"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "mock"


def _provider_module(provider_name: str):
    return importlib.import_module(f"sz.interfaces.llm_providers.{provider_name}")


def _call_provider(prompt: str, *, model: str | None, max_tokens: int) -> Any:
    provider_name = selected_provider()
    provider = _provider_module(provider_name)
    response = provider.call(prompt, model=model, max_tokens=max_tokens)
    setattr(response, "provider", provider_name)
    return response


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        body = lines[1:-1]
        return "\n".join(body).strip()
    return stripped


def _parse_json_envelope(text: str) -> Any:
    stripped = _strip_code_fence(text)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    for opener, closer in (("{", "}"), ("[", "]")):
        start = stripped.find(opener)
        end = stripped.rfind(closer)
        if start != -1 and end != -1 and end > start:
            return json.loads(stripped[start : end + 1])
    raise ValueError("response did not contain a JSON object or array")


def _format_error_path(error) -> str:
    if not error.absolute_path:
        return "$"
    return "$." + ".".join(str(item) for item in error.absolute_path)


def _load_schema(schema_path: Path) -> Any:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return _resolve_local_refs(schema)


def _resolve_local_refs(value: Any) -> Any:
    if isinstance(value, list):
        return [_resolve_local_refs(item) for item in value]
    if not isinstance(value, dict):
        return value

    ref = value.get("$ref")
    if isinstance(ref, str) and ref.startswith("https://systemzero.dev/spec/v0.1.0/"):
        rel = ref.removeprefix("https://systemzero.dev/spec/v0.1.0/")
        ref_path = util.repo_base() / "spec" / "v0.1.0" / rel
        resolved = json.loads(ref_path.read_text(encoding="utf-8"))
        siblings = {key: item for key, item in value.items() if key != "$ref"}
        if siblings:
            resolved.update(siblings)
        return _resolve_local_refs(resolved)

    return {key: _resolve_local_refs(item) for key, item in value.items()}


def _log_call(
    template_id: str | None,
    text: str,
    *,
    attempts: int,
    validation_status: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
) -> None:
    try:
        root = paths.repo_root()
    except FileNotFoundError:
        return
    memory.append(
        root,
        "llm.calls",
        {
            "ts": util.utc_now(),
            "template_id": template_id,
            "response_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "attempts": attempts,
            "validation_status": validation_status,
            "model": model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        },
    )


def invoke(
    prompt: str,
    *,
    model: str | None = None,
    max_tokens: int = 1024,
    schema_path: Path | None = None,
    template_id: str | None = None,
) -> LLMResult:
    if schema_path is None:
        response = _call_provider(prompt, model=model, max_tokens=max_tokens)
        return LLMResult(
            text=response.text,
            parsed=None,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            model=response.model,
            provider=response.provider,
        )

    schema = _load_schema(schema_path)
    validator = Draft202012Validator(schema)
    feedback = ""
    errors: list[str] = []
    response = None

    for attempt in range(1, 4):
        response = _call_provider(prompt + feedback, model=model, max_tokens=max_tokens)
        try:
            parsed = _parse_json_envelope(response.text)
        except Exception as exc:
            errors = [f"not JSON: {exc}"]
        else:
            validation_errors = list(validator.iter_errors(parsed))
            if not validation_errors:
                _log_call(
                    template_id,
                    response.text,
                    attempts=attempt,
                    validation_status="ok",
                    model=response.model,
                    tokens_in=response.tokens_in,
                    tokens_out=response.tokens_out,
                )
                return LLMResult(
                    text=response.text,
                    parsed=parsed,
                    tokens_in=response.tokens_in,
                    tokens_out=response.tokens_out,
                    model=response.model,
                    provider=response.provider,
                )
            errors = [
                f"{_format_error_path(error)}: {error.message}"
                for error in validation_errors
            ]
        if attempt < 3:
            feedback = (
                f"\n\n[VALIDATION_ERROR] retry {attempt + 1}:\n"
                + "\n".join(errors)
            )

    if response is not None:
        _log_call(
            template_id,
            response.text,
            attempts=3,
            validation_status="failed",
            model=response.model,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
        )
    raise CLCFailure(errors)
