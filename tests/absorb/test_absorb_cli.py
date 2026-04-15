from __future__ import annotations

import subprocess as subprocess_module

from click.testing import CliRunner

from sz.commands import absorb as absorb_command


def test_absorb_cli_doctor_failure_prints_notes_and_prompts_for_rollback(monkeypatch) -> None:
    def fake_absorb(source, feature, *, ref, module_id, dry_run):
        return {
            "installed": "bad-module",
            "staging": "/tmp/staging/bad-module",
            "notes": "Wrapped source file and generated a thin entrypoint.",
        }

    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if args[:2] == ["sz", "doctor"]:
            return subprocess_module.CompletedProcess(args, 1, stdout="doctor out\n", stderr="doctor err\n")
        if args[:2] == ["sz", "uninstall"]:
            return subprocess_module.CompletedProcess(args, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected subprocess call: {args}")

    monkeypatch.setattr(absorb_command.engine, "absorb", fake_absorb)
    monkeypatch.setattr(absorb_command.subprocess, "run", fake_run)

    result = CliRunner().invoke(absorb_command.cmd, ["source", "--feature", "feature"], input="y\n")

    assert result.exit_code == 2
    assert "LLM draft notes: Wrapped source file and generated a thin entrypoint." in result.output
    assert "doctor out" in result.output
    assert "doctor err" in result.output
    assert "Roll back absorbed module?" in result.output
    assert ["sz", "uninstall", "bad-module", "--confirm"] in calls
