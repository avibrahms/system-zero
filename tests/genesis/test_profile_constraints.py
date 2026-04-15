from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


def _schema() -> dict:
    return json.loads((Path(__file__).resolve().parents[2] / "spec/v0.1.0/repo-profile.schema.json").read_text())


def _profile(*, existing_heartbeat: str = "none", modules: list[dict] | None = None) -> dict:
    return {
        "purpose": "A constrained test repo",
        "language": "python",
        "frameworks": [],
        "existing_heartbeat": existing_heartbeat,
        "goals": ["Run autonomously"],
        "recommended_modules": modules
        if modules is not None
        else [
            {"id": "heartbeat", "reason": "Start the owned pulse."},
            {"id": "immune", "reason": "Detect regressions."},
            {"id": "subconscious", "reason": "Summarize health."},
        ],
        "risk_flags": [],
    }


def _errors(profile: dict) -> list[str]:
    return [error.message for error in Draft202012Validator(_schema()).iter_errors(profile)]


def test_repo_profile_schema_requires_three_to_five_recommended_modules() -> None:
    errors = _errors(
        _profile(
            modules=[
                {"id": "heartbeat", "reason": "Start the owned pulse."},
            ]
        )
    )

    assert any("too short" in error for error in errors)


def test_repo_profile_schema_requires_heartbeat_first_for_static_repos() -> None:
    errors = _errors(
        _profile(
            modules=[
                {"id": "immune", "reason": "Detect regressions."},
                {"id": "heartbeat", "reason": "Start the owned pulse."},
                {"id": "subconscious", "reason": "Summarize health."},
            ]
        )
    )

    assert any("'heartbeat' was expected" in error for error in errors)


def test_repo_profile_schema_rejects_heartbeat_for_dynamic_repos() -> None:
    errors = _errors(
        _profile(
            existing_heartbeat="hermes",
            modules=[
                {"id": "immune", "reason": "Detect regressions."},
                {"id": "heartbeat", "reason": "Start the owned pulse."},
                {"id": "subconscious", "reason": "Summarize health."},
            ],
        )
    )

    assert any("should not be valid" in error for error in errors)


def test_repo_profile_schema_accepts_dynamic_repos_without_heartbeat() -> None:
    errors = _errors(
        _profile(
            existing_heartbeat="unknown",
            modules=[
                {"id": "immune", "reason": "Detect regressions."},
                {"id": "subconscious", "reason": "Summarize health."},
                {"id": "prediction", "reason": "Predict next events."},
            ],
        )
    )

    assert errors == []
