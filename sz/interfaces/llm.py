"""Vendor-neutral LLM interface with Constrained LLM Call validation."""
from __future__ import annotations

import hashlib
import importlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
import yaml

from sz.core import paths, repo_config, util
from sz.interfaces import memory


@dataclass
class LLMResult:
    text: str
    parsed: Any
    tokens_in: int
    tokens_out: int
    model: str
    provider: str


@dataclass
class ProviderResolution:
    provider: str
    source: str
    reason: str
    priority: list[str]
    candidates: list[dict[str, Any]]


SUPPORTED_PROVIDERS = {
    "codex",
    "claude_code",
    "openai",
    "anthropic",
    "groq",
    "mock",
}
DEFAULT_PROVIDER_PRIORITY = [
    "codex",
    "claude_code",
    "openai",
    "anthropic",
    "groq",
    "mock",
]


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


def _repo_runtime_config(start: Path | None = None) -> dict[str, Any]:
    try:
        root = paths.repo_root(start)
    except FileNotFoundError:
        return {}
    try:
        return repo_config.read(root)
    except Exception:
        return {}


def _provider_from_config(config: dict[str, Any]) -> str | None:
    nested = config.get("providers")
    if isinstance(nested, dict) and nested.get("llm"):
        return str(nested["llm"]).strip().lower()
    if config.get("llm_provider"):
        return str(config["llm_provider"]).strip().lower()
    return None


def _priority_from_config(config: dict[str, Any]) -> list[str]:
    nested = config.get("providers")
    raw = None
    if isinstance(nested, dict):
        raw = nested.get("llm_priority")
    if raw is None:
        raw = config.get("llm_provider_priority")
    if isinstance(raw, str):
        raw = [part.strip().lower() for part in raw.split(",")]
    if not isinstance(raw, list):
        return []
    ordered: list[str] = []
    for item in raw:
        name = str(item).strip().lower()
        if name in SUPPORTED_PROVIDERS and name not in ordered:
            ordered.append(name)
    return ordered


def _configured_provider(start: Path | None = None) -> tuple[str | None, str | None]:
    if os.environ.get("SZ_LLM_PROVIDER"):
        return os.environ["SZ_LLM_PROVIDER"].strip().lower(), "env"
    repo_cfg = _repo_runtime_config(start)
    configured = _provider_from_config(repo_cfg)
    if configured:
        return configured, "repo_config"
    user_cfg = _user_config()
    configured = _provider_from_config(user_cfg)
    if configured:
        return configured, "user_config"
    return None, None


def _configured_priority(start: Path | None = None) -> tuple[list[str], str | None]:
    if os.environ.get("SZ_LLM_PROVIDER_PRIORITY"):
        priority = [
            part.strip().lower()
            for part in os.environ["SZ_LLM_PROVIDER_PRIORITY"].split(",")
            if part.strip()
        ]
        return [name for name in priority if name in SUPPORTED_PROVIDERS], "env"
    repo_cfg = _repo_runtime_config(start)
    priority = _priority_from_config(repo_cfg)
    if priority:
        return priority, "repo_config"
    user_cfg = _user_config()
    priority = _priority_from_config(user_cfg)
    if priority:
        return priority, "user_config"
    return [], None


def _provider_module(provider_name: str):
    return importlib.import_module(f"sz.interfaces.llm_providers.{provider_name}")


def _probe_provider(provider_name: str) -> dict[str, Any]:
    provider = _provider_module(provider_name)
    if hasattr(provider, "probe"):
        probed = provider.probe()
        if isinstance(probed, dict):
            return {
                "provider": provider_name,
                "available": bool(probed.get("available")),
                "reason": str(probed.get("reason") or ""),
                "source": str(probed.get("source") or ""),
            }
    return {
        "provider": provider_name,
        "available": True,
        "reason": "provider has no explicit probe and is assumed available",
        "source": "implicit",
    }


def resolve_provider(start: Path | None = None) -> ProviderResolution:
    configured, configured_source = _configured_provider(start)
    priority, priority_source = _configured_priority(start)
    if not priority:
        priority = list(DEFAULT_PROVIDER_PRIORITY)
    else:
        for provider_name in DEFAULT_PROVIDER_PRIORITY:
            if provider_name not in priority:
                priority.append(provider_name)

    if configured and configured != "auto":
        if configured not in SUPPORTED_PROVIDERS:
            return ProviderResolution(
                provider="mock",
                source=configured_source or "configured",
                reason=f"unsupported configured provider `{configured}`; falling back to mock",
                priority=priority,
                candidates=[],
            )
        candidate = _probe_provider(configured)
        if candidate["available"]:
            return ProviderResolution(
                provider=configured,
                source=configured_source or "configured",
                reason=candidate["reason"] or "configured provider available",
                priority=priority,
                candidates=[candidate],
            )
        return ProviderResolution(
            provider="mock",
            source=configured_source or "configured",
            reason=f"configured provider `{configured}` unavailable: {candidate['reason'] or 'probe failed'}; falling back to mock",
            priority=priority,
            candidates=[candidate],
        )

    candidates = [_probe_provider(provider_name) for provider_name in priority]
    for candidate in candidates:
        if candidate["available"]:
            selection_source = configured_source or priority_source or "auto"
            if candidate["provider"] == "mock":
                reason = candidate["reason"] or "no paid or subscription-backed provider available"
            else:
                reason = candidate["reason"] or "first available provider in priority order"
            return ProviderResolution(
                provider=candidate["provider"],
                source=selection_source,
                reason=reason,
                priority=priority,
                candidates=candidates,
            )
    return ProviderResolution(
        provider="mock",
        source=configured_source or priority_source or "auto",
        reason="no provider probe reported available; falling back to mock",
        priority=priority,
        candidates=candidates,
    )


def selected_provider(start: Path | None = None) -> str:
    return resolve_provider(start).provider


def provider_status(start: Path | None = None) -> dict[str, Any]:
    return asdict(resolve_provider(start))


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
